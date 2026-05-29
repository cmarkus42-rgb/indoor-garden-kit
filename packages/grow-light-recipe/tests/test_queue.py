from grow_recipe.queue import RecipeQueue, RecipeEntry, TransitionEntry
from grow_recipe.recipe import ChannelRule, DimmingConfig, Recipe


def _veg() -> Recipe:
    return Recipe(
        name="Veg",
        photoperiod_on="06:00",
        photoperiod_off="00:00",
        dimming=DimmingConfig(sunrise_min=30, sunset_min=30, max_pct=100, min_pct=0),
        channels={"dawn": ChannelRule(rule="before_on", offset_min=30)},
    )


def _flower() -> Recipe:
    return Recipe(
        name="Flower",
        photoperiod_on="08:00",
        photoperiod_off="20:00",
        dimming=DimmingConfig(sunrise_min=60, sunset_min=60, max_pct=80, min_pct=10),
        channels={"far_red": ChannelRule(rule="after_off", offset_min=5, duration_min=30)},
    )


class TestRecipeQueueSingleRecipe:
    def test_single_entry_no_until(self):
        q = RecipeQueue(
            entries=[RecipeEntry(recipe_name="Veg")],
            recipes={"Veg": _veg()},
        )
        plan = q.plan_for_date("2026-06-15")
        assert plan.recipe_name == "Veg"
        assert plan.main_on == 360
        assert plan.transition_progress is None

    def test_single_entry_with_until_before_date(self):
        """If date is past `until` and no next entry, still use last recipe."""
        q = RecipeQueue(
            entries=[RecipeEntry(recipe_name="Veg", until="2026-06-01")],
            recipes={"Veg": _veg()},
        )
        plan = q.plan_for_date("2026-06-15")
        assert plan.recipe_name == "Veg"


class TestRecipeQueueTransition:
    def test_transition_midpoint(self):
        q = RecipeQueue(
            entries=[
                RecipeEntry(recipe_name="Veg", until="2026-06-01"),
                TransitionEntry(to_recipe="Flower", days=10),
                RecipeEntry(recipe_name="Flower"),
            ],
            recipes={"Veg": _veg(), "Flower": _flower()},
        )
        # Day 5 of 10-day transition = progress 0.5
        plan = q.plan_for_date("2026-06-06")
        assert plan.transition_progress == 0.5
        # Photoperiod on: lerp 06:00→08:00 at 0.5 = 07:00 = 420
        assert plan.main_on == 420

    def test_transition_day_zero(self):
        q = RecipeQueue(
            entries=[
                RecipeEntry(recipe_name="Veg", until="2026-06-01"),
                TransitionEntry(to_recipe="Flower", days=10),
                RecipeEntry(recipe_name="Flower"),
            ],
            recipes={"Veg": _veg(), "Flower": _flower()},
        )
        plan = q.plan_for_date("2026-06-01")
        assert plan.transition_progress == 0.0

    def test_transition_last_day(self):
        q = RecipeQueue(
            entries=[
                RecipeEntry(recipe_name="Veg", until="2026-06-01"),
                TransitionEntry(to_recipe="Flower", days=10),
                RecipeEntry(recipe_name="Flower"),
            ],
            recipes={"Veg": _veg(), "Flower": _flower()},
        )
        plan = q.plan_for_date("2026-06-11")
        # Day 10 of 10 = progress 1.0 → should be Flower
        assert plan.recipe_name == "Flower"
        assert plan.transition_progress is None


class TestRecipeQueueProgression:
    def test_after_transition_uses_target(self):
        q = RecipeQueue(
            entries=[
                RecipeEntry(recipe_name="Veg", until="2026-06-01"),
                TransitionEntry(to_recipe="Flower", days=7),
                RecipeEntry(recipe_name="Flower"),
            ],
            recipes={"Veg": _veg(), "Flower": _flower()},
        )
        plan = q.plan_for_date("2026-06-20")
        assert plan.recipe_name == "Flower"
        assert plan.main_on == 480  # 08:00


class TestRecipeQueueSerialization:
    def test_to_dict(self):
        q = RecipeQueue(
            entries=[
                RecipeEntry(recipe_name="Veg", until="2026-06-01"),
                TransitionEntry(to_recipe="Flower", days=7),
                RecipeEntry(recipe_name="Flower"),
            ],
            recipes={"Veg": _veg(), "Flower": _flower()},
        )
        d = q.to_dict()
        assert len(d["entries"]) == 3
        assert d["entries"][0]["recipe"] == "Veg"
        assert d["entries"][0]["until"] == "2026-06-01"
        assert d["entries"][1]["transition_to"] == "Flower"
        assert d["entries"][1]["days"] == 7

    def test_from_dict(self):
        d = {
            "entries": [
                {"recipe": "Veg", "until": "2026-06-01"},
                {"transition_to": "Flower", "days": 7},
                {"recipe": "Flower"},
            ],
        }
        recipes = {"Veg": _veg(), "Flower": _flower()}
        q = RecipeQueue.from_dict(d, recipes)
        assert len(q.entries) == 3
        assert isinstance(q.entries[0], RecipeEntry)
        assert isinstance(q.entries[1], TransitionEntry)

    def test_roundtrip(self):
        q1 = RecipeQueue(
            entries=[
                RecipeEntry(recipe_name="Veg", until="2026-06-01"),
                TransitionEntry(to_recipe="Flower", days=7),
                RecipeEntry(recipe_name="Flower"),
            ],
            recipes={"Veg": _veg(), "Flower": _flower()},
        )
        d = q1.to_dict()
        q2 = RecipeQueue.from_dict(d, {"Veg": _veg(), "Flower": _flower()})
        plan1 = q1.plan_for_date("2026-06-04")
        plan2 = q2.plan_for_date("2026-06-04")
        assert plan1.main_on == plan2.main_on
