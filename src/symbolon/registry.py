"""The static pack registry: scaffold a pack, build the site's data, pull a pack.

The registry is a folder of packs (`packs/<owner>/<name>/versions/<n>/`) turned
into static files that any web host can serve (distribution design, sections 2-4):

    index.json, llms.txt
    packs/<owner>/<name>/latest.tar.gz, latest.sha256, latest.sig.json,
                         pack.md, llms.txt, files/...

Only the latest version of each pack is published. Older versions stay in the
registry's git history and folders, so attestations that name them can still be
re-checked, but the site never links them. Holdout tests never live inside a
pack folder, and the build refuses a pack that has one.
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
from .digest import contract_files, tree_digest
from .pack import (ASSUMPTIONS_DIR, BRIEF_FILE, COMPONENTS_DIR, OBLIGATIONS_FILE, PACK_MANIFEST_FILE,
                   VERSIONS_DIR, summary_line, validate_pack)

PACK_HEADER = b"symbolon-pack-v1\n"
PACK_REF_RE = re.compile(r"^[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$")
SIGNATURE_FILE = "latest.sig.json"
TARBALL_FILE = "latest.tar.gz"
SHA_FILE = "latest.sha256"


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

# Component contracts, as "<namespace>/<name>@<version>" = "<digest>".
# Add one with `symbolon init` under components/, then list its digest here.
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
3. Read `obligations.toml`: the decisions you must keep. `open` ones are yours to choose.
4. Each component's specification is under `components/<name>/versions/<n>/`.

**Done** means `symbolon attest components/<name>/versions/<n> <impl-dir>` passes
for every component. The publisher keeps a holdout, so don't special-case examples.

If you are the publisher's coding agent, keep this pack current while you build:
when the user makes a choice you could not have guessed, add it to
`obligations.toml` with a check; when they state a fact about the world, add an
assumption; record only what the user decided, not what the code happens to do.
Keep holdout tests outside this folder. Run `symbolon pack validate <this folder>`
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


def pack_markdown(root: Path, pack_id: str, version: int, digest: str) -> str:
    """The whole pack as one Markdown file, so an agent can read it in one fetch."""
    order = {"AGENTS.md": 0, BRIEF_FILE: 1, OBLIGATIONS_FILE: 3, PACK_MANIFEST_FILE: 4}
    files = sorted(_files(root), key=lambda p: (
        order.get(p.relative_to(root).as_posix(),
                  2 if p.relative_to(root).parts[0] == ASSUMPTIONS_DIR else 5),
        p.relative_to(root).as_posix()))
    out = [f"# {pack_id} (version {version})\n",
           f"Pack digest: `{digest}`. Every file of the pack follows, one section each.\n"]
    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            out.append(f"## {rel}\n\n(binary file, {path.stat().st_size} bytes; see the tarball)\n")
            continue
        if path.suffix == ".md":
            out.append(f"## {rel}\n\n{text.rstrip()}\n")
        else:
            fence = _fence(text)
            lang = {".toml": "toml", ".py": "python", ".json": "json", ".jsonl": "json"}.get(path.suffix, "")
            out.append(f"## {rel}\n\n{fence}{lang}\n{text.rstrip()}\n{fence}\n")
    return "\n".join(out)


def _manifest(root: Path) -> dict:
    with (root / PACK_MANIFEST_FILE).open("rb") as f:
        return tomllib.load(f).get("pack", {})


def build_site(registry: Path, out: Path, key_path: Path | None = None, base_url: str = "") -> list[BuiltPack]:
    """Write the registry's static data for the latest version of every pack."""
    registry, out = Path(registry), Path(out)
    key = keys.load_private(key_path) if key_path else None
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
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
        for path in _files(version_dir):
            target = dest / "files" / path.relative_to(version_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        tarball = make_tarball(version_dir, name)
        sha = hashlib.sha256(tarball).hexdigest()
        (dest / TARBALL_FILE).write_bytes(tarball)
        (dest / SHA_FILE).write_text(f"{sha}  {TARBALL_FILE}\n")
        (dest / "pack.md").write_text(pack_markdown(version_dir, pack_id, version, digest))
        if key:
            payload = json.dumps({"pack": pack_id, "version": version, "digest": digest,
                                  "tarball_sha256": sha}, sort_keys=True).encode()
            (dest / SIGNATURE_FILE).write_text(json.dumps(keys.sign_envelope(payload, key), indent=2) + "\n")
        listed = [p.relative_to(version_dir).as_posix() for p in _files(version_dir)]
        prefix = f"{base_url.rstrip('/')}/packs/{pack_id}" if base_url else f"packs/{pack_id}"
        (dest / "llms.txt").write_text(
            f"# {pack_id}\n\n> {meta.get('title', name)}\n\n"
            f"Version {version}, digest {digest}. Read the whole pack in one file at "
            f"{prefix}/pack.md, or download {prefix}/{TARBALL_FILE}.\n\n## Files\n\n"
            + "".join(f"- [{rel}]({prefix}/files/{rel})\n" for rel in listed))
        entries.append({
            "id": pack_id, "version": version, "title": meta.get("title", name),
            "license": meta.get("license", ""), "authors": meta.get("authors", []),
            "digest": digest, "tarball_sha256": sha, "signed": key is not None,
            "summary": report.summary, "summary_line": summary_line(report.summary),
            "files": listed,
        })
        built.append(BuiltPack(pack_id, version, digest, sha))
    (out / "index.json").write_text(json.dumps({"format": 1, "packs": entries}, indent=2) + "\n")
    root_prefix = base_url.rstrip("/") + "/" if base_url else ""
    (out / "llms.txt").write_text(
        "# Symbolon pack registry\n\n> Spec packs that AI coding agents can build from. "
        "Each pack holds a brief, assumptions, obligations and component contracts with tests.\n\n"
        f"Catalog as JSON: {root_prefix}index.json\n\n## Packs\n\n"
        + "".join(f"- [{e['id']}]({root_prefix}packs/{e['id']}/llms.txt): {e['title']} · {e['summary_line']}\n"
                  for e in entries))
    return built


# ---------------------------------------------------------------- pull

def _base(registry: str) -> str:
    if "://" not in registry:
        registry = Path(registry).resolve().as_uri()
    return registry.rstrip("/") + "/"


def _fetch(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.read()
    except (urllib.error.URLError, OSError) as e:
        raise RegistryError(f"could not fetch {url}: {e}") from None


def pull(pack_id: str, registry: str, dest: Path, trust: Path | None = None) -> BuiltPack:
    """Download the latest version of a pack, check it, and unpack it into `dest`."""
    if not PACK_REF_RE.match(pack_id):
        raise RegistryError("pack must look like 'owner/name' (only the latest version can be pulled)")
    base = _base(registry)
    index = json.loads(_fetch(base + "index.json"))
    entry = next((e for e in index.get("packs", []) if e["id"] == pack_id), None)
    if entry is None:
        raise RegistryError(f"{pack_id} is not in the registry at {base}")
    prefix = f"{base}packs/{pack_id}/"
    tarball = _fetch(prefix + TARBALL_FILE)
    sha = hashlib.sha256(tarball).hexdigest()
    listed = _fetch(prefix + SHA_FILE).decode().split()[0]
    if sha != listed or sha != entry["tarball_sha256"]:
        raise RegistryError(f"tarball sha256 is {sha}, the registry lists {listed}")
    if trust:
        envelope = json.loads(_fetch(prefix + SIGNATURE_FILE))
        try:
            payload = json.loads(keys.verify_envelope(envelope, keys.load_public(trust)))
        except ValueError as e:
            raise RegistryError(f"signature: {e}") from None
        if payload.get("pack") != pack_id or payload.get("tarball_sha256") != sha or payload.get("digest") != entry["digest"]:
            raise RegistryError("signature does not cover this tarball")
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise RegistryError(f"{dest} exists and is not empty")
    name = pack_id.split("/", 1)[1]
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as tar:
            tar.extractall(tmp, filter="data")
        unpacked = Path(tmp) / name
        digest = pack_digest(unpacked)
        if digest != entry["digest"]:
            raise RegistryError(f"unpacked pack digest is {digest}, the registry lists {entry['digest']}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.rmdir()
        shutil.copytree(unpacked, dest)
    return BuiltPack(pack_id, entry["version"], digest, sha)
