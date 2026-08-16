from old_gemini_client import GeminiClient, ChatSession


def main():
    client = GeminiClient()

    chat = ChatSession(
        client=client,
        session_id="terminal_ccee",
        system_instruction="""
        Você é meu assistente técnico.

        Tenho experiência com Python, SQL, PySpark, Airflow,
        Hive e APIs. Responda de forma técnica e objetiva,
        mas explique o raciocínio quando necessário.

        Mantenha o contexto da conversa e considere mensagens
        anteriores ao responder.
        """
    )

    print("=" * 60)
    print(" Gemini Chat")
    print("=" * 60)
    print("Sessão: terminal_ccee")
    print("Digite 'sair' para encerrar.")
    print("Digite 'limpar' para começar uma nova conversa.")
    print("=" * 60)

    while True:
        try:
            user_input = input("\nVocê: ").strip()

            if not user_input:
                continue

            if user_input.lower() in {"sair", "exit", "quit"}:
                print("\nEncerrando...")
                break

            if user_input.lower() == "limpar":
                chat.clear_history()
                print("\nContexto limpo.")
                continue

            response = chat.send(user_input)

            print(f"\nGemini:\n{response.text}")

        except KeyboardInterrupt:
            print("\n\nEncerrando...")
            break

        except Exception as e:
            print(f"\nErro: {e}")


if __name__ == "__main__":
    main()