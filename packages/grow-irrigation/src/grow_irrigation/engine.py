from __future__ import annotations

from datetime import datetime

from grow_irrigation.models import IrrigationAction, IrrigationZone


class IrrigationEngine:
    def __init__(self, zones: list[IrrigationZone]) -> None:
        self._zones = zones
        self._active_since: dict[str, datetime] = {}
        self._last_stopped: dict[str, datetime] = {}

    def evaluate(
        self, readings: dict[str, float], *, now: datetime
    ) -> list[IrrigationAction]:
        return [self._evaluate_zone(zone, readings, now) for zone in self._zones]

    def _evaluate_zone(
        self,
        zone: IrrigationZone,
        readings: dict[str, float],
        now: datetime,
    ) -> IrrigationAction:
        is_active = zone.name in self._active_since

        if is_active:
            elapsed = now - self._active_since[zone.name]
            if elapsed >= zone.max_duration:
                self._stop(zone.name, now)
                return IrrigationAction(
                    zone=zone.name,
                    action="stop",
                    reason=f"max duration {zone.max_duration} reached",
                )

        values = [readings[s] for s in zone.sensors if s in readings]
        if not values:
            return IrrigationAction(
                zone=zone.name, action="noop", reason="no readings available"
            )
        avg = sum(values) / len(values)

        if is_active:
            if avg >= zone.wet_threshold:
                self._stop(zone.name, now)
                return IrrigationAction(
                    zone=zone.name,
                    action="stop",
                    reason=f"avg moisture {avg:.1f}% reached wet threshold {zone.wet_threshold}%",
                )
            return IrrigationAction(
                zone=zone.name,
                action="noop",
                reason=f"active, avg moisture {avg:.1f}%",
            )

        if avg >= zone.dry_threshold:
            return IrrigationAction(
                zone=zone.name,
                action="noop",
                reason=f"avg moisture {avg:.1f}% above dry threshold {zone.dry_threshold}%",
            )

        if zone.name in self._last_stopped:
            since_stop = now - self._last_stopped[zone.name]
            if since_stop < zone.min_interval:
                return IrrigationAction(
                    zone=zone.name,
                    action="noop",
                    reason=f"min interval {zone.min_interval} not elapsed ({since_stop} since last stop)",
                )

        self._active_since[zone.name] = now
        return IrrigationAction(
            zone=zone.name,
            action="start",
            reason=f"avg moisture {avg:.1f}% below dry threshold {zone.dry_threshold}%",
        )

    def _stop(self, zone_name: str, now: datetime) -> None:
        del self._active_since[zone_name]
        self._last_stopped[zone_name] = now
