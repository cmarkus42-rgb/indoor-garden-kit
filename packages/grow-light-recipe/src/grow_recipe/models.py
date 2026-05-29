from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import time, timedelta

from grow_recipe.time_utils import shift_time, time_to_minutes


class Phase(str, enum.Enum):
    veg = "veg"
    flower = "flower"


@dataclass(frozen=True, slots=True)
class TimeRange:
    on: time
    off: time


@dataclass(frozen=True, slots=True)
class LightConfig:
    offset_before: timedelta = field(default_factory=timedelta)
    offset_after: timedelta = field(default_factory=timedelta)
    phases: tuple[Phase, ...] = (Phase.veg, Phase.flower)


@dataclass(frozen=True, slots=True)
class ClimateConfig:
    fan_intensity: int = 5
    temp_target_c: float = 25.0
    humidity_target: float = 60.0
    vpd_target_kpa: float = 1.2

    @classmethod
    def from_dict(cls, d: dict) -> ClimateConfig:
        return cls(
            fan_intensity=d.get("fan_intensity", 5),
            temp_target_c=d.get("temp_target_c", 25.0),
            humidity_target=d.get("humidity_target", 60.0),
            vpd_target_kpa=d.get("vpd_target_kpa", 1.2),
        )

    def to_dict(self) -> dict:
        return {
            "fan_intensity": self.fan_intensity,
            "temp_target_c": self.temp_target_c,
            "humidity_target": self.humidity_target,
            "vpd_target_kpa": self.vpd_target_kpa,
        }


@dataclass(frozen=True, slots=True)
class IrrigationConfig:
    dry_threshold: float = 30.0
    wet_threshold: float = 60.0
    max_duration_min: int = 5
    min_interval_hours: float = 2.0

    @classmethod
    def from_dict(cls, d: dict) -> IrrigationConfig:
        return cls(
            dry_threshold=d.get("dry_threshold", 30.0),
            wet_threshold=d.get("wet_threshold", 60.0),
            max_duration_min=d.get("max_duration_min", 5),
            min_interval_hours=d.get("min_interval_hours", 2.0),
        )

    def to_dict(self) -> dict:
        return {
            "dry_threshold": self.dry_threshold,
            "wet_threshold": self.wet_threshold,
            "max_duration_min": self.max_duration_min,
            "min_interval_hours": self.min_interval_hours,
        }


@dataclass(frozen=True, slots=True)
class ScheduleEntry:
    light_type: str
    on_time: time
    off_time: time



@dataclass(frozen=True, slots=True)
class LightRecipe:
    photoperiod: TimeRange
    phase: Phase
    light_types: dict[str, LightConfig]

    def schedule(self) -> list[ScheduleEntry]:
        entries: list[ScheduleEntry] = []
        for name, config in self.light_types.items():
            if self.phase not in config.phases:
                continue
            on = shift_time(self.photoperiod.on, -config.offset_before)
            off = shift_time(self.photoperiod.off, config.offset_after)
            entries.append(ScheduleEntry(light_type=name, on_time=on, off_time=off))
        entries.sort(key=lambda e: time_to_minutes(e.on_time))
        return entries
