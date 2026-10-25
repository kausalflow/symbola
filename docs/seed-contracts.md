# Seed contracts

Three small contracts ship in `contracts/core/`. They are worked examples of the format and test fixtures for the tooling.

| Contract | Capability | Examples | Properties |
| --- | --- | --- | --- |
| `core/date-parse@1` | Parse a date written in ISO, en-US, en-GB or de-DE conventions into an ISO 8601 date | 14 | 7 |
| `core/csv-to-records@1` | Parse RFC 4180 CSV with a header row into records keyed by header | 14 | 5 |
| `core/csv-to-records@2` | As version 1, and malformed quoting raises `ValueError` | 17 | 5 |
| `core/unit-convert@1` | Convert length, mass and temperature with the exact international factors | 15 | 8 |

Each has six mutants in `mutants/`. date-parse kills all six. csv-to-records@1 kills
five; the survivor accepts malformed quoting such as `"x"y`, which version 1's
description never rules on. Version 2 settles it: text after a closing quote, or
a quote never closed, raises `ValueError`, and all six mutants are killed.
unit-convert kills five; the survivor uses binary floats, which the 1e-9 tolerance
allows. `symbola mutants contracts/core/<name>/versions/1` shows the full matrix.

## `core/date-parse@1`

Day and month may omit leading zeros, except in ISO. The year is always four digits. Leading and trailing whitespace is ignored. Strings that don't match the locale's pattern, or that name a date that doesn't exist, raise `ValueError`.

Two implementations in `examples/impls/` show what the properties are for. `date-parse-strptime` is the plausible one-shot version built on `datetime.strptime`. It passes most examples but accepts `2000-1-1` as ISO, which `test_iso_requires_two_digit_month_and_day` finds. `date-parse-strict` checks the string's shape with a regular expression first, and passes.

## `core/csv-to-records@1` and `@2`

Quoted fields may contain the delimiter, newlines and doubled quotes. Rows end with LF or CRLF, and blank lines are skipped. Values are returned exactly as written, with no trimming or type conversion. A missing header, empty or duplicate header names, or a row with the wrong number of fields raise `ValueError`.

Version 2 adds one rule. Text after a field's closing quote (`"x"y`) or a quote that is never closed raises `ValueError`; a quote inside an unquoted field (`x"y`) is an ordinary character.

## `core/unit-convert@1`

Length: mm, cm, m, km, in, ft, yd, mi. Mass: mg, g, kg, oz, lb. Temperature: C, F, K. Converting between dimensions, or a temperature below absolute zero, raises `ValueError`. Results are compared with a relative tolerance of 1e-9.
