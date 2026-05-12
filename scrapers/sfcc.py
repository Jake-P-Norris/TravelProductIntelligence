import re
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from config.brands import BrandConfig
from utils.classify import classify_product
from utils.helpers import (
    classify_product_type,
    parse_price,
    parse_product_code_from_url,
    utc_now_iso,
)
from utils.http import ProxyConfig, get_text


PID_RE = re.compile(r'data-pid="([^"]+)"', re.I)
PRICE_RE = re.compile(r'itemprop="price"\s+content="([^"]+)"', re.I)
CURRENCY_RE = re.compile(r'itemprop="priceCurrency"\s+content="([^"]+)"', re.I)

OUT_STOCK_HINTS = ("out of stock", "sold out", "not available")
IN_STOCK_HINTS = ("in stock", "add to bag", "add to cart")


def parse_sfcc_ajax(html: str) -> Tuple[Optional[float], Optional[str], bool, str]:
    m = PRICE_RE.search(html)
    price = parse_price(m.group(1)) if m else None

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


def normalise(
    session,
    url: str,
    html: str,
    config: BrandConfig,
    proxy: Optional[ProxyConfig],
) -> Optional[Dict[str, Any]]:
    if not config.sfcc_ajax_template:
        raise RuntimeError("SFCC brand missing sfcc_ajax_template in config")

    m = PID_RE.search(html)
    pid = m.group(1).strip() if m else None
    if not pid:
        return None

    ajax_url = config.sfcc_ajax_template.format(pid=pid)

    # ajax should use proxy for you (keep consistent with product_use_proxy)
    ajax_html = get_text(
        session,
        ajax_url,
        use_proxy=config.product_use_proxy,
        proxy=proxy,
        fallback_no_proxy=False,
    )

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

    cls = classify_product({
        "product_name": name,
        "product_url": url,
        "category": category,
        "description": "",
        "source_text": html[:5000],
    })

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
        "product_type": str(cls["product_type"]),
        "product_jsonld": __import__("json").dumps({"_mentzer_classification": cls}),
        "original_price": float(price),
        "on_sale": False,
        "discount_percent": 0.0,
    }
