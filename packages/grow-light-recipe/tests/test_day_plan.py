from grow_light_recipe.day_plan import (
    ChannelSchedule,
    DayPlan,
    DimmingPoint,
    compute_day_plan,
)
from grow_light_recipe.recipe import ChannelRule, DimmingConfig, Recipe


def _veg_recipe() -> Recipe:
    return Recipe(
        name="Veg Standard",
        photoperiod_on="06:00",
        photoperiod_off="00:00",
        dimming=DimmingConfig(sunrise_min=30, sunset_min=30, max_pct=100, min_pct=0),
        channels={
            "far_red": ChannelRule(rule="after_off", offset_min=1, duration_min=15),
            "dawn": ChannelRule(rule="before_on", offset_min=30),
            "uva": ChannelRule(
                rule="window",
                windows=(
                    {"start": "11:00", "duration_min": 30},
                    {"start": "14:00", "duration_min": 30},
                ),
            ),
            "deep_blue": ChannelRule(rule="before_on", offset_min=15, duration_min=20),
        },
    )


class TestChannelSchedule:
    def test_frozen(self):
        cs = ChannelSchedule(channel="test", on_time=360, off_time=720)
        try:
            cs.on_time = 0
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestDimmingPoint:
    def test_construction(self):
        dp = DimmingPoint(time=360, pct=50.0)
        assert dp.time == 360
        assert dp.pct == 50.0


class TestComputeDayPlan:
    def test_basic_structure(self):
        plan = compute_day_plan(_veg_recipe(), "2026-06-01")
        assert plan.date == "2026-06-01"
        assert plan.recipe_name == "Veg Standard"
        assert plan.transition_progress is None
        assert plan.main_on == 360   # 06:00
        assert plan.main_off == 1440  # 00:00 = 1440 (next midnight)

    def test_dimming_curve_four_points(self):
        plan = compute_day_plan(_veg_recipe(), "2026-06-01")
        assert len(plan.dimming_curve) == 4
        # Point 0: start of sunrise — min_pct at main_on
        assert plan.dimming_curve[0] == DimmingPoint(time=360, pct=0.0)
        # Point 1: end of sunrise — max_pct at main_on + sunrise_min
        assert plan.dimming_curve[1] == DimmingPoint(time=390, pct=100.0)
        # Point 2: start of sunset — max_pct at main_off - sunset_min
        assert plan.dimming_curve[2] == DimmingPoint(time=1410, pct=100.0)
        # Point 3: end of sunset — min_pct at main_off
        assert plan.dimming_curve[3] == DimmingPoint(time=1440, pct=0.0)

    def test_before_on_without_duration(self):
        """dawn: before_on 30min, no duration → off at main_on."""
        plan = compute_day_plan(_veg_recipe(), "2026-06-01")
        dawn = [c for c in plan.channels if c.channel == "dawn"]
        assert len(dawn) == 1
        assert dawn[0].on_time == 330   # 06:00 - 30 = 05:30
        assert dawn[0].off_time == 360  # main_on

    def test_before_on_with_duration(self):
        """deep_blue: before_on 15min, duration 20min → on at 05:45, off at 06:05."""
        plan = compute_day_plan(_veg_recipe(), "2026-06-01")
        db = [c for c in plan.channels if c.channel == "deep_blue"]
        assert len(db) == 1
        assert db[0].on_time == 345    # 06:00 - 15 = 05:45
        assert db[0].off_time == 365   # 05:45 + 20 = 06:05

    def test_after_off(self):
        """far_red: after_off 1min, duration 15min."""
        plan = compute_day_plan(_veg_recipe(), "2026-06-01")
        fr = [c for c in plan.channels if c.channel == "far_red"]
        assert len(fr) == 1
        assert fr[0].on_time == 1441   # 00:00 + 1 = 00:01 (next day)
        assert fr[0].off_time == 1456  # 00:01 + 15

    def test_window_channels(self):
        """uva: two windows."""
        plan = compute_day_plan(_veg_recipe(), "2026-06-01")
        uva = [c for c in plan.channels if c.channel == "uva"]
        assert len(uva) == 2
        assert uva[0].on_time == 660   # 11:00
        assert uva[0].off_time == 690  # 11:30
        assert uva[1].on_time == 840   # 14:00
        assert uva[1].off_time == 870  # 14:30

    def test_no_dimming(self):
        """Recipe with default dimming (sunrise=0, sunset=0)."""
        r = Recipe(
            name="Flat",
            photoperiod_on="08:00",
            photoperiod_off="20:00",
            dimming=DimmingConfig(),
            channels={},
        )
        plan = compute_day_plan(r, "2026-06-01")
        # sunrise/sunset both 0min → curve collapses to 4 points at same times
        assert plan.dimming_curve[0].time == 480  # 08:00
        assert plan.dimming_curve[0].pct == 0.0
        assert plan.dimming_curve[1].time == 480  # 08:00 + 0
        assert plan.dimming_curve[1].pct == 100.0

    def test_no_channels(self):
        r = Recipe(
            name="Bare",
            photoperiod_on="08:00",
            photoperiod_off="20:00",
            channels={},
        )
        plan = compute_day_plan(r, "2026-06-01")
        assert plan.channels == ()

    def test_transition_progress_passthrough(self):
        plan = compute_day_plan(_veg_recipe(), "2026-06-01", transition_progress=0.5)
        assert plan.transition_progress == 0.5
