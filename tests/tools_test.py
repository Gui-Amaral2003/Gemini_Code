from old_gemini_client import GeminiClient


client = GeminiClient()

response = client.generate(
    r"""
    Leia o arquivo C:\Users\gamaral\Documents\TAXA_CDI/main.py usando a ferramenta disponível.
    Depois me diga qual é o conteúdo dele.
    """
)

print(response.text)