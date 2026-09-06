import json
import logging
import time
from pathlib import Path
from typing import Optional

from .client import GeminiClient
from .config import DEFAULT_SESSIONS_PATH
from .models import GeminiResponse, Message

logger = logging.getLogger("gemini_client")


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
        response = self.client.generate(
            prompt=user_message,
            previous_interaction_id=self._last_interaction_id,
            system=self.system,
            **kwargs,
        )

        # Só grava no histórico se a chamada teve sucesso — assim, se der
        # erro (mesmo após os retries), a conversa não fica com uma
        # mensagem "órfã" do usuário sem resposta correspondente.
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
