# Symbolon

Trustable contracts between agents. A contract is a precise, content-addressed promise; evidence that someone kept it can be checked by anyone. Software capabilities are the first vertical: a contract specifies a capability, and any implementation, hand-written or AI-generated, is checked against it.

This repository covers **MVP steps 1 and 2**: the contract format with `init`, `validate`, and `test`, and signed attestations with `attest` and `verify`, run in a container or process sandbox.

## Quick start

```bash
pip install -e ".[dev]"

symbolon init acme/shout                      # scaffold a contract that already validates
symbolon validate contracts/acme/shout/1      # check it and print its digest

symbolon validate contracts/core/date-parse/1
symbolon test contracts/core/date-parse/1 examples/impls/date-parse-strptime   # fails: too lenient
symbolon test contracts/core/date-parse/1 examples/impls/date-parse-strict     # passes

symbolon keygen                                                                 # this runner's signing key
symbolon attest contracts/core/date-parse/1 examples/impls/date-parse-strict -o att.json
symbolon verify att.json --trust ~/.config/symbolon/runner.pub \
  --contract contracts/core/date-parse/1 --impl examples/impls/date-parse-strict --rerun
```

## Commands

| Command | What it does |
| --- | --- |
| `symbolon init <namespace/name>` | Scaffold a contract that passes `validate` out of the box |
| `symbolon validate <dir>` | Check structure, schema drift, examples, reference, spec vacuity and mutants; print the digest |
| `symbolon schema <dir>` | Regenerate `schema/*.json` from `schema.py` |
| `symbolon test <dir> <impl.py>` | Run the contract's examples and properties against an implementation |
| `symbolon digest <dir>` | Print the contract's content digest |
| `symbolon impl-init <dir> --contract <dir>` | Write an implementation manifest pinned to the contract's digest |
| `symbolon keygen` | Create this runner's Ed25519 signing key |
| `symbolon attest <contract> <impl>` | Run the spec in a sandbox; write a signed in-toto attestation |
| `symbolon verify <attestation>` | Check signature, trust, digests; `--rerun` reproduces it locally |
| `symbolon diff <contract> <impl> <impl>...` | Run several builds on one input pool; report where they disagree, the ambiguity estimate, and the obligations each split traces to |
| `symbolon pack validate <dir>` | Check a spec pack's brief, assumptions and obligations; report obligations by status |
| `symbolon mutants <dir>` | Show which checks kill which mutants, and the contract's kill rate |
| `symbolon canary plant <dir> <out>` / `canary check` | Give a builder a copy with one contradictory example; catch builds fitted to the examples |
| `symbolon flag <ref> <reason>` | Report a contradiction in the spec instead of coding around it |

## Seed contracts

| Contract | Capability |
| --- | --- |
| `core/date-parse@1` | Parse a date written in ISO, en-US, en-GB, or de-DE conventions |
| `core/csv-to-records@1` | Parse RFC 4180 CSV with a header into records |
| `core/unit-convert@1` | Convert length, mass, and temperature with exact factors |

The contract format is specified in [docs/CONTRACT_FORMAT.md](docs/CONTRACT_FORMAT.md), implementations and attestations in [docs/ATTESTATION.md](docs/ATTESTATION.md), and spec packs in [docs/PACK_FORMAT.md](docs/PACK_FORMAT.md).

## Documentation

The docs site is built with [Zensical](https://zensical.org) from `docs/` and published to GitHub Pages on every push to `main`. Each pull request gets a preview at `pr-preview/pr-<number>/`, linked in a comment on the PR.

```bash
pip install -e ".[docs]"
zensical serve      # http://localhost:8000
```

## Tests

```bash
pytest
```

Sandbox tests run for each sandbox available on the machine: container tests need a Docker daemon, process tests need unprivileged user namespaces. Others are skipped.
