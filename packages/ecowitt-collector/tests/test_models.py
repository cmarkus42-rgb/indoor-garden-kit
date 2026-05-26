from datetime import datetime, timezone
from ecowitt_collector.models import SoilChannel, IndoorClimate, EcowittReading


def test_soil_channel_creation():
    ch = SoilChannel(channel=1, moisture=45.0, battery=1.3)
    assert ch.channel == 1
    assert ch.moisture == 45.0
    assert ch.battery == 1.3


def test_soil_channel_no_battery():
    ch = SoilChannel(channel=2, moisture=60.0)
    assert ch.battery is None


def test_indoor_climate_creation():
    ic = IndoorClimate(temperature_c=22.5, humidity=45.0, pressure_hpa=1013.25)
    assert ic.temperature_c == 22.5
    assert ic.humidity == 45.0
    assert ic.pressure_hpa == 1013.25


def test_indoor_climate_partial():
    ic = IndoorClimate(temperature_c=22.5)
    assert ic.humidity is None
    assert ic.pressure_hpa is None


def test_ecowitt_reading_creation():
    ts = datetime.now(timezone.utc)
    reading = EcowittReading(
        timestamp=ts,
        station_type="GW1200",
        soil_channels={
            1: SoilChannel(channel=1, moisture=45.0, battery=1.3),
        },
        indoor=IndoorClimate(temperature_c=22.5, humidity=45.0),
    )
    assert reading.timestamp == ts
    assert reading.station_type == "GW1200"
    assert len(reading.soil_channels) == 1
    assert reading.soil_channels[1].moisture == 45.0
    assert reading.indoor.temperature_c == 22.5


def test_ecowitt_reading_no_indoor():
    ts = datetime.now(timezone.utc)
    reading = EcowittReading(
        timestamp=ts,
        station_type="GW1200",
        soil_channels={},
    )
    assert reading.indoor is None
