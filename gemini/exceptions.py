class GeminiTimeoutError(RuntimeError):
    """
    O limite de rodadas de ferramentas de um generate() foi excedido e o
    usuário optou por não continuar (via confirm_action), OU uma chamada HTTP
    individual ao Gemini excedeu o timeout configurado / teve a conexão
    interrompida pelo servidor.

    Nunca é incluída em RETRYABLE_ERRORS de propósito: se o orçamento já
    estourou, ou o usuário já disse "não continua", uma nova tentativa
    automática só repetiria o mesmo problema.
    """


class ModelFallbackExhausted(RuntimeError):
    """Todos os modelos elegíveis falharam por limite de uso."""

    def __init__(self, attempted_models: list[str], last_error: Exception | None):
        self.attempted_models = list(attempted_models)
        self.last_error = last_error
        super().__init__("Todos os modelos configurados atingiram o limite de uso.")
