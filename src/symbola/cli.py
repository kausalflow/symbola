"""The `symbola` command line."""

from __future__ import annotations

import json
import re
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

import typer

from . import canary as canary_mod, keys
from .agent import AgentError, parse_agents, resolve_agent
from .changes import OVERRIDES_FILE, compare as compare_packs, conflicts as override_conflicts, load_overrides, \
    markdown as changes_markdown, summary_text as changes_summary
from .attest import AttestError, compare_runs, run_attestation, statement_of, verify_attestation
from .diff import TIERS, load_member, measure, member_name
from .extract import ExtractError, extract as run_extract
from .digest import contract_digest
from .implementation import IMPL_MANIFEST_FILE
from .manifest import ID_RE, load_manifest
from .publish import DEFAULT_SITE, PublishError, finish_login, logout as logout_site, publish as publish_pack, \
    request_state, start_login
from .questions import QuestionError, answer as answer_question, unanswered
from .pack import PACK_MANIFEST_FILE, PRODUCT_FILE, component_name, report_json, summary_line, validate_pack
from .registry import DEFAULT_REGISTRY, RegistryError, build_site, check_registry, components_of, pack_ref, previous_version, pull as pull_pack, release as release_pack, scaffold_pack, upgrade as upgrade_pack
from .replicate import Options, ReplicateError, replicate as replicate_pack
from .sandbox import SandboxError, select
from .scaffold import scaffold
from .validate import WorkerError, check_impl, mutants_report, regenerate_schema, run_worker, validate

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Trustable contracts between agents.")

OK = typer.style("✓", fg=typer.colors.GREEN, bold=True)
FAIL = typer.style("✗", fg=typer.colors.RED, bold=True)


def _line(ok: bool, name: str, detail: str = "") -> None:
    typer.echo(f"{OK if ok else FAIL} {name}" + (typer.style(f"  {detail}", dim=True) if detail and ok else ""))
    if detail and not ok:
        for row in detail.splitlines():
            typer.echo(f"    {row}")


@app.command()
def init(
    contract_id: str = typer.Argument(..., help="Contract id, like 'core/date-parse'."),
    root: Path = typer.Option(Path("contracts"), help="Directory that holds contracts."),
    author: str = typer.Option("you@example.com", help="Author recorded in the manifest."),
) -> None:
    """Scaffold a new contract that passes `validate` out of the box."""
    if not ID_RE.match(contract_id):
        raise typer.BadParameter("must look like 'namespace/name'", param_hint="CONTRACT_ID")
    try:
        target = scaffold(contract_id, root, author)
    except FileExistsError as e:
        typer.echo(f"{FAIL} {e}")
        raise typer.Exit(1)
    regenerate_schema(target)
    typer.echo(f"{OK} created {target}")
    for rel in ["symbolon.toml", "schema.py", "schema/input.json", "schema/output.json",
                "examples.jsonl", "properties.py", "reference/impl.py"]:
        typer.echo(f"    {rel}")
    typer.echo(f"\nNext: edit the files, then run `symbola validate {target}`")


@app.command(name="validate")
def validate_cmd(
    path: Path = typer.Argument(..., help="Contract directory."),
    as_json: bool = typer.Option(False, "--json", help="Print the report as JSON."),
) -> None:
    """Check that a contract is well-formed and that its spec means something."""
    report = validate(path)
    if as_json:
        typer.echo(json.dumps({
            "ok": report.ok, "alias": report.alias, "digest": report.digest,
            "checks": [asdict(c) for c in report.checks],
        }, indent=2))
    else:
        for c in report.checks:
            _line(c.ok, c.name, c.detail)
        if report.ok:
            typer.echo(f"\n{report.alias}  {report.digest}")
        else:
            typer.echo(typer.style("\ncontract is not valid", fg=typer.colors.RED))
    raise typer.Exit(0 if report.ok else 1)


@app.command()
def schema(path: Path = typer.Argument(..., help="Contract directory.")) -> None:
    """Regenerate schema/*.json from schema.py."""
    try:
        written = regenerate_schema(path)
    except WorkerError as e:
        _line(False, "schema generation failed", str(e))
        raise typer.Exit(1)
    for rel in written:
        _line(True, f"wrote {rel}")


@app.command()
def test(
    path: Path = typer.Argument(..., help="Contract directory."),
    impl: Path = typer.Argument(..., help="Implementation directory, or a single Python file."),
    as_json: bool = typer.Option(False, "--json", help="Print the result as JSON."),
) -> None:
    """Run a contract's spec against an implementation."""
    try:
        result = check_impl(path, impl)
    except WorkerError as e:
        _line(False, "spec run failed", str(e))
        raise typer.Exit(1)
    if as_json:
        typer.echo(json.dumps(result, indent=2))
        raise typer.Exit(0 if result.get("passed") else 1)
    if "error" in result:
        _line(False, "could not load implementation", result["error"])
        raise typer.Exit(1)
    for c in result["examples"] + result["properties"]:
        _line(c["ok"], c["name"], c["detail"])
    total = len(result["examples"]) + len(result["properties"])
    failed = sum(not c["ok"] for c in result["examples"] + result["properties"])
    if result["passed"]:
        typer.echo(typer.style(f"\nPASS  {total} checks", fg=typer.colors.GREEN, bold=True))
    else:
        typer.echo(typer.style(f"\nFAIL  {failed} of {total} checks failed", fg=typer.colors.RED, bold=True))
    raise typer.Exit(0 if result["passed"] else 1)


@app.command()
def keygen(
    out: Path = typer.Option(keys.DEFAULT_KEY, help="Where to write the private key; the .pub goes next to it."),
) -> None:
    """Create this runner's Ed25519 signing key."""
    try:
        path = keys.generate(out)
    except FileExistsError as e:
        _line(False, str(e))
        raise typer.Exit(1)
    public = keys.load_public(keys.public_path(path))
    _line(True, f"private key {path}")
    _line(True, f"public key  {keys.public_path(path)}")
    typer.echo(f"\nkeyid {keys.keyid(public)}")


@app.command(name="impl-init")
def impl_init(
    impl_dir: Path = typer.Argument(..., help="Implementation directory (created if missing)."),
    contract: Path = typer.Option(..., help="Contract directory this implementation targets."),
    entrypoint: str = typer.Option("impl.py", help="Python file defining the entrypoint function."),
    author: str = typer.Option("you@example.com", help="Author recorded in the manifest."),
    license: str = typer.Option("Apache-2.0", help="License of the implementation."),
    repin: bool = typer.Option(False, help="Only re-pin an existing implementation to the contract, after an upgrade."),
) -> None:
    """Write symbolon-impl.toml, pinned to the contract's current digest."""
    manifest_path = impl_dir / IMPL_MANIFEST_FILE
    digest = contract_digest(contract)
    if repin:
        if not manifest_path.is_file():
            _line(False, f"{manifest_path} does not exist; run without --repin to create it")
            raise typer.Exit(1)
        text, n = re.subn(r'(?m)^contract\s*=\s*"[^"]*"', f'contract = "{digest}"', manifest_path.read_text(), count=1)
        if not n:
            _line(False, f"{manifest_path} has no contract = \"...\" line")
            raise typer.Exit(1)
        manifest_path.write_text(text)
        _line(True, f"re-pinned {manifest_path}", f"targets {load_manifest(contract).alias} {digest[:19]}…")
        return
    if manifest_path.exists():
        _line(False, f"{manifest_path} already exists")
        raise typer.Exit(1)
    impl_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "[implementation]\n"
        f'contract = "{digest}"\n'
        f'entrypoint = "{entrypoint}"\n'
        'language = "python"\n'
        f'license = "{license}"\n'
        f'authors = ["{author}"]\n'
    )
    entry = impl_dir / entrypoint
    if not entry.exists():
        fn = load_manifest(contract).entrypoint.function
        entry.write_text(f"def {fn}(input: dict) -> dict:\n    raise NotImplementedError\n")
    _line(True, f"wrote {manifest_path}", f"targets {load_manifest(contract).alias} {digest[:19]}…")


def _summarize(statement: dict) -> None:
    p = statement["predicate"]
    s = p["symbolon"]
    cfg = {c["name"].split(":", 1)[0]: c for c in p["configuration"]}
    ok = p["result"] == "PASSED"
    total = len(p["passedTests"]) + len(p["failedTests"])
    typer.echo(f"{OK if ok else FAIL} {p['result']}  {len(p['passedTests'])}/{total} checks passed")
    for name in p["failedTests"]:
        _line(False, name, s["failures"].get(name, ""))
    typer.echo(f"  contract        {cfg['contract']['name'].split(':', 1)[1]}  sha256:{cfg['contract']['digest']['sha256'][:16]}…")
    typer.echo(f"  implementation  sha256:{statement['subject'][0]['digest']['sha256'][:16]}…")
    typer.echo(f"  environment     sha256:{cfg['environment']['digest']['sha256'][:16]}…  ({s['sandbox']['environment']['sandbox']} sandbox, network {s['sandbox']['network']})")
    r = s.get("resources", {})
    if r:
        typer.echo(f"  resources       {r.get('wall_seconds')}s wall, {r.get('cpu_seconds')}s cpu, {r.get('peak_rss_kb', 0) // 1024} MB peak")
    typer.echo(f"  evidence        {s['evidence']}")
    typer.echo(f"  runner          {s['runner']['keyid'][:23]}…")


@app.command()
def attest(
    contract: Path = typer.Argument(..., help="Contract directory."),
    impl: Path = typer.Argument(..., help="Implementation directory with symbolon-impl.toml."),
    out: Path = typer.Option(Path("attestation.json"), "-o", "--out", help="Where to write the signed attestation."),
    key: Path = typer.Option(keys.DEFAULT_KEY, help="Runner signing key."),
    sandbox: str = typer.Option("auto", help="auto, container or process."),
) -> None:
    """Run the spec against an implementation in a sandbox and write a signed attestation."""
    try:
        signing_key = keys.load_private(key)
        box = select(sandbox)
        envelope = run_attestation(contract, impl, box, signing_key)
    except (AttestError, SandboxError, FileNotFoundError, ValueError) as e:
        _line(False, "attestation failed", str(e))
        raise typer.Exit(1)
    out.write_text(json.dumps(envelope, indent=2) + "\n")
    statement = statement_of(envelope)
    _summarize(statement)
    typer.echo(f"\nwrote {out}")
    raise typer.Exit(0 if statement["predicate"]["result"] == "PASSED" else 1)


@app.command()
def verify(
    attestation: Path = typer.Argument(..., help="Attestation JSON (DSSE envelope)."),
    trust: list[Path] = typer.Option([], help="Trusted runner public key (.pub). Repeat for several."),
    contract: Path | None = typer.Option(None, help="Check the contract digest against this directory."),
    impl: Path | None = typer.Option(None, help="Check the implementation digest against this directory."),
    rerun: bool = typer.Option(False, help="Re-run the spec here and compare results (needs --contract and --impl)."),
    key: Path = typer.Option(keys.DEFAULT_KEY, help="Signing key for the rerun's own attestation."),
    sandbox: str = typer.Option("auto", help="Sandbox for --rerun: auto, container or process."),
) -> None:
    """Check an attestation's signature, trust, digests, and optionally reproduce it."""
    try:
        v = verify_attestation(json.loads(attestation.read_text()), trusted_keys=trust,
                               contract_dir=contract, impl_dir=impl)
    except (AttestError, ValueError, KeyError) as e:
        _line(False, "invalid attestation", str(e))
        raise typer.Exit(1)
    _line(True, "signature valid", v.keyid[:23] + "…")
    if v.trusted is None:
        typer.echo(typer.style("  runner trust not checked (pass --trust)", dim=True))
    else:
        _line(v.trusted, "runner is in the trust set" if v.trusted else "runner is not in the trust set")
    if contract is not None or impl is not None:
        _line(not v.problems, "digests match local copies" if not v.problems else "digests checked", "\n".join(v.problems))
    elif v.problems:
        for p in v.problems:
            _line(False, p)
    _summarize(v.statement)
    ok = v.ok
    if rerun:
        if contract is None or impl is None:
            _line(False, "--rerun needs --contract and --impl")
            raise typer.Exit(1)
        try:
            again = statement_of(run_attestation(contract, impl, select(sandbox), keys.load_private(key)))
        except (AttestError, SandboxError, FileNotFoundError, ValueError) as e:
            _line(False, "rerun failed", str(e))
            raise typer.Exit(1)
        diffs = compare_runs(v.statement, again)
        _line(not diffs, "reproduced: every check has the same outcome" if not diffs else "not reproduced", "\n".join(diffs))
        ok = ok and not diffs
    raise typer.Exit(0 if ok else 1)


def _pairs(values: list[str], what: str) -> dict[str, str]:
    out = {}
    for v in values:
        key, sep, val = v.partition("=")
        if not sep or not key:
            raise typer.BadParameter(f"{v!r}: expected NAME=VALUE", param_hint=what)
        out[key] = val
    return out


def _short(value, limit: int = 160) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _print_diff(r: dict, realistic: dict | None, top: int) -> None:
    pool = r["pool"]
    how = ", ".join(f"{v} {k}" for k, v in pool["by_how"].items())
    typer.echo(f"pool       {pool['inputs']} inputs ({how}), {pool['disagreeing']} with a disagreement")
    for m in r["ensemble"]:
        who = " · ".join(x for x in (m["model"], m["family"], m["language"]) if x) or "no [generator] recorded"
        stale = "  (built for another contract digest)" if m["pinned"] and m["pinned"] != r["digest"] else ""
        typer.echo(f"ensemble   {m['name']}  weight {m['weight']:g}  {who}{stale}")
    if r["reference"]:
        typer.echo(f"reference  {r['reference']}  (compared, not in the ensemble)")
    for pair, d in r["distances"].items():
        typer.echo(f"distance   {pair}  {d:.4f}")
    est = r["rao"]
    if est["estimate"] is None:
        typer.echo(typer.style("ambiguity  needs two builds in the ensemble", dim=True))
    else:
        lo, hi = est["interval95"]
        typer.echo(f"ambiguity  {est['estimate']:.4f}  (95% {lo:.4f}–{hi:.4f}; expected error ≥ {est['floor_on_error']:.4f})")
        if realistic and realistic["rao"]["estimate"] is not None:
            rl, rh = realistic["rao"]["interval95"]
            typer.echo(f"           {realistic['rao']['estimate']:.4f} on the realistic pool "
                       f"({realistic['pool']['inputs']} inputs; 95% {rl:.4f}–{rh:.4f})")
    b = r["behaviours"]
    typer.echo(f"behaviours {b['observed']} observed among {b['builds']} builds, Chao estimate {b['chao']:.1f}, "
               f"{b['shannon_bits']:.2f} bits")
    if b["builds"] < 5 or b["singletons"] == b["builds"]:
        typer.echo(typer.style("           too few builds for the Chao and entropy estimates to mean much", dim=True))
    if r["to_reference"]:
        for name, d in r["to_reference"].items():
            typer.echo(f"error      {name} vs {r['reference']}  {d:.4f}")

    if r["splits"]:
        typer.echo(f"\nsplits, largest first ({len(r['splits'])}):")
    for i, s in enumerate(r["splits"][:top], 1):
        share = f"{s['share_of_ambiguity']:.0%} of ambiguity, " if s["share_of_ambiguity"] is not None else ""
        groups = " | ".join(", ".join(g) for g in s["groups"])
        tiers = ", ".join(s["tiers"])
        typer.echo(f"{i}. {groups}   {share}{s['inputs']} inputs, {tiers}")
        traced = ", ".join(s["obligations"]) or "no obligation: a gap in the pack"
        typer.echo(f"   traces to  {traced}")
        typer.echo(f"   witness    {_short(s['witness']['input'])}")
        for who, out in s["witness"]["outcomes"].items():
            typer.echo(f"     {who:<10} {_short(out)}")
    if len(r["splits"]) > top:
        typer.echo(typer.style(f"   … {len(r['splits']) - top} more in the JSON report", dim=True))

    rd = r["readings"]
    if rd["points"]:
        typer.echo(f"\nreadings   {rd['points']} points recorded, {rd['shared']} by two or more builds, "
                   f"{len(rd['splits'])} chosen differently")
        for s in rd["splits"]:
            typer.echo(f"   {s['point']}: " + "; ".join(f"{n}: {c}" for n, c in s["chosen"].items()))


@app.command(name="diff")
def diff_cmd(
    contract: Path = typer.Argument(..., help="Contract directory."),
    impls: list[str] = typer.Argument(..., help="Implementations, as PATH or NAME=PATH. Two or more."),
    reference: str | None = typer.Option(None, help="Name of the original product: compared with every build, not part of the ensemble."),
    pool: list[Path] = typer.Option([], help="Extra inputs, one JSON input (or {\"input\": ...}) per line. Repeat for several."),
    realistic: Path | None = typer.Option(None, help="Inputs drawn to look like real use; reported as a separate, unbiased estimate."),
    mutations: int = typer.Option(500, help="Mutated copies of example and property inputs to add."),
    property_cases: int = typer.Option(50, help="Inputs to record from each property's generator."),
    search: int = typer.Option(300, help="Budget of extra inputs mutated from disagreements."),
    seed: int = typer.Option(0, help="Seed for the pool and the bootstrap."),
    weight: list[str] = typer.Option([], help="Ensemble weight, NAME=W. Default 1 for every build."),
    severity: list[str] = typer.Option([], help="Cost of a disagreement tier, TIER=W (crash, value, format; default 1, 1, 0.1)."),
    max_ambiguity: float | None = typer.Option(None, help="Exit 1 if the ambiguity estimate is above this."),
    top: int = typer.Option(5, help="Splits to print."),
    out: Path | None = typer.Option(None, "-o", "--out", help="Write the full report as JSON."),
    as_json: bool = typer.Option(False, "--json", help="Print the report as JSON."),
    timeout: int = typer.Option(900, help="Seconds before the run is stopped."),
) -> None:
    """Run several builds on one input pool and measure where they disagree."""
    component = component_name(Path(contract))
    named: list[tuple[str, Path]] = []
    for spec in impls:
        name, sep, path = spec.partition("=")
        p = Path(path if sep else spec)
        named.append((name if sep else member_name(p, component), p.resolve()))
    names = [n for n, _ in named]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise typer.BadParameter(f"two implementations are named {', '.join(dupes)}; use NAME=PATH", param_hint="IMPLS")
    if len(named) < 2:
        raise typer.BadParameter("give at least two implementations", param_hint="IMPLS")
    if reference is not None and reference not in names:
        raise typer.BadParameter(f"{reference!r} is not one of {', '.join(names)}", param_hint="--reference")
    weights = {k: float(v) for k, v in _pairs(weight, "--weight").items()}
    costs = {k: float(v) for k, v in _pairs(severity, "--severity").items()}
    unknown = sorted(set(weights) - set(names)) + sorted(set(costs) - set(TIERS))
    if unknown:
        raise typer.BadParameter(f"unknown {', '.join(unknown)}", param_hint="--weight/--severity")
    try:
        members = [load_member(n, p, component, weights.get(n, 1.0)) for n, p in named]
    except Exception as e:
        _line(False, "could not read an implementation's manifest or readings.toml", str(e))
        raise typer.Exit(1)

    try:
        report = measure(contract, members, reference=reference, severity=costs, pools=pool, realistic=realistic,
                         mutations=mutations, property_cases=property_cases, search=search, seed=seed,
                         timeout=timeout)
    except WorkerError as e:
        _line(False, "diff run failed", str(e))
        raise typer.Exit(1)
    real = report.get("realistic")
    if out is not None:
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    if as_json:
        typer.echo(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_diff(report, real, top)
        if out is not None:
            typer.echo(f"\nwrote {out}")
    estimate = report["rao"]["estimate"]
    if max_ambiguity is not None and estimate is not None and estimate > max_ambiguity:
        if not as_json:
            typer.echo(typer.style(f"\nambiguity {estimate:.4f} is above --max-ambiguity {max_ambiguity:g}", fg=typer.colors.RED))
        raise typer.Exit(1)


def _print_replication(r: dict, top: int) -> None:
    for b in r["builds"]:
        built = sum(c.get("built", False) for c in b["components"].values())
        took = f"{b['seconds']:.0f}s" if b["seconds"] is not None else "did not finish"
        _line(b["exit_code"] == 0, f"build {b['name']}", f"{b['agent']}, {took}, {built}/{len(b['components'])} components built")
        if b["exit_code"] != 0:
            typer.echo(f"    agent exit {b['exit_code']}, see {b['log']}")
        for comp, c in b["components"].items():
            pub = c.get("public", {})
            if not pub.get("passed"):
                _line(False, f"  {comp}", pub.get("error") or f"failed {len(pub.get('failed', []))} of {pub.get('checks')} checks: "
                      + ", ".join(pub.get("failed", [])[:5]))
            elif "holdout" in c and not c["holdout"].get("passed"):
                h = c["holdout"]
                _line(False, f"  {comp} holdout", h.get("error") or f"failed {len(h.get('failed', []))} of {h.get('checks')} checks: "
                      + ", ".join(h.get("failed", [])[:5]))
    typer.echo("")
    for comp, row in r["components"].items():
        held = f", holdout {row['holdout_passed']}/{row['passed']}" if row["holdout_passed"] is not None else ""
        if row.get("prose_only"):
            held += f", prose-only {row['prose_only']['passed']}/{row['prose_only']['builds']}"
        d = row["diff"]
        if d is None:
            measured = "not diffed: needs two passing implementations"
        elif "error" in d:
            measured = f"diff failed: {d['error']}"
        else:
            amb = f"ambiguity {d['ambiguity']:.4f}" if d["ambiguity"] is not None else "ambiguity needs two builds"
            ref = ""
            if d["to_reference"]:
                ref = ", vs reference " + ", ".join(f"{n} {v:.4f}" for n, v in d["to_reference"].items())
            measured = f"{amb}{ref}, {len(d['splits'])} split(s)"
        ok = row["passed"] == row["builds"] and (row["holdout_passed"] in (None, row["passed"]))
        _line(ok and bool(d) and "error" not in d and not d["splits"],
              f"{comp}  {row['passed']}/{row['builds']} builds passed{held}", measured)
        if d and "splits" in d:
            for i, s in enumerate(d["splits"][:top], 1):
                groups = " | ".join(", ".join(g) for g in s["groups"])
                traced = ", ".join(s["obligations"])
                what = {"gap": "no obligation covers it, a gap in the pack",
                        "weak-check": f"traces to {traced}, whose checks are too weak to tell them apart",
                        }.get(s["verdict"], f"traces to {traced}")
                typer.echo(f"    {i}. {groups}  {s['inputs']} inputs; {what}")
            if len(d["splits"]) > top:
                typer.echo(typer.style(f"    … {len(d['splits']) - top} more in {d['report']}", dim=True))
    s = r["summary"]
    typer.echo("")
    if s["converged"]:
        typer.echo(typer.style(f"converged: {s['builds']} builds pass and agree on every input tried", fg=typer.colors.GREEN, bold=True))
    else:
        why = []
        if not s["all_passed"]:
            why.append("some builds fail the public suite")
        if not s["holdouts_passed"]:
            why.append("some builds fail the holdout")
        if s["splits"]:
            why.append(f"{s['splits']} split(s) to review")
        if not why:
            why.append("too few passing builds to compare")
        typer.echo(typer.style("not converged: " + "; ".join(why), fg=typer.colors.YELLOW, bold=True))


@app.command()
def replicate(
    pack: Path = typer.Argument(..., help="Pack directory, the one with symbolon-pack.toml."),
    agent: list[str] = typer.Option([], help="Coding agent command, as NAME=COMMAND or COMMAND. Repeat for several; "
                                     "builds take turns. Default $SYMBOLON_AGENT, else Claude Code."),
    builds: int = typer.Option(2, help="How many builds to make."),
    prose_only: int = typer.Option(0, help="How many of the builds (the last ones) get the pack without examples "
                                   "and properties, to test whether the descriptions alone carry the spec."),
    component: list[str] = typer.Option([], help="Build only this component. Repeat for several. Default every one."),
    reference: Path | None = typer.Option(None, help="The original product: a directory with one implementation per component, compared with every build."),
    holdout: Path | None = typer.Option(None, help="Publisher's holdout: a directory of <component>.jsonl examples the builders never see."),
    holdout_seed: int = typer.Option(20261021, help="Property seed for the holdout run."),
    holdout_scale: int = typer.Option(5, help="Holdout runs this many times the property cases."),
    out: Path = typer.Option(Path("replication"), "-o", "--out", help="Run directory to create: builds, logs, attestations, replication.json."),
    attest_builds: bool = typer.Option(True, "--attest/--no-attest", help="Attest each build in a sandbox, or just test it."),
    key: Path = typer.Option(keys.DEFAULT_KEY, help="Runner signing key for the attestations."),
    sandbox: str = typer.Option("auto", help="auto, container or process."),
    jobs: int = typer.Option(1, help="Agents to run at once."),
    agent_timeout: int = typer.Option(3600, help="Seconds before an agent is stopped."),
    prompt: Path | None = typer.Option(None, help="Prompt template to use instead of the default; $pack, $build and $components are filled in."),
    pool: list[Path] = typer.Option([], help="diff: extra inputs, one JSON input per line, such as real use. Repeat for several."),
    mutations: int = typer.Option(500, help="diff: mutated copies of example and property inputs."),
    property_cases: int = typer.Option(50, help="diff: inputs to record from each property's generator."),
    search: int = typer.Option(300, help="diff: budget of extra inputs mutated from disagreements."),
    seed: int = typer.Option(0, help="diff: seed for the pool and the bootstrap."),
    diff_timeout: int = typer.Option(900, help="diff: seconds before a component's run is stopped."),
    max_ambiguity: float | None = typer.Option(None, help="Exit 1 if any component's ambiguity is above this."),
    top: int = typer.Option(3, help="Splits to print per component."),
    as_json: bool = typer.Option(False, "--json", help="Print the report as JSON."),
) -> None:
    """Hand a pack to outside coding agents, then test, attest and diff the builds they make."""
    try:
        agents = parse_agents(agent)
    except AgentError as e:
        raise typer.BadParameter(str(e), param_hint="--agent")
    opts = Options(builds=builds, prose_only=prose_only, components=component or None, reference=reference, holdout=holdout,
                   holdout_seed=holdout_seed, holdout_scale=holdout_scale, jobs=jobs, agent_timeout=agent_timeout,
                   prompt=prompt.read_text() if prompt else None, pools=pool, mutations=mutations,
                   property_cases=property_cases, search=search, seed=seed, diff_timeout=diff_timeout,
                   progress=(lambda msg: None) if as_json else (lambda msg: typer.echo(typer.style(msg, dim=True))))
    if attest_builds:
        try:
            opts.key = keys.load_private(key)
        except FileNotFoundError:
            _line(False, f"no runner key at {key}", "run `symbola keygen`, or pass --no-attest to test without signing")
            raise typer.Exit(1)
    try:
        if attest_builds:
            opts.sandbox = select(sandbox)
        report = replicate_pack(pack, out, agents, opts)
    except (ReplicateError, SandboxError, ValueError) as e:
        _line(False, "replication failed", str(e))
        raise typer.Exit(1)
    if as_json:
        typer.echo(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_replication(report, top)
        typer.echo(f"\nwrote {out / 'replication.json'}")
    s = report["summary"]
    too_ambiguous = max_ambiguity is not None and any(
        r["diff"] and r["diff"].get("ambiguity") is not None and r["diff"]["ambiguity"] > max_ambiguity
        for r in report["components"].values())
    raise typer.Exit(0 if s["all_passed"] and s["holdouts_passed"] and not too_ambiguous else 1)


pack_app = typer.Typer(no_args_is_help=True, help="Work with spec packs.")
app.add_typer(pack_app, name="pack")


@pack_app.command(name="validate")
def pack_validate(
    path: Path = typer.Argument(..., help="Pack directory, the one with symbolon-pack.toml."),
    as_json: bool = typer.Option(False, "--json", help="Print the report as JSON."),
) -> None:
    """Check a pack's brief, assumptions and obligations, and that every obligation is checked or open."""
    report = validate_pack(path)
    if as_json:
        typer.echo(report_json(report))
    else:
        for c in report.checks:
            _line(c.ok, c.name, c.detail)
        if report.ok:
            typer.echo(f"\n{summary_line(report.summary)}")
        else:
            typer.echo(typer.style("\npack is not valid", fg=typer.colors.RED))
    raise typer.Exit(0 if report.ok else 1)


@pack_app.command(name="init")
def pack_init(
    pack_id: str = typer.Argument(..., help="Pack id, like 'acme/invoice-desk'."),
    path: Path = typer.Option(Path("spec"), "--dir", help="Folder to create; by default spec/ next to your code."),
    author: str = typer.Option("you@example.com", help="Author recorded in the manifest and the brief."),
) -> None:
    """Scaffold a spec pack that passes `pack validate` out of the box."""
    try:
        target = scaffold_pack(pack_id, path, author)
    except (ValueError, FileExistsError) as e:
        _line(False, str(e))
        raise typer.Exit(1)
    _line(True, f"created {target}")
    for rel in ["symbolon-pack.toml", "BRIEF.md", "obligations.toml", "assumptions/replace-me.toml",
                "components/", "AGENTS.md"]:
        typer.echo(f"    {rel}")
    typer.echo(f"\nNext: replace the placeholders, then run `symbola pack validate {target}`")


@pack_app.command(name="questions")
def pack_questions(
    path: Path = typer.Argument(Path("spec"), help="Pack directory, the one with symbolon-pack.toml."),
    as_json: bool = typer.Option(False, "--json", help="Print the questions as JSON."),
) -> None:
    """List the questions in .symbolon/questions.toml that the publisher has not answered yet."""
    try:
        todo = unanswered(path)
    except QuestionError as e:
        _line(False, str(e))
        raise typer.Exit(1)
    if as_json:
        typer.echo(json.dumps([q.model_dump(exclude_defaults=True) for q in todo], indent=2, ensure_ascii=False))
        return
    for n, q in enumerate(todo, 1):
        typer.echo(f"{n}. {q.ask}  [{q.id}]")
        for c in q.choice:
            typer.echo(f"   ({c.key}) {c.label}" + ("  (recommended)" if c.key == q.recommended else ""))
        typer.echo("")
    typer.echo(f"{len(todo)} unanswered. Record each with `symbola pack answer {path} <id> <choice|default|open>`.")


@pack_app.command(name="answer")
def pack_answer(
    path: Path = typer.Argument(..., help="Pack directory, the one with symbolon-pack.toml."),
    question: str = typer.Argument(..., help="Question id from .symbolon/questions.toml."),
    pick: str = typer.Argument(..., help="A choice key (decided), 'default' (the recommended choice, "
                                         "left to the builder's pack) or 'open' (builds may differ)."),
) -> None:
    """Record the publisher's answer as an obligation and the example line that checks it."""
    try:
        o = answer_question(path, question, pick)
    except QuestionError as e:
        _line(False, str(e))
        raise typer.Exit(1)
    detail = ", ".join(o.get("checks", [])) or ("unchecked" if o.get("unchecked") else "no check")
    _line(True, f"{o['id']}: {o['status']}", f"{o['statement']} ({detail})")


site_app = typer.Typer(no_args_is_help=True, help="Build the static pack registry.")
app.add_typer(site_app, name="site")


@site_app.command(name="build")
def site_build(
    registry: Path = typer.Argument(Path("packs"), help="Folder of packs: <owner>/<name>/versions/<n>/."),
    out: Path = typer.Option(Path("site-registry"), help="Output folder; replaced on every build."),
    base_url: str = typer.Option("", help="Absolute URL the site is served from, used in llms.txt links."),
    private_out: Path | None = typer.Option(None, help="Where priced packs' tarballs go, for the store's private bucket."),
    store_url: str = typer.Option("", help="URL of the store Worker that sells priced packs."),
    files_out: Path | None = typer.Option(None, help="Put tarballs, parts, raw files and evidence here instead, for a bucket."),
    files_url: str = typer.Option("", help="Absolute URL the --files-out folder is served from."),
) -> None:
    """Write index.json, llms.txt and each pack's tarball, pack.md and files for the latest versions."""
    try:
        built = build_site(registry, out, base_url, private_out, store_url, files_out, files_url)
    except RegistryError as e:
        _line(False, str(e))
        raise typer.Exit(1)
    for b in built:
        _line(True, f"{b.id}  version {b.version}", b.digest)
    typer.echo(f"\n{len(built)} pack(s) written to {out}")


@site_app.command(name="check")
def site_check(
    registry: Path = typer.Argument(Path("packs"), help="Folder of packs: <owner>/<name>/versions/<n>/."),
) -> None:
    """What CI runs on a submission: every latest version validates and builds, and no released version changed."""
    try:
        warnings = check_registry(registry)
    except RegistryError as e:
        _line(False, str(e))
        raise typer.Exit(1)
    for w in warnings:
        typer.echo(typer.style(f"! {w}", fg=typer.colors.YELLOW))
    _line(True, "registry is ready to publish")


@app.command()
def release(
    spec: Path = typer.Argument(Path("spec"), help="Your pack folder, the one `pack init` made."),
    registry: Path = typer.Option(..., help="The packs/ folder of your clone of the registry repository."),
) -> None:
    """Freeze your pack into the registry as its next version; then open a PR."""
    try:
        r = release_pack(spec, registry)
    except (RegistryError, FileNotFoundError) as e:
        _line(False, str(e))
        raise typer.Exit(1)
    if not r.created:
        _line(True, f"{r.id} version {r.version} already has this content; nothing to release", r.digest)
        return
    _line(True, f"{r.id} version {r.version} written to {r.path}", r.digest)
    before = previous_version(r.path.parent.parent, r.path)
    if before is not None:
        typer.echo(f"  changes since version {before.name}: {changes_summary(compare_packs(before, r.path))}")
    typer.echo("\nNext: run `symbola site check` in the registry clone, then commit and open a pull request:")
    typer.echo(f"    git checkout -b release/{r.id.replace('/', '-')}-{r.version} && git add -A "
               f"&& git commit -m 'Release {r.id} version {r.version}' && gh pr create --fill")


SITE_OPTION = typer.Option(DEFAULT_SITE, "--site", envvar="SYMBOLON_SITE", help="The registry website.")


@app.command()
def login(
    site: str = SITE_OPTION,
    name: str = typer.Option("symbola CLI", help="A name for this token, shown on your account page."),
) -> None:
    """Sign in to the registry website with GitHub, so `symbola publish` can upload."""
    site = site.rstrip("/")
    try:
        client_id, code = start_login(site)
        typer.echo(f"Open {code.verification_uri} and enter the code {typer.style(code.user_code, bold=True)}")
        typer.echo("Waiting for you to approve it on GitHub…")
        got = finish_login(site, client_id, code, name)
    except PublishError as e:
        _line(False, str(e))
        raise typer.Exit(1)
    _line(True, f"signed in to {site} as {got['login']}", "namespaces: " + ", ".join(got.get("namespaces", [])))


@app.command()
def logout(site: str = SITE_OPTION) -> None:
    """Forget the token `symbola login` saved. Revoke it on your account page to disable it everywhere."""
    site = site.rstrip("/")
    _line(True, f"signed out of {site}" if logout_site(site) else f"was not signed in to {site}")


@app.command()
def publish(
    spec: Path = typer.Argument(Path("spec"), help="Your pack folder, the one `pack init` made."),
    site: str = SITE_OPTION,
    wait: bool = typer.Option(True, help="Follow the request until its pull request is open (or it fails)."),
    evidence: Path | None = typer.Option(None, help="Attestations from a test build of this pack (a folder of *.json), "
                                                    "listed on the pack's page. Strongly recommended."),
) -> None:
    """Validate a pack and publish it to the registry website as its next version."""
    site = site.rstrip("/")
    if evidence is None:
        typer.echo("  No --evidence: the pack's page will say no build has passed yet. "
                   "A test build first is strongly recommended (`symbola replicate`).")
    try:
        got = publish_pack(spec, site, evidence)
    except PublishError as e:
        _line(False, str(e))
        raise typer.Exit(1)
    req = got["request"]
    _line(True, f"uploaded {req['pack']}", got["url"])
    if not wait:
        return
    seen = None
    for _ in range(120):
        try:
            req = request_state(site, req["id"])
        except PublishError as e:
            _line(False, str(e))
            raise typer.Exit(1)
        if req["state"] != seen:
            seen = req["state"]
            if req["state"] == "failed":
                _line(False, "the registry refused the pack", req["message"])
                raise typer.Exit(1)
            if req["state"] in ("review", "merging", "merged", "live"):
                _line(True, req["message"], req.get("pr", ""))
                return
            typer.echo(f"  {req['message']}")
        time.sleep(5)
    typer.echo(f"Still working; follow it at {got['url']}")


@app.command()
def pull(
    pack_id: str = typer.Argument(..., help="Pack id, like 'acme/invoice-desk', or its page link. Only the latest version is served."),
    registry: str = typer.Option(DEFAULT_REGISTRY,
                                 envvar="SYMBOLON_REGISTRY", help="Registry URL or local folder."),
    dest: Path | None = typer.Option(None, help="Where to unpack; defaults to ./<name>."),
    token: str | None = typer.Option(None, envvar="SYMBOLON_LICENSE", help="License token for a paid pack."),
    digest: str | None = typer.Option(None, help="Pull the older version with this pack digest, to re-check evidence that names it."),
) -> None:
    """Download a pack, check its sha256 and digest against the registry, and unpack it."""
    pack_id, page_registry = pack_ref(pack_id)
    registry = page_registry or registry
    target = dest or Path(pack_id.split("/")[-1])
    try:
        got = pull_pack(pack_id, registry, target, token, digest)
    except RegistryError as e:
        _line(False, str(e))
        raise typer.Exit(1)
    _line(True, "tarball sha256 matches the registry", got.sha256)
    _line(True, "pack digest matches the registry", got.digest)
    typer.echo("  (the publisher is not verified yet: packs get GitHub provenance when they move to GitHub Releases)")
    _line(True, f"{got.id} version {got.version} unpacked into {target}")
    comps = components_of(target)
    if (target / PRODUCT_FILE).is_file():
        typer.echo(f"\nThis is a product pack: build the product {target / PRODUCT_FILE} describes, "
                   "with the components as its core.")
    typer.echo(f"\nNext: build from {target / 'AGENTS.md'}, one folder per component, running its checks as you go:")
    if comps:
        c, n = comps[0], comps[0].split("/")[1]
        typer.echo(f"  symbola impl-init impl/{n} --contract {target / c}\n  symbola test {target / c} impl/{n}")
        typer.echo(f"Components: {', '.join(x.split('/')[1] for x in comps)}")


@app.command()
def changes(
    old: Path = typer.Argument(..., help="The earlier pack folder, such as versions/1."),
    new: Path = typer.Argument(..., help="The later pack folder, such as versions/2."),
    out: Path | None = typer.Option(None, "-o", "--out", help="Write the report as Markdown."),
    as_json: bool = typer.Option(False, "--json", help="Print the changes as JSON."),
) -> None:
    """List what changed between two versions of a pack: decisions, assumptions, components, documents."""
    for p in (old, new):
        if not (p / PACK_MANIFEST_FILE).is_file():
            raise typer.BadParameter(f"{p} has no {PACK_MANIFEST_FILE}")
    found = compare_packs(old, new)
    if as_json:
        typer.echo(json.dumps(found, indent=2, ensure_ascii=False))
        return
    text = changes_markdown(found, f"What changed from {old} to {new}")
    if out is not None:
        out.write_text(text)
        _line(True, changes_summary(found), f"wrote {out}")
    else:
        typer.echo(text, nl=False)


UPGRADE_STEPS = """## How to take this version in

You are upgrading a build of this pack. The build may differ from the pack on
purpose: those departures are listed in `{overrides}`, one per decision id. Keep
them unless a step below says to ask.

1. Change only what this version changes. Leave every other part of the build alone,
   including the user's own code and styling.
2. For each changed or added decision, make the build do what it now says, unless
   the build overrides that decision. Where this version changes a decision the build
   overrides, ask the user whether to keep the override, then update `{overrides}`.
3. For each changed component, re-run its checks against the new contract and fix
   what fails, then re-pin it to the new contract so attest accepts it.
{commands}4. Check every flow in PRODUCT.md that this version touches.
5. When everything passes, replace `{spec}` with `{dest}`, run `symbola attest` again
   for the changed components, and record what you did in NOTES.md.

If you edited `{spec}` yourself, those edits show up above as changes too; record
them as overrides instead of editing the pack.
"""


@app.command()
def upgrade(
    spec: Path = typer.Argument(Path("spec"), help="The pack folder your build came from (the one `symbola pull` made)."),
    dest: Path | None = typer.Option(None, help="Where to unpack the latest version; defaults to <spec>.new."),
    registry: str = typer.Option(DEFAULT_REGISTRY, envvar="SYMBOLON_REGISTRY", help="Registry URL or local folder."),
    impl: Path = typer.Option(Path("impl"), help="Folder holding one implementation folder per component."),
    overrides: Path = typer.Option(Path(OVERRIDES_FILE), help="Your build's departures from the pack, by decision id."),
    report: Path = typer.Option(Path("UPGRADE.md"), help="Where to write the upgrade notes for your agent."),
    token: str | None = typer.Option(None, envvar="SYMBOLON_LICENSE", help="License token for a paid pack."),
) -> None:
    """Fetch the latest version of a pack you built, and write what changed for your agent."""
    target = dest or spec.with_name(spec.name + ".new")
    try:
        mine = load_overrides(overrides)
        up = upgrade_pack(spec, registry, target, token)
    except (RegistryError, ValueError) as e:
        _line(False, str(e))
        raise typer.Exit(1)
    if up.changes is None:
        _line(True, f"{up.id} is up to date (version {up.to_version})", up.digest)
        return
    found = up.changes
    _line(True, f"{up.id} version {up.to_version} unpacked into {target}", up.digest)
    commands = ""
    for c in found["components"]["changed"]:
        folder, contract = impl / c["name"], target / c["to"]
        note = "" if folder.is_dir() else f"   # no {folder} here: use your folder for {c['name']}"
        commands += (f"       symbola test {contract} {folder}{note}\n"
                     f"       symbola impl-init {folder} --contract {contract} --repin\n")
    for c in found["components"]["added"]:
        folder, contract = impl / c["name"], target / c["path"]
        commands += (f"       symbola impl-init {folder} --contract {contract}   # new component\n"
                     f"       symbola test {contract} {folder}\n")
    if commands:
        commands = "   Commands:\n\n" + commands + "\n"
    text = (changes_markdown(found, f"Upgrade {up.id} from version {up.from_version} to {up.to_version}", mine)
            + "\n" + UPGRADE_STEPS.format(overrides=overrides, spec=spec, dest=target, commands=commands))
    report.write_text(text)
    _line(True, changes_summary(found), f"wrote {report}")
    clash = override_conflicts(found, mine)
    if clash:
        typer.echo(typer.style(f"! this version changes decisions your build overrides: {', '.join(clash)}",
                               fg=typer.colors.YELLOW))
    typer.echo(f"\nNext: ask your agent to follow {report}.")


@app.command()
def extract(
    source: Path = typer.Argument(..., help="The product's source directory. It is read, never changed."),
    pack_id: str = typer.Option(..., "--pack", help="Pack id to draft, like 'kausalflow/lightkone'."),
    root: Path = typer.Option(Path("packs"), help="Directory that holds packs; the draft goes in <root>/<pack>/."),
    version: int = typer.Option(1, min=1, help="Pack version to draft."),
    agent: str | None = typer.Option(None, help="Coding agent command; defaults to $SYMBOLON_AGENT, then Claude Code."),
    hint: str = typer.Option("", help="Guidance for the agent, such as which parts of the product to cover."),
    rounds: int = typer.Option(2, min=1, help="Agent runs at most: the draft, then fixes for what fails."),
    timeout: int = typer.Option(3600, help="Seconds each agent run may take."),
    oracle: bool = typer.Option(True, help="Require the original product to pass each component through an adapter."),
) -> None:
    """Have a coding agent draft a spec pack from an existing product, then check the draft."""
    try:
        command = resolve_agent(agent)
    except AgentError as e:
        _line(False, "no agent", str(e))
        raise typer.Exit(1)
    typer.echo(f"drafting {pack_id} from {source} with {command.name} (up to {rounds} rounds)")

    def show(n, rnd):
        typer.echo(f"\nround {n}: agent {'finished' if rnd.run.ok else 'failed'} after {rnd.run.seconds:.0f}s")
        for c in rnd.checks:
            _line(c.ok, c.name, c.detail)

    try:
        result = run_extract(source, pack_id, agent=command, root=root, version=version, hint=hint,
                             rounds=rounds, timeout=timeout, oracle=oracle, on_round=show)
    except (ExtractError, AgentError) as e:
        _line(False, "extract failed", str(e))
        raise typer.Exit(1)
    typer.echo("")
    if result.ok:
        typer.echo(f"{OK} draft pack {result.pack_dir}")
        if result.pack_report:
            typer.echo(f"    {summary_line(result.pack_report.summary)}")
        typer.echo(f"\nNext: answer {result.product_dir / 'REVIEW.md'}, settle the default and open "
                   "obligations, then hand the pack to builders.")
    else:
        typer.echo(typer.style(f"draft is not valid yet: {result.pack_dir}", fg=typer.colors.RED))
        typer.echo(f"Agent logs are in {result.product_dir / '.symbolon'}. Fix the draft by hand, or remove "
                   "it and run extract again with more --rounds.")
    raise typer.Exit(0 if result.ok else 1)


@app.command()
def mutants(
    path: Path = typer.Argument(..., help="Contract directory."),
    mutants_dir: Path | None = typer.Option(None, "--mutants", help="Mutants folder; defaults to the contract's mutants/."),
    as_json: bool = typer.Option(False, "--json", help="Print the report as JSON."),
) -> None:
    """Show which checks kill which mutants, and the contract's kill rate."""
    try:
        report = mutants_report(path, mutants_dir)
    except (WorkerError, FileNotFoundError) as e:
        _line(False, "mutant run failed", str(e))
        raise typer.Exit(1)
    s = report["summary"]
    ok = not s["undocumented_survivors"] and not s["problems"]
    if as_json:
        typer.echo(json.dumps(report, indent=2))
        raise typer.Exit(0 if ok else 1)
    for m in report["mutants"]:
        if m["problem"]:
            _line(False, m["file"], m["problem"])
        elif m["killed"]:
            shown = ", ".join(m["killed_by"][:4]) + (f" +{len(m['killed_by']) - 4}" if len(m["killed_by"]) > 4 else "")
            _line(True, f"{m['file']}  {m['concern']}", f"killed by {len(m['killed_by'])}: {shown}")
        else:
            _line(m["survives"] is not None, f"{m['file']}  {m['concern']}",
                  f"survives: {m['survives']}" if m["survives"] else "survives: no check rejects it")
    kills = {c: 0 for c in report["checks"]}
    for m in report["mutants"]:
        for c in m["killed_by"]:
            kills[c] = kills.get(c, 0) + 1
    idle = [c for c, n in kills.items() if n == 0]
    if idle:
        typer.echo(typer.style(f"\nchecks that kill no mutant ({len(idle)}): " + ", ".join(idle), dim=True))
    typer.echo(f"\n{s['killed']}/{s['total']} mutants killed"
               + (f", {s['documented_survivors']} documented survivors" if s["documented_survivors"] else "")
               + (f", {len(s['undocumented_survivors'])} undocumented survivors" if s["undocumented_survivors"] else ""))
    raise typer.Exit(0 if ok else 1)


canary_app = typer.Typer(no_args_is_help=True, help="Plant and check canaries that catch builds fitted to the examples.")
app.add_typer(canary_app, name="canary")


@canary_app.command(name="plant")
def canary_plant(
    path: Path = typer.Argument(..., help="Contract directory."),
    out: Path = typer.Argument(..., help="Where to write the builder's copy (must not exist)."),
    seed: int = typer.Option(0, help="Chooses which example becomes the canary."),
    record: Path | None = typer.Option(None, help="Private record of the canary; defaults to <out>.canary.json."),
) -> None:
    """Copy a contract for a builder, with one example changed to contradict the spec."""
    try:
        rec = canary_mod.plant(path, out, seed=seed, record=record)
    except (WorkerError, FileExistsError, ValueError) as e:
        _line(False, "could not plant a canary", str(e))
        raise typer.Exit(1)
    _line(True, f"builder copy {out}", "without reference/ and mutants/")
    _line(True, f"canary at examples.jsonl line {rec['line']}", f"{rec['original']} -> {rec['canary']}")
    _line(True, f"private record {rec['record']}")
    typer.echo("\nGive the copy to the builder and keep the record. Then run `symbola canary check`.")


@canary_app.command(name="check")
def canary_check(
    record: Path = typer.Argument(..., help="The canary record written by `canary plant`."),
    impl: Path = typer.Argument(..., help="The finished build: an implementation directory or Python file."),
    contract: Path | None = typer.Option(None, help="Contract directory; defaults to the planted copy."),
    flags: Path | None = typer.Option(None, help=f"Flags file; defaults to {canary_mod.FLAGS_FILE} next to the build."),
    as_json: bool = typer.Option(False, "--json", help="Print the verdict as JSON."),
) -> None:
    """Tell whether a build followed the spec or was fitted to the planted example."""
    try:
        v = canary_mod.check(record, impl, contract_dir=contract, flags_file=flags)
    except (WorkerError, FileNotFoundError, KeyError) as e:
        _line(False, "canary check failed", str(e))
        raise typer.Exit(1)
    if as_json:
        typer.echo(json.dumps({"outcome": v.outcome, "flagged": v.flagged, "got": v.got, "flags": v.flags}, indent=2))
    else:
        _line(v.ok, f"{v.outcome}: {v.describe()}", "" if v.ok else f"got {v.got}")
        typer.echo(typer.style(f"  {len(v.flags)} flag(s) raised by the builder", dim=True))
    raise typer.Exit(0 if v.ok else 1)


@app.command()
def flag(
    ref: str = typer.Argument(..., help="What looks wrong: an obligation id, 'example:<line>', or a property name."),
    reason: str = typer.Argument(..., help="Why it contradicts the spec, and the reading you chose."),
    directory: Path = typer.Option(Path("."), "--dir", help=f"Build directory that holds {canary_mod.FLAGS_FILE}."),
) -> None:
    """Report a part of the spec that contradicts itself, instead of coding around it."""
    path = canary_mod.add_flag(ref, reason, directory)
    _line(True, f"flagged {ref}", str(path))


@app.command()
def digest(path: Path = typer.Argument(..., help="Contract directory.")) -> None:
    """Print a contract's content digest."""
    typer.echo(contract_digest(path))


if __name__ == "__main__":
    app()
