"""`symbola replicate`: rebuild a pack with outside coding agents and measure the result.

Symbolon does not write code. Replication hands a builder's copy of a spec
pack to an external coding agent (Claude Code by default; any agent CLI
through `agent.py`), several times, then checks what came back:

1. each build runs the public suite of every component, attested in a
   sandbox when a runner key is given;
2. each build runs the publisher's holdout when there is one: a different
   property seed, more generated cases, and examples the builder never saw;
3. `symbola diff` runs per component across the builds that passed, with
   the original product as the reference when there is one, so splits show
   where the pack leaves a decision open (design v0.5, section 5.3).

The result is `replication.json` in the run directory, next to the builds,
their agent logs, and the attestations. This is what the lightkone pilots
did by hand. The agent itself is not sandboxed: it runs with the caller's
permissions, in a work directory that holds only the builder's copy.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import string
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .agent import AgentCommand, AgentError, parse_agents, run_agent
from .attest import AttestError, run_attestation, statement_of
from .canary import FLAGS_FILE, NOT_FOR_BUILDERS, read_flags
from .diff import load_member, measure
from .digest import contract_digest
from .implementation import IMPL_MANIFEST_FILE, load_impl_manifest
from .manifest import load_manifest
from .pack import PACK_MANIFEST_FILE, _component_dirs, validate_pack
from .sandbox import SandboxError
from .validate import WorkerError, check_impl, run_worker

REPORT_FILE = "replication.json"
PACK_DIR = "pack"     # the builder's copy, inside each build's work directory
BUILD_DIR = "build"   # where the agent writes one implementation per component
LOG_FILE = "agent.log"

DEFAULT_PROMPT = """\
You are building software from a Symbolon spec pack, in a clean room: build only
from the pack. It is in `$pack/`. Start with `$pack/AGENTS.md` if it exists, then
`$pack/BRIEF.md`, `$pack/assumptions/` and `$pack/obligations.toml`. Do not look for
the original product's source, and do not read anything outside this directory.
This run checks the components: if the pack has a `PRODUCT.md`, read it for context
but build only the components below, not the whole product.

Build each of these components into its own directory under `$build/`:

$components

Each build directory needs a `symbolon-impl.toml`. Create it with
`symbola impl-init $build/<name> --contract <spec>` and edit it if you do not
write Python (the pack's AGENTS.md, or `symbola impl-init --help`, says how).
Check your work with `symbola test <spec> $build/<name>` until it passes.

Write `$build/NOTES.md` with your questions about unclear parts and the reading
you chose for each. Record every such choice in `$build/readings.toml` as well:

    [[reading]]
    point = "what was unclear"
    considered = ["one reading", "another reading"]
    chosen = "the reading you built"
    obligation = "the obligation id, if it is about one"
    component = "the component"
    probes = [ { ... } ]   # inputs (as in examples.jsonl, without output) where the readings differ

Give each reading one to three probes: inputs that the readings you considered
would answer differently. They are run on every build, so be concrete. Probes
may name fixtures like the examples do, written in TOML as `{ "$fixture" = "<file>" }`.

If the spec contradicts itself, run
`symbola flag <component>#example:<line> "<what disagrees, and the reading you chose>" --dir $build/<component>`
and carry on; do not code around it.

You are done when `symbola test` passes for every component. Your builds will
also be checked on inputs you have not seen.
"""

# Prose-only builds get the pack without its checks, so whether they pass shows
# whether the descriptions, brief and obligations alone carry the spec. Examples
# can mask a wrong or incomplete description, since builders fit them.
PROSE_ONLY_HIDDEN = ("examples.jsonl", "properties.py")

PROSE_ONLY_PROMPT = """\
You are building software from a Symbolon spec pack, in a clean room: build only
from the pack. It is in `$pack/`. Start with `$pack/AGENTS.md` if it exists, then
`$pack/BRIEF.md`, `$pack/assumptions/` and `$pack/obligations.toml`. Do not look for
the original product's source, and do not read anything outside this directory.
This run checks the components: if the pack has a `PRODUCT.md`, read it for context
but build only the components below, not the whole product.

This copy of the pack has no examples and no properties: each component's
description (in its `symbolon.toml`), its schema, and the pack's brief,
assumptions and obligations are the whole specification. The `checks` listed in
`obligations.toml` refer to tests you do not have; read the statements instead.
`symbola test` cannot run on this copy, so write your own tests from the
descriptions, and treat every rule a description states as exact.

Build each of these components into its own directory under `$build/`:

$components

Each build directory needs a `symbolon-impl.toml`. Create it with
`symbola impl-init $build/<name> --contract <spec>` and edit it if you do not
write Python (the pack's AGENTS.md, or `symbola impl-init --help`, says how).

Write `$build/NOTES.md` with your questions about unclear parts and the reading
you chose for each. Record every such choice in `$build/readings.toml` as well:

    [[reading]]
    point = "what was unclear"
    considered = ["one reading", "another reading"]
    chosen = "the reading you built"
    obligation = "the obligation id, if it is about one"
    component = "the component"
    probes = [ { ... } ]   # inputs (matching the schema) where the readings differ

Give each reading one to three probes: inputs that the readings you considered
would answer differently. They are run on every build, so be concrete.

If the spec contradicts itself, run
`symbola flag <obligation id> "<what disagrees, and the reading you chose>" --dir $build/<component>`
and carry on; do not code around it.

You are done when every component does what its description says. Your builds
will be checked against the full specification, which you have not seen.
"""


class ReplicateError(Exception):
    pass


@dataclass
class Options:
    builds: int = 2
    components: list[str] | None = None
    reference: Path | None = None       # directory with one implementation per component
    holdout: Path | None = None         # directory with <component>.jsonl extra examples
    holdout_seed: int = 20261021
    holdout_scale: int = 5
    sandbox: object | None = None       # attest in this sandbox, with `key`
    key: object | None = None
    agent_timeout: int = 3600
    jobs: int = 1
    prompt: str | None = None           # template; $pack, $build and $components are filled in
    prose_only: int = 0                 # how many builds (the last ones) get the pack without its checks
    pools: list[Path] = field(default_factory=list)  # extra diff inputs
    mutations: int = 500
    property_cases: int = 50
    search: int = 300
    seed: int = 0
    diff_timeout: int = 900
    progress: Callable[[str], None] = field(default=lambda msg: None)


# ── the builder's copy and the prompt ────────────────────────────────────


def builder_copy(pack_dir: Path, dest: Path, prose_only: bool = False) -> None:
    """The pack as a builder may see it: no reference implementations, no mutants.

    A prose-only copy also leaves out every component's examples and properties.
    """
    hidden = NOT_FOR_BUILDERS + (PROSE_ONLY_HIDDEN if prose_only else ())
    shutil.copytree(pack_dir, dest, ignore=shutil.ignore_patterns(*hidden, ".*"))


def render_prompt(template: str, components: dict[str, Path], pack_dir: Path) -> str:
    rows = "\n".join(f"- `{name}`: spec `{PACK_DIR}/{d.relative_to(pack_dir).as_posix()}`, "
                     f"build into `{BUILD_DIR}/{name}/`" for name, d in components.items())
    return string.Template(template).safe_substitute(pack=PACK_DIR, build=BUILD_DIR, components=rows)


def _toml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def finish_manifest(impl_dir: Path, *, builder_digest: str, published_digest: str, agent: str,
                    prompt_digest: str) -> list[str]:
    """Pin a build to the published contract and record which agent made it.

    The builder's copy has no reference/ or mutants/, so a build pinned to the
    copy's digest is re-pinned to the published one. A [generator] section is
    added unless the agent wrote its own. Returns what was changed.
    """
    path = Path(impl_dir) / IMPL_MANIFEST_FILE
    text = path.read_text()
    changes = []
    if builder_digest != published_digest and builder_digest in text:
        text = text.replace(builder_digest, published_digest)
        changes.append("re-pinned to the published contract digest")
    if "generator" not in tomllib.loads(text):
        text = (text.rstrip("\n") + "\n\n# Added by symbola replicate.\n[generator]\n"
                f"model = {_toml_str(agent)}\nfamily = {_toml_str(agent)}\n"
                f"prompt_digest = {_toml_str(prompt_digest)}\n")
        changes.append("added [generator]")
    path.write_text(text)
    load_impl_manifest(impl_dir)  # still valid
    return changes


# ── holdout ──────────────────────────────────────────────────────────────


def _set_spec(text: str, key: str, value: int) -> str:
    line = f"{key} = {value}"
    if re.search(rf"^{key}\s*=.*$", text, flags=re.M):
        return re.sub(rf"^{key}\s*=.*$", line, text, count=1, flags=re.M)
    if re.search(r"^\[spec\]\s*$", text, flags=re.M):
        return re.sub(r"^\[spec\]\s*$", f"[spec]\n{line}", text, count=1, flags=re.M)
    return text.rstrip("\n") + f"\n\n[spec]\n{line}\n"


def holdout_contract(contract_dir: Path, dest: Path, examples: Path | None, seed: int, scale: int) -> Path:
    """A copy of the contract with another seed, `scale` times the cases, and the extra examples."""
    shutil.copytree(contract_dir, dest, ignore=shutil.ignore_patterns("__pycache__"))
    if examples is not None and examples.is_file():
        current = (dest / "examples.jsonl").read_text()
        extra = examples.read_text()
        (dest / "examples.jsonl").write_text(current.rstrip("\n") + "\n" + extra.lstrip("\n"))
    spec = load_manifest(contract_dir).spec
    text = (dest / "symbolon.toml").read_text()
    text = _set_spec(text, "seed", seed)
    text = _set_spec(text, "max_examples", min(spec.max_examples * scale, 100_000))
    text = _set_spec(text, "timeout_seconds", spec.timeout_seconds * scale)
    (dest / "symbolon.toml").write_text(text)
    return dest


# ── checks ───────────────────────────────────────────────────────────────


def _counts(result: dict) -> dict:
    checks = result.get("examples", []) + result.get("properties", [])
    return {"passed": bool(result.get("passed")), "checks": len(checks),
            "failed": [c["name"] for c in checks if not c["ok"]]}


def _public(contract: Path, impl: Path, opts: Options, attestation: Path) -> dict:
    if opts.sandbox is None:
        try:
            result = check_impl(contract, impl)
        except WorkerError as e:
            return {"passed": False, "error": str(e)}
        if "error" in result:
            return {"passed": False, "error": result["error"]}
        return {**_counts(result), "attested": False}
    try:
        envelope = run_attestation(contract, impl, opts.sandbox, opts.key)
    except (AttestError, SandboxError, ValueError) as e:
        return {"passed": False, "error": str(e), "attested": False}
    attestation.parent.mkdir(parents=True, exist_ok=True)
    attestation.write_text(json.dumps(envelope, indent=2) + "\n")
    p = statement_of(envelope)["predicate"]
    return {"passed": p["result"] == "PASSED", "checks": len(p["passedTests"]) + len(p["failedTests"]),
            "failed": p["failedTests"], "attested": True, "attestation": str(attestation)}


def _holdout(contract: Path, impl: Path, work: Path, name: str, opts: Options) -> dict:
    examples = opts.holdout / f"{name}.jsonl" if opts.holdout else None
    copy = holdout_contract(contract, work / name, examples, opts.holdout_seed, opts.holdout_scale)
    try:
        # The copy's digest differs from the build's pin, so this run is unsigned.
        result = run_worker("test", copy.resolve(), str(impl.resolve()),
                            timeout=load_manifest(copy).spec.timeout_seconds)
    except WorkerError as e:
        return {"passed": False, "error": str(e)}
    if "error" in result:
        return {"passed": False, "error": result["error"]}
    extra = sum(1 for line in examples.read_text().splitlines() if line.strip()) \
        if examples is not None and examples.is_file() else 0
    return {**_counts(result), "unseen_examples": extra, "seed": opts.holdout_seed, "scale": opts.holdout_scale}


# ── one build ────────────────────────────────────────────────────────────


def _build(agent: AgentCommand, name: str, pack_dir: Path, components: dict[str, Path],
           run_dir: Path, opts: Options, template: str, prose_only: bool = False) -> dict:
    work = run_dir / "builds" / name
    work.mkdir(parents=True)
    builder_copy(pack_dir, work / PACK_DIR, prose_only)
    (work / BUILD_DIR).mkdir()
    prompt = render_prompt(template, components, pack_dir)
    prompt_digest = "sha256:" + hashlib.sha256(prompt.encode()).hexdigest()
    opts.progress(f"build {name}: running {agent.name}")
    try:
        run = run_agent(agent, prompt, work, timeout=opts.agent_timeout)
        log, code, seconds, argv = run.log(), run.returncode, run.seconds, run.command
    except AgentError as e:
        log, code, seconds, argv = f"{e}\n", None, None, agent.argv
    (work / LOG_FILE).write_text(log)
    entry = {"name": name, "agent": agent.name, "command": argv, "exit_code": code,
             "seconds": seconds, "workdir": str(work), "log": str(work / LOG_FILE),
             "prompt_digest": prompt_digest, "prose_only": prose_only, "components": {}}
    if code != 0:
        opts.progress(f"build {name}: agent {'failed' if code is None else f'exited with {code}'}; "
                      "checking what it left")

    for comp, contract in components.items():
        impl = work / BUILD_DIR / comp
        c = entry["components"][comp] = {"impl": str(impl)}
        if not (impl / IMPL_MANIFEST_FILE).is_file():
            c.update(built=False, public={"passed": False, "error": f"no {IMPL_MANIFEST_FILE} in {impl}"})
            continue
        c["built"] = True
        builder_contract = work / PACK_DIR / contract.relative_to(pack_dir)
        try:
            c["manifest_changes"] = finish_manifest(
                impl, builder_digest=contract_digest(builder_contract), published_digest=contract_digest(contract),
                agent=agent.name, prompt_digest=prompt_digest)
        except Exception as e:
            c["public"] = {"passed": False, "error": f"{IMPL_MANIFEST_FILE}: {e}"}
            continue
        flags = read_flags(impl / FLAGS_FILE)
        c["flags"] = len(flags)
        opts.progress(f"build {name}: checking {comp}")
        c["public"] = _public(contract, impl, opts, run_dir / "attestations" / f"{comp}.{name}.json")
        if opts.holdout is not None:
            c["holdout"] = _holdout(contract, impl, run_dir / "holdout" / name, comp, opts)
    return entry


# ── the run ──────────────────────────────────────────────────────────────


def _diff_summary(report: dict, decided: dict[str, str]) -> dict:
    splits = []
    for s in report["splits"]:
        obligations = list(s["obligations"])
        # gap: no obligation covers it. weak-check: the builds pass a decided or
        # default obligation's checks but differ on inputs near them.
        if not obligations:
            verdict = "gap"
        elif any(decided.get(o) in ("decided", "default") for o in obligations):
            verdict = "weak-check"
        else:
            verdict = "review"
        splits.append({"groups": s["groups"], "inputs": s["inputs"], "share_of_ambiguity": s["share_of_ambiguity"],
                       "obligations": obligations, "verdict": verdict, "witness": s["witness"]})
    return {"members": [m["name"] for m in report["ensemble"]], "reference": report["reference"],
            "ambiguity": report["rao"]["estimate"], "interval95": report["rao"]["interval95"],
            "to_reference": report["to_reference"], "behaviours": report["behaviours"]["observed"],
            "splits": splits, "readings": report["readings"]}


def replicate(pack_dir: Path, run_dir: Path, agents: list[AgentCommand], opts: Options) -> dict:
    pack_dir = Path(pack_dir).resolve()
    run_dir = Path(run_dir).resolve()
    if not (pack_dir / PACK_MANIFEST_FILE).is_file():
        raise ReplicateError(f"{pack_dir} has no {PACK_MANIFEST_FILE}; give the pack's version directory")
    if run_dir.exists():
        raise ReplicateError(f"{run_dir} already exists")
    if opts.builds < 1:
        raise ReplicateError("--builds must be at least 1")
    if not 0 <= opts.prose_only <= opts.builds:
        raise ReplicateError("--prose-only must be between 0 and --builds")
    if not agents:
        raise ReplicateError("no agent given")
    if opts.sandbox is not None and opts.key is None:
        raise ReplicateError("attesting needs a runner key")

    checked = validate_pack(pack_dir)
    if not checked.ok:
        problems = "; ".join(f"{c.name}: {c.detail}" for c in checked.checks if not c.ok)
        raise ReplicateError(f"the pack is not valid ({problems}); run `symbola pack validate`")
    available = _component_dirs(pack_dir)
    wanted = opts.components or list(available)
    unknown = [c for c in wanted if c not in available]
    if unknown:
        raise ReplicateError(f"no component named {', '.join(unknown)}; the pack has {', '.join(available)}")
    components = {c: available[c] for c in wanted}
    if opts.reference is not None:
        missing = [c for c in components if not (Path(opts.reference) / c).exists()]
        if missing:
            raise ReplicateError(f"the reference has no {', '.join(missing)} under {opts.reference}")

    with (pack_dir / PACK_MANIFEST_FILE).open("rb") as f:
        pack_meta = tomllib.load(f).get("pack", {})
    with (pack_dir / "obligations.toml").open("rb") as f:
        status = {o["id"]: o.get("status") for o in tomllib.load(f).get("obligation", [])}

    run_dir.mkdir(parents=True)
    first_prose = opts.builds - opts.prose_only
    plan = [(i, agents[i % len(agents)]) for i in range(opts.builds)]
    names = [f"{a.name}-{i + 1}" + ("-prose" if i >= first_prose else "") for i, a in plan]

    def job(args):
        (i, agent), name = args
        prose = i >= first_prose
        template = opts.prompt or (PROSE_ONLY_PROMPT if prose else DEFAULT_PROMPT)
        return _build(agent, name, pack_dir, components, run_dir, opts, template, prose)

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with ThreadPoolExecutor(max_workers=max(1, opts.jobs)) as pool:
        builds = list(pool.map(job, zip(plan, names)))

    per_component = {}
    for comp, contract in components.items():
        passing = [b for b in builds if b["components"][comp].get("public", {}).get("passed")]
        holdout = [b for b in passing if "holdout" in b["components"][comp]]
        prose = [b for b in builds if b["prose_only"]]
        row = {"contract": str(contract), "digest": contract_digest(contract),
               "builds": len(builds), "passed": len(passing),
               "prose_only": {"builds": len(prose), "passed": sum(b in passing for b in prose)} if prose else None,
               "holdout_passed": sum(b["components"][comp]["holdout"].get("passed", False) for b in holdout)
               if holdout else None}
        members = [load_member(b["name"], Path(b["components"][comp]["impl"]), comp) for b in passing]
        if opts.reference is not None:
            members.insert(0, load_member("reference", (Path(opts.reference) / comp).resolve(), comp))
        if len(members) >= 2:
            opts.progress(f"diff {comp}: {len(members)} implementations")
            try:
                report = measure(contract, members, reference="reference" if opts.reference else None,
                                 pools=opts.pools,
                                 mutations=opts.mutations, property_cases=opts.property_cases,
                                 search=opts.search, seed=opts.seed, timeout=opts.diff_timeout)
                diff_file = run_dir / "diff" / f"{comp}.json"
                diff_file.parent.mkdir(exist_ok=True)
                diff_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
                row["diff"] = {**_diff_summary(report, status), "report": str(diff_file)}
            except WorkerError as e:
                row["diff"] = {"error": str(e)}
        else:
            row["diff"] = None
        per_component[comp] = row

    all_passed = all(r["passed"] == r["builds"] for r in per_component.values())
    holdouts_ok = all(r["holdout_passed"] in (None, r["passed"]) for r in per_component.values())
    agreed = all(r["diff"] is not None and "error" not in r["diff"] and not r["diff"]["splits"]
                 for r in per_component.values())
    report = {
        "pack": {"id": pack_meta.get("id"), "version": pack_meta.get("version"), "path": str(pack_dir),
                 "components": {c: contract_digest(d) for c, d in components.items()}},
        "startedOn": started,
        "finishedOn": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agents": {a.name: a.command for a in agents},
        "attested": opts.sandbox is not None,
        "reference": str(Path(opts.reference).resolve()) if opts.reference else None,
        "holdout": {"examples": str(Path(opts.holdout).resolve()) if opts.holdout else None,
                    "seed": opts.holdout_seed, "scale": opts.holdout_scale},
        "builds": builds,
        "components": per_component,
        "summary": {"builds": len(builds), "all_passed": all_passed, "holdouts_passed": holdouts_ok,
                    "converged": all_passed and holdouts_ok and agreed,
                    "splits": sum(len(r["diff"]["splits"]) for r in per_component.values()
                                  if r["diff"] and "splits" in r["diff"])},
    }
    (run_dir / REPORT_FILE).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report
