"""`symbolon diff`: how much a contract leaves undecided, measured on builds.

Passing a spec shows a build agrees with the spec on the cases the spec
samples. Two passing builds can still behave differently, and every such
difference is a point the spec leaves open whether or not anyone meant it
to (design v0.5 5.3). This module turns the outcomes of several builds on
one input pool into the measures of the kit paper (sections 4 and 6.2):

- pairwise distances: the share of inputs on which two builds disagree,
  weighted by severity (crash, value, format);
- the Rao ambiguity: the expected distance between two builds drawn from
  the declared ensemble, with a bootstrap interval over inputs;
- behaviour classes, the Chao estimate of classes not yet seen, and the
  Chao-Shen estimate of their entropy;
- splits: groups of disagreements with the same partition of builds, ranked
  by their share of the ambiguity, each with its smallest witness input, so
  the first question to settle is the one that removes the most;
- an ambiguity map: which obligations the disagreeing inputs trace to.

A reference (the original product, when there is one) is compared with
every build but is not part of the ensemble, so the estimate stays
reference-free and the distance to the reference is a separate number.

Nothing here executes contract or implementation code: the outcomes come
from the worker (pool.py).
"""

from __future__ import annotations

import json
import math
import random
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .implementation import IMPL_MANIFEST_FILE, load_impl_manifest
from .pack import OBLIGATIONS_FILE, PACK_MANIFEST_FILE, Obligations
from .spec import values_match

TIERS = ("crash", "value", "format")
DEFAULT_SEVERITY = {"crash": 1.0, "value": 1.0, "format": 0.1}
READINGS_FILE = "readings.toml"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _loose(value: Any) -> Any:
    """The value with case, spacing and list order ignored."""
    if isinstance(value, str):
        return " ".join(value.split()).casefold()
    if isinstance(value, list):
        return sorted((_loose(v) for v in value), key=canonical)
    if isinstance(value, dict):
        return {k: _loose(v) for k, v in value.items()}
    return value


def tier(a: dict, b: dict, rel_tol: float = 1e-9) -> str | None:
    """How badly two outcomes of one input disagree, or None if they agree."""
    if "output" in a and "output" in b:
        if values_match(a["output"], b["output"], rel_tol):
            return None
        return "format" if values_match(_loose(a["output"]), _loose(b["output"]), rel_tol) else "value"
    if "raises" in a and "raises" in b:
        return None if a["raises"] == b["raises"] else "value"
    if "crash" in a and "crash" in b:
        return None
    if "crash" in a or "crash" in b:
        return "crash"
    return "value"


# ── ensemble ─────────────────────────────────────────────────────────────


class Reading(BaseModel):
    model_config = ConfigDict(extra="forbid")

    point: str = Field(min_length=1)
    considered: list[str] = Field(min_length=1)
    chosen: str = Field(min_length=1)
    obligation: str | None = None
    component: str | None = None


class Readings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reading: list[Reading] = []


@dataclass
class Member:
    name: str
    path: Path
    weight: float = 1.0
    model: str | None = None
    family: str | None = None
    language: str | None = None
    pinned: str | None = None  # contract digest in symbolon-impl.toml
    readings: list[Reading] = field(default_factory=list)

    def describe(self) -> dict:
        return {"name": self.name, "path": str(self.path), "weight": self.weight,
                "model": self.model, "family": self.family, "language": self.language,
                "pinned": self.pinned, "readings": len(self.readings)}


def member_name(path: Path, component: str) -> str:
    """rebuilds/go-1/search-query -> go-1; oracle/search-query -> oracle; go-1/ -> go-1."""
    path = Path(path).resolve()
    stem = path.stem if path.is_file() else path.name
    return path.parent.name if stem in (component, "impl") else stem


def load_readings(path: Path, component: str) -> list[Reading]:
    """readings.toml in the implementation directory, or in the build root above it."""
    path = Path(path).resolve()
    here = path if path.is_dir() else path.parent
    for d in (here, here.parent):
        f = d / READINGS_FILE
        if f.is_file():
            with f.open("rb") as fh:
                readings = Readings.model_validate(tomllib.load(fh)).reading
            return [r for r in readings if r.component in (None, component)]
    return []


def load_member(name: str, path: Path, component: str, weight: float = 1.0) -> Member:
    m = Member(name=name, path=Path(path), weight=weight)
    if m.path.is_dir() and (m.path / IMPL_MANIFEST_FILE).is_file():
        manifest = load_impl_manifest(m.path)
        m.pinned = manifest.implementation.contract
        if manifest.generator:
            m.model = manifest.generator.model
            m.family = manifest.generator.family
            m.language = manifest.generator.language
        if not m.language:
            m.language = "python" if manifest.implementation.language == "python" else None
    elif m.path.suffix == ".py":
        m.language = "python"
    m.readings = load_readings(m.path, component)
    return m


def compare_readings(members: list[Member]) -> dict:
    """Points that two or more builds recorded, and where their chosen readings differ."""
    by_point: dict[str, dict[str, Reading]] = defaultdict(dict)
    for m in members:
        for r in m.readings:
            by_point[r.obligation or " ".join(r.point.lower().split())][m.name] = r
    splits, shared = [], 0
    for key, rs in sorted(by_point.items()):
        if len(rs) < 2:
            continue
        shared += 1
        chosen = Counter(" ".join(r.chosen.lower().split()) for r in rs.values())
        if len(chosen) > 1:
            splits.append({"point": next(iter(rs.values())).point, "obligation": next(iter(rs.values())).obligation,
                           "chosen": {n: r.chosen for n, r in rs.items()}})
    return {"points": len(by_point), "shared": shared, "splits": splits}


# ── estimators ───────────────────────────────────────────────────────────


def rao(distances: dict[tuple[str, str], float], weights: dict[str, float]) -> float | None:
    """Weighted mean distance over ordered pairs of distinct members (paper eqn. 13)."""
    names = list(weights)
    num = den = 0.0
    for a, b in combinations(names, 2):
        w = weights[a] * weights[b]
        num += 2 * w * distances[a, b]
        den += 2 * w
    return num / den if den else None


def chao1(counts: list[int]) -> float:
    """Bias-corrected Chao estimate of the number of behaviours (paper eqn. 14)."""
    n = sum(counts)
    f1 = sum(c == 1 for c in counts)
    f2 = sum(c == 2 for c in counts)
    if n == 0:
        return 0.0
    return len(counts) + (n - 1) / n * f1 * (f1 - 1) / (2 * (f2 + 1))


def chao_shen_bits(counts: list[int]) -> float:
    """Shannon entropy of behaviours, corrected for unseen ones (Chao and Shen 2003)."""
    n = sum(counts)
    if n == 0:
        return 0.0
    f1 = sum(c == 1 for c in counts)
    if f1 == n:
        f1 = n - 1
    coverage = 1 - f1 / n
    h = 0.0
    for c in counts:
        p = coverage * c / n
        h -= p * math.log(p) / (1 - (1 - p) ** n)
    return h / math.log(2)


# ── report ───────────────────────────────────────────────────────────────


def _obligation_index(contract_dir: Path) -> tuple[str, dict[str, list[tuple[str, str]]]]:
    """Component name, and check ref -> [(obligation id, status)] from the enclosing pack."""
    contract_dir = Path(contract_dir).resolve()
    component = contract_dir.parent.name
    for d in list(contract_dir.parents)[:5]:
        if (d / PACK_MANIFEST_FILE).is_file() and (d / OBLIGATIONS_FILE).is_file():
            with (d / OBLIGATIONS_FILE).open("rb") as f:
                obligations = Obligations.model_validate(tomllib.load(f)).obligation
            index: dict[str, list[tuple[str, str]]] = defaultdict(list)
            for o in obligations:
                for ref in o.checks:
                    index[ref].append((o.id, o.status))
            return component, index
    return component, {}


def _refs(origin: str, component: str) -> str | None:
    if origin.startswith("pool:"):
        return None
    return f"{component}#{origin}"


@dataclass
class DiffResult:
    report: dict
    rao: float | None


def _partition(outcomes: dict[str, dict], names: list[str]) -> tuple:
    groups: dict[str, list[str]] = defaultdict(list)
    for name in names:
        groups[canonical(outcomes[name])].append(name)
    return tuple(sorted(tuple(g) for g in groups.values()))


def analyse(cases: list[dict], members: list[Member], contract_dir: Path, *, reference: str | None = None,
            severity: dict[str, float] | None = None, rel_tol: float = 1e-9, seed: int = 0,
            bootstrap: int = 200, witnesses: list[dict] | None = None) -> DiffResult:
    severity = {**DEFAULT_SEVERITY, **(severity or {})}
    names = [m.name for m in members]
    ensemble = [m for m in members if m.name != reference]
    weights = {m.name: m.weight for m in ensemble}
    pairs = list(combinations(names, 2))
    n = len(cases)

    # Per input: the tier of every pair, and its distance.
    per_input: list[dict[tuple[str, str], float]] = []
    tiers: Counter = Counter()
    for c in cases:
        row = {}
        for a, b in pairs:
            t = tier(c["outcomes"][a], c["outcomes"][b], rel_tol)
            row[a, b] = row[b, a] = severity[t] if t else 0.0
            if t:
                tiers[t] += 1
        per_input.append(row)

    def mean_distances(rows: list[dict]) -> dict[tuple[str, str], float]:
        out = {}
        for a, b in pairs:
            d = sum(r[a, b] for r in rows) / len(rows) if rows else 0.0
            out[a, b] = out[b, a] = d
        return out

    distances = mean_distances(per_input)
    estimate = rao(distances, weights) if len(ensemble) >= 2 else None
    interval = None
    if estimate is not None and n:
        rng = random.Random(seed)
        draws = sorted(rao(mean_distances([per_input[rng.randrange(n)] for _ in range(n)]), weights)
                       for _ in range(bootstrap))
        interval = [draws[int(0.025 * (bootstrap - 1))], draws[int(0.975 * (bootstrap - 1))]]

    # Behaviour classes among ensemble members: identical outcomes on every input.
    signature = {m.name: tuple(canonical(c["outcomes"][m.name]) for c in cases) for m in ensemble}
    classes: dict[tuple, list[str]] = defaultdict(list)
    for name, sig in signature.items():
        classes[sig].append(name)
    counts = [len(v) for v in classes.values()]

    # Splits: disagreements grouped by how they partition the builds.
    component, index = _obligation_index(contract_dir)
    w2 = sum(2 * weights[a] * weights[b] for a, b in combinations(weights, 2))
    splits: dict[tuple, dict] = {}
    traced: dict[str, dict] = {}
    untraced = 0
    for c, row in zip(cases, per_input):
        if not any(row[p] for p in pairs):
            continue
        part = _partition(c["outcomes"], names)
        ref = _refs(c["origin"], component)
        hits = index.get(ref, []) if ref else []
        # A split is one way the builds divide, about one thing: the
        # obligations its inputs trace to, or their origin when untraced.
        about = tuple(sorted(oid for oid, _ in hits)) or (c["origin"],)
        key = (part, about)
        s = splits.setdefault(key, {"groups": [list(g) for g in part], "inputs": 0, "contribution": 0.0,
                                    "tiers": Counter(), "origins": Counter(), "obligations": Counter(),
                                    "witness": None, "origin_set": set()})
        s["origin_set"].add(c["origin"])
        s["inputs"] += 1
        if w2:
            s["contribution"] += sum(2 * weights[a] * weights[b] * row[a, b]
                                     for a, b in combinations(weights, 2)) / (w2 * n)
        for a, b in pairs:
            t = tier(c["outcomes"][a], c["outcomes"][b], rel_tol)
            if t:
                s["tiers"][t] += 1
        s["origins"][c["origin"]] += 1
        for oid, status in hits:
            s["obligations"][oid] += 1
            t = traced.setdefault(oid, {"status": status, "inputs": 0})
            t["inputs"] += 1
        if not hits:
            untraced += 1
        if s["witness"] is None or len(canonical(c["input"])) < len(canonical(s["witness"]["input"])):
            s["witness"] = c

    # Shrunk witnesses from the worker replace a split's witness when smaller.
    for w in witnesses or []:
        part = _partition(w["outcomes"], names)
        for (p, _), s in splits.items():
            if p == part and w["origin"] in s["origin_set"] and \
                    len(canonical(w["input"])) < len(canonical(s["witness"]["input"])):
                s["witness"] = w

    ranked = sorted(splits.values(), key=lambda s: (-s["contribution"], -s["inputs"]))
    split_list = []
    for s in ranked:
        split_list.append({
            "groups": s["groups"], "inputs": s["inputs"],
            "share_of_ambiguity": (s["contribution"] / estimate) if estimate else None,
            "tiers": dict(s["tiers"]), "origins": dict(s["origins"].most_common(5)),
            "obligations": dict(s["obligations"].most_common(5)),
            "witness": {"input": s["witness"]["input"], "origin": s["witness"]["origin"],
                        "outcomes": {", ".join(g): s["witness"]["outcomes"][g[0]] for g in s["groups"]}},
        })

    to_reference = None
    if reference:
        to_reference = {m.name: distances[m.name, reference] for m in ensemble}

    report = {
        "contract": str(Path(contract_dir)),
        "pool": {"inputs": n, "by_how": dict(Counter(c["how"] for c in cases)),
                 "disagreeing": sum(1 for row in per_input if any(row[p] for p in pairs))},
        "severity": severity,
        "ensemble": [m.describe() for m in ensemble],
        "reference": reference,
        "distances": {f"{a} | {b}": distances[a, b] for a, b in pairs},
        "tiers": dict(tiers),
        "rao": {"estimate": estimate, "interval95": interval, "floor_on_error": estimate / 2 if estimate is not None else None},
        "behaviours": {"builds": len(ensemble), "observed": len(classes), "singletons": sum(c == 1 for c in counts),
                       "doubletons": sum(c == 2 for c in counts), "chao": chao1(counts),
                       "shannon_bits": chao_shen_bits(counts),
                       "classes": sorted(classes.values())},
        "to_reference": to_reference,
        "splits": split_list,
        "ambiguity_map": {"obligations": dict(sorted(traced.items(), key=lambda kv: -kv[1]["inputs"])),
                          "untraced": untraced},
        "readings": compare_readings(ensemble),
    }
    return DiffResult(report, estimate)
