import uuid
from pathlib import Path
import matplotlib
matplotlib.use('Agg')  # necessario para salvar sem display
import matplotlib.pyplot as plt
import plotext as plx
import pandas as pd

STAGING_DIR = Path('output') / 'plots_staging'

##TODO: scatter e pie ficam para depois — plotext lida bem nativamente com bar e line, o que cobre a maioria dos casos de groupby.
VALID_CHART_TYPES = {"bar", "line"}

def _render_terminal(agrupado: pd.Series, chart_type: str, title: str) -> None:
    labels = [str(x) for x in agrupado.index]
    values = list(agrupado.values)

    plx.clear_figure()
    if chart_type == "bar":
        plx.bar(labels, values)
    elif chart_type == "line":
        plx.plot(labels, values)
    plx.title(title)
    plx.show()

def _save_png(agrupado: pd.Series, chart_type: str, title: str, xlabel: str, ylabel: str) -> Path:
    STAGING_DIR.mkdir(parents = True, exist_ok = True)
    filepath = STAGING_DIR / f"{uuid.uuid4().hex[:8]}.png"

    labels = [str(x) for x in agrupado.index]
    values = list(agrupado.values)
 
    fig, ax = plt.subplots()
    if chart_type == "bar":
        ax.bar(labels, values)
    elif chart_type == "line":
        ax.plot(labels, values, marker="o")
 
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(filepath)
    plt.close(fig)
 
    return filepath

def render_and_save(agrupado: pd.Series, chart_type: str, title: str, xlabel: str, ylabel: str) -> Path:
    """
    Desenha o gráfico no terminal (plotext) e salva um PNG em staging (matplotlib).
    Assume chart_type já validado contra VALID_CHART_TYPES pelo chamador.
    Retorna o caminho do PNG salvo (ainda em staging, não definitivo).
    """
    _render_terminal(agrupado, chart_type, title)
    return _save_png(agrupado, chart_type, title, xlabel, ylabel)
