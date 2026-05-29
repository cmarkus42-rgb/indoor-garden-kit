from grow_recipe.interpolate import interpolate_recipes
from grow_recipe.models import ClimateConfig, IrrigationConfig
from grow_recipe.recipe import ChannelRule, DimmingConfig, Recipe


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


class TestInterpolateClimate:
    def _with_climate(self, base: Recipe, climate: ClimateConfig) -> Recipe:
        return Recipe(
            name=base.name,
            photoperiod_on=base.photoperiod_on,
            photoperiod_off=base.photoperiod_off,
            dimming=base.dimming,
            channels=base.channels,
            climate=climate,
        )

    def test_both_have_climate_midpoint(self):
        """Both recipes have climate — all 4 fields lerped at t=0.5."""
        from_r = self._with_climate(_veg(), ClimateConfig(fan_intensity=4, temp_target_c=24.0, humidity_target=55.0, vpd_target_kpa=1.0))
        to_r = self._with_climate(_flower(), ClimateConfig(fan_intensity=8, temp_target_c=28.0, humidity_target=65.0, vpd_target_kpa=1.4))
        result = interpolate_recipes(from_r, to_r, 0.5)
        c = result.climate
        assert c is not None
        assert c.fan_intensity == 6         # round((4+8)/2)
        assert c.temp_target_c == 26.0      # (24+28)/2
        assert c.humidity_target == 60.0    # (55+65)/2
        assert c.vpd_target_kpa == 1.2      # (1.0+1.4)/2

    def test_both_have_climate_at_progress_zero(self):
        """At t=0, result climate equals from_r climate."""
        climate_from = ClimateConfig(fan_intensity=3, temp_target_c=22.0, humidity_target=50.0, vpd_target_kpa=0.9)
        climate_to = ClimateConfig(fan_intensity=9, temp_target_c=30.0, humidity_target=70.0, vpd_target_kpa=1.6)
        from_r = self._with_climate(_veg(), climate_from)
        to_r = self._with_climate(_flower(), climate_to)
        result = interpolate_recipes(from_r, to_r, 0.0)
        assert result.climate == climate_from

    def test_both_have_climate_at_progress_one(self):
        """At t=1, result climate equals to_r climate."""
        climate_from = ClimateConfig(fan_intensity=3, temp_target_c=22.0, humidity_target=50.0, vpd_target_kpa=0.9)
        climate_to = ClimateConfig(fan_intensity=9, temp_target_c=30.0, humidity_target=70.0, vpd_target_kpa=1.6)
        from_r = self._with_climate(_veg(), climate_from)
        to_r = self._with_climate(_flower(), climate_to)
        result = interpolate_recipes(from_r, to_r, 1.0)
        assert result.climate == climate_to

    def test_only_target_has_climate_ramp_in(self):
        """Only to_r has climate — ramp from defaults at t=0.5."""
        to_r = self._with_climate(_flower(), ClimateConfig(fan_intensity=10, temp_target_c=30.0, humidity_target=70.0, vpd_target_kpa=1.6))
        result = interpolate_recipes(_veg(), to_r, 0.5)
        c = result.climate
        assert c is not None
        # fan: round((5+10)/2) = 8 (default=5)
        assert c.fan_intensity == 8
        # temp: (25.0+30.0)/2 = 27.5 (default=25.0)
        assert c.temp_target_c == 27.5

    def test_only_source_has_climate_ramp_out(self):
        """Only from_r has climate — ramp toward defaults at t=0.5."""
        from_r = self._with_climate(_veg(), ClimateConfig(fan_intensity=10, temp_target_c=30.0, humidity_target=70.0, vpd_target_kpa=1.6))
        result = interpolate_recipes(from_r, _flower(), 0.5)
        c = result.climate
        assert c is not None
        # fan: round((10+5)/2) = 8 (toward default=5)
        assert c.fan_intensity == 8
        # temp: (30.0+25.0)/2 = 27.5 (toward default=25.0)
        assert c.temp_target_c == 27.5

    def test_neither_has_climate_returns_none(self):
        """Neither recipe has climate — result climate is None."""
        result = interpolate_recipes(_veg(), _flower(), 0.5)
        assert result.climate is None


class TestInterpolateIrrigation:
    def _with_irrigation(self, base: Recipe, irrigation: IrrigationConfig) -> Recipe:
        return Recipe(
            name=base.name,
            photoperiod_on=base.photoperiod_on,
            photoperiod_off=base.photoperiod_off,
            dimming=base.dimming,
            channels=base.channels,
            irrigation=irrigation,
        )

    def test_both_have_irrigation_midpoint(self):
        """Both recipes have irrigation — all 4 fields lerped at t=0.5."""
        from_r = self._with_irrigation(_veg(), IrrigationConfig(dry_threshold=20.0, wet_threshold=50.0, max_duration_min=4, min_interval_hours=1.0))
        to_r = self._with_irrigation(_flower(), IrrigationConfig(dry_threshold=40.0, wet_threshold=70.0, max_duration_min=8, min_interval_hours=3.0))
        result = interpolate_recipes(from_r, to_r, 0.5)
        irr = result.irrigation
        assert irr is not None
        assert irr.dry_threshold == 30.0     # (20+40)/2
        assert irr.wet_threshold == 60.0     # (50+70)/2
        assert irr.max_duration_min == 6     # round((4+8)/2)
        assert irr.min_interval_hours == 2.0 # (1.0+3.0)/2

    def test_only_target_has_irrigation_ramp_in(self):
        """Only to_r has irrigation — ramp from defaults at t=0.5."""
        to_r = self._with_irrigation(_flower(), IrrigationConfig(dry_threshold=40.0, wet_threshold=80.0, max_duration_min=10, min_interval_hours=4.0))
        result = interpolate_recipes(_veg(), to_r, 0.5)
        irr = result.irrigation
        assert irr is not None
        # dry: (30.0+40.0)/2 = 35.0 (default=30.0)
        assert irr.dry_threshold == 35.0
        # max_duration: round((5+10)/2) = 8 (default=5)
        assert irr.max_duration_min == 8

    def test_only_source_has_irrigation_ramp_out(self):
        """Only from_r has irrigation — ramp toward defaults at t=0.5."""
        from_r = self._with_irrigation(_veg(), IrrigationConfig(dry_threshold=40.0, wet_threshold=80.0, max_duration_min=10, min_interval_hours=4.0))
        result = interpolate_recipes(from_r, _flower(), 0.5)
        irr = result.irrigation
        assert irr is not None
        # dry: (40.0+30.0)/2 = 35.0 (toward default=30.0)
        assert irr.dry_threshold == 35.0

    def test_neither_has_irrigation_returns_none(self):
        """Neither recipe has irrigation — result irrigation is None."""
        result = interpolate_recipes(_veg(), _flower(), 0.5)
        assert result.irrigation is None
