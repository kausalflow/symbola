"""Signed attestations: an in-toto Test Result statement in a DSSE envelope.

The statement's subject is the implementation digest. The contract digest
and the environment digest are configuration entries. Symbolon-specific
details (seed, budget, failures, resources, sandbox, runner key) live under
`predicate.symbolon`, which in-toto consumers that only know the Test Result
predicate can ignore. See docs/ATTESTATION.md.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import symbolon

from . import keys
from .digest import contract_digest, hex_of, implementation_digest
from .implementation import check_lockfile, load_impl_manifest
from .manifest import load_manifest
from .sandbox import Limits, Sandbox, Workspace, environment_digest

STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://in-toto.io/attestation/test-result/v0.1"


class AttestError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _test_names(result: dict) -> tuple[list[str], list[str], dict[str, str]]:
    passed, failed, details = [], [], {}
    for kind, items in (("example", result["examples"]), ("property", result["properties"])):
        for c in items:
            name = f"{kind}:{c['name'].removeprefix('example ')}"
            (passed if c["ok"] else failed).append(name)
            if not c["ok"]:
                details[name] = c["detail"]
    return passed, failed, details


def run_attestation(contract_dir: Path, impl_dir: Path, sandbox: Sandbox, key) -> dict:
    """Run the contract's spec against an implementation in `sandbox`; return a signed envelope."""
    contract_dir, impl_dir = Path(contract_dir).resolve(), Path(impl_dir).resolve()
    manifest = load_manifest(contract_dir)
    try:
        impl_manifest = load_impl_manifest(impl_dir)
        check_lockfile(impl_dir)
    except Exception as e:
        raise AttestError(f"implementation manifest: {e}") from None

    ws = Workspace.create(contract_dir, impl_dir)
    try:
        c_digest = contract_digest(ws.contract)
        i_digest = implementation_digest(ws.impl)
        if impl_manifest.implementation.contract != c_digest:
            raise AttestError(
                f"implementation targets {impl_manifest.implementation.contract}, "
                f"but this contract is {c_digest}"
            )
        entry = impl_manifest.implementation.entrypoint
        if not (ws.impl / entry).is_file():
            raise AttestError(f"entrypoint {entry} not found in the implementation")

        network = bool(manifest.requires.network)
        env = sandbox.environment()
        started = _now()
        result = sandbox.run(
            ws, entry, network=network, lockfile=(ws.impl / "requirements.lock").exists(),
            limits=Limits(timeout_seconds=manifest.spec.timeout_seconds),
        )
        finished = _now()
    finally:
        ws.cleanup()

    if "error" in result:
        raise AttestError(f"implementation could not be loaded: {result['error']}")

    passed, failed, details = _test_names(result)
    public = key.public_key()
    statement = {
        "_type": STATEMENT_TYPE,
        "subject": [{
            "name": f"implementation-of:{manifest.alias}",
            "digest": {"sha256": hex_of(i_digest)},
        }],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "result": "PASSED" if result["passed"] else "FAILED",
            "configuration": [
                {"name": f"contract:{manifest.alias}", "digest": {"sha256": hex_of(c_digest)}},
                {"name": "environment", "digest": {"sha256": hex_of(environment_digest(env))}},
            ],
            "passedTests": passed,
            "warnedTests": [],
            "failedTests": failed,
            "symbolon": {
                "version": symbolon.__version__,
                "evidence": "observed" if network else "reproducible",
                "spec": {"seed": manifest.spec.seed, "max_examples": manifest.spec.max_examples},
                "failures": details,
                "resources": result.get("resources", {}),
                "sandbox": {**sandbox.isolation(network), "environment": env},
                "implementation": impl_manifest.model_dump(exclude_none=True),
                "runner": {
                    "keyid": keys.keyid(public),
                    "publicKey": base64.b64encode(keys.raw_public(public)).decode(),
                },
                "startedOn": started,
                "finishedOn": finished,
            },
        },
    }
    payload = json.dumps(statement, sort_keys=True, separators=(",", ":")).encode()
    return keys.sign_envelope(payload, key)


@dataclass
class Verification:
    statement: dict
    keyid: str
    trusted: bool | None
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems and self.trusted is not False

    @property
    def predicate(self) -> dict:
        return self.statement["predicate"]


def verify_attestation(envelope: dict, *, trusted_keys: list[Path] = (),
                       contract_dir: Path | None = None, impl_dir: Path | None = None) -> Verification:
    """Check the signature, and optionally the trust set and digests against local copies."""
    try:
        claimed = json.loads(base64.b64decode(envelope["payload"]))
        runner = claimed["predicate"]["symbolon"]["runner"]
        public = keys.public_from_b64(runner["publicKey"])
        payload = keys.verify_envelope(envelope, public)
    except Exception as e:
        raise AttestError(f"not a valid Symbolon attestation: {e}") from None
    statement = json.loads(payload)
    kid = keys.keyid(public)
    problems = []
    if runner["keyid"] != kid:
        problems.append("runner keyid does not match the runner public key")
    if statement.get("_type") != STATEMENT_TYPE or statement.get("predicateType") != PREDICATE_TYPE:
        problems.append("unexpected statement or predicate type")

    trusted = None
    if trusted_keys:
        trusted = kid in {keys.keyid(keys.load_public(p)) for p in trusted_keys}

    config = {c["name"].split(":", 1)[0]: c for c in statement["predicate"]["configuration"]}
    if contract_dir is not None:
        actual = hex_of(contract_digest(contract_dir))
        if config["contract"]["digest"]["sha256"] != actual:
            problems.append(f"contract digest differs: attested {config['contract']['digest']['sha256'][:12]}…, local {actual[:12]}…")
    if impl_dir is not None:
        actual = hex_of(implementation_digest(impl_dir))
        if statement["subject"][0]["digest"]["sha256"] != actual:
            problems.append(f"implementation digest differs: attested {statement['subject'][0]['digest']['sha256'][:12]}…, local {actual[:12]}…")
    return Verification(statement, kid, trusted, problems)


def compare_runs(original: dict, rerun: dict) -> list[str]:
    """Differences in per-test outcomes between two statements' predicates."""
    a, b = original["predicate"], rerun["predicate"]
    diffs = []
    if a["result"] != b["result"]:
        diffs.append(f"result {a['result']} vs {b['result']}")
    for label, key in (("passed", "passedTests"), ("failed", "failedTests")):
        only_a = sorted(set(a[key]) - set(b[key]))
        only_b = sorted(set(b[key]) - set(a[key]))
        if only_a:
            diffs.append(f"{label} only originally: {', '.join(only_a)}")
        if only_b:
            diffs.append(f"{label} only on rerun: {', '.join(only_b)}")
    return diffs


def statement_of(envelope: dict) -> dict:
    return json.loads(base64.b64decode(envelope["payload"]))
