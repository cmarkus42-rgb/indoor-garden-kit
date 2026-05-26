from __future__ import annotations

from collections.abc import Awaitable, Callable
from urllib.parse import parse_qs

from ecowitt_collector.models import EcowittReading
from ecowitt_collector.parser import parse_ecowitt_post

try:
    from fastapi import FastAPI, Request
except ImportError as e:
    raise ImportError(
        "FastAPI is required for the receiver. "
        "Install with: pip install ecowitt-collector[fastapi]"
    ) from e


class EcowittCollector:
    """Receives Ecowitt push data via HTTP POST and invokes a callback."""

    def __init__(self, callback: Callable[[EcowittReading], Awaitable[None]]) -> None:
        self._callback = callback

    def mount(self, app: FastAPI, path: str = "/ecowitt/push") -> None:
        callback = self._callback

        @app.post(path)
        async def _ecowitt_push(request: Request) -> dict:
            body = await request.body()
            raw = body.decode("utf-8", errors="replace")
            parsed = {k: v[0] for k, v in parse_qs(raw).items()}
            if not parsed:
                return {"status": "ok", "readings": 0}
            reading = parse_ecowitt_post(parsed)
            await callback(reading)
            return {"status": "ok", "readings": len(reading.soil_channels)}
