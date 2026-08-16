import json
import logging
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
        self.session_id = session_id
        self.sessions_path = Path(sessions_path)
        self.messages: list[Message] = []
        self._last_interaction_id: Optional[str] = None

        if self.session_id:
            self._load()

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
        }

        try:
            with open(self.sessions_path, "w", encoding="utf-8") as f:
                json.dump(all_sessions, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("Não consegui salvar a sessão '%s' em disco: %s", self.session_id, e)
