from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SoilChannel:
    """Single soil moisture sensor reading."""
    channel: int
    moisture: float  # 0-100%
    battery: float | None = None  # voltage


@dataclass(frozen=True, slots=True)
class IndoorClimate:
    """Indoor climate readings from the gateway itself."""
    temperature_c: float  # Celsius
    humidity: float | None = None  # % RH
    pressure_hpa: float | None = None  # hPa


@dataclass(frozen=True, slots=True)
class EcowittReading:
    """Parsed Ecowitt push data payload."""
    timestamp: datetime
    station_type: str
    soil_channels: dict[int, SoilChannel] = field(default_factory=dict)
    indoor: IndoorClimate | None = None
