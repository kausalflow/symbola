"""Interface for core/date-parse."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Locale = Literal["ISO", "en-US", "en-GB", "de-DE"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(description="The date as written, e.g. '10/21/2026' for en-US.")
    locale: Locale = Field(
        description=(
            "ISO: YYYY-MM-DD. en-US: M/D/YYYY. en-GB: D/M/YYYY. de-DE: D.M.YYYY. "
            "Day and month may omit leading zeros, except in ISO."
        )
    )


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="ISO 8601 calendar date.")
