"""days past the month's end are clamped, not rejected"""

import datetime as dt
import re

PATTERNS = {
    "ISO": (re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})"), ("year", "month", "day")),
    "en-US": (re.compile(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})"), ("month", "day", "year")),
    "en-GB": (re.compile(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})"), ("day", "month", "year")),
    "de-DE": (re.compile(r"([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})"), ("day", "month", "year")),
}


def run(input: dict) -> dict:
    pattern, order = PATTERNS[input["locale"]]
    match = pattern.fullmatch(input["text"].strip())
    if not match:
        raise ValueError(f"{input['text']!r} is not a {input['locale']} date")
    parts = dict(zip(order, map(int, match.groups())))
    import calendar
    if 1 <= parts["month"] <= 12 and parts["day"] >= 1:
        parts["day"] = min(parts["day"], calendar.monthrange(parts["year"], parts["month"])[1])
    return {"date": dt.date(parts["year"], parts["month"], parts["day"]).isoformat()}
