import json
import shutil

import pytest
from typer.testing import CliRunner

from symbolon.cli import app
from symbolon.pack import validate_pack

from .conftest import REPO

LIGHTKONE = REPO / "packs" / "kausalflow" / "lightkone" / "1"
runner = CliRunner()


@pytest.fixture
def pack(tmp_path):
    dst = tmp_path / "pack"
    shutil.copytree(LIGHTKONE, dst, ignore=shutil.ignore_patterns("__pycache__"))
    return dst


def failed(report):
    return {c.name: c.detail for c in report.checks if not c.ok}


def obligation(**fields):
    lines = ["\n[[obligation]]"]
    for k, v in fields.items():
        lines.append(f"{k} = {json.dumps(v)}")
    return "\n".join(lines) + "\n"


def add(pack, **fields):
    path = pack / "obligations.toml"
    path.write_text(path.read_text() + obligation(**fields))


def test_lightkone_pack_is_valid():
    report = validate_pack(LIGHTKONE)
    assert report.ok, failed(report)
    s = report.summary
    assert s["components"] == 3 and s["assumptions"] >= 1
    assert s["by_status"]["open"] >= 1
    assert s["checks_tracing_to_an_obligation"] == s["checks"]


def test_open_obligation_must_not_have_checks(pack):
    add(pack, id="search.extra", statement="x", status="open", checks=["search-query#example:1"])
    assert "open, so it must not have checks" in failed(validate_pack(pack))["every obligation is checked, open, or explained"]


def test_decided_obligation_needs_a_check(pack):
    add(pack, id="search.extra", statement="x", status="decided")
    assert "needs at least one check" in failed(validate_pack(pack))["every obligation is checked, open, or explained"]


def test_constraint_needs_a_reason(pack):
    add(pack, id="search.extra", statement="x", status="decided", kind="constraint",
        checks=["search-query#example:1"])
    assert "needs a reason" in failed(validate_pack(pack))["every obligation is checked, open, or explained"]


@pytest.mark.parametrize("ref", ["search-query#example:999", "search-query#test_nope", "nope#example:1"])
def test_checks_must_exist(pack, ref):
    add(pack, id="search.extra", statement="x", status="decided", checks=[ref])
    assert "does not exist" in failed(validate_pack(pack))["every obligation is checked, open, or explained"]


def test_malformed_check_reference(pack):
    add(pack, id="search.extra", statement="x", status="decided", checks=["search-query/examples/1"])
    assert "is not" in failed(validate_pack(pack))["every obligation is checked, open, or explained"]


def test_unknown_assumption(pack):
    add(pack, id="search.extra", statement="x", status="open", assumes=["K-nope"])
    assert "unknown K-nope" in failed(validate_pack(pack))["every obligation is checked, open, or explained"]


def test_duplicate_ids(pack):
    add(pack, id="search.trash", statement="again", status="open")
    assert "search.trash" in failed(validate_pack(pack))["obligation ids are unique"]


def test_bad_status_and_id(pack):
    add(pack, id="NoDots", statement="x", status="maybe")
    detail = failed(validate_pack(pack))["obligations.toml is valid"]
    assert "id" in detail and "status" in detail


def test_brief_needs_non_goals_priorities_and_resolver(pack):
    (pack / "BRIEF.md").write_text("# Lightkone\n\nA paper library.\n")
    detail = failed(validate_pack(pack))["BRIEF.md states non-goals, priorities and who resolves gaps"]
    assert "Non-goals" in detail and "Priorities" in detail and "Who resolves gaps" in detail


def test_assumption_fields(pack):
    (pack / "assumptions" / "bad.toml").write_text('id = "no-prefix"\nstatement = "x"\n')
    detail = failed(validate_pack(pack))["assumptions are valid"]
    assert "bad.toml" in detail and "basis" in detail


def test_changed_component_breaks_the_digest(pack):
    examples = pack / "components" / "search-query" / "1" / "examples.jsonl"
    examples.write_text(examples.read_text() + "\n")
    assert "lightkone/search-query@1" in failed(validate_pack(pack))["component digests match the pack manifest"]


def test_missing_obligations_file(pack):
    (pack / "obligations.toml").unlink()
    assert "obligations.toml" in failed(validate_pack(pack))["required files present"]


def test_cli(pack):
    result = runner.invoke(app, ["pack", "validate", str(LIGHTKONE)])
    assert result.exit_code == 0, result.output
    assert "obligations" in result.output and "decided" in result.output

    result = runner.invoke(app, ["pack", "validate", str(LIGHTKONE), "--json"])
    assert json.loads(result.output)["ok"]

    add(pack, id="search.extra", statement="x", status="decided")
    result = runner.invoke(app, ["pack", "validate", str(pack)])
    assert result.exit_code == 1 and "pack is not valid" in result.output
