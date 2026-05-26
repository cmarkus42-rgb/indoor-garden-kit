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
