import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from .config import DEFAULT_CACHE_PATH

logger = logging.getLogger("gemini_client")


class PromptCache:
    """
    Cache simples em disco (JSON) para respostas de prompts idênticos.
    Evita gastar chamada de novo quando você reexecuta o mesmo prompt —
    comum ao iterar em um system prompt e comparar resultado.

    A chave do cache inclui todos os parâmetros relevantes da chamada
    (model, system, prompt, previous_interaction_id, etc), então:
      - prompts em conversas (com previous_interaction_id) praticamente
        nunca repetem a chave, então nunca "colidem" indevidamente;
      - mudar o system prompt gera uma chave nova automaticamente.
    """

    def __init__(self, path: Path | str = DEFAULT_CACHE_PATH):
        self.path = Path(path)
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Cache corrompido ou ilegível (%s). Começando vazio.", e)
            return {}

    def _save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("Não consegui salvar o cache em %s: %s", self.path, e)

    @staticmethod
    def _make_key(**kwargs) -> str:
        serialized = json.dumps(kwargs, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get(self, **kwargs) -> Optional[dict]:
        return self._data.get(self._make_key(**kwargs))

    def set(self, value: dict, **kwargs) -> None:
        self._data[self._make_key(**kwargs)] = value
        self._save()

    def clear(self) -> None:
        self._data = {}
        self._save()

    def __len__(self) -> int:
        return len(self._data)
