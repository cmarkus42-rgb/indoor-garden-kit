def test_public_api_imports():
    from grow_light_recipe import (
        Phase,
        TimeRange,
        LightConfig,
        LightRecipe,
        ScheduleEntry,
        TransitionPlan,
    )
    assert Phase.veg == "veg"
    assert TransitionPlan is not None


def test_composer_api_imports():
    from grow_light_recipe import (
        Recipe,
        ChannelRule,
        DimmingConfig,
        DayPlan,
        DimmingPoint,
        ChannelSchedule,
        RecipeQueue,
        RecipeEntry,
        TransitionEntry,
        compute_day_plan,
        interpolate_recipes,
    )
    assert Recipe is not None
    assert DayPlan is not None
    assert RecipeQueue is not None
    assert compute_day_plan is not None
    assert interpolate_recipes is not None
