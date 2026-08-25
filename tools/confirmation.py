from typing import Callable, Optional

_confirm_callback: Optional[Callable[[str], bool]] = None
_confirm_typed_callback: Optional[Callable[[str, str], bool]] = None


def set_confirm_callback(callback: Optional[Callable[[str], bool]]) -> None:
    """Define (ou remove, com None) o callback de confirmação simples (s/N)."""
    global _confirm_callback
    _confirm_callback = callback


def set_confirm_typed_callback(callback: Optional[Callable[[str, str], bool]]) -> None:
    """Define (ou remove, com None) o callback de confirmação reforçada (digitar uma frase)."""
    global _confirm_typed_callback
    _confirm_typed_callback = callback


def _default_confirm(message: str) -> bool:
    resposta = input(f"{message} (s/N): ").strip().lower()
    return resposta == 's'


def _default_confirm_typed(message: str, phrase: str) -> bool:
    print(message)
    resposta = input(f"Digite '{phrase}' para confirmar (qualquer outra coisa cancela): ").strip()
    return resposta == phrase


def confirm_action(message: str) -> bool:
    callback = _confirm_callback or _default_confirm
    return callback(message)


def confirm_action_typed(message: str, phrase: str) -> bool:
    callback = _confirm_typed_callback or _default_confirm_typed
    return callback(message, phrase)
