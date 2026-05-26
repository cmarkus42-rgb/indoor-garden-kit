from ecowitt_collector.models import EcowittReading, IndoorClimate, SoilChannel
from ecowitt_collector.parser import parse_ecowitt_post

__all__ = [
    "EcowittReading",
    "IndoorClimate",
    "SoilChannel",
    "parse_ecowitt_post",
]


def __getattr__(name: str):
    if name == "EcowittCollector":
        from ecowitt_collector.receiver import EcowittCollector
        return EcowittCollector
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
