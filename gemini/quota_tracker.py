"""
Rastreamento de cota diária (RPD — requests per day) por modelo, no free
tier do Gemini. A API não expõe endpoint de saldo/quote (só o console/AI
Studio, fora da API) — os limites abaixo são cadastrados manualmente e
podem ficar desatualizados se o Google mudar o free tier. Confira em
ai.google.dev/gemini-api/docs/rate-limits antes de confiar cegamente
nesses números.

Só RPD é rastreado (persistente, por dia civil). RPM/RPS não — é uma
janela curta demais pra fazer sentido persistir entre execuções do
script; se algum dia isso for necessário, cabe como contador em memória
separado, não aqui.

Cada tentativa REAL de request à API conta contra a cota, mesmo que
falhe (erro 400/500) — mesmo critério documentado pelo Google. Por isso
o registro acontece no ponto onde o request de fato é disparado
(gemini/client.py::_create_interaction), não só em caso de sucesso.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional
from gemini.config import DEFAULT_QUOTA_PATH
logger = logging.getLogger("gemini_client")

# Limites de RPD (requests por dia) do free tier, por modelo. None/ausente
# = sem limite cadastrado -> não é bloqueado localmente (o Google ainda
# aplica o limite real do lado dele, só não temos visibilidade local).
# Os valores abaixo foram obtidos por mim dia 02/09/2026 — confirme o RPD real de CADA modelo na doc 
# antes de confiar neles, os limites podem variar por modelo e data.
RATE_LIMITS_RPD: dict[str, int] = {
    "gemini-3.6-flash": 20,
    "gemini-3.5-flash": 20,
    "gemini-3.5-flash-lite": 20,
    "gemini-3-flash": 20,
    "gemini-3.1-flash-lite": 20,
    "gemini-2.5-flash": 20,
    "gemini-2.5-flash-lite": 20,
}

class QuotaTracker:
    """
    Contador persistente (JSON) de chamadas por modelo, resetado por dia
    civil (data local da máquina, formato YYYY-MM-DD). O arquivo em disco
    só guarda o dia atual — dias anteriores são descartados no load, não
    tem propósito de histórico aqui (isso já existe em
    gemini_usage_log.jsonl, se algum dia for necessário).
    """

    def __init__(self, path: Path | str = DEFAULT_QUOTA_PATH):
        self.path = Path(path)
        self._data: dict[str, dict[str, int]] = self._load()

    def _today(self) -> str:
        return time.strftime("%Y-%m-%d")

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            with open(self.path, 'r', encoding = 'utf-8') as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Falha ao ler {self.path}: {e}. Resetando cota.")
            return {}

        today = self._today()
        return {today: raw.get(today, {})}  # só mantém o dia atual

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents = True, exist_ok = True)
            with open(self.path, 'w', encoding = 'utf-8') as f:
                json.dump(self._data, f, ensure_ascii = False, indent = 2)
        except OSError as e:
            logger.warning(f"Falha ao salvar {self.path}: {e}. Cota não persistida.")

    def _counts_today(self) -> dict[str, int]:
        today = self._today()
        if today not in self._data:
            #O dia virou desde o ultimo load
            self._data = {today: {}}
        return self._data[today]

    def register_call(self, model: str) -> None:
        """
        Registra uma tentativa de request à API para o modelo especificado, mesmo se a chamada falhar.
        Se o modelo não tiver limite cadastrado, é registrado mas não há bloqueio local 
        (o Google ainda aplica o limite real do lado dele).
        """
        counts = self._counts_today()
        counts[model] = counts.get(model, 0) + 1
        self._save()

    def used_today(self, model: str) -> int:
        return self._counts_today().get(model, 0)

    def limit(self, model: str) -> Optional[int]:
        return RATE_LIMITS_RPD.get(model)

    def remainig_today(self, model: str) -> Optional[int]:
        """None = modelo sem limite cadastrado (não rastreado localmente)"""
        limit = self.limit(model)
        if limit is None:
            return None
        return max(0, limit - self.used_today(model))

    def is_exhausted(self, model: str) -> bool:
        remainig = self.remainig_today(model)
        return remainig is not None and remainig <= 0

    def summary(self) -> list[dict]:
        """Um item por modelo cadastrado em RATE_LIMITS_RPD — usado por /quote."""
        return [
            {
                "model": model,
                "used": self.used_today(model),
                "limit": limit,
                "remaining": max(0, limit - self.used_today(model)),
            }
            for model, limit in RATE_LIMITS_RPD.items()
        ]

    def reset(self, model: Optional[str] = None) -> None:
        """Uso exclusivo para testes — zera o contador do dia atual (todo ou de um modelo)."""
        counts = self._counts_today()
        if model is None:
            counts.clear()
        else:
            counts.pop(model, None)
        self._save()