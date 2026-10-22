import base64
import json
import shutil
from pathlib import Path

import pytest

from symbolon import keys
from symbolon.attest import AttestError, compare_runs, run_attestation, statement_of, verify_attestation
from symbolon.digest import contract_digest, implementation_digest
from symbolon.implementation import check_lockfile, load_impl_manifest
from symbolon.sandbox import ContainerSandbox, ProcessSandbox, SandboxUnavailable

from .conftest import REPO

DATE_PARSE = REPO / "contracts" / "core" / "date-parse" / "1"
STRICT = REPO / "examples" / "impls" / "date-parse-strict"
STRPTIME = REPO / "examples" / "impls" / "date-parse-strptime"


def _available(cls):
    try:
        return cls()
    except SandboxUnavailable:
        return None


SANDBOXES = {"process": _available(ProcessSandbox), "container": _available(ContainerSandbox)}


@pytest.fixture(params=["process", "container"])
def sandbox(request):
    box = SANDBOXES[request.param]
    if box is None:
        pytest.skip(f"{request.param} sandbox not available here")
    return box


@pytest.fixture
def key(tmp_path):
    return keys.load_private(keys.generate(tmp_path / "runner.key"))


def write_impl(path: Path, contract: Path, code: str, lock: str | None = None) -> Path:
    path.mkdir(parents=True)
    (path / "impl.py").write_text(code)
    (path / "symbolon-impl.toml").write_text(
        f'[implementation]\ncontract = "{contract_digest(contract)}"\nlicense = "MIT"\nauthors = ["test"]\n'
    )
    if lock is not None:
        (path / "requirements.lock").write_text(lock)
    return path


# Keys and envelopes


def test_envelope_round_trip(key):
    env = keys.sign_envelope(b'{"a":1}', key)
    assert keys.verify_envelope(env, key.public_key()) == b'{"a":1}'


def test_envelope_rejects_tampering(key):
    env = keys.sign_envelope(b'{"a":1}', key)
    env["payload"] = base64.b64encode(b'{"a":2}').decode()
    with pytest.raises(ValueError, match="does not match"):
        keys.verify_envelope(env, key.public_key())


def test_envelope_rejects_other_key(key, tmp_path):
    other = keys.load_private(keys.generate(tmp_path / "other.key"))
    with pytest.raises(ValueError, match="no signature"):
        keys.verify_envelope(keys.sign_envelope(b"{}", key), other.public_key())


def test_keygen_refuses_to_overwrite(tmp_path):
    keys.generate(tmp_path / "k.key")
    with pytest.raises(FileExistsError):
        keys.generate(tmp_path / "k.key")
    assert (tmp_path / "k.key").stat().st_mode & 0o077 == 0


# Implementation manifests


def test_example_impls_target_current_contract():
    for impl in (STRICT, STRPTIME):
        assert load_impl_manifest(impl).implementation.contract == contract_digest(DATE_PARSE)


def test_impl_digest_differs_from_contract_framing(tmp_path):
    shutil.copytree(STRICT, tmp_path / "a")
    assert implementation_digest(tmp_path / "a") == implementation_digest(STRICT)
    assert implementation_digest(STRICT) != contract_digest(STRICT)


def test_lockfile_must_be_pinned(tmp_path):
    impl = write_impl(tmp_path / "i", DATE_PARSE, "def run(i): ...\n", lock="six>=1.0\n")
    with pytest.raises(ValueError, match="pinned"):
        check_lockfile(impl)
    (impl / "requirements.lock").write_text("six==1.17.0 \\\n    --hash=sha256:abc\n")
    assert check_lockfile(impl) is not None


@pytest.mark.parametrize("entry", ["../escape.py", "/abs.py", "impl.txt"])
def test_entrypoint_must_stay_inside(tmp_path, entry):
    impl = write_impl(tmp_path / "i", DATE_PARSE, "")
    text = (impl / "symbolon-impl.toml").read_text().replace("[implementation]\n", f'[implementation]\nentrypoint = "{entry}"\n')
    (impl / "symbolon-impl.toml").write_text(text)
    with pytest.raises(Exception):
        load_impl_manifest(impl)


# Attestation runs


def test_passing_attestation(sandbox, key):
    env = run_attestation(DATE_PARSE, STRICT, sandbox, key)
    v = verify_attestation(env, contract_dir=DATE_PARSE, impl_dir=STRICT)
    assert v.ok and not v.problems
    p = v.predicate
    assert p["result"] == "PASSED" and p["failedTests"] == []
    assert len(p["passedTests"]) == 21
    assert p["symbolon"]["sandbox"]["environment"]["sandbox"] == sandbox.kind
    assert p["symbolon"]["evidence"] == "reproducible"
    assert v.statement["subject"][0]["digest"]["sha256"] == implementation_digest(STRICT).split(":")[1]


def test_failing_attestation_names_failures(sandbox, key):
    p = statement_of(run_attestation(DATE_PARSE, STRPTIME, sandbox, key))["predicate"]
    assert p["result"] == "FAILED"
    assert "property:test_iso_requires_two_digit_month_and_day" in p["failedTests"]
    assert "Failing test case" in p["symbolon"]["failures"]["property:test_iso_requires_two_digit_month_and_day"]


def test_reruns_reproduce(sandbox, key):
    a = statement_of(run_attestation(DATE_PARSE, STRPTIME, sandbox, key))
    b = statement_of(run_attestation(DATE_PARSE, STRPTIME, sandbox, key))
    assert compare_runs(a, b) == []
    env = lambda s: [c for c in s["predicate"]["configuration"] if c["name"] == "environment"][0]
    assert env(a) == env(b)


def test_process_and_container_agree(key):
    if None in SANDBOXES.values():
        pytest.skip("needs both sandboxes")
    a = statement_of(run_attestation(DATE_PARSE, STRPTIME, SANDBOXES["process"], key))
    b = statement_of(run_attestation(DATE_PARSE, STRPTIME, SANDBOXES["container"], key))
    assert compare_runs(a, b) == []


def test_network_is_blocked(sandbox, key, contract, tmp_path):
    code = (
        "import socket\n"
        "def run(input):\n"
        "    try:\n"
        "        socket.create_connection(('1.1.1.1', 443), timeout=3).close()\n"
        "        return {'text': 'NETWORK REACHED'}\n"
        "    except OSError:\n"
        "        return {'text': input['text'].upper()}\n"
    )
    impl = write_impl(tmp_path / "net", contract, code)
    p = statement_of(run_attestation(contract, impl, sandbox, key))["predicate"]
    assert p["result"] == "PASSED", p["symbolon"]["failures"]


def test_memory_is_limited(sandbox, key, contract, tmp_path):
    code = "def run(input):\n    blob = bytearray(4 * 1024**3)\n    return {'text': input['text'].upper()}\n"
    impl = write_impl(tmp_path / "mem", contract, code)
    try:
        p = statement_of(run_attestation(contract, impl, sandbox, key))["predicate"]
    except Exception as e:  # the container is killed outright when it exceeds its memory
        assert "memory" in str(e).lower() or "killed" in str(e).lower()
    else:
        assert p["result"] == "FAILED"
        assert any("MemoryError" in d for d in p["symbolon"]["failures"].values())


def test_inputs_are_read_only_in_container(key, contract, tmp_path):
    box = SANDBOXES["container"]
    if box is None:
        pytest.skip("container sandbox not available here")
    code = (
        "from pathlib import Path\n"
        "def run(input):\n"
        "    try:\n"
        "        Path('/work/contract/examples.jsonl').write_text('')\n"
        "        return {'text': 'WROTE'}\n"
        "    except OSError:\n"
        "        return {'text': input['text'].upper()}\n"
    )
    impl = write_impl(tmp_path / "ro", contract, code)
    assert statement_of(run_attestation(contract, impl, box, key))["predicate"]["result"] == "PASSED"


def test_contract_digest_must_match(sandbox, key, contract, tmp_path):
    impl = write_impl(tmp_path / "x", DATE_PARSE, "def run(i): ...\n")
    with pytest.raises(AttestError, match="targets"):
        run_attestation(contract, impl, sandbox, key)


def test_verify_detects_local_drift(sandbox, key, tmp_path):
    env = run_attestation(DATE_PARSE, STRICT, sandbox, key)
    changed = tmp_path / "changed"
    shutil.copytree(STRICT, changed)
    (changed / "impl.py").write_text((changed / "impl.py").read_text() + "\n# edited\n")
    v = verify_attestation(env, impl_dir=changed)
    assert any("implementation digest differs" in p for p in v.problems)


def test_verify_trust_set(sandbox, key, tmp_path):
    env = run_attestation(DATE_PARSE, STRICT, sandbox, key)
    mine = tmp_path / "runner.pub"
    other = keys.public_path(keys.generate(tmp_path / "other.key"))
    assert verify_attestation(env, trusted_keys=[mine]).trusted is True
    v = verify_attestation(env, trusted_keys=[other])
    assert v.trusted is False and not v.ok


def test_lockfile_dependencies_are_installed(sandbox, key, contract, tmp_path):
    code = "import six\ndef run(input):\n    return {'text': six.ensure_str(input['text']).upper()}\n"
    impl = write_impl(tmp_path / "deps", contract, code, lock="six==1.17.0\n")
    try:
        env = run_attestation(contract, impl, sandbox, key)
    except Exception as e:
        if "install" in str(e):
            pytest.skip(f"package index not reachable: {e}")
        raise
    assert statement_of(env)["predicate"]["result"] == "PASSED"


def test_command_implementation_attests(sandbox, key, tmp_path):
    from .test_command_impl import JS_LOOP, command_impl
    if sandbox.kind == "process" and shutil.which("node") is None:
        pytest.skip("node not installed on this machine")
    impl = command_impl(tmp_path, "js", JS_LOOP, ["node", "impl.mjs"])
    p = statement_of(run_attestation(DATE_PARSE, impl, sandbox, key))["predicate"]
    assert p["result"] == "PASSED", p["symbolon"]["failures"]
    assert p["symbolon"]["implementation"]["implementation"]["language"] == "command"
