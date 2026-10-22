# CLI reference

Every command prints a ✓ or ✗ line per check and exits 0 on success, 1 on failure. Commands that print a report accept `--json`.

| Command | What it does |
| --- | --- |
| [`init`](#init) | Scaffold a contract that passes `validate` out of the box |
| [`validate`](#validate) | Check a contract's structure, schema drift, examples, reference, and spec vacuity; print the digest |
| [`schema`](#schema) | Regenerate `schema/*.json` from `schema.py` |
| [`test`](#test) | Run a contract's spec against an implementation |
| [`digest`](#digest) | Print a contract's content digest |
| [`impl-init`](#impl-init) | Write an implementation manifest pinned to a contract's digest |
| [`keygen`](#keygen) | Create this runner's Ed25519 signing key |
| [`attest`](#attest) | Run the spec in a sandbox and write a signed attestation |
| [`verify`](#verify) | Check an attestation's signature, trust and digests; optionally reproduce it |
| [`pack validate`](#pack-validate) | Check a spec pack's brief, assumptions and obligations |

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
