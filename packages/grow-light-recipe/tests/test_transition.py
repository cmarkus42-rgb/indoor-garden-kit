from datetime import time, timedelta

from grow_light_recipe.models import (
    LightConfig,
    LightRecipe,
    Phase,
    ScheduleEntry,
    TimeRange,
)
from grow_light_recipe.transition import TransitionPlan


def _veg_recipe() -> LightRecipe:
    return LightRecipe(
        photoperiod=TimeRange(on=time(6, 0), off=time(0, 0)),  # 18h
        phase=Phase.veg,
        light_types={
            "main": LightConfig(),
            "far_red": LightConfig(offset_after=timedelta(minutes=15)),
        },
    )


def _flower_recipe() -> LightRecipe:
    return LightRecipe(
        photoperiod=TimeRange(on=time(8, 0), off=time(20, 0)),  # 12h
        phase=Phase.flower,
        light_types={
            "main": LightConfig(),
            "far_red": LightConfig(offset_after=timedelta(minutes=15)),
        },
    )


class TestTransitionPlanBoundaries:
    def test_day_zero_returns_from_recipe(self):
        plan = TransitionPlan(
            from_recipe=_veg_recipe(),
            to_recipe=_flower_recipe(),
            days=14,
        )
        entries = plan.schedule_for_day(0)
        by_type = {e.light_type: e for e in entries}
        assert by_type["main"].on_time == time(6, 0)
        assert by_type["main"].off_time == time(0, 0)

    def test_day_n_returns_to_recipe(self):
        plan = TransitionPlan(
            from_recipe=_veg_recipe(),
            to_recipe=_flower_recipe(),
            days=14,
        )
        entries = plan.schedule_for_day(14)
        by_type = {e.light_type: e for e in entries}
        assert by_type["main"].on_time == time(8, 0)
        assert by_type["main"].off_time == time(20, 0)

    def test_negative_day_clamps_to_from(self):
        plan = TransitionPlan(
            from_recipe=_veg_recipe(),
            to_recipe=_flower_recipe(),
            days=14,
        )
        entries = plan.schedule_for_day(-1)
        by_type = {e.light_type: e for e in entries}
        assert by_type["main"].on_time == time(6, 0)

    def test_beyond_n_clamps_to_target(self):
        plan = TransitionPlan(
            from_recipe=_veg_recipe(),
            to_recipe=_flower_recipe(),
            days=14,
        )
        entries = plan.schedule_for_day(20)
        by_type = {e.light_type: e for e in entries}
        assert by_type["main"].on_time == time(8, 0)


class TestTransitionPlanInterpolation:
    def test_midpoint_interpolates_photoperiod(self):
        plan = TransitionPlan(
            from_recipe=_veg_recipe(),
            to_recipe=_flower_recipe(),
            days=14,
        )
        entries = plan.schedule_for_day(7)
        by_type = {e.light_type: e for e in entries}
        # on: 06:00 -> 08:00, midpoint = 07:00
        assert by_type["main"].on_time == time(7, 0)
        # off: 00:00 -> 20:00. Shortest path: 00:00 backward 4h = 20:00
        # Midpoint via shortest path: 00:00 - 2h = 22:00
        assert by_type["main"].off_time == time(22, 0)

    def test_far_red_offset_applied_to_interpolated_period(self):
        plan = TransitionPlan(
            from_recipe=_veg_recipe(),
            to_recipe=_flower_recipe(),
            days=14,
        )
        entries = plan.schedule_for_day(7)
        by_type = {e.light_type: e for e in entries}
        # far_red has +15min offset_after on the interpolated off time (22:00)
        assert by_type["far_red"].off_time == time(22, 15)

    def test_quarter_interpolation(self):
        plan = TransitionPlan(
            from_recipe=_veg_recipe(),
            to_recipe=_flower_recipe(),
            days=8,
        )
        entries = plan.schedule_for_day(2)
        by_type = {e.light_type: e for e in entries}
        # on: 06:00 -> 08:00, t=0.25, lerp = 06:30
        assert by_type["main"].on_time == time(6, 30)

    def test_single_day_transition(self):
        plan = TransitionPlan(
            from_recipe=_veg_recipe(),
            to_recipe=_flower_recipe(),
            days=1,
        )
        # Day 0 = from, Day 1 = to, no intermediate days
        assert plan.schedule_for_day(0) == _veg_recipe().schedule()
        assert plan.schedule_for_day(1) == _flower_recipe().schedule()


class TestTransitionPlanPhaseHandling:
    def test_uses_to_recipe_light_types_for_intermediate_days(self):
        veg = LightRecipe(
            photoperiod=TimeRange(on=time(6, 0), off=time(0, 0)),
            phase=Phase.veg,
            light_types={
                "main": LightConfig(),
                "veg_boost": LightConfig(phases=(Phase.veg,)),
            },
        )
        flower = LightRecipe(
            photoperiod=TimeRange(on=time(8, 0), off=time(20, 0)),
            phase=Phase.flower,
            light_types={
                "main": LightConfig(),
                "flower_boost": LightConfig(phases=(Phase.flower,)),
            },
        )
        plan = TransitionPlan(from_recipe=veg, to_recipe=flower, days=10)
        entries = plan.schedule_for_day(5)
        types = {e.light_type for e in entries}
        # Intermediate uses to_recipe's light_types + phase
        assert "main" in types
        assert "flower_boost" in types
        assert "veg_boost" not in types
