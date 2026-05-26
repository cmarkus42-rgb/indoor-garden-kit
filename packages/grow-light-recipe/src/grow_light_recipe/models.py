from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import time, timedelta

from grow_light_recipe.time_utils import shift_time, time_to_minutes


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
