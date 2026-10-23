"""Spec packs: a product's purpose, assumptions and obligations, plus component contracts.

A pack is minimal by design (design v0.5, section 4): it holds the decisions an
AI builder could not make on its own, each with a checker. This module checks
the parts that make that true. It never executes contract code: property names
are read from properties.py with `ast`, and component digests are recomputed.
"""

from __future__ import annotations

import ast
import json
import re
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .digest import contract_digest
from .manifest import load_manifest
from .spec import CheckResult

PACK_MANIFEST_FILE = "symbolon-pack.toml"
OBLIGATIONS_FILE = "obligations.toml"
BRIEF_FILE = "BRIEF.md"
ASSUMPTIONS_DIR = "assumptions"
COMPONENTS_DIR = "components"
# Each version of a pack or contract lives in versions/<n>/ next to the others.
VERSIONS_DIR = "versions"

OBLIGATION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)+$")
ASSUMPTION_ID_RE = re.compile(r"^K-[a-z0-9][a-z0-9-]*$")
CHECK_RE = re.compile(r"^(?P<component>[a-z0-9][a-z0-9-]*)#(?:example:(?P<line>[1-9][0-9]*)|(?P<prop>test_[A-Za-z0-9_]*))$")

# Headings BRIEF.md must have, matched case-insensitively at any level.
BRIEF_SECTIONS = {
    "non-goals": "Non-goals",
    "priorities": "Priorities",
    "who resolves gaps": "Who resolves gaps",
}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Obligation(_Strict):
    id: str
    statement: str = Field(min_length=1)
    status: Literal["decided", "default", "open"]
    kind: Literal["behaviour", "constraint", "security", "audit"] = "behaviour"
    # Exact: every output must satisfy it. Statistical: the output distribution
    # must, checked over `samples` runs with false-alarm rate `alpha`, using
    # `tolerance` of the pack's budget for disagreement. Open is the free case.
    exactness: Literal["exact", "statistical"] = "exact"
    samples: int | None = Field(default=None, ge=1)
    alpha: float | None = Field(default=None, gt=0, lt=1)
    tolerance: float | None = Field(default=None, ge=0)
    reason: str = ""
    source: Literal["extract", "oracle", "replication", "counterexample", "publisher"] = "publisher"
    assumes: list[str] = []
    checks: list[str] = []

    @field_validator("id")
    @classmethod
    def _check_id(cls, v: str) -> str:
        if not OBLIGATION_ID_RE.match(v):
            raise ValueError("must look like 'area.name' (lowercase letters, digits, hyphens, dot-separated)")
        return v


class Obligations(_Strict):
    obligation: list[Obligation] = Field(min_length=1)


class Assumption(_Strict):
    id: str
    statement: str = Field(min_length=1)
    basis: str = Field(min_length=1)
    monitor: str = Field(min_length=1, description='how to watch it in a deployment, or "none"')

    @field_validator("id")
    @classmethod
    def _check_id(cls, v: str) -> str:
        if not ASSUMPTION_ID_RE.match(v):
            raise ValueError("must look like 'K-name' (lowercase letters, digits, hyphens)")
        return v

    @property
    def monitored(self) -> bool:
        return self.monitor.strip().lower() != "none"


@dataclass
class PackReport:
    checks: list[CheckResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)


def _error(e: Exception) -> str:
    if isinstance(e, ValidationError):
        return "; ".join(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors())
    return f"{type(e).__name__}: {e}"


def component_name(contract_dir: Path) -> str:
    """The name a contract directory is known by: tidy for components/tidy/versions/1."""
    contract_dir = Path(contract_dir).resolve()
    return contract_dir.parent.parent.name if contract_dir.parent.name == VERSIONS_DIR else contract_dir.parent.name


def _component_dirs(root: Path) -> dict[str, Path]:
    """Component name -> contract directory, for components/<name>/versions/<n>/symbolon.toml."""
    found = {}
    for manifest in sorted((root / COMPONENTS_DIR).glob(f"*/{VERSIONS_DIR}/*/symbolon.toml")):
        found[component_name(manifest.parent)] = manifest.parent
    return found


def _available_checks(contract_dir: Path) -> set[str]:
    """Every check a contract defines, as 'example:N' and property function names."""
    name = component_name(contract_dir)
    out = set()
    lines = (contract_dir / "examples.jsonl").read_text().split("\n")
    out |= {f"{name}#example:{i}" for i, line in enumerate(lines, 1) if line.strip()}
    tree = ast.parse((contract_dir / "properties.py").read_text())
    out |= {f"{name}#{n.name}" for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")}
    return out


def _brief_headings(text: str) -> set[str]:
    return {m.group(1).strip().lower() for m in re.finditer(r"^#+\s+(.+?)\s*#*\s*$", text, re.M)}


def validate_pack(pack_dir: Path) -> PackReport:
    root = Path(pack_dir).resolve()
    report = PackReport()
    add = report.checks.append

    missing = [f for f in (PACK_MANIFEST_FILE, BRIEF_FILE, OBLIGATIONS_FILE) if not (root / f).is_file()]
    if missing:
        add(CheckResult("required files present", False, "missing: " + ", ".join(missing)))
        return report
    add(CheckResult("required files present", True))

    # Components: every contract listed in the manifest is present and unchanged.
    try:
        with (root / PACK_MANIFEST_FILE).open("rb") as f:
            listed: dict[str, str] = tomllib.load(f).get("components", {})
    except tomllib.TOMLDecodeError as e:
        add(CheckResult(f"{PACK_MANIFEST_FILE} is valid", False, str(e)))
        return report
    components = _component_dirs(root)
    by_alias = {}
    for d in components.values():
        try:
            by_alias[load_manifest(d).alias] = d
        except Exception as e:
            add(CheckResult("component manifests are valid", False, f"{d.relative_to(root)}: {_error(e)}"))
            return report
    problems = []
    for alias, digest in listed.items():
        if alias not in by_alias:
            problems.append(f"{alias}: not found under {COMPONENTS_DIR}/")
        elif contract_digest(by_alias[alias]) != digest:
            problems.append(f"{alias}: digest is {contract_digest(by_alias[alias])}, manifest says {digest}")
    problems += [f"{alias}: present but not listed in {PACK_MANIFEST_FILE}" for alias in by_alias if alias not in listed]
    add(CheckResult("component digests match the pack manifest", not problems,
                    "\n".join(problems) or f"{len(listed)} components"))

    # BRIEF.md: purpose plus the sections an agent cannot infer.
    headings = _brief_headings((root / BRIEF_FILE).read_text())
    absent = [label for key, label in BRIEF_SECTIONS.items() if key not in headings]
    add(CheckResult("BRIEF.md states non-goals, priorities and who resolves gaps", not absent,
                    "missing sections: " + ", ".join(absent) if absent else ""))

    # Assumptions.
    assumptions: dict[str, Assumption] = {}
    problems = []
    for path in sorted((root / ASSUMPTIONS_DIR).glob("*.toml")):
        try:
            with path.open("rb") as f:
                a = Assumption.model_validate(tomllib.load(f))
        except Exception as e:
            problems.append(f"{path.name}: {_error(e)}")
            continue
        if a.id in assumptions:
            problems.append(f"{path.name}: duplicate id {a.id}")
        assumptions[a.id] = a
    monitored = sum(a.monitored for a in assumptions.values())
    add(CheckResult("assumptions are valid", not problems,
                    "\n".join(problems) or f"{len(assumptions)} assumptions, {monitored} monitored"))

    # Obligations.
    try:
        with (root / OBLIGATIONS_FILE).open("rb") as f:
            obligations = Obligations.model_validate(tomllib.load(f)).obligation
    except Exception as e:
        add(CheckResult(f"{OBLIGATIONS_FILE} is valid", False, _error(e)))
        return report
    add(CheckResult(f"{OBLIGATIONS_FILE} is valid", True, f"{len(obligations)} obligations"))

    dupes = [i for i, n in Counter(o.id for o in obligations).items() if n > 1]
    add(CheckResult("obligation ids are unique", not dupes, ", ".join(dupes)))

    available = set()
    for d in components.values():
        available |= _available_checks(d)
    problems = []
    for o in obligations:
        if o.status == "open" and o.checks:
            problems.append(f"{o.id}: open, so it must not have checks (a check would decide it)")
        if o.status != "open" and not o.checks:
            problems.append(f"{o.id}: {o.status}, so it needs at least one check")
        if o.kind == "constraint" and not o.reason.strip():
            problems.append(f"{o.id}: a constraint needs a reason")
        stats = {"samples": o.samples, "alpha": o.alpha, "tolerance": o.tolerance}
        if o.exactness == "statistical":
            if o.status == "open":
                problems.append(f"{o.id}: open, so it is free; it cannot also be statistical")
            missing = [k for k, v in stats.items() if v is None]
            if missing:
                problems.append(f"{o.id}: statistical, so it needs {', '.join(missing)}")
        elif any(v is not None for v in stats.values()):
            problems.append(f"{o.id}: samples, alpha and tolerance only apply to exactness = \"statistical\"")
        for ref in o.checks:
            if not CHECK_RE.match(ref):
                problems.append(f"{o.id}: '{ref}' is not '<component>#example:<line>' or '<component>#test_<name>'")
            elif ref not in available:
                problems.append(f"{o.id}: '{ref}' does not exist")
        for k in o.assumes:
            if k not in assumptions:
                problems.append(f"{o.id}: assumes unknown {k}")
    add(CheckResult("every obligation is checked, open, or explained", not problems, "\n".join(problems)))

    referenced = {ref for o in obligations for ref in o.checks}
    status = Counter(o.status for o in obligations)
    report.summary = {
        "obligations": len(obligations),
        "by_status": {s: status.get(s, 0) for s in ("decided", "default", "open")},
        "by_source": dict(Counter(o.source for o in obligations)),
        "by_exactness": {"exact": sum(o.status != "open" and o.exactness == "exact" for o in obligations),
                         "statistical": sum(o.exactness == "statistical" for o in obligations),
                         "free": status.get("open", 0)},
        "assumptions": len(assumptions),
        "monitored_assumptions": monitored,
        "components": len(components),
        "checks": len(available),
        "checks_tracing_to_an_obligation": len(available & referenced),
    }
    return report


def summary_line(summary: dict) -> str:
    s = summary["by_status"]
    return (f"{summary['obligations']} obligations ({s['decided']} decided, {s['default']} default, "
            f"{s['open']} open) · {summary['assumptions']} assumptions "
            f"({summary['monitored_assumptions']} monitored) · "
            f"{summary['checks_tracing_to_an_obligation']}/{summary['checks']} checks trace to an obligation")


def report_json(report: PackReport) -> str:
    return json.dumps({
        "ok": report.ok,
        "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in report.checks],
        "summary": report.summary,
    }, indent=2)
