import json
from types import SimpleNamespace

import pytest

import gemini.client as client_module
from gemini.client import GeminiClient


# --------------------------------------------------------------------------- #
# Fakes que imitam a shape de retorno de google.genai (interactions.create)
# --------------------------------------------------------------------------- #

def make_usage(input_tokens=10, output_tokens=5, total_tokens=15):
    return SimpleNamespace(
        total_input_tokens=input_tokens,
        total_output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def make_thought_step(text):
    return SimpleNamespace(
        type="thought",
        summary=[SimpleNamespace(type="text", text=text)],
    )


def make_function_call_step(name, arguments, call_id="call_1"):
    return SimpleNamespace(
        type="function_call",
        name=name,
        arguments=arguments,
        id=call_id,
    )


def make_interaction(interaction_id, steps=None, output_text="", usage=None):
    return SimpleNamespace(
        id=interaction_id,
        steps=steps or [],
        usage=usage or make_usage(),
        output_text=output_text,
    )


class FakeInteractionsAPI:
    """
    Fila de respostas programadas para client.interactions.create(). Cada
    item é uma interação (retornada) ou uma Exception (levantada), na
    ordem em que forem consumidas. Guarda os kwargs de cada chamada para
    os testes inspecionarem qual modelo/previous_interaction_id/input foi
    efetivamente enviado em cada rodada.
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError(
                "FakeInteractionsAPI ficou sem respostas programadas — "
                "o cliente fez mais chamadas do que o teste esperava."
            )
        next_item = self._responses.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        return next_item


class FakeGenAIClient:
    def __init__(self, responses):
        self.interactions = FakeInteractionsAPI(responses)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def make_client(tmp_path):
    """
    Cria um GeminiClient real (retry/fallback/cache/roteamento intactos),
    com gc.client substituído por um FakeGenAIClient programável e todos
    os arquivos de log/cache isolados em tmp_path (evita colisão entre
    testes e com arquivos reais do projeto).
    """
    def _make(responses, **kwargs):
        gc = GeminiClient(
            api_key="fake-key",
            usage_log_path=tmp_path / "usage.jsonl",
            trace_log_path=tmp_path / "trace.jsonl",
            cache_path=tmp_path / "cache.json",
            quota_path=tmp_path / "quota.json",
            **kwargs,
        )
        gc.client = FakeGenAIClient(responses)
        return gc
    return _make


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Evita esperas reais de backoff (retry interno e retry externo) nos testes."""
    monkeypatch.setattr(client_module.time, "sleep", lambda *_a, **_kw: None)


# --------------------------------------------------------------------------- #
# 1. Resposta simples, sem tools — inclui captura de thought summary
# --------------------------------------------------------------------------- #

def test_generate_simple_text_response_and_thought_callback(make_client):
    thought_step = make_thought_step("Pensando na resposta...")
    interaction = make_interaction(
        "interaction-1",
        steps=[thought_step],
        output_text="Olá!",
        usage=make_usage(10, 5, 15),
    )
    gc = make_client([interaction])

    captured_thoughts = []
    gc.set_thought_callback(captured_thoughts.append)

    response = gc.generate("oi", use_cache=False)

    assert response.text == "Olá!"
    assert response.input_tokens == 10
    assert response.output_tokens == 5
    assert response.total_tokens == 15
    assert response.api_calls == 1
    assert response.interaction_id == "interaction-1"
    assert response.thoughts == ["Pensando na resposta..."]
    assert captured_thoughts == ["Pensando na resposta..."]
    assert gc.client.interactions.calls[0]["previous_interaction_id"] is None


# --------------------------------------------------------------------------- #
# 2. Cache hit não consome a fila de respostas programadas
# --------------------------------------------------------------------------- #

def test_cache_hit_avoids_second_api_call(make_client):
    interaction = make_interaction("interaction-1", output_text="resposta cacheável")
    gc = make_client([interaction])  # só UMA resposta programada de propósito

    first = gc.generate("pergunta repetida", use_cache=True)
    second = gc.generate("pergunta repetida", use_cache=True)

    assert first.text == second.text == "resposta cacheável"
    assert second.api_calls == 0
    assert second.input_tokens == 0
    assert len(gc.client.interactions.calls) == 1  # segunda chamada não bateu na "API"


# --------------------------------------------------------------------------- #
# 3. Loop completo de tool-calling: chamada -> execução -> síntese
# --------------------------------------------------------------------------- #

def test_generate_executes_tool_call_and_synthesizes(make_client, monkeypatch):
    def fake_soma(a, b):
        return {"resultado": a + b}

    monkeypatch.setattr(client_module, "TOOLS", {"soma": fake_soma})

    call_step = make_function_call_step("soma", {"a": 2, "b": 3}, call_id="call_abc")
    first_interaction = make_interaction("interaction-1", steps=[call_step], output_text="")
    second_interaction = make_interaction("interaction-2", output_text="A soma é 5.")

    gc = make_client([first_interaction, second_interaction])

    response = gc.generate("quanto é 2 + 3?", use_cache=False)

    assert response.text == "A soma é 5."
    assert response.api_calls == 2

    second_call_kwargs = gc.client.interactions.calls[1]
    assert second_call_kwargs["previous_interaction_id"] == "interaction-1"

    function_result = second_call_kwargs["input"][0]
    assert function_result["name"] == "soma"
    assert function_result["call_id"] == "call_abc"
    assert json.loads(function_result["result"][0]["text"]) == {"resultado": 5}


# --------------------------------------------------------------------------- #
# 4. Tool não registrada -> erro devolvido ao modelo, sem crashar
# --------------------------------------------------------------------------- #

def test_unknown_tool_returns_error_without_crashing(make_client, monkeypatch):
    monkeypatch.setattr(client_module, "TOOLS", {})  # nenhuma tool registrada

    call_step = make_function_call_step("tool_inexistente", {}, call_id="call_x")
    first_interaction = make_interaction("interaction-1", steps=[call_step], output_text="")
    second_interaction = make_interaction(
        "interaction-2", output_text="Não consegui usar essa ferramenta."
    )

    gc = make_client([first_interaction, second_interaction])

    response = gc.generate("usa uma tool que não existe", use_cache=False)

    assert response.text == "Não consegui usar essa ferramenta."

    function_result = gc.client.interactions.calls[1]["input"][0]
    result_payload = json.loads(function_result["result"][0]["text"])
    assert "error" in result_payload
    assert "tool_inexistente" in result_payload["error"]


# --------------------------------------------------------------------------- #
# 5. Arquivo gerado por tool de plot é rastreado em generated_files
# --------------------------------------------------------------------------- #

def test_generated_files_from_plot_tool_are_tracked(make_client, monkeypatch, tmp_path):
    fake_png = tmp_path / "grafico.png"
    fake_png.write_bytes(b"fake-png-bytes")

    def fake_plot_sheet_data(**_kwargs):
        return {"status": "ok", "file_path": str(fake_png)}

    monkeypatch.setattr(client_module, "TOOLS", {"plot_sheet_data": fake_plot_sheet_data})

    call_step = make_function_call_step(
        "plot_sheet_data", {"file_path": "dados.csv"}, call_id="call_plot"
    )
    first_interaction = make_interaction("interaction-1", steps=[call_step], output_text="")
    second_interaction = make_interaction("interaction-2", output_text="Aqui está o gráfico.")

    gc = make_client([first_interaction, second_interaction])
    response = gc.generate("gera um gráfico de vendas", use_cache=False)

    assert response.generated_files == [fake_png]


# --------------------------------------------------------------------------- #
# 6. Fallback para o próximo modelo em erro de rate limit
# --------------------------------------------------------------------------- #

def test_fallback_to_next_model_on_rate_limit(make_client):
    # _create_interaction faz até 3 tentativas (max_retries=2, hardcoded)
    # no MESMO modelo antes de propagar o erro para _create_with_fallback
    # decidir trocar de modelo — por isso são 3 erros, não 1.
    rate_limit_errors = [Exception("429 Resource exhausted") for _ in range(3)]
    interaction = make_interaction("interaction-1", output_text="ok com fallback")

    gc = make_client(
        [*rate_limit_errors, interaction],
        fallback_models=["modelo-fallback"],
    )

    response = gc.generate("teste", use_cache=False)

    assert response.text == "ok com fallback"
    assert response.model == "modelo-fallback"
    assert len(gc.client.interactions.calls) == 4  # 3 tentativas no modelo padrão + 1 no fallback
    assert all(c["model"] == gc.default_model for c in gc.client.interactions.calls[:3])
    assert gc.client.interactions.calls[3]["model"] == "modelo-fallback"


# --------------------------------------------------------------------------- #
# 7. Erro transitório (RETRYABLE_ERRORS) reinicia generate() do zero
# --------------------------------------------------------------------------- #

def test_retryable_error_retries_full_generate_call(make_client):
    transient_error = ConnectionError("network down")
    interaction = make_interaction("interaction-1", output_text="ok após retry")

    gc = make_client([transient_error, interaction])

    response = gc.generate("teste", use_cache=False)

    assert response.text == "ok após retry"
    # duas tentativas completas de _create_with_fallback (não retry interno
    # de rate limit — ConnectionError não é rate limit, então propaga
    # imediatamente e é o generate() externo que reinicia tudo)
    assert len(gc.client.interactions.calls) == 2


def test_retryable_error_gives_up_after_max_retries(make_client):
    errors = [ConnectionError("network down") for _ in range(4)]  # > max_retries padrão (3)
    gc = make_client(errors, max_retries=3)

    with pytest.raises(ConnectionError):
        gc.generate("teste", use_cache=False)


# --------------------------------------------------------------------------- #
# 8. Roteamento para o modelo barato após rodada 100% terminal
# --------------------------------------------------------------------------- #

def test_cheap_model_routing_after_terminal_tool_round(make_client, monkeypatch):
    def fake_analyze_sheet_data(**_kwargs):
        return "Resultado: 42"

    monkeypatch.setattr(client_module, "TOOLS", {"analyze_sheet_data": fake_analyze_sheet_data})

    call_step = make_function_call_step(
        "analyze_sheet_data", {"file_path": "x.csv", "operation": "sum"}, call_id="call_analyze"
    )
    initial_interaction = make_interaction("interaction-1", steps=[call_step], output_text="")
    cheap_interaction = make_interaction("interaction-2", output_text="Resultado: 42")

    gc = make_client([initial_interaction, cheap_interaction], cheap_model="modelo-barato")

    response = gc.generate("soma a coluna de vendas", use_cache=False)

    assert response.text == "Resultado: 42"
    assert response.model == "modelo-barato"
    assert gc.client.interactions.calls[1]["model"] == "modelo-barato"


# --------------------------------------------------------------------------- #
# 9. Rede de segurança: modelo barato pede mais tools -> refaz com o forte
# --------------------------------------------------------------------------- #

def test_cheap_model_requesting_more_tools_falls_back_to_strong_model(make_client, monkeypatch):
    def fake_analyze_sheet_data(**_kwargs):
        return "Resultado: 42"

    monkeypatch.setattr(client_module, "TOOLS", {"analyze_sheet_data": fake_analyze_sheet_data})

    call_step = make_function_call_step(
        "analyze_sheet_data", {"file_path": "x.csv", "operation": "sum"}, call_id="call_analyze"
    )
    initial_interaction = make_interaction("interaction-1", steps=[call_step], output_text="")

    # Modelo barato "erra" e pede mais uma tool em vez de sintetizar —
    # essa chamada nunca chega a ser executada (ver comentário no client.py).
    cheap_more_tools_step = make_function_call_step("outra_tool", {}, call_id="call_extra")
    cheap_interaction = make_interaction(
        "interaction-2-cheap", steps=[cheap_more_tools_step], output_text=""
    )

    strong_interaction = make_interaction(
        "interaction-3-strong", output_text="Resposta final com modelo forte."
    )

    gc = make_client(
        [initial_interaction, cheap_interaction, strong_interaction],
        cheap_model="modelo-barato",
    )

    response = gc.generate("soma a coluna de vendas", use_cache=False)

    assert response.text == "Resposta final com modelo forte."
    assert response.model == gc.default_model
    assert response.api_calls == 3

    calls = gc.client.interactions.calls
    assert calls[1]["model"] == "modelo-barato"
    assert calls[2]["model"] == gc.default_model
    # o refazer usa o mesmo ponto de partida (a interação inicial) e o
    # mesmo resultado de tool que o modelo barato recebeu e não sintetizou
    assert calls[2]["previous_interaction_id"] == calls[1]["previous_interaction_id"] == "interaction-1"
    assert calls[2]["input"] == calls[1]["input"]
