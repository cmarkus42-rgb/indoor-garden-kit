from grow_light_recipe.interpolate import interpolate_recipes
from grow_light_recipe.recipe import ChannelRule, DimmingConfig, Recipe


def _veg() -> Recipe:
    return Recipe(
        name="Veg",
        photoperiod_on="06:00",
        photoperiod_off="00:00",
        dimming=DimmingConfig(sunrise_min=30, sunset_min=30, max_pct=100, min_pct=0),
        channels={
            "far_red": ChannelRule(rule="after_off", offset_min=1, duration_min=15),
            "dawn": ChannelRule(rule="before_on", offset_min=30),
        },
    )


def _flower() -> Recipe:
    return Recipe(
        name="Flower",
        photoperiod_on="08:00",
        photoperiod_off="20:00",
        dimming=DimmingConfig(sunrise_min=60, sunset_min=60, max_pct=80, min_pct=10),
        channels={
            "far_red": ChannelRule(rule="after_off", offset_min=5, duration_min=30),
            "uva": ChannelRule(
                rule="window",
                windows=({"start": "12:00", "duration_min": 60},),
            ),
        },
    )


class TestInterpolateProgress:
    def test_progress_zero_equals_source(self):
        result = interpolate_recipes(_veg(), _flower(), 0.0)
        assert result.photoperiod_on == "06:00"
        assert result.photoperiod_off == "00:00"
        assert result.dimming.sunrise_min == 30
        assert result.dimming.max_pct == 100

    def test_progress_one_equals_target(self):
        result = interpolate_recipes(_veg(), _flower(), 1.0)
        assert result.photoperiod_on == "08:00"
        assert result.photoperiod_off == "20:00"
        assert result.dimming.sunrise_min == 60
        assert result.dimming.max_pct == 80

    def test_midpoint_photoperiod(self):
        result = interpolate_recipes(_veg(), _flower(), 0.5)
        # on: 06:00 → 08:00, midpoint = 07:00
        assert result.photoperiod_on == "07:00"
        # off: 00:00 → 20:00, shortest path backward = 22:00
        assert result.photoperiod_off == "22:00"

    def test_midpoint_dimming(self):
        result = interpolate_recipes(_veg(), _flower(), 0.5)
        assert result.dimming.sunrise_min == 45  # (30+60)/2
        assert result.dimming.sunset_min == 45
        assert result.dimming.max_pct == 90      # (100+80)/2
        assert result.dimming.min_pct == 5        # (0+10)/2


class TestInterpolateChannels:
    def test_shared_channel_interpolated(self):
        """far_red exists in both — offset and duration interpolated."""
        result = interpolate_recipes(_veg(), _flower(), 0.5)
        fr = result.channels["far_red"]
        assert fr.offset_min == 3     # round((1+5)/2)
        assert fr.duration_min == 22  # round((15+30)/2) = 22 (midpoint rounds down)

    def test_channel_in_target_only_introduced(self):
        """uva is only in flower — at progress 0.5, duration ramped from 0."""
        result = interpolate_recipes(_veg(), _flower(), 0.5)
        assert "uva" in result.channels
        uva = result.channels["uva"]
        assert uva.rule == "window"
        # duration_min in window: 60 * 0.5 = 30
        assert uva.windows is not None
        assert uva.windows[0]["duration_min"] == 30

    def test_channel_in_source_only_removed(self):
        """dawn is only in veg — at progress 0.5, offset ramped toward 0."""
        result = interpolate_recipes(_veg(), _flower(), 0.5)
        assert "dawn" in result.channels
        dawn = result.channels["dawn"]
        assert dawn.offset_min == 15  # 30 * (1 - 0.5) = 15

    def test_channel_in_source_gone_at_progress_one(self):
        """dawn fully removed at progress 1.0."""
        result = interpolate_recipes(_veg(), _flower(), 1.0)
        # dawn should have offset_min=0 or be absent
        if "dawn" in result.channels:
            assert result.channels["dawn"].offset_min == 0

    def test_name_uses_interpolated_marker(self):
        result = interpolate_recipes(_veg(), _flower(), 0.5)
        assert "Veg" in result.name
        assert "Flower" in result.name
