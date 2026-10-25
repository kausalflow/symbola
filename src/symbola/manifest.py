"""The contract manifest, `symbolon.toml`."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class Statistical(_Strict):
    """A property that holds for the distribution of outputs, not for every output.

    Its function takes (impl, seed) and returns a number (a bool counts as 0 or 1).
    The runner calls it with `samples` seeds and fails it only when the mean is,
    at false-alarm rate `alpha`, below `at_least` or above `at_most`.
    """

    at_least: float | None = None
    at_most: float | None = None
    samples: int = Field(default=100, ge=2, le=100_000)
    alpha: float = Field(default=0.01, gt=0, lt=1)

    @model_validator(mode="after")
    def _check_band(self) -> "Statistical":
        if self.at_least is None and self.at_most is None:
            raise ValueError("give at_least, at_most or both")
        if self.at_least is not None and self.at_most is not None and self.at_least > self.at_most:
            raise ValueError("at_least is above at_most")
        return self


class Spec(_Strict):
    seed: int = 0
    max_examples: int = Field(default=200, ge=1, le=100_000)
    float_rel_tol: float = Field(default=1e-9, ge=0)
    timeout_seconds: int = Field(default=120, ge=1)
    # Property name -> how to run it over seeds, as [spec.statistical.test_name].
    statistical: dict[str, Statistical] = {}

    @field_validator("statistical")
    @classmethod
    def _check_names(cls, v: dict[str, Statistical]) -> dict[str, Statistical]:
        bad = [k for k in v if not (k.startswith("test_") and IDENTIFIER_RE.match(k))]
        if bad:
            raise ValueError(f"keys must name test_* properties in properties.py, not {', '.join(bad)}")
        return v


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
