"""Light schedule recipe engine with photoperiod transitions."""

from grow_light_recipe.models import (
    LightConfig,
    LightRecipe,
    Phase,
    ScheduleEntry,
    TimeRange,
)
from grow_light_recipe.transition import TransitionPlan
from grow_light_recipe.recipe import ChannelRule, DimmingConfig, Recipe
from grow_light_recipe.day_plan import ChannelSchedule, DayPlan, DimmingPoint, compute_day_plan
from grow_light_recipe.interpolate import interpolate_recipes
from grow_light_recipe.queue import RecipeEntry, RecipeQueue, TransitionEntry

__all__ = [
    # Original
    "LightConfig",
    "LightRecipe",
    "Phase",
    "ScheduleEntry",
    "TimeRange",
    "TransitionPlan",
    # Composer
    "ChannelRule",
    "ChannelSchedule",
    "DayPlan",
    "DimmingConfig",
    "DimmingPoint",
    "Recipe",
    "RecipeEntry",
    "RecipeQueue",
    "TransitionEntry",
    "compute_day_plan",
    "interpolate_recipes",
]
