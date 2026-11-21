import json
import shutil

import pytest
from typer.testing import CliRunner

from symbola.cli import app
import tomllib

from symbola.pack import component_name, draft_flows, product_flows, summary_line, validate_pack

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
    assert "lightkone/search-query@1" in failed(validate_pack(pack))["component digests match the Blueprint manifest"]


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
    assert result.exit_code == 1 and "Blueprint is not valid" in result.output


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


def test_product_pack_needs_shape_surfaces_and_flows(pack):
    assert validate_pack(pack).summary["product"] is False
    (pack / "PRODUCT.md").write_text("# Product\n\n## Shape\n\nA web app.\n\n## Flows\n\n1. Search.\n")
    report = validate_pack(pack)
    assert failed(report)["PRODUCT.md states the shape, surfaces and flows"] == "missing sections: Surfaces"
    (pack / "PRODUCT.md").write_text(PRODUCT)
    (pack / "flows.toml").write_text(FLOWS)
    report = validate_pack(pack)
    assert report.ok, failed(report)
    assert report.summary["product"] is True and report.summary["flows"] == 2
    assert summary_line(report.summary).startswith("product pack · ")


PRODUCT = """# Product

## Shape

A web app.

## Surfaces

- The search box.

## Flows

1. **Find a paper.** Type in the search box; `search-query` ranks the results.
2. **Tidy up**: run `tidy` from the side bar. Uses `bibtex-export`, `bibtex-import`, `citation-key`,
   `library-file`, `library-merge` and `pdf-filing` too.

## Order

1. Not a flow.
"""

FLOWS = """
[[flow]]
id = "find-a-paper"
title = "Find a paper"
uses = ["search-query"]
keeps = ["search.trash"]

[[flow]]
id = "tidy-up"
title = "Tidy up"
uses = ["tidy", "bibtex-export", "bibtex-import", "citation-key", "library-file", "library-merge", "pdf-filing"]
"""

FLOWS_NAME = "flows.toml ties every flow to its components"


@pytest.fixture
def product(pack):
    (pack / "PRODUCT.md").write_text(PRODUCT)
    (pack / "flows.toml").write_text(FLOWS)
    assert validate_pack(pack).ok, failed(validate_pack(pack))
    return pack


def test_flow_titles_come_from_the_numbered_bold_items_under_flows():
    assert product_flows(PRODUCT) == (["Find a paper", "Tidy up"], [])
    titles, problems = product_flows("## Flows\n\n1. Search, then read.\n2. **A.** x\n3. **A.** y\n")
    assert titles == ["A", "A"]
    assert problems == ["flow 1 must open with its title in bold, like '1. **Find a paper.** ...'",
                        "two flows are titled 'A'"]


def test_a_product_blueprint_needs_flows_toml_and_a_library_must_not_have_it(pack, product):
    (pack / "flows.toml").unlink()
    assert failed(validate_pack(pack))[FLOWS_NAME].startswith("missing flows.toml")
    (pack / "flows.toml").write_text(FLOWS)
    (pack / "PRODUCT.md").unlink()
    assert "a component library has neither" in failed(validate_pack(pack))[FLOWS_NAME]


def test_flows_toml_must_match_product_md(product):
    (product / "flows.toml").write_text(FLOWS.replace('title = "Tidy up"', 'title = "Tidy"'))
    assert failed(validate_pack(product))[FLOWS_NAME] == (
        "flows of PRODUCT.md not in flows.toml: 'Tidy up'\nflows of flows.toml not in PRODUCT.md: 'Tidy'")
    first, second = FLOWS.strip().split("\n\n")
    (product / "flows.toml").write_text(second + "\n\n" + first + "\n")
    assert failed(validate_pack(product))[FLOWS_NAME] == "flows are in a different order than in PRODUCT.md"


def test_flows_name_real_components_and_decisions_and_leave_no_component_idle(product):
    (product / "flows.toml").write_text(FLOWS.replace('uses = ["tidy", ', 'uses = ["tidier", ')
                                        .replace("search.trash", "search.nope"))
    detail = failed(validate_pack(product))[FLOWS_NAME]
    assert "find-a-paper: keeps unknown decision 'search.nope'" in detail
    assert "tidy-up: uses unknown component 'tidier'" in detail
    assert "no flow uses tidy:" in detail
    (product / "flows.toml").write_text(FLOWS.replace('id = "tidy-up"', 'id = "find-a-paper"'))
    assert "two flows have the id 'find-a-paper'" in failed(validate_pack(product))[FLOWS_NAME]
    (product / "flows.toml").write_text(FLOWS.replace('id = "tidy-up"', 'id = "Tidy Up"'))
    assert "lowercase letters, digits and hyphens" in failed(validate_pack(product))[FLOWS_NAME]


def test_about_ties_a_decision_without_checks_to_its_component(pack):
    add(pack, id="search.unicode", statement="x", status="decided", unchecked="a fuzz check", about=["search-query"])
    add(pack, id="search.free", statement="y", status="open", about=["search-query", "tidy"])
    report = validate_pack(pack)
    assert report.ok, failed(report)
    add(pack, id="search.bad", statement="z", status="open", about=["nope"])
    add(pack, id="search.twice", statement="z", status="decided", checks=["tidy#example:1"], about=["tidy"])
    detail = failed(validate_pack(pack))["every obligation is checked, open, or explained"]
    assert "search.bad: is about unknown component 'nope'" in detail
    assert "search.twice: its checks already tie it to 'tidy'; drop it from `about`" in detail


def test_summary_counts_standing(pack):
    before = validate_pack(pack).summary["standing"]
    add(pack, id="search.unicode", statement="x", status="decided", unchecked="a fuzz check")
    add(pack, id="search.free", statement="y", status="open")
    after = validate_pack(pack).summary["standing"]
    assert after == {"checked": before["checked"], "unchecked": before["unchecked"] + 1, "open": before["open"] + 1}


def test_draft_flows_keeps_what_is_there_and_drafts_the_rest(product):
    assert tomllib.loads(draft_flows(product)) == tomllib.loads(FLOWS)
    (product / "PRODUCT.md").write_text(PRODUCT.replace(
        "2. **Tidy up**", "2. **Find a paper again.** With `tidy` and `nothing`.\n3. **Tidy up**"))
    flows = tomllib.loads(draft_flows(product))["flow"]
    assert [f["id"] for f in flows] == ["find-a-paper", "find-a-paper-again", "tidy-up"]
    assert flows[1] == {"id": "find-a-paper-again", "title": "Find a paper again", "uses": ["tidy"]}
    assert flows[0]["keeps"] == ["search.trash"]
