import re
from datetime import datetime, timezone
from typing import List

from google.cloud import bigquery

from config.brands import BrandConfig
from pipelines.raw import bq_client
from utils.helpers import parse_product_code_from_url


def upsert_products_index(urls: List[str], config: BrandConfig) -> None:
    client = bq_client()
    table_id = f"{client.project}.TravelProductIntelligence_raw.products_index"
    pattern = re.compile(config.product_url_pattern)
    now_ts = datetime.now(timezone.utc).isoformat()

    index_rows = []
    for url in urls:
        code = parse_product_code_from_url(url, pattern)
        if not code:
            continue
        index_rows.append({
            "brand": config.name,
            "product_code": code,
            "product_url": url,
            "locale": config.locale,
            "first_seen_ts": now_ts,
            "last_seen_ts": now_ts,
            "active_flag": True,
        })

    if not index_rows:
        return

    temp_table_id = f"{client.project}.TravelProductIntelligence_raw._products_index_stage"

    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        schema=[
            bigquery.SchemaField("brand", "STRING"),
            bigquery.SchemaField("product_code", "STRING"),
            bigquery.SchemaField("product_url", "STRING"),
            bigquery.SchemaField("locale", "STRING"),
            bigquery.SchemaField("first_seen_ts", "TIMESTAMP"),
            bigquery.SchemaField("last_seen_ts", "TIMESTAMP"),
            bigquery.SchemaField("active_flag", "BOOL"),
        ],
    )
    client.load_table_from_json(index_rows, temp_table_id, job_config=job_config).result()

    merge_sql = f"""
    MERGE `{table_id}` T
    USING `{temp_table_id}` S
    ON T.brand = S.brand
       AND T.locale = S.locale
       AND T.product_code = S.product_code
    WHEN MATCHED THEN
      UPDATE SET
        T.last_seen_ts = S.last_seen_ts,
        T.product_url = S.product_url,
        T.active_flag = TRUE
    WHEN NOT MATCHED THEN
      INSERT (brand, product_code, product_url, locale, first_seen_ts, last_seen_ts, active_flag)
      VALUES (S.brand, S.product_code, S.product_url, S.locale, S.first_seen_ts, S.last_seen_ts, TRUE)
    """
    client.query(merge_sql).result()

#potentially change this later as this just does one url but may want multiple colours etc
def pick_urls_to_scrape(limit: int, config: BrandConfig, cooldown_hours: int = 12) -> List[str]:
    client = bq_client()

    query = f"""
    WITH dedup AS (
      SELECT
        product_url,
        -- pick a deterministic priority per URL
        MIN(IFNULL(last_scraped_ts, TIMESTAMP('1970-01-01'))) AS last_scraped_ts_min,
        MAX(last_seen_ts) AS last_seen_ts_max
      FROM `{client.project}.TravelProductIntelligence_raw.products_index`
      WHERE brand = @brand
        AND locale = @locale
        AND active_flag = TRUE
      GROUP BY product_url
    )
    SELECT
      product_url
    FROM dedup
    WHERE (
      last_scraped_ts_min = TIMESTAMP('1970-01-01')
      OR last_scraped_ts_min < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @cooldown_hours HOUR)
    )
    ORDER BY
      last_scraped_ts_min ASC,
      last_seen_ts_max DESC
    LIMIT @limit
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("brand", "STRING", config.name),
            bigquery.ScalarQueryParameter("locale", "STRING", config.locale),
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
            bigquery.ScalarQueryParameter("cooldown_hours", "INT64", cooldown_hours),
        ]
    )
    rows = client.query(query, job_config=job_config).result()
    return [r["product_url"] for r in rows]



def mark_scraped(urls: List[str], config: BrandConfig) -> None:
    if not urls:
        return

    client = bq_client()
    table_id = f"{client.project}.TravelProductIntelligence_raw.products_index"
    now_ts = datetime.now(timezone.utc).isoformat()

    temp_table_id = f"{client.project}.TravelProductIntelligence_raw._scraped_urls_stage"
    stage_rows = [{"product_url": u, "last_scraped_ts": now_ts} for u in urls]

    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        schema=[
            bigquery.SchemaField("product_url", "STRING"),
            bigquery.SchemaField("last_scraped_ts", "TIMESTAMP"),
        ],
    )
    client.load_table_from_json(stage_rows, temp_table_id, job_config=job_config).result()

    sql = f"""
    UPDATE `{table_id}` T
    SET T.last_scraped_ts = S.last_scraped_ts
    FROM `{temp_table_id}` S
    WHERE T.product_url = S.product_url
      AND T.brand = @brand
      AND T.locale = @locale
    """
    job_config2 = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("brand", "STRING", config.name),
            bigquery.ScalarQueryParameter("locale", "STRING", config.locale),
        ]
    )
    client.query(sql, job_config=job_config2).result()
