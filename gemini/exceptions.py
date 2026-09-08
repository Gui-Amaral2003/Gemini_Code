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
