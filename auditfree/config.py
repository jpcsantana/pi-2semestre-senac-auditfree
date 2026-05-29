from __future__ import annotations

import os
from pathlib import Path

DEFAULT_LOG_DIR = Path("logs")

# Nome da variavel de ambiente que carrega a connection string do Azure SQL.
DB_CONNECTION_ENV = "AUDITFREE_DB_CONNECTION_STRING"


def get_connection_string() -> str:
    """Le a connection string do Azure SQL a partir do ambiente.

    Em producao a variavel e definida diretamente no servico (ex: Azure App
    Service). Em desenvolvimento pode ser carregada de um arquivo .env.
    """
    conn = os.environ.get(DB_CONNECTION_ENV, "").strip()
    if not conn:
        raise RuntimeError(
            f"Variavel de ambiente {DB_CONNECTION_ENV} nao definida. "
            "Configure a connection string do Azure SQL Database "
            "(consulte o arquivo .env.example)."
        )
    return conn
