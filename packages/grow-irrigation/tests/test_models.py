from datetime import timedelta
from typing import Literal

from grow_irrigation.models import IrrigationZone, IrrigationAction


class TestIrrigationZone:
    def test_construction(self):
        zone = IrrigationZone(
            name="tent-a",
            sensors=["sensor-1", "sensor-2"],
            dry_threshold=30.0,
            wet_threshold=60.0,
            min_interval=timedelta(hours=2),
            max_duration=timedelta(minutes=5),
        )
        assert zone.name == "tent-a"
        assert zone.sensors == ["sensor-1", "sensor-2"]
        assert zone.dry_threshold == 30.0
        assert zone.wet_threshold == 60.0
        assert zone.min_interval == timedelta(hours=2)
        assert zone.max_duration == timedelta(minutes=5)

    def test_frozen(self):
        zone = IrrigationZone(
            name="tent-a",
            sensors=["s1"],
            dry_threshold=30.0,
            wet_threshold=60.0,
            min_interval=timedelta(hours=1),
            max_duration=timedelta(minutes=3),
        )
        try:
            zone.name = "other"
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestIrrigationAction:
    def test_start_action(self):
        action = IrrigationAction(
            zone="tent-a",
            action="start",
            reason="soil moisture 25% below dry threshold 30%",
        )
        assert action.zone == "tent-a"
        assert action.action == "start"
        assert "25%" in action.reason

    def test_stop_action(self):
        action = IrrigationAction(
            zone="tent-a",
            action="stop",
            reason="max duration reached",
        )
        assert action.action == "stop"

    def test_noop_action(self):
        action = IrrigationAction(
            zone="tent-a",
            action="noop",
            reason="moisture 45% within range",
        )
        assert action.action == "noop"
