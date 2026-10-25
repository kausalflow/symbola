"""The contract manifest, `symbolon.toml`."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MANIFEST_FILE = "symbolon.toml"

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContractSection(_Strict):
    id: str
    version: int = Field(ge=1)
    title: str = Field(min_length=1)
    description: str = ""
    regenerability: Literal["disposable", "pinned", "sovereign"]
    license: str = Field(min_length=1)
    authors: list[str] = Field(min_length=1)
    forked_from: str | None = None

    @field_validator("id")
    @classmethod
    def _check_id(cls, v: str) -> str:
        if not ID_RE.match(v):
            raise ValueError("must look like 'namespace/name' (lowercase letters, digits, hyphens)")
        return v

    @field_validator("regenerability")
    @classmethod
    def _check_regenerability(cls, v: str) -> str:
        if v == "sovereign":
            raise ValueError("'sovereign' is reserved and not supported yet")
        return v

    @field_validator("forked_from")
    @classmethod
    def _check_forked_from(cls, v: str | None) -> str | None:
        if v is not None and not DIGEST_RE.match(v):
            raise ValueError("must be a contract digest like 'sha256:<64 hex chars>'")
        return v


class Entrypoint(_Strict):
    function: str = "run"
    # "cli": implementations are programs, run once per call; see spec.CliImpl.
    driver: Literal["function", "cli"] = "function"

    @field_validator("function")
    @classmethod
    def _check_function(cls, v: str) -> str:
        if not IDENTIFIER_RE.match(v):
            raise ValueError("must be a Python identifier")
        return v


class Requires(_Strict):
    network: list[str] = []
    credentials: list[str] = []
    state: list[str] = []
    permissions: list[str] = []


class Spec(_Strict):
    seed: int = 0
    max_examples: int = Field(default=200, ge=1, le=100_000)
    float_rel_tol: float = Field(default=1e-9, ge=0)
    timeout_seconds: int = Field(default=120, ge=1)


class Runtime(_Strict):
    python: str = ">=3.11"


class Manifest(_Strict):
    contract: ContractSection
    entrypoint: Entrypoint = Entrypoint()
    requires: Requires = Requires()
    spec: Spec = Spec()
    runtime: Runtime = Runtime()

    @property
    def alias(self) -> str:
        return f"{self.contract.id}@{self.contract.version}"


def load_manifest(contract_dir: Path) -> Manifest:
    """Parse and validate a contract's manifest. Raises on any problem."""
    with (Path(contract_dir) / MANIFEST_FILE).open("rb") as f:
        data = tomllib.load(f)
    return Manifest.model_validate(data)
