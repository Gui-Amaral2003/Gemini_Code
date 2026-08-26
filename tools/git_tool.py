"""
Ferramentas de leitura (e, para repos marcados como writable, edição
controlada) de repositórios git locais.
 
Escopo: repositórios pré-cadastrados em GIT_ALLOWED_REPOS (mesmo padrão de
TABELAS_PERMITIDAS em database.py — o modelo escolhe um nome de repo
pré-validado, nunca um path livre). Cada repo tem um flag "writable": só
repos com writable=True aceitam edit_repo_file; os demais continuam
somente-leitura (ex: gemini_code, o próprio projeto — nunca é auto-editável).
 
edit_repo_file — invariante de segurança:
    A tool só aplica a edição sobre um arquivo cujo working tree está limpo
    (git status --porcelain restrito ao path), verificado ANTES de escrever.
    Isso garante que "git checkout -- path" sempre reverte para um estado
    commitado sem perda, o que é o que sustenta o fluxo de "aplica a edição,
    mostra o diff real, pergunta depois, reverte se recusado" em vez de
    simular o diff antes de tocar no arquivo.
 
Segurança:
- Nenhuma tool aceita flags livres do modelo; cada uma monta uma lista fixa
  de argumentos e só recebe DADOS (nome de repo, commit_ref, path, números,
  old_str/new_str).
- commit_ref e path passam por validação antes de chegar ao subprocess.
- path é sempre resolvido e checado como estando DENTRO do repositório.
- subprocess.run(shell=False) com timeout, mesmo padrão de script_runner.py.
- edit_repo_file exige confirmação reforçada (digitar uma frase), mesmo
  padrão de update_table/delete_table_rows — mexer em código de outro
  repositório merece o mesmo nível de fricção que mexer em dados.
 
TODO v2: commit automático do que for aprovado (fora de escopo agora —
decisão de commitar fica manual, fora da tool). Integração com API remota
do GitHub (PRs, issues) também fica como TODO futuro.
"""
import json
import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Optional
from .confirmation import confirm_action_typed

logger = logging.getLogger('gemini_client')
# --------------------------------------------------------------------------- #
# Configuração — repositórios permitidos (nome -> path)
# --------------------------------------------------------------------------- #
# Por padrão, cadastra apenas o próprio projeto (raiz = um nível acima de tools/).
# Adicione outras entradas aqui para permitir outros repositórios.
GIT_ALLOWED_REPOS: dict[str, dict] = {
    "gemini_code": {
        'path': Path(__file__).resolve().parent.parent,
        'writable': False
    },
}

GIT_TIMEOUT_SECONDS = 20
MAX_OUTPUT_CHARS = 10000
EDIT_CONFIRM_PHRASE = 'EDITAR'
EDIT_AUDIT_LOG_PATH = Path("gemini/git_write_audit_log.jsonl")

# HEAD, HEAD~2, HEAD^, hash curto/longo, nomes de branch simples — mas nunca
# algo que comece com "-" (evita que um "commit_ref" seja lido como flag).
_COMMIT_REF_RE = re.compile(r"^[A-Za-z0-9_./\-~^]{1,100}$")

# --------------------------------------------------------------------------- #
# Validação e resolução
# --------------------------------------------------------------------------- #

def _resolve_repo(repo: str, require_writable: bool = False) -> tuple[Optional[Path], Optional[str]]:
    """
    Valida o nome do repo contra GIT_ALLOWED_REPOS e confere que ainda é um
    repo válido (tem .git). Se require_writable=True, também confere que o
    repo está marcado como editável — usado por edit_repo_file; as demais
    tools (somente leitura) continuam chamando com o padrão False.
    """
 
    if repo not in GIT_ALLOWED_REPOS:
        return None, (
            f"Repositório não permitido: {repo}. "
            f"Disponíveis: {list(GIT_ALLOWED_REPOS)}"
        )
 
    config = GIT_ALLOWED_REPOS[repo]
    repo_path = config["path"]
 
    if not (repo_path / ".git").exists():
        return None, (
            f"O caminho configurado para '{repo}' não é um repositório git "
            f"válido (sem .git): {repo_path}"
        )
 
    if require_writable and not config.get("writable", False):
        editaveis = [nome for nome, cfg in GIT_ALLOWED_REPOS.items() if cfg.get("writable")]
        return None, (
            f"Repositório '{repo}' não está liberado para edição. "
            f"Editáveis: {editaveis or '[nenhum cadastrado]'}"
        )
 
    return repo_path, None

def _validate_commit_ref(commit_ref: str) -> Optional[str]:
    """Retorna mensagem de erro, None se válido"""
    if not commit_ref or commit_ref.startswith('-'):
        return f"Referência de commit inválida: {commit_ref!r}"
    if not _COMMIT_REF_RE.match(commit_ref):
        return f"Referência de commit inválida: {commit_ref!r}"

    return None

def _validate_repo_relative_path(repo_path: Path, relative_path: str) -> tuple[Optional[Path], Optional[str]]:
    """Garante que relative_path resolve para dentro do repositório. Não exige que o arquivo exista (chamador decide)."""
    if not relative_path or relative_path.startswith('-'):
        return None, f"Caminho relativo inválido: {relative_path!r}"

    candidate = (repo_path / relative_path).resolve()
    resolved_repo = repo_path.resolve()

    try:
        candidate.relative_to(resolved_repo)
    except ValueError:
        return None, (
            f"Caminho relativo inválido: {relative_path!r} "
            f"(resolve para fora do repositório: {candidate})"
        )

    return candidate, None

# --------------------------------------------------------------------------- #
# Execução do subprocess
# --------------------------------------------------------------------------- #

def _run_git(repo_path: Path, args: list[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Executa um comando git já validado pelo chamador (args é uma lista fixa,
    nunca uma string vinda direto do modelo). Retorna (stdout, error).
    """
    try:
        process = subprocess.run(
            ["git", "-C", str(repo_path), *args],
            shell=False,
            timeout=GIT_TIMEOUT_SECONDS,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return None, "Git não está instalado ou não foi encontrado no PATH."
    except subprocess.TimeoutExpired:
        return None, f"Comando git excedeu o limite de {GIT_TIMEOUT_SECONDS}s."
    except OSError as e:
        return None, f"Erro ao executar git: {e}"
 
    if process.returncode != 0:
        return None, f"Erro ao executar 'git {' '.join(args)}': {process.stderr.strip()}"
 
    return process.stdout, None

def _truncate(text: str, label: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
 
    truncated = text[:MAX_OUTPUT_CHARS]
    return (
        truncated
        + f"\n\n[...{label} truncado — {len(text)} caracteres no total. "
        "Use o parâmetro path para focar em um arquivo específico.]"
    )

def _log_edit_audit(entry: dict) -> None:
    entry['timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")

    try:
        EDIT_AUDIT_LOG_PATH.parent.mkdir(parents = True, exist_ok = True)
        with open(EDIT_AUDIT_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False, default = str) + "\n")

    except OSError as e:
        logger.error(f"Falha ao registrar log de auditoria de edição: {e}")

# --------------------------------------------------------------------------- #
# Tools expostas ao Gemini - leitura
# --------------------------------------------------------------------------- #

def git_status(repo: str) -> str:
    """Mostra os arquivos com mudanças staged, unstages e untracked no repositório"""
    repo_path, error = _resolve_repo(repo)
    if error:
        return error

    stdout, error = _run_git(repo_path, ['status', '--porcelain=v1', '--branch'])
    if error:
        return error

    lines = stdout.strip("\n").split("\n") if stdout.strip("\n") else []
    branch_line = lines[0].lstrip("# ") if lines and lines[0].startswith("##") else None
    changes = [line for line in lines if not line.startswith("##")]

    if not changes:
        sufixo = f" ({branch_line})" if branch_line else ""
        return f"Working directory limpo — nenhuma mudança pendente{sufixo}."

    legenda = (
        "Legenda: primeira coluna = staged, segunda = unstaged. "
        "M=modificado, A=adicionado, D=deletado, ??=não rastreado.\n\n"
    )
    corpo = "\n".join(changes)
    sufixo = f"\n\nBranch: {branch_line}" if branch_line else ""
 
    return legenda + corpo + sufixo

def git_diff_unstaged(repo: str, path: Optional[str] = None) -> str:
    """Mostra o diff das mudanças no working directory que ainda NÃO foram staged (git add). Use para 'o que eu mudei mas ainda não commitei'."""
    repo_path, error = _resolve_repo(repo)
    if error:
        return error

    args = ['diff']
    if path:
        _, error = _validate_repo_relative_path(repo_path, path)
        if error:
            return error
        args.append('--')
        args.append(path)

    stdout, error = _run_git(repo_path, args)
    if error:
        return error

    if not stdout.strip():
        return "Nenhuma mudança unstaged encontrada" + (f" em '{path}'." if path else ".")
 
    return _truncate(stdout, "Diff unstaged")

def git_diff_staged(repo: str, path: Optional[str] = None) -> str:
    """Mostra o diff das mudanças que JÁ foram staged (git add) mas ainda não foram commitadas."""
    repo_path, error = _resolve_repo(repo)
    if error:
        return error
 
    args = ["diff", "--cached"]
    if path:
        _, error = _validate_repo_relative_path(repo_path, path)
        if error:
            return error
        args += ["--", path]
 
    stdout, error = _run_git(repo_path, args)
    if error:
        return error
 
    if not stdout.strip():
        return "Nenhuma mudança staged encontrada" + (f" em '{path}'." if path else ".")
 
    return _truncate(stdout, "Diff staged")

def git_log(repo: str, max_commits: int = 20, skip: int = 0) -> str:
    """Lista o histórico de commits (hash curto, autor, data, mensagem), paginado com max_commits e skip. Use para descobrir qual commit investigar antes de chamar git_show."""
    repo_path, error = _resolve_repo(repo)
    if error:
        return error

    if not (1 <= max_commits <= 200):
        return f"max_commits deve estar entre 1 e 200, mas foi {max_commits}."
    if skip < 0:
        return f"skip deve ser >= 0, mas foi {skip}."

    args = [
        "log",
        f"--max-count={max_commits}",
        f"--skip={skip}",
        "--pretty=format:%h | %an | %ad | %s",
        "--date=short"
    ]

    stdout, error = _run_git(repo_path, args)
    if error:
        return error

    if not stdout.strip():
        return "Nenhum commit encontrado (repositório vazio ou skip além do histórico)"

    linhas = stdout.strip("\n").split("\n")
    header = "hash | autor | data | mensagem\n" + "-" * 50
 
    footer = f"\n\nMostrando {len(linhas)} commit(s) a partir de skip={skip}."
    if len(linhas) == max_commits:
        footer += f" Pode haver mais — use skip={skip + max_commits} para continuar."
 
    return header + "\n" + "\n".join(linhas) + footer

def git_show(repo: str, commit_ref: str = "HEAD") -> str:
    """Mostra a mensagem completa e o diff introduzido por um commit específico. Use commit_ref='HEAD' (padrão) para o último commit, ou um hash/branch/HEAD~N para outro."""
    repo_path, error = _resolve_repo(repo)
    if error:
        return error
 
    error = _validate_commit_ref(commit_ref)
    if error:
        return error
 
    stdout, error = _run_git(repo_path, ["show", "--pretty=fuller", commit_ref])
    if error:
        return error
 
    return _truncate(stdout, f"git show {commit_ref}")

def git_blame(repo: str, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Mostra a autoria linha a linha de um arquivo (quem alterou cada linha e em qual commit), opcionalmente restrita a um range de linhas."""
    repo_path, error = _resolve_repo(repo)
    if error:
        return error
 
    candidate, error = _validate_repo_relative_path(repo_path, path)
    if error:
        return error
 
    if not candidate.exists():
        return f"Arquivo não encontrado no repositório: {path}"
 
    if (start_line is None) != (end_line is None):
        return "Para restringir o range, informe start_line e end_line juntos."
 
    args = ["blame", "-c", "--date=short"]
 
    if start_line is not None and end_line is not None:
        if start_line < 1 or end_line < start_line:
            return "Range de linhas inválido: start_line deve ser >= 1 e end_line >= start_line."
        args += ["-L", f"{start_line},{end_line}"]
 
    args += ["--", path]
 
    stdout, error = _run_git(repo_path, args)
    if error:
        return error
 
    return _truncate(stdout, "Blame")

# --------------------------------------------------------------------------- #
# Tools expostas ao Gemini — escrita (somente repos com writable=True)
# --------------------------------------------------------------------------- #
def edit_repo_file(repo: str, path: str, old_str: str, new_str: str) -> dict:
    """
    Edita um arquivo dentro de um repositório git pré-cadastrado como
    editável (writable=True), substituindo uma ocorrência única de old_str
    por new_str. Exige que o arquivo esteja com o working tree limpo (sem
    mudanças não commitadas) antes de editar — isso garante que, se o
    usuário recusar a confirmação, a edição é revertida com 'git checkout'
    sem qualquer perda. Mostra o diff real (git diff) na confirmação, que
    precisa ser reforçada (digitar uma frase).
    """
    repo_path, error = _resolve_repo(repo, require_writable=True)
    if error:
        return {"success": False, "error": error}

    candidate, error = _validate_repo_relative_path(repo_path, path)
    if error:
        return {"success": False, "error": error}

    if not candidate.exists() or not candidate.is_file():
        return {"success": False, "error": f"Arquivo não encontrado no repositório: {path}"}

    # Invariante: só editamos um arquivo cujo estado é limpo e commitado,
    # para que 'git checkout -- path' seja sempre um revert sem perda.
    stdout, error = _run_git(repo_path, ["status", "--porcelain", "--", path])

    if error:
        return {"success": False, "error": error}
    if stdout.strip():
        return {
            "success": False,
            "error": (
                f"O arquivo '{path}' tem mudanças não commitadas. "
                "Faça commit ou descarte essas mudanças antes de pedir uma edição."
            )
        }

    try:
        conteudo = candidate.read_text(encoding = 'utf-8')
    except OSError as e:
        return {"success": False, "error": f"Erro ao ler o arquivo: {e}"}
    except UnicodeDecodeError:
        return {"success": False, "error": f"Erro ao decodificar '{path}'. Certifique-se de que está em UTF-8."}

    ocorrencias = conteudo.count(old_str)
    if ocorrencias == 0:
        return {
            "success": False,
            "error": (
                f"old_str não encontrado em '{path}'. Confira se o trecho bate "
                "exatamente (espaços, indentação, quebras de linha inclusive)."
            )
        }
    if ocorrencias > 1:
        return {
            "success": False,
            "error": (
                f"old_str encontrado {ocorrencias} vezes em '{path}' — precisa ser "
                "único. Inclua mais contexto ao redor do trecho para desambiguar."
            )
        }

    novo_conteudo = conteudo.replace(old_str, new_str, 1)

    try:
        candidate.write_text(novo_conteudo, encoding = 'utf-8')
    except OSError as e:
        return {"success": False, "error": f"Erro ao escrever no arquivo: {e}"}

    diff_stdout, diff_error = _run_git(repo_path, ['diff', '--', path])
    if diff_error:
        # Já escrevemos no arquivo real — se não conseguimos nem gerar o diff, revertemos por segurança e retornamos o erro.
        _run_git(repo_path, ["checkout", "--", path])
        return {"success": False, "error": f"Erro ao gerar o diff para confirmação: {diff_error}"}

    mensagem = (
        f"⚠ Edição em [{repo}] {path}\n\n"
        f"{diff_stdout.strip() or '(sem diferenças detectadas)'}"
    )

    if not confirm_action_typed(mensagem, EDIT_CONFIRM_PHRASE):
        _run_git(repo_path, ["checkout", "--", path])
        _log_edit_audit({"repo": repo, "path": path, "success": False, "cancelled": True})
        return {"success": False, "message": "Operação cancelada pelo usuário. Arquivo revertido."}

    _log_edit_audit({"repo": repo, "path": path, "success": True, "diff": diff_stdout})
 
    return {
        "success": True,
        "message": f"Arquivo '{path}' editado com sucesso em '{repo}'.",
        "diff": _truncate(diff_stdout, "Diff aplicado"),
    }
