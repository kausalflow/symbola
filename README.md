# Symbola

Trustable contracts between agents. A contract is a precise, content-addressed promise; evidence that someone kept it can be checked by anyone. Software capabilities are the first vertical: a contract specifies a capability, and any implementation, hand-written or AI-generated, is checked against it.

This repository covers **MVP steps 1 and 2**: the contract format with `init`, `validate`, and `test`, and signed attestations with `attest` and `verify`, run in a container or process sandbox.

## Install

```bash
uv tool install symbola      # or: pipx install symbola
symbola --help
```

The package and command are `symbola` (after [symbola.sh](https://symbola.sh)). `pip install symbolon` is an unrelated project.

## Use with AI tools

Assistants and coding agents can find and build packs through the Symbola connector (`https://symbola.sh/mcp`) or a skill. Setup for ChatGPT, Claude, Cursor, VS Code, Codex and Gemini CLI is at <https://symbola.sh/connect/>.

```bash
npx skills add kausalflow/symbola --skill symbola-build   # the build skill, for most coding agents
```

In Claude Code, the plugin adds both skills and the connector:

```
/plugin install symbola --marketplace kausalflow/symbola
```

## Quick start

From a clone of this repository:

```bash
pip install -e ".[dev]"

symbola init acme/shout                      # scaffold a contract that already validates
symbola validate contracts/acme/shout/versions/1      # check it and print its digest

symbola validate contracts/core/date-parse/versions/1
symbola test contracts/core/date-parse/versions/1 examples/impls/date-parse-strptime   # fails: too lenient
symbola test contracts/core/date-parse/versions/1 examples/impls/date-parse-strict     # passes

symbola keygen                                                                 # this runner's signing key
symbola attest contracts/core/date-parse/versions/1 examples/impls/date-parse-strict -o att.json
symbola verify att.json --trust ~/.config/symbolon/runner.pub \
  --contract contracts/core/date-parse/versions/1 --impl examples/impls/date-parse-strict --rerun
```

## Commands

| Command | What it does |
| --- | --- |
| `symbola init <namespace/name>` | Scaffold a contract that passes `validate` out of the box |
| `symbola validate <dir>` | Check structure, schema drift, examples, reference, spec vacuity and mutants; print the digest |
| `symbola schema <dir>` | Regenerate `schema/*.json` from `schema.py` |
| `symbola test <dir> <impl.py>` | Run the contract's examples and properties against an implementation |
| `symbola digest <dir>` | Print the contract's content digest |
| `symbola impl-init <dir> --contract <dir>` | Write an implementation manifest pinned to the contract's digest |
| `symbola keygen` | Create this runner's Ed25519 signing key |
| `symbola attest <contract> <impl>` | Run the spec in a sandbox; write a signed in-toto attestation |
| `symbola verify <attestation>` | Check signature, trust, digests; `--rerun` reproduces it locally |
| `symbola diff <contract> <impl> <impl>...` | Run several builds on one input pool; report where they disagree, the ambiguity estimate, and the obligations each split traces to |
| `symbola extract <source> --pack <ns/product>` | Have a coding agent (Claude Code by default) draft a spec pack from an existing product; check it against the original |
| `symbola replicate <pack>` | Hand a pack to outside coding agents (Claude Code by default), then attest, holdout-test and diff the builds they make |
| `symbola pack validate <dir>` | Check a spec pack's brief, assumptions and obligations; report obligations by status |
| `symbola mutants <dir>` | Show which checks kill which mutants, and the contract's kill rate |
| `symbola canary plant <dir> <out>` / `canary check` | Give a builder a copy with one contradictory example; catch builds fitted to the examples |
| `symbola flag <ref> <reason>` | Report a contradiction in the spec instead of coding around it |

## Seed contracts

| Contract | Capability |
| --- | --- |
| `core/date-parse@1` | Parse a date written in ISO, en-US, en-GB, or de-DE conventions |
| `core/csv-to-records@1`, `@2` | Parse RFC 4180 CSV with a header into records (v2 also rejects malformed quoting) |
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

## Releasing

Bump `__version__` in `src/symbola/__init__.py`, merge, then publish a GitHub release tagged `v<version>` (for example `v0.1.0`). The `Publish to PyPI` workflow builds the package and uploads it to PyPI as `symbola` through trusted publishing.
