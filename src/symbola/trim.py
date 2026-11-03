"""`symbola blueprint trim`: slim a pack, with the publisher approving every cut.

A pack should hold only what a builder could get wrong, but packs grow: extract
keeps observations, prose restates obligations, examples repeat. Trimming has
three steps, and nothing leaves the pack without the publisher saying so:

1. Propose. Cheap screens that run no agent find likely cuts:
     example     an example line with the same input and result as an earlier one
     obligation  an obligation whose statement and checks another obligation already holds
     prose       a sentence in PRODUCT.md or a component description that restates
                 an obligation, so the obligation and its checks already carry it
   With `--deep`, one run of the publisher's coding agent proposes more, such as
   presentation details and prose that examples already pin down. It reads a copy
   and only writes proposals; symbola checks each one before listing it.
   Proposals go to `<pack>/.symbolon/trim.toml`, which never ships.
2. Review. The undecided proposals show in `symbola blueprint review`, with what would go
   and why. The publisher approves each (`--cut ID`) or rejects it (`--keep ID`).
3. Apply. Only "cut" proposals are applied. Cutting an obligation also removes
   the examples and properties no other obligation uses; example references are
   renumbered and digests synced. The result must pass `blueprint validate`, or
   nothing is written. A released version is frozen, so it is trimmed into a
   copy (`--out`) that is then released as the next version.

Lessons this follows (the lightkone ablation and trim): prose whose fact no check
pins down is load-bearing, so the screens only cut prose an obligation restates;
obligations that builders disagreed on (source "replication" or "counterexample")
are never proposed; and a trimmed pack is worth one `symbola replicate` build
before release, since a screen is not proof.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import tempfile
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .agent import PROMPT_DIR, AgentCommand, AgentRun, run_agent
from .pack import BRIEF_FILE, OBLIGATIONS_FILE, PRODUCT_FILE, VERSIONS_DIR, _component_dirs, validate_pack

TRIM_FILE = Path(PROMPT_DIR) / "trim.toml"
AGENT_FILE = Path(PROMPT_DIR) / "trim-proposals.toml"
KINDS = ("example", "obligation", "prose")
DECISIONS = ("undecided", "cut", "keep")
# The size budget extract drafts to (symbola PR #50); trim reports against it.
MAX_OBLIGATIONS = 80
MAX_PRODUCT_WORDS = 2500
# A sentence restates an obligation when this share of its content words is in
# the obligation's statement, and it has at least MIN_WORDS of them.
RESTATE_SHARE = 0.75
MIN_WORDS = 6
# An obligation repeats another when this share of its words is in the other's
# statement and all its checks are among the other's.
REPEAT_SHARE = 0.8
PROTECTED_SOURCES = {"replication", "counterexample"}

_STOP = set("""the a an and or of to in on for is are be it its as by with that this from at not no any each
when then than if else only all one can may must which who what was were has have had their them they into
out but so do does via per also more most other such same both own""".split())


class TrimError(Exception):
    pass


@dataclass
class Cut:
    id: str
    kind: str
    file: str            # relative to the pack
    text: str            # exactly what goes: the sentence, the obligation's statement, the example line
    why: str
    obligation: str = ""  # kind obligation: its id
    component: str = ""   # kind example
    line: int = 0         # kind example: 1-based line in examples.jsonl
    same_as: int = 0      # kind example: the line that stays, whose references take this one's
    also: list[str] = field(default_factory=list)  # kind obligation: checks that go with it
    by: str = "screen"    # screen | agent
    decision: str = "undecided"
    applied: bool = False

    @property
    def words(self) -> int:
        return len(self.text.split())

    def where(self) -> str:
        if self.kind == "example":
            return f"{self.component} example {self.line}"
        if self.kind == "obligation":
            return f"obligation {self.obligation}"
        return self.file


def _cut_id(kind: str, *parts) -> str:
    h = hashlib.sha256("\0".join(str(p) for p in (kind, *parts)).encode()).hexdigest()[:8]
    return f"{kind}-{h}"


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9_]+(?:[-.:/][a-z0-9_]+)*", text.lower())
            if len(w) > 2 and w not in _STOP}


def _share(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a) if a else 0.0


# ---------------------------------------------------------------- reading a pack

def _obligations(pack: Path) -> list[dict]:
    with (pack / OBLIGATIONS_FILE).open("rb") as f:
        found = tomllib.load(f).get("obligation", [])
    return [o for o in found if isinstance(o, dict) and isinstance(o.get("id"), str)]


def _prose_files(pack: Path) -> list[tuple[str, str]]:
    """(relative path, text) for PRODUCT.md and every component's description."""
    out = []
    if (pack / PRODUCT_FILE).is_file():
        out.append((PRODUCT_FILE, (pack / PRODUCT_FILE).read_text()))
    for d in _component_dirs(pack).values():
        manifest = d / "symbolon.toml"
        try:
            with manifest.open("rb") as f:
                text = tomllib.load(f).get("contract", {}).get("description", "")
        except (OSError, tomllib.TOMLDecodeError):
            continue
        out.append((manifest.relative_to(pack).as_posix(), text))
    return out


_UNIT_START = re.compile(r"^\s*(?:[-*+] |\d+[.)] |#|\||>)")


def sentences(text: str) -> list[str]:
    """Sentences of prose, each exactly as it appears in the text (line breaks kept).

    Headings, tables, quotes and code blocks are skipped; a bullet is its own unit.
    """
    units, cur, fence = [], [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
            cur and units.append(cur)
            cur = []
            continue
        if fence:
            continue
        if not line.strip() or _UNIT_START.match(line):
            cur and units.append(cur)
            cur = []
            if not line.strip() or re.match(r"^\s*(?:#|\||>)", line):
                continue
            line = re.sub(r"^\s*(?:[-*+] |\d+[.)] )", "", line)
        cur.append(line)
    cur and units.append(cur)
    out = []
    for unit in units:
        out += _split("\n".join(unit).strip())
    return out


_CLOSE = {"(": ")", "[": "]", "{": "}"}


def _split(body: str) -> list[str]:
    """Split at a full stop, ! or ? followed by space and a capital, outside code, quotes and brackets."""
    out, start, code, quote, depth = [], 0, False, False, []
    for i, ch in enumerate(body):
        if ch == "`":
            code = not code
        elif code:
            continue
        elif ch == '"':
            quote = not quote
        elif ch in _CLOSE:
            depth.append(_CLOSE[ch])
        elif depth and ch == depth[-1]:
            depth.pop()
        elif ch in ".!?" and not quote and not depth:
            m = re.match(r"\s+(?=[A-Z`\"(*\[])", body[i + 1:])
            if m and not re.search(r"(?:\b(?:e\.g|i\.e|etc|vs|cf)|\.\.)$", body[start:i]):
                out.append(body[start:i + 1])
                start = i + 1 + m.end()
    out.append(body[start:])
    return [s for s in out if s.strip()]


# ---------------------------------------------------------------- screens

def screen(pack: Path) -> list[Cut]:
    """Likely cuts, found without running an agent or any contract code."""
    pack = Path(pack).resolve()
    return _duplicate_examples(pack) + _repeated_obligations(pack) + _restated_prose(pack)


def _duplicate_examples(pack: Path) -> list[Cut]:
    cuts = []
    for name, d in _component_dirs(pack).items():
        path = d / "examples.jsonl"
        if not path.is_file():
            continue
        seen: dict[str, int] = {}
        for n, raw in enumerate(path.read_text().split("\n"), 1):
            if not raw.strip():
                continue
            try:
                ex = json.loads(raw)
            except json.JSONDecodeError:
                continue
            key = json.dumps({k: ex.get(k) for k in ("input", "output", "raises")}, sort_keys=True)
            if key in seen:
                cuts.append(Cut(_cut_id("example", name, raw), "example", path.relative_to(pack).as_posix(),
                                raw, f"same input and result as example {seen[key]}", component=name,
                                line=n, same_as=seen[key]))
            else:
                seen[key] = n
    return cuts


def _repeated_obligations(pack: Path) -> list[Cut]:
    obligations = [o for o in _obligations(pack) if o.get("status") != "open"]
    cuts, gone = [], set()
    for a in obligations:
        if a.get("source") in PROTECTED_SOURCES:
            continue
        wa = _words(a.get("statement", ""))
        for b in obligations:
            if b is a or b["id"] in gone or len(b.get("statement", "")) < len(a.get("statement", "")):
                continue
            if not set(a.get("checks", [])) <= set(b.get("checks", [])):
                continue
            if bool(a.get("unchecked", "").strip()) and not b.get("unchecked", "").strip() and not b.get("checks"):
                continue
            if _share(wa, _words(b.get("statement", ""))) >= REPEAT_SHARE:
                cuts.append(Cut(_cut_id("obligation", a["id"]), "obligation", OBLIGATIONS_FILE,
                                a.get("statement", ""), f"{b['id']} says this and has all its checks",
                                obligation=a["id"]))
                gone.add(a["id"])
                break
    return cuts


def _restated_prose(pack: Path) -> list[Cut]:
    bound = [(o, _words(o.get("statement", ""))) for o in _obligations(pack) if o.get("status") != "open"]
    if not bound:
        return []
    cuts = []
    for rel, text in _prose_files(pack):
        raw = (pack / rel).read_text()
        for s in sentences(text):
            w = _words(s)
            if len(w) < MIN_WORDS or raw.count(s) != 1:
                continue
            o, ow = max(bound, key=lambda x: _share(w, x[1]))
            if _share(w, ow) >= RESTATE_SHARE:
                checked = ", and its checks pin it" if o.get("checks") else ""
                cuts.append(Cut(_cut_id("prose", rel, s), "prose", rel, s,
                                f"obligation {o['id']} says this{checked}"))
    return cuts


# ---------------------------------------------------------------- the deep pass

AGENT_PROMPT = '''\
You are trimming a Symbola spec pack (a blueprint) so it is simpler to build from.
Other AI agents build the product from this pack alone. A pack should hold only the
decisions a good builder could get wrong, the facts no builder could infer, and a
check for each. Your working directory is a copy of the pack: read it, change nothing
in it, and write only {out}.

Now: {obligations} obligations (budget {max_obligations}), PRODUCT.md {product_words} words
(budget {max_product_words}). These cuts are already proposed; do not repeat them:
{known}

Propose cuts the publisher would likely accept:
  - presentation details: labels, wording, button order, presets, colours and layout,
    unless users would reject a build without them
  - obligations that are really one decision with another (cut the smaller one)
  - prose in PRODUCT.md or a component's `description` (in its symbolon.toml) whose
    fact an example or property already pins down; name the check
  - examples that pin nothing another check does not already pin

Keep, whatever the budget: any fact only prose carries (a cut would lose it); obligations
whose source is "replication" or "counterexample" (builders disagreed on them); the
Shape, Surfaces and Flows a build of the whole product needs; and every assumption.
When unsure, leave it in. Propose nothing rather than something doubtful.

Write {out} as TOML, one entry per cut:

  [[cut]]
  kind = "prose"                     # prose | obligation | example
  file = "PRODUCT.md"                # prose: the file, relative to the pack
  text = """the exact text to remove, copied character for character"""
  why = "one line: why a build does not need it"

  [[cut]]
  kind = "obligation"
  obligation = "area.name"
  why = "..."

  [[cut]]
  kind = "example"
  component = "<name>"
  line = 12                          # line in that component's examples.jsonl
  why = "..."

A prose `text` must occur exactly once in its file, and is a whole sentence or bullet.
Cutting an obligation also removes the examples and properties only it uses.
'''


def deep_screen(pack: Path, agent: AgentCommand, known: list[Cut], *, timeout: int = 1800,
                log_dir: Path | None = None) -> tuple[list[Cut], list[str], AgentRun]:
    """One agent run that proposes more cuts, from a copy of the pack. Returns (cuts, rejected, run)."""
    pack = Path(pack).resolve()
    with tempfile.TemporaryDirectory(prefix="symbola-trim-") as tmp:
        work = Path(tmp) / "pack"
        shutil.copytree(pack, work, ignore=shutil.ignore_patterns(PROMPT_DIR, "__pycache__"))
        stats = budget(pack)
        prompt = AGENT_PROMPT.format(
            out=AGENT_FILE.as_posix(), known="\n".join(f"  {c.kind}: {c.where()}: {c.text[:80]}" for c in known)
            or "  (none)", max_obligations=MAX_OBLIGATIONS, max_product_words=MAX_PRODUCT_WORDS, **stats)
        run = run_agent(agent, prompt, work, timeout=timeout, prompt_file=Path(tmp) / "prompt.md")
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "trim-agent.log").write_text(run.log())
        out = work / AGENT_FILE
        if not out.is_file():
            return [], [f"the agent wrote no {AGENT_FILE.as_posix()}"], run
        try:
            with out.open("rb") as f:
                raw = tomllib.load(f).get("cut", [])
        except tomllib.TOMLDecodeError as e:
            return [], [f"{AGENT_FILE.as_posix()} is not valid TOML: {e}"], run
    cuts, rejected = [], []
    for n, entry in enumerate(raw if isinstance(raw, list) else [], 1):
        try:
            cuts.append(_checked(pack, entry))
        except TrimError as e:
            rejected.append(f"proposal {n}: {e}")
    return cuts, rejected, run


def _checked(pack: Path, entry: dict) -> Cut:
    """Turn an agent's proposal into a Cut, or say why it cannot be applied as written."""
    if not isinstance(entry, dict):
        raise TrimError("not a table")
    kind, why = entry.get("kind"), str(entry.get("why", "")).strip() or "proposed by the agent"
    if kind == "prose":
        rel, text = str(entry.get("file", "")), str(entry.get("text", "")).strip()
        allowed = {r for r, _ in _prose_files(pack)} | {BRIEF_FILE}
        if rel not in allowed:
            raise TrimError(f"prose can only be cut from PRODUCT.md, BRIEF.md or a component description, not {rel!r}")
        if not text or (pack / rel).read_text().count(text) != 1:
            raise TrimError(f"the text does not occur exactly once in {rel}")
        return Cut(_cut_id("prose", rel, text), "prose", rel, text, why, by="agent")
    if kind == "obligation":
        oid = str(entry.get("obligation", ""))
        found = {o["id"]: o for o in _obligations(pack)}
        if oid not in found:
            raise TrimError(f"no obligation {oid!r}")
        if found[oid].get("source") in PROTECTED_SOURCES:
            raise TrimError(f"{oid} came from {found[oid]['source']}, where builders disagreed; it stays")
        return Cut(_cut_id("obligation", oid), "obligation", OBLIGATIONS_FILE, found[oid].get("statement", ""),
                   why, obligation=oid, by="agent")
    if kind == "example":
        name, line = str(entry.get("component", "")), entry.get("line")
        dirs = _component_dirs(pack)
        if name not in dirs:
            raise TrimError(f"no component {name!r}")
        lines = (dirs[name] / "examples.jsonl").read_text().split("\n")
        if not isinstance(line, int) or not 1 <= line <= len(lines) or not lines[line - 1].strip():
            raise TrimError(f"{name} has no example on line {line}")
        return Cut(_cut_id("example", name, lines[line - 1]), "example",
                   (dirs[name] / "examples.jsonl").relative_to(pack).as_posix(), lines[line - 1], why,
                   component=name, line=line, by="agent")
    raise TrimError(f"kind must be one of {', '.join(KINDS)}, not {kind!r}")


def budget(pack: Path) -> dict:
    pack = Path(pack)
    product = pack / PRODUCT_FILE
    return {"obligations": len(_obligations(pack)),
            "product_words": len(product.read_text().split()) if product.is_file() else 0}


# ---------------------------------------------------------------- the review file

HEADER = '''\
# Proposed cuts for this pack, from `symbola blueprint trim`. Nothing has been removed.
# Set each decision to "cut" or "keep" (or use `symbola blueprint trim --cut ID` / `--keep ID`), then
# `symbola blueprint trim --apply` removes the ones marked "cut", and only those.
# This file is in .symbolon/, so it never ships; keep it as the record of what was cut.
'''


def load(pack: Path) -> list[Cut]:
    path = Path(pack) / TRIM_FILE
    if not path.is_file():
        return []
    try:
        with path.open("rb") as f:
            raw = tomllib.load(f).get("cut", [])
    except tomllib.TOMLDecodeError as e:
        raise TrimError(f"{TRIM_FILE.as_posix()} is not valid TOML: {e}") from None
    cuts = []
    for entry in raw:
        try:
            cut = Cut(**entry)
        except TypeError as e:
            raise TrimError(f"{TRIM_FILE.as_posix()}: {e}") from None
        if cut.decision not in DECISIONS:
            raise TrimError(f"{TRIM_FILE.as_posix()}: {cut.id}: decision must be one of "
                            f"{', '.join(DECISIONS)}, not {cut.decision!r}")
        cuts.append(cut)
    return cuts


def save(pack: Path, cuts: list[Cut]) -> Path:
    path = Path(pack) / TRIM_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
    defaults = asdict(Cut("", "", "", "", ""))
    for c in cuts:
        rows = ["[[cut]]"]
        for k, v in asdict(c).items():
            if k in ("id", "kind", "file", "text", "why", "decision") or v != defaults[k]:
                rows.append(f"{k} = {json.dumps(v, ensure_ascii=False)}")
        blocks.append("\n".join(rows))
    path.write_text(HEADER + "\n" + "\n\n".join(blocks) + ("\n" if blocks else ""))
    load(pack)  # never leave a file that does not read back
    return path


def propose(pack: Path, new: list[Cut]) -> list[Cut]:
    """Merge new proposals into the review file, keeping every decision already made."""
    pack = Path(pack)
    old = load(pack)
    by_id = {c.id: c for c in old}
    merged = list(old)
    for c in new:
        if c.id not in by_id:
            merged.append(c)
            by_id[c.id] = c
    save(pack, merged)
    return merged


def decide(pack: Path, ids: list[str], decision: str) -> list[Cut]:
    """Record the publisher's decision ("cut" or "keep") on proposals, by id."""
    if decision not in ("cut", "keep"):
        raise TrimError('a decision is "cut" or "keep"')
    if not ids:
        return []
    cuts = load(pack)
    by_id = {c.id: c for c in cuts}
    unknown = [i for i in ids if i not in by_id]
    if unknown:
        raise TrimError(f"no proposal {', '.join(unknown)} in {TRIM_FILE.as_posix()}; run `symbola blueprint trim` first")
    done = [i for i in ids if by_id[i].applied]
    if done:
        raise TrimError(f"already applied: {', '.join(done)}")
    for i in ids:
        by_id[i].decision = decision
    save(pack, cuts)
    return [by_id[i] for i in ids]


def undecided(pack: Path) -> list[Cut]:
    return [c for c in load(pack) if c.decision == "undecided" and not c.applied]


# ---------------------------------------------------------------- applying

@dataclass
class Applied:
    cuts: list[Cut]
    removed_examples: dict[str, list[int]]
    removed_properties: dict[str, list[str]]
    before: dict
    after: dict
    target: Path


def released(pack: Path) -> bool:
    """Whether this folder is a version already frozen in a registry (listed in digests.txt)."""
    pack = Path(pack).resolve()
    digests = pack.parent.parent / "digests.txt"
    if pack.parent.name != VERSIONS_DIR or not digests.is_file():
        return False
    return any(line.split()[:1] == [pack.name] for line in digests.read_text().splitlines())


def apply(pack: Path, out: Path | None = None) -> Applied:
    """Apply the cuts marked "cut" to the pack (or to a copy at `out`). All or nothing."""
    from .extract import sync_components  # extract imports agent and validate; keep trim light

    pack = Path(pack).resolve()
    cuts = load(pack)
    chosen = [c for c in cuts if c.decision == "cut" and not c.applied]
    if out is None and released(pack):
        raise TrimError(f"{pack} is a released version, which is frozen; pass --out <folder> to write "
                        "the trimmed copy there, then release it as the next version")
    if out is not None and Path(out).exists():
        raise TrimError(f"{out} exists; give a new folder")
    if not chosen:
        raise TrimError("nothing is marked \"cut\"; review the proposals first")
    before = budget(pack)
    with tempfile.TemporaryDirectory(prefix="symbola-trim-") as tmp:
        work = Path(tmp) / "pack"
        shutil.copytree(pack, work, ignore=shutil.ignore_patterns("__pycache__"))
        examples, properties = _apply(work, chosen)
        sync_components(work)
        report = validate_pack(work)
        if not report.ok:
            bad = "\n".join(f"{c.name}: {c.detail}" for c in report.checks if not c.ok)
            raise TrimError(f"the trimmed Blueprint would not validate, so nothing was changed:\n{bad}")
        for c in chosen:
            c.applied = True
        save(work, [c if c.id not in {x.id for x in chosen} else next(x for x in chosen if x.id == c.id)
                    for c in cuts])
        after = budget(work)
        target = Path(out).resolve() if out is not None else pack
        if out is not None:
            shutil.copytree(work, target)
        else:
            _sync_back(work, pack)
    return Applied(chosen, examples, properties, before, after, target)


def _sync_back(work: Path, pack: Path) -> None:
    for path in work.rglob("*"):
        if path.is_file():
            dest = pack / path.relative_to(work)
            if not dest.is_file() or dest.read_bytes() != path.read_bytes():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, dest)


def _apply(pack: Path, chosen: list[Cut]) -> tuple[dict[str, list[int]], dict[str, list[str]]]:
    dirs = _component_dirs(pack)
    obligations = _obligations(pack)
    cut_ids = {c.obligation for c in chosen if c.kind == "obligation"}
    for oid in cut_ids:
        if oid not in {o["id"] for o in obligations}:
            raise TrimError(f"obligation {oid} is no longer in {OBLIGATIONS_FILE}; propose again")
    kept_refs = {r for o in obligations if o["id"] not in cut_ids for r in o.get("checks", [])}

    # What goes from each component: lines, with the line that takes over each one's references.
    drop: dict[str, dict[int, int]] = {}
    props: dict[str, list[str]] = {}
    for c in chosen:
        if c.kind == "example":
            if c.component not in dirs:
                raise TrimError(f"{c.id}: no component {c.component}")
            lines = (dirs[c.component] / "examples.jsonl").read_text().split("\n")
            if not 1 <= c.line <= len(lines) or lines[c.line - 1] != c.text:
                raise TrimError(f"{c.id}: {c.component} example {c.line} has changed since it was proposed; "
                                "propose again")
            drop.setdefault(c.component, {})[c.line] = c.same_as
        elif c.kind == "obligation":
            o = next(o for o in obligations if o["id"] == c.obligation)
            for ref in o.get("checks", []):
                if ref in kept_refs:
                    continue
                name, _, check = ref.partition("#")
                if check.startswith("example:"):
                    drop.setdefault(name, {})[int(check.split(":")[1])] = 0
                else:
                    props.setdefault(name, []).append(check)
    for name, lines in drop.items():
        for line, same in list(lines.items()):
            while same in lines:  # a duplicate of a duplicate: follow it to the line that stays
                same = lines[same]
            lines[line] = same

    # obligations.toml: drop cut obligations, then renumber or drop references.
    path = pack / OBLIGATIONS_FILE
    text = path.read_text()
    for oid in cut_ids:
        text = _drop_obligation(text, oid)
    text = re.sub(r"(?ms)^(\s*checks\s*=\s*)(\[.*?\])", lambda m: m.group(1) + _renumber(m.group(2), drop), text)
    path.write_text(text)

    removed_examples = {}
    for name, lines in drop.items():
        if name not in dirs:
            continue
        p = dirs[name] / "examples.jsonl"
        rows = p.read_text().split("\n")
        p.write_text("\n".join(r for i, r in enumerate(rows, 1) if i not in lines))
        removed_examples[name] = sorted(lines)
    for name, tests in props.items():
        if name in dirs:
            _drop_properties(dirs[name] / "properties.py", tests)

    for c in chosen:
        if c.kind == "prose":
            p = pack / c.file
            raw = p.read_text()
            if raw.count(c.text) != 1:
                raise TrimError(f"{c.id}: the text no longer occurs exactly once in {c.file}; propose again")
            p.write_text(_remove_text(raw, c.text))
            if p.suffix == ".toml":
                try:
                    tomllib.loads(p.read_text())
                except tomllib.TOMLDecodeError as e:
                    raise TrimError(f"{c.id}: cutting it would break {c.file}: {e}") from None
    return removed_examples, props


def _drop_obligation(text: str, oid: str) -> str:
    starts = [m.start() for m in re.finditer(r"(?m)^\[\[obligation\]\]", text)] + [len(text)]
    for a, b in zip(starts, starts[1:]):
        block = text[a:b]
        if re.search(rf'(?m)^\s*id\s*=\s*"{re.escape(oid)}"', block):
            return text[:a] + text[b:]
    raise TrimError(f"obligation {oid} not found in {OBLIGATIONS_FILE}")


def _renumber(array: str, drop: dict[str, dict[int, int]]) -> str:
    refs = tomllib.loads("x = " + array)["x"]
    out = []
    for ref in refs:
        name, _, check = ref.partition("#")
        if name in drop and check.startswith("example:"):
            n = int(check.split(":")[1])
            if n in drop[name]:
                if not drop[name][n]:
                    continue
                n = drop[name][n]
            n -= sum(1 for gone in drop[name] if gone < n)
            ref = f"{name}#example:{n}"
        if ref not in out:
            out.append(ref)
    if out == refs:
        return array
    return json.dumps(out, ensure_ascii=False).replace('", "', '", "')


def _drop_properties(path: Path, tests: list[str]) -> None:
    source = path.read_text()
    tree = ast.parse(source)
    lines = source.split("\n")
    spans = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in tests:
            first = min([node.lineno] + [d.lineno for d in node.decorator_list])
            spans.append((first, node.end_lineno))
    keep = [row for i, row in enumerate(lines, 1) if not any(a <= i <= b for a, b in spans)]
    path.write_text(re.sub(r"\n{4,}", "\n\n\n", "\n".join(keep)))


def _remove_text(raw: str, text: str) -> str:
    i = raw.index(text)
    head, tail = raw[:i], raw[i + len(text):]
    if tail[:1] in (" ", "\n") and head.endswith((" ", "\n")) or not tail.strip(" ").startswith("\n"):
        tail = tail.lstrip(" ")
        if tail.startswith("\n") and head.endswith(" "):
            head = head.rstrip(" ")
    else:
        head = head.rstrip(" ")
    out = head + tail
    # A bullet or line left empty goes too.
    out = re.sub(r"(?m)^[ \t]*(?:[-*+]|\d+[.)])?[ \t]*\n(?=[ \t]*\S)", lambda m: "" if m.group(0).strip() else m.group(0), out)
    return re.sub(r"\n{3,}", "\n\n", out)
