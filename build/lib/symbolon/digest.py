"""Content addressing for contracts and implementations.

A digest is SHA-256 over a deterministic framing of every file in a
directory: sorted POSIX paths, CRLF normalized to LF, no timestamps or
permissions. Contracts and implementations use the same framing with
different headers. See docs/CONTRACT_FORMAT.md for the exact framing.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

CONTRACT_HEADER = b"symbolon-contract-v1\n"
IMPLEMENTATION_HEADER = b"symbolon-implementation-v1\n"
SKIPPED_DIRS = {"__pycache__"}
SKIPPED_SUFFIXES = {".pyc", ".pyo"}


def contract_files(root: Path) -> list[Path]:
    """Files that make up a contract or implementation, in digest order."""
    root = Path(root)
    files = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part.startswith(".") or part in SKIPPED_DIRS for part in rel.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"symlinks are not allowed: {rel.as_posix()}")
        if path.is_file() and path.suffix not in SKIPPED_SUFFIXES:
            files.append(path)
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def tree_digest(root: Path, header: bytes) -> str:
    root = Path(root)
    h = hashlib.sha256(header)
    for path in contract_files(root):
        rel = path.relative_to(root).as_posix().encode()
        data = path.read_bytes().replace(b"\r\n", b"\n")
        h.update(rel + b"\n" + str(len(data)).encode() + b"\n" + data + b"\n")
    return "sha256:" + h.hexdigest()


def contract_digest(root: Path) -> str:
    return tree_digest(root, CONTRACT_HEADER)


def implementation_digest(root: Path) -> str:
    return tree_digest(root, IMPLEMENTATION_HEADER)


def hex_of(digest: str) -> str:
    """'sha256:abc...' -> 'abc...'"""
    return digest.split(":", 1)[1]
