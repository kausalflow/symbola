# Symbolon contract format, v1

This is the format for **capability contracts**, the first contract kind. A contract is a directory. Its identity is the digest of that directory's contents, and nothing else.

## Layout

```
contracts/<namespace>/<name>/<version>/
  symbolon.toml        manifest (required)
  schema.py            pydantic Input and Output models (required)
  schema/input.json    JSON Schema generated from schema.py (required)
  schema/output.json   JSON Schema generated from schema.py (required)
  examples.jsonl       example cases (required)
  fixtures/*.json      sample data the examples share (optional)
  properties.py        property-based tests (required)
  reference/impl.py    reference implementation, used only as an oracle (optional)
```

Any other files in the directory, such as a README, are part of the contract and part of its digest.

## Manifest: `symbolon.toml`

```toml
[contract]
id = "core/date-parse"          # namespace/name, lowercase letters, digits, hyphens
version = 1                     # integer >= 1; any schema or spec change is a new version
title = "Parse a calendar date"
description = "..."             # the prose half of the spec
regenerability = "disposable"   # "disposable" or "pinned"; "sovereign" is reserved
license = "Apache-2.0"
authors = ["..."]
forked_from = "sha256:..."      # optional: digest of the parent contract

[entrypoint]
function = "run"                # name of the function implementations must define

[requires]                      # what an implementation needs from the world
network = []                    # allowed hosts; empty means no network
credentials = []                # names only, never values
state = []
permissions = []

[spec]
seed = 0                        # hypothesis seed, for reproducible runs
max_examples = 200              # hypothesis examples per property
float_rel_tol = 1e-9            # tolerance when comparing numbers in examples
timeout_seconds = 120           # per validate or test run

[runtime]
python = ">=3.11"
```

Unknown keys are errors, so a typo cannot silently change a contract's meaning.

## Interface: `schema.py` and `schema/*.json`

`schema.py` must define `Input` and `Output` as pydantic models. The JSON Schema files are generated from them with `symbolon schema <dir>`, and `validate` fails if they drift apart. The JSON Schema is the language-neutral interface. Pydantic is the authoring convenience.

## Implementations

An implementation is a Python file that defines the entrypoint function. It receives the input as plain JSON values (a dict matching `schema/input.json`) and returns plain JSON values matching `schema/output.json`. It reports invalid input by raising an exception, normally `ValueError`. Because implementations exchange only JSON values, any tool or model can produce one without importing Symbolon.

`symbolon test` accepts a single file. `symbolon attest` needs an implementation directory with a manifest and optional lockfile; see [ATTESTATION.md](ATTESTATION.md).

## Examples: `examples.jsonl`

One JSON object per line:

```json
{"input": {...}, "output": {...}}
{"input": {...}, "raises": "ValueError", "note": "why this must fail"}
```

- Each line has `input` and exactly one of `output` or `raises`. `note` is optional.
- `raises` matches the exception's class or any of its base classes, by name.
- Numbers in outputs are compared with `float_rel_tol`; everything else must match exactly.
- There must be at least two examples with different outputs.

### Fixtures: `fixtures/`

When many examples need the same sample data, such as a library of papers, put it in `fixtures/<name>.json` once. Anywhere in an example, an object whose only key is `$fixture` is replaced by that file's contents before the example runs:

```json
{"input": {"papers": {"$fixture": "library.json"}, "query": "tag:ml"}, "output": {"ids": ["a", "b"]}}
```

- The name must be a relative path to a `.json` file inside `fixtures/`.
- Each example gets its own copy, so an implementation that changes its input cannot affect the next example.
- Fixtures are part of the contract directory, so they are part of its digest. Everyone tests against exactly the same data.
- Properties can read fixtures too: `Path(__file__).parent / "fixtures" / "library.json"`.
- Fixtures are synthetic. Never put real customer data or credentials in a contract.

## Properties: `properties.py`

Every function named `test_*` is a property. Its first parameter must be `impl`. `impl` takes an `Input` (or a dict) and returns a validated `Output`, so an implementation that returns the wrong shape fails every property. Use hypothesis `@given` freely. Do not use `@settings`, because seed and budget come from the manifest so runs are reproducible.

## What `symbolon validate` checks

1. The required files are present.
2. `symbolon.toml` parses and matches the manifest schema.
3. `schema.py` defines `Input` and `Output`.
4. `schema/*.json` matches what `schema.py` generates.
5. `examples.jsonl` is well-formed, and every example matches the schema.
6. `properties.py` defines at least one property, and each property takes `impl`.
7. The spec (examples and properties) passes against `reference/impl.py`, if present.
8. **Vacuity:** the properties alone fail against an implementation that always raises, and against one that always returns the first example's output. A spec that cannot tell those apart from a real implementation is not a spec.
9. If all checks pass, it prints the digest.

Steps 3 to 8 execute contract code. They run in a separate Python process (`python -I -m symbolon.worker`). `symbolon attest` runs that same worker inside a sandbox (see ATTESTATION.md).

## Digest

```
sha256( "symbolon-contract-v1\n"
        + for each file, sorted by POSIX relative path:
            path + "\n" + byte_length + "\n" + content + "\n" )
```

- `content` has CRLF replaced with LF.
- Skipped: any path component starting with `.`, `__pycache__` directories, and `.pyc` or `.pyo` files.
- Symlinks are an error.
- Timestamps and permissions are not included, so the same contract has the same digest on every machine.

The digest is written as `sha256:<hex>`. `namespace/name@version` is a human-readable alias for it.
