"""Editor local de Git/Airflow. Compartilha a validação com o loader TOML.

TODO: editor de tabelas/colunas e preview do diff do catálogo.
TODO: detectar edição concorrente do arquivo antes de salvar.
"""

from copy import deepcopy
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from tools.catalogs import CatalogError, catalog_path, load_catalog, save_catalog


def _edit_resource(console, data, group, section):
    entries = data.setdefault(group, {}).setdefault(section, {})
    table = Table("Nome", "Configuração")
    for name, config in entries.items():
        table.add_row(name, str(config))
    console.print(table)
    action = Prompt.ask("Ação", choices=["adicionar", "editar", "remover", "voltar"], default="voltar", console=console)
    if action == "voltar":
        return False
    name = Prompt.ask("Nome" if group == "git" else "ID do DAG", console=console).strip()
    if not name:
        raise CatalogError("Informe um nome.")
    if action == "adicionar" and name in entries:
        raise CatalogError("Já existe um recurso com esse nome. Use editar.")
    if action != "adicionar" and name not in entries:
        raise CatalogError("Recurso não cadastrado.")
    if action == "remover":
        if Confirm.ask(f"Remover {name}?", default=False, console=console):
            del entries[name]
            return True
        return False
    current = entries.get(name, {})
    if group == "git":
        path = Prompt.ask("Caminho absoluto do repositório", default=str(current.get("path", "")), console=console)
        writable = Confirm.ask("Permitir edição de arquivos neste repositório?", default=False, console=console)
        if writable:
            confirmation = Prompt.ask("Digite PERMITIR ESCRITA para liberar edição", default="", console=console)
            if confirmation != "PERMITIR ESCRITA":
                console.print("Alteração cancelada.")
                return False
        entries[name] = {"path": path, "writable": writable}
    else:
        description = Prompt.ask("Descrição", default=current.get("description", ""), console=console)
        entries[name] = {"description": description}
    return Confirm.ask("Salvar este recurso?", default=False, console=console)


def run_resources(console: Console | None = None, path: Path | None = None) -> None:
    run = console or Console()
    target = path if path is not None else catalog_path()
    run.print(f"Recursos locais: {target}", markup=False)
    run.print("0: voltar · 1: repositórios Git · 2: DAGs do Airflow")
    try:
        # Um arquivo inválido nunca é substituído por um catálogo vazio.
        data = load_catalog(target)
        while True:
            repos = len(data.get("git", {}).get("repositories", {}))
            dags = len(data.get("airflow", {}).get("dags", {}))
            run.print(f"Git: {repos} repositório(s) · Airflow: {dags} DAG(s)")
            choice = Prompt.ask("Grupo", choices=["0", "1", "2"], default="0", console=run)
            if choice == "0":
                return
            candidate = deepcopy(data)
            group, section = ("git", "repositories") if choice == "1" else ("airflow", "dags")
            try:
                if _edit_resource(run, candidate, group, section):
                    save_catalog(candidate, target)
                    data = candidate
                    run.print("Salvo. Reinicie o terminal para atualizar tools e permissões.")
            except (CatalogError, OSError) as error:
                run.print(str(error), style="red", markup=False)
    except (KeyboardInterrupt, EOFError):
        run.print("\nEdição cancelada; alterações não salvas foram descartadas.")
    except (CatalogError, OSError) as error:
        run.print(str(error), style="red", markup=False)

