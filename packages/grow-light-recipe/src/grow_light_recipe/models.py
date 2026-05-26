from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import time, timedelta


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
