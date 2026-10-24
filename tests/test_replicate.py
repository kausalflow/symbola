import json
import shutil
import sys

import pytest
from typer.testing import CliRunner

from symbolon import keys
from symbolon.attest import verify_attestation
from symbolon.cli import app
from symbolon.digest import contract_digest
from symbolon.implementation import load_impl_manifest
from symbolon.sandbox import ProcessSandbox, SandboxUnavailable

runner = CliRunner()

# A stand-in for a coding agent: it copies the reference implementation into
# build/date-parse/, changed as its variant says, the way an agent's build would land.
STUB = r'''
import json, pathlib, sys
from symbolon.digest import contract_digest

variant, source = sys.argv[1], pathlib.Path(sys.argv[2])
prompt = sys.stdin.read()
assert "build/date-parse/" in prompt and pathlib.Path(".symbolon/prompt.md").read_text() == prompt
if variant == "nothing":
    sys.exit(3)
spec = pathlib.Path("pack/components/date-parse/versions/1")
assert not (spec / "reference").exists(), "the builder must not see the reference"
code = source.read_text()
if variant == "lenient":  # passes the suite, but also ignores spaces inside the date
    code = code.replace('input["text"].strip()', '"".join(input["text"].split())')
out = pathlib.Path("build/date-parse")
out.mkdir(parents=True)
(out / "impl.py").write_text(code)
(out / "symbolon-impl.toml").write_text(
    f'[implementation]\ncontract = "{contract_digest(spec)}"\nlicense = "MIT"\nauthors = ["stub"]\n')
spaces = "ignored" if variant == "lenient" else "rejected"
pathlib.Path("build/readings.toml").write_text(
    f'[[reading]]\npoint = "spaces inside a date"\nconsidered = ["rejected", "ignored"]\nchosen = "{spaces}"\n'
    + ('probes = [{ text = "1. 2.1999", locale = "de-DE" }, { text = "x", locale = "nope" }]\n'
       if variant == "lenient" else ""))
if variant == "lenient":
    (out / "symbolon-flags.jsonl").write_text(json.dumps({"ref": "date-parse#example:1", "reason": "r"}) + "\n")
'''

DIFF_BUDGET = ["--mutations", "60", "--property-cases", "10", "--search", "20"]


@pytest.fixture
def pack(tmp_path, copy_seed):
    """A one-component pack around core/date-parse, and a stub agent command per variant."""
    root = tmp_path / "pack" / "versions" / "1"
    contract = root / "components" / "date-parse" / "versions" / "1"
    contract.parent.mkdir(parents=True)
    shutil.move(copy_seed("core/date-parse"), contract)
    (root / "symbolon-pack.toml").write_text(
        f'[pack]\nid = "test/dates"\nversion = 1\n\n[components]\n"core/date-parse@1" = "{contract_digest(contract)}"\n')
    (root / "BRIEF.md").write_text("# Dates\n\n## Non-goals\n\nNone.\n\n## Priorities\n\nCorrect.\n\n"
                                   "## Who resolves gaps\n\nThe test.\n")
    (root / "obligations.toml").write_text(
        '[[obligation]]\nid = "date.round-trip"\nstatement = "Every date round-trips."\n'
        'status = "decided"\nchecks = ["date-parse#test_round_trips_every_date"]\n')
    stub = tmp_path / "stub_agent.py"
    stub.write_text(STUB)
    source = contract / "reference" / "impl.py"
    reference = tmp_path / "original" / "date-parse"
    reference.mkdir(parents=True)
    shutil.copy(source, reference / "impl.py")
    (reference / "symbolon-impl.toml").write_text(
        f'[implementation]\ncontract = "{contract_digest(contract)}"\nlicense = "MIT"\nauthors = ["original"]\n')

    def agent(name: str, variant: str) -> str:
        return f"{name}={sys.executable} {stub} {variant} {source}"
    return root, agent, tmp_path


def _replicate(root, *args, code=0):
    result = runner.invoke(app, ["replicate", str(root), "--no-attest", *DIFF_BUDGET, "--json", *args])
    assert result.exit_code == code, result.output
    return json.loads(result.output)


def test_builds_are_checked_and_diffed(pack):
    root, agent, tmp = pack
    holdout = tmp / "holdout"
    holdout.mkdir()
    (holdout / "date-parse.jsonl").write_text(
        json.dumps({"input": {"text": "3.4.2021", "locale": "de-DE"}, "output": {"date": "2021-04-03"}}) + "\n")
    out = tmp / "run"
    r = _replicate(root, "--agent", agent("alpha", "same"), "--agent", agent("beta", "lenient"),
                   "--builds", "2", "--holdout", str(holdout), "-o", str(out))

    assert [b["name"] for b in r["builds"]] == ["alpha-1", "beta-2"]
    for b in r["builds"]:
        assert b["exit_code"] == 0
        c = b["components"]["date-parse"]
        assert c["built"] and c["public"]["passed"]
        assert c["holdout"]["passed"] and c["holdout"]["unseen_examples"] == 1
        assert c["manifest_changes"] == ["re-pinned to the published contract digest", "added [generator]"]
        m = load_impl_manifest(out / "builds" / b["name"] / "build" / "date-parse")
        assert m.implementation.contract == r["pack"]["components"]["date-parse"]
        assert m.generator.model == b["agent"] and m.generator.prompt_digest == b["prompt_digest"]
    assert r["builds"][1]["components"]["date-parse"]["flags"] == 1

    row = r["components"]["date-parse"]
    assert row["passed"] == 2 and row["holdout_passed"] == 2
    d = row["diff"]
    assert d["members"] == ["alpha-1", "beta-2"] and d["ambiguity"] > 0
    gap = [s for s in d["splits"] if s["groups"] == [["alpha-1"], ["beta-2"]] and not s["obligations"]]
    assert gap and gap[0]["verdict"] == "gap"
    # Found by beta's probe, not by chance: the pool has no input with a space inside a date.
    report = json.loads((out / "diff" / "date-parse.json").read_text())
    assert any("pool:probes-beta-2.jsonl" in s["origins"] for s in report["splits"])
    assert report["readings"]["probes"] == 2
    assert d["readings"]["splits"][0]["chosen"] == {"alpha-1": "rejected", "beta-2": "ignored"}
    assert (out / "diff" / "date-parse.json").is_file()
    assert r["summary"]["all_passed"] and not r["summary"]["converged"]
    assert json.loads((out / "replication.json").read_text())["summary"] == r["summary"]


def test_agreeing_builds_converge_and_match_the_reference(pack):
    root, agent, tmp = pack
    r = _replicate(root, "--agent", agent("a", "same"), "--agent", agent("b", "same"), "--builds", "3",
                   "--reference", str(tmp / "original"), "-o", str(tmp / "run"))
    d = r["components"]["date-parse"]["diff"]
    assert d["members"] == ["a-1", "b-2", "a-3"] and d["reference"] == "reference"
    assert d["ambiguity"] == 0 and d["splits"] == []
    assert d["to_reference"] == {"a-1": 0, "b-2": 0, "a-3": 0}
    assert r["summary"]["converged"]


def test_a_failed_agent_is_reported(pack):
    root, agent, tmp = pack
    r = _replicate(root, "--agent", agent("good", "same"), "--agent", agent("bad", "nothing"),
                   "-o", str(tmp / "run"), code=1)
    bad = r["builds"][1]
    assert bad["exit_code"] == 3 and not bad["components"]["date-parse"]["built"]
    assert (tmp / "run" / "builds" / "bad-2" / "agent.log").read_text().startswith("$ ")
    assert r["components"]["date-parse"]["passed"] == 1
    assert r["components"]["date-parse"]["diff"] is None
    assert not r["summary"]["all_passed"]


def test_holdout_catches_what_the_public_suite_does_not(pack):
    root, agent, tmp = pack
    holdout = tmp / "holdout"
    holdout.mkdir()
    # The publisher keeps a rule back: here, one the reference itself breaks.
    (holdout / "date-parse.jsonl").write_text(
        json.dumps({"input": {"text": "2021-04-03", "locale": "ISO"}, "output": {"date": "2021-04-04"}}) + "\n")
    r = _replicate(root, "--agent", agent("a", "same"), "--builds", "1", "--holdout", str(holdout),
                   "-o", str(tmp / "run"), code=1)
    c = r["builds"][0]["components"]["date-parse"]
    assert c["public"]["passed"] and not c["holdout"]["passed"]
    assert r["components"]["date-parse"]["holdout_passed"] == 0


def test_rejects_bad_requests(pack):
    root, agent, tmp = pack
    result = runner.invoke(app, ["replicate", str(root), "--no-attest", "--agent", agent("a", "same"),
                                 "--component", "nope", "-o", str(tmp / "run")])
    assert result.exit_code == 1 and "no component named nope" in result.output
    result = runner.invoke(app, ["replicate", str(root), "--no-attest", "--agent", agent("a", "same"),
                                 "--agent", agent("a", "lenient")])
    assert result.exit_code != 0 and "unique" in result.output
    (root / "BRIEF.md").write_text("# Dates\n")
    result = runner.invoke(app, ["replicate", str(root), "--no-attest", "--agent", agent("a", "same"),
                                 "-o", str(tmp / "run2")])
    assert result.exit_code == 1 and "pack is not valid" in result.output


def _process_sandbox():
    try:
        return ProcessSandbox()
    except SandboxUnavailable:
        return None


@pytest.mark.skipif(_process_sandbox() is None, reason="process sandbox not available here")
def test_builds_are_attested(pack):
    root, agent, tmp = pack
    key = keys.generate(tmp / "runner.key")
    out = tmp / "run"
    r = _replicate(root, "--attest", "--key", str(key), "--sandbox", "process", "--agent", agent("a", "same"),
                   "--builds", "1", "-o", str(out))
    pub = r["builds"][0]["components"]["date-parse"]["public"]
    assert pub["attested"] and pub["passed"]
    envelope = json.loads((out / "attestations" / "date-parse.a-1.json").read_text())
    v = verify_attestation(envelope, trusted_keys=[keys.public_path(key)],
                           contract_dir=root / "components" / "date-parse" / "versions" / "1",
                           impl_dir=out / "builds" / "a-1" / "build" / "date-parse")
    assert v.ok
