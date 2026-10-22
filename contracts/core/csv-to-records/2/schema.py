"""Interface for core/csv-to-records."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    csv: str = Field(description="CSV text including the header row.")
    delimiter: Literal[",", ";", "\t", "|"] = ","


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[dict[str, str]] = Field(description="One record per data row, in file order.")
