from datetime import time, timedelta

from grow_recipe.time_utils import (
    lerp_time,
    minutes_to_time,
    shift_time,
    time_to_minutes,
)


class TestTimeToMinutes:
    def test_midnight(self):
        assert time_to_minutes(time(0, 0)) == 0

    def test_noon(self):
        assert time_to_minutes(time(12, 0)) == 720

    def test_with_minutes(self):
        assert time_to_minutes(time(6, 30)) == 390

    def test_end_of_day(self):
        assert time_to_minutes(time(23, 59)) == 1439


class TestMinutesToTime:
    def test_midnight(self):
        assert minutes_to_time(0) == time(0, 0)

    def test_noon(self):
        assert minutes_to_time(720) == time(12, 0)

    def test_wraps_over_24h(self):
        assert minutes_to_time(1440) == time(0, 0)

    def test_wraps_negative(self):
        assert minutes_to_time(-60) == time(23, 0)

    def test_wraps_large_positive(self):
        assert minutes_to_time(1500) == time(1, 0)



class TestShiftTime:
    def test_shift_forward(self):
        assert shift_time(time(6, 0), timedelta(minutes=30)) == time(6, 30)

    def test_shift_backward(self):
        assert shift_time(time(6, 0), timedelta(minutes=-30)) == time(5, 30)

    def test_shift_wraps_past_midnight(self):
        assert shift_time(time(23, 30), timedelta(minutes=60)) == time(0, 30)

    def test_shift_wraps_before_midnight(self):
        assert shift_time(time(0, 15), timedelta(minutes=-30)) == time(23, 45)

    def test_shift_zero(self):
        assert shift_time(time(12, 0), timedelta()) == time(12, 0)



class TestLerpTime:
    def test_t_zero_returns_start(self):
        assert lerp_time(time(6, 0), time(8, 0), 0.0) == time(6, 0)

    def test_t_one_returns_end(self):
        assert lerp_time(time(6, 0), time(8, 0), 1.0) == time(8, 0)

    def test_midpoint(self):
        assert lerp_time(time(6, 0), time(8, 0), 0.5) == time(7, 0)

    def test_quarter(self):
        assert lerp_time(time(6, 0), time(10, 0), 0.25) == time(7, 0)

    def test_wrapping_forward(self):
        # 22:00 -> 02:00 (4h span crossing midnight), t=0.5 -> 00:00
        assert lerp_time(time(22, 0), time(2, 0), 0.5) == time(0, 0)

    def test_no_movement(self):
        assert lerp_time(time(12, 0), time(12, 0), 0.5) == time(12, 0)
