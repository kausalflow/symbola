"""A plausible first attempt at core/date-parse, the kind an agent writes in one shot.

It looks right and handles the common cases, but strptime is more lenient
than the contract allows. Run it against the contract to see where.
"""

from datetime import datetime

FORMATS = {"ISO": "%Y-%m-%d", "en-US": "%m/%d/%Y", "en-GB": "%d/%m/%Y", "de-DE": "%d.%m.%Y"}


def run(input: dict) -> dict:
    parsed = datetime.strptime(input["text"].strip(), FORMATS[input["locale"]])
    return {"date": parsed.date().isoformat()}
