##TODO: 1. Testar tools de excel para planilhas grandes, verificar se o modelo vai chamar a read_sheet e não a preview_sheet 
##TODO: 2. Usar para um caso generico, com o objetivo de testar a search_in_sheet
##TODO: 3. Solicitar dados que não existe, para garantir que o modelo não vai invertar dados
##TODO: 4. Adicionar uma busca por arqruivos mais robusta
##TODO: 5. Testar o analyze_table_data
##TODO: 6. Refinar a instrução sobre quando chamar plot_sheet_data/plot_table_data (evitar que o modelo gere gráfico quando o usuário só queria um número)
##TODO: 7. Adicionar os tests para filesystem, database, pdf_reader e GeminiClient
##TODO: 8. Limpeza de arquivos
##TODO: 9. Prosseguir com a criação dos tests
##TODO 10. Testar economia gerada pelo model_routing
from pathlib import Path
from gemini import GeminiClient, ChatSession
from rich.console import Console
from rich.markdown import Markdown

SESSION_ID = 'teste'
PLOTS_DIR = Path("output") / "plots"

console = Console()

def main():
    client = GeminiClient(cheap_model = 'gemini-3.5-flash-lite')

    chat = ChatSession(
        client = client,
        session_id = SESSION_ID,
        system_instruction = """
        Você é meu assistente técnico de programação.
        Responda de forma ojetiva e técnica. 
        Mantenha o contexto da conversa

        REGRA SOBRE MÚLTIPLOS ARQUIVOS:
        Se o usuário pedir para processar mais de um arquivo (planilha, PDF ou tabela)
        na mesma solicitação, chame a ferramenta correspondente uma vez para cada
        arquivo, todas na mesma resposta — não processe um arquivo, escreva um
        resumo parcial e espere confirmação para continuar com o próximo.

        REGRA OBRIGATÓRIA sobre cálculos em dados de planilha ou banco:
        Se a pergunta pedir soma, média, contagem, mínimo, máximo, ou total agrupado por
        categoria/região/vendedor/etc., você DEVE chamar a ferramenta analyze_sheet_data
        (planilhas) ou analyze_table_data (banco) e responder com o RESULTADO que ela retornar.

        Isso significa que, para esse tipo de pergunta:
        - É proibido calcular o resultado você mesmo a partir de dados lidos via read_sheet,
        preview_sheet ou query_table.
        - read_sheet/preview_sheet/query_table só servem para exibir linhas/registros ao usuário
        ou para descobrir nomes de colunas — nunca como substituto de analyze_sheet_data/
        analyze_table_data para produzir um resultado agregado.

        REGRA SOBRE GRÁFICOS:
        Só chame plot_sheet_data ou plot_table_data quando o usuário pedir explicitamente
        para ver, gerar ou visualizar um gráfico/plot. Se o usuário só pediu um número, uma
        soma, uma média ou uma tabela, use analyze_sheet_data/analyze_table_data — NUNCA
        chame as ferramentas de plot nesse caso.
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
                print("See You Space Cowboy...")
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
            console.print(Markdown(response.text))

            if response.generated_files:
                handle_generated_files(response.generated_files)

        except KeyboardInterrupt:
            print("\nEncerrando...")
            break

        except Exception as e:
            print(f"\nErro: {e}")

def handle_generated_files(files: list[Path]) -> None:
    """Pergunta ao usuário, para cada arquivo gerado nesta resposta (ex: gráficos),
    se ele quer manter (move para PLOTS_DIR) ou descartar (deleta do staging)."""
    for file_path in files:
        if not file_path.exists():
            continue

        resposta = input(
            f"\nSalvar o gráfico gerado ({file_path.name})? [s/N] "
        ).strip().lower()

        if resposta == "s":
            PLOTS_DIR.mkdir(parents=True, exist_ok=True)
            destino = PLOTS_DIR / file_path.name
            file_path.replace(destino)
            print(f"Salvo em: {destino}")
        else:
            try:
                file_path.unlink()
            except OSError as e:
                print(f"Não consegui remover o arquivo temporário {file_path}: {e}")
            else:
                print("Descartado.")

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
        console.print(Markdown(message.text))

if __name__ == "__main__":
    main()