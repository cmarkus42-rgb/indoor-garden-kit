from ecowitt_collector.parser import parse_ecowitt_post

MINIMAL_POST = {
    "stationtype": "GW1200A_V2.3.5",
    "dateutc": "2026-05-26 14:30:00",
    "soilmoisture1": "45",
    "soilbatt1": "1.3",
}

FULL_POST = {
    "stationtype": "GW1200A_V2.3.5",
    "dateutc": "2026-05-26 14:30:00",
    "tempinf": "72.5",
    "humidityin": "45",
    "baromrelin": "30.12",
    "soilmoisture1": "45",
    "soilbatt1": "1.3",
    "soilmoisture2": "52",
    "soilbatt2": "1.25",
    "soilmoisture3": "38",
}

INDOOR_ONLY_POST = {
    "stationtype": "GW1200A_V2.3.5",
    "dateutc": "2026-05-26 14:30:00",
    "tempinf": "72.5",
    "humidityin": "45",
}

EMPTY_POST = {
    "stationtype": "GW1200A_V2.3.5",
    "dateutc": "2026-05-26 14:30:00",
}


def test_parse_minimal():
    reading = parse_ecowitt_post(MINIMAL_POST)
    assert reading.station_type == "GW1200A_V2.3.5"
    assert len(reading.soil_channels) == 1
    assert reading.soil_channels[1].moisture == 45.0
    assert reading.soil_channels[1].battery == 1.3
    assert reading.indoor is None


def test_parse_full():
    reading = parse_ecowitt_post(FULL_POST)
    assert len(reading.soil_channels) == 3
    assert reading.soil_channels[1].moisture == 45.0
    assert reading.soil_channels[2].moisture == 52.0
    assert reading.soil_channels[3].moisture == 38.0
    assert reading.soil_channels[3].battery is None
    assert reading.indoor is not None
    assert reading.indoor.temperature_c == 22.5
    assert reading.indoor.humidity == 45.0
    assert reading.indoor.pressure_hpa is not None


def test_parse_indoor_only():
    reading = parse_ecowitt_post(INDOOR_ONLY_POST)
    assert len(reading.soil_channels) == 0
    assert reading.indoor is not None
    assert reading.indoor.temperature_c == 22.5


def test_parse_empty():
    reading = parse_ecowitt_post(EMPTY_POST)
    assert len(reading.soil_channels) == 0
    assert reading.indoor is None


def test_parse_timestamp():
    reading = parse_ecowitt_post(MINIMAL_POST)
    assert reading.timestamp.year == 2026
    assert reading.timestamp.month == 5
    assert reading.timestamp.day == 26
    assert reading.timestamp.hour == 14
    assert reading.timestamp.minute == 30


def test_parse_fahrenheit_to_celsius():
    post = {
        "stationtype": "GW1200A_V2.3.5",
        "dateutc": "2026-05-26 14:30:00",
        "tempinf": "32",
    }
    reading = parse_ecowitt_post(post)
    assert reading.indoor.temperature_c == 0.0


def test_parse_pressure_inhg_to_hpa():
    post = {
        "stationtype": "GW1200A_V2.3.5",
        "dateutc": "2026-05-26 14:30:00",
        "baromrelin": "29.92",
    }
    reading = parse_ecowitt_post(post)
    assert abs(reading.indoor.pressure_hpa - 1013.25) < 0.5


def test_parse_all_8_soil_channels():
    post = {
        "stationtype": "GW1200A_V2.3.5",
        "dateutc": "2026-05-26 14:30:00",
    }
    for i in range(1, 9):
        post[f"soilmoisture{i}"] = str(10 + i * 5)
        post[f"soilbatt{i}"] = "1.3"
    reading = parse_ecowitt_post(post)
    assert len(reading.soil_channels) == 8
    assert reading.soil_channels[1].moisture == 15.0
    assert reading.soil_channels[8].moisture == 50.0
