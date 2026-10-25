import json
import shutil

import pytest
from typer.testing import CliRunner

from symbola.cli import app
from symbola.pack import component_name, summary_line, validate_pack

from .conftest import REPO

LIGHTKONE = REPO / "tests" / "fixtures" / "lightkone" / "versions" / "1"
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
    assert s["components"] == 8 and s["assumptions"] >= 1
    assert s["by_status"] == {"decided": s["obligations"], "default": 0, "open": 0}
    assert s["checks_tracing_to_an_obligation"] == s["checks"]


def test_open_obligation_must_not_have_checks(pack):
    add(pack, id="search.extra", statement="x", status="open", checks=["search-query#example:1"])
    assert "open, so it must not have checks" in failed(validate_pack(pack))["every obligation is checked, open, or explained"]


def test_decided_obligation_needs_a_check(pack):
    add(pack, id="search.extra", statement="x", status="decided")
    assert "needs at least one check" in failed(validate_pack(pack))["every obligation is checked, open, or explained"]


def test_unchecked_obligation_names_the_check_it_needs(pack):
    add(pack, id="search.extra", statement="x", status="decided",
        unchecked="a static check over the source tree")
    report = validate_pack(pack)
    assert report.ok, failed(report)
    assert report.summary["unchecked"] == 1
    assert "1 unchecked" in summary_line(report.summary)
    detail = next(c.detail for c in report.checks if c.name == "unchecked obligations are within the cap")
    assert "search.extra" in detail and "1 of" in detail


@pytest.mark.parametrize("fields, message", [
    ({"status": "open"}, "cannot be unchecked"),
    ({"status": "decided", "checks": ["search-query#example:1"]}, "not unchecked"),
])
def test_unchecked_is_only_for_required_obligations_without_checks(pack, fields, message):
    add(pack, id="search.extra", statement="x", unchecked="later", **fields)
    assert message in failed(validate_pack(pack))["every obligation is checked, open, or explained"]


def test_unchecked_debt_is_capped(pack):
    for i in range(10):
        add(pack, id=f"search.later-{i}", statement="x", status="decided", unchecked="a session check")
    detail = failed(validate_pack(pack))["unchecked obligations are within the cap"]
    assert "the cap is 10%" in detail
    manifest = pack / "symbolon-pack.toml"
    manifest.write_text(manifest.read_text().replace("[pack]\n", "[pack]\nmax_unchecked = 0.5\n", 1))
    assert validate_pack(pack).ok


def test_unchecked_cap_must_be_a_share(pack):
    manifest = pack / "symbolon-pack.toml"
    manifest.write_text(manifest.read_text().replace("[pack]\n", "[pack]\nmax_unchecked = 3\n", 1))
    add(pack, id="search.extra", statement="x", status="decided", unchecked="later")
    assert "between 0 and 1" in failed(validate_pack(pack))["unchecked obligations are within the cap"]


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
    examples = pack / "components" / "search-query" / "versions" / "1" / "examples.jsonl"
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


def make_statistical(pack, prop="test_terms_are_conjunctive"):
    """Declare one search-query property statistical and refresh the pack's digest for it."""
    from symbola.digest import contract_digest
    contract = pack / "components" / "search-query" / "versions" / "1"
    manifest = contract / "symbolon.toml"
    manifest.write_text(manifest.read_text() + f"\n[spec.statistical.{prop}]\nat_least = 0.9\n")
    pack_manifest = pack / "symbolon-pack.toml"
    lines = [f'"lightkone/search-query@1" = "{contract_digest(contract)}"' if l.startswith('"lightkone/search-query@1"') else l
             for l in pack_manifest.read_text().splitlines()]
    pack_manifest.write_text("\n".join(lines) + "\n")


def test_statistical_obligation_needs_a_statistical_check(pack):
    add(pack, id="search.extra", statement="x", status="decided", exactness="statistical",
        checks=["search-query#example:1"])
    assert "must be a property listed under [spec.statistical]" in failed(validate_pack(pack))["every obligation is checked, open, or explained"]


def test_statistical_obligation(pack):
    make_statistical(pack)
    add(pack, id="search.extra", statement="x", status="default", exactness="statistical",
        checks=["search-query#example:1", "search-query#test_terms_are_conjunctive"])
    report = validate_pack(pack)
    assert report.ok, failed(report)
    assert report.summary["by_exactness"]["statistical"] == 1
    assert report.summary["statistical_checks"] == 1


def test_open_obligation_is_free_not_statistical(pack):
    add(pack, id="search.extra", statement="x", status="open", exactness="statistical")
    assert "cannot also be statistical" in failed(validate_pack(pack))["every obligation is checked, open, or explained"]


def test_obligations_no_longer_take_sample_sizes(pack):
    add(pack, id="search.extra", statement="x", status="decided", checks=["search-query#example:1"], samples=10)
    assert "samples" in failed(validate_pack(pack))["obligations.toml is valid"]


def test_component_name_skips_the_versions_folder(tmp_path):
    assert component_name(tmp_path / "components" / "tidy" / "versions" / "1") == "tidy"
    assert component_name(tmp_path / "components" / "tidy" / "1") == "tidy"
