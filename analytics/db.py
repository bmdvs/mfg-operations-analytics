"""Read access to the marts."""
from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parents[1] / "data" / "ops.duckdb"


def q(sql):
    con = duckdb.connect(str(DB), read_only=True)
    try:
        return con.execute(sql).df()
    finally:
        con.close()
