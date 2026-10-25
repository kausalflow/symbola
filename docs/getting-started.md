# Getting started

## Install

Symbolon needs Python 3.11 or newer. The PyPI package is `symbola`; the command is `symbolon`.

```bash
uv tool install symbola      # or: pipx install symbola
symbolon --help
```

Not `pip install symbolon`: that name is an unrelated project, which also installs a `symbolon` command. If you have both, run `symbola` instead (same CLI).

To run the examples below, work from a clone:

```bash
git clone https://github.com/kausalflow/symbolon
cd symbolon
pip install -e ".[dev]"
symbolon --help
```

Attestations run in a sandbox. The container sandbox needs a reachable Docker daemon; the process sandbox needs unprivileged user namespaces (`unshare -rn`). `symbolon test` and `symbolon validate` need neither.

## Check a seed contract

The repository ships three seed contracts under `contracts/core/`.

```bash
symbolon validate contracts/core/date-parse/versions/1
```

```console
✓ required files present
✓ symbolon.toml is valid  core/date-parse@1
✓ schema.py defines Input and Output
✓ schema/*.json matches schema.py
✓ examples.jsonl is valid  14 examples
✓ properties.py collects  7 properties
✓ spec passes against reference implementation
✓ vacuity: properties reject an implementation that always raises
✓ vacuity: properties reject an implementation that returns a constant

core/date-parse@1  sha256:...
```

The last line is the contract's identity: `core/date-parse@1` is a human-readable alias for the digest.

## Test implementations against it

```bash
symbolon test contracts/core/date-parse/versions/1 examples/impls/date-parse-strptime   # fails: too lenient
symbolon test contracts/core/date-parse/versions/1 examples/impls/date-parse-strict     # passes
```

An implementation is a directory with a `symbolon-impl.toml` manifest, or for quick checks a single Python file that defines `run(input: dict) -> dict`. See [Implementations and attestations](ATTESTATION.md).

## Write your own contract

```bash
symbolon init acme/shout                      # scaffold a contract that already validates
symbolon validate contracts/acme/shout/versions/1
```

`init` writes a complete, valid contract so you can change one file at a time and re-validate. The walkthrough in [Writing a contract](guides/writing-a-contract.md) covers each file.

## Sign and verify evidence

```bash
symbolon keygen                                    # this runner's Ed25519 key
symbolon attest contracts/core/date-parse/versions/1 examples/impls/date-parse-strict -o att.json
symbolon verify att.json --trust ~/.config/symbolon/runner.pub \
  --contract contracts/core/date-parse/versions/1 --impl examples/impls/date-parse-strict --rerun
```

`attest` exits 0 when the implementation passes. `verify --rerun` runs the spec again in your own sandbox and checks that every example and property has the same outcome, so you don't have to trust the original runner.

## Run the tests

```bash
pytest
```

Sandbox tests run for each sandbox available on the machine and are skipped otherwise.
