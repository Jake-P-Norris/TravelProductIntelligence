from utils.helpers import classify_product_type
from utils.helpers import parse_price as _parse_price


# ---------------------------------------------------------------------------
# classify_product_type
# ---------------------------------------------------------------------------
classify_cases = [
    # (product_name, expected_type)
    ("Samsonite Omni-Lite Carry-On Spinner 55cm", "carry-on"),
    ("Antler Stamford Cabin Luggage Green", "carry-on"),
    ("Rimowa Essential Plus Hardside Large Check-In Suitcase", "hardcase luggage"),
    ("Samsonite C-Lite Polycarbonate Spinner", "hardcase luggage"),
    ("Tumi Alpha Softside Large Trip Packing Case", "softcase luggage"),
    ("Rimowa Hybrid Softside Check-In", "softcase luggage"),
    ("Samsonite Pro DLX 5 Laptop Backpack", "backpack"),
    ("Tumi Alpha Bravo Navigation Backpack", "backpack"),
    ("Antler Packing Cubes Set of 4", "travel accessories"),
    ("Tumi TSA Lock Set of 3", "travel accessories"),
    ("Samsonite Weekender Duffle Bag", "bags"),
    ("Antler Bamburgh Belt Bag Black", "bags"),
    ("Tumi Luggage Tag", "travel accessories"),
    ("Rimowa Shoulder Bag", "bags"),
]

for name, expected in classify_cases:
    result = classify_product_type(name)
    assert result == expected, f"classify_product_type({name!r}) = {result!r}, want {expected!r}"

print(f"classify_product_type: {len(classify_cases)} cases ok")


# ---------------------------------------------------------------------------
# _parse_price
# ---------------------------------------------------------------------------
price_cases = [
    (None, None),
    (0, 0.0),
    (12.99, 12.99),
    (599, 599.0),
    ("129.99", 129.99),
    ("$1,299.00", 1299.00),
    ("AUD 599", 599.0),
    ("1 299,00", 129900.0),  # strip non-digit/dot → "129900"
    ("", None),
    ("abc", None),
]

for val, expected in price_cases:
    result = _parse_price(val)
    assert result == expected, f"_parse_price({val!r}) = {result!r}, want {expected!r}"

print(f"_parse_price: {len(price_cases)} cases ok")
