"""The `symbolon` command line."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer

from .digest import contract_digest
from .manifest import ID_RE
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
    impl: Path = typer.Argument(..., help="Implementation file (Python)."),
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
def digest(path: Path = typer.Argument(..., help="Contract directory.")) -> None:
    """Print a contract's content digest."""
    typer.echo(contract_digest(path))


if __name__ == "__main__":
    app()
