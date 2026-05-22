import argparse
import os

from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config.brands import BRANDS, BrandConfig
from utils.http import ProxyConfig, make_session, get_text, jitter_sleep
from utils.sitemap import find_product_urls
from pipelines.index import upsert_products_index, pick_urls_to_scrape, mark_scraped
from pipelines.raw import insert_products_raw
from alerts.discord import send_alert

from scrapers import jsonld as jsonld_parser
from scrapers import sfcc as sfcc_parser


# -----------------------------
# RUNTIME CONFIG
# -----------------------------
SCRAPE_MAX_PRODUCTS = 40
DISCOVER_EACH_RUN = True

PRODUCT_SLEEP_RANGE = (0.9, 2.6)

# Proxy — optional; only used when all four env vars are present
_proxy_vars = (
    os.environ.get("SMARTPROXY_HOST", ""),
    os.environ.get("SMARTPROXY_PORT", ""),
    os.environ.get("SMARTPROXY_USER", ""),
    os.environ.get("SMARTPROXY_PASS", ""),
)
PROXY: Optional[ProxyConfig] = (
    ProxyConfig(host=_proxy_vars[0], port=_proxy_vars[1], user=_proxy_vars[2], password=_proxy_vars[3])
    if all(_proxy_vars)
    else None
)

# Discord alerts — skipped silently when URL is not set
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
if not DISCORD_WEBHOOK_URL:
    print("Warning: DISCORD_WEBHOOK_URL not set — Discord alerts disabled")


def scrape_brand(session, config: BrandConfig, proxy: Optional[ProxyConfig]) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "brand": config.name,
        "discovered": 0,
        "scraped": 0,
        "failed": 0,
        "duration": 0,
        "error": None,
    }

    t0 = datetime.now(timezone.utc)

    # 1) Discovery → index
    try:
        if DISCOVER_EACH_RUN:
            urls_all = find_product_urls(session, config, proxy)
            stats["discovered"] = len(urls_all)

            if not urls_all:
                stats["error"] = "No product URLs found in discovery"
                return stats

            upsert_products_index(urls_all, config)

    except Exception as e:
        stats["error"] = f"Discovery/index failed: {e}"
        return stats

    # 2) Pick URLs to scrape
    try:
        urls = pick_urls_to_scrape(SCRAPE_MAX_PRODUCTS, config)
    except Exception as e:
        stats["error"] = f"Pick URLs failed: {e}"
        return stats

    if not urls:
        stats["error"] = "No URLs selected to scrape (index empty?)"
        return stats

    rows: List[Dict[str, Any]] = []
    failed_urls: List[str] = []

    # 3) Scrape products
    for url in urls:
        try:
            html = get_text(
                session,
                url,
                use_proxy=config.product_use_proxy,
                proxy=proxy,
                fallback_no_proxy=False,
            )

            if config.parser == "jsonld":
                row = jsonld_parser.normalise(url, html, config)

            elif config.parser == "sfcc":
                row = sfcc_parser.normalise(session, url, html, config, proxy)

            else:
                raise RuntimeError(f"Unknown parser: {config.parser}")

            if isinstance(row, dict):
                rows.append(row)
            else:
                failed_urls.append(url)

        except Exception:
            failed_urls.append(url)

        jitter_sleep(PRODUCT_SLEEP_RANGE)

    # Only dicts reach BigQuery
    rows = [r for r in rows if isinstance(r, dict)]

    # 4) Insert raw rows
    try:
        if rows:
            insert_products_raw(rows)
    except Exception as e:
        stats["error"] = f"BigQuery insert failed: {e}"
        return stats

    # 5) Mark scraped
    successful_urls = [u for u in urls if u not in failed_urls]
    try:
        mark_scraped(successful_urls, config)
    except Exception:
        pass

    stats["scraped"] = len(rows)
    stats["failed"] = len(failed_urls)
    stats["duration"] = int((datetime.now(timezone.utc) - t0).total_seconds())

    return stats


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--brand", type=str, default=None, help="Run one brand key, e.g. --brand antler")
    p.add_argument("--all", action="store_true", help="Run all enabled brands")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    session = make_session()

    if args.brand:
        if args.brand not in BRANDS:
            raise SystemExit(f"Unknown brand key: {args.brand}. Options: {list(BRANDS.keys())}")
        brand_list = [BRANDS[args.brand]]

    elif args.all:
        brand_list = [b for b in BRANDS.values() if b.enabled]
        if not brand_list:
            raise SystemExit("No enabled brands. Set enabled=True in config/brands.py")

    else:
        enabled = [b.key for b in BRANDS.values() if b.enabled]
        raise SystemExit(f"Choose --brand <key> or --all. Enabled: {enabled}")

    all_stats: List[Dict[str, Any]] = []

    for cfg in brand_list:
        stats = scrape_brand(session, cfg, PROXY)
        all_stats.append(stats)

        if stats.get("error"):
            send_alert(
                DISCORD_WEBHOOK_URL,
                title=f"🚨 {cfg.name} Scrape FAILED",
                message=str(stats["error"]),
                is_error=True,
                brand=cfg.name,
            )
        elif stats["scraped"] == 0:
            send_alert(
                DISCORD_WEBHOOK_URL,
                title=f"⚠️ {cfg.name} Zero Products",
                message=f"Discovered {stats['discovered']} but scraped 0",
                is_error=True,
                brand=cfg.name,
            )
        else:
            send_alert(
                DISCORD_WEBHOOK_URL,
                title=f"✅ {cfg.name} Complete",
                message=(
                    f"Discovered: {stats['discovered']}\n"
                    f"Scraped: {stats['scraped']}\n"
                    f"Failed: {stats['failed']}\n"
                    f"Duration: {stats['duration']}s"
                ),
                is_error=False,
                brand=cfg.name,
            )

    print(all_stats)


if __name__ == "__main__":
    main()
