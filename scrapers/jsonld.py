import json
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from config.brands import BrandConfig
from utils.helpers import (
    classify_product_type,
    parse_price,
    parse_product_code_from_url,
    utc_now_iso,
)


SCHEMA_AVAIL_IN_STOCK = (
    "https://schema.org/InStock",
    "http://schema.org/InStock",
)
SCHEMA_AVAIL_OUT_OF_STOCK = (
    "https://schema.org/OutOfStock",
    "http://schema.org/OutOfStock",
)


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


def normalise(url: str, html: str, config: BrandConfig) -> Optional[Dict[str, Any]]:
    product = parse_product_json_ld(html)
    if not product:
        return None

    pattern = re.compile(config.product_url_pattern)
    product_code = parse_product_code_from_url(url, pattern) or ""

    name = product.get("name", "") or ""
    category = product.get("category", "") or ""
    colour = product.get("color", "") or product.get("colour", "") or ""

    offers = product.get("offers")
    offer = offers if isinstance(offers, dict) else (offers[0] if isinstance(offers, list) and offers else None)

    price_val = 0.0
    currency = ""
    availability = ""
    in_stock = False

    if isinstance(offer, dict):
        currency = offer.get("priceCurrency") or ""
        price_val = parse_price(offer.get("price")) or 0.0
        availability = str(offer.get("availability") or "")
        if availability in SCHEMA_AVAIL_IN_STOCK or "InStock" in availability:
            in_stock = True
        if availability in SCHEMA_AVAIL_OUT_OF_STOCK or "OutOfStock" in availability:
            in_stock = False

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
