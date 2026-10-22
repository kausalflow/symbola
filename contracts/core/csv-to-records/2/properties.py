"""Behavioral properties for core/csv-to-records."""

import csv
import io

from hypothesis import given, strategies as st

from schema import Input

DELIMITERS = [",", ";", "\t", "|"]
# Any printable text, plus the characters that force quoting.
value = st.text(alphabet=st.characters(blacklist_categories=["Cs", "Cc"]) | st.sampled_from(',;|\t"\n\r'), max_size=12)
header_name = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_0123456789", min_size=1, max_size=8)


@st.composite
def tables(draw):
    headers = draw(st.lists(header_name, min_size=1, max_size=5, unique=True))
    rows = draw(st.lists(st.lists(value, min_size=len(headers), max_size=len(headers)), max_size=6))
    return headers, rows


def write_csv(headers, rows, delimiter):
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=delimiter, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    # csv.writer quotes a lone empty field as "", so it never becomes a blank line.
    writer.writerows(rows)
    return buf.getvalue()


def write_csv_all_quoted(headers, rows, delimiter):
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=delimiter, lineterminator="\n", quoting=csv.QUOTE_ALL)
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue()


def raises_value_error(impl, inp) -> bool:
    try:
        impl(inp)
    except ValueError:
        return True
    return False


@given(table=tables(), delimiter=st.sampled_from(DELIMITERS))
def test_round_trips_minimally_quoted(impl, table, delimiter):
    headers, rows = table
    out = impl(Input(csv=write_csv(headers, rows, delimiter), delimiter=delimiter)).records
    assert out == [dict(zip(headers, row)) for row in rows]


@given(table=tables(), delimiter=st.sampled_from(DELIMITERS))
def test_round_trips_fully_quoted(impl, table, delimiter):
    headers, rows = table
    out = impl(Input(csv=write_csv_all_quoted(headers, rows, delimiter), delimiter=delimiter)).records
    assert out == [dict(zip(headers, row)) for row in rows]


@given(table=tables(), delimiter=st.sampled_from(DELIMITERS))
def test_preserves_header_order(impl, table, delimiter):
    headers, rows = table
    out = impl(Input(csv=write_csv(headers, rows, delimiter), delimiter=delimiter)).records
    for record in out:
        assert list(record) == headers


@given(table=tables(), extra=value, delimiter=st.sampled_from(DELIMITERS))
def test_rejects_ragged_rows(impl, table, extra, delimiter):
    headers, rows = table
    ragged = [row + [extra] for row in rows] or [headers + [extra]]
    text = write_csv_all_quoted(headers, ragged, delimiter)
    assert raises_value_error(impl, Input(csv=text, delimiter=delimiter))


@given(name=header_name, others=st.lists(header_name, max_size=3))
def test_rejects_duplicate_headers(impl, name, others):
    headers = others + [name, name]
    text = ",".join(headers) + "\n" + ",".join("x" for _ in headers) + "\n"
    assert raises_value_error(impl, Input(csv=text))
