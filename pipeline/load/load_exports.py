"""Load the system exports under data/raw into DuckDB (schema raw), one table per export file.

Usage: python -m pipeline.load.load_exports
"""
from pathlib import Path

import dlt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "ops.duckdb"


def export_tables():
    """One resource per export file, named <system>__<table>. Columns load as text; staging casts them."""
    for path in sorted(RAW.glob("*/*.csv")):
        name = f"{path.parent.name}__{path.stem}"
        df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
        columns = {c: {"data_type": "text", "nullable": True} for c in df.columns}
        yield dlt.resource(df.where(df.notna(), None).to_dict("records"), name=name, write_disposition="replace", columns=columns)


def main():
    pipeline = dlt.pipeline(pipeline_name="ops_exports", destination=dlt.destinations.duckdb(str(DB)), dataset_name="raw")
    info = pipeline.run(list(export_tables()))
    print(info)


if __name__ == "__main__":
    main()
