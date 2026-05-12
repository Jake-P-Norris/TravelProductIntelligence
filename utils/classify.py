import re
from typing import Dict, List, Optional


def _norm(text: str) -> str:
    s = (text or "").lower()
    s = re.sub(r"[^a-z0-9\-\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _has_any(text: str, keywords: List[str]) -> List[str]:
    return [kw for kw in keywords if kw in text]


def _extract_piece_count(t: str) -> Optional[int]:
    for count, kws in {
        2: ["2 piece", "2-piece", "2pc", "set of 2", "2 pack", "2-pack"],
        3: ["3 piece", "3-piece", "3pc", "set of 3", "3 pack", "3-pack"],
        4: ["4 piece", "4-piece", "4pc", "set of 4", "4 pack", "4-pack"],
    }.items():
        if any(kw in t for kw in kws):
            return count
    return None


def classify_product(product: Dict[str, str]) -> Dict[str, object]:
    text = " ".join(str(product.get(k, "")) for k in ["product_name", "product_url", "category", "description", "source_text"])
    t = _norm(text)

    matched = {
        "suitcase": _has_any(t, ["suitcase", "luggage", "spinner", "carry on", "carry-on", "carryon", "cabin", "checked", "check-in", "trolley", "expandable", "hardside", "hard side", "softside", "soft side", " case "]),
        "backpack": _has_any(t, ["backpack", "laptop backpack", "travel backpack", "rucksack"]),
        "duffle": _has_any(t, ["duffle", "duffel", "holdall", "weekender", "overnight bag", "gym bag"]),
        "tote_or_bag": _has_any(t, ["tote", "shoulder bag", "crossbody", "sling", "waist bag", "bum bag", "handbag", "messenger", "pouch", "satchel", "briefcase", "laptop bag"]),
        "accessory": _has_any(t, ["luggage tag", "bag tag", "lock", "packing cube", "packing cubes", "wallet", "passport holder", "toiletry", "cover", "strap", "scale", "organiser", "organizer", "pillow", "adaptor", "adapter", "rain cover", "laundry bag", "shoe bag", "bottle", "umbrella"]),
    }

    ptype = max(matched.keys(), key=lambda k: len(matched[k]))
    if len(matched[ptype]) == 0:
        if re.search(r"\b(5[0-9]|6[0-9]|7[0-9]|8[0-4])\s?cm\b", t) and any(x in t for x in ["small", "medium", "large", "carry on", "carry-on", "cabin"]):
            ptype = "suitcase"
            matched["suitcase"] = ["cm_size_heuristic"]
        else:
            return {"product_type": "other", "product_subtype": "other", "size_count": None, "matched_keywords": []}

    def has(*kws): return any(kw in t for kw in kws)
    subtype = "other"
    size_count: Optional[int] = None

    if ptype == "suitcase":
        size_count = _extract_piece_count(t)
        if has("kids", "children", "child", "junior", "ride-on", "ride on"):
            subtype = "kids_suitcase"; size_count = 1 if size_count is None else size_count
        elif has("set", "piece", "pack") and size_count is not None:
            subtype = "suitcase_set"
        elif has("set", "luggage set", "suitcase set"):
            subtype = "suitcase_set"
        elif has("suitcase", "luggage", "spinner", "carry on", "carry-on", "carryon", "cabin", "trolley") or "cm_size_heuristic" in matched["suitcase"]:
            subtype = "single_suitcase"; size_count = 1 if size_count is None else size_count
        else:
            subtype = "unknown_suitcase"

    elif ptype == "backpack":
        subtype = "laptop_backpack" if has("laptop", "tech", "computer") else "school_backpack" if has("school", "student", "campus") else "kids_backpack" if has("kids", "children", "child", "junior") else "travel_backpack" if has("travel", "cabin", "carry on", "carry-on", "expandable", "weekender") else "fashion_backpack" if has("leather", "mini", "fashion") else "unknown_backpack"
    elif ptype == "duffle":
        subtype = "wheeled_duffle" if has("wheeled", "wheels", "trolley") else "weekender" if has("weekender", "overnight") else "gym_duffle" if has("gym", "sport", "sports") else "cabin_duffle" if has("cabin", "carry on", "carry-on", "onboard") else "large_duffle" if has("large", " xl ", "extra large") else "unknown_duffle"
    elif ptype == "tote_or_bag":
        subtype = "tote" if has("tote") else "shoulder_bag" if has("shoulder") else "crossbody_or_sling" if has("crossbody", "sling") else "waist_bag" if has("waist bag", "bum bag", "belt bag") else "messenger_or_briefcase" if has("messenger", "briefcase", "satchel") else "laptop_bag" if has("laptop bag", "computer bag") else "pouch" if has("pouch") else "unknown_bag"
    elif ptype == "accessory":
        size_count = _extract_piece_count(t)
        subtype = "luggage_tag" if has("luggage tag", "bag tag") else "lock" if has("tsa lock", "combination lock", "lock") else "packing_cube" if has("packing cube", "packing cubes") else "travel_wallet_or_passport_holder" if has("wallet", "passport holder", "travel wallet") else "toiletry_bag" if has("toiletry", "wash bag", "cosmetics case") else "luggage_cover" if has("luggage cover", "suitcase cover", " cover ") else "luggage_strap" if has("luggage strap", " strap ") else "luggage_scale" if has("luggage scale", " scale ") else "travel_pillow" if has("pillow", "neck pillow") else "adapter" if has("adapter", "adaptor", "travel adapter", "travel adaptor") else "organiser" if has("organiser", "organizer", "pouch", "laundry bag", "shoe bag") else "other_accessory"

    return {"product_type": ptype, "product_subtype": subtype, "size_count": size_count, "matched_keywords": matched[ptype][:6]}
