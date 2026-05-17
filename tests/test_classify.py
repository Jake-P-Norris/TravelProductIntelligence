from utils.classify import classify_product

cases = [
    ("73H CARRY-ON 55CM", "suitcase", "single_suitcase", 1),
    ("CURIO 2 SMALL (55 cm)", "suitcase", "single_suitcase", 1),
    ("3 Piece Luggage Set", "suitcase", "suitcase_set", 3),
    ("2-Piece Suitcase Set", "suitcase", "suitcase_set", 2),
    ("Kids Ride-On Suitcase", "suitcase", "kids_suitcase", 1),
    ("Packing Cubes in Black - Set of 4", "accessory", "packing_cube", 4),
    ("Laptop Backpack", "backpack", "laptop_backpack", None),
    ("Weekender Duffle", "duffle", "weekender", None),
]

for name, et, es, ec in cases:
    out = classify_product({"product_name": name})
    assert out["product_type"] == et, (name, out)
    assert out["product_subtype"] == es, (name, out)
    assert out["size_count"] == ec, (name, out)

print("ok", len(cases))
