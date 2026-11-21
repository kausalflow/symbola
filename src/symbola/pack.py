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
from .spec import CheckResult, SpecError, load_examples

PACK_MANIFEST_FILE = "symbolon-pack.toml"
OBLIGATIONS_FILE = "obligations.toml"
BRIEF_FILE = "BRIEF.md"
# Optional: the whole product a build delivers. A pack with it is a product pack,
# whose components are the product's core; one without it is a component library.
PRODUCT_FILE = "PRODUCT.md"
# The flows of PRODUCT.md as data: which components each one uses and which
# decisions it carries. Required beside PRODUCT.md, absent without it.
FLOWS_FILE = "flows.toml"
ASSUMPTIONS_DIR = "assumptions"
COMPONENTS_DIR = "components"
# Each version of a pack or contract lives in versions/<n>/ next to the others.
VERSIONS_DIR = "versions"

OBLIGATION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)+$")
FLOW_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
COMPONENT_NAME_RE = FLOW_ID_RE
ASSUMPTION_ID_RE = re.compile(r"^K-[a-z0-9][a-z0-9-]*$")
CHECK_RE = re.compile(r"^(?P<component>[a-z0-9][a-z0-9-]*)#(?:example:(?P<line>[1-9][0-9]*)|(?P<prop>test_[A-Za-z0-9_]*))$")

# Headings BRIEF.md must have, matched case-insensitively at any level.
BRIEF_SECTIONS = {
    "non-goals": "Non-goals",
    "priorities": "Priorities",
    "who resolves gaps": "Who resolves gaps",
}

# Headings PRODUCT.md must have when present.
PRODUCT_SECTIONS = {
    "shape": "Shape",
    "surfaces": "Surfaces",
    "flows": "Flows",
}

# A decided or default obligation with no check yet must say what check it
# needs (`unchecked`). Such debt may be at most this share of them, so the
# pack stays a set of checked promises rather than prose.
DEFAULT_MAX_UNCHECKED = 0.1


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Obligation(_Strict):
    id: str
    statement: str = Field(min_length=1)
    status: Literal["decided", "default", "open"]
    kind: Literal["behaviour", "constraint", "security", "audit"] = "behaviour"
    # Exact: every output must satisfy it. Statistical: the output distribution
    # must, so at least one of its checks is a statistical property, run over
    # seeds as its contract's [spec.statistical] says. Open is the free case.
    exactness: Literal["exact", "statistical"] = "exact"
    reason: str = ""
    source: Literal["extract", "oracle", "replication", "counterexample", "publisher"] = "publisher"
    assumes: list[str] = []
    checks: list[str] = []
    # Required but not yet checkable: the kind of check that would settle it,
    # such as "a static check over the source tree". Reported as debt.
    unchecked: str = ""
    # Components the decision is about beyond those its checks name; the only
    # way a decision without checks says which part of the product it binds.
    about: list[str] = []

    @field_validator("id")
    @classmethod
    def _check_id(cls, v: str) -> str:
        if not OBLIGATION_ID_RE.match(v):
            raise ValueError("must look like 'area.name' (lowercase letters, digits, hyphens, dot-separated)")
        return v

    @property
    def standing(self) -> str:
        """How settled the decision is: checked, unchecked (required, no check yet) or open."""
        if self.status == "open":
            return "open"
        return "checked" if self.checks else "unchecked"

    @property
    def components(self) -> list[str]:
        """The components it binds: those its checks run against, then those in `about`."""
        names = [ref.split("#", 1)[0] for ref in self.checks] + self.about
        return list(dict.fromkeys(names))


class Obligations(_Strict):
    obligation: list[Obligation] = Field(min_length=1)


class Flow(_Strict):
    """One thing users do, as PRODUCT.md tells it, tied to the parts that carry it."""

    id: str
    title: str = Field(min_length=1)
    uses: list[str] = []
    # Decisions the flow itself must keep, beyond those of the components it uses:
    # the product-level ones no single component owns.
    keeps: list[str] = []

    @field_validator("id")
    @classmethod
    def _check_id(cls, v: str) -> str:
        if not FLOW_ID_RE.match(v):
            raise ValueError("must be lowercase letters, digits and hyphens")
        return v


class Flows(_Strict):
    flow: list[Flow] = Field(min_length=1)


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


def _expected(example: dict) -> str:
    return json.dumps({k: example[k] for k in ("output", "raises") if k in example}, sort_keys=True)


def _brief_headings(text: str) -> set[str]:
    return {m.group(1).strip().lower() for m in re.finditer(r"^#+\s+(.+?)\s*#*\s*$", text, re.M)}


def product_flows(text: str) -> tuple[list[str], list[str]]:
    """The flow titles of a PRODUCT.md, in order, and what is wrong with its Flows section.

    A flow is a numbered item under the Flows heading that opens with its title in
    bold: `1. **Join and sync.** Opening a link ...`. The title, without closing
    punctuation, is what flows.toml refers to.
    """
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines)
                  if re.match(r"^#+\s+flows\s*#*\s*$", line.strip(), re.I)), None)
    if start is None:
        return [], []
    titles, problems = [], []
    for line in lines[start + 1:]:
        if re.match(r"^#+\s", line):
            break
        item = re.match(r"^(\d+)\.\s+(.*)$", line)
        if not item:
            continue
        bold = re.match(r"^\*\*(.+?)\*\*", item.group(2))
        title = bold.group(1).strip().rstrip(".:").strip() if bold else ""
        if not title:
            problems.append(f"flow {item.group(1)} must open with its title in bold, like '1. **Find a paper.** ...'")
        else:
            titles.append(title)
    dupes = [t for t, n in Counter(titles).items() if n > 1]
    problems += [f"two flows are titled '{t}'" for t in dupes]
    return titles, problems


def _flow_items(text: str) -> list[tuple[str, str]]:
    """(title, body) of each flow of a PRODUCT.md, the body running to the next flow."""
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines)
                  if re.match(r"^#+\s+flows\s*#*\s*$", line.strip(), re.I)), None)
    items: list[tuple[str, list[str]]] = []
    for line in lines[start + 1:] if start is not None else []:
        if re.match(r"^#+\s", line):
            break
        item = re.match(r"^\d+\.\s+\*\*(.+?)\*\*(.*)$", line)
        if item:
            items.append((item.group(1).strip().rstrip(".:").strip(), [item.group(2)]))
        elif items:
            items[-1][1].append(line)
    return [(title, "\n".join(body)) for title, body in items if title]


def flow_id(title: str) -> str:
    """A flow id from its title: 'Join and sync' -> 'join-and-sync'."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "flow"


def draft_flows(root: Path) -> str:
    """flows.toml for a Blueprint, in step with its PRODUCT.md.

    Flows already listed keep their id, `uses` and `keeps`, matched by title. A new
    flow gets an id from its title and, as a first draft for the publisher to
    correct, the components its text names in backticks.
    """
    root = Path(root)
    components = _component_dirs(root)
    try:
        known = {f.title: f for f in load_flows(root)}
    except Exception:
        known = {}
    taken = {f.id for f in known.values()}
    out = [f"# The flows of {PRODUCT_FILE}, in its order: the components each one uses, and the decisions",
           "# it keeps itself (product-level ones no component's checks cover). `symbola blueprint flows`",
           "# keeps this file in step with the titles there; `uses` and `keeps` are yours to maintain.", ""]
    for title, body in _flow_items((root / PRODUCT_FILE).read_text()):
        flow = known.get(title)
        if flow is None:
            base = fid = flow_id(title)
            n = 2
            while fid in taken:
                fid, n = f"{base}-{n}", n + 1
            taken.add(fid)
            named = dict.fromkeys(re.findall(r"`([^`]+)`", body))
            flow = Flow(id=fid, title=title, uses=[c for c in named if c in components])
        out += ["[[flow]]", f"id = {json.dumps(flow.id)}", f"title = {json.dumps(flow.title, ensure_ascii=False)}",
                f"uses = {json.dumps(flow.uses)}"]
        if flow.keeps:
            out.append(f"keeps = {json.dumps(flow.keeps)}")
        out.append("")
    return "\n".join(out)


def load_flows(root: Path) -> list[Flow]:
    """The flows of a product Blueprint; none for a component library. Raises when malformed."""
    path = Path(root) / FLOWS_FILE
    if not path.is_file():
        return []
    with path.open("rb") as f:
        return Flows.model_validate(tomllib.load(f)).flow


def load_obligations(root: Path) -> list[Obligation]:
    with (Path(root) / OBLIGATIONS_FILE).open("rb") as f:
        return Obligations.model_validate(tomllib.load(f)).obligation


def load_assumptions(root: Path) -> dict[str, Assumption]:
    found = {}
    for path in sorted((Path(root) / ASSUMPTIONS_DIR).glob("*.toml")):
        with path.open("rb") as f:
            a = Assumption.model_validate(tomllib.load(f))
        found[a.id] = a
    return found


def _check_flows(root: Path, components: dict[str, Path], obligations: list[Obligation]) -> CheckResult | None:
    """flows.toml says, for each flow PRODUCT.md tells, the components it uses and the decisions it keeps."""
    product, flows_file = root / PRODUCT_FILE, root / FLOWS_FILE
    name = f"{FLOWS_FILE} ties every flow to its components"
    if not product.is_file():
        if flows_file.is_file():
            return CheckResult(name, False, f"{FLOWS_FILE} needs a {PRODUCT_FILE} that tells its flows; "
                                            "a component library has neither")
        return None
    if not flows_file.is_file():
        return CheckResult(name, False, f"missing {FLOWS_FILE}: a product Blueprint lists each flow of "
                                        f"{PRODUCT_FILE} with the components it uses")
    try:
        flows = load_flows(root)
    except Exception as e:
        return CheckResult(name, False, _error(e))
    titles, problems = product_flows(product.read_text())
    if not titles and not problems:
        problems.append(f"{PRODUCT_FILE} tells no flows: number them under Flows, each opening with a bold title")
    problems += [f"two flows have the id '{i}'" for i, n in Counter(f.id for f in flows).items() if n > 1]
    listed = [f.title for f in flows]
    if not problems and listed != titles:
        missing = [t for t in titles if t not in listed]
        extra = [t for t in listed if t not in titles]
        if missing:
            problems.append(f"flows of {PRODUCT_FILE} not in {FLOWS_FILE}: " + ", ".join(f"'{t}'" for t in missing))
        if extra:
            problems.append(f"flows of {FLOWS_FILE} not in {PRODUCT_FILE}: " + ", ".join(f"'{t}'" for t in extra))
        if not missing and not extra:
            problems.append(f"flows are in a different order than in {PRODUCT_FILE}")
    ids = {o.id for o in obligations}
    used = set()
    for f in flows:
        used |= set(f.uses)
        problems += [f"{f.id}: uses unknown component '{c}'" for c in f.uses if c not in components]
        problems += [f"{f.id}: keeps unknown decision '{k}'" for k in f.keeps if k not in ids]
        for field_name, values in (("uses", f.uses), ("keeps", f.keeps)):
            problems += [f"{f.id}: lists '{v}' twice under {field_name}" for v, n in Counter(values).items() if n > 1]
    idle = sorted(set(components) - used)
    if idle:
        problems.append("no flow uses " + ", ".join(idle) + ": add each to the flows that rely on it, "
                        "or leave the component out of the Blueprint")
    kept = Counter(k for f in flows for k in f.keeps)
    return CheckResult(name, not problems, "\n".join(problems) or
                       f"{len(flows)} flows, {len(used)} components used, {len(kept)} decisions kept by flows")


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
            manifest = tomllib.load(f)
        listed: dict[str, str] = manifest.get("components", {})
        max_unchecked = manifest.get("pack", {}).get("max_unchecked", DEFAULT_MAX_UNCHECKED)
    except tomllib.TOMLDecodeError as e:
        add(CheckResult(f"{PACK_MANIFEST_FILE} is valid", False, str(e)))
        return report
    components = _component_dirs(root)
    by_alias = {}
    statistical = set()
    for name, d in components.items():
        try:
            m = load_manifest(d)
            by_alias[m.alias] = d
            statistical |= {f"{name}#{t}" for t in m.spec.statistical}
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
    add(CheckResult("component digests match the Blueprint manifest", not problems,
                    "\n".join(problems) or f"{len(listed)} components"))

    # Examples: two lines with the same input must expect the same result. Without a
    # product to run them against (a pack written before any code), this is the one
    # check that catches decisions recorded twice, differently.
    problems = []
    for name, d in components.items():
        try:
            examples = load_examples(d / "examples.jsonl")
        except (SpecError, OSError) as e:
            problems.append(f"{name}: {e}")
            continue
        seen: dict[str, dict] = {}
        for ex in examples:
            key = json.dumps(ex["input"], sort_keys=True)
            first = seen.setdefault(key, ex)
            if first is not ex and _expected(first) != _expected(ex):
                problems.append(f"{name}: examples {first['_line']} and {ex['_line']} have the same input "
                                "but expect different results")
    add(CheckResult("examples do not contradict each other", not problems, "\n".join(problems)))

    # BRIEF.md: purpose plus the sections an agent cannot infer.
    headings = _brief_headings((root / BRIEF_FILE).read_text())
    absent = [label for key, label in BRIEF_SECTIONS.items() if key not in headings]
    add(CheckResult("BRIEF.md states non-goals, priorities and who resolves gaps", not absent,
                    "missing sections: " + ", ".join(absent) if absent else ""))

    # PRODUCT.md: optional; when present the pack is built as a whole product.
    if (root / PRODUCT_FILE).is_file():
        headings = _brief_headings((root / PRODUCT_FILE).read_text())
        absent = [label for key, label in PRODUCT_SECTIONS.items() if key not in headings]
        add(CheckResult("PRODUCT.md states the shape, surfaces and flows", not absent,
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
        if o.unchecked.strip():
            if o.status == "open":
                problems.append(f"{o.id}: open, so it is free; it cannot be unchecked")
            elif o.checks:
                problems.append(f"{o.id}: has checks, so it is not unchecked; remove one or the other")
        elif o.status != "open" and not o.checks:
            problems.append(f"{o.id}: {o.status}, so it needs at least one check, "
                            "or an `unchecked` reason naming the check it would need")
        if o.kind == "constraint" and not o.reason.strip():
            problems.append(f"{o.id}: a constraint needs a reason")
        if o.exactness == "statistical":
            if o.status == "open":
                problems.append(f"{o.id}: open, so it is free; it cannot also be statistical")
            elif o.checks and not statistical & set(o.checks):
                problems.append(f"{o.id}: statistical, so at least one of its checks must be a property "
                                "listed under [spec.statistical] in its contract")
        for ref in o.checks:
            if not CHECK_RE.match(ref):
                problems.append(f"{o.id}: '{ref}' is not '<component>#example:<line>' or '<component>#test_<name>'")
            elif ref not in available:
                problems.append(f"{o.id}: '{ref}' does not exist")
        for k in o.assumes:
            if k not in assumptions:
                problems.append(f"{o.id}: assumes unknown {k}")
        for c in o.about:
            if c not in components:
                problems.append(f"{o.id}: is about unknown component '{c}'")
            elif any(ref.startswith(f"{c}#") for ref in o.checks):
                problems.append(f"{o.id}: its checks already tie it to '{c}'; drop it from `about`")
    add(CheckResult("every obligation is checked, open, or explained", not problems, "\n".join(problems)))

    flows_check = _check_flows(root, components, obligations)
    if flows_check is not None:
        add(flows_check)

    bound = [o for o in obligations if o.status != "open"]
    unchecked = [o.id for o in bound if o.unchecked.strip()]
    if not isinstance(max_unchecked, (int, float)) or isinstance(max_unchecked, bool) or not 0 <= max_unchecked <= 1:
        add(CheckResult("unchecked obligations are within the cap", False,
                        f"[pack] max_unchecked must be a share between 0 and 1, not {max_unchecked!r}"))
    elif unchecked:
        share = len(unchecked) / len(bound)
        add(CheckResult("unchecked obligations are within the cap", share <= max_unchecked,
                        f"{len(unchecked)} of {len(bound)} decided or default obligations have no check yet "
                        f"({share:.0%}; the cap is {max_unchecked:.0%}): {', '.join(unchecked)}"))

    referenced = {ref for o in obligations for ref in o.checks}
    status = Counter(o.status for o in obligations)
    report.summary = {
        "product": (root / PRODUCT_FILE).is_file(),
        "obligations": len(obligations),
        "by_status": {s: status.get(s, 0) for s in ("decided", "default", "open")},
        "unchecked": len(unchecked),
        # How settled the decisions are: checked by something a build must pass,
        # required on the builder's word alone, or left to the builder.
        "standing": {k: sum(o.standing == k for o in obligations) for k in ("checked", "unchecked", "open")},
        "assumptions_relied_on": len({k for o in obligations for k in o.assumes}),
        "flows": len(load_flows(root)) if flows_check is not None and flows_check.ok else 0,
        "by_source": dict(Counter(o.source for o in obligations)),
        "statistical_checks": len(statistical),
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
    debt = f", {summary['unchecked']} unchecked" if summary.get("unchecked") else ""
    kind = "product pack · " if summary.get("product") else ""
    return (f"{kind}{summary['obligations']} obligations ({s['decided']} decided, {s['default']} default, "
            f"{s['open']} open{debt}) · {summary['assumptions']} assumptions "
            f"({summary['monitored_assumptions']} monitored) · "
            f"{summary['checks_tracing_to_an_obligation']}/{summary['checks']} checks trace to an obligation")


def report_json(report: PackReport) -> str:
    return json.dumps({
        "ok": report.ok,
        "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in report.checks],
        "summary": report.summary,
    }, indent=2)
