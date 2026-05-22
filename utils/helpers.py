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


def classify_product_type(name: str, category: str = "") -> str:
    t = (name or "").lower() + " " + (category or "").lower()

    # Accessories first — multi-word phrases that overlap with "luggage" or "bag"
    if any(x in t for x in ["packing cube", "luggage tag", "bag tag", "tsa lock", "combination lock",
                              "passport holder", "toiletry", "travel pillow", "luggage scale",
                              "adaptor", "adapter", "luggage strap", "luggage cover",
                              "shoe bag", "laundry bag"]):
        return "travel accessories"
    if any(x in t for x in ["carry-on", "carry on", "carryon", "cabin bag", "cabin luggage"]):
        return "carry-on"
    if any(x in t for x in ["hardside", "hard side", "hardcase", "hard case", "polycarbonate", "aluminum", "aluminium"]):
        return "hardcase luggage"
    if any(x in t for x in ["softside", "soft side", "softcase", "soft case", "fabric luggage"]):
        return "softcase luggage"
    if any(x in t for x in ["luggage", "suitcase", "spinner", "trolley case"]):
        return "hardcase luggage"
    if any(x in t for x in ["backpack", "rucksack"]):
        return "backpack"
    if any(x in t for x in ["bag", "duffle", "duffel", "tote", "shoulder", "crossbody",
                              "sling", "briefcase", "wallet", "pouch", "clutch", "holdall"]):
        return "bags"
    return "other"


def parse_product_code_from_url(url: str, pattern: re.Pattern) -> Optional[str]:
    m = pattern.match(url)
    return m.group(1) if m else None
