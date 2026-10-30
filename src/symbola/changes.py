"""What changed between two versions of a pack, decision by decision.

Computed from the two folders alone, so publishers write nothing extra: the
registry shows it on the pack's page, `release` prints it, and `upgrade` hands it
to a builder's agent with the builder's own overrides marked.

Decisions (obligations) and assumptions are matched by id, components by name,
and documents (the top-level Markdown files) by file name.
"""

from __future__ import annotations

import difflib
import hashlib
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .digest import contract_digest, contract_files
from .pack import ASSUMPTIONS_DIR, COMPONENTS_DIR, OBLIGATIONS_FILE, PACK_MANIFEST_FILE, VERSIONS_DIR

OVERRIDES_FILE = "overrides.toml"
DECISION_FIELDS = ("statement", "status", "kind", "exactness", "reason", "assumes", "checks", "unchecked")
ASSUMPTION_FIELDS = ("statement", "basis", "monitor")
# Lines of each document's diff kept in the Markdown report.
DIFF_LINES = 120


class Override(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, description="the decision (obligation) id this build departs from")
    reason: str = Field(min_length=1)
    # What this build does instead, in a sentence or two.
    instead: str = ""


class Overrides(BaseModel):
    model_config = ConfigDict(extra="forbid")
    override: list[Override] = []


def load_overrides(path: Path) -> list[Override]:
    """A builder's departures from the pack, or none if the file does not exist."""
    path = Path(path)
    if not path.is_file():
        return []
    try:
        with path.open("rb") as f:
            return Overrides.model_validate(tomllib.load(f)).override
    except (tomllib.TOMLDecodeError, ValidationError) as e:
        raise ValueError(f"{path}: {e}") from None


def _toml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def _version(root: Path) -> int | None:
    return _toml(root / PACK_MANIFEST_FILE).get("pack", {}).get("version")


def _decisions(root: Path) -> dict[str, dict]:
    return {o["id"]: o for o in _toml(root / OBLIGATIONS_FILE).get("obligation", [])}


def _assumptions(root: Path) -> dict[str, dict]:
    found = {}
    for path in sorted((root / ASSUMPTIONS_DIR).glob("*.toml")):
        data = _toml(path)
        found[data.get("id", path.stem)] = data
    return found


def _components(root: Path) -> dict[str, Path]:
    """Component name -> its newest contract folder in this pack version."""
    found: dict[str, Path] = {}
    for manifest in (root / COMPONENTS_DIR).glob(f"*/{VERSIONS_DIR}/*/symbolon.toml"):
        name, folder = manifest.parent.parent.parent.name, manifest.parent
        if name not in found or int(folder.name) > int(found[name].name):
            found[name] = folder
    return found


def _hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for p in contract_files(root)}


def _field_changes(old: dict, new: dict, fields: tuple[str, ...]) -> dict:
    return {f: [old.get(f), new.get(f)] for f in fields if old.get(f) != new.get(f)}


def _matched(old: dict[str, dict], new: dict[str, dict], fields: tuple[str, ...]) -> dict:
    changed = []
    for key in sorted(old.keys() & new.keys()):
        fields_changed = _field_changes(old[key], new[key], fields)
        if fields_changed:
            changed.append({"id": key, "fields": fields_changed})
    return {
        "added": [{"id": k, **{f: new[k].get(f) for f in fields if f in new[k]}} for k in sorted(new.keys() - old.keys())],
        "removed": [{"id": k, **{f: old[k].get(f) for f in fields if f in old[k]}} for k in sorted(old.keys() - new.keys())],
        "changed": changed,
    }


def compare(old: Path, new: Path) -> dict:
    """The changes from pack folder `old` to pack folder `new`, as plain JSON values."""
    old, new = Path(old), Path(new)
    components: dict[str, list] = {"added": [], "removed": [], "changed": []}
    a, b = _components(old), _components(new)
    for name in sorted(b.keys() - a.keys()):
        components["added"].append({"name": name, "path": b[name].relative_to(new).as_posix()})
    for name in sorted(a.keys() - b.keys()):
        components["removed"].append({"name": name, "path": a[name].relative_to(old).as_posix()})
    for name in sorted(a.keys() & b.keys()):
        if contract_digest(a[name]) == contract_digest(b[name]):
            continue
        x, y = _hashes(a[name]), _hashes(b[name])
        components["changed"].append({
            "name": name,
            "from": a[name].relative_to(old).as_posix(),
            "to": b[name].relative_to(new).as_posix(),
            "files": sorted(f for f in x.keys() | y.keys() if x.get(f) != y.get(f)),
        })
    documents = []
    for name in sorted({p.name for p in (*old.glob("*.md"), *new.glob("*.md"))}):
        x = (old / name).read_text().splitlines() if (old / name).is_file() else []
        y = (new / name).read_text().splitlines() if (new / name).is_file() else []
        if x != y:
            diff = list(difflib.unified_diff(x, y, f"a/{name}", f"b/{name}", lineterm="", n=1))
            documents.append({"file": name, "added": not x, "removed": not y, "diff": diff})
    decisions = _matched(_decisions(old), _decisions(new), DECISION_FIELDS)
    assumptions = _matched(_assumptions(old), _assumptions(new), ASSUMPTION_FIELDS)
    return {
        "from": _version(old), "to": _version(new),
        "decisions": decisions, "assumptions": assumptions,
        "components": components, "documents": documents,
        "summary": {
            **{f"decisions_{k}": len(v) for k, v in decisions.items()},
            **{f"assumptions_{k}": len(v) for k, v in assumptions.items()},
            **{f"components_{k}": len(v) for k, v in components.items()},
            "documents_changed": len(documents),
        },
    }


def is_empty(changes: dict) -> bool:
    return not any(changes["summary"].values())


def summary_text(changes: dict) -> str:
    """One line, such as 'decisions: 2 changed, 1 added; component tidy changed; PRODUCT.md changed'."""
    s, parts = changes["summary"], []
    for what in ("decisions", "assumptions"):
        counts = [f"{s[f'{what}_{k}']} {k}" for k in ("changed", "added", "removed") if s[f"{what}_{k}"]]
        if counts:
            parts.append(f"{what}: {', '.join(counts)}")
    for k in ("changed", "added", "removed"):
        names = [c["name"] for c in changes["components"][k]]
        if names:
            parts.append(f"{'component' if len(names) == 1 else 'components'} {', '.join(names)} {k}")
    if changes["documents"]:
        parts.append(f"{', '.join(d['file'] for d in changes['documents'])} changed")
    return "; ".join(parts) or "no changes"


def _value(v) -> str:
    if isinstance(v, list):
        return ", ".join(f"`{x}`" for x in v) or "(none)"
    return f"{v}" if v not in (None, "") else "(none)"


def markdown(changes: dict, title: str, overrides: list[Override] = (), diff_lines: int = DIFF_LINES) -> str:
    """The changes as Markdown. With `overrides`, decisions the builder departs from are marked."""
    mine = {o.id: o for o in overrides}
    out = [f"# {title}\n", f"{summary_text(changes)}.\n"]
    d = changes["decisions"]
    if any(d.values()):
        out.append("## Decisions\n")
        for c in d["changed"]:
            mark = "  **You override this decision**: decide with the user whether to keep your override." if c["id"] in mine else ""
            out.append(f"- **changed** `{c['id']}`{mark}")
            for field, (x, y) in c["fields"].items():
                out.append(f"  - {field}: {_value(x)}  \n    now: {_value(y)}")
        for c in d["added"]:
            out.append(f"- **added** `{c['id']}` ({c.get('status')}): {c.get('statement')}")
        for c in d["removed"]:
            mark = " You override it; your override no longer has anything to depart from." if c["id"] in mine else ""
            out.append(f"- **removed** `{c['id']}`: {c.get('statement')}{mark}")
        out.append("")
    a = changes["assumptions"]
    if any(a.values()):
        out.append("## Assumptions\n")
        for c in a["changed"]:
            out.append(f"- **changed** `{c['id']}`")
            for field, (x, y) in c["fields"].items():
                out.append(f"  - {field}: {_value(x)}  \n    now: {_value(y)}")
        out += [f"- **added** `{c['id']}`: {c.get('statement')}" for c in a["added"]]
        out += [f"- **removed** `{c['id']}`: {c.get('statement')}" for c in a["removed"]]
        out.append("")
    c = changes["components"]
    if any(c.values()):
        out.append("## Components\n")
        out += [f"- **changed** `{x['name']}` ({x['to']}): {', '.join(x['files'])}" for x in c["changed"]]
        out += [f"- **added** `{x['name']}` ({x['path']})" for x in c["added"]]
        out += [f"- **removed** `{x['name']}`" for x in c["removed"]]
        out.append("")
    for doc in changes["documents"]:
        out.append(f"## {doc['file']}\n")
        lines = doc["diff"][2:]  # drop the ---/+++ header
        shown = lines[:diff_lines]
        out += ["```diff", *shown, "```"]
        if len(lines) > len(shown):
            out.append(f"\n({len(lines) - len(shown)} more lines; compare the two files.)")
        out.append("")
    orphans = [o for o in overrides if o.id not in {x["id"] for x in d["changed"] + d["removed"]}]
    if overrides:
        out.append("## Your overrides\n")
        for o in overrides:
            state = "unchanged upstream: keep it" if o in orphans else "touched by this version: see above"
            out.append(f"- `{o.id}`: {o.reason} ({state})")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def conflicts(changes: dict, overrides: list[Override]) -> list[str]:
    """Overridden decisions that this version changes or removes."""
    touched = {x["id"] for x in changes["decisions"]["changed"] + changes["decisions"]["removed"]}
    return [o.id for o in overrides if o.id in touched]
