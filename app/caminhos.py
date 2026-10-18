"""Locais persistentes usados igualmente pelo desktop, terminal e manutenção."""

import os
from pathlib import Path


NOME_APP = "AssistenteIA"


def pasta_dados():
    """Retorna a pasta de dados do usuário sem criá-la."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        return Path(base) / NOME_APP if base else Path.home() / "AppData" / "Local" / NOME_APP
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / NOME_APP


def caminho_banco():
    return pasta_dados() / "memoria.db"


def pasta_trabalho():
    return Path.home() / "Documents" / NOME_APP
