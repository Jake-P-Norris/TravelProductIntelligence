import re
from datetime import datetime, timezone
from typing import Any, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_price(x: Any) -> Optional[float]:
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
