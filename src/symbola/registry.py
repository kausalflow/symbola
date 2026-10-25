"""The static pack registry: scaffold a pack, build the site's data, pull a pack.

The registry is a folder of packs (`packs/<owner>/<name>/versions/<n>/`) turned
into static files that any web host can serve (distribution design, sections 2-4):

    index.json, llms.txt
    packs/<owner>/<name>/latest.tar.gz, latest.sha256,
                         pack.md, parts/*.md, llms.txt, files/...,
                         evidence.json, attestations/, by-digest/<digest>.tar.gz

With a files folder (`--files-out`, served from `--files-url`), only index.json and
each pack's pack.md and llms.txt stay in the site folder; the rest, which grows with
every file of every pack, goes to the files folder for a bucket, so a host's cap on
files per site does not cap the number of packs.

Only the latest version of each pack is published. Older versions stay in the
registry's git history and folders, so attestations that name them can still be
re-checked. An older version that some attestation names is also published
under by-digest/ so anyone can re-check it, but the catalog never offers it.
Holdout tests never live inside a pack folder, and the build refuses a pack
that has one.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import shutil
import tarfile
import tempfile
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import keys
from .digest import contract_files, hex_of, tree_digest
from .pack import (ASSUMPTIONS_DIR, BRIEF_FILE, COMPONENTS_DIR, OBLIGATIONS_FILE, PACK_MANIFEST_FILE,
                   VERSIONS_DIR, summary_line, validate_pack)

PACK_HEADER = b"symbolon-pack-v1\n"
PACK_REF_RE = re.compile(r"^[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$")
TARBALL_FILE = "latest.tar.gz"
SHA_FILE = "latest.sha256"
DIGESTS_FILE = "digests.txt"


class RegistryError(Exception):
    pass


def pack_digest(root: Path) -> str:
    """Content digest of a pack folder: the contract framing with a pack header."""
    return tree_digest(root, PACK_HEADER)


# ---------------------------------------------------------------- pack init

MANIFEST = '''\
[pack]
id = "{pack_id}"
version = 1
title = "{name}"
license = "Proprietary"
authors = ["{author}"]

# Who publishes this pack, shown on its registry page. The profile defaults to
# your GitHub page; support links (Buy Me a Coffee, GitHub Sponsors, Ko-fi, ...)
# are optional, at most five, https only.
# [publisher]
# name = "Your name"
# url = "https://github.com/you"
# support = [{{ label = "Buy me a coffee", url = "https://buymeacoffee.com/you" }}]

# Component contracts, as "<namespace>/<name>@<version>" = "<digest>".
# Add one with `symbola init` under components/, then list its digest here.
[components]
'''

BRIEF = '''\
# {name}

One paragraph: what the product is for and who uses it.

## Non-goals

- What it deliberately does not do.

## Priorities

1. The goal that wins when goals conflict.

## Who resolves gaps

{author} answers questions this pack does not settle.
'''

OBLIGATIONS = '''\
# The decisions a build must keep. Record a decision here when a user makes a
# choice that a good builder could not have guessed, and give it a check.
# See docs/PACK_FORMAT.md. Replace this placeholder with your first decision.

[[obligation]]
id = "example.replace-me"
statement = "Placeholder: an open decision, so builds may differ here."
status = "open"
source = "publisher"
'''

ASSUMPTION = '''\
id = "K-replace-me"
statement = "Placeholder: something that must be true about the world."
basis = "Why you believe it."
monitor = "none"
'''

AGENTS = '''\
# AGENTS.md

This is a Symbolon spec pack. If you are building from it:

1. Read `BRIEF.md`: what the product is, its non-goals and priorities.
2. Read `assumptions/`: what you may take as true about the world.
3. Read `obligations.toml`: the decisions you must keep. `open` ones are yours to choose;
   `unchecked` ones are required although no check covers them yet.
4. Each component's specification is under `components/<name>/versions/<n>/`.

**Done** means `symbola attest components/<name>/versions/<n> <impl-dir>` passes
for every component. The publisher keeps a holdout, so don't special-case examples.

If you are the publisher's coding agent, keep this pack current while you build:
when the user makes a choice you could not have guessed, add it to
`obligations.toml` with a check; when they state a fact about the world, add an
assumption; record only what the user decided, not what the code happens to do.
Keep holdout tests outside this folder. Run `symbola pack validate <this folder>`
after each change.
'''


def scaffold_pack(pack_id: str, target: Path, author: str = "you@example.com") -> Path:
    """Create a pack folder that passes `pack validate` as it stands."""
    if not PACK_REF_RE.match(pack_id):
        raise ValueError("pack id must look like 'owner/name'")
    target = Path(target)
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"{target} exists and is not empty")
    name = pack_id.split("/", 1)[1]
    files = {
        PACK_MANIFEST_FILE: MANIFEST.format(pack_id=pack_id, name=name, author=author),
        BRIEF_FILE: BRIEF.format(name=name, author=author),
        OBLIGATIONS_FILE: OBLIGATIONS,
        f"{ASSUMPTIONS_DIR}/replace-me.toml": ASSUMPTION,
        "AGENTS.md": AGENTS,
    }
    for rel, text in files.items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    (target / COMPONENTS_DIR).mkdir(exist_ok=True)
    return target


# ---------------------------------------------------------------- site build

@dataclass
class BuiltPack:
    id: str
    version: int
    digest: str
    sha256: str


def latest_version(pack_root: Path) -> Path | None:
    versions = [p for p in (pack_root / VERSIONS_DIR).glob("*") if p.is_dir() and p.name.isdigit()]
    return max(versions, key=lambda p: int(p.name)) if versions else None


def _files(root: Path) -> list[Path]:
    files = contract_files(root)
    held = [f for f in files if "holdout" in f.relative_to(root).parts]
    if held:
        raise RegistryError(f"{root}: holdout files must not be inside a pack: {held[0].relative_to(root).as_posix()}")
    return files


def make_tarball(root: Path, top: str) -> bytes:
    """A gzipped tar of the pack's files that is byte-identical on every build."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path in _files(root):
            data = path.read_bytes()
            info = tarfile.TarInfo(f"{top}/{path.relative_to(root).as_posix()}")
            info.size, info.mtime, info.mode = len(data), 0, 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", mtime=0, filename="") as gz:
        gz.write(raw.getvalue())
    return out.getvalue()


def _fence(text: str) -> str:
    ticks = "```"
    while ticks in text:
        ticks += "`"
    return ticks


DATA_SUFFIXES = {".jsonl", ".csv"}
DATA_PREVIEW_LINES = 3


def _section(root: Path, path: Path, files_prefix: str) -> str:
    rel = path.relative_to(root).as_posix()
    try:
        text = path.read_text()
    except UnicodeDecodeError:
        return f"## {rel}\n\n(binary file, {path.stat().st_size} bytes: [{rel}]({files_prefix}{rel}))\n"
    if path.suffix == ".md":
        return f"## {rel}\n\n{text.rstrip()}\n"
    lang = {".toml": "toml", ".py": "python", ".json": "json", ".jsonl": "json"}.get(path.suffix, "")
    note = ""
    if path.suffix in DATA_SUFFIXES:
        lines = text.splitlines()
        if len(lines) > DATA_PREVIEW_LINES:
            note = (f"The first {DATA_PREVIEW_LINES} of {len(lines)} lines. The rest is part of the spec "
                    f"too: read the whole file at [{rel}]({files_prefix}{rel}).\n\n")
            text = "\n".join(lines[:DATA_PREVIEW_LINES])
    fence = _fence(text)
    return f"## {rel}\n\n{note}{fence}{lang}\n{text.rstrip()}\n{fence}\n"


def _component_key(rel: str) -> str | None:
    """`components/<name>/versions/<n>/...` -> `<name>-v<n>`, or `<name>` for an unversioned component."""
    parts = rel.split("/")
    if len(parts) < 3 or parts[0] != COMPONENTS_DIR:
        return None
    if len(parts) >= 5 and parts[2] == VERSIONS_DIR:
        return f"{parts[1]}-v{parts[3]}"
    return parts[1]


INSTALL = "uv tool install git+https://github.com/kausalflow/symbolon"
DEFAULT_REGISTRY = "https://symbola.sh"
CLI_DOCS = "https://kausalflow.github.io/symbolon/cli/"


def components_of(version_dir: Path) -> list[str]:
    """The pack's contract folders, like `components/tidy/versions/1`, relative to the pack."""
    return sorted(m.parent.relative_to(version_dir).as_posix()
                  for m in Path(version_dir).glob(f"{COMPONENTS_DIR}/*/{VERSIONS_DIR}/*/symbolon.toml"))


def build_steps(pack_id: str, page: str, components: list[str], price: dict | None = None,
                registry: str = "") -> str:
    """Build instructions for a coding agent that was handed only the pack's page link."""
    token = (f" --registry {registry}" if registry.rstrip("/") not in ("", DEFAULT_REGISTRY) else "") \
        + (" --token <license>" if price else "")
    first = components[0] if components else f"{COMPONENTS_DIR}/<name>/{VERSIONS_DIR}/1"
    name = first.split("/")[1]
    listed = "".join(f"- `{c.split('/')[1]}`: `spec/{c}`\n" for c in components)
    return (
        "## Build this pack\n\n"
        f"For coding agents whose user shared {page} and wants it built. Run these steps yourself; "
        "ask the user only for the language if they have not named one.\n\n"
        f"1. Install the Symbola CLI (Python 3.11+): `{INSTALL}` (or `pipx install "
        "git+https://github.com/kausalflow/symbolon`). Not `pip install symbolon`: that PyPI name is another project.\n"
        + (f"2. Download the pack: `symbola pull {pack_id} --dest spec{token}`"
           + (" (the user buys a license on the pack page first).\n" if price else ".\n"))
        + "3. Read `spec/AGENTS.md` and follow it. Build only from `spec/`: don't look for the original "
        "product's source, the registry repository (it holds holdout tests) or other builds.\n"
        "4. Build each component in its own folder and run its checks as you go, fixing what fails:\n\n"
        f"       symbola impl-init impl/{name} --contract spec/{first}\n"
        f"       symbola test spec/{first} impl/{name}\n\n"
        "   In Python, define `run(input)` in `impl.py`: it takes and returns a dict, and raises `ValueError` "
        "for input the contract rejects. Pin third-party packages with `==` in `requirements.lock`. In another language, set `language = \"command\"` and "
        "`command = [...]` in `symbolon-impl.toml`; the program reads one JSON input per line on stdin and writes "
        "`{\"output\": ...}` per line.\n"
        f"5. When every component passes, run `symbola keygen` once, then for each component "
        f"`symbola attest spec/{first} impl/{name} -o attestations/{name}.json`. On macOS, attest needs Docker "
        "running and accepts Python, Node or a static Linux binary (for Go, `GOOS=linux`); "
        "`symbola test` runs the same checks without it.\n\n"
        "You are done when attest reports PASSED for every component. Write open questions and the readings you "
        f"chose in `NOTES.md`. Every command is described at {CLI_DOCS}.\n\n"
        + (f"Components:\n\n{listed}\n" if listed else "")
    )


def pack_markdown(root: Path, pack_id: str, version: int, digest: str, brief: bool = False,
                  site_prefix: str = "", files_prefix: str = "") -> dict[str, str]:
    """The pack as a few Markdown files an agent can read in order, keyed by path.

    `pack.md` holds the brief, assumptions, obligations and manifest, plus a list of
    the component files `parts/<component>.md`. Data files such as examples.jsonl
    show their first lines and link the raw file, so each Markdown file stays small
    enough for one read. With `brief` (a priced pack's preview), only `pack.md` is
    written and the components are named but not included.

    Links are relative unless `site_prefix` (where pack.md is served) and
    `files_prefix` (where files/ and parts/ are served) are given, both ending in "/".
    """
    here = files_prefix or ""
    files = f"{here}files/"
    top = f"{site_prefix}pack.md" if site_prefix else "../pack.md"
    part_files = files if files_prefix else "../files/"
    order = {"AGENTS.md": 0, BRIEF_FILE: 1, OBLIGATIONS_FILE: 3, PACK_MANIFEST_FILE: 4}
    core, components = [], {}
    for path in _files(root):
        key = _component_key(path.relative_to(root).as_posix())
        (components.setdefault(key, []) if key else core).append(path)
    core.sort(key=lambda p: (order.get(p.relative_to(root).as_posix(),
                                       2 if p.relative_to(root).parts[0] == ASSUMPTIONS_DIR else 5),
                             p.relative_to(root).as_posix()))
    if brief:
        listed = "".join(f"- {key}\n" for key in sorted(components))
        head = [f"# {pack_id} (version {version})\n",
                f"Pack digest: `{digest}`. This is the preview of a priced pack: the brief, assumptions, "
                "obligations and manifest. The component contracts, schemas and tests come with the "
                "purchase, in the tarball.\n"]
        if listed:
            head.append(f"## Components (in the tarball)\n\n{listed}")
        return {"pack.md": "\n".join(head + [_section(root, p, files) for p in core])}
    parts = {}
    for key, paths in sorted(components.items()):
        parts[f"parts/{key}.md"] = "\n".join(
            [f"# {pack_id} (version {version}): component {key}\n",
             f"Part of the pack at [{top}]({top}). Pack digest: `{digest}`.\n",
             f"The contract folder, to check a build against: [{key}.tar.gz]({key}.tar.gz). Unpack it, "
             f"then run `symbola impl-init <build folder> --contract <contract folder>`, `symbola keygen` "
             f"once, and `symbola attest <contract folder> <build folder>`.\n"]
            + [_section(root, p, part_files) for p in sorted(paths)])
    contents = "".join(f"- [{rel}]({here}{rel}) ({len(text.encode()) // 1024 + 1} KB)\n" for rel, text in parts.items())
    head = [f"# {pack_id} (version {version})\n",
            f"Pack digest: `{digest}`. This file holds the brief, assumptions, obligations and manifest. "
            "Each component's contract, schemas and tests are in their own file; read the ones you build. "
            f"Raw files are under [files/]({files}), and the tarball holds everything.\n"]
    if contents:
        head.append(f"## Components\n\n{contents}")
    return {"pack.md": "\n".join(head + [_section(root, p, files) for p in core]), **parts}


def _manifest(root: Path) -> dict:
    with (root / PACK_MANIFEST_FILE).open("rb") as f:
        return tomllib.load(f).get("pack", {})


CURRENCY_RE = re.compile(r"^[a-z]{3}$")


def listing_price(pack_dir: Path) -> dict | None:
    """A pack's price from `[listing]` in its manifest: price in minor units, ISO currency."""
    with (Path(pack_dir) / PACK_MANIFEST_FILE).open("rb") as f:
        listing = tomllib.load(f).get("listing", {})
    if "price" not in listing:
        return None
    price, currency = listing["price"], listing.get("currency", "")
    if not isinstance(price, int) or isinstance(price, bool) or price <= 0:
        raise RegistryError(f"{pack_dir}: [listing] price must be a positive integer in minor units (1900 = 19.00)")
    if not isinstance(currency, str) or not CURRENCY_RE.match(currency):
        raise RegistryError(f"{pack_dir}: [listing] currency must be a lowercase ISO code such as \"eur\"")
    return {"amount": price, "currency": currency}


MAX_SUPPORT_LINKS = 5


def _https(value: object) -> bool:
    return isinstance(value, str) and value.startswith("https://") and len(value) <= 300 and not any(
        c.isspace() for c in value)


def listing_publisher(pack_dir: Path, owner: str) -> dict:
    """Who publishes a pack and where to support them, from `[publisher]` in its manifest.

    The profile defaults to the owner's GitHub page. Support links are the
    publisher's own (Buy Me a Coffee, GitHub Sponsors, Ko-fi, ...); the registry
    only shows them.
    """
    with (Path(pack_dir) / PACK_MANIFEST_FILE).open("rb") as f:
        pub = tomllib.load(f).get("publisher", {})
    name = pub.get("name", owner)
    url = pub.get("url", f"https://github.com/{owner}")
    if not isinstance(name, str) or not 0 < len(name) <= 80:
        raise RegistryError(f"{pack_dir}: [publisher] name must be a string of at most 80 characters")
    if not _https(url):
        raise RegistryError(f"{pack_dir}: [publisher] url must be an https:// link")
    support = pub.get("support", [])
    if not isinstance(support, list) or len(support) > MAX_SUPPORT_LINKS:
        raise RegistryError(f"{pack_dir}: [publisher] support must be a list of at most {MAX_SUPPORT_LINKS} links")
    links = []
    for link in support:
        label = link.get("label") if isinstance(link, dict) else None
        if not isinstance(label, str) or not 0 < len(label) <= 40 or not _https(link.get("url")):
            raise RegistryError(f"{pack_dir}: each [publisher] support link needs a label (at most 40 characters) "
                                "and an https:// url")
        links.append({"label": label, "url": link["url"]})
    return {"name": name, "url": url, "support": links}


def listing_preview(pack_dir: Path, price: dict | None) -> str:
    """How much of a pack the site shows: "full", or "brief" (the default for a priced pack)."""
    with (Path(pack_dir) / PACK_MANIFEST_FILE).open("rb") as f:
        preview = tomllib.load(f).get("listing", {}).get("preview", "brief" if price else "full")
    if preview not in ("full", "brief"):
        raise RegistryError(f"{pack_dir}: [listing] preview must be \"full\" or \"brief\"")
    return preview


ATTESTATIONS_DIR = "attestations"
EVIDENCE_FILE = "evidence.json"
BY_DIGEST_DIR = "by-digest"


def _component_digests(version_dir: Path) -> dict[str, str]:
    """Contract digest (hex) -> component key (`<name>-v<n>`) for every component of a pack version."""
    from .digest import contract_digest
    found = {}
    for manifest in sorted((version_dir / COMPONENTS_DIR).glob(f"*/{VERSIONS_DIR}/*/symbolon.toml")):
        found[hex_of(contract_digest(manifest.parent))] = _component_key(
            manifest.parent.relative_to(version_dir).as_posix() + "/symbolon.toml")
    return found


def pack_evidence(pack_root: Path, latest: Path) -> dict:
    """Check every attestation beside a pack and say which pack version each one covers.

    Attestations sit in `<pack>/attestations/*.json`, with the runners' public keys
    as `*.pub`. A signature or digest that does not check is reported, never hidden.
    """
    from .attest import AttestError, verify_attestation
    folder = pack_root / ATTESTATIONS_DIR
    runners = {keys.keyid(keys.load_public(p)): p.stem for p in sorted(folder.glob("*.pub"))}
    versions = {}
    numbered = [p for p in (pack_root / VERSIONS_DIR).glob("*") if p.is_dir() and p.name.isdigit()]
    for version_dir in sorted(numbered, key=lambda p: -int(p.name)):  # a contract kept unchanged counts as the latest
        for digest, key in _component_digests(version_dir).items():
            versions.setdefault(digest, (int(version_dir.name), key))
    latest_n = int(latest.name)
    records = []
    for path in sorted(folder.glob("*.json")):
        record = {"file": f"{ATTESTATIONS_DIR}/{path.name}"}
        try:
            check = verify_attestation(json.loads(path.read_text()))
        except (AttestError, json.JSONDecodeError) as e:
            records.append({**record, "valid": False, "problems": [str(e)]})
            continue
        pred = check.predicate
        contract = next(c for c in pred["configuration"] if c["name"].startswith("contract:"))
        digest = contract["digest"]["sha256"]
        version, component = versions.get(digest, (None, None))
        if component is None:  # a contract no published version has: name it as the folder would be
            name_part, _, n = contract["name"].split(":", 1)[1].rpartition("@")
            component = f"{name_part.rsplit('/', 1)[-1]}-v{n}"
        impl = pred["symbolon"].get("implementation", {})
        impl = impl.get("implementation", impl)
        problems = list(check.problems)
        if check.keyid not in runners:
            problems.append("runner key is not published beside the pack")
        records.append({
            **record,
            "valid": not problems,
            "problems": problems,
            "contract": contract["name"].split(":", 1)[1],
            "contract_digest": f"sha256:{digest}",
            "component": component,
            "pack_version": version,
            "covers": "latest" if version == latest_n else ("older" if version else "unpublished"),
            "build": (impl.get("authors") or ["unknown"])[0],
            "implementation_digest": check.statement["subject"][0]["digest"]["sha256"],
            "result": pred["result"],
            "passed": len(pred["passedTests"]),
            "failed": pred["failedTests"],
            "runner": runners.get(check.keyid, check.keyid),
            "evidence": pred["symbolon"].get("evidence"),
            "finished": pred["symbolon"].get("finishedOn"),
        })
    good = [r for r in records if r["valid"] and r["covers"] == "latest"]
    passing = [r for r in good if r["result"] == "PASSED"]
    components = len(_component_digests(latest))
    summary = {
        "attestations": len(records),
        "invalid": sum(not r["valid"] for r in records),
        "on_latest": len(good),
        "components": components,
        "components_with_passing_build": len({r["component"] for r in passing}),
        "builds": sorted({r["build"] for r in passing}),
        "full_builds": sorted(b for b in {r["build"] for r in passing}
                              if len({r["component"] for r in passing if r["build"] == b}) == components),
        "runners": sorted({r["runner"] for r in good}),
        "newest": max((r["finished"] for r in good if r["finished"]), default=None),
    }
    return {"summary": summary, "attestations": records}


def build_site(registry: Path, out: Path, base_url: str = "",
               private_out: Path | None = None, store_url: str = "",
               files_out: Path | None = None, files_url: str = "") -> list[BuiltPack]:
    """Write the registry's static data for the latest version of every pack.

    With `files_out`, everything but index.json, llms.txt and each pack's pack.md and
    llms.txt goes there instead of `out`, for a bucket served at `files_url` (the
    module docstring). index.json then names `files_url` so `pull` goes straight there.

    A priced pack's tarball goes to `private_out` (uploaded to the store's private
    bucket) instead of the public site; everything else, including the preview and
    the tarball's sha256, stays public so buyers can check what they download.
    """
    registry, out = Path(registry), Path(out)
    if files_out is not None and not files_url:
        raise RegistryError("--files-out needs --files-url, the address the files folder is served from")
    for folder in (out, files_out):
        if folder is not None:
            if folder.exists():
                shutil.rmtree(folder)
            folder.mkdir(parents=True)
    files_url = files_url.rstrip("/")
    entries, built = [], []
    for pack_root in sorted(p for p in registry.glob("*/*") if (p / VERSIONS_DIR).is_dir()):
        owner, name = pack_root.parent.name, pack_root.name
        pack_id = f"{owner}/{name}"
        version_dir = latest_version(pack_root)
        if version_dir is None:
            continue
        report = validate_pack(version_dir)
        if not report.ok:
            bad = "; ".join(f"{c.name}: {c.detail}" for c in report.checks if not c.ok)
            raise RegistryError(f"{pack_id}: pack validate fails: {bad}")
        meta = _manifest(version_dir)
        if meta.get("id") != pack_id:
            raise RegistryError(f"{pack_id}: {PACK_MANIFEST_FILE} says id = {meta.get('id')!r}")
        version = int(version_dir.name)
        digest = pack_digest(version_dir)
        dest = out / "packs" / owner / name
        bulk = Path(files_out) / "packs" / owner / name if files_out is not None else dest
        dest.mkdir(parents=True, exist_ok=True)
        price = listing_price(version_dir)
        preview = listing_preview(version_dir, price)
        public = [p for p in _files(version_dir)
                  if preview == "full" or _component_key(p.relative_to(version_dir).as_posix()) is None]
        for path in public:
            target = bulk / "files" / path.relative_to(version_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        tarball = make_tarball(version_dir, name)
        sha = hashlib.sha256(tarball).hexdigest()
        if price:
            if private_out is None or not store_url:
                raise RegistryError(f"{pack_id}: priced, so the build needs --private-out and --store-url")
            private = Path(private_out) / "packs" / owner / name / TARBALL_FILE
            private.parent.mkdir(parents=True, exist_ok=True)
            private.write_bytes(tarball)
        else:
            (bulk / TARBALL_FILE).write_bytes(tarball)
        (bulk / SHA_FILE).write_text(f"{sha}  {TARBALL_FILE}\n")
        site_prefix = f"{base_url.rstrip('/')}/packs/{pack_id}" if base_url else f"packs/{pack_id}"
        files_prefix = f"{files_url}/packs/{pack_id}" if files_url else site_prefix
        links = (f"{site_prefix}/", f"{files_prefix}/") if files_out is not None else ("", "")
        for rel, text in pack_markdown(version_dir, pack_id, version, digest, preview == "brief", *links).items():
            target = (dest if rel == "pack.md" else bulk) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        if preview == "full":
            for manifest in sorted((version_dir / COMPONENTS_DIR).glob(f"*/{VERSIONS_DIR}/*/symbolon.toml")):
                key = _component_key(manifest.parent.relative_to(version_dir).as_posix() + "/symbolon.toml")
                (bulk / "parts" / f"{key}.tar.gz").write_bytes(make_tarball(manifest.parent, key))
        evidence = pack_evidence(pack_root, version_dir)
        older = []
        for n in sorted({r["pack_version"] for r in evidence["attestations"] if r.get("covers") == "older"}):
            old_dir = pack_root / VERSIONS_DIR / str(n)
            old_digest = pack_digest(old_dir)
            old_tarball = make_tarball(old_dir, name)
            rel = f"{BY_DIGEST_DIR}/{hex_of(old_digest)}.tar.gz"
            target = (Path(private_out) / "packs" / owner / name if price else bulk) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(old_tarball)
            older.append({"version": n, "digest": old_digest,
                          "tarball_sha256": hashlib.sha256(old_tarball).hexdigest(), "path": rel})
        for record in evidence["attestations"]:
            if record.get("pack_version"):
                record["pack_digest"] = (digest if record["pack_version"] == version else
                                         next(o["digest"] for o in older if o["version"] == record["pack_version"]))
        if evidence["attestations"]:
            (bulk / ATTESTATIONS_DIR).mkdir(parents=True, exist_ok=True)
            for path in sorted((pack_root / ATTESTATIONS_DIR).glob("*")):
                if path.suffix in (".json", ".pub"):
                    shutil.copyfile(path, bulk / ATTESTATIONS_DIR / path.name)
        (bulk / EVIDENCE_FILE).write_text(json.dumps(evidence, indent=2) + "\n")
        listed = [p.relative_to(version_dir).as_posix() for p in public]
        download = (f"buy it for {price['amount'] / 100:.2f} {price['currency'].upper()} and pull it with "
                    f"`symbola pull {pack_id} --token <license>`" if price else f"download {site_prefix}/{TARBALL_FILE}")
        page = f"{site_prefix}/" if base_url else f"the pack {pack_id}"
        (dest / "llms.txt").write_text(
            f"# {pack_id}\n\n> {meta.get('title', name)}\n\n"
            f"Version {version}, digest {digest}. {summary_line(report.summary)}.\n\n"
            + build_steps(pack_id, page, components_of(version_dir), price, base_url)
            + "## Read it online\n\n"
            f"Start with {site_prefix}/pack.md (brief, assumptions, "
            + (f"obligations, and links to one file per component under {files_prefix}/parts/), or {download}.\n\n"
               if preview == "full" else f"obligations; the components come with the purchase), or {download}.\n\n")
            + "## Files\n\n"
            + "".join(f"- [{rel}]({files_prefix}/files/{rel})\n" for rel in listed))
        entries.append({
            "id": pack_id, "version": version, "title": meta.get("title", name),
            "license": meta.get("license", ""), "authors": meta.get("authors", []),
            "digest": digest, "tarball_sha256": sha,
            "summary": report.summary, "summary_line": summary_line(report.summary),
            "files": listed, "price": price, "preview": preview,
            "publisher": listing_publisher(version_dir, owner),
            "evidence": evidence["summary"], "older": older,
        })
        built.append(BuiltPack(pack_id, version, digest, sha))
    index = {"format": 1, "packs": entries}
    if files_out is not None:
        index["files_url"] = files_url
    if store_url:
        index["store"] = store_url.rstrip("/")
    (out / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    root_prefix = base_url.rstrip("/") + "/" if base_url else ""
    (out / "llms.txt").write_text(
        "# Symbolon pack registry\n\n> Spec packs that AI coding agents can build from. "
        "Each pack holds a brief, assumptions, obligations and component contracts with tests.\n\n"
        "To build a pack, open its llms.txt below and follow its \"Build this pack\" steps. "
        f"Install the CLI with `{INSTALL}`.\n\n"
        f"Catalog as JSON: {root_prefix}index.json\n\n## Packs\n\n"
        + "".join(f"- [{e['id']}]({root_prefix}packs/{e['id']}/llms.txt): {e['title']} · {e['summary_line']}\n"
                  for e in entries))
    return built


# ---------------------------------------------------------------- release

@dataclass
class Release:
    id: str
    version: int
    digest: str
    path: Path
    created: bool


def _set_version(manifest: Path, version: int) -> None:
    text = manifest.read_text()
    new, n = re.subn(r"(?m)^version\s*=\s*\d+\s*$", f"version = {version}", text, count=1)
    if not n:
        raise RegistryError(f"{manifest}: no 'version = <n>' line under [pack]")
    manifest.write_text(new)


def _recorded_digests(pack_root: Path) -> dict[int, str]:
    path = pack_root / DIGESTS_FILE
    if not path.is_file():
        return {}
    pairs = (line.split() for line in path.read_text().splitlines() if line.strip())
    return {int(n): d for n, d in pairs}


def release(spec: Path, registry: Path) -> Release:
    """Freeze a pack folder into the registry as its next version.

    The spec folder's manifest is bumped to the new version first, so the spec and
    the frozen copy share a digest and a second release of the same content is a no-op.
    Each version's digest is appended to the pack's `digests.txt`, and `site check`
    refuses a version whose files no longer match it. Who may release is decided by
    who can merge into the registry (and, with GitHub Releases, who can release in
    the publisher's repository), not by keys of our own.
    """
    spec, registry = Path(spec), Path(registry)
    report = validate_pack(spec)
    if not report.ok:
        bad = "; ".join(f"{c.name}: {c.detail}" for c in report.checks if not c.ok)
        raise RegistryError(f"pack validate fails: {bad}")
    pack_id = _manifest(spec).get("id", "")
    if not PACK_REF_RE.match(pack_id):
        raise RegistryError(f"{PACK_MANIFEST_FILE}: id must look like 'owner/name', got {pack_id!r}")
    owner, name = pack_id.split("/")
    pack_root = registry / owner / name
    current = latest_version(pack_root)
    if current is not None:
        n = int(current.name)
        _set_version(spec / PACK_MANIFEST_FILE, n)
        if pack_digest(spec) == pack_digest(current):
            return Release(pack_id, n, pack_digest(current), current, False)
    version = int(current.name) + 1 if current is not None else 1
    _set_version(spec / PACK_MANIFEST_FILE, version)
    target = pack_root / VERSIONS_DIR / str(version)
    for path in _files(spec):
        dest = target / path.relative_to(spec)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    digest = pack_digest(target)
    with (pack_root / DIGESTS_FILE).open("a") as f:
        f.write(f"{version} {digest}\n")
    return Release(pack_id, version, digest, target, True)


def check_registry(registry: Path) -> list[str]:
    """What a submission must pass: every latest version builds, and no released version changed.

    Returns warnings for packs that have no `digests.txt` yet (made before `release` wrote one).
    """
    registry = Path(registry)
    with tempfile.TemporaryDirectory() as tmp:
        built = build_site(registry, Path(tmp) / "site", private_out=Path(tmp) / "private",
                           store_url="https://store.invalid")
    warnings = []
    for b in built:
        pack_root = registry / b.id
        recorded = _recorded_digests(pack_root)
        if not recorded:
            warnings.append(f"{b.id}: no {DIGESTS_FILE}, so edits to released versions are not caught")
            continue
        for n, expected in sorted(recorded.items()):
            actual = pack_digest(pack_root / VERSIONS_DIR / str(n))
            if actual != expected:
                raise RegistryError(f"{b.id}: version {n} was released as {expected} but is now {actual}; "
                                    "release a new version instead of editing an old one")
    return warnings


# ---------------------------------------------------------------- pull

def _base(registry: str) -> str:
    if "://" not in registry:
        registry = Path(registry).resolve().as_uri()
    return registry.rstrip("/") + "/"


def _fetch(url: str, token: str | None = None) -> bytes:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})
    try:
        with urllib.request.urlopen(request, timeout=60) as r:
            return r.read()
    except (urllib.error.URLError, OSError) as e:
        raise RegistryError(f"could not fetch {url}: {e}") from None


PAGE_RE = re.compile(r"^([a-z]+://[^?#]*?)/packs/([^/?#]+/[^/?#]+)(?:[/?#].*)?$")


def pack_ref(ref: str) -> tuple[str, str | None]:
    """`owner/name` -> (id, None); a pack page link such as https://symbola.sh/packs/owner/name/
    (or any file under it) -> (id, the registry it is served from)."""
    m = PAGE_RE.match(ref.strip())
    return (m.group(2), m.group(1)) if m else (ref, None)


def pull(pack_id: str, registry: str, dest: Path, token: str | None = None,
         digest: str | None = None) -> BuiltPack:
    """Download the latest version of a pack, check it, and unpack it into `dest`.

    With `digest`, download that version instead, if some evidence names it: the
    registry keeps every attested version so attestations can be re-checked.
    """
    if not PACK_REF_RE.match(pack_id):
        raise RegistryError("pack must look like 'owner/name' (only the latest version can be pulled)")
    base = _base(registry)
    index = json.loads(_fetch(base + "index.json"))
    entry = next((e for e in index.get("packs", []) if e["id"] == pack_id), None)
    if entry is None:
        raise RegistryError(f"{pack_id} is not in the registry at {base}")
    # A site that keeps its files in a bucket names it; the site also redirects there.
    prefix = f"{index['files_url'].rstrip('/')}/packs/{pack_id}/" if index.get("files_url") else f"{base}packs/{pack_id}/"
    if digest and digest != entry["digest"]:
        old = next((o for o in entry.get("older", []) if o["digest"] == digest), None)
        if old is None:
            raise RegistryError(f"{pack_id}: no evidence names {digest}, so the registry does not keep it; "
                                f"the latest is {entry['digest']}")
        if entry.get("price"):
            raise RegistryError(f"{pack_id} is priced; ask the store for older versions")
        tarball = _fetch(prefix + old["path"])
        if hashlib.sha256(tarball).hexdigest() != old["tarball_sha256"]:
            raise RegistryError(f"tarball sha256 does not match the registry for {digest}")
        got = _unpack(tarball, pack_id, dest, digest)
        return BuiltPack(pack_id, old["version"], got, old["tarball_sha256"])
    if entry.get("price"):
        if not token:
            p = entry["price"]
            raise RegistryError(f"{pack_id} costs {p['amount'] / 100:.2f} {p['currency'].upper()}; "
                                f"buy it on its page, then pull with --token <license>")
        if not index.get("store"):
            raise RegistryError(f"{pack_id} is priced but the registry names no store")
        tarball = _fetch(f"{index['store']}/download/{pack_id}", token)
    else:
        # The site's own path first: symbola.sh counts the download there, then redirects to the
        # bucket. A static copy of a bucket-backed site has no such path, so fall back to the bucket.
        try:
            tarball = _fetch(f"{base}packs/{pack_id}/{TARBALL_FILE}")
        except RegistryError:
            if not index.get("files_url"):
                raise
            tarball = _fetch(prefix + TARBALL_FILE)
    sha = hashlib.sha256(tarball).hexdigest()
    listed = _fetch(prefix + SHA_FILE).decode().split()[0]
    if sha != listed or sha != entry["tarball_sha256"]:
        raise RegistryError(f"tarball sha256 is {sha}, the registry lists {listed}")
    return BuiltPack(pack_id, entry["version"], _unpack(tarball, pack_id, dest, entry["digest"]), sha)


def _unpack(tarball: bytes, pack_id: str, dest: Path, expected: str) -> str:
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise RegistryError(f"{dest} exists and is not empty")
    name = pack_id.split("/", 1)[1]
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as tar:
            tar.extractall(tmp, filter="data")
        unpacked = Path(tmp) / name
        digest = pack_digest(unpacked)
        if digest != expected:
            raise RegistryError(f"unpacked pack digest is {digest}, the registry lists {expected}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.rmdir()
        shutil.copytree(unpacked, dest)
    return digest
