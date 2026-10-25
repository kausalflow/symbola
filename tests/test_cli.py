import json

from typer.testing import CliRunner

from symbola.cli import app

runner = CliRunner()


def test_init_then_validate(tmp_path):
    root = tmp_path / "contracts"
    result = runner.invoke(app, ["init", "acme/shout", "--root", str(root)])
    assert result.exit_code == 0, result.output
    target = root / "acme" / "shout" / "versions" / "1"
    assert (target / "schema" / "input.json").exists()

    result = runner.invoke(app, ["validate", str(target), "--json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["ok"] and report["alias"] == "acme/shout@1"


def test_init_refuses_existing(tmp_path):
    root = tmp_path / "contracts"
    runner.invoke(app, ["init", "acme/shout", "--root", str(root)])
    result = runner.invoke(app, ["init", "acme/shout", "--root", str(root)])
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_init_rejects_bad_id(tmp_path):
    result = runner.invoke(app, ["init", "NoNamespace", "--root", str(tmp_path)])
    assert result.exit_code != 0


def test_validate_exit_code_on_failure(contract):
    (contract / "examples.jsonl").write_text("not json\n")
    result = runner.invoke(app, ["validate", str(contract)])
    assert result.exit_code == 1
    assert "contract is not valid" in result.output


def test_digest_command_matches_validate(contract):
    digest = runner.invoke(app, ["digest", str(contract)]).output.strip()
    report = json.loads(runner.invoke(app, ["validate", str(contract), "--json"]).output)
    assert digest == report["digest"]


def test_attest_and_verify_round_trip(tmp_path, monkeypatch):
    import pytest
    from symbola.sandbox import SandboxUnavailable, select
    try:
        select("auto")
    except SandboxUnavailable:
        pytest.skip("no sandbox available")
    from .conftest import REPO
    contract = REPO / "contracts" / "core" / "date-parse" / "versions" / "1"
    impl = REPO / "examples" / "impls" / "date-parse-strict"
    key = tmp_path / "runner.key"
    assert runner.invoke(app, ["keygen", "--out", str(key)]).exit_code == 0
    out = tmp_path / "att.json"
    result = runner.invoke(app, ["attest", str(contract), str(impl), "--key", str(key), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert "PASSED" in result.output
    result = runner.invoke(app, [
        "verify", str(out), "--trust", str(key.with_suffix(".pub")),
        "--contract", str(contract), "--impl", str(impl), "--rerun", "--key", str(key),
    ])
    assert result.exit_code == 0, result.output
    assert "reproduced" in result.output


def test_impl_init_pins_digest(contract, tmp_path):
    impl = tmp_path / "impl"
    result = runner.invoke(app, ["impl-init", str(impl), "--contract", str(contract)])
    assert result.exit_code == 0, result.output
    digest = runner.invoke(app, ["digest", str(contract)]).output.strip()
    assert digest in (impl / "symbolon-impl.toml").read_text()
    assert (impl / "impl.py").exists()
