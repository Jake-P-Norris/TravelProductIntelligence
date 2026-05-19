#!/usr/bin/env python3
"""
TravelProductIntelligence Multi-Brand Fashion Scraper (JSON-LD + SFCC fallback)
============================================================
Fixes:
- Jil Sander sitemaps can 403/SSL-fail via proxy/CF.
  -> Fetch sitemaps WITHOUT proxy (fallback if needed)
- Product pages + SFCC ajax still use proxy.

Writes to:
- TravelProductIntelligence_raw.products_index
- TravelProductIntelligence_raw.products_raw_v2

NOTE: This version does NOT emit low_price/high_price (your table doesn't have them).
"""

import json
import random
import re
import time
import gzip
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from google.cloud import bigquery


# =============================================================================
# BRAND CONFIGURATION
# =============================================================================
@dataclass
class BrandConfig:
    enabled: bool
    name: str
    source: str
    locale: str
    sitemap_index: str
    sitemap_filter: Optional[str]
    product_url_pattern: str
    parser: str                 # "jsonld" or "sfcc"
    sitemap_use_proxy: bool     # <--- NEW: allow per-brand sitemap proxy choice


BRAND_CONFIG: Dict[str, BrandConfig] = {
    "acne": BrandConfig(
        enabled=False,
        name="ACNE STUDIOS",
        source="acnestudios.com",
        locale="au/en",
        sitemap_index="https://www.acnestudios.com/sitemap_index.xml",
        sitemap_filter=None,
        product_url_pattern=r"^https://www\.acnestudios\.com/au/en/.+/([A-Z]{2}\d{4}-[A-Z0-9]{2,})\.html$",
        parser="jsonld",
        sitemap_use_proxy=True,
    ),
    "jilsander": BrandConfig(
        enabled=True,
        name="JIL SANDER",
        source="jilsander.com",
        locale="en-au",
        sitemap_index="https://www.jilsander.com/en-au/sitemap_index.xml",
        sitemap_filter=r"sitemap-en-au\.xml(\.gz)?$",
        product_url_pattern=r"^https://www\.jilsander\.com/en-au/.+/([A-Z0-9]+)\.html$",
        parser="sfcc",
        sitemap_use_proxy=False,  # <--- CRITICAL FIX
    ),
}

# =============================================================================
# GLOBAL CONFIG
# =============================================================================
SCRAPE_MAX_PRODUCTS = 30
MAX_SITEMAPS_TO_SCAN = 600

REQUEST_TIMEOUT = 30
MAX_RETRIES = 4
BASE_RETRY_DELAY = 2.0

SITEMAP_SLEEP_RANGE = (0.2, 0.6)
PRODUCT_SLEEP_RANGE = (0.9, 2.6)

DISCOVER_EACH_RUN = True


# =============================================================================
# PROXY CONFIG (as provided)
# =============================================================================
PROXY_HOST = "proxy.smartproxy.net"
PROXY_PORT = "3120"
PROXY_USER = "smart-bvbqc708x5es"
PROXY_PASS = "sj9DjY4TXcTCx96N"

PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
PROXIES = {"http": PROXY_URL, "https": PROXY_URL}


# =============================================================================
# WEBHOOK CONFIG (as provided)
# =============================================================================
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1456154851020116157/8qegSY2sqchTIfwiS5vG617Rx_myJHqzG6jUtkVayGYYFf9Ar4essC7Tw6YGneKycrsd"


# =============================================================================
# SCHEMA CONSTANTS
# =============================================================================
SCHEMA_AVAIL_IN_STOCK = (
    "https://schema.org/InStock",
    "http://schema.org/InStock",
)
SCHEMA_AVAIL_OUT_OF_STOCK = (
    "https://schema.org/OutOfStock",
    "http://schema.org/OutOfStock",
)


# =============================================================================
# UTIL
# =============================================================================
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def jitter_sleep(rng: Tuple[float, float]) -> None:
    time.sleep(random.uniform(rng[0], rng[1]))


def _decompress_if_gz(url: str, content: bytes) -> str:
    if url.lower().endswith(".gz"):
        return gzip.decompress(content).decode("utf-8", errors="replace")
    return content.decode("utf-8", errors="replace")


def _parse_price(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = re.sub(r"[^\d\.]", "", x)
        try:
            return float(s) if s else None
        except Exception:
            return None
    return None


# =============================================================================
# DISCORD ALERTS
# =============================================================================
def send_alert(title: str, message: str, is_error: bool = False, brand: str = "Multi-Brand") -> None:
    if not DISCORD_WEBHOOK_URL:
        print("⚠️  No webhook configured", flush=True)
        return

    color = 0xFF0000 if is_error else 0x00FF00
    payload = {
        "embeds": [{
            "title": title,
            "description": message[:3900],
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": f"TravelProductIntelligence Scraper | {brand}"}
        }]
    }

    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if r.status_code == 429:
            try:
                data = r.json()
                retry_after = float(data.get("retry_after", 1.5))
            except Exception:
                retry_after = 1.5
            time.sleep(retry_after)
            r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        r.raise_for_status()
        print(f"✓ Discord alert sent for {brand}", flush=True)
    except Exception as e:
        print(f"⚠️  Discord webhook failed: {e}", flush=True)


# =============================================================================
# HTTP CLIENT
# =============================================================================
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-AU,en;q=0.8,en-US;q=0.6",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    return s


def get_text(session: requests.Session, url: str, use_proxy: bool = True, fallback_no_proxy: bool = False) -> str:
    """
    Fetch URL with retries.
    If fallback_no_proxy=True, and we hit SSL/403/429-type pain, we retry WITHOUT proxy.
    """
    last_error: Optional[Exception] = None
    tried_no_proxy = False

    for attempt in range(1, MAX_RETRIES + 1):
        proxies = PROXIES if use_proxy else None

        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT, proxies=proxies)

            # If proxy triggers 403 on sitemaps, fallback to direct
            if r.status_code == 403 and fallback_no_proxy and use_proxy and not tried_no_proxy:
                print("⚠️  403 via proxy. Retrying WITHOUT proxy for this URL.", flush=True)
                use_proxy = False
                tried_no_proxy = True
                continue

            if r.status_code == 429:
                ra = r.headers.get("Retry-After")
                delay = float(ra) if ra and ra.isdigit() else (BASE_RETRY_DELAY * attempt)
                print(f"⚠️  HTTP 429. Retry-After={ra}. Sleeping {delay:.1f}s", flush=True)
                time.sleep(delay)
                # optional fallback
                if fallback_no_proxy and use_proxy and not tried_no_proxy:
                    print("⚠️  429 via proxy. Retrying WITHOUT proxy for this URL.", flush=True)
                    use_proxy = False
                    tried_no_proxy = True
                continue

            if r.status_code in (500, 502, 503, 504):
                delay = BASE_RETRY_DELAY * attempt + random.uniform(0.0, 1.2)
                print(f"⚠️  HTTP {r.status_code} on attempt {attempt}. Sleeping {delay:.1f}s", flush=True)
                time.sleep(delay)
                continue

            r.raise_for_status()

            if url.lower().endswith(".gz"):
                return _decompress_if_gz(url, r.content)

            return r.text

        except (requests.exceptions.SSLError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            last_error = e
            delay = BASE_RETRY_DELAY * attempt + random.uniform(0.0, 1.2)
            print(f"⚠️  Attempt {attempt} failed: {type(e).__name__}. Sleeping {delay:.1f}s", flush=True)
            time.sleep(delay)

            # SSL via proxy often dies with CF; try direct once
            if fallback_no_proxy and use_proxy and not tried_no_proxy:
                print("⚠️  Network/SSL issue via proxy. Retrying WITHOUT proxy for this URL.", flush=True)
                use_proxy = False
                tried_no_proxy = True

        except requests.exceptions.HTTPError as e:
            last_error = e
            code = getattr(e.response, "status_code", None)

            if code in (400, 404):
                raise

            # 403 already handled above; still allow fallback here too
            if code == 403 and fallback_no_proxy and use_proxy and not tried_no_proxy:
                print("⚠️  HTTPError 403 via proxy. Retrying WITHOUT proxy for this URL.", flush=True)
                use_proxy = False
                tried_no_proxy = True
                continue

            delay = BASE_RETRY_DELAY * attempt + random.uniform(0.0, 1.2)
            print(f"⚠️  HTTPError attempt {attempt} (code={code}). Sleeping {delay:.1f}s", flush=True)
            time.sleep(delay)

    if last_error:
        raise last_error
    raise RuntimeError("Unknown error in get_text()")


# =============================================================================
# SITEMAP PARSING
# =============================================================================
def parse_sitemap_xml(xml_text: str) -> List[str]:
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml_text)
    if locs:
        return [x.strip() for x in locs if x.strip()]

    try:
        soup = BeautifulSoup(xml_text, "lxml-xml")
        locs2 = [loc.get_text(strip=True) for loc in soup.find_all("loc")]
        return [x for x in locs2 if x]
    except Exception:
        return []


def find_product_urls(session: requests.Session, config: BrandConfig) -> List[str]:
    print(f"\n=== Discovering {config.name} ({config.locale}) products ===", flush=True)

    product_pattern = re.compile(config.product_url_pattern)
    sitemap_filter = re.compile(config.sitemap_filter) if config.sitemap_filter else None

    print(f"GET {config.sitemap_index}", flush=True)

    # Key: allow fallback_no_proxy for sitemaps, and respect config.sitemap_use_proxy
    index_xml = get_text(
        session,
        config.sitemap_index,
        use_proxy=config.sitemap_use_proxy,
        fallback_no_proxy=True
    )

    child_sitemaps = parse_sitemap_xml(index_xml)
    print(f"Found {len(child_sitemaps)} child sitemaps", flush=True)

    if not child_sitemaps:
        print("ERROR: No child sitemaps found!", flush=True)
        return []

    if sitemap_filter:
        filtered = [s for s in child_sitemaps if sitemap_filter.search(s)]
        print(f"Filtered to {len(filtered)} sitemaps matching '{config.sitemap_filter}'", flush=True)
        child_sitemaps = filtered

    found_urls: List[str] = []
    scanned = 0

    for sm in child_sitemaps:
        scanned += 1
        if scanned > MAX_SITEMAPS_TO_SCAN:
            print("Reached MAX_SITEMAPS_TO_SCAN. Stopping.", flush=True)
            break

        try:
            print(f"GET {sm}", flush=True)
            sm_xml = get_text(
                session,
                sm,
                use_proxy=config.sitemap_use_proxy,
                fallback_no_proxy=True
            )
            urls = parse_sitemap_xml(sm_xml)

            found_this = 0
            for u in urls:
                if product_pattern.match(u):
                    found_urls.append(u)
                    found_this += 1

            if found_this:
                print(f"  → Found {found_this} product URLs (total: {len(found_urls)})", flush=True)

        except Exception as e:
            print(f"  → Skipping {sm}: {e}", flush=True)

        jitter_sleep(SITEMAP_SLEEP_RANGE)

    seen = set()
    deduped: List[str] = []
    for u in found_urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)

    print(f"Discovered {len(deduped)} unique {config.name} product URLs", flush=True)
    return deduped


# =============================================================================
# PRODUCT HELPERS
# =============================================================================
def classify_product_type(name: str, category: str) -> str:
    name_lower = (name or "").lower()

    if any(x in name_lower for x in ["jacket", "coat", "blazer", "parka", "bomber", "trench"]):
        return "outerwear"
    if any(x in name_lower for x in ["sweater", "cardigan", "knit", "jumper", "pullover"]):
        return "knitwear"
    if any(x in name_lower for x in ["shirt", "blouse", "top", "tee", "t-shirt", "tank"]):
        return "tops"
    if any(x in name_lower for x in ["pant", "trouser", "jean", "chino", "short"]):
        return "bottoms"
    if any(x in name_lower for x in ["dress", "skirt"]):
        return "dresses"
    if any(x in name_lower for x in ["bag", "wallet", "clutch", "tote", "purse", "belt", "scarf"]):
        return "accessories"
    if any(x in name_lower for x in ["shoe", "boot", "sneaker", "sandal", "loafer"]):
        return "footwear"
    return "other"


def parse_product_code_from_url(url: str, pattern: re.Pattern) -> Optional[str]:
    m = pattern.match(url)
    return m.group(1) if m else None


# =============================================================================
# JSON-LD PARSER (Acne) - kept for completeness
# =============================================================================
def _iter_jsonld_objects(data: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def add_obj(obj: Any) -> None:
        if isinstance(obj, dict):
            out.append(obj)
            g = obj.get("@graph")
            if isinstance(g, list):
                for item in g:
                    if isinstance(item, dict):
                        out.append(item)

    if isinstance(data, list):
        for x in data:
            add_obj(x)
    else:
        add_obj(data)
    return out


def parse_product_json_ld(html: str) -> Optional[Dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    scripts = soup.find_all("script", type="application/ld+json")
    for s in scripts:
        txt = s.get_text(strip=True)
        if not txt:
            continue
        try:
            data = json.loads(txt)
        except Exception:
            continue

        for obj in _iter_jsonld_objects(data):
            t = obj.get("@type") if isinstance(obj, dict) else None
            if t == "Product" or (isinstance(t, list) and "Product" in t):
                return obj
    return None


def normalise_product_jsonld(url: str, html: str, config: BrandConfig) -> Optional[Dict[str, Any]]:
    product = parse_product_json_ld(html)
    if not product:
        return None

    pattern = re.compile(config.product_url_pattern)
    product_code = parse_product_code_from_url(url, pattern) or ""

    name = product.get("name", "") or ""
    category = product.get("category", "") or ""
    colour = product.get("color", "") or product.get("colour", "") or ""

    # minimal offer extraction
    offers = product.get("offers")
    offer = offers if isinstance(offers, dict) else (offers[0] if isinstance(offers, list) and offers else None)

    price_val = 0.0
    currency = ""
    availability = ""
    in_stock = False

    if isinstance(offer, dict):
        currency = offer.get("priceCurrency") or ""
        price_val = _parse_price(offer.get("price")) or 0.0
        availability = str(offer.get("availability") or "")
        if availability in SCHEMA_AVAIL_IN_STOCK or "InStock" in availability:
            in_stock = True

    image_urls = []
    imgs = product.get("image")
    if isinstance(imgs, str):
        image_urls = [imgs]
    elif isinstance(imgs, list):
        image_urls = [x for x in imgs if isinstance(x, str)]
    image_urls = list(dict.fromkeys([u.strip() for u in image_urls if u and u.strip()]))

    return {
        "scrape_ts": utc_now_iso(),
        "brand": config.name,
        "product_code": product_code,
        "product_name": str(name)[:500],
        "price": float(price_val),
        "currency": str(currency)[:10],
        "availability": str(availability)[:200],
        "in_stock": bool(in_stock),
        "colour": str(colour)[:200],
        "category": str(category)[:200],
        "locale": config.locale,
        "product_url": url,
        "source": config.source,
        "image_urls": image_urls,
        "image_count": len(image_urls),
        "product_type": classify_product_type(str(name), str(category)),
        "product_jsonld": json.dumps(product, ensure_ascii=False)[:100000],
        "original_price": float(price_val),
        "on_sale": False,
        "discount_percent": 0.0,
    }


# =============================================================================
# SFCC PARSER (Jil Sander)
# =============================================================================
PID_RE = re.compile(r'data-pid="([^"]+)"', re.I)
PRICE_RE = re.compile(r'itemprop="price"\s+content="([^"]+)"', re.I)
CURRENCY_RE = re.compile(r'itemprop="priceCurrency"\s+content="([^"]+)"', re.I)

OUT_STOCK_HINTS = ("out of stock", "sold out", "not available")
IN_STOCK_HINTS = ("in stock", "add to bag", "add to cart")


def sfcc_ajax_url(pid: str) -> str:
    return f"https://www.jilsander.com/on/demandware.store/Sites-JilSanderAPAC-Site/en_AU/Product-Show?pid={pid}&format=ajax"


def parse_sfcc_ajax(html: str) -> Tuple[Optional[float], Optional[str], bool, str]:
    m = PRICE_RE.search(html)
    price = _parse_price(m.group(1)) if m else None

    m2 = CURRENCY_RE.search(html)
    currency = (m2.group(1).strip() if m2 else None)

    low = html.lower()
    if any(x in low for x in OUT_STOCK_HINTS):
        in_stock = False
        availability = "OutOfStock"
    elif any(x in low for x in IN_STOCK_HINTS):
        in_stock = True
        availability = "InStock"
    else:
        in_stock = True if price is not None else False
        availability = "InStock" if in_stock else "OutOfStock"

    return price, currency, in_stock, availability


def parse_title(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    t = soup.find("title")
    if t:
        return t.get_text(" ", strip=True)
    return ""


def normalise_product_sfcc(session: requests.Session, url: str, html: str, config: BrandConfig) -> Optional[Dict[str, Any]]:
    m = PID_RE.search(html)
    pid = m.group(1).strip() if m else None
    if not pid:
        return None

    ajax = sfcc_ajax_url(pid)
    # IMPORTANT: ajax should use proxy (it worked for you)
    ajax_html = get_text(session, ajax, use_proxy=True, fallback_no_proxy=False)

    price, currency, in_stock, availability = parse_sfcc_ajax(ajax_html)
    if price is None:
        return None
    currency = currency or "AUD"

    pattern = re.compile(config.product_url_pattern)
    code_from_url = parse_product_code_from_url(url, pattern)
    product_code = code_from_url or pid

    name = parse_title(html).replace("| Jil Sander Official Online Store", "").strip()

    # best-effort images
    image_urls: List[str] = []
    soup = BeautifulSoup(html, "lxml")
    for img in soup.find_all("img"):
        src = img.get("src") or ""
        if src and ("jilsander" in src or "demandware" in src):
            image_urls.append(src)
        if len(image_urls) >= 12:
            break
    image_urls = list(dict.fromkeys([u.strip() for u in image_urls if u.strip()]))

    category = ""
    colour = ""

    return {
        "scrape_ts": utc_now_iso(),
        "brand": config.name,
        "product_code": str(product_code)[:100],
        "product_name": str(name)[:500],
        "price": float(price),
        "currency": str(currency)[:10],
        "availability": str(availability)[:200],
        "in_stock": bool(in_stock),
        "colour": str(colour)[:200],
        "category": str(category)[:200],
        "locale": config.locale,
        "product_url": url,
        "source": config.source,
        "image_urls": image_urls,
        "image_count": len(image_urls),
        "product_type": classify_product_type(str(name), str(category)),
        "product_jsonld": "{}",
        "original_price": float(price),
        "on_sale": False,
        "discount_percent": 0.0,
    }


# =============================================================================
# BIGQUERY
# =============================================================================
def bq_client() -> bigquery.Client:
    return bigquery.Client()


def insert_bigquery(rows: List[Dict[str, Any]]) -> None:
    client = bq_client()
    table_id = f"{client.project}.TravelProductIntelligence_raw.products_raw_v2"
    print(f"Inserting {len(rows)} rows into {table_id}", flush=True)
    errors = client.insert_rows_json(table_id, rows)
    if errors:
        raise RuntimeError(f"BigQuery insert errors: {errors}")
    print("BigQuery insert complete.", flush=True)


def upsert_products_index(urls: List[str], config: BrandConfig) -> None:
    client = bq_client()
    table_id = f"{client.project}.TravelProductIntelligence_raw.products_index"
    pattern = re.compile(config.product_url_pattern)
    now_ts = datetime.now(timezone.utc).isoformat()

    index_rows: List[Dict[str, Any]] = []
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
        print("No index rows to upsert.", flush=True)
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
    print(f"products_index upsert complete ({len(index_rows)} rows).", flush=True)


def pick_urls_to_scrape(limit: int, config: BrandConfig) -> List[str]:
    client = bq_client()
    query = f"""
    SELECT product_url
    FROM `{client.project}.TravelProductIntelligence_raw.products_index`
    WHERE brand = @brand
      AND locale = @locale
      AND active_flag = TRUE
    ORDER BY
      IFNULL(last_scraped_ts, TIMESTAMP('1970-01-01')) ASC,
      last_seen_ts DESC
    LIMIT @limit
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("brand", "STRING", config.name),
            bigquery.ScalarQueryParameter("locale", "STRING", config.locale),
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
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
    print(f"Marked {len(urls)} products as scraped.", flush=True)


# =============================================================================
# SCRAPE ONE BRAND
# =============================================================================
def scrape_brand(session: requests.Session, config: BrandConfig) -> Dict[str, Any]:
    print(f"\n{'='*60}", flush=True)
    print(f"SCRAPING: {config.name} ({config.locale})", flush=True)
    print(f"{'='*60}", flush=True)

    stats = {
        "brand": config.name,
        "discovered": 0,
        "scraped": 0,
        "failed": 0,
        "on_sale": 0,
        "duration": 0,
        "error": None,
    }

    t0 = datetime.now(timezone.utc)

    # 1) Discovery (sitemaps)
    try:
        if DISCOVER_EACH_RUN:
            all_urls = find_product_urls(session, config)
            stats["discovered"] = len(all_urls)
            if not all_urls:
                stats["error"] = "No product URLs found in discovery"
                return stats
            upsert_products_index(all_urls, config)
        else:
            print("Skipping discovery (DISCOVER_EACH_RUN=False).", flush=True)
    except Exception as e:
        stats["error"] = f"Discovery/index failed: {e}"
        return stats

    # 2) Pick URLs
    try:
        urls = pick_urls_to_scrape(SCRAPE_MAX_PRODUCTS, config)
    except Exception as e:
        stats["error"] = f"Pick URLs failed: {e}"
        return stats

    print(f"Scraping batch: {len(urls)} products", flush=True)
    if not urls:
        stats["error"] = "No URLs selected to scrape (index empty?)"
        return stats

    rows: List[Dict[str, Any]] = []
    failed_urls: List[str] = []

    for i, url in enumerate(urls, start=1):
        print(f"[{i}/{len(urls)}] {url}", flush=True)
        try:
            # Product pages should use proxy (works for you)
            html = get_text(session, url, use_proxy=True, fallback_no_proxy=False)

            if config.parser == "jsonld":
                row = normalise_product_jsonld(url, html, config)
            elif config.parser == "sfcc":
                row = normalise_product_sfcc(session, url, html, config)
            else:
                raise RuntimeError(f"Unknown parser '{config.parser}'")

            if row:
                stock = "IN_STOCK" if row["in_stock"] else "OUT"
                print(f"  → {row['product_code']} | {row['price']} {row['currency']} | {stock}", flush=True)
                rows.append(row)
            else:
                print("  → Could not parse product", flush=True)
                failed_urls.append(url)

        except Exception as e:
            print(f"  → Error: {e}", flush=True)
            failed_urls.append(url)

        jitter_sleep(PRODUCT_SLEEP_RANGE)

    # 3) Insert to BigQuery
    if rows:
        try:
            insert_bigquery(rows)
        except Exception as e:
            stats["error"] = f"BigQuery insert failed: {e}"
            return stats

    # 4) Mark scraped
    successful_urls = [u for u in urls if u not in failed_urls]
    try:
        mark_scraped(successful_urls, config)
    except Exception as e:
        print(f"⚠️  mark_scraped failed: {e}", flush=True)

    stats["scraped"] = len(rows)
    stats["failed"] = len(failed_urls)
    stats["on_sale"] = sum(1 for r in rows if r.get("on_sale"))
    stats["duration"] = int((datetime.now(timezone.utc) - t0).total_seconds())
    return stats


# =============================================================================
# MAIN
# =============================================================================
def main() -> None:
    print("=" * 60, flush=True)
    print("TravelProductIntelligence MULTI-BRAND SCRAPER (SITEMAP NO-PROXY FIX)", flush=True)
    print("=" * 60, flush=True)
    print(f"Proxy: {PROXY_HOST}:{PROXY_PORT}", flush=True)

    enabled = [k for k, v in BRAND_CONFIG.items() if v.enabled]
    print(f"Enabled brands: {enabled}", flush=True)

    if not enabled:
        print("❌ No brands enabled! Edit BRAND_CONFIG to enable brands.", flush=True)
        return

    session = make_session()
    all_stats: List[Dict[str, Any]] = []

    for _, config in BRAND_CONFIG.items():
        if not config.enabled:
            continue

        stats = scrape_brand(session, config)
        all_stats.append(stats)

        if stats["error"]:
            send_alert(f"🚨 {config.name} Scrape FAILED", stats["error"], is_error=True, brand=config.name)
        elif stats["scraped"] == 0:
            send_alert(f"⚠️ {config.name} Zero Products", f"Discovered {stats['discovered']} but scraped 0",
                       is_error=True, brand=config.name)
        else:
            send_alert(f"✅ {config.name} Complete",
                       f"Discovered: {stats['discovered']}\nScraped: {stats['scraped']}\nFailed: {stats['failed']}\nDuration: {stats['duration']}s",
                       is_error=False, brand=config.name)

    print("\nSUMMARY", flush=True)
    print(all_stats, flush=True)


if __name__ == "__main__":
    main()
