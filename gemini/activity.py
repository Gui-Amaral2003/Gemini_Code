"""
Centraliza o registro de eventos operacionais (ActivityEvent) emitidos durante
generate() e a escrita do trace de tentativas individuais de chamada ao modelo
(gemini_trace_log.jsonl).

Isolado do GeminiClient para que o estado de "o que aconteceu na última
chamada" (last_activities) e o callback de UI (ex: ToolTimeline do terminal)
não fiquem misturados com orquestração de tools/modelo. Não tem lógica de
decisão própria — só registra o que é emitido por quem chama.
"""
import json
import logging
import time
from pathlib import Path
from typing import Callable, Optional
from .models import ActivityEvent

logger = logging.getLogger("gemini_client")


class ActivityRecorder:
    """
    Estado:
      - last_activities: eventos emitidos durante a execução ATUAL de
        generate() (reiniciado a cada chamada via reset()).
      - callback: consumidor opcional (ex: ToolTimeline) chamado de forma
        síncrona a cada emit(). Falha no callback é logada e engolida —
        nunca deve interromper o fluxo de generate() (mesmo comportamento
        do try/except que já existia em GeminiClient._emit_activity).

    trace_model_attempt() é uma responsabilidade separada de emit(): grava
    UMA linha por tentativa individual de chamada ao modelo dentro de
    _create_with_fallback (fase start/success/failure), sempre em disco,
    independente do nível do logger — usado só para diagnóstico de
    latência/hang, não é fonte de custo/tokens (isso é gemini_usage_log.jsonl).
    """

    def __init__(self, trace_log_path: Path | str):
        self.trace_log_path = Path(trace_log_path)
        self.last_activities: list[ActivityEvent] = []
        self._callback: Optional[Callable[[ActivityEvent], None]] = None

    def set_callback(self, callback: Optional[Callable[[ActivityEvent], None]]) -> None:
        """Registra (ou remove, com None) o consumidor dos eventos — mesmo padrão de confirmation.py."""
        self._callback = callback

    def reset(self) -> None:
        """Reinicia o histórico de eventos. Chamado no início de cada generate()."""
        self.last_activities = []

    def emit(self, event_type: str, message: str, **kwargs) -> ActivityEvent:
        """Cria, acumula e notifica um ActivityEvent. kwargs repassados direto ao dataclass (model, tool, stage, duration, details)."""
        event = ActivityEvent(
            type=event_type,
            message=message,
            timestamp=time.time(),
            **kwargs,
        )
        self.last_activities.append(event)
        if self._callback:
            try:
                self._callback(event)
            except Exception:
                logger.exception("Erro no callback de atividade; execução continuará.")
        return event

    def trace_model_attempt(
        self,
        *,
        call_id: str,
        stage: str,
        model: str,
        phase: str,
        error: Optional[str] = None,
    ) -> None:
        """
        Grava uma tentativa individual de chamada ao modelo em
        trace_log_path. stage identifica o ponto do fluxo de generate()
        ("initial", "tool_continuation", "cheap_synthesis",
        "strong_fallback"); phase é "start", "success" ou "failure".
        """
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "call_id": call_id,
            "stage": stage,
            "model": model,
            "phase": phase,
        }
        if error is not None:
            entry["error"] = error

        try:
            self.trace_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.trace_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except OSError as e:
            logger.warning("Não consegui gravar o log de rastreio em %s: %s", self.trace_log_path, e)
