from __future__ import annotations

import re
from datetime import datetime, timezone

from ecowitt_collector.models import EcowittReading, IndoorClimate, SoilChannel

_SOIL_RE = re.compile(r"^soilmoisture(\d+)$")
_INHG_TO_HPA = 33.8639


def _float(data: dict[str, str], key: str) -> float | None:
    v = data.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _f_to_c(fahrenheit: float) -> float:
    return round((fahrenheit - 32) * 5 / 9, 2)


def _parse_timestamp(data: dict[str, str]) -> datetime:
    raw = data.get("dateutc", "")
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _parse_soil_channels(data: dict[str, str]) -> dict[int, SoilChannel]:
    channels: dict[int, SoilChannel] = {}
    for key in data:
        m = _SOIL_RE.match(key)
        if not m:
            continue
        ch_num = int(m.group(1))
        moisture = _float(data, key)
        if moisture is None:
            continue
        battery = _float(data, f"soilbatt{ch_num}")
        channels[ch_num] = SoilChannel(channel=ch_num, moisture=moisture, battery=battery)
    return channels


def _parse_indoor(data: dict[str, str]) -> IndoorClimate | None:
    temp_f = _float(data, "tempinf")
    humidity = _float(data, "humidityin")
    pressure_inhg = _float(data, "baromrelin")

    if temp_f is None and humidity is None and pressure_inhg is None:
        return None

    temp_c = _f_to_c(temp_f) if temp_f is not None else None
    pressure_hpa = round(pressure_inhg * _INHG_TO_HPA, 2) if pressure_inhg is not None else None

    if temp_c is None and pressure_hpa is not None:
        return IndoorClimate(temperature_c=0.0, humidity=humidity, pressure_hpa=pressure_hpa)
    if temp_c is None:
        return None

    return IndoorClimate(temperature_c=temp_c, humidity=humidity, pressure_hpa=pressure_hpa)


def parse_ecowitt_post(data: dict[str, str]) -> EcowittReading:
    """Parse form-encoded Ecowitt push data into an EcowittReading."""
    return EcowittReading(
        timestamp=_parse_timestamp(data),
        station_type=data.get("stationtype", "unknown"),
        soil_channels=_parse_soil_channels(data),
        indoor=_parse_indoor(data),
    )
