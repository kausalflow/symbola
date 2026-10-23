import json

import pytest
from typer.testing import CliRunner

from symbolon.cli import app
from symbolon.validate import mutants_report, validate

from .conftest import SEEDS

runner = CliRunner()

KILLED = '"""lowercases instead"""\n\ndef run(input):\n    return {"text": input["text"].lower()}\n'
ASCII_ONLY = (
    '"""only ASCII letters are uppercased"""\n{marker}\n'
    'def run(input):\n'
    '    return {{"text": "".join(c.upper() if c.isascii() else c for c in input["text"])}}\n'
)


def mutants_check(report):
    return next(c for c in report.checks if c.name.startswith("mutants"))


def add(contract, name, source):
    d = contract / "mutants"
    d.mkdir(exist_ok=True)
    (d / name).write_text(source)


def test_no_mutants_folder_means_no_check(contract):
    report = validate(contract)
    assert report.ok
    assert not any(c.name.startswith("mutants") for c in report.checks)


def test_killed_mutant_passes(contract):
    add(contract, "m01.py", KILLED)
    report = validate(contract)
    assert report.ok
    assert mutants_check(report).detail == "1/1 killed"


def test_survivor_fails_until_documented(contract):
    add(contract, "m01.py", KILLED)
    add(contract, "m02.py", ASCII_ONLY.format(marker=""))
    check = mutants_check(validate(contract))
    assert not check.ok and "m02.py survives" in check.detail

    add(contract, "m02.py", ASCII_ONLY.format(marker='SURVIVES = "non-ASCII text is out of scope"\n'))
    report = validate(contract)
    assert report.ok
    assert mutants_check(report).detail == "1/2 killed, 1 documented survivor"


def test_stale_survives_marker_fails(contract):
    add(contract, "m01.py", KILLED.replace('"""\n', '"""\nSURVIVES = "not really"\n', 1))
    check = mutants_check(validate(contract))
    assert not check.ok and "remove the marker" in check.detail


def test_mutant_identical_to_reference_is_rejected(contract):
    ref = (contract / "reference" / "impl.py").read_text()
    add(contract, "m01.py", '"""no change at all"""\n# a comment\n' + ref.split('"""', 2)[2])
    check = mutants_check(validate(contract))
    assert not check.ok and "same program as reference/impl.py" in check.detail


def test_mutant_needs_a_concern(contract):
    add(contract, "m01.py", 'def run(input):\n    return {"text": ""}\n')
    check = mutants_check(validate(contract))
    assert not check.ok and "docstring" in check.detail


def test_report_names_killing_checks(contract, tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "m01.py").write_text(KILLED)
    report = mutants_report(contract, outside)
    [m] = report["mutants"]
    assert m["killed"] and "example:1" in m["killed_by"] and "test_leaves_no_lowercase" in m["killed_by"]
    assert report["summary"]["killed"] == 1


def test_cli_mutants_exit_code(contract):
    add(contract, "m01.py", ASCII_ONLY.format(marker=""))
    result = runner.invoke(app, ["mutants", str(contract), "--json"])
    assert result.exit_code == 1
    assert json.loads(result.output)["summary"]["undocumented_survivors"] == ["m01.py"]


@pytest.mark.parametrize("manifest", SEEDS, ids=lambda p: f"{p.parents[2].name}@{p.parent.name}")
def test_seed_contracts_kill_their_mutants(manifest):
    check = mutants_check(validate(manifest.parent))
    assert check.ok, check.detail
