"""The `symbolon` command line."""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from pathlib import Path

import typer

from . import canary as canary_mod, keys
from .attest import AttestError, compare_runs, run_attestation, statement_of, verify_attestation
from .diff import TIERS, analyse, load_member, member_name
from .digest import contract_digest
from .implementation import IMPL_MANIFEST_FILE
from .manifest import ID_RE, load_manifest
from .pack import component_name, report_json, summary_line, validate_pack
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
    typer.echo(f"\nNext: edit the files, then run `symbolon validate {target}`")


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
) -> None:
    """Write symbolon-impl.toml, pinned to the contract's current digest."""
    manifest_path = impl_dir / IMPL_MANIFEST_FILE
    if manifest_path.exists():
        _line(False, f"{manifest_path} already exists")
        raise typer.Exit(1)
    digest = contract_digest(contract)
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

    def run(config: dict) -> list[dict]:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "diff.json"
            cfg.write_text(json.dumps({"impls": [[n, str(p)] for n, p in named], "seed": seed, **config}))
            result = run_worker("diff", Path(contract).resolve(), str(cfg), timeout=timeout)
        if "error" in result:
            raise WorkerError(result["error"])
        return result

    tol = load_manifest(contract).spec.float_rel_tol
    try:
        result = run({"mutations": mutations, "property_cases": property_cases, "search": search,
                      "pools": [str(p.resolve()) for p in pool]})
        report = analyse(result["cases"], members, contract, reference=reference, severity=costs, rel_tol=tol,
                         seed=seed, witnesses=result["witnesses"]).report
        real = None
        if realistic is not None:
            real_cases = run({"examples": False, "pools": [str(realistic.resolve())], "witnesses": 0})["cases"]
            real = analyse(real_cases, members, contract, reference=reference, severity=costs,
                           rel_tol=tol, seed=seed).report
            report["realistic"] = {k: real[k] for k in ("pool", "distances", "rao", "to_reference")}
    except WorkerError as e:
        _line(False, "diff run failed", str(e))
        raise typer.Exit(1)
    report = {"digest": contract_digest(contract), **report}
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
    typer.echo("\nGive the copy to the builder and keep the record. Then run `symbolon canary check`.")


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
