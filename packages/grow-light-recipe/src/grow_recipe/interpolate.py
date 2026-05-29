from __future__ import annotations

from datetime import time as dt_time

from grow_recipe.models import ClimateConfig, IrrigationConfig
from grow_recipe.recipe import ChannelRule, DimmingConfig, Recipe
from grow_recipe.time_utils import lerp_time, minutes_to_time, time_to_minutes


def _parse_hhmm(s: str) -> dt_time:
    h, m = map(int, s.split(":"))
    return dt_time(h, m)


def _format_hhmm(t: dt_time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def _lerp_int(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def _lerp_float(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _interpolate_climate(src: ClimateConfig, dst: ClimateConfig, progress: float) -> ClimateConfig:
    return ClimateConfig(
        fan_intensity=_lerp_int(src.fan_intensity, dst.fan_intensity, progress),
        temp_target_c=_lerp_float(src.temp_target_c, dst.temp_target_c, progress),
        humidity_target=_lerp_float(src.humidity_target, dst.humidity_target, progress),
        vpd_target_kpa=_lerp_float(src.vpd_target_kpa, dst.vpd_target_kpa, progress),
    )


def _interpolate_irrigation(src: IrrigationConfig, dst: IrrigationConfig, progress: float) -> IrrigationConfig:
    return IrrigationConfig(
        dry_threshold=_lerp_float(src.dry_threshold, dst.dry_threshold, progress),
        wet_threshold=_lerp_float(src.wet_threshold, dst.wet_threshold, progress),
        max_duration_min=_lerp_int(src.max_duration_min, dst.max_duration_min, progress),
        min_interval_hours=_lerp_float(src.min_interval_hours, dst.min_interval_hours, progress),
    )


def interpolate_recipes(from_r: Recipe, to_r: Recipe, progress: float) -> Recipe:
    # Photoperiod interpolation (shortest-path via existing lerp_time)
    on_interp = lerp_time(_parse_hhmm(from_r.photoperiod_on), _parse_hhmm(to_r.photoperiod_on), progress)
    off_interp = lerp_time(_parse_hhmm(from_r.photoperiod_off), _parse_hhmm(to_r.photoperiod_off), progress)

    # Dimming interpolation
    dimming = DimmingConfig(
        sunrise_min=_lerp_int(from_r.dimming.sunrise_min, to_r.dimming.sunrise_min, progress),
        sunset_min=_lerp_int(from_r.dimming.sunset_min, to_r.dimming.sunset_min, progress),
        max_pct=_lerp_int(from_r.dimming.max_pct, to_r.dimming.max_pct, progress),
        min_pct=_lerp_int(from_r.dimming.min_pct, to_r.dimming.min_pct, progress),
    )

    # Channel interpolation
    all_channels = set(from_r.channels.keys()) | set(to_r.channels.keys())
    channels: dict[str, ChannelRule] = {}

    for ch_name in all_channels:
        src = from_r.channels.get(ch_name)
        dst = to_r.channels.get(ch_name)

        if src and dst:
            # Both exist — interpolate values
            channels[ch_name] = _interpolate_channel(src, dst, progress)
        elif dst and not src:
            # New channel in target — ramp up from zero
            channels[ch_name] = _ramp_channel_in(dst, progress)
        elif src and not dst:
            # Channel removed in target — ramp down to zero
            channels[ch_name] = _ramp_channel_out(src, progress)

    # Climate interpolation
    climate = None
    from_c, to_c = from_r.climate, to_r.climate
    if from_c and to_c:
        climate = _interpolate_climate(from_c, to_c, progress)
    elif to_c and not from_c:
        climate = _interpolate_climate(ClimateConfig(), to_c, progress)
    elif from_c and not to_c:
        climate = _interpolate_climate(from_c, ClimateConfig(), progress)

    # Irrigation interpolation
    irrigation = None
    from_i, to_i = from_r.irrigation, to_r.irrigation
    if from_i and to_i:
        irrigation = _interpolate_irrigation(from_i, to_i, progress)
    elif to_i and not from_i:
        irrigation = _interpolate_irrigation(IrrigationConfig(), to_i, progress)
    elif from_i and not to_i:
        irrigation = _interpolate_irrigation(from_i, IrrigationConfig(), progress)

    return Recipe(
        name=f"{from_r.name} → {to_r.name}",
        photoperiod_on=_format_hhmm(on_interp),
        photoperiod_off=_format_hhmm(off_interp),
        dimming=dimming,
        channels=channels,
        climate=climate,
        irrigation=irrigation,
    )


def _interpolate_channel(src: ChannelRule, dst: ChannelRule, progress: float) -> ChannelRule:
    """Interpolate between two channel rules of the same type."""
    if src.rule != dst.rule:
        # Type change: switch at midpoint
        if progress < 0.5:
            return _ramp_channel_out(src, progress * 2)
        return _ramp_channel_in(dst, (progress - 0.5) * 2)

    if src.rule == "window":
        return _interpolate_window(src, dst, progress)

    offset = _lerp_int(src.offset_min, dst.offset_min, progress)
    duration = None
    if src.duration_min is not None and dst.duration_min is not None:
        duration = _lerp_int(src.duration_min, dst.duration_min, progress)
    elif dst.duration_min is not None:
        duration = _lerp_int(0, dst.duration_min, progress)
    elif src.duration_min is not None:
        duration = _lerp_int(src.duration_min, 0, progress)

    return ChannelRule(rule=src.rule, offset_min=offset, duration_min=duration)


def _interpolate_window(src: ChannelRule, dst: ChannelRule, progress: float) -> ChannelRule:
    """Interpolate window channels — match windows by index, ramp durations."""
    src_wins = list(src.windows or ())
    dst_wins = list(dst.windows or ())
    max_len = max(len(src_wins), len(dst_wins))
    result_wins: list[dict] = []
    for i in range(max_len):
        if i < len(src_wins) and i < len(dst_wins):
            s_start = _parse_hhmm(src_wins[i]["start"])
            d_start = _parse_hhmm(dst_wins[i]["start"])
            interp_start = lerp_time(s_start, d_start, progress)
            dur = _lerp_int(src_wins[i]["duration_min"], dst_wins[i]["duration_min"], progress)
            result_wins.append({"start": _format_hhmm(interp_start), "duration_min": dur})
        elif i < len(dst_wins):
            # New window — ramp duration from 0
            dur = _lerp_int(0, dst_wins[i]["duration_min"], progress)
            result_wins.append({"start": dst_wins[i]["start"], "duration_min": dur})
        else:
            # Removed window — ramp duration to 0
            dur = _lerp_int(src_wins[i]["duration_min"], 0, progress)
            if dur > 0:
                result_wins.append({"start": src_wins[i]["start"], "duration_min": dur})
    return ChannelRule(rule="window", windows=tuple(result_wins))


def _ramp_channel_in(dst: ChannelRule, progress: float) -> ChannelRule:
    """Introduce a channel from zero."""
    if dst.rule == "window":
        wins = []
        for w in (dst.windows or ()):
            dur = _lerp_int(0, w["duration_min"], progress)
            wins.append({"start": w["start"], "duration_min": dur})
        return ChannelRule(rule="window", windows=tuple(wins))
    offset = dst.offset_min  # offset stays, duration ramps
    duration = None
    if dst.duration_min is not None:
        duration = _lerp_int(0, dst.duration_min, progress)
    else:
        offset = _lerp_int(0, dst.offset_min, progress)
    return ChannelRule(rule=dst.rule, offset_min=offset, duration_min=duration)


def _ramp_channel_out(src: ChannelRule, progress: float) -> ChannelRule:
    """Remove a channel toward zero."""
    if src.rule == "window":
        wins = []
        for w in (src.windows or ()):
            dur = _lerp_int(w["duration_min"], 0, progress)
            if dur > 0:
                wins.append({"start": w["start"], "duration_min": dur})
        return ChannelRule(rule="window", windows=tuple(wins))
    if src.duration_min is not None:
        duration = _lerp_int(src.duration_min, 0, progress)
        return ChannelRule(rule=src.rule, offset_min=src.offset_min, duration_min=duration)
    offset = _lerp_int(src.offset_min, 0, progress)
    return ChannelRule(rule=src.rule, offset_min=offset)
