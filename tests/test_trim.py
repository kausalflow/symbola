import tomllib

import pytest
from typer.testing import CliRunner

from symbola import trim
from symbola.cli import app
from symbola.extract import sync_components
from symbola.pack import validate_pack
from symbola.questions import review
from symbola.registry import scaffold_pack
from symbola.scaffold import scaffold

runner = CliRunner()

OBLIGATIONS = '''# Shout's decisions.

[[obligation]]
id = "shout.upper"
statement = "Every letter of the text comes back in upper case, and nothing else changes."
status = "decided"
source = "extract"
checks = ["upper#example:1", "upper#example:2", "upper#test_leaves_no_lowercase"]

[[obligation]]
id = "shout.upper-again"
statement = "Every letter comes back in upper case."
status = "decided"
source = "extract"
checks = ["upper#example:1"]

[[obligation]]
id = "shout.empty"
statement = "Empty text stays empty."
status = "decided"
source = "replication"
checks = ["upper#example:3", "upper#example:5"]

[[obligation]]
id = "shout.length"
statement = "The text keeps its length."
status = "decided"
source = "extract"
checks = ["upper#test_preserves_length", "upper#example:4"]
'''

PRODUCT = '''# Shout

## Shape

A command line that shouts. Every letter of the text comes back in upper case, and nothing else changes.
It reads standard input.

## Surfaces

- `shout TEXT`: prints the text in upper case.

## Flows

1. Run it; read the answer.
'''


@pytest.fixture
def pack(tmp_path):
    root = scaffold_pack("acme/shout", tmp_path / "spec")
    contract = scaffold("acme/upper", root / "components")
    examples = contract / "examples.jsonl"
    examples.write_text(examples.read_text() + '{"input": {"text": "x"}, "output": {"text": "X"}}\n'
                        '{"input": {"text": ""}, "output": {"text": ""}}\n')
    (root / "obligations.toml").write_text(OBLIGATIONS)
    (root / "PRODUCT.md").write_text(PRODUCT)
    sync_components(root)
    assert validate_pack(root).ok
    return root


def contract(pack):
    return pack / "components" / "upper" / "versions" / "1"


def obligations(pack):
    return {o["id"]: o for o in tomllib.loads((pack / "obligations.toml").read_text())["obligation"]}


def by_kind(cuts, kind):
    return [c for c in cuts if c.kind == kind]


def test_screen_finds_duplicates_repeats_and_restated_prose(pack):
    cuts = trim.screen(pack)
    [ex] = by_kind(cuts, "example")
    assert (ex.line, ex.same_as) == (5, 3)
    [ob] = by_kind(cuts, "obligation")
    assert ob.obligation == "shout.upper-again" and "shout.upper" in ob.why
    [prose] = by_kind(cuts, "prose")
    assert prose.file == "PRODUCT.md" and prose.text.startswith("Every letter of the text")


def test_obligations_builders_disagreed_on_are_never_proposed(pack):
    text = (pack / "obligations.toml").read_text().replace('source = "replication"', 'source = "extract"')
    (pack / "obligations.toml").write_text(text + '''
[[obligation]]
id = "shout.empty-again"
statement = "Empty text stays empty."
status = "decided"
source = "replication"
checks = ["upper#example:3"]
''')
    assert "shout.empty-again" not in {c.obligation for c in trim.screen(pack)}


def test_nothing_is_removed_without_approval(pack):
    before = {p: p.read_bytes() for p in pack.rglob("*") if p.is_file()}
    trim.propose(pack, trim.screen(pack))
    assert all(c.decision == "undecided" for c in trim.load(pack))
    with pytest.raises(trim.TrimError, match="nothing is marked"):
        trim.apply(pack)
    after = {p: p.read_bytes() for p in pack.rglob("*") if p.is_file() and ".symbolon" not in p.parts}
    assert after == {p: b for p, b in before.items()}


def test_decisions_survive_a_second_screen(pack):
    cuts = trim.propose(pack, trim.screen(pack))
    trim.decide(pack, [cuts[0].id], "keep")
    again = trim.propose(pack, trim.screen(pack))
    assert len(again) == len(cuts) and again[0].decision == "keep"
    with pytest.raises(trim.TrimError, match="no proposal nope"):
        trim.decide(pack, ["nope"], "cut")


def test_apply_cuts_only_what_was_approved_and_renumbers(pack):
    cuts = trim.propose(pack, trim.screen(pack))
    approve = [c.id for c in cuts if c.kind in ("example", "prose")]
    trim.decide(pack, approve, "cut")
    done = trim.apply(pack)
    assert done.removed_examples == {"upper": [5]}
    assert len((contract(pack) / "examples.jsonl").read_text().strip().splitlines()) == 4
    assert obligations(pack)["shout.empty"]["checks"] == ["upper#example:3"], "the duplicate's reference moves"
    assert "shout.upper-again" in obligations(pack), "a proposal not approved stays"
    product = (pack / "PRODUCT.md").read_text()
    assert "Every letter" not in product and "A command line that shouts.\nIt reads standard input." in product
    assert validate_pack(pack).ok
    assert all(c.applied for c in trim.load(pack) if c.id in approve)


def test_cutting_an_obligation_takes_the_checks_only_it_uses(pack):
    cut = trim._checked(pack, {"kind": "obligation", "obligation": "shout.length", "why": "obvious"})
    trim.propose(pack, [cut])
    trim.decide(pack, [cut.id], "cut")
    done = trim.apply(pack)
    assert "shout.length" not in obligations(pack)
    assert done.removed_examples == {"upper": [4]}
    assert done.removed_properties == {"upper": ["test_preserves_length"]}
    assert "def test_preserves_length" not in (contract(pack) / "properties.py").read_text()
    assert obligations(pack)["shout.empty"]["checks"] == ["upper#example:3", "upper#example:4"]
    assert validate_pack(pack).ok


def test_a_cut_that_breaks_the_pack_writes_nothing(pack):
    # The only check of shout.length: cutting it leaves a decided obligation unchecked.
    cut = trim._checked(pack, {"kind": "example", "component": "upper", "line": 4, "why": "x"})
    text = (pack / "obligations.toml").read_text().replace('"upper#test_preserves_length", ', "")
    (pack / "obligations.toml").write_text(text)
    trim.propose(pack, [cut])
    trim.decide(pack, [cut.id], "cut")
    before = (contract(pack) / "examples.jsonl").read_text()
    with pytest.raises(trim.TrimError, match="would not validate"):
        trim.apply(pack)
    assert (contract(pack) / "examples.jsonl").read_text() == before
    assert not trim.load(pack)[0].applied


def test_agent_proposals_are_checked(pack):
    with pytest.raises(trim.TrimError, match="exactly once"):
        trim._checked(pack, {"kind": "prose", "file": "PRODUCT.md", "text": "not in the file"})
    with pytest.raises(trim.TrimError, match="builders disagreed"):
        trim._checked(pack, {"kind": "obligation", "obligation": "shout.empty"})
    with pytest.raises(trim.TrimError, match="no example on line 9"):
        trim._checked(pack, {"kind": "example", "component": "upper", "line": 9})
    with pytest.raises(trim.TrimError, match="not 'symbolon-pack.toml'"):
        trim._checked(pack, {"kind": "prose", "file": "symbolon-pack.toml", "text": "acme"})


def test_a_released_version_is_trimmed_into_a_copy(tmp_path, pack):
    version = tmp_path / "reg" / "acme" / "shout" / "versions" / "1"
    version.parent.mkdir(parents=True)
    pack.rename(version)
    (version.parent.parent / "digests.txt").write_text("1 sha256:abc\n")
    cuts = trim.propose(version, trim.screen(version))
    trim.decide(version, [cuts[0].id], "cut")
    with pytest.raises(trim.TrimError, match="released version"):
        trim.apply(version)
    out = tmp_path / "spec2"
    trim.apply(version, out)
    assert validate_pack(out).ok and not trim.load(version)[0].applied


def test_sentences_keep_code_and_brackets_whole():
    text = "Fails with `Error. Try again.` (see A. Smith). Next one.\n- A bullet. Two\n  lines.\n# Heading."
    assert trim.sentences(text) == ["Fails with `Error. Try again.` (see A. Smith).", "Next one.",
                                    "A bullet.", "Two\n  lines."]


def test_cli_and_review_list(pack):
    result = runner.invoke(app, ["blueprint", "trim", str(pack)])
    assert result.exit_code == 0, result.output
    assert "3 proposals" in result.output and "Nothing" not in result.output.split("proposals")[0]
    todo = review(pack)
    assert len(todo["cuts"]) == 3 and todo["questions"] == []
    result = runner.invoke(app, ["blueprint", "review", str(pack)])
    assert "Proposed cuts to approve (3)" in result.output
    ids = [c.id for c in todo["cuts"]]
    result = runner.invoke(app, ["blueprint", "trim", str(pack), "--cut", ids[0], "--keep", ids[1]])
    assert result.exit_code == 0 and "1 cut, 1 keep, 1 undecided" in result.output
    result = runner.invoke(app, ["blueprint", "trim", str(pack), "--apply"])
    assert result.exit_code == 0, result.output
    assert "cut 1 proposals" in result.output
    assert len(review(pack)["cuts"]) == 1


def test_deep_pass_reads_a_copy_and_only_proposes(tmp_path, pack):
    agent = tmp_path / "agent.py"
    agent.write_text('''import pathlib
pathlib.Path("PRODUCT.md").write_text("vandalised")
out = pathlib.Path(".symbolon/trim-proposals.toml")
out.parent.mkdir(exist_ok=True)
out.write_text(\'\'\'
[[cut]]
kind = "prose"
file = "PRODUCT.md"
text = "It reads standard input."
why = "any CLI does"

[[cut]]
kind = "prose"
file = "PRODUCT.md"
text = "made up"
why = "x"
\'\'\')
''')
    import sys
    from symbola.agent import AgentCommand
    cuts, rejected, run = trim.deep_screen(pack, AgentCommand(f"{sys.executable} {agent}"), [])
    assert run.ok and [c.text for c in cuts] == ["It reads standard input."] and cuts[0].by == "agent"
    assert len(rejected) == 1 and "exactly once" in rejected[0]
    assert "vandalised" not in (pack / "PRODUCT.md").read_text()
