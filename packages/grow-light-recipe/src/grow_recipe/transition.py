from __future__ import annotations

from dataclasses import dataclass

from grow_recipe.models import LightRecipe, ScheduleEntry, TimeRange
from grow_recipe.time_utils import lerp_time


@dataclass(frozen=True, slots=True)
class TransitionPlan:
    from_recipe: LightRecipe
    to_recipe: LightRecipe
    days: int

    def schedule_for_day(self, day: int) -> list[ScheduleEntry]:
        if day <= 0:
            return self.from_recipe.schedule()
        if day >= self.days:
            return self.to_recipe.schedule()

        t = day / self.days
        on = lerp_time(
            self.from_recipe.photoperiod.on,
            self.to_recipe.photoperiod.on,
            t,
        )
        off = lerp_time(
            self.from_recipe.photoperiod.off,
            self.to_recipe.photoperiod.off,
            t,
        )
        interim = LightRecipe(
            photoperiod=TimeRange(on=on, off=off),
            phase=self.to_recipe.phase,
            light_types=self.to_recipe.light_types,
        )
        return interim.schedule()
