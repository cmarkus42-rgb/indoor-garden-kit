from datetime import time, timedelta

from grow_light_recipe.models import (
    LightRecipe,
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



class TestLightRecipe:
    def test_construction(self):
        recipe = LightRecipe(
            photoperiod=TimeRange(on=time(6, 0), off=time(0, 0)),
            phase=Phase.veg,
            light_types={"main": LightConfig()},
        )
        assert recipe.phase == Phase.veg
        assert "main" in recipe.light_types

    def test_schedule_single_light_no_offset(self):
        recipe = LightRecipe(
            photoperiod=TimeRange(on=time(6, 0), off=time(0, 0)),
            phase=Phase.veg,
            light_types={"main": LightConfig()},
        )
        entries = recipe.schedule()
        assert len(entries) == 1
        assert entries[0] == ScheduleEntry(
            light_type="main", on_time=time(6, 0), off_time=time(0, 0)
        )

    def test_schedule_with_offsets(self):
        recipe = LightRecipe(
            photoperiod=TimeRange(on=time(6, 0), off=time(0, 0)),
            phase=Phase.veg,
            light_types={
                "main": LightConfig(),
                "far_red": LightConfig(
                    offset_before=timedelta(0),
                    offset_after=timedelta(minutes=15),
                ),
            },
        )
        entries = recipe.schedule()
        by_type = {e.light_type: e for e in entries}
        assert by_type["main"].on_time == time(6, 0)
        assert by_type["main"].off_time == time(0, 0)
        assert by_type["far_red"].on_time == time(6, 0)
        assert by_type["far_red"].off_time == time(0, 15)

    def test_schedule_with_before_offset(self):
        recipe = LightRecipe(
            photoperiod=TimeRange(on=time(6, 0), off=time(0, 0)),
            phase=Phase.veg,
            light_types={
                "dawn": LightConfig(
                    offset_before=timedelta(minutes=30),
                    offset_after=timedelta(0),
                ),
            },
        )
        entries = recipe.schedule()
        assert entries[0].on_time == time(5, 30)
        assert entries[0].off_time == time(0, 0)

    def test_schedule_filters_by_phase(self):
        recipe = LightRecipe(
            photoperiod=TimeRange(on=time(6, 0), off=time(0, 0)),
            phase=Phase.veg,
            light_types={
                "main": LightConfig(phases=(Phase.veg, Phase.flower)),
                "flower_boost": LightConfig(phases=(Phase.flower,)),
            },
        )
        entries = recipe.schedule()
        assert len(entries) == 1
        assert entries[0].light_type == "main"

    def test_schedule_empty_when_no_lights_for_phase(self):
        recipe = LightRecipe(
            photoperiod=TimeRange(on=time(8, 0), off=time(20, 0)),
            phase=Phase.veg,
            light_types={
                "flower_only": LightConfig(phases=(Phase.flower,)),
            },
        )
        assert recipe.schedule() == []

    def test_schedule_multiple_lights_sorted_by_on_time(self):
        recipe = LightRecipe(
            photoperiod=TimeRange(on=time(6, 0), off=time(0, 0)),
            phase=Phase.veg,
            light_types={
                "main": LightConfig(),
                "dawn": LightConfig(
                    offset_before=timedelta(minutes=30),
                    offset_after=timedelta(0),
                ),
            },
        )
        entries = recipe.schedule()
        assert len(entries) == 2
        # dawn starts at 05:30, main at 06:00
        assert entries[0].light_type == "dawn"
        assert entries[1].light_type == "main"
