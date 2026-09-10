"""
Completer e histórico de prompt via prompt_toolkit, usados pelo terminal
interativo (gemini_terminal.py). Isolado da camada de renderização (Rich)
de propósito — só cuida de COMO o texto é digitado, não de como é exibido.
"""
import os
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion, merge_completers
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from tools.definitions import TOOL_DEFINITIONS
from tools.database import TABELAS_PERMITIDAS
from tools.airflow_tool import AIRFLOW_ALLOWED_DAGS
from tools.git_tool import GIT_ALLOWED_REPOS
from tools.filesystem import ALLOWED_SEARCH_DIRS

from gemini.config import DEFAULT_SESSIONS_PATH
from gemini.session import ChatSession

HISTORY_PATH = "gemini/prompt_history.txt"
MIN_CHARS_FILE_COMPLETION = 3

# Uniao dos formatos que as ferramentas atuais conseguem consumir de forma
# util. Formatos binarios e internos (.pyc, objetos Git etc.) ficam de fora.
COMPLETABLE_FILE_EXTENSIONS = {
    ".csv", ".xls", ".xlsx",
    ".pdf", ".txt", ".md", ".log",
    ".json", ".jsonl", ".yaml", ".yml", ".xml",
    ".py", ".sql", ".js", ".html", ".css", ".sh",
}

IGNORED_DIRECTORY_NAMES = {
    ".git", ".mypy_cache", ".nox", ".pytest_cache", ".ruff_cache",
    ".tox", ".venv", "__pycache__", "env", "node_modules", "venv",
}

SLASH_COMMANDS = [
    "/help", "/config", "/history", "/sessions", "/new", "/switch", "/quote",
    "/clear", "/tools", "/think", "/logs", "/tokens", "/trace", "/exit",
]
CONFIG_SUBCOMMANDS = ["edit"]
_TOOL_NAMES = [d["name"] for d in TOOL_DEFINITIONS]

PROMPT_STYLE = Style.from_dict({"prompt": "bold fg:#00ffff"}) 

class IdentifierCompleter(Completer):
    """
    Sugere nomes pré-cadastrados (tabelas, DAGs, repositórios) em qualquer
    ponto do texto livre — diferente do SlashCommandCompleter, não exige
    prefixo de comando, já que o usuário normalmente escreve em linguagem
    natural ('apague da tabela TEST_DOA... onde...').
    """
    def __init__(self):
        # nome -> categoria, só para o display_meta (contexto na lista)
        self._catalog: dict[str, str] = {}
        self._catalog.update({name: "tabela" for name in TABELAS_PERMITIDAS})
        self._catalog.update({name: "DAG" for name in AIRFLOW_ALLOWED_DAGS})
        self._catalog.update({name: "repositório" for name in GIT_ALLOWED_REPOS})

    def get_completions(self, document, complete_event):
        if document.text_before_cursor.lstrip().startswith("/"):
            return

        word = document.get_word_before_cursor(WORD=True)
        if not word:
            return

        word_lower = word.lower()
        for name, categoria in self._catalog.items():
            if name.lower().startswith(word_lower) and name.lower() != word_lower:
                yield Completion(name, start_position=-len(word), display_meta=categoria)


class FileNameCompleter(Completer):
    """
    Sugere nomes de arquivo encontrados em ALLOWED_SEARCH_DIRS (mesmo escopo
    de busca de resolve_file_path, em tools/filesystem.py). O índice é
    montado uma vez na criação — arquivos criados/movidos depois só aparecem
    reiniciando o terminal.

    TODO: comando /reindex para reconstruir o índice sem reiniciar o
    terminal (reatribuir prompt_session.completer). Deixado de fora por
    ora — escopo mínimo até confirmar que o índice congelado incomoda na
    prática.
    """
    def __init__(self):
        self._index = self._scan()

    def _scan(self) -> dict[str, list[Path]]:
        index: dict[str, list[Path]] = {}
        for base_dir in ALLOWED_SEARCH_DIRS:
            try:
                exists = base_dir.exists()
            except OSError:
                continue
            if not exists:
                continue

            for root, directories, filenames in os.walk(
                base_dir,
                followlinks=False,
                onerror=lambda _error: None,
            ):
                directories[:] = [
                    name for name in directories
                    if name.casefold() not in IGNORED_DIRECTORY_NAMES
                ]
                root_path = Path(root)
                for filename in filenames:
                    path = root_path / filename
                    if path.suffix.casefold() not in COMPLETABLE_FILE_EXTENSIONS:
                        continue
                    index.setdefault(filename.casefold(), []).append(path)

        for paths in index.values():
            paths.sort(key=lambda path: str(path).casefold())
        return index

    def get_completions(self, document, complete_event):
        if document.text_before_cursor.lstrip().startswith("/"):
            return

        word = document.get_word_before_cursor(WORD=True)
        if not word or len(word) < MIN_CHARS_FILE_COMPLETION:
            return

        word_lower = word.casefold()
        matches = [
            paths for key, paths in self._index.items()
            if key.startswith(word_lower) and key != word_lower
        ]
        matches.sort(key=lambda paths: paths[0].name.casefold())

        for paths in matches:
            if len(paths) == 1:
                path = paths[0]
                yield Completion(
                    path.name,
                    start_position=-len(word),
                    display_meta=str(path.parent),
                )
                continue

            for path in paths:
                yield Completion(
                    str(path),
                    start_position=-len(word),
                    display_meta=f"ambíguo · {path.parent}",
                )


    
class SlashCommandCompleter(Completer):
    """
    Sem dependência de contexto do modelo, só do que já existe localmente:
    - início da linha começando com '/' -> sugere os comandos
    - depois de '/switch ' -> sugere os nomes de sessões
    - depois de '/tools ' -> sugere os nomes de ferramentas (mesma lista
      enviada ao Gemini em TOOL_DEFINITIONS, então nunca fica desatualizado)
    """
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        if text.startswith("/switch "):
            partial = text[len("/switch "):]
            for session in ChatSession.list_sessions(DEFAULT_SESSIONS_PATH):
                session_id = session["session_id"]
                if session_id.startswith(partial):
                    yield Completion(session_id, start_position=-len(partial))
            return

        if text.startswith("/tools "):
            partial = text[len("/tools "):]
            for name in _TOOL_NAMES:
                if name.startswith(partial):
                    yield Completion(name, start_position=-len(partial))
            return

        if text.startswith("/config "):
            partial = text[len("/config "):]
            for option in CONFIG_SUBCOMMANDS:
                if option.startswith(partial):
                    yield Completion(option, start_position=-len(partial))
            return

        if text.startswith("/") and " " not in text:
            for cmd in SLASH_COMMANDS:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))

def build_completer() -> Completer:
    return merge_completers([
        SlashCommandCompleter(),
        IdentifierCompleter(),
        FileNameCompleter(),
    ])

def build_prompt_session() -> PromptSession:
    return PromptSession(
        history=FileHistory(HISTORY_PATH),
        completer=build_completer(),
        style=PROMPT_STYLE,
    )
