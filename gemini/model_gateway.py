"""Acesso ao SDK Gemini com retry, quota local, trace e fallback de modelos."""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Callable, Optional

import httpx

from .exceptions import GeminiTimeoutError, ModelFallbackExhausted
from .rate_limits import RateLimitKind, classify_rate_limit

logger = logging.getLogger("gemini_client")

_TIMEOUT_HTTP_ERRORS = (httpx.TimeoutException, httpx.RemoteProtocolError)


@dataclass(frozen=True)
class ModelRequest:
    input: object
    tools: Optional[list] = None
    preferred_model: Optional[str] = None
    previous_interaction_id: Optional[str] = None
    system_instruction: Optional[str] = None
    generation_config: Optional[dict] = None
    call_id: Optional[str] = None
    stage: str = "unknown"


@dataclass(frozen=True)
class ModelCallResult:
    interaction: object
    model: str


class ModelGateway:
    """Executa chamadas de modelo sem conhecer cache, tools ou GeminiResponse."""

    def __init__(
        self,
        api_client,
        *,
        default_model: str,
        fallback_models: list[str],
        quota_tracker,
        emit_activity: Callable[..., object],
        trace_attempt: Callable[..., None],
        confirm_quota_override: Callable[[str], bool],
        request_timeout: float,
        max_rate_limit_retries: int = 2,
        sleep: Callable[[float], None] = time.sleep,
        random_jitter: Callable[[float, float], float] = random.uniform,
    ):
        self.api_client = api_client
        self.default_model = default_model
        self.fallback_models = list(fallback_models)
        self.quota = quota_tracker
        self._emit_activity = emit_activity
        self._trace_attempt = trace_attempt
        self._confirm_quota_override = confirm_quota_override
        self.request_timeout = request_timeout
        self.max_rate_limit_retries = max_rate_limit_retries
        self._sleep = sleep
        self._random_jitter = random_jitter

    def count_tokens(self, prompt: str, model: Optional[str] = None) -> int:
        selected_model = model or self.default_model
        result = self.api_client.models.count_tokens(
            model=selected_model,
            contents=prompt,
        )
        return result.total_tokens

    def create(self, request: ModelRequest) -> ModelCallResult:
        models_to_try = self._models_to_try(request.preferred_model)
        available_models = [
            model for model in models_to_try if not self.quota.is_exhausted(model)
        ]
        exhausted_models = [
            model for model in models_to_try if model not in available_models
        ]

        if exhausted_models:
            self._emit_activity(
                "models_skipped",
                "Modelos ignorados por cota local: " + ", ".join(exhausted_models),
                details={"models": exhausted_models},
            )
            logger.info(
                "Modelo(s) com cota diária estimada esgotada, pulando: %s",
                ", ".join(exhausted_models),
            )

        if not available_models:
            detail = ", ".join(
                f"{model} ({self.quota.used_today(model)}/{self.quota.limit(model)})"
                for model in models_to_try
            )
            message = (
                "⚠ Todos os modelos configurados atingiram a cota diária (RPD) "
                f"estimada localmente: {detail}.\n\n"
                "Isso é uma estimativa própria — a API do Gemini não expõe cota "
                "real, então pode estar desatualizada. Tentar mesmo assim?"
            )
            if not self._confirm_quota_override(message):
                raise RuntimeError(
                    "Cota diária estimada esgotada para todos os modelos "
                    "configurados. Operação cancelada pelo usuário."
                )
            available_models = models_to_try

        attempted_models = []
        last_error = None
        for model in available_models:
            attempted_models.append(model)
            self._emit_activity(
                "model_selected",
                f"Modelo selecionado: {model}",
                model=model,
                stage=request.stage,
            )
            if request.call_id:
                self._trace_attempt(
                    call_id=request.call_id,
                    stage=request.stage,
                    model=model,
                    phase="start",
                )
            try:
                interaction = self._create_for_model(model=model, request=request)
                if request.call_id:
                    self._trace_attempt(
                        call_id=request.call_id,
                        stage=request.stage,
                        model=model,
                        phase="success",
                    )
                return ModelCallResult(interaction=interaction, model=model)
            except Exception as error:
                last_error = error
                if request.call_id:
                    self._trace_attempt(
                        call_id=request.call_id,
                        stage=request.stage,
                        model=model,
                        phase="failure",
                        error=str(error),
                    )
                if classify_rate_limit(error).kind is RateLimitKind.NOT_RATE_LIMIT:
                    raise
                self._emit_activity(
                    "fallback_selected",
                    f"Limite de {model}; tentando o próximo modelo",
                    model=model,
                    stage=request.stage,
                )

        raise ModelFallbackExhausted(attempted_models, last_error) from last_error

    def _models_to_try(self, preferred_model: Optional[str]) -> list[str]:
        models = []
        for candidate in [preferred_model, self.default_model, *self.fallback_models]:
            if candidate and candidate not in models:
                models.append(candidate)
        return models

    def _create_for_model(self, *, model: str, request: ModelRequest):
        last_error = None
        for attempt in range(self.max_rate_limit_retries + 1):
            started_at = time.perf_counter()
            self._emit_activity(
                "api_attempt_started",
                f"Consultando {model} (tentativa {attempt + 1})",
                model=model,
                details={
                    "attempt": attempt + 1,
                    "max_attempts": self.max_rate_limit_retries + 1,
                },
            )
            try:
                kwargs = {
                    "model": model,
                    "input": request.input,
                    "tools": request.tools,
                    "previous_interaction_id": request.previous_interaction_id,
                    "timeout": self.request_timeout,
                }
                if request.system_instruction is not None:
                    kwargs["system_instruction"] = request.system_instruction
                if request.generation_config:
                    kwargs["generation_config"] = request.generation_config

                self.quota.register_call(model)
                interaction = self.api_client.interactions.create(**kwargs)
                self._emit_activity(
                    "api_attempt_completed",
                    f"Resposta recebida de {model}",
                    model=model,
                    duration=time.perf_counter() - started_at,
                    details={"attempt": attempt + 1},
                )
                return interaction
            except Exception as error:
                last_error = error
                self._emit_activity(
                    "api_attempt_failed",
                    f"Falha em {model}: {error}",
                    model=model,
                    duration=time.perf_counter() - started_at,
                    details={"attempt": attempt + 1},
                )
                if isinstance(error, _TIMEOUT_HTTP_ERRORS):
                    raise GeminiTimeoutError(
                        f"A chamada a {model} excedeu o timeout configurado "
                        f"({self.request_timeout}s) ou a conexão foi interrompida "
                        "pelo servidor antes de responder. Nenhuma nova tentativa "
                        "automática será feita."
                    ) from error

                rate_limit = classify_rate_limit(error)
                if rate_limit.kind is not RateLimitKind.TRANSIENT:
                    raise
                if attempt >= self.max_rate_limit_retries:
                    raise

                delay = rate_limit.retry_after_seconds
                if delay is None:
                    delay = min(2 ** attempt, 10) + self._random_jitter(0, 0.5)
                self._emit_activity(
                    "rate_limit_backoff",
                    f"Limite atingido em {model}; aguardando {delay:.2f}s antes de tentar de novo",
                    model=model,
                    duration=delay,
                )
                self._sleep(delay)

        raise last_error
