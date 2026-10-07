import json
import logging
import time
from pathlib import Path
from typing import Optional

from google.genai import errors as genai_errors

from tools.confirmation import confirm_action

from .client import GeminiClient
from .config import DEFAULT_SESSIONS_PATH
from .models import GeminiResponse, Message

logger = logging.getLogger("gemini_client")

# Reconstrução de contexto quando o interaction_id some do servidor.

class ChatSession:
    """
    Representa uma conversa com histórico. O histórico de verdade é mantido
    pelo servidor via `previous_interaction_id` — este objeto guarda uma
    cópia local (self.messages) só para você exibir/inspecionar.

    Se `session_id` for informado, o `interaction_id` mais recente (e o
    histórico local) é salvo em disco a cada mensagem, num arquivo
    compartilhado por session_id (`sessions_path`). Isso permite retomar a
    MESMA conversa em uma execução futura do script — o vínculo de
    continuidade é o interaction_id, que vive no servidor do Gemini, não
    no processo Python. Sem session_id, a sessão só existe em memória e se
    perde quando o script termina (comportamento anterior).

    Se o servidor já descartou a interação (sessão antiga), send() oferece
    reconstruir o contexto a partir do histórico local — ver
    _build_replay_prompt() para o que se perde nessa reconstrução.
    """

    def __init__(
        self,
        client: GeminiClient,
        system_instruction: Optional[str] = None,
        session_id: Optional[str] = None,
        sessions_path: Path | str = DEFAULT_SESSIONS_PATH,
    ):
        self.client = client
        self.system = system_instruction
        self.session_id = (
            self.validate_session_id(session_id) if session_id is not None else None
        )
        self.sessions_path = Path(sessions_path)
        self.messages: list[Message] = []
        self._last_interaction_id: Optional[str] = None

        if self.session_id:
            self._load()

    @staticmethod
    def validate_session_id(session_id: str) -> str:
        """Normaliza um nome de sessao e rejeita valores dificeis de exibir."""
        normalized = session_id.strip()
        if not normalized:
            raise ValueError("O nome da sessao nao pode ser vazio.")
        if len(normalized) > 80:
            raise ValueError("O nome da sessao deve ter no maximo 80 caracteres.")
        if any(ord(char) < 32 for char in normalized):
            raise ValueError("O nome da sessao nao pode conter caracteres de controle.")
        return normalized

    @classmethod
    def list_sessions(cls, sessions_path: Path | str = DEFAULT_SESSIONS_PATH) -> list[dict]:
        """Lista sessoes persistidas, das mais recentes para as mais antigas."""
        path = Path(sessions_path)
        if not path.exists():
            return []
        try:
            with open(path, encoding="utf-8") as f:
                saved_sessions = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Nao consegui listar sessoes em %s: %s", path, e)
            return []
        if not isinstance(saved_sessions, dict):
            return []

        sessions = [
            {
                "session_id": session_id,
                "messages": len(data.get("messages", [])) if isinstance(data, dict) else 0,
                "updated_at": data.get("updated_at") if isinstance(data, dict) else None,
            }
            for session_id, data in saved_sessions.items()
        ]
        return sorted(
            sessions,
            key=lambda item: item["updated_at"] or "",
            reverse=True,
        )

    @classmethod
    def session_exists(
        cls, session_id: str, sessions_path: Path | str = DEFAULT_SESSIONS_PATH
    ) -> bool:
        normalized = cls.validate_session_id(session_id)
        return any(
            item["session_id"] == normalized
            for item in cls.list_sessions(sessions_path)
        )

    def persist(self) -> None:
        """Cria ou atualiza no disco inclusive uma sessao ainda vazia."""
        if not self.session_id:
            raise ValueError("Uma sessao sem nome nao pode ser persistida.")
        self._save()

    def send(self, user_message: str, **kwargs) -> GeminiResponse:
        """Envia uma mensagem e recebe a resposta, mantendo o histórico."""
        try:
            response = self.client.generate(
                prompt=user_message,
                previous_interaction_id=self._last_interaction_id,
                system=self.system,
                **kwargs,
            )
        except genai_errors.ClientError as error:
            if not self._confirm_replay(error):
                raise
            # Contexto do servidor perdido: manda o histórico local como texto,
            # sem previous_interaction_id. A resposta traz um interaction_id
            # novo, e as proximas mensagens voltam a continuar no servidor.
            response = self.client.generate(
                prompt=self._build_replay_prompt(user_message),
                previous_interaction_id=None,
                system=self.system,
                **kwargs,
            )

        # Só grava no histórico se a chamada teve sucesso — assim, se der
        # erro (mesmo após os retries), a conversa não fica com uma
        # mensagem "órfã" do usuário sem resposta correspondente.
        # Grava a mensagem ORIGINAL do usuário, nunca o prompt de reconstrução.
        self.messages.append(Message(role="user", text=user_message))
        self.messages.append(Message(role="model", text=response.text))
        self._last_interaction_id = response.interaction_id

        if self.session_id:
            self._save()

        return response

    def get_history(self) -> list[Message]:
        """Retorna o histórico local (cópia, para não permitir mutação externa)."""
        return self.messages.copy()

    def clear_history(self) -> None:
        """Limpa o histórico local, desvincula da conversa anterior e apaga do disco."""
        self.messages.clear()
        self._last_interaction_id = None
        if self.session_id:
            self._save()

    # ------------------------------------------------------------------- #
    # Reconstrução de contexto (interaction_id expirado no servidor)
    # ------------------------------------------------------------------- #

    @staticmethod
    def _looks_like_expired_interaction(error: Exception) -> bool:
        if getattr(error, "code", None) not in _EXPIRED_ERROR_CODES:
            return False
        text = str(error).lower()
        references_interaction = any(
            marker in text for marker in _INTERACTION_REFERENCE_MARKERS
        )
        describes_missing_state = any(
            marker in text for marker in _INTERACTION_STATE_MARKERS
        )
        return references_interaction and describes_missing_state

    def _confirm_replay(self, error: Exception) -> bool:
        """True se vale (e o usuário aceitou) reconstruir o contexto localmente."""
        if not self._last_interaction_id or not self.messages:
            return False  # nada para reconstruir
        if not self._looks_like_expired_interaction(error):
            return False  # outro erro de cliente (chave, parâmetro...) — propaga

        logger.warning("Interação anterior indisponível no servidor: %s", error)
        return confirm_action(
            "Não consegui continuar a conversa no servidor (a interação anterior "
            "pode ter expirado).\n\n"
            f"Reconstruir o contexto a partir das últimas {REPLAY_MAX_MESSAGES} "
            "mensagens do histórico local? Resultados de ferramentas (dados de "
            "planilhas, banco etc.) não fazem parte do histórico e não serão "
            "recuperados. As mensagens reenviadas consomem tokens de entrada."
        )

    def _build_replay_prompt(self, new_message: str) -> str:
        recent = self.messages[-REPLAY_MAX_MESSAGES:]
        lines = []
        for message in recent:
            speaker = "Usuário" if message.role == "user" else "Assistente"
            text = message.text
            if len(text) > REPLAY_MAX_CHARS_PER_MESSAGE:
                text = text[:REPLAY_MAX_CHARS_PER_MESSAGE] + " [...truncado]"
            lines.append(f"{speaker}: {text}")

        transcript = "\n\n".join(lines)
        return (
            "Esta conversa está sendo retomada: o contexto original foi perdido no "
            "servidor. Abaixo está a transcrição das mensagens mais recentes, só com "
            "o texto trocado (resultados de ferramentas não estão incluídos). Use-a "
            "como contexto e responda à nova mensagem do usuário.\n\n"
            f"--- Transcrição anterior ---\n{transcript}\n--- Fim da transcrição ---\n\n"
            f"Nova mensagem do usuário:\n{new_message}"
        )

    # ------------------------------------------------------------------- #
    # Persistência em disco (entre execuções diferentes do script)
    # ------------------------------------------------------------------- #

    def _load(self) -> None:
        if not self.sessions_path.exists():
            return
        try:
            with open(self.sessions_path, encoding="utf-8") as f:
                all_sessions = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Não consegui ler %s (%s). Começando sessão nova.", self.sessions_path, e)
            return

        saved = all_sessions.get(self.session_id)
        if saved is None:
            return  # session_id novo, ainda não existe em disco

        self._last_interaction_id = saved.get("last_interaction_id")
        self.messages = [Message(**m) for m in saved.get("messages", [])]
        logger.info(
            "Sessão '%s' retomada (%d mensagem(ns) no histórico local).",
            self.session_id, len(self.messages),
        )

    def _save(self) -> None:
        all_sessions = {}
        if self.sessions_path.exists():
            try:
                with open(self.sessions_path, encoding="utf-8") as f:
                    all_sessions = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass  # arquivo corrompido: sobrescreve do zero em vez de travar

        all_sessions[self.session_id] = {
            "last_interaction_id": self._last_interaction_id,
            "messages": [{"role": m.role, "text": m.text} for m in self.messages],
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        try:
            self.sessions_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.sessions_path, "w", encoding="utf-8") as f:
                json.dump(all_sessions, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("Não consegui salvar a sessão '%s' em disco: %s", self.session_id, e)
