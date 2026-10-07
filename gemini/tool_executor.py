"""
Execução de tool calls solicitadas pelo Gemini: resolve a ToolPolicy, aplica
timeout (exceto para tools de confirmação — ver nota abaixo), trata exceções
e mantém o rastreamento de arquivos criados/gerados durante a sessão.

Isolado do GeminiClient para que o ciclo de vida do ThreadPoolExecutor
pertença a quem de fato o usa, e para que a política de execução de cada
tool (timeout, confirmação, restrição de sessão) fique num único lugar
testável isoladamente.
"""

# TODO: priorizar timeouts nativos para HTTP, banco de dados e subprocessos.
# future.result(timeout=...) interrompe apenas a espera; uma função que já
# começou continua executando em background mesmo após o timeout do executor.

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logger = logging.getLogger("gemini_client")

@dataclass
class ToolExecutionContext:
    """
    Estado de arquivos ligado a tools, com dois ciclos de vida distintos
    intencionalmente reunidos num único objeto:

      - created_files: arquivos criados via create_file. Vive durante toda
        a sessão do client — NÃO deve ser resetado entre chamadas de
        generate() (um script criado numa chamada continua executável em
        chamadas seguintes da mesma sessão).
      - generated_files: arquivos gerados por tools de plotagem NESTA
        chamada de generate(). Deve ser reiniciado a cada tentativa dentro
        do loop de retry de generate() — quem orquestra (GeminiClient) é
        responsável por fazer `context.generated_files = []` no início de
        cada tentativa.
    """
    created_files: set[Path] = field(default_factory=set)
    generated_files: list[Path] = field(default_factory=list)

class ToolExecutor:
    """
    policies: TOOL_POLICIES (tools/registry.py) — única fonte de verdade
        sobre função, confirmação, timeout e roteamento de cada tool.
    emit_activity: callable injetado (ex: ActivityRecorder.emit) — o
        executor não conhece ActivityRecorder, só a assinatura
        (event_type, message, **kwargs) -> ActivityEvent.
    default_timeout: usado quando policy.timeout_seconds é None
        (MAX_TOOL_EXEC_SECONDS, em gemini/config.py).
    """

    def __init__(
            self, 
            policies: dict, 
            emit_activity: Callable[..., object],
            default_timeout: float,
            max_workers: int = 4 
    ):
        self.policies = policies
        self._emit_activity = emit_activity
        self.default_timeout = default_timeout
        self._pool = ThreadPoolExecutor(max_workers=max_workers)

    def close(self, wait: bool = True) -> None:
        """Encerra o pool e impede o envio de novas execuções.

        ``wait=False`` não mata funções que já começaram; apenas evita esperar
        por elas aqui e cancela futures ainda não iniciados.
        """
        self._pool.shutdown(wait=wait, cancel_futures=True)

    def __enter__(self) -> "ToolExecutor":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def execute(self, step, context: ToolExecutionContext) -> object:
        tool_name = step.name
        arguments = step.arguments or {}
        started_at = time.perf_counter()
        self._emit_activity(
            'tool_started',
            f'Executando {tool_name}',
            tool = tool_name
        )

        logger.info("Gemini solicitou ferramenta '%s' com argumentos: %s", tool_name, arguments)

        policy = self.policies.get(tool_name)
        if policy is None:
            self._emit_activity(
                "tool_failed",
                f"Ferramenta {tool_name} nao registrada",
                tool=tool_name,
                duration=time.perf_counter() - started_at,
            )
            return {
                "error": (
                    f"Ferramenta '{tool_name}' não está registrada. "
                    f"Disponíveis: {list(self.policies)}"
                )
            }

        function = policy.function

        try:
            # Restrição de sessão (ex: run_script só executa arquivo criado nesta sessão via create_file) — ver ToolPolicy.requires_session_created_file.
            if policy.requires_session_created_file:
                path_argument = policy.requires_session_created_file
                requested_path = Path(arguments.get(path_argument, "")).resolve()

                if requested_path not in context.created_files:
                    self._emit_activity(
                        "tool_failed",
                        f"Execucao de {tool_name} bloqueada pela politica de seguranca",
                        tool=tool_name,
                        duration=time.perf_counter() - started_at,
                    )
                    return {
                        "error": (
                            f"Execução bloqueada. '{tool_name}' só aceita um "
                            "arquivo registrado por uma ferramenta autorizada "
                            f"nesta sessão (argumento '{path_argument}')."
                        )
                    }

            if policy.requires_confirmation:
                # Sem wrapper de timeout — o confirm_action/confirm_action_typed de dentro da função espera o humano, e não há como interromper essa espera sem risco de execução "fantasma" concorrente.
                result = function(**arguments)
            else:
                timeout = (
                    policy.timeout_seconds
                    if policy.timeout_seconds is not None
                    else self.default_timeout
                )
                future = self._pool.submit(function, **arguments)
                try:
                    result = future.result(timeout=timeout)
                except FutureTimeoutError:
                    future.cancel()
                    logger.warning(
                        "Ferramenta '%s' excedeu %ds e foi abandonada (a "
                        "execução pode continuar rodando em background).",
                        tool_name, timeout,
                    )
                    self._emit_activity(
                        "tool_failed",
                        f"Ferramenta {tool_name} excedeu {timeout}s",
                        tool=tool_name,
                        duration=time.perf_counter() - started_at,
                    )
                    return {
                        "error": (
                            f"A ferramenta '{tool_name}' excedeu o tempo limite de "
                            f"execução ({timeout}s) e a espera foi abandonada. "
                            "Considere refinar o filtro/parâmetros para reduzir o "
                            "volume de dados processado."
                        )
                    }

            logger.info("Ferramenta '%s' executada com sucesso.", tool_name)
            self._emit_activity(
                "tool_completed",
                f"Ferramenta {tool_name} concluida",
                tool=tool_name,
                duration=time.perf_counter() - started_at,
            )

            # Registra arquivos produzidos por policies autorizadas. O campo
            # que contém o caminho faz parte da policy, sem regra por nome.
            created_file_field = policy.registers_session_created_file
            if (
                created_file_field
                and isinstance(result, dict)
                and result.get("success")
                and result.get(created_file_field)
            ):
                created_path = Path(result[created_file_field]).resolve()
                context.created_files.add(created_path)
                logger.info("Arquivo criado nesta sessão registrado: %s", created_path)

            # Arquivos gerados por tools de plotagem, para propagar no GeminiResponse.
            if (policy.generate_file and isinstance(result, dict) and result.get("file_path")):
                file_path = Path(result["file_path"])
                context.generated_files.append(file_path)
                logger.info("Arquivo gerado por '%s' registrado: %s", tool_name, file_path)

            return result

        except Exception as e:
            logger.exception("Erro ao executar ferramenta '%s'.", tool_name)
            self._emit_activity(
                "tool_failed",
                f"Falha em {tool_name}: {e}",
                tool=tool_name,
                duration=time.perf_counter() - started_at,
            )
            return {"error": str(e)}
