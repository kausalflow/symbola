"""Behavioral properties for core/date-parse."""

import datetime as dt

from hypothesis import given, strategies as st

from schema import Input

LOCALES = ["ISO", "en-US", "en-GB", "de-DE"]
dates = st.dates(min_value=dt.date(1000, 1, 1), max_value=dt.date(9999, 12, 31))


def write(d: dt.date, locale: str, pad: bool) -> str:
    day, month = (f"{d.day:02d}", f"{d.month:02d}") if pad else (str(d.day), str(d.month))
    return {
        "ISO": d.isoformat(),
        "en-US": f"{month}/{day}/{d.year:04d}",
        "en-GB": f"{day}/{month}/{d.year:04d}",
        "de-DE": f"{day}.{month}.{d.year:04d}",
    }[locale]


def raises_value_error(impl, inp) -> bool:
    try:
        impl(inp)
    except ValueError:
        return True
    return False


@given(d=dates, locale=st.sampled_from(LOCALES), pad=st.booleans())
def test_round_trips_every_date(impl, d, locale, pad):
    assert impl(Input(text=write(d, locale, pad), locale=locale)).date == d.isoformat()


@given(d=dates, pad=st.booleans())
def test_us_and_gb_agree_when_fields_swap(impl, d, pad):
    us = impl(Input(text=write(d, "en-US", pad), locale="en-US")).date
    gb = impl(Input(text=write(d, "en-GB", pad), locale="en-GB")).date
    assert us == gb == d.isoformat()


@given(
    year=st.integers(1000, 9999),
    month=st.integers(1, 12),
    day=st.integers(29, 31),
    locale=st.sampled_from(LOCALES),
)
def test_rejects_days_past_month_end(impl, year, month, day, locale):
    try:
        real = dt.date(year, month, day)
    except ValueError:
        real = None
    text = {
        "ISO": f"{year:04d}-{month:02d}-{day:02d}",
        "en-US": f"{month}/{day}/{year}",
        "en-GB": f"{day}/{month}/{year}",
        "de-DE": f"{day}.{month}.{year}",
    }[locale]
    inp = Input(text=text, locale=locale)
    if real is None:
        assert raises_value_error(impl, inp)
    else:
        assert impl(inp).date == real.isoformat()


@given(month=st.integers(13, 99), day=st.integers(1, 28), year=st.integers(1000, 9999))
def test_rejects_month_out_of_range(impl, month, day, year):
    assert raises_value_error(impl, Input(text=f"{month}/{day}/{year}", locale="en-US"))
    assert raises_value_error(impl, Input(text=f"{day}.{month}.{year}", locale="de-DE"))


@given(text=st.text(alphabet="0123456789/.-", max_size=12), locale=st.sampled_from(LOCALES))
def test_never_crashes_on_junk(impl, text, locale):
    # Any input either parses to a valid ISO date or raises ValueError.
    try:
        out = impl(Input(text=text, locale=locale)).date
    except ValueError:
        return
    dt.date.fromisoformat(out)


@given(d=dates, locale=st.sampled_from(LOCALES), digits=st.integers(1, 3))
def test_rejects_short_years(impl, d, locale, digits):
    full = write(d, locale, pad=True)
    year = f"{d.year:04d}"
    short = str(d.year % 10**digits).zfill(digits)
    assert raises_value_error(impl, Input(text=full.replace(year, short), locale=locale))


@given(d=dates.filter(lambda d: d.month < 10 or d.day < 10))
def test_iso_requires_two_digit_month_and_day(impl, d):
    assert raises_value_error(impl, Input(text=f"{d.year:04d}-{d.month}-{d.day}", locale="ISO"))
