from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal


@dataclass(frozen=True, slots=True)
class IrrigationZone:
    name: str
    sensors: list[str]
    dry_threshold: float
    wet_threshold: float
    min_interval: timedelta
    max_duration: timedelta


@dataclass(frozen=True, slots=True)
class IrrigationAction:
    zone: str
    action: Literal["start", "stop", "noop"]
    reason: str
