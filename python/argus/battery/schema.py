"""Battery measurements with explicit units, provenance and manufacturer limits."""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

PublicDatasetId = Literal["nasa-B0005", "nasa-B0006", "nasa-B0007", "nasa-B0018"]


class BatteryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class OperatingLimits(BatteryModel):
    source: str = Field(min_length=5, max_length=500)
    charge_min_c: float | None = Field(default=None, ge=-60, le=100)
    charge_max_c: float | None = Field(default=None, ge=-60, le=100)
    cell_spread_limit_mv: float | None = Field(default=None, gt=0, le=2000)

    @model_validator(mode="after")
    def ordered(self) -> OperatingLimits:
        if (
            self.charge_min_c is not None
            and self.charge_max_c is not None
            and self.charge_min_c >= self.charge_max_c
        ):
            raise ValueError("charging limits must be ordered")
        return self


class BatteryProfile(BatteryModel):
    battery_id: str = Field(min_length=1, max_length=80, pattern=r"^[\w .-]+$")
    application: Literal["ev", "uav", "equipment"] = "ev"
    chemistry: Literal["li-ion", "nmc", "nca", "lfp", "unknown"] = "unknown"
    measurement_scope: Literal["cell", "pack"] = "pack"
    cycle_axis: Literal["equivalent_cycles", "discharge_test_index"] = (
        "equivalent_cycles"
    )
    reference_capacity_ah: float = Field(ge=0.001, le=100000)
    reference_condition_id: str = Field(min_length=1, max_length=120)
    service_threshold_pct: float = Field(default=80, ge=40, le=95)
    equivalent_cycles_per_month: float | None = Field(default=None, gt=0, le=1000)
    limits: OperatingLimits | None = None

    @model_validator(mode="after")
    def cycle_rate(self) -> BatteryProfile:
        if (
            self.cycle_axis != "equivalent_cycles"
            and self.equivalent_cycles_per_month is not None
        ):
            raise ValueError("calendar projection requires equivalent full cycles")
        return self


class CapacityRecord(BatteryModel):
    equivalent_cycles: float = Field(ge=0, le=1000000)
    capacity_ah: float = Field(gt=0, le=100000)
    condition_id: str = Field(min_length=1, max_length=120)
    temperature_c: float | None = Field(default=None, ge=-80, le=150)
    timestamp: str | None = Field(default=None, max_length=40)


class BMSReading(BatteryModel):
    soc_pct: float | None = Field(default=None, ge=0, le=100)
    temperature_c: float | None = Field(default=None, ge=-80, le=150)
    cell_spread_mv: float | None = Field(default=None, ge=0, le=5000)
    charging: bool = False
    safety_alarm: bool = False
    high_soc_hot_storage_reported: bool = False
    frequent_fast_charging_reported: bool = False
    observed_at: str | None = Field(default=None, max_length=40)


class BatteryRequest(BatteryModel):
    dataset_id: PublicDatasetId | None = None
    data_origin: Literal["user_supplied", "laboratory", "synthetic"] = "user_supplied"
    profile: BatteryProfile
    records: list[CapacityRecord] = Field(default_factory=list, max_length=2000)
    bms: BMSReading = Field(default_factory=BMSReading)

    @model_validator(mode="after")
    def history_order(self) -> BatteryRequest:
        cycles = [r.equivalent_cycles for r in self.records]
        if any(b <= a for a, b in zip(cycles, cycles[1:])):
            raise ValueError("history must have unique strictly increasing cycles")
        return self
