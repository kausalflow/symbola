"""The `symbolon` command line."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer

from . import keys
from .attest import AttestError, compare_runs, run_attestation, statement_of, verify_attestation
from .digest import contract_digest
from .implementation import IMPL_MANIFEST_FILE
from .manifest import ID_RE, load_manifest
from .sandbox import SandboxError, select
from .scaffold import scaffold
from .validate import WorkerError, check_impl, regenerate_schema, validate

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


@app.command()
def digest(path: Path = typer.Argument(..., help="Contract directory.")) -> None:
    """Print a contract's content digest."""
    typer.echo(contract_digest(path))


if __name__ == "__main__":
    app()
