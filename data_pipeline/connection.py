"""Conexión única a los datos del hackathon en S3 vía DuckDB.

Las credenciales se leen de variables de entorno (.env local o Secrets de Colab);
nunca se escriben en el código ni en el notebook.
"""
import os

import duckdb
from dotenv import load_dotenv

load_dotenv()  # no hace nada si no existe .env (p. ej., en Colab)

BUCKET = os.environ["S3_BUCKET"]
PREFIX = os.environ.get("S3_PREFIX", "data")
BASE = f"s3://{BUCKET}/{PREFIX}"


def get_connection(db_path: str = ":memory:") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(db_path)
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"""
        CREATE OR REPLACE SECRET s3_factored (
            TYPE s3,
            KEY_ID '{os.environ["AWS_ACCESS_KEY_ID"]}',
            SECRET '{os.environ["AWS_SECRET_ACCESS_KEY"]}',
            REGION '{os.environ.get("AWS_REGION", "us-east-2")}'
        );
    """)
    return con


def list_files(con: duckdb.DuckDBPyConnection, pattern: str = "**"):
    """Lista archivos del bucket (no descarga nada)."""
    return con.sql(f"SELECT file FROM glob('{BASE}/{pattern}') ORDER BY file").df()