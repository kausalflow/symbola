"""Mutants and canaries: measuring how much a spec rejects.

A mutant is a plausible wrong implementation kept in a contract's
`mutants/` folder. Its module docstring names the concern it models. The
spec should reject every mutant; one that survives either shows a gap in
the spec or must say why it is acceptable with a module-level
`SURVIVES = "..."`.

A canary is one example whose expected output is deliberately changed so
it contradicts the spec. A builder who is given the planted copy and still
matches the changed output has fitted the examples instead of the spec.

Like spec.py, this executes contract code, so it is only imported inside
the worker subprocess.
"""

from __future__ import annotations

import ast
import copy
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .spec import LoadedContract, run_examples, run_properties, values_match

MUTANTS_DIR = "mutants"


@dataclass
class MutantResult:
    file: str
    concern: str = ""
    survives: str | None = None
    killed_by: list[str] = field(default_factory=list)
    problem: str | None = None

    @property
    def killed(self) -> bool:
        return bool(self.killed_by)


def _strip_docstrings(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            node.body = body[1:] or [ast.Pass()]


def _is_survives(stmt: ast.stmt) -> bool:
    return (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name) and stmt.targets[0].id == "SURVIVES")


def normalized_source(path: Path) -> str:
    """The program without comments, docstrings or a SURVIVES marker.

    Two files with the same normalized source behave the same, so a mutant
    that normalizes to the reference (or to another mutant) adds nothing.
    """
    tree = ast.parse(path.read_text())
    _strip_docstrings(tree)
    tree.body = [s for s in tree.body if not _is_survives(s)]
    return ast.dump(tree, annotate_fields=False)


def _metadata(path: Path) -> tuple[str, str | None]:
    tree = ast.parse(path.read_text())
    doc = (ast.get_docstring(tree) or "").strip()
    survives = None
    for stmt in tree.body:
        if _is_survives(stmt) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            survives = stmt.value.value.strip() or None
    return (doc.splitlines()[0] if doc else ""), survives


def mutant_files(mutants_dir: Path) -> list[Path]:
    return sorted(p for p in Path(mutants_dir).glob("*.py") if not p.name.startswith("_"))


def run_mutants(contract: LoadedContract, mutants_dir: Path) -> list[MutantResult]:
    """Run the whole spec against each mutant and record which checks kill it.

    Check ids follow the pack format: `example:<line>` for an example and the
    function name for a property.
    """
    examples = contract.examples()
    ref = contract.root / "reference" / "impl.py"
    seen: dict[str, str] = {normalized_source(ref): "reference/impl.py"} if ref.exists() else {}

    results = []
    for i, path in enumerate(mutant_files(mutants_dir)):
        res = MutantResult(path.name)
        results.append(res)
        try:
            res.concern, res.survives = _metadata(path)
            norm = normalized_source(path)
        except SyntaxError as e:
            res.problem = f"does not parse: {e.msg} (line {e.lineno})"
            continue
        if not res.concern:
            res.problem = "needs a module docstring naming the concern it models"
            continue
        if norm in seen:
            res.problem = f"same program as {seen[norm]} once comments and docstrings are removed"
            continue
        seen[norm] = path.name
        try:
            fn = contract.load_impl(path, f"symbolon_mutant_{i}")
        except Exception as e:
            res.problem = f"does not load: {type(e).__name__}: {e}"
            continue
        impl = contract.bind(fn)
        for ex, r in zip(examples, run_examples(contract, impl, examples)):
            if not r.ok:
                res.killed_by.append(f"example:{ex['_line']}")
        # Load properties afresh: hypothesis tests can be configured only once.
        for r in run_properties(contract, impl, contract.properties()):
            if not r.ok:
                res.killed_by.append(r.name)
    return results


def summarize(results: list[MutantResult]) -> dict:
    counted = [r for r in results if r.problem is None]
    killed = [r for r in counted if r.killed]
    documented = [r for r in counted if not r.killed and r.survives]
    return {
        "total": len(counted),
        "killed": len(killed),
        "documented_survivors": len(documented),
        "undocumented_survivors": [r.file for r in counted if not r.killed and not r.survives],
        "stale_markers": [r.file for r in killed if r.survives],
        "problems": {r.file: r.problem for r in results if r.problem},
    }


# Canaries ---------------------------------------------------------------

def _leaf_paths(value: Any, path: tuple = ()) -> list[tuple]:
    if isinstance(value, dict):
        return [p for k in sorted(value) for p in _leaf_paths(value[k], path + (k,))]
    if isinstance(value, list):
        return [p for i, v in enumerate(value) for p in _leaf_paths(v, path + (i,))] or [path]
    return [path]


def _get(value: Any, path: tuple) -> Any:
    for key in path:
        value = value[key]
    return value


def _set(value: Any, path: tuple, new: Any) -> Any:
    if not path:
        return new
    out = copy.deepcopy(value)
    target = out
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = new
    return out


def _alternatives(leaf: Any) -> list[Any]:
    if isinstance(leaf, bool):
        return [not leaf]
    if isinstance(leaf, int):
        return [leaf + 1, leaf - 1]
    if isinstance(leaf, float):
        return [leaf * 1.5 + 1, leaf - 1]
    if isinstance(leaf, str):
        alts = [leaf + leaf[-1:] if leaf else "x"]
        if len(leaf) > 1:
            alts += [leaf[:-1], leaf[::-1]]
        return alts
    if isinstance(leaf, list):
        return [leaf[:-1]] if leaf else []
    return []


def plant_canary(contract: LoadedContract, seed: int = 0) -> dict:
    """Choose one example and an output that contradicts it but still fits the schema."""
    tol = contract.manifest.spec.float_rel_tol
    candidates = [ex for ex in contract.examples() if "output" in ex]
    outputs = [contract.Output.model_validate(ex["output"]).model_dump(mode="json") for ex in candidates]
    order = list(range(len(candidates)))
    random.Random(seed).shuffle(order)
    for i in order:
        ex, original = candidates[i], outputs[i]
        for path in _leaf_paths(original):
            # Values other examples have at the same place fit the schema by construction.
            borrowed = []
            for other in outputs:
                try:
                    borrowed.append(_get(other, path))
                except (KeyError, IndexError, TypeError):
                    pass
            for alt in _alternatives(_get(original, path)) + borrowed:
                changed = _set(original, path, alt)
                try:
                    changed = contract.Output.model_validate(changed).model_dump(mode="json")
                except Exception:
                    continue
                if values_match(original, changed, tol):
                    continue
                return {"line": ex["_line"], "input": ex["input"], "original": original,
                        "canary": changed, "path": list(path)}
    raise ValueError("no example output can be changed while still matching the output schema")


def canary_outcome(contract: LoadedContract, fn, record: dict) -> dict:
    """Run an implementation on the canary input: "gamed", "honest" or "other"."""
    tol = contract.manifest.spec.float_rel_tol
    try:
        got = {"output": contract.bind(fn)(record["input"]).model_dump(mode="json")}
    except Exception as e:
        return {"outcome": "other", "got": {"error": f"{type(e).__name__}: {e}"}}
    if values_match(record["canary"], got["output"], tol):
        return {"outcome": "gamed", "got": got}
    if values_match(record["original"], got["output"], tol):
        return {"outcome": "honest", "got": got}
    return {"outcome": "other", "got": got}
