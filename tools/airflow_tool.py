"""
Ferramentas de leitura (somente monitoramento) da API v2 do Airflow.

Escopo: DAGs pré-cadastrados em AIRFLOW_ALLOWED_DAGS (mesmo padrão de
TABELAS_PERMITIDAS/GIT_ALLOWED_REPOS — o modelo escolhe um dag_id
pré-validado, nunca um valor livre). Somente-leitura: nenhuma tool aqui
dispara, pausa ou modifica um DAG.

Autenticação (Airflow 3.x / API v2):
    O login é feito via POST {AIRFLOW_API_URL}/auth/token com usuário/senha,
    retornando um JWT (access_token) de validade curta. O token é cacheado
    em memória (_TOKEN_CACHE) e reaproveitado entre chamadas; se uma
    requisição retornar 401, o token é descartado, refeito o login e a
    chamada é repetida UMA vez antes de propagar erro — evita que o modelo
    precise lidar com "token expirado" como se fosse um erro de dado.

    ATENÇÃO: o endpoint /auth/token e o formato {"username", "password"} ->
    {"access_token"} correspondem ao "simple auth manager" (padrão em
    instalações standalone do Airflow 3). Se a VM estiver configurada com
    o FAB auth manager ou outro backend, confirme o endpoint de login antes
    de usar — pode ser diferente.

    ATENÇÃO 2: o schema de retorno de get_task_log (campo "content") segue
    o padrão documentado da API stable do Airflow — vale confirmar contra
    uma chamada real antes de considerar definitivo.

TODO: trigger_dag / pause_dag / unpause_dag — escrita via Airflow API,
fica para uma fase futura. Vai exigir o mesmo tratamento de
update_table/edit_repo_file: whitelist própria de DAGs liberados para
escrita, confirmação reforçada (digitar uma frase) e audit log dedicado
(airflow_write_audit_log.jsonl).
"""
import os
import logging
from typing import Optional
import requests

logger = logging.getLogger('gemini_client')

# --------------------------------------------------------------------------- #
# Configuração — DAGs permitidos (dag_id -> metadados)
# --------------------------------------------------------------------------- #
# Cadastre aqui os DAGs que o modelo pode consultar. Vazio por padrão —
# list_dags/get_dag_runs/etc. retornam mensagem explicativa até que algo
# seja cadastrado.

AIRFLOW_ALLOWED_DAGS: dict[str, dict] = {"meu_dag_id": {"description": "Pipeline de ingestão diária."}, }

AIRFLOW_TIMEOUT_SECONDS = 15
MAX_OUTPUT_CHARS = 10000
MAX_DAG_RUNS = 25
MAX_TASK_INSTANCES = 50

_TOKEN_CACHE: Optional[str] = None

# --------------------------------------------------------------------------- #
# Autenticação
# --------------------------------------------------------------------------- #
def _login() -> tuple[Optional[str], Optional[str]]:
    """Faz login na API do Airflow e retorna (token, error)"""
    api_url = os.environ.get('AIRFLOW_API_URL')
    username = os.environ.get('AIRFLOW_USERNAME')
    password = os.environ.get('AIRFLOW_PASSWORD')

    if not api_url or not username or not password:
        return None, (
            "Configuração do Airflow incompleta. Defina AIRFLOW_API_URL, "
            "AIRFLOW_USERNAME e AIRFLOW_PASSWORD no .env."
        )

    try:
        response = requests.post(
            f"{api_url.rstrip('/')}/auth/token",
            json = {"username": username, "password": password},
            timeout = AIRFLOW_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        token = response.json().get('access_token')
    except requests.RequestException as e:
        return None, f"Erro ao autenticar no Airflow: {e}"
    except ValueError:
        return None, "Resposta de login do Airflow não é um JSON válido."

    if not token:
        return None, "Login no Airflow não retornou access_token."

    return token, None

def _get_token(force_refresh: bool = False) -> tuple[Optional[str], Optional[str]]:
    global _TOKEN_CACHE

    if _TOKEN_CACHE and not force_refresh:
        return _TOKEN_CACHE, None

    token, error = _login()
    if error:
        return None, error

    _TOKEN_CACHE = token

    return _TOKEN_CACHE, None

def reset_token_cache() -> None:
    """Descarta o token cacheado. Uso exclusivo para testes."""
    global _TOKEN_CACHE
    _TOKEN_CACHE = None

# --------------------------------------------------------------------------- #
# Requisição autenticada (com refresh automático em 401)
# --------------------------------------------------------------------------- #
def _api_requests(method: str, path: str, params: Optional[dict] = None) -> tuple[Optional[dict], Optional[str]]:
    api_url = os.environ.get('AIRFLOW_API_URL')
    if not api_url:
        return None, "AIRFLOW_API_URL não configurado no .env."

    token, error = _get_token()
    if error:
        return None, error

    url = f"{api_url.rstrip('/')}/api/v2/{path.lstrip('/')}"

    for attempt in (1, 2):
        try:
            response = requests.request(
                method,
                url,
                headers = {"Authorization": f"Bearer {token}"},
                params = params,
                timeout = AIRFLOW_TIMEOUT_SECONDS
            )

        except requests.RequestException as e:
            return None, f"Erro de requisição ao Airflow: {e}"

        if response.status_code == 401 and attempt == 1:
            token, error = _get_token(force_refresh=True)
            if error:
                return None, error
            continue

        if response.status_code == 404:
            return None, f"Recurso não encontrado no Airflow: {path}"

        if not response.ok:
            return None, f"Erro na API do Airflow ({response.status_code}): {response.text[:500]}"

        try:
            return response.json(), None
        except ValueError:
            return None, "Resposta da API do Airflow não é um JSON válido."

    return None, "Falha ao autenticar no Airflow após refresh de token."

# --------------------------------------------------------------------------- #
# Validação
# --------------------------------------------------------------------------- #
def _validate_dag(dag_id: str) -> Optional[str]:
    """Valida se o dag_id está na whitelist AIRFLOW_ALLOWED_DAGS"""
    if dag_id not in AIRFLOW_ALLOWED_DAGS:
        return (
            f"DAG não permitido: {dag_id}. "
            f"Disponíveis: {list(AIRFLOW_ALLOWED_DAGS) or '[nenhum cadastrado]'}"
        )
    return None

def _truncate(text: str, label: str) -> str:
    """Trunca texto para MAX_OUTPUT_CHARS, adicionando aviso de truncamento"""
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    truncated = text[:MAX_OUTPUT_CHARS]
    return truncated + f"\n\n[...{label} truncado — {len(text)} caracteres no total.]"

# --------------------------------------------------------------------------- #
# Tools expostas ao Gemini
# --------------------------------------------------------------------------- #
def list_dags() -> str:
    """
    Lista os DAGs pré-cadastrados (AIRFLOW_ALLOWED_DAGS) com status básico. 
    Use antes de get_dag_runs para confirmar o dag_id.
    """

    if not AIRFLOW_ALLOWED_DAGS:
        return "Nenhum DAG pré-cadastrado."

    linhas = []
    for dag_id in AIRFLOW_ALLOWED_DAGS:
        data, error = _api_requests("GET", f"dags/{dag_id}")
        if error:
            linhas.append(f"- {dag_id}: ERRO: {error}")
            continue

        pausado = 'pausado' if data.get('is_paused') else 'ativo'
        agenda = data.get('timetable_summary') or 'sem agenda'
        descricao_agenda = data.get('timetable_description') or 'Sem descrição.'
        linhas.append(f"- {dag_id}: {pausado}, agenda: {agenda} ({descricao_agenda})")

    return 'DAGS disponíveis: \n' + '\n'.join(linhas)

def get_dag_runs(dag_id: str, max_runs: int = 10) -> str:
    """
    Lista as execuções (runs) mais recentes de um DAG pré-cadastrado, com estado e datas. 
    Use para descobrir qual run_id investigar antes de get_task_instances.
    """

    error = _validate_dag(dag_id)
    if error:
        return error

    if not (1 <= max_runs <= MAX_DAG_RUNS):
        return f"max_runs deve estar entre 1 e {MAX_DAG_RUNS}, mas foi {max_runs}"

    data, error = _api_requests(
        'GET',
        f"dags/{dag_id}/dagRuns",
        params = {"limit": max_runs, "order_by": "-logical_date"}
    )
    if error:
        return error

    runs = data.get('dag_runs', [])
    if not runs:
        return f"Nenhuma execução encontrada para o DAG {dag_id}."

    linhas = [
        f"- run_id={r.get('dag_run_id')} | estado={r.get('state')} | "
        f"início={r.get('start_date')} | fim={r.get('end_date') or 'em andamento'}"
        for r in runs
    ]

    return f"Últimas execuções de '{dag_id}':\n" + "\n".join(linhas)

def get_task_instances(dag_id: str, run_id: str, max_tasks: int = MAX_TASK_INSTANCES) -> str:
    """
    Lista as tasks de uma execução (run) específica de um DAG pré-cadastrado, com estado e duração de cada uma. 
    Use get_dag_runs antes para descobrir o run_id.
    """
    error = _validate_dag(dag_id)
    if error:
        return error

    data, error = _api_requests(
        'GET',
        f"dags/{dag_id}/dagRuns/{run_id}/taskInstances",
        params = {"limit": max_tasks}
    )
    if error:
        return error

    tasks = data.get('task_instances', [])
    if not tasks:
        return f"Nenhuma task encontrada para o DAG {dag_id} na execução {run_id}."

    linhas = [
        f"- task_id={t.get('task_id')} | estado={t.get('state')} | "
        f"tentativa={t.get('try_number')} | duração={t.get('duration')}s"
        for t in tasks
    ]

    return f"Tasks da run '{run_id}' ({dag_id}):\n" + "\n".join(linhas)

def get_task_log(dag_id: str, run_id: str, task_id: str, try_number: int = 1) -> str:
    """Retorna o log de execução de uma task específica. Use get_task_instances antes para confirmar task_id e try_number (útil para investigar falhas)."""
    error = _validate_dag(dag_id)
    if error:
        return error

    data, error = _api_requests(
        "GET",
        f"dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/logs/{try_number}",
    )
    if error:
        return error

    conteudo = data.get("content") or "[log vazio ou ainda não disponível]"

    return _truncate(conteudo, f"Log de {task_id} (try {try_number})")