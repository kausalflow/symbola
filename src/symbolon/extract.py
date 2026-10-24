"""`symbolon extract`: draft a spec pack from software someone already built.

Symbolon does not read the code itself. An external coding agent (see agent.py)
reads the product and writes the draft; this module sets up the folder, hands
over the brief, and then checks the result the way a publisher would (design
v0.5, sections 5.1 and 5.2):

  packs/<namespace>/<product>/
    versions/<n>/      the draft pack, which ships
    oracle/<name>/     adapters that run the original product as an
                       implementation of each component, which do not ship
    REVIEW.md          what the publisher must confirm before publishing
    .symbolon/         the prompt and the agent's logs

A round is one agent run followed by the checks: the pack validates, every
component contract validates, and every component passes against the original
product through its oracle adapter. When a round fails, the next round gives
the agent the failures to fix. Component digests in symbolon-pack.toml are
recomputed here, since an agent should not have to copy hashes.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .agent import PROMPT_DIR, AgentCommand, AgentRun, run_agent
from .digest import contract_digest
from .manifest import ID_RE, load_manifest
from .pack import (ASSUMPTIONS_DIR, BRIEF_FILE, COMPONENTS_DIR, OBLIGATIONS_FILE, PACK_MANIFEST_FILE,
                   VERSIONS_DIR, PackReport, _component_dirs, validate_pack)
from .spec import CheckResult
from .validate import WorkerError, check_impl, validate

ORACLE_DIR = "oracle"
REVIEW_FILE = "REVIEW.md"
AGENTS_FILE = "AGENTS.md"

PACK_MANIFEST = '''\
[pack]
id = "{id}"
version = {version}
title = "TODO: one line on what the product is"
license = "TODO"
authors = ["TODO"]

# Recomputed by `symbolon extract` from components/; no need to edit by hand.
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

OBLIGATIONS = '''\
# Obligations of the {id} spec pack (format: docs/PACK_FORMAT.md).
#
# Each obligation is one decision a builder could get wrong, with the checks
# that pin it down. status: decided (required), default (chosen; a fork may
# change it with a note), open (deliberately undecided; builds may differ).
# Checks are "<component>#example:<line in examples.jsonl>" or
# "<component>#<property test name>".
'''

AGENTS = '''\
# AGENTS.md

This is a Symbolon spec pack. Build from it; do not look for the original source.

1. Read `BRIEF.md`: what the product is, its non-goals and priorities.
2. Read `assumptions/`: what you may take as true about the world. Don't build for cases they rule out.
3. Read `obligations.toml`: the decisions you must keep. Obligations marked `open` are yours to choose.
4. Each component's full specification is `components/<name>/versions/<n>/`: `symbolon.toml`
   (the description), `schema.py`, `examples.jsonl` and `properties.py`. Where the
   description and an example seem to disagree, the example is what the original does.

**Harness.** An implementation is a directory with `symbolon-impl.toml`
(`symbolon impl-init <dir> --contract components/<name>/versions/<n>`). In Python, define
`run(input)` returning the contract's output; in any other language, a program
that reads one JSON input per line on stdin and writes `{{"output": ...}}` per line.

**Done** means `symbolon attest components/<name>/versions/<n> <impl-dir>` reports PASSED
for every component. Don't special-case the examples: the properties generate
other inputs, and the publisher keeps a holdout. Write questions about unclear
parts, and the reading you chose, in `NOTES.md` next to your build.

**If the spec contradicts itself**, don't code around it. Run
`symbolon flag <component>#example:<line> "<what disagrees, and the reading you chose>" --dir <impl-dir>`,
build the reading you think is right, and carry on.
'''

PROMPT = '''\
You are drafting a Symbolon spec pack from an existing product. Symbolon is a
registry of checkable contracts: other AI agents will rebuild this product from
the pack alone, without its source, and the pack's checks decide whether a
rebuild is faithful.

The product's source is at: {source}
Read it, its docs and its tests. Do not modify anything there.
Your working directory is: {workdir}
{hint}
Write these files, relative to your working directory:

  {pack}/                         the pack (already scaffolded: fill in the TODOs)
    {manifest}             [pack] title, license, authors. Leave [components] alone.
    {brief}                       purpose; "Non-goals"; "Priorities" (ordered); "Who resolves gaps"
    {agents}                      guide for builders (already written; adjust only if needed)
    {assumptions}/<name>.toml       what the product relies on about the world but never checks
    {obligations}              the decisions a rebuild must keep
    {components}/<name>/{versions}/1/  one capability contract per component
  {oracle}/<name>/                 an adapter per component that runs the ORIGINAL product's
                                  code as an implementation of that component's contract
  {review}                       questions the publisher must answer before publishing

## Be minimal

AI builders fill gaps well. A pack holds only what a competent builder could not
decide alone: the points where good builders would choose differently and the
publisher would reject one choice, facts about the world no builder can infer,
and a check for each. Do not spell out what any good builder would do anyway.
Pick a handful of pure, well-bounded components that carry the product's
non-obvious behaviour (parsing, ranking, formats, merge rules, naming,
authorisation, audit events). Do not try to cover the whole product.

## Components (capability contracts)

Each `{components}/<name>/{versions}/1/` has:
  symbolon.toml    [contract] id = "{namespace}/<name>", version = 1, title, description
                   (the prose half of the spec: state the rules exactly), regenerability =
                   "disposable", license, authors; [entrypoint] function = "run";
                   [requires] network/credentials/state/permissions = [];
                   [spec] seed = 0, max_examples = 200. Unknown keys are errors.
  schema.py        pydantic models `Input` and `Output`
  schema/*.json    generated: run `symbolon schema <dir>`
  examples.jsonl   one {{"input": ..., "output": ...}} or {{"input": ..., "raises": "ValueError"}}
                   per line. RECORD outputs by running the original code through your
                   oracle adapter; never write them from your reading of the code.
  properties.py    hypothesis properties: functions named test_* whose first parameter is
                   `impl` (call impl(input_dict), get a validated Output). No @settings.
  fixtures/*.json  optional shared sample data, referenced as {{"$fixture": "name.json"}}
  mutants/*.py     optional plausible wrong implementations, each with a docstring
                   naming the concern; the spec must reject every one

Contracts are language-neutral: inputs and outputs are plain JSON values.

## Oracle adapters

`{oracle}/<name>/` is an implementation directory with `symbolon-impl.toml`
(create it with `symbolon impl-init {oracle}/<name> --contract <component dir>`).
For Python, the manifest's entrypoint file defines `run(input)` and calls the
original code. For any other language, set language = "command" and
command = [...]: a program that reads one JSON input per line on stdin and writes
{{"output": ...}} or {{"error": {{"type": "ValueError", "message": "..."}}}} per line.
Re-run `symbolon impl-init` after changing a contract, since it pins the digest.

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
A decided or default obligation needs at least one check, and the checks must
exist. Every example and property should trace to some obligation.

When you are unsure what the publisher wants, choose `default` and ask in {review}.

## Check your work before you finish

  symbolon schema <component dir>
  symbolon validate <component dir>              every component must be valid
  symbolon test <component dir> {oracle}/<name>   the original must pass its own spec
  symbolon pack validate {pack}

Digests in {manifest} are filled in after you finish, so `pack validate` may
report digest mismatches while you work; everything else must pass.

## {review}

List, briefly: the non-goals and priority order to confirm; each `default`
obligation and each assumption to confirm; any behaviour of the original that
looks like a bug (the spec should describe what the product should do, and the
publisher decides); and anything you left out on purpose.
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
    (pack_dir / OBLIGATIONS_FILE).write_text(OBLIGATIONS.format(**fill))
    (pack_dir / AGENTS_FILE).write_text(AGENTS.format(**fill))
    return pack_dir


def extract_prompt(source: Path, product_dir: Path, pack_dir: Path, hint: str = "") -> str:
    namespace = Path(product_dir).parent.name
    return PROMPT.format(
        source=Path(source).resolve(), workdir=Path(product_dir).resolve(),
        hint=f"\nThe publisher adds: {hint.strip()}\n" if hint.strip() else "",
        pack=pack_dir.relative_to(product_dir).as_posix(), namespace=namespace,
        manifest=PACK_MANIFEST_FILE, brief=BRIEF_FILE, agents=AGENTS_FILE, assumptions=ASSUMPTIONS_DIR,
        obligations=OBLIGATIONS_FILE, components=COMPONENTS_DIR, versions=VERSIONS_DIR,
        oracle=ORACLE_DIR, review=REVIEW_FILE)


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


def check_draft(product_dir: Path, pack_dir: Path, *, oracle: bool = True) -> tuple[list[CheckResult], PackReport]:
    """The publisher's checks on a draft: pack, each contract, and the original against each."""
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
            checks.append(CheckResult(f"{name}: original passes its spec", False,
                                      f"no oracle adapter at {ORACLE_DIR}/{name}/"))
            continue
        checks.append(_oracle_check(name, d, adapter))
    if not (Path(product_dir) / REVIEW_FILE).is_file():
        checks.append(CheckResult(f"{REVIEW_FILE} lists what the publisher must confirm", False,
                                  f"no {REVIEW_FILE} next to {VERSIONS_DIR}/"))
    return checks, pack_report


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


def extract(source: Path, pack_id: str, *, agent: AgentCommand, root: Path = Path("packs"),
            version: int = 1, hint: str = "", rounds: int = 2, timeout: int = 3600,
            oracle: bool = True, on_round=None) -> ExtractResult:
    """Have the agent draft a pack from source, then check it, for up to `rounds` agent runs."""
    source = Path(source).resolve()
    if not source.is_dir():
        raise ExtractError(f"{source} is not a directory")
    if not ID_RE.match(pack_id):
        raise ExtractError("the pack id must look like 'namespace/product'")
    if rounds < 1:
        raise ExtractError("rounds must be at least 1")
    product_dir = (Path(root) / pack_id).resolve()
    if product_dir == source or source in product_dir.parents:
        raise ExtractError("write the pack outside the product's source (see --root)")
    pack_dir = scaffold_pack(pack_id, product_dir, version)
    result = ExtractResult(product_dir, pack_dir)
    state = product_dir / PROMPT_DIR
    prompt_file = state / "extract-prompt.md"
    prompt = extract_prompt(source, product_dir, pack_dir, hint)
    for n in range(1, rounds + 1):
        if n == 1:
            run = run_agent(agent, prompt, product_dir, timeout=timeout, prompt_file=prompt_file,
                            extra_dirs=[source])
        else:
            failures = "\n".join(f"- {c.name}" + "".join(f"\n    {row}" for row in c.detail.splitlines())
                                 for c in result.rounds[-1].checks if not c.ok)
            fix = FIX_PROMPT.format(workdir=product_dir, prompt_file=prompt_file, failures=failures)
            run = run_agent(agent, fix, product_dir, timeout=timeout,
                            prompt_file=state / f"extract-fix-{n}.md", extra_dirs=[source])
        log = state / f"extract-round-{n}.log"
        log.write_text(run.log())
        if run.ok:
            checks, result.pack_report = check_draft(product_dir, pack_dir, oracle=oracle)
        else:
            checks = [CheckResult(f"agent {agent.name} finished", False,
                                  f"exit {run.returncode}; see {log}")]
        result.rounds.append(ExtractRound(run, checks, log))
        if on_round:
            on_round(n, result.rounds[-1])
        if result.rounds[-1].ok or not run.ok:
            break
    return result
