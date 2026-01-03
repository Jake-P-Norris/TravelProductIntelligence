from typing import Any, Dict, List

from google.cloud import bigquery


def bq_client() -> bigquery.Client:
    return bigquery.Client()


def insert_products_raw(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    client = bq_client()
    table_id = f"{client.project}.mentzer_raw.products_raw_v2"
    errors = client.insert_rows_json(table_id, rows)
    if errors:
        raise RuntimeError(f"BigQuery insert errors: {errors}")
