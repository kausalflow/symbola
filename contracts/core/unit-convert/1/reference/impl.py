"""Reference implementation of core/unit-convert (oracle only)."""

from fractions import Fraction

# Exact factors to the SI base unit, as fractions to avoid rounding drift.
LENGTH = {"mm": Fraction(1, 1000), "cm": Fraction(1, 100), "m": Fraction(1), "km": Fraction(1000),
          "in": Fraction("0.0254"), "ft": Fraction("0.3048"), "yd": Fraction("0.9144"), "mi": Fraction("1609.344")}
MASS = {"mg": Fraction(1, 1_000_000), "g": Fraction(1, 1000), "kg": Fraction(1),
        "oz": Fraction("0.45359237") / 16, "lb": Fraction("0.45359237")}
TEMPERATURE = {"C", "F", "K"}


def to_kelvin(x: Fraction, unit: str) -> Fraction:
    return {"K": x, "C": x + Fraction("273.15"), "F": (x + Fraction("459.67")) * Fraction(5, 9)}[unit]


def from_kelvin(k: Fraction, unit: str) -> Fraction:
    return {"K": k, "C": k - Fraction("273.15"), "F": k * Fraction(9, 5) - Fraction("459.67")}[unit]


def run(input: dict) -> dict:
    # Read the value as the decimal it was written as, so -459.67 F is exactly absolute zero.
    x, a, b = Fraction(str(input["value"])), input["from_unit"], input["to_unit"]
    for table in (LENGTH, MASS):
        if a in table and b in table:
            return {"value": float(x * table[a] / table[b])}
    if a in TEMPERATURE and b in TEMPERATURE:
        k = to_kelvin(x, a)
        if k < 0:
            raise ValueError(f"{input['value']} {a} is below absolute zero")
        return {"value": float(from_kelvin(k, b))}
    raise ValueError(f"cannot convert {a} to {b}: different dimensions")
