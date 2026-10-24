import shutil
import sys
import tomllib

import pytest
from typer.testing import CliRunner

from symbolon.agent import AgentCommand, AgentError, parse_agents, resolve_agent, run_agent
from symbolon.cli import app
from symbolon.digest import contract_digest
from symbolon.extract import ExtractError, extract, scaffold_pack, sync_components
from symbolon.pack import validate_pack
from symbolon.scaffold import scaffold
from symbolon.validate import regenerate_schema

from .conftest import REPO

STUB = f"{sys.executable} {REPO / 'tests' / 'stub_agent.py'}"
runner = CliRunner()

OBLIGATIONS = '''
[[obligation]]
id = "upper.ascii"
statement = "Letters a-z become A-Z; everything else is kept."
status = "decided"
source = "extract"
checks = ["upper#example:1", "upper#test_only_changes_case"]

[[obligation]]
id = "upper.non-ascii"
statement = "Whether non-ASCII letters are upper-cased."
status = "open"
source = "extract"
'''

BRIEF = '''# Shout

Upper-cases text.

## Non-goals

- Translation.

## Priorities

1. Correctness.

## Who resolves gaps

acme.
'''


@pytest.fixture
def source(tmp_path):
    src = tmp_path / "product"
    src.mkdir()
    (src / "shout.py").write_text("def shout(s):\n    return s.upper()\n")
    return src


@pytest.fixture
def draft(tmp_path):
    """What a good agent leaves behind: one component, its oracle adapter, and REVIEW.md."""
    d = tmp_path / "draft"
    contract = scaffold("acme/upper", tmp_path / "scratch")
    regenerate_schema(contract)
    comp = d / "versions" / "1" / "components" / "upper" / "versions" / "1"
    shutil.copytree(contract, comp, ignore=shutil.ignore_patterns("reference", "__pycache__"))
    pack = d / "versions" / "1"
    (pack / "obligations.toml").write_text(OBLIGATIONS)
    (pack / "BRIEF.md").write_text(BRIEF)
    (pack / "assumptions").mkdir()
    (pack / "assumptions" / "ascii.toml").write_text(
        'id = "K-ascii"\nstatement = "Input is mostly ASCII."\nbasis = "It is."\nmonitor = "none"\n')
    oracle = d / "oracle" / "upper"
    oracle.mkdir(parents=True)
    shutil.copy(contract / "reference" / "impl.py", oracle / "impl.py")
    (oracle / "symbolon-impl.toml").write_text(
        f'[implementation]\ncontract = "{contract_digest(comp)}"\nentrypoint = "impl.py"\n'
        'language = "python"\nlicense = "MIT"\nauthors = ["acme"]\n')
    (d / "REVIEW.md").write_text("# Review\n\n- Confirm the non-goals.\n")
    return d


@pytest.fixture
def stub(monkeypatch, draft):
    monkeypatch.setenv("STUB_DRAFT", str(draft))
    monkeypatch.setenv("STUB_MODE", "good")
    return AgentCommand(STUB)


# ── agent.py ──────────────────────────────────────────────────────────────


def test_resolve_agent_order(monkeypatch):
    monkeypatch.delenv("SYMBOLON_AGENT", raising=False)
    assert resolve_agent().is_claude_code
    monkeypatch.setenv("SYMBOLON_AGENT", "codex exec")
    assert resolve_agent().name == "codex"
    assert resolve_agent("aider --yes").name == "aider"


def test_parse_agents_names():
    agents = parse_agents(["claude=claude -p", "codex exec --flag=1", "my-agent=./run.sh"])
    assert [a.name for a in agents] == ["claude", "codex", "my-agent"]
    assert agents[1].argv == ["codex", "exec", "--flag=1"]
    with pytest.raises(AgentError, match="unique"):
        parse_agents(["claude -p", "claude -p --model x"])


def test_run_agent_passes_prompt_placeholders_and_env(tmp_path, monkeypatch, draft):
    monkeypatch.setenv("STUB_DRAFT", str(draft))
    work = tmp_path / "work"
    run = run_agent(AgentCommand(STUB + " --prompt {prompt_file} --in {workdir} {literal}"), "hello agent", work,
                    extra_dirs=[tmp_path / "product"])
    assert run.ok, run.stderr
    assert "hello agent" in (work / "stub-prompts.txt").read_text()
    assert (work / ".symbolon" / "prompt.md").read_text() == "hello agent"
    env = (work / "stub-env.txt").read_text()
    assert f"SYMBOLON_WORKDIR={work.resolve()}" in env
    assert f"SYMBOLON_EXTRA_DIRS={(tmp_path / 'product').resolve()}" in env
    assert str(work.resolve() / ".symbolon" / "prompt.md") in env and "{literal}" in env


def test_claude_code_gets_add_dir():
    assert AgentCommand("/usr/local/bin/claude -p").is_claude_code
    assert not AgentCommand("codex exec").is_claude_code


def test_run_agent_missing_command(tmp_path):
    with pytest.raises(AgentError, match="not found"):
        run_agent(AgentCommand("no-such-agent-xyz"), "hi", tmp_path)


def test_run_agent_timeout(tmp_path):
    with pytest.raises(AgentError, match="timed out"):
        run_agent(AgentCommand(f"{sys.executable} -c 'import time; time.sleep(5)'"), "", tmp_path, timeout=1)


# ── extract ───────────────────────────────────────────────────────────────


def test_extract_with_a_good_agent(tmp_path, source, stub):
    result = extract(source, "acme/shout", agent=stub, root=tmp_path / "packs")
    failed = [(c.name, c.detail) for r in result.rounds for c in r.checks if not c.ok]
    assert result.ok, failed
    assert len(result.rounds) == 1
    product = tmp_path / "packs" / "acme" / "shout"
    assert result.pack_dir == product / "versions" / "1"
    # The prompt names the source and the layout, and the agent may read the source.
    prompt = (product / "stub-prompts.txt").read_text()
    assert str(source) in prompt and "oracle/<name>/" in prompt
    assert f"SYMBOLON_EXTRA_DIRS={source}" in (product / "stub-env.txt").read_text()
    # Digests were filled in, so the pack validates on its own.
    with (result.pack_dir / "symbolon-pack.toml").open("rb") as f:
        manifest = tomllib.load(f)
    assert manifest["pack"]["id"] == "acme/shout"
    assert list(manifest["components"]) == ["acme/upper@1"]
    assert validate_pack(result.pack_dir).ok
    assert result.pack_report.summary["by_status"] == {"decided": 1, "default": 0, "open": 1}
    names = {c.name for c in result.rounds[0].checks}
    assert "upper: original passes its spec" in names
    assert (product / ".symbolon" / "extract-prompt.md").is_file()
    assert (product / ".symbolon" / "extract-round-1.log").is_file()
    # Nothing was written into the product.
    assert sorted(p.name for p in source.iterdir()) == ["shout.py"]


def test_extract_runs_a_fix_round(tmp_path, source, stub, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "no-review")
    result = extract(source, "acme/shout", agent=stub, root=tmp_path / "packs", rounds=2)
    assert not result.rounds[0].ok and result.rounds[1].ok
    prompts = (tmp_path / "packs" / "acme" / "shout" / "stub-prompts.txt").read_text()
    assert "does not pass yet" in prompts and "REVIEW.md" in prompts.split("does not pass yet")[1]


def test_extract_gives_up_after_its_rounds(tmp_path, source, stub, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "no-review")
    result = extract(source, "acme/shout", agent=stub, root=tmp_path / "packs", rounds=1)
    assert not result.ok and len(result.rounds) == 1


def test_extract_catches_a_spec_the_original_fails(tmp_path, source, stub, draft):
    (draft / "oracle" / "upper" / "impl.py").write_text("def run(input):\n    return {'text': input['text']}\n")
    result = extract(source, "acme/shout", agent=stub, root=tmp_path / "packs", rounds=1)
    failed = {c.name: c.detail for c in result.rounds[0].checks if not c.ok}
    assert "upper: original passes its spec" in failed


def test_extract_requires_an_oracle_adapter(tmp_path, source, stub, draft):
    shutil.rmtree(draft / "oracle" / "upper")
    result = extract(source, "acme/shout", agent=stub, root=tmp_path / "packs", rounds=1)
    assert not result.ok
    result = extract(source, "acme/shout", agent=stub, root=tmp_path / "other", oracle=False)
    assert result.ok


def test_extract_stops_when_the_agent_fails(tmp_path, source, stub, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "fail")
    result = extract(source, "acme/shout", agent=stub, root=tmp_path / "packs", rounds=3)
    assert len(result.rounds) == 1 and not result.ok
    assert "exit 3" in result.rounds[0].checks[0].detail
    assert "stub agent gave up" in result.rounds[0].log.read_text()


def test_extract_refuses_existing_version_and_bad_input(tmp_path, source, stub):
    extract(source, "acme/shout", agent=stub, root=tmp_path / "packs")
    with pytest.raises(ExtractError, match="already exists"):
        extract(source, "acme/shout", agent=stub, root=tmp_path / "packs")
    with pytest.raises(ExtractError, match="namespace/product"):
        extract(source, "shout", agent=stub, root=tmp_path / "packs")
    with pytest.raises(ExtractError, match="outside"):
        extract(source, "acme/shout", agent=stub, root=source / "packs")


def test_scaffold_has_the_brief_sections(tmp_path):
    pack = scaffold_pack("acme/shout", tmp_path / "acme" / "shout")
    report = validate_pack(pack)
    brief = next(c for c in report.checks if c.name.startswith("BRIEF.md"))
    assert brief.ok


def test_sync_components_keeps_the_rest_of_the_manifest(tmp_path, draft):
    pack = draft / "versions" / "1"
    (pack / "symbolon-pack.toml").write_text(
        '[pack]\nid = "acme/shout"\nversion = 1\n\n[components]\n"stale@1" = "sha256:00"\n\n[extra]\nx = 1\n')
    listed = sync_components(pack)
    with (pack / "symbolon-pack.toml").open("rb") as f:
        manifest = tomllib.load(f)
    assert manifest["components"] == listed == {"acme/upper@1": contract_digest(pack / "components" / "upper" / "versions" / "1")}
    assert manifest["extra"] == {"x": 1} and manifest["pack"]["id"] == "acme/shout"


def test_extract_cli(tmp_path, source, stub):
    result = runner.invoke(app, ["extract", str(source), "--pack", "acme/shout",
                                 "--root", str(tmp_path / "packs"), "--agent", STUB])
    assert result.exit_code == 0, result.output
    assert "draft pack" in result.output and "1 decided" in result.output


def test_extract_cli_failure(tmp_path, source, stub, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "fail")
    result = runner.invoke(app, ["extract", str(source), "--pack", "acme/shout",
                                 "--root", str(tmp_path / "packs"), "--agent", STUB])
    assert result.exit_code == 1
    assert "draft is not valid yet" in result.output


def test_relative_agent_path_means_the_callers_directory(tmp_path, monkeypatch, draft):
    script = tmp_path / "agent.sh"
    script.write_text(f"#!/bin/sh\nexec {STUB}\n")
    script.chmod(0o755)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("STUB_DRAFT", str(draft))
    run = run_agent(AgentCommand("./agent.sh"), "hi", tmp_path / "work")
    assert run.ok, run.stderr
