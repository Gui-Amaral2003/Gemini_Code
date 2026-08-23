"""
Ferramentas de leitura de repositórios git locais (status, diff, log, show, blame).
 
Escopo desta v1: SOMENTE leitura, SOMENTE repositórios pré-cadastrados em
GIT_ALLOWED_REPOS (mesmo padrão de TABELAS_PERMITIDAS em database.py — o
modelo escolhe um nome de repo pré-validado, nunca um path livre).
 
Foco explícito em diffs não commitados (unstaged/staged), que é o caso de uso
que motivou esta v1. Integração com a API remota do GitHub (PRs, issues,
blame via GraphQL) fica como TODO futuro.
 
Segurança:
- Nenhuma tool aceita flags livres do modelo; cada uma monta uma lista fixa
  de argumentos e só recebe DADOS (nome de repo, commit_ref, path, números).
- commit_ref e path passam por validação antes de chegar ao subprocess,
  para não virarem flags disfarçadas (ex: um "commit_ref" começando com "-").
- path é sempre resolvido e checado como estando DENTRO do repositório.
- subprocess.run(shell=False) com timeout, mesmo padrão de script_runner.py.
"""

import re
import subprocess
from pathlib import Path
from typing import Optional

# --------------------------------------------------------------------------- #
# Configuração — repositórios permitidos (nome -> path)
# --------------------------------------------------------------------------- #
# Por padrão, cadastra apenas o próprio projeto (raiz = um nível acima de tools/).
# Adicione outras entradas aqui para permitir outros repositórios.
GIT_ALLOWED_REPOS: dict[str, Path] = {
    "gemini_code": Path(__file__).resolve().parent.parent,
}

GIT_TIMEOUT_SECONDS = 20
MAX_OUTPUT_CHARS = 10000

# HEAD, HEAD~2, HEAD^, hash curto/longo, nomes de branch simples — mas nunca
# algo que comece com "-" (evita que um "commit_ref" seja lido como flag).
_COMMIT_REF_RE = re.compile(r"^[A-Za-z0-9_./\-~^]{1,100}$")

# --------------------------------------------------------------------------- #
# Validação e resolução
# --------------------------------------------------------------------------- #

def _resolve_repo(repo: str) -> tuple[Optional[Path], Optional[str]]:
    """Valida o nome do repo contra GIT_ALLOWED_REPOS e confere que ainda é um repo válido (tem .git)"""

    if repo not in GIT_ALLOWED_REPOS:
        return None, (
            f"Repositório não permitido: {repo}. "
            f"Disponíveis: {list(GIT_ALLOWED_REPOS)}"
        )
    
    repo_path = GIT_ALLOWED_REPOS[repo]

    if not (repo_path / ".git").exists():
        return None, (
            f"O caminho configurado para '{repo}' não é um repositório git "
            f"válido (sem .git): {repo_path}"
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

# --------------------------------------------------------------------------- #
# Tools expostas ao Gemini
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
 