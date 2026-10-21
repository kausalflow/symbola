import json

from typer.testing import CliRunner

from symbolon.cli import app

runner = CliRunner()


def test_init_then_validate(tmp_path):
    root = tmp_path / "contracts"
    result = runner.invoke(app, ["init", "acme/shout", "--root", str(root)])
    assert result.exit_code == 0, result.output
    target = root / "acme" / "shout" / "1"
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
