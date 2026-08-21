def confirm_action(message: str) -> bool:
    resposta = input(f"{message} (s/N): ").strip().lower()
    return resposta == 's'