"""三个独立口径均需显式给出。"""

import json
from dataclasses import FrozenInstanceError, asdict
from itertools import product
from typing import Any

import pytest

from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, YearBoundary


def test_all_independent_combinations() -> None:
  configurations = tuple(
    ChartConfig(leap_month_policy=leap_month, day_rollover=day, year_boundary=year)
    for leap_month, day, year in product(LeapMonthPolicy, DayRollover, YearBoundary)
  )
  assert len(set(configurations)) == 12
  for config in configurations:
    assert asdict(config) == {
      "leap_month_policy": config.leap_month_policy,
      "day_rollover": config.day_rollover,
      "year_boundary": config.year_boundary,
    }
    assert json.loads(json.dumps(asdict(config), ensure_ascii=False)) == {
      "leap_month_policy": config.leap_month_policy.value,
      "day_rollover": config.day_rollover.value,
      "year_boundary": config.year_boundary.value,
    }
    field = "year_boundary"
    with pytest.raises(FrozenInstanceError):
      setattr(config, field, YearBoundary.立春)


@pytest.mark.parametrize("missing", ["leap_month_policy", "day_rollover", "year_boundary"])
def test_no_policy_defaults(missing: str) -> None:
  values: dict[str, Any] = {
    "leap_month_policy": LeapMonthPolicy.全月归本月,
    "day_rollover": DayRollover.晚子时归次日,
    "year_boundary": YearBoundary.农历正月初一,
  }
  del values[missing]
  with pytest.raises(TypeError):
    ChartConfig(**values)


@pytest.mark.parametrize("field", ["leap_month_policy", "day_rollover", "year_boundary"])
@pytest.mark.parametrize("invalid", [None, "立春", 0, [], YearBoundary.立春])
def test_policies_are_not_coerced(field: str, invalid: Any) -> None:
  values: dict[str, Any] = {
    "leap_month_policy": LeapMonthPolicy.全月归本月,
    "day_rollover": DayRollover.晚子时归次日,
    "year_boundary": YearBoundary.农历正月初一,
    field: invalid,
  }
  if field == "year_boundary" and invalid is YearBoundary.立春:
    assert ChartConfig(**values).year_boundary is YearBoundary.立春
  else:
    with pytest.raises(TypeError):
      ChartConfig(**values)


def test_policy_aliases() -> None:
  for chinese, english in (
    ("全月归下月", "NEXT_MONTH"),
    ("全月归本月", "CURRENT_MONTH"),
    ("上半月归本月下半月归下月", "SPLIT_MONTH"),
  ):
    assert LeapMonthPolicy.__members__[chinese] is LeapMonthPolicy.__members__[english]
  for chinese, english in (
    ("晚子时归次日", "LATE_ZI_NEXT_DAY"),
    ("早晚子时同日", "SAME_CIVIL_DAY"),
  ):
    assert DayRollover.__members__[chinese] is DayRollover.__members__[english]
  for chinese, name in (("农历正月初一", "LUNAR_NEW_YEAR"), ("立春", "LICHUN")):
    assert YearBoundary.__members__[chinese] is YearBoundary.__members__[name]
