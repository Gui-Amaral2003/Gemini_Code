from gemini_client import GeminiClient, ChatSession

SESSION_ID = 'terminal'

def main():
    client = GeminiClient()

    chat = ChatSession(
        client = client,
        session_id = SESSION_ID,
        system_instruction = """
        Você é meu assistente técnico de programação.
        O usuário trabalha principalmente com dois ambientes:
        -LOCAL WINDOWS: Python, SQL Server
        -VM LINUX: Python, SQL, PySpark, Airflow, Hive

        Responda de forma ojetiva e técnica. 
        Mantenha o contexto da conversa
        """
    )

    print("=" * 70)
    print(" Gemini Terminal")
    print("=" * 70)
    print(f"Sessão: {SESSION_ID}")
    print()
    print("Comandos:")
    print("  /help      - mostra os comandos")
    print("  /history   - mostra o histórico")
    print("  /clear     - limpa o contexto")
    print("  /tokens    - mostra consumo")
    print("  /exit      - sair")
    print("=" * 70)

    while True:
        try:
            user_input = input("\nVocê > ").strip()

            if not user_input:
                continue

            if user_input == "/exit":
                break

            if user_input == "/help":
                print_help()
                continue

            if user_input == "/history":
                print_history(chat)
                continue

            if user_input == "/clear":
                chat.clear_history()
                print("Contexto limpo.")
                continue

            if user_input == "/tokens":
                print(client.session_summary())
                continue

            response = chat.send(user_input)

            print("\nGemini >")
            print(response.text)

        except KeyboardInterrupt:
            print("\nEncerrando...")
            break

        except Exception as e:
            print(f"\nErro: {e}")

def print_help() -> None:
    print("""
Comandos:

  /help       Mostra esta ajuda
  /history    Mostra o histórico local
  /clear      Limpa a conversa
  /tokens     Mostra consumo de tokens
  /exit       Encerra o programa
    """)

def print_history(chat: ChatSession) -> None:
    for message in chat.get_history():
        role = "Você" if message.role == "user" else "Gemini"

        print(f"\n{role}:")
        print(message.text)