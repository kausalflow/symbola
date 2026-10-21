"""Content addressing for contracts.

The digest is SHA-256 over a deterministic framing of every file in the
contract directory: sorted POSIX paths, CRLF normalized to LF, no timestamps
or permissions. See docs/CONTRACT_FORMAT.md for the exact framing.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

FRAMING_HEADER = b"symbolon-contract-v1\n"
SKIPPED_DIRS = {"__pycache__"}
SKIPPED_SUFFIXES = {".pyc", ".pyo"}


def contract_files(root: Path) -> list[Path]:
    """Files that make up a contract, in digest order."""
    root = Path(root)
    files = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part.startswith(".") or part in SKIPPED_DIRS for part in rel.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"symlinks are not allowed in a contract: {rel.as_posix()}")
        if path.is_file() and path.suffix not in SKIPPED_SUFFIXES:
            files.append(path)
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def contract_digest(root: Path) -> str:
    root = Path(root)
    h = hashlib.sha256(FRAMING_HEADER)
    for path in contract_files(root):
        rel = path.relative_to(root).as_posix().encode()
        data = path.read_bytes().replace(b"\r\n", b"\n")
        h.update(rel + b"\n" + str(len(data)).encode() + b"\n" + data + b"\n")
    return "sha256:" + h.hexdigest()
