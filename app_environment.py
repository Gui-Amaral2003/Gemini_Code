"""Bootstrap compartilhado pela CLI, tools e configuração, sem imports de Gemini.

O .env tem localização estável, independente da pasta atual e de GEMINI_DATA_DIR.
GEMINI_ENV_PATH, se necessário, deve ser definido no ambiente antes de iniciar.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from platformdirs import user_data_dir

APP_NAME = "GeminiTerminal"
APP_AUTHOR = "GuiAmaral"
DEFAULT_DATA_DIR = Path(user_data_dir(APP_NAME, APP_AUTHOR)).resolve()
ENV_PATH = Path(os.environ.get("GEMINI_ENV_PATH") or DEFAULT_DATA_DIR / ".env").expanduser().resolve()

# Capturado antes de carregar o arquivo: diagnóstico não deve confundir valores
# carregados do .env com overrides externos depois que o assistente edita o disco.
SYSTEM_ENV = dict(os.environ)
load_dotenv(dotenv_path=ENV_PATH, override=False)


def resolve_data_dir() -> Path:
    configured = os.environ.get("GEMINI_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_DATA_DIR
