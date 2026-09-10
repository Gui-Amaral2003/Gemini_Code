from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

import terminal_completer
from terminal_completer import FileNameCompleter, SlashCommandCompleter


def complete(text: str) -> list[str]:
    return [
        item.text
        for item in SlashCommandCompleter().get_completions(
            Document(text, cursor_position=len(text)),
            CompleteEvent(completion_requested=True),
        )
    ]


def complete_with(completer, text: str):
    return list(
        completer.get_completions(
            Document(text, cursor_position=len(text)),
            CompleteEvent(completion_requested=True),
        )
    )


def test_completa_comandos_parciais():
    assert complete("/sw") == ["/switch"]
    assert complete("/n") == ["/new"]
    assert complete("/con") == ["/config"]


def test_completa_subcomando_de_configuracao():
    assert complete("/config ") == ["edit"]
    assert complete("/config e") == ["edit"]
    assert complete("/config edit") == ["edit"]
    assert complete("/config desconhecido") == []


def test_nao_completa_texto_comum():
    assert complete("explique este arquivo") == []


def test_completa_nome_de_ferramenta():
    assert "read_file" in complete("/tools read")


def test_completa_sessao_no_comando_switch(monkeypatch):
    monkeypatch.setattr(
        terminal_completer.ChatSession,
        "list_sessions",
        lambda _path: [
            {"session_id": "trabalho"},
            {"session_id": "pessoal"},
        ],
    )

    assert complete("/switch tra") == ["trabalho"]
    assert complete("/sessions tra") == []


def test_arquivo_exige_tres_caracteres_e_extensao_permitida(monkeypatch, tmp_path):
    (tmp_path / "relatorio.xlsx").touch()
    (tmp_path / "resultado.pyc").touch()
    (tmp_path / "README").touch()
    monkeypatch.setattr(terminal_completer, "ALLOWED_SEARCH_DIRS", [tmp_path])
    completer = FileNameCompleter()

    assert complete_with(completer, "abra re") == []
    assert [item.text for item in complete_with(completer, "abra rel")] == [
        "relatorio.xlsx"
    ]
    assert complete_with(completer, "abra res") == []
    assert complete_with(completer, "abra REA") == []


def test_ignora_diretorios_tecnicos(monkeypatch, tmp_path):
    hidden = tmp_path / ".git"
    hidden.mkdir()
    (hidden / "relatorio.sql").touch()
    monkeypatch.setattr(terminal_completer, "ALLOWED_SEARCH_DIRS", [tmp_path])

    assert complete_with(FileNameCompleter(), "abra rel") == []


def test_nome_ambiguo_sugere_caminhos_completos(monkeypatch, tmp_path):
    first = tmp_path / "a" / "relatorio.csv"
    second = tmp_path / "b" / "relatorio.csv"
    first.parent.mkdir()
    second.parent.mkdir()
    first.touch()
    second.touch()
    monkeypatch.setattr(terminal_completer, "ALLOWED_SEARCH_DIRS", [tmp_path])

    completions = complete_with(FileNameCompleter(), "analise rel")

    assert [item.text for item in completions] == [str(first), str(second)]
    assert all("ambíguo" in str(item.display_meta) for item in completions)


def test_sugestoes_de_arquivo_sao_ordenadas(monkeypatch, tmp_path):
    (tmp_path / "resultado.sql").touch()
    (tmp_path / "resumo.pdf").touch()
    monkeypatch.setattr(terminal_completer, "ALLOWED_SEARCH_DIRS", [tmp_path])

    completions = complete_with(FileNameCompleter(), "abra res")

    assert [item.text for item in completions] == ["resultado.sql", "resumo.pdf"]
