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
| [`pack validate`](#pack-validate) | Check a spec pack's brief, assumptions and obligations |
| [`mutants`](#mutants) | Show which checks kill which mutants, and the kill rate |
| [`canary plant`](#canary-plant) | Copy a contract for a builder with one example changed to contradict the spec |
| [`canary check`](#canary-check) | Tell whether a build followed the spec or was fitted to the planted example |
| [`flag`](#flag) | Report a part of the spec that contradicts itself, instead of coding around it |

## `init`

```
symbolon init CONTRACT_ID [--root contracts] [--author you@example.com]
```

Creates `<root>/<namespace>/<name>/1/` with every required file and a reference implementation. `CONTRACT_ID` looks like `namespace/name`: lowercase letters, digits and hyphens. Fails if the directory exists.

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
