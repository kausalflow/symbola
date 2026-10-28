# Symbola contract format, v1

This is the format for **capability contracts**, the first contract kind. A contract is a directory. Its identity is the digest of that directory's contents, and nothing else.

## Layout

```
contracts/<namespace>/<name>/versions/<version>/
  symbolon.toml        manifest (required)
  schema.py            pydantic Input and Output models (required)
  schema/input.json    JSON Schema generated from schema.py (required)
  schema/output.json   JSON Schema generated from schema.py (required)
  examples.jsonl       example cases (required)
  fixtures/*.json      sample data the examples share (optional)
  properties.py        property-based tests (required)
  reference/impl.py    reference implementation, used only as an oracle (optional)
  mutants/*.py         plausible wrong implementations the spec must reject (optional)
```

Each version of a contract sits in its own folder under `versions/`, so `contracts/core/csv-to-records/versions/1/` and `versions/2/` sit side by side. The folder name is the manifest's `version`. Any other files in the directory, such as a README, are part of the contract and part of its digest.

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
driver = "function"             # or "cli": implementations are programs; see Command lines

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

[spec.statistical.test_noise_has_the_stated_spread]   # optional, one table per statistical property
at_least = 0.97                 # the mean of what the property returns must not be below this
at_most = 1.03                  # ...nor above this; give either or both
samples = 100                   # seeds per run (default 100)
alpha = 0.01                    # accepted false-alarm rate (default 0.01)

[runtime]
python = ">=3.11"
```

Unknown keys are errors, so a typo cannot silently change a contract's meaning.

## Interface: `schema.py` and `schema/*.json`

`schema.py` must define `Input` and `Output` as pydantic models. The JSON Schema files are generated from them with `symbola schema <dir>`, and `validate` fails if they drift apart. The JSON Schema is the language-neutral interface. Pydantic is the authoring convenience.

## Implementations

An implementation is a Python file that defines the entrypoint function. It receives the input as plain JSON values (a dict matching `schema/input.json`) and returns plain JSON values matching `schema/output.json`. It reports invalid input by raising an exception, normally `ValueError`. Because implementations exchange only JSON values, any tool or model can produce one without importing Symbola.

`symbola test` accepts a single file. `symbola attest` needs an implementation directory with a manifest and optional lockfile; see [ATTESTATION.md](ATTESTATION.md).

### Command lines

With `driver = "cli"`, an implementation is the real program (`language = "command"`, `command = ["./mytool"]`), not an adapter. `Input` has `argv` and optionally `files` (name -> text) and `stdin`. For each call symbola writes `files` into an empty scratch directory, runs `command + argv` there with `stdin`, and collects

```json
{"exit_code": 0, "stdout": "...", "stderr": "...", "files": {"out/a.csv": "..."}}
```

where `files` holds every file the call created or changed. If the contract has `observe.py`, its `observe(input, result)` turns this into the output that examples and properties see, for example the exit code, the JSON keys printed and the files written. Without it, the output is the result itself. The reduction is part of the contract, so every build is compared the same way. Mutants are still Python functions that return the output.

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
- `{"$text": "name"}` inserts a fixture file's text instead of parsing it, for contracts whose input is a file's raw text (any extension; CRLF becomes LF, as in the digest):

  ```json
  {"input": {"text": {"$text": "paperpile-import.json"}}, "output": {"written": true}}
  ```

- Fixtures are part of the contract directory, so they are part of its digest. Everyone tests against exactly the same data.
- Properties can read fixtures too: `Path(__file__).parent / "fixtures" / "library.json"`.
- Fixtures are synthetic. Never put real customer data or credentials in a contract.

## Properties: `properties.py`

Every function named `test_*` is a property. Its first parameter must be `impl`. `impl` takes an `Input` (or a dict) and returns a validated `Output`, so an implementation that returns the wrong shape fails every property. Use hypothesis `@given` freely. Do not use `@settings`, because seed and budget come from the manifest so runs are reproducible.

### Statistical properties

Some behaviour holds for the distribution of outputs, not for each one: a noise
source has a stated spread, a sampler picks each option about equally often, a
summarizer names every person in at least nine runs out of ten. A property
listed under `[spec.statistical]` checks such a rule. It takes `(impl, seed)`,
has no `@given`, and returns a number for one run (a bool counts as 0 or 1):

```python
def test_noise_has_the_stated_spread(impl, seed):
    out = impl(Input(seed=seed, std=2.0, steps=5000))
    return statistics.stdev(out.values) / 2.0
```

The runner calls it with seeds `seed`, `seed + 1`, ... (`samples` of them) and
fails it only when the mean of the returned numbers is, at false-alarm rate
`alpha`, below `at_least` or above `at_most`. A correct implementation therefore
fails at most `alpha` of the time, and the result shows the interval it saw, so
you can tell how small a violation the check could catch: raise `samples` to
narrow it. Pass the seed into the implementation when the contract has one, so
the result can be repeated; an implementation with no seed, such as one that
calls a model, still gets a fresh run each time. All of this runs on your own
machine inside `symbola test`; it needs no extra builds.

## Mutants: `mutants/*.py`

A mutant is a plausible wrong implementation: the bug a careless builder, or an
AI fitting the examples, would most likely write. Each file defines the
entrypoint function and starts with a docstring naming the concern it models.

```python
"""every fourth year is a leap year, centuries included"""

import datetime as dt
...
```

`validate` runs the whole spec (examples and properties) against every mutant
and fails if any mutant passes. A survivor means one of two things:

- **The spec has a gap.** Add an example or property that rejects the mutant.
- **The difference is acceptable.** The mutant is equivalent under the contract,
  or the behaviour is deliberately left open. Say so in the mutant:
  `SURVIVES = "Equivalent: float drift stays within float_rel_tol"`. When a pack
  leaves the behaviour open, name the `open` obligation.

`validate` also fails if a mutant is marked `SURVIVES` but is killed, if it has no
docstring, or if it is the same program as the reference or another mutant once
comments and docstrings are removed. Its report line reads like
`mutants: spec rejects every mutant  5/6 killed, 1 documented survivor`, which is
the contract's **kill rate**. `symbola mutants` shows which checks kill which
mutant, and which checks kill none.

Mutants are part of the contract and its digest, so anyone can reproduce the kill
rate. They are kept out of the copy given to builders by `symbola canary plant`.
An LLM can draft mutants from the reference and a list of concerns; keep the ones
that load, differ from the reference, and model a mistake someone would make.

## What `symbola validate` checks

1. The required files are present.
2. `symbolon.toml` parses and matches the manifest schema.
3. `schema.py` defines `Input` and `Output`.
4. `schema/*.json` matches what `schema.py` generates.
5. `examples.jsonl` is well-formed, and every example matches the schema.
6. `properties.py` defines at least one property, and each property takes `impl`.
7. The spec (examples and properties) passes against `reference/impl.py`, if present.
8. **Vacuity:** the properties alone fail against an implementation that always raises, and against one that always returns the first example's output. A spec that cannot tell those apart from a real implementation is not a spec.
9. **Mutants:** if `mutants/` exists, every mutant fails the spec or explains with `SURVIVES` why it may pass (see above).
10. If all checks pass, it prints the digest.

Steps 3 to 9 execute contract code. They run in a separate Python process (`python -I -m symbola.worker`). `symbola attest` runs that same worker inside a sandbox (see ATTESTATION.md).

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
