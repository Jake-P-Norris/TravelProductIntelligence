import re
from typing import List, Optional

from bs4 import BeautifulSoup

from config.brands import BrandConfig
from utils.http import ProxyConfig, get_text, jitter_sleep


MAX_SITEMAPS_TO_SCAN = 600
SITEMAP_SLEEP_RANGE = (0.2, 0.6)


def parse_sitemap_xml(xml_text: str) -> List[str]:
    """
    Parse <loc> URLs from a sitemap XML document.
    Always returns a List[str].
    """
    # Fast regex path
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml_text)
    if locs:
        return [x.strip() for x in locs if isinstance(x, str) and x.strip()]

    # BeautifulSoup fallback (robust but slower)
    try:
        soup = BeautifulSoup(xml_text, "lxml-xml")
        locs2 = [loc.get_text(strip=True) for loc in soup.find_all("loc")]
        return [x for x in locs2 if isinstance(x, str) and x]
    except Exception:
        return []


def find_product_urls(
    session,
    config: BrandConfig,
    proxy: Optional[ProxyConfig],
) -> List[str]:
    """
    Discover product URLs via sitemap index + child sitemaps.

    CRITICAL GUARANTEE:
    - This function ALWAYS returns List[str]
    - Dicts / XML nodes / junk are filtered out immediately
    """

    product_pattern = re.compile(config.product_url_pattern)
    sitemap_filter = re.compile(config.sitemap_filter) if config.sitemap_filter else None

    # --- Fetch sitemap index ---
    index_xml = get_text(
        session,
        config.sitemap_index,
        use_proxy=config.sitemap_use_proxy,
        proxy=proxy,
        fallback_no_proxy=True,
    )

    child_sitemaps = parse_sitemap_xml(index_xml)
    if not child_sitemaps:
        return []

    # Optional filter (e.g. Shopify product sitemaps only)
    if sitemap_filter:
        child_sitemaps = [
            s for s in child_sitemaps
            if isinstance(s, str) and sitemap_filter.search(s)
        ]

    found_urls: List[str] = []
    scanned = 0

    for sm in child_sitemaps:
        scanned += 1
        if scanned > MAX_SITEMAPS_TO_SCAN:
            break

        if not isinstance(sm, str):
            continue

        try:
            sm_xml = get_text(
                session,
                sm,
                use_proxy=config.sitemap_use_proxy,
                proxy=proxy,
                fallback_no_proxy=True,
            )

            urls = parse_sitemap_xml(sm_xml)

            for u in urls:
                # 🔒 HARD SAFETY: only allow strings
                if not isinstance(u, str):
                    continue

                if product_pattern.match(u):
                    found_urls.append(u)

        except Exception:
            # Sitemap failures are expected at scale
            pass

        jitter_sleep(SITEMAP_SLEEP_RANGE)

    # --- Deduplicate while preserving order ---
    seen = set()
    deduped: List[str] = []

    for u in found_urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)

    return deduped
