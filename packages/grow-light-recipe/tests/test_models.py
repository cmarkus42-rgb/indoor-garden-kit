from datetime import time, timedelta

from grow_recipe.models import (
    ClimateConfig,
    IrrigationConfig,
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


class TestClimateConfig:
    def test_defaults(self):
        cfg = ClimateConfig()
        assert cfg.fan_intensity == 5
        assert cfg.temp_target_c == 25.0
        assert cfg.humidity_target == 60.0
        assert cfg.vpd_target_kpa == 1.2

    def test_construction(self):
        cfg = ClimateConfig(fan_intensity=8, temp_target_c=22.0, humidity_target=55.0, vpd_target_kpa=0.9)
        assert cfg.fan_intensity == 8
        assert cfg.temp_target_c == 22.0
        assert cfg.humidity_target == 55.0
        assert cfg.vpd_target_kpa == 0.9

    def test_frozen(self):
        cfg = ClimateConfig()
        try:
            cfg.fan_intensity = 10
            assert False, "Should be frozen"
        except AttributeError:
            pass

    def test_to_dict(self):
        cfg = ClimateConfig(fan_intensity=7, temp_target_c=23.5, humidity_target=58.0, vpd_target_kpa=1.0)
        d = cfg.to_dict()
        assert d == {
            "fan_intensity": 7,
            "temp_target_c": 23.5,
            "humidity_target": 58.0,
            "vpd_target_kpa": 1.0,
        }

    def test_from_dict(self):
        d = {"fan_intensity": 3, "temp_target_c": 20.0, "humidity_target": 70.0, "vpd_target_kpa": 1.5}
        cfg = ClimateConfig.from_dict(d)
        assert cfg.fan_intensity == 3
        assert cfg.temp_target_c == 20.0
        assert cfg.humidity_target == 70.0
        assert cfg.vpd_target_kpa == 1.5

    def test_from_dict_uses_defaults_for_missing_keys(self):
        cfg = ClimateConfig.from_dict({})
        assert cfg.fan_intensity == 5
        assert cfg.temp_target_c == 25.0
        assert cfg.humidity_target == 60.0
        assert cfg.vpd_target_kpa == 1.2

    def test_roundtrip(self):
        cfg = ClimateConfig(fan_intensity=6, temp_target_c=21.0, humidity_target=65.0, vpd_target_kpa=1.1)
        assert ClimateConfig.from_dict(cfg.to_dict()) == cfg


class TestIrrigationConfig:
    def test_defaults(self):
        cfg = IrrigationConfig()
        assert cfg.dry_threshold == 30.0
        assert cfg.wet_threshold == 60.0
        assert cfg.max_duration_min == 5
        assert cfg.min_interval_hours == 2.0

    def test_construction(self):
        cfg = IrrigationConfig(dry_threshold=25.0, wet_threshold=55.0, max_duration_min=10, min_interval_hours=4.0)
        assert cfg.dry_threshold == 25.0
        assert cfg.wet_threshold == 55.0
        assert cfg.max_duration_min == 10
        assert cfg.min_interval_hours == 4.0

    def test_frozen(self):
        cfg = IrrigationConfig()
        try:
            cfg.dry_threshold = 99.0
            assert False, "Should be frozen"
        except AttributeError:
            pass

    def test_to_dict(self):
        cfg = IrrigationConfig(dry_threshold=20.0, wet_threshold=50.0, max_duration_min=3, min_interval_hours=1.5)
        d = cfg.to_dict()
        assert d == {
            "dry_threshold": 20.0,
            "wet_threshold": 50.0,
            "max_duration_min": 3,
            "min_interval_hours": 1.5,
        }

    def test_from_dict(self):
        d = {"dry_threshold": 35.0, "wet_threshold": 65.0, "max_duration_min": 8, "min_interval_hours": 3.0}
        cfg = IrrigationConfig.from_dict(d)
        assert cfg.dry_threshold == 35.0
        assert cfg.wet_threshold == 65.0
        assert cfg.max_duration_min == 8
        assert cfg.min_interval_hours == 3.0

    def test_from_dict_uses_defaults_for_missing_keys(self):
        cfg = IrrigationConfig.from_dict({})
        assert cfg.dry_threshold == 30.0
        assert cfg.wet_threshold == 60.0
        assert cfg.max_duration_min == 5
        assert cfg.min_interval_hours == 2.0

    def test_roundtrip(self):
        cfg = IrrigationConfig(dry_threshold=28.0, wet_threshold=58.0, max_duration_min=6, min_interval_hours=2.5)
        assert IrrigationConfig.from_dict(cfg.to_dict()) == cfg
