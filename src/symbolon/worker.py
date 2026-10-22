"""Subprocess entry point for everything that executes contract code.

Usage: python -I -m symbolon.worker <mode> <contract_dir> <out.json> [impl] [--deps DIR]

Modes:
  check   structural and behavioral checks for `validate`
  test    run the spec against an implementation
  schema  regenerate schema/input.json and schema/output.json
  mutants run the spec against each mutant; optional [mutants_dir]
  plant   choose a canary example (see mutation.py); optional [seed]
  canary  run an implementation on a canary record's input and compare

The result is written as JSON to <out.json>, so anything the contract prints
cannot corrupt it. `symbolon attest` runs this process inside a sandbox
(see sandbox.py).
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

from .manifest import load_manifest
from .mutation import MUTANTS_DIR, canary_outcome, plant_canary, run_mutants, summarize
from .spec import (
    CheckResult,
    LoadedContract,
    SpecError,
    constant_stub,
    raising_stub,
    run_spec,
)

SCHEMA_FILES = {"Input": "schema/input.json", "Output": "schema/output.json"}


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def generated_schemas(contract: LoadedContract) -> dict[str, str]:
    return {
        rel: canonical_json(getattr(contract, name).model_json_schema())
        for name, rel in SCHEMA_FILES.items()
    }


def write_schemas(contract: LoadedContract) -> list[str]:
    written = []
    for rel, text in generated_schemas(contract).items():
        path = contract.root / rel
        path.parent.mkdir(exist_ok=True)
        path.write_text(text)
        written.append(rel)
    return written


def _failures(result) -> str:
    bad = [c for c in result.examples + result.properties if not c.ok]
    return "\n".join(f"{c.name}: {c.detail}" for c in bad)


def check(root: Path) -> list[CheckResult]:
    """Steps 2-7 of `validate`. Stops at the first structural failure."""
    checks: list[CheckResult] = []

    def fail(name: str, detail: str) -> list[CheckResult]:
        checks.append(CheckResult(name, False, detail))
        return checks

    manifest = load_manifest(root)

    name = "schema.py defines Input and Output"
    try:
        contract = LoadedContract.load(root, manifest)
    except Exception as e:
        return fail(name, f"{type(e).__name__}: {e}")
    checks.append(CheckResult(name, True))

    name = "schema/*.json matches schema.py"
    stale = []
    for rel, text in generated_schemas(contract).items():
        path = root / rel
        if not path.exists():
            stale.append(f"{rel} is missing")
        elif json.loads(path.read_text()) != json.loads(text):
            stale.append(f"{rel} differs from schema.py")
    if stale:
        return fail(name, "; ".join(stale) + ". Run `symbolon schema` to regenerate.")
    checks.append(CheckResult(name, True))

    name = "examples.jsonl is valid"
    try:
        examples = contract.examples()
    except SpecError as e:
        return fail(name, str(e))
    problems = []
    for ex in examples:
        try:
            contract.Input.model_validate(ex["input"])
            if "output" in ex:
                contract.Output.model_validate(ex["output"])
            elif not isinstance(ex["raises"], str):
                problems.append(f"line {ex['_line']}: 'raises' must be an exception class name")
        except Exception as e:
            problems.append(f"line {ex['_line']}: {e}")
    outputs = [canonical_json(ex["output"]) for ex in examples if "output" in ex]
    if len(set(outputs)) < 2:
        problems.append("need at least two examples with different outputs")
    if problems:
        return fail(name, "\n".join(problems))
    checks.append(CheckResult(name, True, f"{len(examples)} example" + ("s" if len(examples) != 1 else "")))

    name = "properties.py collects"
    try:
        props = contract.properties()
    except Exception as e:
        return fail(name, f"{type(e).__name__}: {e}")
    if not props:
        return fail(name, "define at least one test_* property taking `impl`")
    checks.append(CheckResult(name, True, f"{len(props)} propert" + ("ies" if len(props) != 1 else "y")))

    name = "spec passes against reference implementation"
    ref = root / "reference" / "impl.py"
    if ref.exists():
        try:
            result = run_spec(contract, contract.load_impl(ref, "symbolon_reference"))
        except Exception as e:
            return fail(name, f"{type(e).__name__}: {e}")
        if not result.passed:
            return fail(name, _failures(result))
        checks.append(CheckResult(name, True))
    else:
        checks.append(CheckResult(name, True, "skipped: no reference/impl.py (optional)"))

    # Vacuity: the properties alone must reject trivial implementations.
    # Examples are excluded on purpose; they catch these stubs too easily.
    first_output = next(ex["output"] for ex in examples if "output" in ex)
    stubs = [
        ("vacuity: properties reject an implementation that always raises", raising_stub),
        ("vacuity: properties reject an implementation that returns a constant", constant_stub(first_output)),
    ]
    for name, stub in stubs:
        result = run_spec(contract, stub, properties_only=True)
        if result.passed:
            return fail(name, "every property passed against a trivial stub; the spec does not constrain behavior")
        checks.append(CheckResult(name, True))

    # Mutants: plausible wrong implementations the whole spec must reject.
    if (root / MUTANTS_DIR).is_dir():
        name = "mutants: spec rejects every mutant"
        try:
            summary = summarize(run_mutants(contract, root / MUTANTS_DIR))
        except Exception as e:
            return fail(name, f"{type(e).__name__}: {e}")
        problems = [f"{f}: {why}" for f, why in summary["problems"].items()]
        problems += [f"{f} survives: no check rejects it. Add a check, or explain with SURVIVES = \"...\""
                     for f in summary["undocumented_survivors"]]
        problems += [f"{f} is marked SURVIVES but is killed; remove the marker" for f in summary["stale_markers"]]
        if problems:
            return fail(name, "\n".join(problems))
        detail = f"{summary['killed']}/{summary['total']} killed"
        if summary["documented_survivors"]:
            detail += f", {summary['documented_survivors']} documented survivor" + ("s" if summary["documented_survivors"] != 1 else "")
        checks.append(CheckResult(name, True, detail))

    return checks


def _resources(started: float) -> dict:
    import resource
    me = resource.getrusage(resource.RUSAGE_SELF)
    # Children: a `language = "command"` implementation runs as a child process.
    kids = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "wall_seconds": round(time.monotonic() - started, 3),
        "cpu_seconds": round(me.ru_utime + me.ru_stime + kids.ru_utime + kids.ru_stime, 3),
        "peak_rss_kb": max(me.ru_maxrss, kids.ru_maxrss),
    }


def main(argv: list[str]) -> int:
    started = time.monotonic()
    args = list(argv)
    deps = None
    if "--deps" in args:
        i = args.index("--deps")
        deps = args[i + 1]
        del args[i:i + 2]
    if deps:
        # Implementation dependencies, installed by the sandbox before this run.
        sys.path.insert(0, deps)
    mode, root, out = args[0], Path(args[1]).resolve(), Path(args[2])
    if mode == "check":
        payload = {"checks": [asdict(c) for c in check(root)]}
    elif mode == "test":
        contract = LoadedContract.load(root, load_manifest(root))
        try:
            fn = contract.load_any(Path(args[3]))
        except Exception as e:
            payload = {"error": f"{type(e).__name__}: {e}"}
        else:
            try:
                payload = run_spec(contract, fn).to_dict()
            finally:
                if hasattr(fn, "close"):
                    fn.close()
        payload["resources"] = _resources(started)
    elif mode == "mutants":
        contract = LoadedContract.load(root, load_manifest(root))
        mutants_dir = Path(args[3]).resolve() if len(args) > 3 else root / MUTANTS_DIR
        results = run_mutants(contract, mutants_dir)
        payload = {"mutants": [{**asdict(r), "killed": r.killed} for r in results],
                   "checks": [f"example:{ex['_line']}" for ex in contract.examples()]
                             + [n for n, _ in contract.properties()],
                   "summary": summarize(results)}
    elif mode == "plant":
        contract = LoadedContract.load(root, load_manifest(root))
        try:
            payload = plant_canary(contract, int(args[3]) if len(args) > 3 else 0)
        except ValueError as e:
            payload = {"error": str(e)}
    elif mode == "canary":
        contract = LoadedContract.load(root, load_manifest(root))
        try:
            fn = contract.load_any(Path(args[3]))
        except Exception as e:
            payload = {"load_error": f"{type(e).__name__}: {e}"}
        else:
            try:
                payload = canary_outcome(contract, fn, json.loads(Path(args[4]).read_text()))
            finally:
                if hasattr(fn, "close"):
                    fn.close()
    elif mode == "schema":
        contract = LoadedContract.load(root, load_manifest(root))
        payload = {"written": write_schemas(contract)}
    else:
        raise SystemExit(f"unknown mode {mode!r}")
    out.write_text(json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
