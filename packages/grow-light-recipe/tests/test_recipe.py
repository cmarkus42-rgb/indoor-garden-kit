from grow_light_recipe.recipe import ChannelRule, DimmingConfig, Recipe


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
