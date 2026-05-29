from datetime import datetime, timedelta, timezone

from grow_irrigation.models import IrrigationZone
from grow_irrigation.engine import IrrigationEngine


def _zone(
    name: str = "tent-a",
    sensors: list[str] | None = None,
    dry: float = 30.0,
    wet: float = 60.0,
    min_iv: timedelta = timedelta(hours=2),
    max_dur: timedelta = timedelta(minutes=5),
) -> IrrigationZone:
    return IrrigationZone(
        name=name,
        sensors=sensors or ["s1"],
        dry_threshold=dry,
        wet_threshold=wet,
        min_interval=min_iv,
        max_duration=max_dur,
    )


def _now() -> datetime:
    return datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


class TestEvaluateStartStop:
    def test_dry_triggers_start(self):
        engine = IrrigationEngine(zones=[_zone()])
        actions = engine.evaluate({"s1": 25.0}, now=_now())
        assert len(actions) == 1
        assert actions[0].action == "start"
        assert actions[0].zone == "tent-a"

    def test_wet_is_noop(self):
        engine = IrrigationEngine(zones=[_zone()])
        actions = engine.evaluate({"s1": 50.0}, now=_now())
        assert len(actions) == 1
        assert actions[0].action == "noop"

    def test_at_dry_threshold_is_noop(self):
        engine = IrrigationEngine(zones=[_zone()])
        actions = engine.evaluate({"s1": 30.0}, now=_now())
        assert actions[0].action == "noop"

    def test_below_dry_threshold_triggers_start(self):
        engine = IrrigationEngine(zones=[_zone()])
        actions = engine.evaluate({"s1": 29.9}, now=_now())
        assert actions[0].action == "start"

    def test_wet_threshold_stops_active_irrigation(self):
        engine = IrrigationEngine(zones=[_zone()])
        t0 = _now()
        engine.evaluate({"s1": 25.0}, now=t0)  # starts
        actions = engine.evaluate({"s1": 60.0}, now=t0 + timedelta(minutes=1))
        assert actions[0].action == "stop"
        assert "wet threshold" in actions[0].reason.lower()

    def test_still_dry_while_active_is_noop(self):
        engine = IrrigationEngine(zones=[_zone()])
        t0 = _now()
        engine.evaluate({"s1": 25.0}, now=t0)  # starts
        actions = engine.evaluate({"s1": 28.0}, now=t0 + timedelta(minutes=1))
        assert actions[0].action == "noop"
        assert "active" in actions[0].reason.lower()


class TestMultipleSensors:
    def test_average_of_sensors(self):
        zone = _zone(sensors=["s1", "s2"], dry=30.0)
        engine = IrrigationEngine(zones=[zone])
        actions = engine.evaluate({"s1": 20.0, "s2": 50.0}, now=_now())
        assert actions[0].action == "noop"

    def test_average_below_threshold_starts(self):
        zone = _zone(sensors=["s1", "s2"], dry=30.0)
        engine = IrrigationEngine(zones=[zone])
        actions = engine.evaluate({"s1": 20.0, "s2": 25.0}, now=_now())
        assert actions[0].action == "start"

    def test_missing_sensor_uses_available(self):
        zone = _zone(sensors=["s1", "s2"], dry=30.0)
        engine = IrrigationEngine(zones=[zone])
        actions = engine.evaluate({"s1": 25.0}, now=_now())
        assert actions[0].action == "start"

    def test_all_sensors_missing_is_noop(self):
        zone = _zone(sensors=["s1", "s2"])
        engine = IrrigationEngine(zones=[zone])
        actions = engine.evaluate({}, now=_now())
        assert actions[0].action == "noop"
        assert "no readings" in actions[0].reason.lower()


class TestMaxDuration:
    def test_stops_after_max_duration(self):
        zone = _zone(max_dur=timedelta(minutes=5))
        engine = IrrigationEngine(zones=[zone])
        t0 = _now()
        engine.evaluate({"s1": 25.0}, now=t0)
        actions = engine.evaluate({"s1": 25.0}, now=t0 + timedelta(minutes=5))
        assert actions[0].action == "stop"
        assert "max duration" in actions[0].reason.lower()

    def test_no_stop_before_max_duration(self):
        zone = _zone(max_dur=timedelta(minutes=5))
        engine = IrrigationEngine(zones=[zone])
        t0 = _now()
        engine.evaluate({"s1": 25.0}, now=t0)
        actions = engine.evaluate({"s1": 25.0}, now=t0 + timedelta(minutes=4))
        assert actions[0].action == "noop"


class TestMinInterval:
    def test_respects_min_interval_after_stop(self):
        zone = _zone(min_iv=timedelta(hours=2), max_dur=timedelta(minutes=5))
        engine = IrrigationEngine(zones=[zone])
        t0 = _now()
        engine.evaluate({"s1": 25.0}, now=t0)
        engine.evaluate({"s1": 60.0}, now=t0 + timedelta(minutes=3))
        actions = engine.evaluate({"s1": 25.0}, now=t0 + timedelta(minutes=33))
        assert actions[0].action == "noop"
        assert "min interval" in actions[0].reason.lower()

    def test_allows_start_after_min_interval(self):
        zone = _zone(min_iv=timedelta(hours=2), max_dur=timedelta(minutes=5))
        engine = IrrigationEngine(zones=[zone])
        t0 = _now()
        engine.evaluate({"s1": 25.0}, now=t0)
        engine.evaluate({"s1": 60.0}, now=t0 + timedelta(minutes=3))
        actions = engine.evaluate({"s1": 25.0}, now=t0 + timedelta(hours=2, minutes=4))
        assert actions[0].action == "start"


class TestApplyDayTargets:
    def test_apply_day_targets_updates_thresholds(self):
        engine = IrrigationEngine(zones=[_zone(dry=30.0, wet=60.0)])
        engine.apply_day_targets(
            dry_threshold=25.0,
            wet_threshold=55.0,
            max_duration_min=5,
            min_interval_hours=2.0,
        )
        # moisture=27 is above old dry=30 (noop) but below new dry=25? No:
        # 27 >= 25 → noop; 24 < 25 → start
        actions = engine.evaluate({"s1": 24.0}, now=_now())
        assert actions[0].action == "start"
        # Confirm old threshold wouldn't trigger: 27 < 30 → would have started too,
        # so verify with a value between old and new threshold:
        engine2 = IrrigationEngine(zones=[_zone(dry=30.0, wet=60.0)])
        engine2.apply_day_targets(
            dry_threshold=25.0,
            wet_threshold=55.0,
            max_duration_min=5,
            min_interval_hours=2.0,
        )
        # 27 is above new dry=25 → noop (would have been start with old dry=30)
        actions2 = engine2.evaluate({"s1": 27.0}, now=_now())
        assert actions2[0].action == "noop"

    def test_apply_day_targets_preserves_state(self):
        engine = IrrigationEngine(zones=[_zone(dry=30.0, wet=60.0)])
        t0 = _now()
        # Start irrigation
        engine.evaluate({"s1": 25.0}, now=t0)
        assert "tent-a" in engine._active_since
        # Apply new targets — state must survive
        engine.apply_day_targets(
            dry_threshold=25.0,
            wet_threshold=55.0,
            max_duration_min=5,
            min_interval_hours=2.0,
        )
        assert "tent-a" in engine._active_since
        # Also test last_stopped is preserved
        engine2 = IrrigationEngine(zones=[_zone(dry=30.0, wet=60.0)])
        engine2.evaluate({"s1": 25.0}, now=t0)
        engine2.evaluate({"s1": 60.0}, now=t0 + timedelta(minutes=1))
        assert "tent-a" in engine2._last_stopped
        engine2.apply_day_targets(
            dry_threshold=25.0,
            wet_threshold=55.0,
            max_duration_min=5,
            min_interval_hours=2.0,
        )
        assert "tent-a" in engine2._last_stopped


class TestMultipleZones:
    def test_independent_zones(self):
        z1 = _zone(name="zone-a", sensors=["s1"], dry=30.0)
        z2 = _zone(name="zone-b", sensors=["s2"], dry=40.0)
        engine = IrrigationEngine(zones=[z1, z2])
        actions = engine.evaluate({"s1": 25.0, "s2": 50.0}, now=_now())
        by_zone = {a.zone: a for a in actions}
        assert by_zone["zone-a"].action == "start"
        assert by_zone["zone-b"].action == "noop"
