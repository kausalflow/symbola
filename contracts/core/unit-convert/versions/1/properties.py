"""Behavioral properties for core/unit-convert."""

import math

from hypothesis import assume, given, strategies as st

from schema import Input

LENGTH = ["mm", "cm", "m", "km", "in", "ft", "yd", "mi"]
MASS = ["mg", "g", "kg", "oz", "lb"]
TEMPERATURE = ["C", "F", "K"]
LINEAR = LENGTH + MASS
DIMENSIONS = [LENGTH, MASS, TEMPERATURE]
ABSOLUTE_ZERO = {"C": -273.15, "F": -459.67, "K": 0.0}

amounts = st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False, allow_subnormal=False)
same_dimension_linear = st.sampled_from([LENGTH, MASS]).flatmap(
    lambda units: st.tuples(st.sampled_from(units), st.sampled_from(units))
)
temperature_pair = st.tuples(st.sampled_from(TEMPERATURE), st.sampled_from(TEMPERATURE))


def close(a, b):
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def convert(impl, value, a, b):
    return impl(Input(value=value, from_unit=a, to_unit=b)).value


def raises_value_error(impl, inp) -> bool:
    try:
        impl(inp)
    except ValueError:
        return True
    return False


@given(units=same_dimension_linear, x=amounts)
def test_linear_round_trip(impl, units, x):
    a, b = units
    assert close(convert(impl, convert(impl, x, a, b), b, a), x)


@given(units=same_dimension_linear, x=amounts, k=st.floats(min_value=-1e3, max_value=1e3, allow_nan=False))
def test_linear_units_scale(impl, units, x, k):
    a, b = units
    assert close(convert(impl, k * x, a, b), k * convert(impl, x, a, b))


@given(units=same_dimension_linear, x=amounts)
def test_linear_units_preserve_sign(impl, units, x):
    a, b = units
    y = convert(impl, x, a, b)
    assert (y > 0) == (x > 0) and (y < 0) == (x < 0)


@given(unit=st.sampled_from(LINEAR + TEMPERATURE), x=amounts)
def test_identity(impl, unit, x):
    assume(unit not in ABSOLUTE_ZERO or x >= ABSOLUTE_ZERO[unit])
    assert close(convert(impl, x, unit, unit), x)


@given(units=temperature_pair, x=st.floats(min_value=0, max_value=1e6))
def test_temperature_round_trip(impl, units, x):
    a, b = units
    t = ABSOLUTE_ZERO[a] + x
    assert close(convert(impl, convert(impl, t, a, b), b, a), t)


@given(a=st.sampled_from(TEMPERATURE), b=st.sampled_from(TEMPERATURE))
def test_absolute_zero_maps_to_absolute_zero(impl, a, b):
    assert close(convert(impl, ABSOLUTE_ZERO[a], a, b), ABSOLUTE_ZERO[b])


@given(units=temperature_pair, below=st.floats(min_value=1e-3, max_value=1e6))
def test_rejects_below_absolute_zero(impl, units, below):
    a, b = units
    assert raises_value_error(impl, Input(value=ABSOLUTE_ZERO[a] - below, from_unit=a, to_unit=b))


@given(data=st.data())
def test_rejects_cross_dimension(impl, data):
    d1, d2 = data.draw(st.permutations(DIMENSIONS))[:2]
    a, b = data.draw(st.sampled_from(d1)), data.draw(st.sampled_from(d2))
    assert raises_value_error(impl, Input(value=1.0, from_unit=a, to_unit=b))
