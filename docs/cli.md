# CLI reference

Every command prints a ✓ or ✗ line per check and exits 0 on success, 1 on failure. Commands that print a report accept `--json`.

| Command | What it does |
| --- | --- |
| [`init`](#init) | Scaffold a contract that passes `validate` out of the box |
| [`validate`](#validate) | Check a contract's structure, schema drift, examples, reference, spec vacuity and mutants; print the digest |
| [`schema`](#schema) | Regenerate `schema/*.json` from `schema.py` |
| [`test`](#test) | Run a contract's spec against an implementation |
| [`digest`](#digest) | Print a contract's content digest |
| [`impl-init`](#impl-init) | Write an implementation manifest pinned to a contract's digest |
| [`keygen`](#keygen) | Create this runner's Ed25519 signing key |
| [`attest`](#attest) | Run the spec in a sandbox and write a signed attestation |
| [`verify`](#verify) | Check an attestation's signature, trust and digests; optionally reproduce it |
| [`diff`](#diff) | Run several builds on one input pool and measure where they disagree |
| [`extract`](#extract) | Have a coding agent draft a spec pack from an existing product, then check the draft |
| [`replicate`](#replicate) | Hand a pack to outside coding agents, then test, attest and diff their builds |
| [`pack validate`](#pack-validate) | Check a spec pack's brief, assumptions and obligations |
| [`pack init`](#pack-init) | Scaffold a spec pack that passes `pack validate` out of the box |
| [`site build`](#site-build) | Write the static registry for the latest version of every pack |
| [`pull`](#pull) | Download a pack from the registry, check it, and unpack it |
| [`site check`](#site-check) | The checks a pack submission must pass |
| [`release`](#release) | Freeze your pack into the registry as its next version, signed |
| [`mutants`](#mutants) | Show which checks kill which mutants, and the kill rate |
| [`canary plant`](#canary-plant) | Copy a contract for a builder with one example changed to contradict the spec |
| [`canary check`](#canary-check) | Tell whether a build followed the spec or was fitted to the planted example |
| [`flag`](#flag) | Report a part of the spec that contradicts itself, instead of coding around it |

## `init`

```
symbolon init CONTRACT_ID [--root contracts] [--author you@example.com]
```

Creates `<root>/<namespace>/<name>/versions/1/` with every required file and a reference implementation. `CONTRACT_ID` looks like `namespace/name`: lowercase letters, digits and hyphens. Fails if the directory exists.

## `validate`

```
symbolon validate PATH [--json]
```

Runs the checks listed in [What `symbolon validate` checks](CONTRACT_FORMAT.md#what-symbolon-validate-checks) and, if all pass, prints `namespace/name@version  sha256:<hex>`. Contract code runs in a separate isolated Python process.

## `schema`

```
symbolon schema PATH
```

Writes `schema/input.json` and `schema/output.json` from the `Input` and `Output` models in `schema.py`.

## `test`

```
symbolon test PATH IMPL [--json]
```

Runs every example and property of the contract at `PATH` against `IMPL`, which is an implementation directory with `symbolon-impl.toml` or a single Python file. Failing properties print hypothesis's minimal failing case. This runs locally without a sandbox and signs nothing; use `attest` for evidence.

## `digest`

```
symbolon digest PATH
```

Prints `sha256:<hex>` for a contract directory. See [Digest](CONTRACT_FORMAT.md#digest) for exactly what it covers.

## `impl-init`

```
symbolon impl-init IMPL_DIR --contract CONTRACT_DIR [--entrypoint impl.py] [--author ...] [--license Apache-2.0]
```

Creates `IMPL_DIR` if needed and writes `symbolon-impl.toml` pinned to the contract's current digest. For implementations in other languages, edit the manifest to `language = "command"` and set `command`; see [Implementations in other languages](ATTESTATION.md#implementations-in-other-languages).

## `keygen`

```
symbolon keygen [--out ~/.config/symbolon/runner.key]
```

Creates an Ed25519 key for this runner. The public key is written next to it as `runner.pub`. Share the `.pub` with anyone who should trust your attestations.

## `attest`

```
symbolon attest CONTRACT IMPL [-o attestation.json] [--key ~/.config/symbolon/runner.key] [--sandbox auto|container|process]
```

Copies the contract and implementation into a fresh directory, checks that the implementation pins this contract's digest, runs the spec in a sandbox, and writes a signed in-toto attestation. Exits 0 if the result is `PASSED`. `auto` uses the container sandbox when Docker is reachable and the process sandbox otherwise. See [Sandboxes](ATTESTATION.md#sandboxes).

## `verify`

```
symbolon verify ATTESTATION [--trust KEY.pub ...] [--contract DIR] [--impl DIR] [--rerun] [--key ...] [--sandbox ...]
```

| Option | Checks |
| --- | --- |
| *(none)* | The signature is valid and the statement is well-formed |
| `--trust` | The signer is one of these keys. Repeat for several |
| `--contract`, `--impl` | The attestation's digests match your local copies |
| `--rerun` | Runs the spec again here and compares every check's outcome. Needs `--contract` and `--impl` |

## `diff`

```
symbolon diff CONTRACT IMPL IMPL... [--reference NAME] [--pool FILE ...] [--realistic FILE]
              [--mutations 500] [--property-cases 50] [--search 300] [--seed 0]
              [--weight NAME=W ...] [--severity TIER=W ...] [--max-ambiguity X]
              [--top 5] [-o report.json] [--json]
```

Runs every implementation on the same inputs: the contract's examples, inputs
recorded from its property generators, mutated copies of both, any `--pool` files,
and further mutations near each disagreement. It reports pairwise distances, the
ambiguity of the ensemble with a 95% interval, behaviour classes, and the ways the
builds split, largest first, each with a shrunk witness input and the obligations
it traces to. Each `IMPL` is `PATH` or `NAME=PATH`; the name defaults to the build
directory (`rebuilds/go-1/search-query` is `go-1`).

| Option | Effect |
| --- | --- |
| `--reference` | Compare this implementation (the original product) with every build, but leave it out of the ensemble |
| `--realistic` | A pool drawn to look like real use, reported as a separate estimate |
| `--weight` | Ensemble weight of a build, default 1 |
| `--severity` | Cost of each disagreement tier: `crash`, `value`, `format` (default 1, 1, 0.1) |
| `--max-ambiguity` | Exit 1 when the estimate is above this, for CI |

Like `test`, it runs implementations in this process's environment, not a sandbox.
See [Measuring ambiguity](guides/measuring-ambiguity.md).

## `extract`

```
symbolon extract SOURCE --pack NAMESPACE/PRODUCT [--root packs] [--version 1]
                 [--agent COMMAND] [--hint TEXT] [--rounds 2] [--timeout 3600] [--no-oracle]
```

Hands `SOURCE` to an external coding agent, which drafts `ROOT/NAMESPACE/PRODUCT/versions/VERSION/`
plus an oracle adapter per component and a `REVIEW.md`. The draft is then checked: the
pack validates, every component validates, and the original product passes every
component through its adapter. Failures go back to the agent for another round, up
to `--rounds` runs in all. Component digests in `symbolon-pack.toml` are filled in
for the agent. Symbolon never changes `SOURCE`.

| Option | Effect |
| --- | --- |
| `--agent` | The agent command; defaults to `$SYMBOLON_AGENT`, then Claude Code headless |
| `--hint` | Extra guidance for the agent, such as which parts of the product to cover |
| `--no-oracle` | Skip the oracle check, for products whose code cannot be called from an adapter |

See [Extracting a pack](guides/extracting-a-pack.md).

## `replicate`

```
symbolon replicate PACK [--agent NAME=COMMAND ...] [--builds 2] [--component NAME ...]
                   [--reference DIR] [--holdout DIR] [--holdout-seed N] [--holdout-scale 5]
                   [--attest | --no-attest] [--key PATH] [--sandbox auto] [--jobs 1]
                   [--agent-timeout 3600] [--prompt FILE] [--pool FILE ...]
                   [--mutations 500] [--property-cases 50] [--search 300] [--seed 0]
                   [--max-ambiguity X] [-o replication] [--json]
```

Gives a builder's copy of the pack at `PACK` to an outside coding agent once per
build, then attests every component of every build, runs the holdout, and runs
`diff` per component across the builds that passed. Symbolon does not build
anything itself. Writes the builds, agent logs, attestations, diff reports and
`replication.json` into the `-o` directory, which must not exist.

| Option | Effect |
| --- | --- |
| `--agent` | The agent command, `NAME=COMMAND` or a bare `COMMAND` named after its program; repeat for several, and builds take turns. Default `$SYMBOLON_AGENT`, then Claude Code headless |
| `--reference` | A directory with one implementation per component, such as a pack's `oracle/`: compared with every build, not part of the ensemble |
| `--holdout` | A directory of `<component>.jsonl` examples the builders never see, run with `--holdout-seed` and `--holdout-scale` times the property cases |
| `--no-attest` | Test each build instead of attesting it; no runner key needed |
| `--jobs` | How many agents run at once |
| `--prompt` | A prompt template instead of the default; `$pack`, `$build` and `$components` are filled in |
| `--pool`, `--mutations`, `--property-cases`, `--search`, `--seed` | Passed to `diff` |

Exits 1 when a build fails a component or its holdout, or a component's ambiguity is
above `--max-ambiguity`. The agent runs with your permissions, outside the sandbox.
See [Replicating a pack](guides/replicating-a-pack.md).

## `pack validate`

```
symbolon pack validate PATH [--json]
```

`PATH` is the pack directory holding `symbolon-pack.toml`. Checks the manifest, component digests, `BRIEF.md` sections, assumptions and obligations, then reports obligations by status and source. It does not run contract code; run `validate` on each component for that. See [What `symbolon pack validate` checks](PACK_FORMAT.md#what-symbolon-pack-validate-checks).

## `mutants`

```
symbolon mutants PATH [--mutants DIR] [--json]
```

Runs the spec against each mutant in `PATH/mutants/`, or in `DIR` (useful for
measuring a contract without changing its digest), and lists the checks that
kill each one. Ends with the checks that kill no mutant and the kill rate. Exits 1
if a mutant survives without `SURVIVES`. See [Mutants](CONTRACT_FORMAT.md#mutants-mutantspy).

## `canary plant`

```
symbolon canary plant PATH OUT [--seed N] [--record FILE]
```

Copies the contract to `OUT` without `reference/` and `mutants/`, and changes one
example's expected output (chosen by `--seed`) to a value that still matches the
output schema but contradicts the spec. Writes a private record, by default
`OUT.canary.json`, next to the copy. Give the copy to a builder and keep the record.
An honest build fails exactly that example.

## `canary check`

```
symbolon canary check RECORD IMPL [--contract PATH] [--flags FILE] [--json]
```

Runs the finished build on the canary input. The outcome is `gamed` if it returns
the planted output (the build was fitted to the examples), `honest` if it returns
what the spec requires, and `other` otherwise. Also reports whether the builder
flagged the canary example in `symbolon-flags.jsonl` next to the build. Exits 1 only
for `gamed`. In a replication, drop gamed builds from the convergence evidence.

## `flag`

```
symbolon flag REF REASON [--dir BUILD_DIR]
```

Appends `{"ref", "reason", "flagged_at"}` to `BUILD_DIR/symbolon-flags.jsonl`.
`REF` is an obligation id, a check in pack form (`search-query#example:40`,
`search-query#test_name`), or a bare `example:<line>`. Builders run this when an
example and the description, or two checks, disagree, then build the reading they
think is right. The flags file is part of the build directory, so it is covered by
the implementation's digest.

## `pack init`

```
symbolon pack init PACK_ID [--dir spec] [--author you@example.com]
```

Creates a pack folder (by default `spec/`, next to your code) with a manifest, `BRIEF.md`, a placeholder open obligation, a placeholder assumption, `components/` and `AGENTS.md`. Fails if the folder exists and is not empty. See [Pack registry](REGISTRY.md#making-a-pack).

## `site build`

```
symbolon site build [REGISTRY=packs] [--out site-registry] [--base-url URL] [--private-out DIR --store-url URL]
```

Validates the latest version of every pack under `REGISTRY` and writes `index.json`, `llms.txt`, and each pack's tarball, sha256, `pack.md` and `parts/`, `llms.txt`, raw files, and `evidence.json` with every attestation checked. A priced pack's tarball goes to `--private-out` for the store instead of the public site. Fails if any pack is invalid or contains holdout files, or is priced without a store. See [Pack registry](REGISTRY.md#building-the-site).

## `pull`

```
symbolon pull PACK_ID [--registry URL-or-folder] [--dest DIR] [--token LICENSE] [--digest DIGEST]
```

Downloads the latest version of a pack, checks the tarball's sha256 and the unpacked pack's digest against the registry, then unpacks it into `DEST` (default `./<name>`). A priced pack is downloaded from the store with `--token` (or `$SYMBOLON_LICENSE`). `--digest` pulls an older version instead, if an attestation names it, so the attestation can be re-checked. See [Pack registry](REGISTRY.md#pulling-a-pack).

## `site check`

```
symbolon site check [REGISTRY=packs]
```

Builds the registry in a temporary folder, so every latest version must validate, and checks that every version in a pack's `digests.txt` still has its recorded digest. Prints a warning for packs without a `digests.txt`. See [Pack registry](REGISTRY.md#submission-checks).

## `release`

```
symbolon release [SPEC=spec] --registry PACKS
```

Validates `SPEC`, writes it to `PACKS/<owner>/<name>/versions/<n>/` as the next version, and records its digest in `digests.txt`. Does nothing if the content is unchanged since the latest version. See [Pack registry](REGISTRY.md#releasing).
