# indoor-garden-kit Test Case Documentation

Stand: 2026-05-26 | 85 Tests total

---

## ecowitt-collector (19 Tests)

### Models (6)
| Test | Verifies |
|------|----------|
| test_soil_channel_creation | SoilChannel with moisture + battery |
| test_soil_channel_no_battery | SoilChannel without battery (optional) |
| test_indoor_climate_creation | IndoorClimate with temp/humidity/pressure |
| test_indoor_climate_partial | IndoorClimate with only temperature_c |
| test_ecowitt_reading_creation | EcowittReading with soil_channels + indoor |
| test_ecowitt_reading_no_indoor | EcowittReading without indoor (optional) |

### Parser (8)
| Test | Verifies |
|------|----------|
| test_parse_minimal | Minimal payload with 1 soil channel |
| test_parse_full | Full payload with multiple channels + indoor |
| test_parse_indoor_only | Indoor data only, no soil |
| test_parse_empty | Empty payload produces empty reading |
| test_parse_timestamp | dateutc field parsed correctly |
| test_parse_fahrenheit_to_celsius | tempinf (Fahrenheit) converted to Celsius |
| test_parse_pressure_inhg_to_hpa | baromrelin (inHg) converted to hPa |
| test_parse_all_8_soil_channels | All 8 Ecowitt channels recognized |

### Receiver (5)
| Test | Verifies |
|------|----------|
| test_push_endpoint_returns_200 | POST to push endpoint returns 200 |
| test_push_invokes_callback | Callback invoked with EcowittReading |
| test_push_custom_path | Custom mount path works |
| test_push_empty_body | Empty body handled without crash |
| test_push_response_body | Response contains {"status": "ok"} |

---

## grow-light-recipe (45 Tests)

### Time Utils (20)
| Test | Verifies |
|------|----------|
| TestTimeToMinutes::test_midnight | time(0,0) to 0 |
| TestTimeToMinutes::test_noon | time(12,0) to 720 |
| TestTimeToMinutes::test_with_minutes | time(6,30) to 390 |
| TestTimeToMinutes::test_end_of_day | time(23,59) to 1439 |
| TestMinutesToTime::test_midnight | 0 to time(0,0) |
| TestMinutesToTime::test_noon | 720 to time(12,0) |
| TestMinutesToTime::test_wraps_over_24h | 1440 wraps to time(0,0) |
| TestMinutesToTime::test_wraps_negative | -60 wraps to time(23,0) |
| TestMinutesToTime::test_wraps_large_positive | 1500 to time(1,0) |
| TestShiftTime::test_shift_forward | +30min forward |
| TestShiftTime::test_shift_backward | -30min backward |
| TestShiftTime::test_shift_wraps_past_midnight | 23:30 + 60min wraps to 00:30 |
| TestShiftTime::test_shift_wraps_before_midnight | 00:15 - 30min wraps to 23:45 |
| TestShiftTime::test_shift_zero | Zero delta is identity |
| TestLerpTime::test_t_zero_returns_start | t=0.0 returns start time |
| TestLerpTime::test_t_one_returns_end | t=1.0 returns end time |
| TestLerpTime::test_midpoint | Linear midpoint between two times |
| TestLerpTime::test_quarter | 25% interpolation |
| TestLerpTime::test_wrapping_forward | Shortest-path across midnight (22:00 to 02:00) |
| TestLerpTime::test_no_movement | Same start/end time |

### Models (15)
| Test | Verifies |
|------|----------|
| TestPhase::test_veg_value | Phase.veg == "veg" |
| TestPhase::test_flower_value | Phase.flower == "flower" |
| TestPhase::test_is_string | Phase is str subtype |
| TestTimeRange::test_construction | on/off fields |
| TestTimeRange::test_frozen | Frozen dataclass (immutable) |
| TestLightConfig::test_defaults | Default: offset=0, phases=(veg, flower) |
| TestLightConfig::test_custom | Custom offsets and phases |
| TestScheduleEntry::test_construction | light_type, on_time, off_time |
| TestLightRecipe::test_construction | Recipe with photoperiod + light types |
| TestLightRecipe::test_schedule_single_light_no_offset | 1 light, no offset = exact photoperiod |
| TestLightRecipe::test_schedule_with_offsets | Far-red +15min after photoperiod |
| TestLightRecipe::test_schedule_with_before_offset | Dawn -30min before photoperiod |
| TestLightRecipe::test_schedule_filters_by_phase | Only active phase lights emitted |
| TestLightRecipe::test_schedule_empty_when_no_lights_for_phase | No lights for phase = empty list |
| TestLightRecipe::test_schedule_multiple_lights_sorted_by_on_time | Sorted by on_time |

### Transition (9)
| Test | Verifies |
|------|----------|
| TestTransitionPlanBoundaries::test_day_zero_returns_from_recipe | Day 0 = exact source recipe |
| TestTransitionPlanBoundaries::test_day_n_returns_to_recipe | Day N = exact target recipe |
| TestTransitionPlanBoundaries::test_negative_day_clamps_to_from | Day < 0 clamped to source |
| TestTransitionPlanBoundaries::test_beyond_n_clamps_to_target | Day > N clamped to target |
| TestTransitionPlanInterpolation::test_midpoint_interpolates_photoperiod | Midpoint: 06:00-08:00=07:00, 00:00-20:00 shortest-path=22:00 |
| TestTransitionPlanInterpolation::test_far_red_offset_applied_to_interpolated_period | Far-red offset on interpolated photoperiod |
| TestTransitionPlanInterpolation::test_quarter_interpolation | 25% interpolation of on-time |
| TestTransitionPlanInterpolation::test_single_day_transition | 1-day transition: only day 0 and day 1 |
| TestTransitionPlanPhaseHandling::test_uses_to_recipe_light_types_for_intermediate_days | Intermediate days use target recipe light types |

### Package (1)
| Test | Verifies |
|------|----------|
| test_public_api_imports | All 6 public classes importable |

---

## grow-irrigation (21 Tests)

### Models (5)
| Test | Verifies |
|------|----------|
| TestIrrigationZone::test_construction | Zone with sensors, thresholds, timing |
| TestIrrigationZone::test_frozen | Frozen dataclass |
| TestIrrigationAction::test_start_action | Action "start" with reason |
| TestIrrigationAction::test_stop_action | Action "stop" |
| TestIrrigationAction::test_noop_action | Action "noop" |

### Engine (15)
| Test | Verifies |
|------|----------|
| TestEvaluateStartStop::test_dry_triggers_start | Moisture below threshold triggers start |
| TestEvaluateStartStop::test_wet_is_noop | Moisture in OK range is noop |
| TestEvaluateStartStop::test_at_dry_threshold_is_noop | Exactly at threshold = noop (strict <) |
| TestEvaluateStartStop::test_below_dry_threshold_triggers_start | Just below threshold triggers start |
| TestEvaluateStartStop::test_wet_threshold_stops_active_irrigation | Wet threshold reached stops active irrigation |
| TestEvaluateStartStop::test_still_dry_while_active_is_noop | Active + still dry = noop (keep running) |
| TestMultipleSensors::test_average_of_sensors | Average of 2 sensors |
| TestMultipleSensors::test_average_below_threshold_starts | Average below threshold triggers start |
| TestMultipleSensors::test_missing_sensor_uses_available | 1 of 2 sensors missing, uses available |
| TestMultipleSensors::test_all_sensors_missing_is_noop | No sensor data = noop + "no readings" |
| TestMaxDuration::test_stops_after_max_duration | Safety stop after max_duration |
| TestMaxDuration::test_no_stop_before_max_duration | No stop before max_duration elapsed |
| TestMinInterval::test_respects_min_interval_after_stop | Restart blocked within min_interval |
| TestMinInterval::test_allows_start_after_min_interval | Restart allowed after min_interval |
| TestMultipleZones::test_independent_zones | Two zones evaluated independently |

### Package (1)
| Test | Verifies |
|------|----------|
| test_public_api_imports | All 3 public classes importable |
