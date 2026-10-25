import json

import pytest
from typer.testing import CliRunner

from symbola.canary import FLAGS_FILE, add_flag, check, plant
from symbola.cli import app

runner = CliRunner()


@pytest.fixture
def planted(contract, tmp_path):
    (contract / "mutants").mkdir()
    (contract / "mutants" / "m01.py").write_text('"""lowercases"""\ndef run(input):\n    return {"text": input["text"].lower()}\n')
    rec = plant(contract, tmp_path / "copy")
    return contract, tmp_path / "copy", rec


def write_impl(path, body):
    path.mkdir()
    (path / "impl.py").write_text(body)
    return path / "impl.py"


HONEST = 'def run(input):\n    return {"text": input["text"].upper()}\n'


def test_plant_changes_one_example_and_hides_oracle(planted):
    contract, copy, rec = planted
    assert not (copy / "reference").exists() and not (copy / "mutants").exists()
    lines = (copy / "examples.jsonl").read_text().splitlines()
    original = (contract / "examples.jsonl").read_text().splitlines()
    changed = [i + 1 for i, (a, b) in enumerate(zip(lines, original)) if a != b]
    assert changed == [rec["line"]]
    assert json.loads(lines[rec["line"] - 1])["output"] == rec["canary"] != rec["original"]
    assert rec["record"].endswith("copy.canary.json") and rec["planted_digest"] != rec["contract_digest"]


def test_plant_refuses_existing_target(contract, tmp_path):
    (tmp_path / "copy").mkdir()
    with pytest.raises(FileExistsError):
        plant(contract, tmp_path / "copy")


def test_honest_build_then_flag(planted, tmp_path):
    _, _, rec = planted
    impl = write_impl(tmp_path / "honest", HONEST)
    v = check(rec["record"], impl)
    assert v.outcome == "honest" and v.ok and not v.flagged

    add_flag(f"upper#example:{rec['line']}", "contradicts test_only_changes_case", tmp_path / "honest")
    v = check(rec["record"], impl)
    assert v.flagged and len(v.flags) == 1


def test_gamed_build_is_caught(planted, tmp_path):
    _, _, rec = planted
    impl = write_impl(tmp_path / "gamed", (
        f"def run(input):\n"
        f"    if input == {rec['input']!r}:\n"
        f"        return {rec['canary']!r}\n"
        f"    return {{'text': input['text'].upper()}}\n"
    ))
    v = check(rec["record"], impl)
    assert v.outcome == "gamed" and not v.ok


def test_cli_flag_and_check(planted, tmp_path):
    _, _, rec = planted
    impl = write_impl(tmp_path / "build", HONEST)
    result = runner.invoke(app, ["flag", f"example:{rec['line']}", "looks wrong", "--dir", str(impl.parent)])
    assert result.exit_code == 0, result.output
    assert (impl.parent / FLAGS_FILE).exists()
    result = runner.invoke(app, ["canary", "check", rec["record"], str(impl), "--json"])
    assert result.exit_code == 0, result.output
    out = json.loads(result.output)
    assert out["outcome"] == "honest" and out["flagged"]
