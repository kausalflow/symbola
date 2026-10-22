"""Orchestration that runs in the CLI process.

Only the manifest and digest are handled here. Anything that executes
contract or implementation code goes through `run_worker`.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from .digest import contract_digest
from .manifest import MANIFEST_FILE, Manifest, load_manifest
from .spec import CheckResult

REQUIRED_FILES = [MANIFEST_FILE, "schema.py", "examples.jsonl", "properties.py"]


class WorkerError(Exception):
    pass


def run_worker(mode: str, contract_dir: Path, *extra: str, timeout: int = 120) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "result.json"
        cmd = [sys.executable, "-I", "-m", "symbolon.worker", mode, str(contract_dir), str(out), *extra]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=tmp)
        except subprocess.TimeoutExpired:
            raise WorkerError(f"timed out after {timeout}s") from None
        if proc.returncode != 0 or not out.exists():
            tail = (proc.stderr or proc.stdout).strip().splitlines()[-5:]
            raise WorkerError("\n".join(tail) or f"worker exited with {proc.returncode}")
        return json.loads(out.read_text())


def _manifest_error(e: Exception) -> str:
    if isinstance(e, ValidationError):
        return "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()
        )
    return f"{type(e).__name__}: {e}"


@dataclass
class Report:
    checks: list[CheckResult] = field(default_factory=list)
    digest: str | None = None
    alias: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)


def validate(contract_dir: Path) -> Report:
    root = Path(contract_dir).resolve()
    report = Report()

    missing = [f for f in REQUIRED_FILES if not (root / f).is_file()]
    if missing:
        report.checks.append(CheckResult("required files present", False, "missing: " + ", ".join(missing)))
        return report
    report.checks.append(CheckResult("required files present", True))

    try:
        manifest: Manifest = load_manifest(root)
    except Exception as e:
        report.checks.append(CheckResult("symbolon.toml is valid", False, _manifest_error(e)))
        return report
    report.alias = manifest.alias
    report.checks.append(CheckResult("symbolon.toml is valid", True, manifest.alias))

    try:
        result = run_worker("check", root, timeout=manifest.spec.timeout_seconds * (1 + _mutant_count(root / "mutants")))
    except WorkerError as e:
        report.checks.append(CheckResult("contract code runs", False, str(e)))
        return report
    report.checks += [CheckResult(**c) for c in result["checks"]]

    if report.ok:
        report.digest = contract_digest(root)
    return report


def _mutant_count(mutants_dir: Path) -> int:
    return len(list(mutants_dir.glob("*.py"))) if mutants_dir.is_dir() else 0


def mutants_report(contract_dir: Path, mutants_dir: Path | None = None) -> dict:
    """Which checks kill which mutants. Defaults to the contract's own mutants/."""
    root = Path(contract_dir).resolve()
    manifest = load_manifest(root)
    mdir = Path(mutants_dir).resolve() if mutants_dir else root / "mutants"
    if not mdir.is_dir():
        raise WorkerError(f"no mutants folder at {mdir}")
    extra = [str(mdir)] if mutants_dir else []
    return run_worker("mutants", root, *extra, timeout=manifest.spec.timeout_seconds * (1 + _mutant_count(mdir)))


def regenerate_schema(contract_dir: Path) -> list[str]:
    root = Path(contract_dir).resolve()
    manifest = load_manifest(root)
    return run_worker("schema", root, timeout=manifest.spec.timeout_seconds)["written"]


def check_impl(contract_dir: Path, impl_path: Path) -> dict:
    """Run the spec against an implementation file, or a directory with symbolon-impl.toml."""
    root = Path(contract_dir).resolve()
    manifest = load_manifest(root)
    impl_path = Path(impl_path).resolve()
    return run_worker("test", root, str(impl_path), timeout=manifest.spec.timeout_seconds)
