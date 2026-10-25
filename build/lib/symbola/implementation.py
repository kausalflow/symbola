"""The implementation manifest, `symbolon-impl.toml`.

An implementation is a directory: source, this manifest, and optionally a
pinned `requirements.lock`. Its identity is the digest of the whole
directory, so the same source with different dependency pins is a
different implementation.

A Python implementation names a file that defines the entrypoint function.
Any other language uses `language = "command"`: a program that speaks the
line protocol described in spec.CommandImpl.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .manifest import DIGEST_RE

IMPL_MANIFEST_FILE = "symbolon-impl.toml"
LOCKFILE = "requirements.lock"
PINNED_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9,._-]+\])?==[^\s;]+")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ImplementationSection(_Strict):
    contract: str
    entrypoint: str = "impl.py"
    language: Literal["python", "command"] = "python"
    command: list[str] | None = None
    license: str = Field(min_length=1)
    authors: list[str] = Field(min_length=1)

    @field_validator("contract")
    @classmethod
    def _check_contract(cls, v: str) -> str:
        if not DIGEST_RE.match(v):
            raise ValueError("must be the target contract's digest, 'sha256:<64 hex chars>'")
        return v

    @field_validator("entrypoint")
    @classmethod
    def _check_entrypoint(cls, v: str) -> str:
        path = PurePosixPath(v)
        if path.is_absolute() or ".." in path.parts or path.suffix != ".py":
            raise ValueError("must be a relative path to a .py file inside the implementation")
        return v

    @model_validator(mode="after")
    def _check_command(self) -> "ImplementationSection":
        if self.language == "command" and not self.command:
            raise ValueError("language 'command' needs command = [...], e.g. [\"node\", \"impl.mjs\"]")
        if self.language == "python" and self.command:
            raise ValueError("command is only used with language = 'command'")
        return self


class Generator(_Strict):
    """How a generated implementation was produced. Absent for hand-written code."""

    model: str
    family: str | None = None      # model family, for declaring a replication ensemble
    language: str | None = None    # source language, e.g. "go"; `language = "command"` does not say
    prompt_digest: str | None = None


class ImplManifest(_Strict):
    implementation: ImplementationSection
    generator: Generator | None = None


def load_impl_manifest(impl_dir: Path) -> ImplManifest:
    with (Path(impl_dir) / IMPL_MANIFEST_FILE).open("rb") as f:
        return ImplManifest.model_validate(tomllib.load(f))


def check_lockfile(impl_dir: Path) -> Path | None:
    """Return the lockfile if present, after checking every line is pinned with ==."""
    path = Path(impl_dir) / LOCKFILE
    if not path.exists():
        return None
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        line = line.split("#", 1)[0].strip().rstrip("\\").strip()
        if not line or line.startswith("--hash"):
            continue
        if not PINNED_RE.match(line):
            raise ValueError(f"{LOCKFILE} line {lineno}: every requirement must be pinned with '=='")
    return path
