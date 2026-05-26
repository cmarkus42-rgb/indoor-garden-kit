from datetime import time, timedelta

from grow_light_recipe.models import (
    Phase,
    TimeRange,
    LightConfig,
    ScheduleEntry,
)


class TestPhase:
    def test_veg_value(self):
        assert Phase.veg == "veg"

    def test_flower_value(self):
        assert Phase.flower == "flower"

    def test_is_string(self):
        assert isinstance(Phase.veg, str)


class TestTimeRange:
    def test_construction(self):
        tr = TimeRange(on=time(6, 0), off=time(0, 0))
        assert tr.on == time(6, 0)
        assert tr.off == time(0, 0)

    def test_frozen(self):
        tr = TimeRange(on=time(6, 0), off=time(0, 0))
        try:
            tr.on = time(7, 0)
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestLightConfig:
    def test_defaults(self):
        cfg = LightConfig()
        assert cfg.offset_before == timedelta()
        assert cfg.offset_after == timedelta()
        assert cfg.phases == (Phase.veg, Phase.flower)

    def test_custom(self):
        cfg = LightConfig(
            offset_before=timedelta(minutes=15),
            offset_after=timedelta(minutes=30),
            phases=(Phase.flower,),
        )
        assert cfg.offset_before == timedelta(minutes=15)
        assert cfg.phases == (Phase.flower,)


class TestScheduleEntry:
    def test_construction(self):
        entry = ScheduleEntry(light_type="far_red", on_time=time(6, 0), off_time=time(0, 15))
        assert entry.light_type == "far_red"
        assert entry.on_time == time(6, 0)
        assert entry.off_time == time(0, 15)
