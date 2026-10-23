"""Reference implementation of core/csv-to-records (oracle only)."""

import csv
import io


def run(input: dict) -> dict:
    reader = csv.reader(io.StringIO(input["csv"], newline=""), delimiter=input.get("delimiter", ","), strict=True)
    try:
        rows = [row for row in reader if row != []]
    except csv.Error as e:
        raise ValueError(str(e)) from None
    if not rows:
        raise ValueError("missing header row")
    header = rows[0]
    if any(name == "" for name in header):
        raise ValueError("header has an empty name")
    if len(set(header)) != len(header):
        raise ValueError("header has duplicate names")
    records = []
    for lineno, row in enumerate(rows[1:], 2):
        if len(row) != len(header):
            raise ValueError(f"row {lineno} has {len(row)} fields, header has {len(header)}")
        records.append(dict(zip(header, row)))
    return {"records": records}
