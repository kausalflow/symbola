import json
import shutil

import pytest
from typer.testing import CliRunner

from symbola.blueprint import (BlueprintError, blueprint_map, build_status, decision_states, kept_by, load_blueprint,
                               map_markdown, attested_checks, search, search_entries, standing, standing_line,
                               status_line, status_markdown)
from symbola.cli import app
from symbola.registry import build_site, fetch_search_index
from symbola.scaffold import scaffold

from .conftest import REPO
from .test_pack import FLOWS, PRODUCT, add

LIGHTKONE = REPO / "tests" / "fixtures" / "lightkone" / "versions" / "1"
runner = CliRunner()


@pytest.fixture
def pack(tmp_path):
    """Lightkone as a product Blueprint, with one unchecked, one open and one product-wide decision."""
    dst = tmp_path / "spec"
    shutil.copytree(LIGHTKONE, dst, ignore=shutil.ignore_patterns("__pycache__"))
    (dst / "PRODUCT.md").write_text(PRODUCT)
    (dst / "flows.toml").write_text(FLOWS.replace('keeps = ["search.trash"]', 'keeps = ["app.offline"]'))
    add(dst, id="app.offline", statement="Search works with no network.", status="decided",
        unchecked="a run of the whole app with the network off")
    add(dst, id="search.fuzzy", statement="Whether search forgives typos.", status="open", about=["search-query"])
    add(dst, id="app.no-telemetry", statement="Nothing is sent anywhere.", status="decided",
        unchecked="a network capture of a session")
    return dst


def test_load_blueprint_refuses_what_validate_refuses(pack):
    bp = load_blueprint(pack)
    assert bp.id == "kausalflow/lightkone" and bp.product and len(bp.components) == 8 and len(bp.flows) == 2
    (pack / "flows.toml").unlink()
    with pytest.raises(BlueprintError, match="missing flows.toml"):
        load_blueprint(pack)


def test_decisions_are_tied_to_components_flows_or_the_whole_product(pack):
    bp = load_blueprint(pack)
    assert bp.decision("search.trash").components == ["search-query"]
    assert bp.decision("search.fuzzy").components == ["search-query"]
    assert [d.id for d in bp.product_wide] == ["app.no-telemetry"]
    of_flow = [d.id for d in bp.of_flow(bp.flows[0])]
    assert of_flow[0] == "app.offline" and "search.trash" in of_flow and "search.fuzzy" in of_flow
    assert not any(i.startswith("tidy.") for i in of_flow)


def test_order_follows_the_flows(pack):
    bp = load_blueprint(pack)
    assert bp.order[:2] == ["search-query", "tidy"] and sorted(bp.order) == sorted(bp.components)
    (pack / "PRODUCT.md").unlink()
    (pack / "flows.toml").unlink()
    assert load_blueprint(pack).order == sorted(bp.components)


def test_standing_counts_decisions_and_the_assumptions_they_rest_on(pack):
    bp = load_blueprint(pack)
    s = standing(bp.decisions)
    assert s["decisions"] == len(bp.decisions) and s["unchecked"] == 2 and s["open"] == 1
    assert s["checked"] == s["decisions"] - 3
    assert s["assumes"] == sorted({k for d in bp.decisions for k in d.assumes}) and s["assumes"]
    assert standing_line({"decisions": 1, "checked": 1, "unchecked": 0, "open": 0, "assumes": ["K-a"]}) == (
        "1 decision: 1 checked, 0 unchecked, 0 open; rests on 1 assumption")
    assert standing_line(standing([])) == "0 decisions: 0 checked, 0 unchecked, 0 open"


def test_map_links_every_part(pack):
    bp = load_blueprint(pack)
    m = blueprint_map(bp)
    assert m["format"] == 1 and m["order"] == bp.order
    assert [c["name"] for c in m["components"]] == bp.order
    search_part = m["components"][0]
    assert search_part["flows"] == ["find-a-paper"] and "search.fuzzy" in search_part["decisions"]
    assert search_part["standing"]["open"] == 1
    assert m["flows"][0]["keeps"] == ["app.offline"] and m["flows"][0]["standing"]["unchecked"] == 1
    assert m["product_wide"]["decisions"] == ["app.no-telemetry"]
    by_id = {d["id"]: d for d in m["decisions"]}
    assert by_id["app.offline"] == {"id": "app.offline", "status": "decided", "standing": "unchecked",
                                    "components": [], "flows": ["find-a-paper"], "assumes": []}
    assert sum(len(c["decisions"]) for c in m["components"]) >= len(bp.decisions) - 2
    for a in m["assumptions"]:
        assert all(a["id"] in by_id[d]["assumes"] for d in a["decisions"])
    json.dumps(m)


def test_map_markdown_gives_order_flows_and_what_no_check_settles(pack):
    text = map_markdown(load_blueprint(pack))
    assert "## Build order" in text and "1. `search-query` (`components/search-query/versions/1`)" in text
    assert "1. **Find a paper** (`find-a-paper`): uses `search-query`; keeps `app.offline`" in text
    assert "Decisions tied to no single component or flow: `app.no-telemetry`." in text
    assert "- `search.fuzzy` (open): Whether search forgives typos." in text
    assert "- `app.offline` (unchecked): Search works with no network. (a run of the whole app with the network off)" in text
    assert "## Assumptions it rests on" in text


def _result(bp, name, fail=()):
    """A test result for a component in which every check passes but those in `fail`."""
    import ast
    d = bp.components[name]
    lines = [i for i, line in enumerate((d / "examples.jsonl").read_text().split("\n"), 1) if line.strip()]
    props = [n.name for n in ast.parse((d / "properties.py").read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    return {
        "passed": not fail,
        "examples": [{"name": f"example line {i} (a note)", "ok": f"example:{i}" not in fail, "detail": ""} for i in lines],
        "properties": [{"name": p, "ok": p not in fail, "detail": ""} for p in props],
    }


def test_decision_states_follow_the_checks(pack):
    bp = load_blueprint(pack)
    results = {name: _result(bp, name) for name in bp.components}
    states = {d["id"]: d for d in decision_states(bp, results, {"tidy.missing-lists", "search.trash"})}
    assert states["app.offline"]["state"] == "unchecked" and states["search.fuzzy"]["state"] == "open"
    assert states["search.trash"]["state"] == "overridden"
    assert all(d["state"] in ("kept", "unchecked", "open", "overridden") for d in states.values())

    victim = next(d for d in bp.decisions if d.checks and d.components == ["search-query"] and d.id != "search.trash")
    component, check = victim.checks[0].split("#")
    results[component] = _result(bp, component, fail={check})
    results["tidy"] = None
    states = {d["id"]: d for d in decision_states(bp, results)}
    assert states[victim.id]["state"] == "failing" and states[victim.id]["failing"] == [victim.checks[0]]
    tidy = [d for d in states.values() if d["components"] == ["tidy"]]
    assert tidy and all(d["state"] == "not built" and d["waits_for"] == ["tidy"] for d in tidy)


def test_build_status_counts_a_build_in_decisions(pack, tmp_path):
    bp = load_blueprint(pack)
    impl = tmp_path / "impl"
    for name in bp.components:
        if name != "tidy":
            (impl / name).mkdir(parents=True)
    (tmp_path / "overrides.toml").write_text('[[override]]\nid = "search.trash"\nreason = "we keep trash"\n\n'
                                             '[[override]]\nid = "search.gone"\nreason = "old"\n')
    victim = next(d for d in bp.decisions if d.checks and d.components == ["citation-key"])
    fail = {victim.checks[0].split("#")[1]}

    def run(contract, impl_dir):
        name = impl_dir.name
        return _result(bp, name, fail if name == "citation-key" else ())

    status = build_status(pack, impl, run=run)
    assert status["done"] is False
    by = status["by_state"]
    assert by["unchecked"] == 2 and by["open"] == 1 and by["overridden"] == 1 and by["failing"] >= 1
    assert by["not built"] == sum(d.components == ["tidy"] for d in bp.decisions if d.checks)
    assert sum(by.values()) == len(bp.decisions)
    assert status["unknown_overrides"] == ["search.gone"]
    tidy = next(c for c in status["components"] if c["name"] == "tidy")
    assert tidy == {"name": "tidy", "built": False, "checks": 0, "failed": [], "error": ""}
    assert "failing" in status_line(status) and "not built" in status_line(status)
    note = status_markdown(status)
    assert f"- `{victim.id}`: {victim.checks[0]}" in note and "waits for tidy" in note
    assert "## Unchecked: required, and only you confirm it" in note

    (impl / "tidy").mkdir()
    status = build_status(pack, impl, run=lambda c, i: _result(bp, i.name))
    assert status["done"] is True and status["by_state"]["failing"] == 0 and status["by_state"]["kept"] > 0
    assert status["failing_outside_decisions"] == []


def test_a_component_that_cannot_run_is_not_done(pack, tmp_path):
    bp = load_blueprint(pack)
    for name in bp.components:
        (tmp_path / "impl" / name).mkdir(parents=True)
    status = build_status(pack, tmp_path / "impl",
                          run=lambda c, i: {"error": "no impl.py"} if i.name == "tidy" else _result(bp, i.name))
    assert status["done"] is False
    assert next(c for c in status["components"] if c["name"] == "tidy")["error"] == "no impl.py"
    assert any(d["state"] == "not built" for d in status["decisions"])


def test_status_cli_runs_the_real_checks(tmp_path):
    from symbola.extract import sync_components
    from symbola.registry import scaffold_pack
    spec = scaffold_pack("acme/shout", tmp_path / "spec")
    contract = scaffold("acme/upper", spec / "components")
    (spec / "obligations.toml").write_text(
        '[[obligation]]\nid = "shout.upper"\nstatement = "Text comes back in upper case."\nstatus = "decided"\n'
        'checks = ["upper#example:1"]\n\n'
        '[[obligation]]\nid = "shout.colour"\nstatement = "The colour of the output."\nstatus = "open"\n')
    sync_components(spec)
    r = runner.invoke(app, ["status", str(spec), "--impl", str(tmp_path / "impl")])
    assert r.exit_code == 1 and "upper: not built" in r.output and "NOT DONE" in r.output
    assert runner.invoke(app, ["impl-init", str(tmp_path / "impl" / "upper"), "--contract", str(contract)]).exit_code == 0
    shutil.copy(contract / "reference" / "impl.py", tmp_path / "impl" / "upper" / "impl.py")
    r = runner.invoke(app, ["status", str(spec), "--impl", str(tmp_path / "impl"), "--write", str(tmp_path / "STATUS.md")])
    assert r.exit_code == 0, r.output
    assert "DONE  2 decisions: 1 kept, 1 open" in r.output and "shout.colour" in r.output
    assert "# Build status: acme/shout" in (tmp_path / "STATUS.md").read_text()
    (tmp_path / "impl" / "upper" / "impl.py").write_text("def run(input):\n    return {'text': input['text']}\n")
    r = runner.invoke(app, ["status", str(spec), "--impl", str(tmp_path / "impl"), "--json"])
    status = json.loads(r.output)
    assert r.exit_code == 1 and status["by_state"]["failing"] == 1
    assert status["decisions"][0]["failing"] == ["upper#example:1"]


def test_attested_checks_and_kept_by(pack):
    bp = load_blueprint(pack)
    assert attested_checks(["example:line 3 (empty list)", "example:line 12", "property:test_x", "other"]) == {
        "example:3", "example:12", "test_x"}
    everything = {name: {c for c in _names(bp, name)} for name in bp.components}
    checked = [d.id for d in bp.decisions if d.standing == "checked"]
    assert kept_by(bp, everything) == checked
    everything.pop("tidy")
    assert kept_by(bp, everything) == [i for i in checked if bp.decision(i).components != ["tidy"]]


def _names(bp, name):
    r = _result(bp, name)
    return attested_checks([f"example:{c['name'].removeprefix('example ')}" for c in r["examples"]]
                           + [f"property:{c['name']}" for c in r["properties"]])


def test_search_finds_and_ranks(pack):
    rows = search_entries(load_blueprint(pack))
    assert {r["kind"] for r in rows} == {"decision", "assumption"}
    hits = search(rows, "search without network")
    assert hits[0]["id"] == "app.offline" and hits[0]["blueprint"] == "kausalflow/lightkone"
    assert search(rows, "typos")[0]["id"] == "search.fuzzy"
    assert search(rows, "forgiving typo")[0]["id"] == "search.fuzzy"  # stems, and words that are not there
    assert all(r["kind"] == "assumption" for r in search(rows, "library", kind="assumption"))
    assert search(rows, "the of and") == [] and search(rows, "zzzz") == []
    assert len(search(rows, "search", limit=3)) == 3


def test_site_writes_the_map_and_the_search_index(tmp_path, pack):
    registry = tmp_path / "packs"
    shutil.copytree(pack, registry / "kausalflow" / "lightkone" / "versions" / "1")
    shutil.copytree(LIGHTKONE.parent.parent / "attestations", registry / "kausalflow" / "lightkone" / "attestations")
    site = tmp_path / "site"
    build_site(registry, site, "https://symbola.sh")
    folder = site / "packs" / "kausalflow" / "lightkone"
    m = json.loads((folder / "map.json").read_text())
    assert m["order"][0] == "search-query" and m["standing"]["unchecked"] == 2
    assert (folder / "map.md").read_text().startswith("# kausalflow/lightkone: map")
    llms = (folder / "llms.txt").read_text()
    assert "## Map" in llms and "https://symbola.sh/packs/kausalflow/lightkone/map.md" in llms
    assert "Components, in the order the flows first need them" in llms
    assert llms.index("- `search-query`:") < llms.index("- `tidy`:") < llms.index("- `bibtex-export`:")
    assert "symbola status spec --impl impl --write STATUS.md" in llms
    entry = json.loads((site / "index.json").read_text())["packs"][0]
    assert entry["standing"] == m["standing"] and entry["standing_line"].startswith(f"{m['standing']['decisions']} decisions")
    index = json.loads((site / "decisions.json").read_text())
    assert index["format"] == 1 and any(e["id"] == "app.offline" for e in index["entries"])
    assert "decisions.json" in (site / "llms.txt").read_text()

    decisions = json.loads((folder / "evidence.json").read_text())["summary"]["decisions"]
    assert decisions["unchecked"] == 2 and decisions["open"] == 1
    assert decisions["checked"] == m["standing"]["checked"]
    assert 0 < decisions["kept"] <= decisions["checked"] and decisions["build"]
    assert len(decisions["not_shown"]) == decisions["checked"] - decisions["kept"]

    for source in (str(site), str(registry)):
        assert any(r["id"] == "app.offline" for r in fetch_search_index(source))
    r = runner.invoke(app, ["blueprint", "search", "search with no network", "--registry", str(site)])
    assert r.exit_code == 0 and "kausalflow/lightkone  app.offline" in r.output and "Nothing is imported" in r.output
    r = runner.invoke(app, ["blueprint", "search", "zzzz", "--registry", str(registry)])
    assert "No Blueprint states anything like that yet." in r.output


def test_map_and_flows_cli(pack):
    r = runner.invoke(app, ["blueprint", "map", str(pack)])
    assert r.exit_code == 0 and "## Build order" in r.output
    assert json.loads(runner.invoke(app, ["blueprint", "map", str(pack), "--json"]).output)["id"] == "kausalflow/lightkone"
    before = (pack / "flows.toml").read_text()
    (pack / "PRODUCT.md").write_text((pack / "PRODUCT.md").read_text().replace(
        "## Order", "3. **Cite.** Copy with `citation-key`.\n\n## Order"))
    assert runner.invoke(app, ["blueprint", "map", str(pack)]).exit_code == 1
    r = runner.invoke(app, ["blueprint", "flows", str(pack), "--write"])
    assert r.exit_code == 0 and "3 flows" in r.output
    after = (pack / "flows.toml").read_text()
    assert 'id = "cite"' in after and 'uses = ["citation-key"]' in after and 'keeps = ["app.offline"]' in after
    assert before != after and runner.invoke(app, ["blueprint", "map", str(pack)]).exit_code == 0
