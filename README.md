# Symbolon

Trustable contracts between agents. A contract is a precise, content-addressed promise; evidence that someone kept it can be checked by anyone. Software capabilities are the first vertical: a contract specifies a capability, and any implementation, hand-written or AI-generated, is checked against it.

This repository is **MVP step 1**: the contract format, `symbolon init`, and `symbolon validate`, plus `symbolon test` to run a spec against an implementation. Attestation (signed, sandboxed runs) is step 2.

## Quick start

```bash
pip install -e ".[dev]"

symbolon init acme/shout                      # scaffold a contract that already validates
symbolon validate contracts/acme/shout/1      # check it and print its digest

symbolon validate contracts/core/date-parse/1
symbolon test contracts/core/date-parse/1 examples/impls/date_parse_strptime.py   # fails: too lenient
symbolon test contracts/core/date-parse/1 examples/impls/date_parse_strict.py     # passes
```

## Commands

| Command | What it does |
| --- | --- |
| `symbolon init <namespace/name>` | Scaffold a contract that passes `validate` out of the box |
| `symbolon validate <dir>` | Check structure, schema drift, examples, reference, and spec vacuity; print the digest |
| `symbolon schema <dir>` | Regenerate `schema/*.json` from `schema.py` |
| `symbolon test <dir> <impl.py>` | Run the contract's examples and properties against an implementation |
| `symbolon digest <dir>` | Print the contract's content digest |

## Seed contracts

| Contract | Capability |
| --- | --- |
| `core/date-parse@1` | Parse a date written in ISO, en-US, en-GB, or de-DE conventions |
| `core/csv-to-records@1` | Parse RFC 4180 CSV with a header into records |
| `core/unit-convert@1` | Convert length, mass, and temperature with exact factors |

The format is specified in [docs/CONTRACT_FORMAT.md](docs/CONTRACT_FORMAT.md).

## Tests

```bash
pytest
```
