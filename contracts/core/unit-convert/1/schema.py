"""Interface for core/unit-convert."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Unit = Literal["mm", "cm", "m", "km", "in", "ft", "yd", "mi", "mg", "g", "kg", "oz", "lb", "C", "F", "K"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float = Field(allow_inf_nan=False)
    from_unit: Unit
    to_unit: Unit


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float = Field(allow_inf_nan=False)
