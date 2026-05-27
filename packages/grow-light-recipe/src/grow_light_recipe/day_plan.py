from __future__ import annotations

from dataclasses import dataclass

from grow_light_recipe.recipe import Recipe
from grow_light_recipe.time_utils import time_to_minutes


def _parse_hhmm(s: str) -> int:
    """Convert 'HH:MM' to minutes since midnight."""
    h, m = map(int, s.split(":"))
    return h * 60 + m


@dataclass(frozen=True, slots=True)
class ChannelSchedule:
    channel: str
    on_time: int   # minutes since midnight
    off_time: int  # minutes since midnight


@dataclass(frozen=True, slots=True)
class DimmingPoint:
    time: int    # minutes since midnight
    pct: float   # 0.0-100.0


@dataclass(frozen=True, slots=True)
class DayPlan:
    date: str
    recipe_name: str
    transition_progress: float | None
    main_on: int
    main_off: int
    dimming_curve: tuple[DimmingPoint, ...]
    channels: tuple[ChannelSchedule, ...]


def compute_day_plan(
    recipe: Recipe,
    date_str: str,
    *,
    transition_progress: float | None = None,
) -> DayPlan:
    main_on = _parse_hhmm(recipe.photoperiod_on)
    main_off = _parse_hhmm(recipe.photoperiod_off)

    # Normalize: if off <= on, treat off as next day
    effective_off = main_off if main_off > main_on else main_off + 1440

    # Dimming curve: 4 points
    dim = recipe.dimming
    dimming_curve = (
        DimmingPoint(time=main_on, pct=float(dim.min_pct)),
        DimmingPoint(time=main_on + dim.sunrise_min, pct=float(dim.max_pct)),
        DimmingPoint(time=effective_off - dim.sunset_min, pct=float(dim.max_pct)),
        DimmingPoint(time=effective_off, pct=float(dim.min_pct)),
    )

    # Channel schedules
    channel_list: list[ChannelSchedule] = []
    for ch_name, rule in recipe.channels.items():
        if rule.rule == "before_on":
            on = main_on - rule.offset_min
            if rule.duration_min is not None:
                off = on + rule.duration_min
            else:
                off = main_on
            channel_list.append(ChannelSchedule(channel=ch_name, on_time=on, off_time=off))

        elif rule.rule == "after_off":
            on = effective_off + rule.offset_min
            off = on + (rule.duration_min or 0)
            channel_list.append(ChannelSchedule(channel=ch_name, on_time=on, off_time=off))

        elif rule.rule == "window":
            if rule.windows:
                for w in rule.windows:
                    w_on = _parse_hhmm(w["start"])
                    w_off = w_on + w["duration_min"]
                    channel_list.append(
                        ChannelSchedule(channel=ch_name, on_time=w_on, off_time=w_off)
                    )

    # Sort channels by on_time
    channel_list.sort(key=lambda c: c.on_time)

    return DayPlan(
        date=date_str,
        recipe_name=recipe.name,
        transition_progress=transition_progress,
        main_on=main_on,
        main_off=effective_off,
        dimming_curve=dimming_curve,
        channels=tuple(channel_list),
    )
