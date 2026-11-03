"""`symbola extract`: draft a spec pack from software someone already built.

Symbola does not read the product itself. An external coding agent (see agent.py)
reads whatever there is about the product and writes the draft: its source code,
documents about it (manuals, help pages, changelogs, API specs, sample files), and
the running product (a URL or a command), in any mix, so a closed-source product
can be extracted too. This module sets up the folder, hands over the brief, and
then checks the result the way a publisher would (design v0.5, sections 5.1 and 5.2):

  packs/<namespace>/<product>/
    versions/<n>/      the draft pack, which ships
    oracle/<name>/     adapters that run the original product as an
                       implementation of each component, which do not ship
    REVIEW.md          what the publisher must confirm before publishing
    EVIDENCE.toml      where each obligation came from, which does not ship
    .symbolon/         the prompt and the agent's logs

A round is one agent run followed by the checks: the pack validates, every
component contract validates, every component passes against the original
product through its oracle adapter (required when there is source code to run),
every obligation names its evidence, and the pack stays within its size budget:
more sources should make a pack more accurate, not bigger. When a round fails, the next round gives
the agent the failures to fix. Component digests in symbolon-pack.toml are
recomputed here, since an agent should not have to copy hashes.
"""

from __future__ import annotations

import re
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .agent import PROMPT_DIR, AgentCommand, AgentRun, run_agent
from .digest import contract_digest
from .manifest import ID_RE, load_manifest
from .pack import (ASSUMPTIONS_DIR, BRIEF_FILE, COMPONENTS_DIR, PRODUCT_FILE, OBLIGATIONS_FILE, PACK_MANIFEST_FILE,
                   VERSIONS_DIR, PackReport, _component_dirs, validate_pack)
from .spec import CheckResult
from .validate import WorkerError, check_impl, validate

ORACLE_DIR = "oracle"
REVIEW_FILE = "REVIEW.md"
AGENTS_FILE = "AGENTS.md"
EVIDENCE_FILE = "EVIDENCE.toml"
EVIDENCE_KINDS = ("code", "docs", "observed", "interview")

# A drafted pack's size budget. The packs made so far hold 61 to 75 obligations
# and PRODUCT.md files of 1,300 to 3,000 words; a draft over these has kept
# observations a builder does not need.
DEFAULT_MAX_OBLIGATIONS = 80
DEFAULT_MAX_PRODUCT_WORDS = 2500

PACK_MANIFEST = '''\
[pack]
id = "{id}"
version = {version}
title = "TODO: one line on what the product is"
license = "TODO"
authors = ["TODO"]

# Recomputed by `symbola extract` from components/; no need to edit by hand.
[components]
'''

BRIEF = '''\
# {product}

TODO: what the product is for and who uses it, in a few short paragraphs.

## Non-goals

- TODO

## Priorities

When goals conflict, earlier ones win:

1. TODO

## Who resolves gaps

{namespace}, as the namespace holder. If the pack doesn't settle something, record the
question and the reading you chose in `NOTES.md` next to your build; obligations marked
`open` in `obligations.toml` are yours to choose.
'''

PRODUCT = '''\
# {product}: the product

TODO: what a build of the whole product is. The components are its core.

## Shape

- TODO: what kind of program it is and where it runs

## Surfaces

- TODO: each screen, command, endpoint or file users touch

## Flows

1. TODO: a thing users do, its steps, the outcome they see, and the components it uses
'''

OBLIGATIONS = '''\
# Obligations of the {id} spec pack (format: docs/PACK_FORMAT.md).
#
# Each obligation is one decision a builder could get wrong, with the checks
# that pin it down. status: decided (required), default (chosen; a fork may
# change it with a note), open (deliberately undecided; builds may differ).
# Checks are "<component>#example:<line in examples.jsonl>" or
# "<component>#<property test name>". A required obligation no check can
# express yet has checks = [] and unchecked = "<the check it would need>".
'''

AGENTS = '''\
# AGENTS.md

This is a Symbola pack. Build from it; do not look for the original source.

1. Read `BRIEF.md`: what the product is, its non-goals and priorities.
2. Read `assumptions/`: what you may take as true about the world. Don't build for cases they rule out.
3. Read `obligations.toml`: the decisions you must keep. Obligations marked `open` are yours to choose;
   ones marked `unchecked` are required although no check covers them yet.
4. Each component's full specification is `components/<name>/versions/<n>/`: `symbolon.toml`
   (the description), `schema.py`, `examples.jsonl` and `properties.py`. Where the
   description and an example seem to disagree, the example is what the original does.

**Harness.** An implementation is a directory with `symbolon-impl.toml`
(`symbola impl-init <dir> --contract components/<name>/versions/<n>`). In Python, define
`run(input)` returning the contract's output; in any other language, a program
that reads one JSON input per line on stdin and writes `{{"output": ...}}` per line.
A component whose `symbolon.toml` says `driver = "cli"` is a command line: build the
real program and set `command` to it; symbola runs it once per check.

**The product.** If `PRODUCT.md` exists, the pack is a whole product: build it as
`PRODUCT.md` describes (its shape, surfaces and flows), with your component builds as
its core. Don't build a demo page around the components instead.

**Done** means `symbola attest components/<name>/versions/<n> <impl-dir>` reports PASSED
for every component and, for a product pack, every flow in `PRODUCT.md` works. Don't
special-case the examples: the properties generate other inputs, and the publisher
keeps a holdout. Write questions about unclear parts, and the reading you chose, in
`NOTES.md` next to your build.

**If the spec contradicts itself**, don't code around it. Run
`symbola flag <component>#example:<line> "<what disagrees, and the reading you chose>" --dir <impl-dir>`,
build the reading you think is right, and carry on.
'''

PROMPT = '''\
You are drafting a Symbola pack from an existing product. Symbola is a
registry of checkable contracts: other AI agents will rebuild this product from
the pack alone, without its source, and the pack's checks decide whether a
rebuild is faithful.

Your working directory is: {workdir}
{hint}
## Sources

{sources}

Use every source you were given; each settles different things:
  source code      the exact rules. Read it, its docs and its tests; change nothing there.
  documents        intent, terms, flows and formats. Changelogs and known-issue lists are
                   full of edge cases. Documents go out of date: where the code or the
                   running product disagrees with them, behaviour wins, and the clash goes
                   to {review}.
  running product  real behaviour. Use it as a user would: for a website, a headless
                   browser (Playwright: visible text, the accessibility tree, screenshots,
                   clicks, forms, the files it offers to download); for a command, run it
                   in a scratch directory. Learn from what it does rather than from its
                   shipped bundles. Use made-up data only, or the test account in the hint.
                   Survey first (every screen, command and file), then probe the edges of
                   each rule you saw: boundaries and rounding, empty and extreme values,
                   midnight, month ends, time zones and leap days, long or odd text and how
                   it comes out in exports, delete and restore, importing old, foreign or
                   hand-edited files, two sessions at once. Hidden rules show up there.
{oracle_note}

Write these files, relative to your working directory:

  {pack}/                         the pack (already scaffolded: fill in the TODOs)
    {manifest}             [pack] title, license, authors. Leave [components] alone.
    {brief}                       purpose; "Non-goals"; "Priorities" (ordered); "Who resolves gaps"
    {product}                     the whole product: "Shape", "Surfaces", "Flows" (see below)
    {agents}                      guide for builders (already written; adjust only if needed)
    {assumptions}/<name>.toml       what the product relies on about the world but never checks
    {obligations}              the decisions a rebuild must keep
    {components}/<name>/{versions}/1/  one capability contract per component
  {oracle}/<name>/                 an adapter per component that runs the ORIGINAL product's
                                  code as an implementation of that component's contract
  {review}                       questions the publisher must answer before publishing
  {evidence}                    where each obligation came from (does not ship)

## Be minimal

AI builders fill gaps well. A pack holds only what a competent builder could not
decide alone: the points where good builders would choose differently and the
publisher would reject one choice, facts about the world no builder can infer,
and a check for each. Do not spell out what any good builder would do anyway.

Specify the product at the surfaces its users rely on (its API, file formats,
command line, the results it reports), not at internal seams: a component at an
internal seam forces builders into the original's architecture. Pick a handful
of components that carry the product's non-obvious behaviour (parsing, ranking,
formats, merge rules, naming, authorisation, audit events). Do not try to cover
everything, but do not leave out a surface because it is not a pure function:
an adapter can drive a command line in a scratch directory or a whole run, and a
property can hold for every seed of a random process. Leave out what concerns
only the original's own codebase (its module layout, naming, code style).

More sources make a pack more accurate, not bigger. Keep at most {max_obligations}
obligations and {max_product_words} words in {product}; these are checked. An observation
earns an obligation only if two good builders would differ on it and the publisher
would reject one of them. Leave out labels, wording, button order, presets, colours
and layout unless users would reject a build without them, and merge obligations
that are one decision. Everything else you learned stays in {evidence} or nowhere.

## {product}

The components alone are not the product: an agent asked to build the product from
them invents everything else. {product} says what a build of the whole product is,
written from the product's own README and docs (summarise them; do not re-read the
code for it). Keep it to what a builder could not guess:
  ## Shape      what kind of program it is, where it runs, what it needs (no server,
                a CLI, a service), and the stack choices users would notice
  ## Surfaces   every screen, command, endpoint and file users touch, one line each
  ## Flows      the main things users do, each as steps and the outcome they see,
                naming the component each step uses
  ## Interfaces outside services, plugin or storage interfaces, credentials
  ## Order      optional: what to build first when a build cannot do it all
State rules exactly only where they matter; leave layout and styling to the builder.

## Components (capability contracts)

Each `{components}/<name>/{versions}/1/` has:
  symbolon.toml    [contract] id = "{namespace}/<name>", version = 1, title, description
                   (the prose half of the spec: state the rules exactly), regenerability =
                   "disposable", license, authors; [entrypoint] function = "run";
                   [requires] network/credentials/state/permissions = [];
                   [spec] seed = 0, max_examples = 200. Unknown keys are errors.
  schema.py        pydantic models `Input` and `Output`
  schema/*.json    generated: run `symbola schema <dir>`
  examples.jsonl   one {{"input": ..., "output": ...}} or {{"input": ..., "raises": "ValueError"}}
                   per line. RECORD outputs from the original: through your oracle adapter,
                   or from what the running product showed or produced. Never write them
                   from your reading of the code or the documents.
  properties.py    hypothesis properties: functions named test_* whose first parameter is
                   `impl` (call impl(input_dict), get a validated Output). No @settings.
                   A rule about a distribution (noise, sampling) is a statistical property:
                   test_*(impl, seed) returns a number per run, and [spec.statistical.<name>]
                   gives at_least and/or at_most for its mean over seeds; mark its
                   obligation exactness = "statistical".
  fixtures/*.json  optional shared sample data, referenced as {{"$fixture": "name.json"}}
  mutants/*.py     optional plausible wrong implementations, each with a docstring
                   naming the concern; the spec must reject every one

Contracts are language-neutral: inputs and outputs are plain JSON values.

## Oracle adapters

`{oracle}/<name>/` is an implementation directory with `symbolon-impl.toml`
(create it with `symbola impl-init {oracle}/<name> --contract <component dir>`).
For Python, the manifest's entrypoint file defines `run(input)` and calls the
original code. For any other language, set language = "command" and
command = [...]: a program that reads one JSON input per line on stdin and writes
{{"output": ...}} or {{"error": {{"type": "ValueError", "message": "..."}}}} per line.
Re-run `symbola impl-init` after changing a contract, since it pins the digest.

For a command line, give the component `[entrypoint] driver = "cli"`: `Input` is
`argv`, `files` (name -> text) and `stdin`; symbola runs the program once per call
in a scratch directory holding `files`, and `observe.py` defines
`observe(input, result)`, turning `result` = {{exit_code, stdout, stderr, files (created or
changed)}} into the `Output` to compare. The oracle is then just language = "command",
command = ["<the original program>"], and builders ship only their real program.

## Assumptions

`{assumptions}/<name>.toml`: id = "K-<name>", statement, basis (why it holds),
monitor (how a deployment could watch it, or "none"). Look for what the code
relies on but never checks, e.g. no locking around writes suggests a
single-writer assumption.

## Obligations

`{obligations}` holds [[obligation]] tables:
  id = "area.name"            dot-separated lowercase words
  statement = "..."           one decision, stated exactly
  status = "decided" | "default" | "open"
                              decided: required. default: your best guess at the
                              publisher's choice; they confirm it. open: deliberately
                              undecided, so it has no checks.
  source = "extract"
  kind = "behaviour" | "constraint" | "security" | "audit"   (constraint needs reason = "...")
  assumes = ["K-..."]         optional
  checks = ["<name>#example:<line>", "<name>#test_<property>"]
  unchecked = "..."           only when no example or property can check it: the
                              kind of check it would need (then checks = [])
A decided or default obligation needs at least one check, and the checks must
exist; `unchecked` is for a requirement the publisher would hold a build to but
no example or property can express (at most a tenth of them). Every example and
property should trace to some obligation.

Leave nothing unclear unmarked; people review it after you (`symbola pack review`):
  - the sources settle it: decided
  - they lean one way but the publisher may want otherwise: default (they confirm or reject it)
  - they don't settle it and a wrong guess would matter: a question (below)
  - builds may reasonably differ: open

A gap no source settles, where a wrong guess would matter, is a question rather than an
obligation: add it to {pack}/{questions} and the publisher answers it with
`symbola pack answer`, which writes the obligation and its example. One question:

  [[question]]
  id = "area.name"                 # the obligation id the answer becomes
  ask = "One concrete situation, as the publisher would see it?"
  component = "<name>"             # where the example goes; leave out for the product as a whole
  input = '{{"...": "..."}}'          # the component input, as JSON
  unchecked = "..."                # only without a component: the check it would need
  recommended = "a"
  [[question.choice]]
  key = "a"
  label = "short answer"
  statement = "the obligation, if chosen"
  output = '{{"...": "..."}}'         # or raises = "ValueError"; leave out without a component

## {evidence}

One entry per obligation, naming where it came from, each item starting with its kind
({kinds}):

  [evidence]
  "area.name" = ["code: src/merge.ts, mergeLists", "observed: restored a v2 backup; it was upgraded"]

## Check your work before you finish

  symbola schema <component dir>
  symbola validate <component dir>              every component must be valid
  symbola test <component dir> {oracle}/<name>   the original must pass its own spec
  symbola pack validate {pack}

Digests in {manifest} are filled in after you finish, so `pack validate` may
report digest mismatches while you work; everything else must pass.

## {review}

List, briefly: the non-goals and priority order to confirm; each `default`
obligation and each assumption to confirm; any behaviour of the original that
looks like a bug (the spec should describe what the product should do, and the
publisher decides); where the sources disagreed; what you could not see (with
the access that would show it, such as a test account or an API key); and
anything you left out on purpose.
'''

FIX_PROMPT = '''\
Your draft of the spec pack in {workdir} does not pass yet. Fix the problems
below, keeping the rest of the draft as it is, and run the same checks again
before you finish. The instructions you were given are in {prompt_file}.

{failures}
'''


class ExtractError(Exception):
    pass


@dataclass
class ExtractRound:
    run: AgentRun
    checks: list[CheckResult] = field(default_factory=list)
    log: Path | None = None

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)


@dataclass
class ExtractResult:
    product_dir: Path
    pack_dir: Path
    rounds: list[ExtractRound] = field(default_factory=list)
    pack_report: PackReport | None = None

    @property
    def ok(self) -> bool:
        return bool(self.rounds) and self.rounds[-1].ok


def scaffold_pack(pack_id: str, product_dir: Path, version: int = 1) -> Path:
    """Write the parts of a pack that need no reading of the product."""
    namespace, product = pack_id.split("/")
    pack_dir = product_dir / VERSIONS_DIR / str(version)
    if pack_dir.exists() and any(pack_dir.iterdir()):
        raise ExtractError(f"{pack_dir} already exists; pick another --version or remove it")
    fill = {"id": pack_id, "version": version, "namespace": namespace, "product": product}
    (pack_dir / ASSUMPTIONS_DIR).mkdir(parents=True, exist_ok=True)
    (pack_dir / COMPONENTS_DIR).mkdir(exist_ok=True)
    (product_dir / ORACLE_DIR).mkdir(exist_ok=True)
    (pack_dir / PACK_MANIFEST_FILE).write_text(PACK_MANIFEST.format(**fill))
    (pack_dir / BRIEF_FILE).write_text(BRIEF.format(**fill))
    (pack_dir / PRODUCT_FILE).write_text(PRODUCT.format(**fill))
    (pack_dir / OBLIGATIONS_FILE).write_text(OBLIGATIONS.format(**fill))
    (pack_dir / AGENTS_FILE).write_text(AGENTS.format(**fill))
    return pack_dir


@dataclass
class Sources:
    """What there is about the product: its code, documents about it, the running product."""
    code: Path | None = None
    docs: list[str] = field(default_factory=list)
    live: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.code = Path(self.code).resolve() if self.code else None
        self.docs = [d if _is_url(d) else str(Path(d).resolve()) for d in self.docs]
        self.live = list(self.live)

    def check(self) -> None:
        if not (self.code or self.docs or self.live):
            raise ExtractError("give at least one source: the code, --docs or --live")
        if self.code and not self.code.is_dir():
            raise ExtractError(f"{self.code} is not a directory")
        for d in self.docs:
            if not _is_url(d) and not Path(d).exists():
                raise ExtractError(f"{d} does not exist")

    def dirs(self) -> list[Path]:
        """Local folders the agent must be allowed to read."""
        found = [self.code] if self.code else []
        for d in self.docs:
            if not _is_url(d):
                found.append(Path(d) if Path(d).is_dir() else Path(d).parent)
        return found

    def describe(self) -> str:
        rows = []
        if self.code:
            rows.append(f"  source code      {self.code}")
        rows += [f"  documents        {d}" for d in self.docs]
        rows += [f"  running product  {u}" for u in self.live]
        return "\n".join(rows)


def _is_url(s: str) -> bool:
    return bool(re.match(r"https?://", s))


def extract_prompt(sources: Sources | Path, product_dir: Path, pack_dir: Path, hint: str = "", *,
                   max_obligations: int = DEFAULT_MAX_OBLIGATIONS,
                   max_product_words: int = DEFAULT_MAX_PRODUCT_WORDS) -> str:
    from .questions import QUESTIONS_FILE  # questions imports this module
    if not isinstance(sources, Sources):
        sources = Sources(code=sources)
    namespace = Path(product_dir).parent.name
    if sources.code:
        oracle_note = ("Every component needs an oracle adapter that runs the original code (see below).")
    else:
        oracle_note = ("There is no source code here, so oracle adapters are optional: write one where the\n"
                       "running product can be driven directly (a command, an API), and otherwise record\n"
                       "examples from what you observed the product do.")
    return PROMPT.format(
        sources=sources.describe(), oracle_note=oracle_note, workdir=Path(product_dir).resolve(),
        hint=f"\nThe publisher adds: {hint.strip()}\n" if hint.strip() else "",
        pack=pack_dir.relative_to(product_dir).as_posix(), namespace=namespace,
        manifest=PACK_MANIFEST_FILE, brief=BRIEF_FILE, product=PRODUCT_FILE, agents=AGENTS_FILE,
        assumptions=ASSUMPTIONS_DIR, obligations=OBLIGATIONS_FILE, components=COMPONENTS_DIR, versions=VERSIONS_DIR,
        oracle=ORACLE_DIR, review=REVIEW_FILE, evidence=EVIDENCE_FILE, kinds=", ".join(EVIDENCE_KINDS),
        questions=QUESTIONS_FILE.as_posix(), max_obligations=max_obligations,
        max_product_words=max_product_words)


def sync_components(pack_dir: Path) -> dict[str, str]:
    """Rewrite the manifest's [components] table from the contracts under components/."""
    path = Path(pack_dir) / PACK_MANIFEST_FILE
    listed = {}
    for d in _component_dirs(Path(pack_dir).resolve()).values():
        try:
            listed[load_manifest(d).alias] = contract_digest(d)
        except Exception:
            continue  # validate reports a broken manifest
    text = path.read_text()
    match = re.search(r"^\[components\][^\n]*\n", text, re.M)
    head = text[:match.start()] if match else text.rstrip("\n") + "\n\n"
    rest = text[match.end():] if match else ""
    nxt = re.search(r"^\[", rest, re.M)
    tail = rest[nxt.start():] if nxt else ""
    table = "".join(f'"{alias}" = "{digest}"\n' for alias, digest in sorted(listed.items()))
    path.write_text(head + "[components]\n" + table + ("\n" + tail if tail else ""))
    with path.open("rb") as f:
        tomllib.load(f)  # never leave a manifest that no longer parses
    return listed


def check_draft(product_dir: Path, pack_dir: Path, *, oracle: bool = True, require_oracle: bool = True,
                max_obligations: int | None = DEFAULT_MAX_OBLIGATIONS,
                max_product_words: int | None = DEFAULT_MAX_PRODUCT_WORDS,
                evidence: bool = True) -> tuple[list[CheckResult], PackReport]:
    """The publisher's checks on a draft: pack, each contract, the original against each, evidence, size.

    `require_oracle` is off when there is no source code: then a component without an
    adapter is fine (its examples were recorded from the running product), and the
    adapters that do exist must still pass.
    """
    checks = []
    sync_components(pack_dir)
    pack_report = validate_pack(pack_dir)
    checks += [CheckResult(f"pack: {c.name}", c.ok, c.detail) for c in pack_report.checks]
    components = _component_dirs(Path(pack_dir).resolve())
    if not components:
        checks.append(CheckResult("pack has at least one component", False, f"nothing under {COMPONENTS_DIR}/"))
    for name, d in components.items():
        report = validate(d)
        failed = [c for c in report.checks if not c.ok]
        checks.append(CheckResult(f"{name}: contract is valid", not failed,
                                  "\n".join(f"{c.name}: {c.detail}" for c in failed)))
        if not oracle or failed:
            continue
        adapter = Path(product_dir) / ORACLE_DIR / name
        if not adapter.exists():
            if require_oracle:
                checks.append(CheckResult(f"{name}: original passes its spec", False,
                                          f"no oracle adapter at {ORACLE_DIR}/{name}/"))
            continue
        checks.append(_oracle_check(name, d, adapter))
    if not (Path(product_dir) / REVIEW_FILE).is_file():
        checks.append(CheckResult(f"{REVIEW_FILE} lists what the publisher must confirm", False,
                                  f"no {REVIEW_FILE} next to {VERSIONS_DIR}/"))
    ids = _obligation_ids(pack_dir)
    if evidence:
        checks.append(check_evidence(Path(product_dir) / EVIDENCE_FILE, ids))
    checks += check_budget(pack_dir, ids, max_obligations, max_product_words)
    checks += _check_questions(pack_dir)
    return checks, pack_report


def _obligation_ids(pack_dir: Path) -> list[str]:
    try:
        with (Path(pack_dir) / OBLIGATIONS_FILE).open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return []  # validate_pack reports it
    found = data.get("obligation", [])
    if not isinstance(found, list):
        return []  # validate_pack reports it
    return [o["id"] for o in found if isinstance(o, dict) and isinstance(o.get("id"), str) and o["id"]]


def check_evidence(path: Path, ids: list[str]) -> CheckResult:
    """Every obligation names where it came from: code, docs, observed or interview."""
    label = f"every obligation has evidence in {EVIDENCE_FILE}"
    if not path.is_file():
        return CheckResult(label, False, f"no {EVIDENCE_FILE} next to {VERSIONS_DIR}/")
    try:
        with path.open("rb") as f:
            table = tomllib.load(f).get("evidence", {})
    except tomllib.TOMLDecodeError as e:
        return CheckResult(label, False, f"{EVIDENCE_FILE} is not valid TOML: {e}")
    if not isinstance(table, dict):
        return CheckResult(label, False, "[evidence] must be a table of obligation id = [\"<kind>: <where>\", ...]")
    problems, kinds = [], Counter()
    for oid in ids:
        items = table.get(oid)
        if isinstance(items, str):
            items = [items]
        if not items:
            problems.append(f"{oid}: no evidence")
            continue
        if not isinstance(items, list):
            problems.append(f"{oid}: must be a string or a list of strings")
            continue
        for item in items:
            kind, _, where = str(item).partition(":") if isinstance(item, str) else ("", "", "")
            if kind.strip() not in EVIDENCE_KINDS or not where.strip():
                problems.append(f"{oid}: {item!r} must be '<kind>: <where>' with kind one of "
                                f"{', '.join(EVIDENCE_KINDS)}")
            else:
                kinds[kind.strip()] += 1
    stale = sorted(set(table) - set(ids))
    problems += [f"{oid}: not an obligation of the pack" for oid in stale]
    if problems:
        return CheckResult(label, False, "\n".join(problems))
    return CheckResult(label, True, ", ".join(f"{n} {k}" for k, n in sorted(kinds.items())))


def check_budget(pack_dir: Path, ids: list[str], max_obligations: int | None,
                 max_product_words: int | None) -> list[CheckResult]:
    """A drafted pack stays small: more sources should make it more accurate, not bigger."""
    checks = []
    if max_obligations is not None:
        checks.append(CheckResult(f"at most {max_obligations} obligations", len(ids) <= max_obligations,
                                  f"{len(ids)}: keep only what good builders would get differently and "
                                  "the publisher would reject; merge ones that are one decision"
                                  if len(ids) > max_obligations else f"{len(ids)}"))
    product = Path(pack_dir) / PRODUCT_FILE
    if max_product_words is not None and product.is_file():
        words = len(product.read_text().split())
        checks.append(CheckResult(f"{PRODUCT_FILE} has at most {max_product_words} words",
                                  words <= max_product_words,
                                  f"{words}: cut what a builder would do anyway (labels, layout, wording)"
                                  if words > max_product_words else f"{words}"))
    return checks


def _check_questions(pack_dir: Path) -> list[CheckResult]:
    from .questions import QuestionError, load_questions, questions_path
    if not questions_path(pack_dir).is_file():
        return []
    try:
        found = load_questions(pack_dir)
    except QuestionError as e:
        return [CheckResult("questions for the publisher are well-formed", False, str(e))]
    return [CheckResult("questions for the publisher are well-formed", True, f"{len(found)} to answer")]


def _oracle_check(name: str, contract_dir: Path, adapter: Path) -> CheckResult:
    label = f"{name}: original passes its spec"
    try:
        result = check_impl(contract_dir, adapter)
    except WorkerError as e:
        return CheckResult(label, False, str(e))
    if "error" in result:
        return CheckResult(label, False, f"could not load the adapter: {result['error']}")
    cases = result["examples"] + result["properties"]
    failed = [c for c in cases if not c["ok"]]
    detail = "\n".join(f"{c['name']}: {c['detail']}" for c in failed[:10])
    if len(failed) > 10:
        detail += f"\n... and {len(failed) - 10} more"
    return CheckResult(label, bool(result.get("passed")), detail or f"{len(cases)} checks")


def extract(source: Path | None, pack_id: str, *, agent: AgentCommand, root: Path = Path("packs"),
            version: int = 1, hint: str = "", rounds: int = 2, timeout: int = 3600,
            oracle: bool = True, on_round=None, docs: list[str] = (), live: list[str] = (),
            max_obligations: int | None = DEFAULT_MAX_OBLIGATIONS,
            max_product_words: int | None = DEFAULT_MAX_PRODUCT_WORDS) -> ExtractResult:
    """Have the agent draft a pack from what there is about a product, then check it, for up to `rounds` runs."""
    sources = Sources(code=source, docs=list(docs), live=list(live))
    sources.check()
    if not ID_RE.match(pack_id):
        raise ExtractError("the pack id must look like 'namespace/product'")
    if rounds < 1:
        raise ExtractError("rounds must be at least 1")
    product_dir = (Path(root) / pack_id).resolve()
    code = sources.code
    if code and (product_dir == code or code in product_dir.parents):
        raise ExtractError("write the pack outside the product's source (see --root)")
    pack_dir = scaffold_pack(pack_id, product_dir, version)
    result = ExtractResult(product_dir, pack_dir)
    state = product_dir / PROMPT_DIR
    prompt_file = state / "extract-prompt.md"
    budget = {"max_obligations": max_obligations, "max_product_words": max_product_words}
    prompt = extract_prompt(sources, product_dir, pack_dir, hint,
                            max_obligations=max_obligations or DEFAULT_MAX_OBLIGATIONS,
                            max_product_words=max_product_words or DEFAULT_MAX_PRODUCT_WORDS)
    extra = sources.dirs()
    for n in range(1, rounds + 1):
        if n == 1:
            run = run_agent(agent, prompt, product_dir, timeout=timeout, prompt_file=prompt_file,
                            extra_dirs=extra)
        else:
            failures = "\n".join(f"- {c.name}" + "".join(f"\n    {row}" for row in c.detail.splitlines())
                                 for c in result.rounds[-1].checks if not c.ok)
            fix = FIX_PROMPT.format(workdir=product_dir, prompt_file=prompt_file, failures=failures)
            run = run_agent(agent, fix, product_dir, timeout=timeout,
                            prompt_file=state / f"extract-fix-{n}.md", extra_dirs=extra)
        log = state / f"extract-round-{n}.log"
        log.write_text(run.log())
        if run.ok:
            checks, result.pack_report = check_draft(product_dir, pack_dir, oracle=oracle,
                                                     require_oracle=sources.code is not None, **budget)
        else:
            checks = [CheckResult(f"agent {agent.name} finished", False,
                                  f"exit {run.returncode}; see {log}")]
        result.rounds.append(ExtractRound(run, checks, log))
        if on_round:
            on_round(n, result.rounds[-1])
        if result.rounds[-1].ok or not run.ok:
            break
    return result
