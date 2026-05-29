from __future__ import annotations

from dataclasses import dataclass, field

from grow_recipe.models import ClimateConfig, IrrigationConfig


@dataclass(frozen=True, slots=True)
class ChannelRule:
    rule: str  # "before_on" | "after_off" | "window"
    offset_min: int = 0
    duration_min: int | None = None
    windows: tuple[dict, ...] | None = None


@dataclass(frozen=True, slots=True)
class DimmingConfig:
    sunrise_min: int = 0
    sunset_min: int = 0
    max_pct: int = 100
    min_pct: int = 0


@dataclass(frozen=True, slots=True)
class Recipe:
    name: str
    photoperiod_on: str   # "HH:MM"
    photoperiod_off: str  # "HH:MM"
    dimming: DimmingConfig = field(default_factory=DimmingConfig)
    channels: dict[str, ChannelRule] = field(default_factory=dict)
    climate: ClimateConfig | None = None
    irrigation: IrrigationConfig | None = None

    @classmethod
    def from_dict(cls, d: dict) -> Recipe:
        pp = d.get("photoperiod", {})
        dim_raw = d.get("dimming", {})
        dimming = DimmingConfig(
            sunrise_min=dim_raw.get("sunrise_min", 0),
            sunset_min=dim_raw.get("sunset_min", 0),
            max_pct=dim_raw.get("max_pct", 100),
            min_pct=dim_raw.get("min_pct", 0),
        )
        channels: dict[str, ChannelRule] = {}
        for ch_name, ch_raw in d.get("channels", {}).items():
            windows = None
            if "windows" in ch_raw:
                windows = tuple(ch_raw["windows"])
            channels[ch_name] = ChannelRule(
                rule=ch_raw["rule"],
                offset_min=ch_raw.get("offset_min", 0),
                duration_min=ch_raw.get("duration_min"),
                windows=windows,
            )
        climate = None
        if "climate" in d:
            climate = ClimateConfig.from_dict(d["climate"])
        irrigation = None
        if "irrigation" in d:
            irrigation = IrrigationConfig.from_dict(d["irrigation"])
        return cls(
            name=d["name"],
            photoperiod_on=pp.get("on", "06:00"),
            photoperiod_off=pp.get("off", "00:00"),
            dimming=dimming,
            channels=channels,
            climate=climate,
            irrigation=irrigation,
        )

    def to_dict(self) -> dict:
        channels: dict[str, dict] = {}
        for ch_name, rule in self.channels.items():
            ch: dict = {"rule": rule.rule}
            if rule.offset_min:
                ch["offset_min"] = rule.offset_min
            if rule.duration_min is not None:
                ch["duration_min"] = rule.duration_min
            if rule.windows is not None:
                ch["windows"] = list(rule.windows)
            channels[ch_name] = ch
        result: dict = {
            "name": self.name,
            "photoperiod": {
                "on": self.photoperiod_on,
                "off": self.photoperiod_off,
            },
            "dimming": {
                "sunrise_min": self.dimming.sunrise_min,
                "sunset_min": self.dimming.sunset_min,
                "max_pct": self.dimming.max_pct,
                "min_pct": self.dimming.min_pct,
            },
            "channels": channels,
        }
        if self.climate is not None:
            result["climate"] = self.climate.to_dict()
        if self.irrigation is not None:
            result["irrigation"] = self.irrigation.to_dict()
        return result
