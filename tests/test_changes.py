import json
import shutil

import pytest
from typer.testing import CliRunner

from symbola.changes import compare, conflicts, is_empty, load_overrides, markdown, summary_text, Override
from symbola.cli import app
from symbola.digest import contract_digest
from symbola.registry import build_site

from .conftest import REPO

LIGHTKONE = REPO / "tests" / "fixtures" / "lightkone" / "versions" / "1"
runner = CliRunner()


def _edit(path, old, new):
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new, 1))


def make_v2(v2):
    """A second version: one decision reworded, one added, a component's examples and BRIEF.md changed."""
    _edit(v2 / "obligations.toml", 'statement = "Results are distinct ids of papers in the input library."',
          'statement = "Results are distinct ids of papers in the input library, in library order."')
    with (v2 / "obligations.toml").open("a") as f:
        f.write('\n[[obligation]]\nid = "search.new-rule"\nstatement = "A new rule."\nstatus = "open"\n')
    tidy = v2 / "components" / "tidy" / "versions" / "1"
    before = contract_digest(tidy)
    examples = tidy / "examples.jsonl"
    examples.write_text(examples.read_text() + examples.read_text().splitlines()[0] + "\n")
    _edit(v2 / "symbolon-pack.toml", before, contract_digest(tidy))
    with (v2 / "BRIEF.md").open("a") as f:
        f.write("\nVersion two.\n")


@pytest.fixture
def versions(tmp_path):
    root = tmp_path / "packs" / "kausalflow" / "lightkone" / "versions"
    for n in (1, 2):
        shutil.copytree(LIGHTKONE, root / str(n), ignore=shutil.ignore_patterns("__pycache__"))
    make_v2(root / "2")
    return root


def test_compare_lists_changes_by_decision_component_and_document(versions):
    c = compare(versions / "1", versions / "2")
    assert [x["id"] for x in c["decisions"]["changed"]] == ["search.results-from-library"]
    assert list(c["decisions"]["changed"][0]["fields"]) == ["statement"]
    assert [x["id"] for x in c["decisions"]["added"]] == ["search.new-rule"]
    assert c["decisions"]["removed"] == []
    assert [(x["name"], x["files"]) for x in c["components"]["changed"]] == [("tidy", ["examples.jsonl"])]
    assert [d["file"] for d in c["documents"]] == ["BRIEF.md"]
    assert summary_text(c) == "decisions: 1 changed, 1 added; component tidy changed; BRIEF.md changed"
    assert is_empty(compare(versions / "1", versions / "1"))


def test_markdown_marks_overridden_decisions(versions):
    c = compare(versions / "1", versions / "2")
    mine = [Override(id="search.results-from-library", reason="we sort by year"),
            Override(id="search.trash", reason="no trash in our build")]
    assert conflicts(c, mine) == ["search.results-from-library"]
    text = markdown(c, "Upgrade", mine)
    assert "**You override this decision**" in text
    assert "`search.trash`: no trash in our build (unchanged upstream: keep it)" in text
    assert "+Version two." in text


def test_overrides_file_is_checked(tmp_path):
    assert load_overrides(tmp_path / "missing.toml") == []
    bad = tmp_path / "overrides.toml"
    bad.write_text('[[override]]\nid = "a.b"\n')
    with pytest.raises(ValueError):
        load_overrides(bad)


def test_site_publishes_what_the_latest_version_changed(versions, tmp_path):
    site = tmp_path / "site"
    build_site(versions.parent.parent.parent, site)
    (entry,) = json.loads((site / "index.json").read_text())["packs"]
    assert entry["changes"]["from"] == 1 and entry["changes"]["summary"]["decisions_changed"] == 1
    files = site / "packs" / "kausalflow" / "lightkone"
    assert json.loads((files / "changes.json").read_text())["to"] == 2
    assert "search.new-rule" in (files / "changes.md").read_text()
    assert "## What changed in version 2" in (files / "llms.txt").read_text()


def test_a_first_version_has_no_changes(tmp_path):
    shutil.copytree(LIGHTKONE, tmp_path / "packs" / "kausalflow" / "lightkone" / "versions" / "1",
                    ignore=shutil.ignore_patterns("__pycache__"))
    build_site(tmp_path / "packs", tmp_path / "site")
    (entry,) = json.loads((tmp_path / "site" / "index.json").read_text())["packs"]
    assert entry["changes"] is None
    assert not (tmp_path / "site" / "packs" / "kausalflow" / "lightkone" / "changes.json").exists()


def test_upgrade_writes_notes_for_the_agent(versions, tmp_path, monkeypatch):
    site1, site2 = tmp_path / "site1", tmp_path / "site2"
    only_v1 = tmp_path / "only-v1" / "kausalflow" / "lightkone" / "versions"
    shutil.copytree(versions / "1", only_v1 / "1")
    build_site(only_v1.parent.parent.parent, site1)
    build_site(versions.parent.parent.parent, site2)
    work = tmp_path / "build"
    work.mkdir()
    monkeypatch.chdir(work)
    assert runner.invoke(app, ["pull", "kausalflow/lightkone", "--registry", str(site1), "--dest", "spec"]).exit_code == 0

    r = runner.invoke(app, ["upgrade", "--registry", str(site1)])
    assert r.exit_code == 0 and "up to date" in r.output
    assert not (work / "spec.new").exists()

    (work / "overrides.toml").write_text('[[override]]\nid = "search.results-from-library"\nreason = "we sort by year"\n')
    (work / "impl" / "tidy").mkdir(parents=True)
    r = runner.invoke(app, ["upgrade", "--registry", str(site2)])
    assert r.exit_code == 0, r.output
    assert "changes decisions your build overrides: search.results-from-library" in r.output
    notes = (work / "UPGRADE.md").read_text()
    assert notes.startswith("# Upgrade kausalflow/lightkone from version")
    assert "symbola test spec.new/components/tidy/versions/1 impl/tidy\n" in notes
    assert "--repin" in notes
    assert (work / "spec.new" / "BRIEF.md").read_text().endswith("Version two.\n")


def test_impl_init_repin(tmp_path):
    contract = tmp_path / "tidy"
    shutil.copytree(LIGHTKONE / "components" / "tidy" / "versions" / "1", contract,
                    ignore=shutil.ignore_patterns("__pycache__"))
    impl = tmp_path / "impl"
    assert runner.invoke(app, ["impl-init", str(impl), "--contract", str(contract)]).exit_code == 0
    examples = contract / "examples.jsonl"
    examples.write_text(examples.read_text() + examples.read_text().splitlines()[0] + "\n")
    assert runner.invoke(app, ["impl-init", str(impl), "--contract", str(contract)]).exit_code == 1
    r = runner.invoke(app, ["impl-init", str(impl), "--contract", str(contract), "--repin"])
    assert r.exit_code == 0, r.output
    assert contract_digest(contract) in (impl / "symbolon-impl.toml").read_text()


def test_changes_command(versions, tmp_path):
    r = runner.invoke(app, ["changes", str(versions / "1"), str(versions / "2"), "--json"])
    assert r.exit_code == 0
    assert json.loads(r.output)["summary"]["components_changed"] == 1
    out = tmp_path / "changes.md"
    r = runner.invoke(app, ["changes", str(versions / "1"), str(versions / "2"), "-o", str(out)])
    assert r.exit_code == 0 and "search.new-rule" in out.read_text()
