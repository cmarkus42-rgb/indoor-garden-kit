from grow_recipe.models import ClimateConfig, IrrigationConfig
from grow_recipe.recipe import ChannelRule, DimmingConfig, Recipe


VEG_DICT = {
    "name": "Veg Standard",
    "photoperiod": {"on": "06:00", "off": "00:00"},
    "dimming": {
        "sunrise_min": 30,
        "sunset_min": 30,
        "max_pct": 100,
        "min_pct": 0,
    },
    "channels": {
        "far_red": {
            "rule": "after_off",
            "offset_min": 1,
            "duration_min": 15,
        },
        "dawn": {
            "rule": "before_on",
            "offset_min": 30,
        },
        "uva": {
            "rule": "window",
            "windows": [
                {"start": "11:00", "duration_min": 30},
                {"start": "14:00", "duration_min": 30},
            ],
        },
    },
}


class TestChannelRule:
    def test_before_on(self):
        rule = ChannelRule(rule="before_on", offset_min=30)
        assert rule.rule == "before_on"
        assert rule.offset_min == 30
        assert rule.duration_min is None
        assert rule.windows is None

    def test_after_off(self):
        rule = ChannelRule(rule="after_off", offset_min=1, duration_min=15)
        assert rule.duration_min == 15

    def test_window(self):
        rule = ChannelRule(
            rule="window",
            windows=({"start": "11:00", "duration_min": 30},),
        )
        assert rule.windows is not None
        assert len(rule.windows) == 1

    def test_frozen(self):
        rule = ChannelRule(rule="before_on", offset_min=10)
        try:
            rule.offset_min = 20
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestDimmingConfig:
    def test_construction(self):
        d = DimmingConfig(sunrise_min=30, sunset_min=30, max_pct=100, min_pct=0)
        assert d.sunrise_min == 30
        assert d.max_pct == 100

    def test_defaults(self):
        d = DimmingConfig()
        assert d.sunrise_min == 0
        assert d.sunset_min == 0
        assert d.max_pct == 100
        assert d.min_pct == 0


class TestRecipe:
    def test_construction(self):
        r = Recipe(
            name="Test",
            photoperiod_on="06:00",
            photoperiod_off="00:00",
            dimming=DimmingConfig(),
            channels={},
        )
        assert r.name == "Test"
        assert r.photoperiod_on == "06:00"

    def test_from_dict(self):
        r = Recipe.from_dict(VEG_DICT)
        assert r.name == "Veg Standard"
        assert r.photoperiod_on == "06:00"
        assert r.photoperiod_off == "00:00"
        assert r.dimming.sunrise_min == 30
        assert r.dimming.max_pct == 100
        assert "far_red" in r.channels
        assert r.channels["far_red"].rule == "after_off"
        assert r.channels["dawn"].offset_min == 30
        assert r.channels["uva"].rule == "window"
        assert len(r.channels["uva"].windows) == 2

    def test_to_dict(self):
        r = Recipe.from_dict(VEG_DICT)
        d = r.to_dict()
        assert d["name"] == "Veg Standard"
        assert d["photoperiod"]["on"] == "06:00"
        assert d["dimming"]["sunrise_min"] == 30
        assert d["channels"]["far_red"]["rule"] == "after_off"
        assert d["channels"]["far_red"]["duration_min"] == 15
        assert len(d["channels"]["uva"]["windows"]) == 2

    def test_roundtrip(self):
        r1 = Recipe.from_dict(VEG_DICT)
        d = r1.to_dict()
        r2 = Recipe.from_dict(d)
        assert r1 == r2

    def test_frozen(self):
        r = Recipe.from_dict(VEG_DICT)
        try:
            r.name = "Changed"
            assert False, "Should be frozen"
        except AttributeError:
            pass

    def test_minimal_recipe(self):
        """Recipe with no channels and default dimming."""
        d = {
            "name": "Bare",
            "photoperiod": {"on": "08:00", "off": "20:00"},
        }
        r = Recipe.from_dict(d)
        assert r.name == "Bare"
        assert r.dimming.sunrise_min == 0
        assert r.channels == {}


class TestRecipeClimateIrrigation:
    def test_recipe_climate_defaults_to_none(self):
        r = Recipe(name="X", photoperiod_on="06:00", photoperiod_off="00:00")
        assert r.climate is None

    def test_recipe_irrigation_defaults_to_none(self):
        r = Recipe(name="X", photoperiod_on="06:00", photoperiod_off="00:00")
        assert r.irrigation is None

    def test_from_dict_without_climate_or_irrigation(self):
        d = {"name": "Old", "photoperiod": {"on": "06:00", "off": "00:00"}}
        r = Recipe.from_dict(d)
        assert r.climate is None
        assert r.irrigation is None

    def test_from_dict_with_climate(self):
        d = {
            "name": "Climate Recipe",
            "photoperiod": {"on": "06:00", "off": "00:00"},
            "climate": {"fan_intensity": 7, "temp_target_c": 22.0, "humidity_target": 55.0, "vpd_target_kpa": 0.9},
        }
        r = Recipe.from_dict(d)
        assert r.climate is not None
        assert r.climate.fan_intensity == 7
        assert r.climate.temp_target_c == 22.0

    def test_from_dict_with_irrigation(self):
        d = {
            "name": "Irrigation Recipe",
            "photoperiod": {"on": "06:00", "off": "00:00"},
            "irrigation": {"dry_threshold": 25.0, "wet_threshold": 55.0, "max_duration_min": 8, "min_interval_hours": 3.0},
        }
        r = Recipe.from_dict(d)
        assert r.irrigation is not None
        assert r.irrigation.dry_threshold == 25.0
        assert r.irrigation.max_duration_min == 8

    def test_to_dict_omits_none_climate(self):
        r = Recipe(name="X", photoperiod_on="06:00", photoperiod_off="00:00")
        d = r.to_dict()
        assert "climate" not in d

    def test_to_dict_omits_none_irrigation(self):
        r = Recipe(name="X", photoperiod_on="06:00", photoperiod_off="00:00")
        d = r.to_dict()
        assert "irrigation" not in d

    def test_to_dict_includes_climate_when_set(self):
        r = Recipe(
            name="X",
            photoperiod_on="06:00",
            photoperiod_off="00:00",
            climate=ClimateConfig(fan_intensity=4),
        )
        d = r.to_dict()
        assert "climate" in d
        assert d["climate"]["fan_intensity"] == 4

    def test_to_dict_includes_irrigation_when_set(self):
        r = Recipe(
            name="X",
            photoperiod_on="06:00",
            photoperiod_off="00:00",
            irrigation=IrrigationConfig(max_duration_min=10),
        )
        d = r.to_dict()
        assert "irrigation" in d
        assert d["irrigation"]["max_duration_min"] == 10

    def test_roundtrip_with_both(self):
        r1 = Recipe(
            name="Full",
            photoperiod_on="06:00",
            photoperiod_off="00:00",
            climate=ClimateConfig(fan_intensity=6, temp_target_c=21.0, humidity_target=65.0, vpd_target_kpa=1.1),
            irrigation=IrrigationConfig(dry_threshold=28.0, wet_threshold=58.0, max_duration_min=6, min_interval_hours=2.5),
        )
        r2 = Recipe.from_dict(r1.to_dict())
        assert r2.climate == r1.climate
        assert r2.irrigation == r1.irrigation

    def test_backward_compat_old_dict_no_new_keys(self):
        """Dicts without climate/irrigation keys must still parse correctly."""
        d = {
            "name": "Legacy",
            "photoperiod": {"on": "08:00", "off": "20:00"},
            "dimming": {"sunrise_min": 15, "sunset_min": 15, "max_pct": 80, "min_pct": 5},
            "channels": {"main": {"rule": "before_on", "offset_min": 10}},
        }
        r = Recipe.from_dict(d)
        assert r.climate is None
        assert r.irrigation is None
        assert r.dimming.sunrise_min == 15
        assert "main" in r.channels
