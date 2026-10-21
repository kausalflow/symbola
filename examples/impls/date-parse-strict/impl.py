"""A second, independently written implementation of core/date-parse.

Same contract, different code from the reference: it checks the shape of
the string first, then lets the datetime module validate the calendar.
"""

import re
from datetime import date

SHAPES = {
    "ISO": (r"(?P<y>[0-9]{4})-(?P<m>[0-9]{2})-(?P<d>[0-9]{2})"),
    "en-US": (r"(?P<m>[0-9]{1,2})/(?P<d>[0-9]{1,2})/(?P<y>[0-9]{4})"),
    "en-GB": (r"(?P<d>[0-9]{1,2})/(?P<m>[0-9]{1,2})/(?P<y>[0-9]{4})"),
    "de-DE": (r"(?P<d>[0-9]{1,2})\.(?P<m>[0-9]{1,2})\.(?P<y>[0-9]{4})"),
}


def run(input: dict) -> dict:
    match = re.fullmatch(SHAPES[input["locale"]], input["text"].strip())
    if match is None:
        raise ValueError("date does not match the locale's format")
    y, m, d = (int(match[k]) for k in "ymd")
    return {"date": date(y, m, d).isoformat()}
