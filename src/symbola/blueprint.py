"""A Blueprint as one connected thing: flows, components, decisions and assumptions.

A Blueprint's files already say how its parts hang together. A flow of PRODUCT.md
uses components (flows.toml). A decision binds the components its checks run
against, or the ones it is `about`, or is kept by a flow. A decision rests on the
assumptions it names. This module loads those links once, so that everything that
reasons about a Blueprint (`blueprint validate`, `blueprint map`, `status`, the
site, `blueprint search`) reads the same model rather than its own parse.

Two things follow from the links without anyone writing more:

- **Standing**: how settled each decision is. `checked` has a check a build must
  pass; `unchecked` is required but rests on the builder's word; `open` is the
  builder's to choose. A Blueprint, a component or a flow has the standing of the
  decisions under it, and rests on the assumptions those decisions name.
- **Order**: the components in the order the flows first need them, which is the
  order a build can make progress in.

`build_status` then asks the same question of a build: for each decision, do its
checks pass here? That is what a builder has left, counted in decisions rather
than in test lines.
"""

from __future__ import annotations

import re
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .changes import OVERRIDES_FILE, load_overrides
from .pack import (PACK_MANIFEST_FILE, PRODUCT_FILE, Assumption, Flow, Obligation, PackReport, _component_dirs, load_assumptions,
                   load_flows, load_obligations, validate_pack)

MAP_FORMAT = 1
STANDINGS = ("checked", "unchecked", "open")
# A decision in a build: its checks pass (kept), one fails (failing), its component
# has no build yet (not built), or it is the builder's by the Blueprint's own terms.
STATES = ("kept", "failing", "not built", "unchecked", "open", "overridden")


class BlueprintError(Exception):
    pass


@dataclass
class Blueprint:
    root: Path
    id: str
    version: int | None
    title: str
    product: bool
    components: dict[str, Path]
    assumptions: dict[str, Assumption]
    decisions: list[Obligation]
    flows: list[Flow]
    summary: dict = field(default_factory=dict)

    def decision(self, decision_id: str) -> Obligation | None:
        return next((d for d in self.decisions if d.id == decision_id), None)

    def of_component(self, name: str) -> list[Obligation]:
        return [d for d in self.decisions if name in d.components]

    def of_flow(self, flow: Flow) -> list[Obligation]:
        """Every decision a flow must keep: its own, then those of the components it uses."""
        own = [d for d in self.decisions if d.id in flow.keeps]
        rest = [d for d in self.decisions if d.id not in flow.keeps and set(d.components) & set(flow.uses)]
        return own + rest

    @property
    def product_wide(self) -> list[Obligation]:
        """Decisions tied to no component and no flow: they bind the product as a whole."""
        kept = {k for f in self.flows for k in f.keeps}
        return [d for d in self.decisions if not d.components and d.id not in kept]

    @property
    def order(self) -> list[str]:
        """Components in the order the flows first use them; the rest by name."""
        seen = list(dict.fromkeys(c for f in self.flows for c in f.uses if c in self.components))
        return seen + sorted(set(self.components) - set(seen))


def load_blueprint(root: Path, report: PackReport | None = None) -> Blueprint:
    """Load a Blueprint that passes `blueprint validate`; say what fails when it does not.

    Pass the `report` of a validation already run on this folder to skip a second one.
    """
    root = Path(root).resolve()
    report = report or validate_pack(root)
    if not report.ok:
        bad = "; ".join(f"{c.name}: {c.detail}" for c in report.checks if not c.ok)
        raise BlueprintError(f"{root} is not a valid Blueprint ({bad or 'nothing to check'})")
    with (root / PACK_MANIFEST_FILE).open("rb") as f:
        meta = tomllib.load(f).get("pack", {})
    return Blueprint(
        root=root, id=meta.get("id", root.name), version=meta.get("version"), title=meta.get("title", ""),
        product=(root / PRODUCT_FILE).is_file(), components=_component_dirs(root),
        assumptions=load_assumptions(root), decisions=load_obligations(root), flows=load_flows(root),
        summary=report.summary,
    )


def standing(decisions: list[Obligation]) -> dict:
    """How settled a set of decisions is, and the assumptions it rests on."""
    counts = Counter(d.standing for d in decisions)
    return {
        "decisions": len(decisions),
        **{s: counts.get(s, 0) for s in STANDINGS},
        "assumes": sorted({k for d in decisions for k in d.assumes}),
    }


def standing_line(s: dict) -> str:
    """One line, such as '74 decisions: 69 checked, 5 unchecked, 0 open; rests on 4 assumptions'."""
    n = len(s["assumes"])
    rests = f"; rests on {n} assumption{'' if n == 1 else 's'}" if n else ""
    return (f"{s['decisions']} decision{'' if s['decisions'] == 1 else 's'}: {s['checked']} checked, "
            f"{s['unchecked']} unchecked, {s['open']} open{rests}")


def blueprint_map(bp: Blueprint) -> dict:
    """The Blueprint's parts and links as plain JSON values, for the site and for agents."""
    flows_of = {name: [f.id for f in bp.flows if name in f.uses] for name in bp.components}
    return {
        "format": MAP_FORMAT,
        "id": bp.id,
        "version": bp.version,
        "product": bp.product,
        "standing": standing(bp.decisions),
        "flows": [{
            "id": f.id, "title": f.title, "uses": f.uses, "keeps": f.keeps,
            "standing": standing(bp.of_flow(f)),
        } for f in bp.flows],
        "components": [{
            "name": name,
            "path": bp.components[name].relative_to(bp.root).as_posix(),
            "flows": flows_of[name],
            "decisions": [d.id for d in bp.of_component(name)],
            "standing": standing(bp.of_component(name)),
        } for name in bp.order],
        "product_wide": {
            "decisions": [d.id for d in bp.product_wide],
            "standing": standing(bp.product_wide),
        },
        "assumptions": [{
            "id": k, "statement": a.statement, "monitored": a.monitored,
            "decisions": [d.id for d in bp.decisions if k in d.assumes],
        } for k, a in bp.assumptions.items()],
        "decisions": [{
            "id": d.id, "status": d.status, "standing": d.standing, "components": d.components,
            "flows": [f.id for f in bp.flows if d.id in f.keeps], "assumes": d.assumes,
        } for d in bp.decisions],
        "order": bp.order,
    }


def map_markdown(bp: Blueprint) -> str:
    """The map for a reader: what to build in which order, and what each part must keep."""
    m = blueprint_map(bp)
    out = [f"# {bp.id}: map\n", standing_line(m["standing"]) + ".\n"]
    if m["components"]:
        out.append("## Build order\n")
        out.append("Components in the order the flows first need them. A component is done when its checks pass.\n"
                   if bp.flows else "Components, each done when its checks pass.\n")
        for i, c in enumerate(m["components"], 1):
            used = f"; used by {', '.join(c['flows'])}" if c["flows"] else ""
            out.append(f"{i}. `{c['name']}` (`{c['path']}`): {standing_line(c['standing'])}{used}")
        out.append("")
    if m["flows"]:
        out.append("## Flows\n")
        out.append(f"Each flow of `{PRODUCT_FILE}`, the components it uses and the decisions it keeps itself.\n")
        for i, f in enumerate(m["flows"], 1):
            uses = ", ".join(f"`{c}`" for c in f["uses"]) or "no component"
            keeps = f"; keeps {', '.join(f'`{k}`' for k in f['keeps'])}" if f["keeps"] else ""
            out.append(f"{i}. **{f['title']}** (`{f['id']}`): uses {uses}{keeps}")
        out.append("")
    wide = m["product_wide"]["decisions"]
    if wide:
        out.append("## The whole product\n")
        out.append("Decisions tied to no single component or flow: " + ", ".join(f"`{d}`" for d in wide) + ".\n")
    loose = [d for d in bp.decisions if d.standing != "checked"]
    if loose:
        out.append("## Not settled by a check\n")
        out.append("Unchecked decisions are required, and nothing but the builder confirms them. "
                   "Open decisions are the builder's to choose.\n")
        for d in loose:
            why = f" ({d.unchecked.strip()})" if d.unchecked.strip() else ""
            out.append(f"- `{d.id}` ({d.standing}): {d.statement}{why}")
        out.append("")
    if m["assumptions"]:
        out.append("## Assumptions it rests on\n")
        out.append("True of the world for every build; the decisions that name one depend on it directly.\n")
        for a in m["assumptions"]:
            n = len(a["decisions"])
            rests = f" ({n} decision{'' if n == 1 else 's'} name it)" if n else ""
            out.append(f"- `{a['id']}`: {a['statement']}{rests}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- a build's status

def _check_names(result: dict) -> dict[str, tuple[bool, str]]:
    """A component's test result by check name as decisions cite it: 'example:N' or 'test_x'."""
    found = {}
    for c in result.get("examples", []):
        m = re.match(r"^example line (\d+)", c["name"])
        if m:
            found[f"example:{m.group(1)}"] = (c["ok"], c["detail"])
    for c in result.get("properties", []):
        found[c["name"]] = (c["ok"], c["detail"])
    return found


def decision_states(bp: Blueprint, results: dict[str, dict | None], overridden: set[str] = frozenset()) -> list[dict]:
    """Each decision's state in a build, given every component's test result (None: not built)."""
    names = {c: _check_names(r) for c, r in results.items() if r is not None and "error" not in r}
    out = []
    for d in bp.decisions:
        failing, missing = [], []
        for ref in d.checks:
            component, check = ref.split("#", 1)
            if component not in names:
                missing.append(component)
            elif not names[component].get(check, (False, "this check did not run"))[0]:
                failing.append(ref)
        if d.id in overridden:
            state = "overridden"
        elif d.standing != "checked":
            state = d.standing
        elif failing:
            state = "failing"
        elif missing:
            state = "not built"
        else:
            state = "kept"
        out.append({"id": d.id, "state": state, "statement": d.statement, "components": d.components,
                    "failing": failing if state == "failing" else [],
                    "waits_for": sorted(set(missing)) if state == "not built" else []})
    return out


def kept_by(bp: Blueprint, passed: dict[str, set[str]]) -> list[str]:
    """The checked decisions whose every check is among those a build passed, per component."""
    return [d.id for d in bp.decisions if d.standing == "checked"
            and all(ref.split("#", 1)[1] in passed.get(ref.split("#", 1)[0], ()) for ref in d.checks)]


def attested_checks(passed_tests: list[str]) -> set[str]:
    """An attestation's passedTests as decisions cite checks: 'example:3', 'test_x'."""
    found = set()
    for name in passed_tests:
        m = re.match(r"^example:line (\d+)", name)
        if m:
            found.add(f"example:{m.group(1)}")
        elif name.startswith("property:"):
            found.add(name.removeprefix("property:"))
    return found


def build_status(spec: Path, impl_root: Path, overrides: Path | None = None, run=None) -> dict:
    """What a build has kept of a Blueprint, counted in decisions.

    `impl_root` holds one folder per component, named after it. `run(contract, impl)`
    runs a component's checks and defaults to the same run as `symbola test`.
    """
    from .validate import WorkerError, check_impl
    run = run or check_impl
    bp = load_blueprint(spec)
    spec, impl_root = Path(spec).resolve(), Path(impl_root).resolve()
    overridden = {o.id for o in load_overrides(overrides if overrides is not None else spec.parent / OVERRIDES_FILE)}
    unknown = sorted(overridden - {d.id for d in bp.decisions})
    results: dict[str, dict | None] = {}
    components = []
    for name in bp.order:
        impl = impl_root / name
        entry = {"name": name, "built": impl.is_dir(), "checks": 0, "failed": [], "error": ""}
        if not entry["built"]:
            results[name] = None
        else:
            try:
                result = run(bp.components[name], impl)
            except WorkerError as e:
                result = {"error": str(e)}
            results[name] = result
            if "error" in result:
                entry["error"] = str(result["error"])
            else:
                checks = _check_names(result)
                entry["checks"] = len(checks)
                entry["failed"] = sorted(n for n, (ok, _) in checks.items() if not ok)
        components.append(entry)
    decisions = decision_states(bp, results, overridden)
    by_state = Counter(d["state"] for d in decisions)
    cited = {ref for d in bp.decisions for ref in d.checks}
    stray = sorted(f"{c['name']}#{n}" for c in components for n in c["failed"] if f"{c['name']}#{n}" not in cited)
    broken = [c["name"] for c in components if c["error"]]
    return {
        "id": bp.id, "version": bp.version,
        "decisions": decisions,
        "by_state": {s: by_state.get(s, 0) for s in STATES},
        "components": components,
        # Failing checks no decision cites: a gap in the Blueprint, but still a failing build.
        "failing_outside_decisions": stray,
        "assumes": standing(bp.decisions)["assumes"],
        "unknown_overrides": unknown,
        "done": not (by_state.get("failing") or by_state.get("not built") or stray or broken),
    }


def status_line(status: dict) -> str:
    s = status["by_state"]
    parts = [f"{s[k]} {k}" for k in STATES if s[k]]
    n = len(status["assumes"])
    rests = f"; rests on {n} assumption{'' if n == 1 else 's'}" if n else ""
    return f"{len(status['decisions'])} decisions: {', '.join(parts) or 'none'}{rests}"


def status_markdown(status: dict) -> str:
    """The status as a note a builder's agent can keep beside the build."""
    out = [f"# Build status: {status['id']}" + (f" version {status['version']}" if status["version"] else "") + "\n",
           status_line(status) + ".\n"]
    labels = {
        "failing": "Failing: a check of the decision does not pass",
        "not built": "Not built: the decision's component has no build yet",
        "unchecked": "Unchecked: required, and only you confirm it",
        "open": "Open: yours to choose; note the choice",
        "overridden": f"Overridden: departed from on purpose in {OVERRIDES_FILE}",
    }
    for state, label in labels.items():
        rows = [d for d in status["decisions"] if d["state"] == state]
        if not rows:
            continue
        out.append(f"## {label}\n")
        for d in rows:
            extra = (": " + ", ".join(d["failing"]) if d["failing"] else
                     ": waits for " + ", ".join(d["waits_for"]) if d["waits_for"] else "")
            out.append(f"- `{d['id']}`{extra}  \n  {d['statement']}")
        out.append("")
    if status["failing_outside_decisions"]:
        out.append("## Failing checks no decision cites\n")
        out += [f"- `{ref}`" for ref in status["failing_outside_decisions"]] + [""]
    if status["assumes"]:
        out.append("## Assumptions the result rests on\n")
        out += [f"- `{k}`" for k in status["assumes"]] + [""]
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- search

def search_entries(bp: Blueprint) -> list[dict]:
    """A Blueprint's decisions and assumptions as rows a search can match and a publisher can copy."""
    rows = [{
        "blueprint": bp.id, "kind": "decision", "id": d.id, "statement": d.statement, "status": d.status,
        "standing": d.standing, "components": d.components, "checks": len(d.checks),
    } for d in bp.decisions]
    rows += [{
        "blueprint": bp.id, "kind": "assumption", "id": a.id, "statement": a.statement, "basis": a.basis,
        "monitor": a.monitor,
    } for a in bp.assumptions.values()]
    return rows


_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset("a an and are as at be by for from has have if in is it its of on or that the to with when "
                  "must not no only each every any".split())


def _words(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1]


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def search(entries: list[dict], query: str, limit: int = 10, kind: str = "") -> list[dict]:
    """Rows that share words with the query, best first: rows with every query word, else with some.

    A word matches a row when it, or its stem, appears in the row's statement or id.
    Rows are ranked by how rare their matching words are across all rows, so a
    query's distinctive words count for more than its common ones.
    """
    wanted = list(dict.fromkeys(_stem(w) for w in _words(query)))
    if not wanted:
        return []
    pool = [e for e in entries if not kind or e["kind"] == kind]
    bags = [{_stem(w) for w in _words(f"{e['statement']} {e['id'].replace('.', ' ').replace('-', ' ')}")} for e in pool]
    seen = Counter(w for bag in bags for w in bag)
    scored = []
    for need_all in (True, False):  # rows with every word first; failing that, rows with most of them
        for e, bag in zip(pool, bags):
            hits = [w for w in wanted if w in bag]
            if not hits or (need_all and len(hits) < len(wanted)):
                continue
            score = sum(1 / seen[w] for w in hits) * len(hits) / len(wanted) / (1 + len(bag) / 40)
            scored.append((score, e))
        if scored:
            break
    scored.sort(key=lambda x: (-x[0], x[1]["blueprint"], x[1]["id"]))
    return [e for _, e in scored[:limit]]
