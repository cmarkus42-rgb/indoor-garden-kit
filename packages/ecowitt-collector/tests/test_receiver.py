from urllib.parse import urlencode

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from ecowitt_collector import EcowittReading
from ecowitt_collector.receiver import EcowittCollector

SAMPLE_FORM = {
    "stationtype": "GW1200A_V2.3.5",
    "dateutc": "2026-05-26 14:30:00",
    "tempinf": "72.5",
    "humidityin": "45",
    "soilmoisture1": "45",
    "soilbatt1": "1.3",
}

@pytest.fixture
def captured_readings() -> list[EcowittReading]:
    return []

@pytest.fixture
def app(captured_readings: list[EcowittReading]) -> FastAPI:
    app = FastAPI()
    async def on_reading(reading: EcowittReading) -> None:
        captured_readings.append(reading)
    collector = EcowittCollector(callback=on_reading)
    collector.mount(app)
    return app

@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

async def test_push_endpoint_returns_200(client: AsyncClient):
    resp = await client.post(
        "/ecowitt/push",
        content=urlencode(SAMPLE_FORM),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200

async def test_push_invokes_callback(client: AsyncClient, captured_readings: list[EcowittReading]):
    await client.post(
        "/ecowitt/push",
        content=urlencode(SAMPLE_FORM),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert len(captured_readings) == 1
    assert captured_readings[0].soil_channels[1].moisture == 45.0
    assert captured_readings[0].indoor.temperature_c == 22.5

async def test_push_custom_path():
    app = FastAPI()
    received = []
    async def cb(r: EcowittReading) -> None:
        received.append(r)
    collector = EcowittCollector(callback=cb)
    collector.mount(app, path="/data/report")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/data/report",
            content=urlencode(SAMPLE_FORM),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert resp.status_code == 200
    assert len(received) == 1

async def test_push_empty_body(client: AsyncClient):
    resp = await client.post(
        "/ecowitt/push",
        content="",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200

async def test_push_response_body(client: AsyncClient):
    resp = await client.post(
        "/ecowitt/push",
        content=urlencode(SAMPLE_FORM),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    body = resp.json()
    assert body["status"] == "ok"
