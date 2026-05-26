# ecowitt-collector

Receive and parse Ecowitt weather station push data (custom server protocol).

## Overview

Ecowitt weather stations can push sensor readings to a custom HTTP endpoint.
This library provides models and a parser for that payload, plus an optional
FastAPI integration to mount a ready-made receiver endpoint.

## Installation

```bash
# Core (models + parser only, no web framework dependency)
pip install ecowitt-collector

# With FastAPI integration
pip install "ecowitt-collector[fastapi]"
```

## Usage

### Standalone parsing

```python
from ecowitt_collector import parse_ecowitt_post

# raw_data is a dict of form fields as sent by the station
raw_data = {
    "PASSKEY": "ABC123",
    "stationtype": "GW2000A_V2.1.4",
    "dateutc": "2026-01-15 12:00:00",
    "tempinf": "72.3",
    "humidityin": "45",
    "soilmoisture1": "62",
    "soiltemp1f": "68.0",
    "soilmoisture2": "58",
    "soiltemp2f": "67.5",
}

reading = parse_ecowitt_post(raw_data)
print(reading.indoor.temp_c)       # indoor temperature in Celsius
print(reading.soil[1].moisture)    # soil channel 1 moisture %
print(reading.soil[2].temp_c)      # soil channel 2 temperature in Celsius
```

### FastAPI integration

```python
from fastapi import FastAPI
from ecowitt_collector.fastapi import ecowitt_router, get_last_reading

app = FastAPI()
app.include_router(ecowitt_router, prefix="/ecowitt")

@app.get("/latest")
async def latest():
    reading = get_last_reading()
    if reading is None:
        return {"status": "no data yet"}
    return reading.model_dump()
```

The router mounts a `POST /ecowitt/push` endpoint that Ecowitt stations post to.
Configure the station's "custom server" to point at `http://<your-host>/ecowitt/push`.

## Data Models

### `EcowittReading`

Top-level parsed reading:

| Field | Type | Description |
|-------|------|-------------|
| `passkey` | `str` | Station passkey |
| `station_type` | `str` | Firmware version string |
| `timestamp` | `datetime` | UTC timestamp from station |
| `indoor` | `IndoorClimate \| None` | Indoor temperature + humidity |
| `soil` | `dict[int, SoilChannel]` | Soil channels keyed by channel number |

### `SoilChannel`

| Field | Type | Description |
|-------|------|-------------|
| `channel` | `int` | Channel number (1-based) |
| `moisture` | `int` | Volumetric moisture % |
| `temp_c` | `float \| None` | Soil temperature in Celsius |

### `IndoorClimate`

| Field | Type | Description |
|-------|------|-------------|
| `temp_c` | `float` | Indoor temperature in Celsius |
| `humidity` | `int` | Indoor relative humidity % |

## License

MIT
