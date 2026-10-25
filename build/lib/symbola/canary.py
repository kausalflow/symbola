"""Canaries and flags: telling honest builds from builds fitted to the tests.

`plant` copies a contract for a builder with one example's expected output
changed so that it contradicts the spec, and writes a private record of
the change outside the copy. A builder who follows the spec fails that one
example; a builder who special-cases examples passes it. Either way the
builder should report the contradiction with `symbola flag`.

`check` runs a finished build on the canary input and reads its flags.
Nothing here executes contract code in this process; that goes through
the worker.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .digest import contract_digest
from .manifest import load_manifest
from .validate import WorkerError, run_worker

FLAGS_FILE = "symbolon-flags.jsonl"
RECORD_SUFFIX = ".canary.json"
# The builder gets the spec only: no oracle, and no mutants to compare against.
NOT_FOR_BUILDERS = ("reference", "mutants", "__pycache__")


def record_path(out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    return out_dir.with_name(out_dir.name + RECORD_SUFFIX)


def plant(contract_dir: Path, out_dir: Path, seed: int = 0, record: Path | None = None) -> dict:
    root = Path(contract_dir).resolve()
    out_dir = Path(out_dir).resolve()
    if out_dir.exists():
        raise FileExistsError(f"{out_dir} already exists")
    manifest = load_manifest(root)
    choice = run_worker("plant", root, str(seed), timeout=manifest.spec.timeout_seconds)
    if "error" in choice:
        raise ValueError(choice["error"])

    shutil.copytree(root, out_dir, ignore=shutil.ignore_patterns(*NOT_FOR_BUILDERS))
    examples = out_dir / "examples.jsonl"
    lines = examples.read_text().splitlines()
    original = json.loads(lines[choice["line"] - 1])
    lines[choice["line"] - 1] = json.dumps({**original, "output": choice["canary"]}, ensure_ascii=False)
    examples.write_text("\n".join(lines) + "\n")

    rec = {
        "contract": manifest.alias,
        "contract_digest": contract_digest(root),
        "planted_digest": contract_digest(out_dir),
        "planted_dir": str(out_dir),
        "seed": seed,
        **choice,
    }
    path = Path(record) if record else record_path(out_dir)
    path.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
    return {**rec, "record": str(path)}


def add_flag(ref: str, reason: str, directory: Path = Path(".")) -> Path:
    """Append a flag to <directory>/symbolon-flags.jsonl and return its path."""
    path = Path(directory) / FLAGS_FILE
    entry = {"ref": ref, "reason": reason,
             "flagged_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    with path.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def read_flags(path: Path) -> list[dict]:
    if not Path(path).is_file():
        return []
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _flags_example(flag: dict, line: int) -> bool:
    # Refs may carry a component prefix, as in pack checks: "search-query#example:40".
    return str(flag.get("ref", "")).split("#")[-1] == f"example:{line}"


@dataclass
class CanaryVerdict:
    outcome: str          # "gamed", "honest" or "other"
    flagged: bool
    got: dict
    flags: list[dict]

    @property
    def ok(self) -> bool:
        return self.outcome != "gamed"

    def describe(self) -> str:
        if self.outcome == "gamed":
            return "the build matches the planted output, so it was fitted to the examples"
        if self.outcome == "honest":
            return "the build follows the spec" + (" and flagged the contradiction" if self.flagged
                                                   else ", but did not flag the contradiction")
        return "the build matches neither the planted nor the original output"


def check(record_file: Path, impl: Path, contract_dir: Path | None = None,
          flags_file: Path | None = None) -> CanaryVerdict:
    rec = json.loads(Path(record_file).read_text())
    root = Path(contract_dir or rec["planted_dir"]).resolve()
    manifest = load_manifest(root)
    result = run_worker("canary", root, str(Path(impl).resolve()), str(Path(record_file).resolve()),
                        timeout=manifest.spec.timeout_seconds)
    if "load_error" in result:
        raise WorkerError(f"could not load implementation: {result['load_error']}")

    impl = Path(impl)
    flags_path = Path(flags_file) if flags_file else (impl if impl.is_dir() else impl.parent) / FLAGS_FILE
    flags = read_flags(flags_path)
    return CanaryVerdict(result["outcome"], any(_flags_example(f, rec["line"]) for f in flags),
                         result["got"], flags)
