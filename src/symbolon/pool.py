"""Input pools for `symbolon diff`, and running every implementation on them.

This executes contract and implementation code, so like spec.py it is only
imported inside the worker subprocess.

A pool is a list of inputs the contract's Input accepts, each with an origin:
the example line or property it came from (`example:12`, `test_name`), or
the pool file it was read from (`pool:cases.jsonl`). Mutated inputs keep the
origin of the input they were mutated from, which is how a disagreement is
traced back to the obligations whose checks exercise that example or
property (design v0.5 4.4, paper section 6.2).
"""

from __future__ import annotations

import copy
import dataclasses
import json
import random
from pathlib import Path
from typing import Any, Callable

from .spec import LoadedContract, load_examples, run_properties

# Leaves that tend to split readings: separators, braces and quotes,
# whitespace outside ASCII, case-folding and collation traps.
NASTY = ["", " ", "  ", "\t", "\n", "-", " - ", "{", "}", "\\", "\"", ",", ";", ":", "/", ".", "_",
         "é", "É", "ß", "İ", "ı", "Σ", "ς", "ø", "李", "🙂", " ", " ", "　", "﻿",
         "́", "A", "z", "0", "12", "-1", "1e3", "@", "%", "&", "#", "~", "'", "(", ")", "  x  "]


@dataclasses.dataclass
class Case:
    input: Any
    origin: str
    how: str  # example | property | mutation | search | pool


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _accepts(contract: LoadedContract, value: Any) -> bool:
    try:
        contract.Input.model_validate(value)
        return True
    except Exception:
        return False


class _Recorder:
    """Stands in for an implementation while properties run, to collect their inputs."""

    def __init__(self, fn: Callable):
        self.fn = fn
        self.name = ""
        self.seen: list[tuple[str, Any]] = []

    def __call__(self, data: dict) -> dict:
        self.seen.append((self.name, copy.deepcopy(data)))
        return self.fn(data)


def property_inputs(contract: LoadedContract, fn: Callable, max_examples: int, seed: int) -> list[Case]:
    """Every input the properties generate, recorded while they run against fn."""
    spec = contract.manifest.spec.model_copy(update={"max_examples": max_examples, "seed": seed})
    manifest = contract.manifest.model_copy(update={"spec": spec})
    recording = dataclasses.replace(contract, manifest=manifest)
    recorder = _Recorder(fn)
    impl = recording.bind(recorder)
    for name, prop in contract.properties():
        recorder.name = name
        run_properties(recording, impl, [(name, prop)])
    return [Case(x, name, "property") for name, x in recorder.seen]


def _leaves(value: Any, path: tuple = ()):
    if isinstance(value, (str, int, float, bool)) or value is None:
        yield path
    elif isinstance(value, list):
        if not value:
            yield path
        for i, x in enumerate(value):
            yield from _leaves(x, path + (i,))
    elif isinstance(value, dict):
        for k, x in value.items():
            yield from _leaves(x, path + (k,))


def _get(value: Any, path: tuple) -> Any:
    for p in path:
        value = value[p]
    return value


def _set(value: Any, path: tuple, new: Any) -> Any:
    if not path:
        return new
    _get(value, path[:-1])[path[-1]] = new
    return value


def _mutate_leaf(rng: random.Random, leaf: Any) -> Any:
    if isinstance(leaf, bool):
        return not leaf
    if isinstance(leaf, int):
        return rng.choice([0, -1, 1, leaf - 1, leaf + 1, leaf * 10, 2 ** 31])
    if isinstance(leaf, float):
        return rng.choice([0.0, -leaf, leaf / 3, leaf * 1e6])
    if isinstance(leaf, str):
        i = rng.randint(0, len(leaf))
        op = rng.random()
        if op < 0.45:
            return leaf[:i] + rng.choice(NASTY) + leaf[i:]
        if op < 0.6:
            return leaf[:i] + leaf[i + rng.randint(1, 4):]
        if op < 0.7:
            return leaf.upper()
        if op < 0.8:
            return leaf + " " + leaf
        return rng.choice(NASTY)
    return leaf


def mutate(rng: random.Random, value: Any) -> Any:
    """One to three edits: a changed leaf, or a list item dropped, repeated or swapped."""
    value = copy.deepcopy(value)
    for _ in range(rng.randint(1, 3)):
        lists = [p for p in _lists(value) if _get(value, p)]
        if lists and rng.random() < 0.25:
            seq = _get(value, rng.choice(lists))
            i = rng.randrange(len(seq))
            op = rng.random()
            if op < 0.4:
                del seq[i]
            elif op < 0.8:
                seq.insert(i, copy.deepcopy(seq[i]))
            elif len(seq) > 1:
                j = rng.randrange(len(seq))
                seq[i], seq[j] = seq[j], seq[i]
            continue
        paths = [p for p in _leaves(value) if not isinstance(_get(value, p), list)]
        if not paths:
            continue
        p = rng.choice(paths)
        value = _set(value, p, _mutate_leaf(rng, _get(value, p)))
    return value


def _lists(value: Any, path: tuple = ()):
    if isinstance(value, list):
        yield path
        for i, x in enumerate(value):
            yield from _lists(x, path + (i,))
    elif isinstance(value, dict):
        for k, x in value.items():
            yield from _lists(x, path + (k,))


def read_pool(path: Path) -> list[Case]:
    """A JSONL file of inputs, each line an input object or {"input": ...}."""
    cases = []
    for line in Path(path).read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict) and set(value) >= {"input"} and set(value) <= {"input", "output", "raises", "note"}:
            value = value["input"]
        cases.append(Case(value, f"pool:{Path(path).name}", "pool"))
    return cases


def outcome(contract: LoadedContract, fn: Callable, value: Any) -> dict:
    """What one implementation does with one input, in a form two runs can compare.

    {"output": ...} for a valid output, {"raises": "ValueError"} for a raised
    error, {"crash": "..."} for an output that breaks the schema or a process
    that died.
    """
    try:
        got = fn(copy.deepcopy(value))
    except Exception as e:
        if isinstance(e, RuntimeError) and str(e).startswith("implementation "):
            return {"crash": str(e)[:200]}
        return {"raises": type(e).__name__}
    try:
        return {"output": contract.Output.model_validate(got).model_dump(mode="json")}
    except Exception as e:
        return {"crash": f"output does not match schema: {str(e)[:200]}"}


def partition(outcomes: dict[str, dict]) -> tuple:
    """Which implementations gave the same outcome, as sorted groups of names."""
    groups: dict[str, list[str]] = {}
    for name, o in outcomes.items():
        groups.setdefault(canonical(o), []).append(name)
    return tuple(sorted(tuple(g) for g in groups.values()))


def _smaller(value: Any):
    """Candidates one step smaller than value: a list item removed, a string shortened."""
    for path in _lists(value):
        seq = _get(value, path)
        for i in reversed(range(len(seq))):
            v = copy.deepcopy(value)
            del _get(v, path)[i]
            yield v
    for path in _leaves(value):
        leaf = _get(value, path)
        if isinstance(leaf, str) and leaf:
            for new in ("", leaf[: len(leaf) // 2], leaf[len(leaf) // 2:], leaf[:-1], leaf[1:]):
                if new != leaf:
                    yield _set(copy.deepcopy(value), path, new)


def shrink(contract: LoadedContract, impls: dict[str, Callable], value: Any, budget: int = 400) -> tuple[Any, dict]:
    """Greedily make a disagreeing input smaller while the builds split the same way."""
    names = list(impls)
    target = partition({n: outcome(contract, impls[n], value) for n in names})
    best, best_outcomes = value, None
    improved = True
    while improved and budget > 0:
        improved = False
        for cand in _smaller(best):
            budget -= 1
            if budget <= 0:
                break
            if not _accepts(contract, cand):
                continue
            outs = {n: outcome(contract, impls[n], cand) for n in names}
            if partition(outs) == target:
                best, best_outcomes, improved = cand, outs, True
                break
    if best_outcomes is None:
        best_outcomes = {n: outcome(contract, impls[n], best) for n in names}
    return best, best_outcomes


def run_diff(contract: LoadedContract, impls: dict[str, Callable], config: dict) -> dict:
    """Build the pool, run every implementation on it, and search near disagreements.

    Returns {"cases": [{"input", "origin", "how", "outcomes": {name: outcome}}]}.
    Statistics are computed in the CLI process by diff.py.
    """
    rng = random.Random(config.get("seed", 0))
    names = list(impls)
    base: list[Case] = []
    if config.get("examples", True):
        for ex in load_examples(contract.root / "examples.jsonl"):
            base.append(Case(ex["input"], f"example:{ex['_line']}", "example"))
    if config.get("property_cases", 0) > 0:
        base += property_inputs(contract, impls[names[0]], config["property_cases"], config.get("seed", 0))
    seeds = [c for c in base if _accepts(contract, c.input)]
    pool = list(seeds)
    for _ in range(config.get("mutations", 0)):
        if not seeds:
            break
        parent = rng.choice(seeds)
        pool.append(Case(mutate(rng, parent.input), parent.origin, "mutation"))
    for path in config.get("pools", []):
        pool += read_pool(Path(path))

    seen: set[str] = set()
    cases: list[dict] = []

    def evaluate(batch: list[Case]) -> list[dict]:
        found = []
        for c in batch:
            key = canonical(c.input)
            if key in seen or not _accepts(contract, c.input):
                continue
            seen.add(key)
            row = {"input": c.input, "origin": c.origin, "how": c.how,
                   "outcomes": {n: outcome(contract, impls[n], c.input) for n in names}}
            cases.append(row)
            if len({canonical(o) for o in row["outcomes"].values()}) > 1:
                found.append(row)
        return found

    frontier = evaluate(pool)
    # Search: inputs near a disagreement are likely to find more of the same
    # split, and the smallest of them makes the clearest question.
    budget = config.get("search", 0)
    for _ in range(config.get("search_rounds", 2)):
        if not frontier or budget <= 0:
            break
        batch = []
        for row in frontier[:max(1, budget // 10)]:
            for _ in range(10):
                batch.append(Case(mutate(rng, row["input"]), row["origin"], "search"))
        budget -= len(batch)
        frontier = evaluate(batch)

    # Witnesses: the smallest input for each way the builds split, per origin,
    # shrunk further. They are kept out of the pool so the estimates are not
    # tilted towards disagreement.
    smallest: dict[tuple, dict] = {}
    for row in cases:
        key = (partition(row["outcomes"]), row["origin"])
        if len(key[0]) > 1 and (key not in smallest or len(canonical(row["input"])) < len(canonical(smallest[key]["input"]))):
            smallest[key] = row
    witnesses = []
    for row in list(smallest.values())[: config.get("witnesses", 50)]:
        value, outs = shrink(contract, impls, row["input"], config.get("shrink", 400))
        witnesses.append({"input": value, "origin": row["origin"], "outcomes": outs})
    return {"cases": cases, "witnesses": witnesses}
