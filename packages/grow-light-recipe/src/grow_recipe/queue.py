from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_type

from grow_recipe.day_plan import compute_day_plan, DayPlan
from grow_recipe.interpolate import interpolate_recipes
from grow_recipe.recipe import Recipe


def _parse_date(s: str) -> date_type:
    return date_type.fromisoformat(s)


@dataclass(frozen=True, slots=True)
class RecipeEntry:
    recipe_name: str
    until: str | None = None  # ISO date or None (run forever)


@dataclass(frozen=True, slots=True)
class TransitionEntry:
    to_recipe: str
    days: int


@dataclass(frozen=True, slots=True)
class RecipeQueue:
    entries: list[RecipeEntry | TransitionEntry]
    recipes: dict[str, Recipe]

    def plan_for_date(self, date_str: str) -> DayPlan:
        target = _parse_date(date_str)
        cursor = None  # tracks where in the timeline we are
        prev_recipe_name: str | None = None

        for i, entry in enumerate(self.entries):
            if isinstance(entry, RecipeEntry):
                if entry.until is None:
                    # Last entry — use this recipe
                    return compute_day_plan(self.recipes[entry.recipe_name], date_str)
                until_date = _parse_date(entry.until)
                if target < until_date:
                    return compute_day_plan(self.recipes[entry.recipe_name], date_str)
                cursor = until_date
                prev_recipe_name = entry.recipe_name

            elif isinstance(entry, TransitionEntry):
                if cursor is None:
                    raise ValueError("TransitionEntry cannot be first in queue")
                end_date = date_type.fromordinal(cursor.toordinal() + entry.days)
                if target < end_date:
                    day_in_transition = (target - cursor).days
                    progress = day_in_transition / entry.days
                    from_recipe = self.recipes[prev_recipe_name]
                    to_recipe = self.recipes[entry.to_recipe]
                    interpolated = interpolate_recipes(from_recipe, to_recipe, progress)
                    return compute_day_plan(
                        interpolated, date_str, transition_progress=progress
                    )
                cursor = end_date
                prev_recipe_name = entry.to_recipe

        # Past all entries — use last known recipe
        if prev_recipe_name and prev_recipe_name in self.recipes:
            return compute_day_plan(self.recipes[prev_recipe_name], date_str)
        # Fallback: first recipe
        first = self.entries[0]
        if isinstance(first, RecipeEntry):
            return compute_day_plan(self.recipes[first.recipe_name], date_str)
        raise ValueError("Cannot determine recipe for date")

    def to_dict(self) -> dict:
        entries_list = []
        for entry in self.entries:
            if isinstance(entry, RecipeEntry):
                d: dict = {"recipe": entry.recipe_name}
                if entry.until is not None:
                    d["until"] = entry.until
                entries_list.append(d)
            elif isinstance(entry, TransitionEntry):
                entries_list.append({
                    "transition_to": entry.to_recipe,
                    "days": entry.days,
                })
        return {"entries": entries_list}

    @classmethod
    def from_dict(cls, d: dict, recipes: dict[str, Recipe]) -> RecipeQueue:
        entries: list[RecipeEntry | TransitionEntry] = []
        for raw in d["entries"]:
            if "recipe" in raw:
                entries.append(RecipeEntry(
                    recipe_name=raw["recipe"],
                    until=raw.get("until"),
                ))
            elif "transition_to" in raw:
                entries.append(TransitionEntry(
                    to_recipe=raw["transition_to"],
                    days=raw["days"],
                ))
        return cls(entries=entries, recipes=recipes)
