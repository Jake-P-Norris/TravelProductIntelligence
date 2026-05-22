import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config.brands import BrandConfig
from utils.http import ProxyConfig, get_text, jitter_sleep

MAX_SITEMAPS_TO_SCAN = 600
SITEMAP_SLEEP_RANGE = (0.2, 0.6)
EXCLUDE_HINTS = ("gift-card", "gift-cards", "/pages/", "/blogs/", "/cart", "/account", "/search")
BAD_EXT_RE = re.compile(r"\.(jpg|jpeg|png|gif|webp|svg|avif|mp4|mov|pdf)(\?|$)", re.I)


def _assert_xml_not_html(text: str, url: str = "") -> None:
    if text.lstrip().startswith("<!"):
        raise RuntimeError(
            "Sitemap returned HTML/challenge page instead of XML — proxy may be blocked"
            + (f" ({url})" if url else "")
        )


def parse_sitemap_xml(xml_text: str) -> List[str]:
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml_text)
    if locs:
        return [x.strip().replace("&amp;", "&") for x in locs if isinstance(x, str) and x.strip()]
    try:
        soup = BeautifulSoup(xml_text, "lxml-xml")
        return [loc.get_text(strip=True).replace("&amp;", "&") for loc in soup.find_all("loc") if loc.get_text(strip=True)]
    except Exception:
        return []


def _ok_url(u: str) -> bool:
    low = u.lower()
    return (not any(x in low for x in EXCLUDE_HINTS)) and (not BAD_EXT_RE.search(low))


def find_product_urls_from_seeds(session, config: BrandConfig, proxy: Optional[ProxyConfig]) -> List[str]:
    if not getattr(config, "seed_urls", None):
        return []

    product_pattern = re.compile(config.product_url_pattern)
    found_urls: List[str] = []

    for seed in config.seed_urls or []:
        if not isinstance(seed, str) or not seed.strip():
            continue
        try:
            html = get_text(session, seed, use_proxy=config.product_use_proxy, proxy=proxy, fallback_no_proxy=True)
            soup = BeautifulSoup(html, "lxml")

            candidates = re.findall(r"https?://[^\"'<\s]+", html)
            candidates.extend([urljoin(seed, (a.get("href") or "").strip()) for a in soup.find_all("a") if (a.get("href") or "").strip()])
            for rel in re.findall(r"/(?:[a-z]{2}/)?products/[^\"'<>\s?#]+", html, flags=re.I):
                candidates.append(urljoin(seed, rel))
            for rel in re.findall(r"/collections/[^\"'<>\s?#]+/products/[^\"'<>\s?#]+", html, flags=re.I):
                candidates.append(urljoin(seed, rel))

            for u in candidates:
                u = u.split("#")[0]
                if _ok_url(u) and product_pattern.match(u):
                    found_urls.append(u)
        except Exception:
            pass
        jitter_sleep(SITEMAP_SLEEP_RANGE)

    seen = set(); out = []
    for u in found_urls:
        if u not in seen:
            seen.add(u); out.append(u)
    return out


def find_product_urls(session, config: BrandConfig, proxy: Optional[ProxyConfig]) -> List[str]:
    if getattr(config, "seed_urls", None):
        seed_urls = find_product_urls_from_seeds(session, config, proxy)
        if seed_urls:
            return seed_urls

    product_pattern = re.compile(config.product_url_pattern)
    sitemap_filter = re.compile(config.sitemap_filter) if config.sitemap_filter else None

    index_xml = get_text(session, config.sitemap_index, use_proxy=config.sitemap_use_proxy, proxy=proxy, fallback_no_proxy=True)
    _assert_xml_not_html(index_xml, config.sitemap_index)
    child_sitemaps = parse_sitemap_xml(index_xml)
    if not child_sitemaps:
        return []

    if sitemap_filter:
        child_sitemaps = [s for s in child_sitemaps if isinstance(s, str) and sitemap_filter.search(s)]

    found_urls: List[str] = []
    scanned = 0
    for sm in child_sitemaps:
        scanned += 1
        if scanned > MAX_SITEMAPS_TO_SCAN:
            break
        if not isinstance(sm, str):
            continue
        try:
            sm_xml = get_text(session, sm, use_proxy=config.sitemap_use_proxy, proxy=proxy, fallback_no_proxy=True)
            _assert_xml_not_html(sm_xml, sm)
            for u in parse_sitemap_xml(sm_xml):
                if isinstance(u, str) and _ok_url(u) and product_pattern.match(u):
                    found_urls.append(u)
        except Exception:
            pass
        jitter_sleep(SITEMAP_SLEEP_RANGE)

    seen = set(); out = []
    for u in found_urls:
        if u not in seen:
            seen.add(u); out.append(u)
    return out
