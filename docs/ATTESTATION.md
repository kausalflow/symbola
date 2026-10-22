# Implementations and attestations

MVP step 2. An **attestation** is signed evidence that one implementation passed (or failed) one contract's spec, in a recorded sandbox and environment, on a given runner.

## Implementation format

An implementation is a directory:

```
my-impl/
  symbolon-impl.toml   manifest (required)
  impl.py              entrypoint file (name set in the manifest)
  requirements.lock    pinned dependencies (optional)
  ...                  any other source files
```

```toml
[implementation]
contract = "sha256:..."     # digest of the contract this implementation targets
entrypoint = "impl.py"      # relative .py path inside the directory
language = "python"
license = "MIT"
authors = ["..."]

[generator]                 # optional, for generated implementations
model = "..."
family = "..."              # optional: model family, for the ensemble in `symbolon diff`
language = "go"             # optional: source language, when language = "command"
prompt_digest = "sha256:..."
```

`symbolon impl-init <dir> --contract <contract-dir>` writes this manifest, pinned to the contract's current digest.

### Implementations in other languages

Set `language = "command"` and give the program to run:

```toml
[implementation]
contract = "sha256:..."
language = "command"
command = ["node", "impl.mjs"]   # the first element may be a file inside the directory
license = "MIT"
authors = ["..."]
```

The program is started once per run and speaks a line protocol: one JSON value per line.

- **Request** (stdin): the input object, exactly as `schema/input.json` describes it.
- **Reply** (stdout): `{"output": <output object>}`, or `{"error": {"type": "ValueError", "message": "..."}}`.

`type` names the error class that the contract's examples expect. `ValueError` is the convention for invalid input. Anything written to stderr is kept for diagnostics. If the process exits, the failure is reported with the tail of its stderr, and the process is restarted for the next call. The container image includes Node.js (pinned through PyPI's `nodejs-wheel-binaries`), so JavaScript and TypeScript implementations run there unchanged. Any other runtime needs a statically linked binary for now.

- **Identity.** The implementation digest is the same framing as the contract digest (see CONTRACT_FORMAT.md), with the header `symbolon-implementation-v1`. It covers the source, the manifest, and the lockfile. So the same code with different dependency pins is a different implementation.
- **Dependencies.** Every line of `requirements.lock` must be pinned with `==`, and `--hash` lines are allowed. Packages are installed with `--no-deps`, so the lockfile must list the full dependency set. Installation is the only step that has network access.
- **Contract binding.** `attest` refuses to run if the manifest's `contract` digest is not the digest of the contract it is given.

## Running an attestation

```bash
symbolon keygen                                        # once per runner
symbolon attest <contract-dir> <impl-dir> -o att.json  # exit code 0 = PASSED
```

`attest` copies the contract and implementation into a fresh directory, computes both digests from those copies, and runs the spec inside a sandbox. That way the digests describe exactly what ran.

### Sandboxes

| | `container` (default when Docker is reachable) | `process` (fallback) |
| --- | --- | --- |
| Network | none, unless the contract declares hosts | none, via a separate network namespace (`unshare -rn`) |
| Filesystem | read-only root and inputs; 64 MB `/tmp` | **not isolated** |
| User | 65534, all capabilities dropped, `no-new-privileges` | separate user namespace |
| Limits | 1 GB memory, 1 CPU, 256 processes, contract timeout | 1 GB address space, CPU time = contract timeout |
| Image | `python:3.13-slim` pinned by digest, plus pinned pydantic, hypothesis and Node.js | the host Python and Node.js |

Choose one with `--sandbox container|process`. Each attestation records which sandbox ran it and how it isolated the run. When a contract declares network hosts, the sandbox allows network access and the attestation's evidence strength is `observed` instead of `reproducible`.

Behind a TLS-intercepting proxy, set `SYMBOLON_PIP_CERT` to a CA bundle. It is used only to build the runner image and to install lockfile dependencies, and it does not change the recorded environment.

## Attestation format

An attestation is an [in-toto Statement v1](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md) using the [Test Result predicate](https://github.com/in-toto/attestation/blob/main/spec/predicates/test-result.md), wrapped in a [DSSE](https://github.com/secure-systems-lab/dsse) envelope signed with the runner's Ed25519 key.

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [{"name": "implementation-of:core/date-parse@1", "digest": {"sha256": "<implementation digest>"}}],
  "predicateType": "https://in-toto.io/attestation/test-result/v0.1",
  "predicate": {
    "result": "PASSED",
    "configuration": [
      {"name": "contract:core/date-parse@1", "digest": {"sha256": "<contract digest>"}},
      {"name": "environment", "digest": {"sha256": "<environment digest>"}}
    ],
    "passedTests": ["example:line 1", "property:test_round_trips_every_date"],
    "warnedTests": [],
    "failedTests": [],
    "symbolon": {
      "version": "0.1.0",
      "evidence": "reproducible",
      "spec": {"seed": 0, "max_examples": 300},
      "failures": {"<test name>": "<failure detail, including the failing case>"},
      "resources": {"wall_seconds": 2.3, "cpu_seconds": 2.29, "peak_rss_kb": 49152},
      "sandbox": {"network": "none", "filesystem": "...", "user": "...", "environment": {"sandbox": "container", "...": "..."}},
      "implementation": {"implementation": {"contract": "sha256:...", "entrypoint": "impl.py", "...": "..."}},
      "runner": {"keyid": "ed25519:<sha256 of the raw public key>", "publicKey": "<base64 raw Ed25519 key>"},
      "startedOn": "2026-10-21T12:30:00Z",
      "finishedOn": "2026-10-21T12:30:03Z"
    }
  }
}
```

- Test names are `example:<line and note>` and `property:<function name>`.
- The `symbolon` object extends the Test Result predicate. Tools that only know the standard predicate can ignore it.
- The **environment digest** covers the inputs that decide behavior: sandbox kind, base image, Python version, OS, architecture, and package versions. It excludes machine-specific ids such as the local image id, so two runners that build the same environment get the same digest.

## Verifying

```bash
symbolon verify att.json                                  # signature and contents
symbolon verify att.json --trust runner.pub               # signer is in your trust set
symbolon verify att.json --contract C --impl I            # digests match your local copies
symbolon verify att.json --contract C --impl I --rerun    # run it again here and compare
```

`--rerun` runs the attestation again in your own sandbox and compares the result of every check. "Reproduced" means every example and property has the same outcome. That is the property a third party relies on: they don't have to trust the original runner, they can check.

The runner's public key is embedded in the attestation so the signature can always be checked. **Trust is a separate question**: a valid signature from a key you don't trust proves only that someone ran the tests. Pass the keys you accept with `--trust`.
