"""出生记录保真、形状校验与完整性边界。"""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, time, timedelta
from itertools import product
from typing import Any

import pytest

from ziwei.birth import (
  BirthRecord,
  CalculationInput,
  Gender,
  GregorianBirthRecord,
  LunarBirthRecord,
  TimePrecision,
  shichen_from_time,
)
from ziwei.calendar import LunarAlgorithm
from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, YearBoundary
from ziwei.ganzhi import Dizhi, Yinyang
from ziwei.timezone import FixedOffset, IanaTimezone


def gregorian_record(**changes: Any) -> GregorianBirthRecord:
  values: dict[str, Any] = {
    "birth_date": date(1988, 7, 1),
    "birth_time": time(12),
    "time_precision": TimePrecision.分,
    "timezone": IanaTimezone("Asia/Shanghai"),
    "gender": Gender.男,
  }
  values.update(changes)
  return GregorianBirthRecord(**values)


def lunar_record(**changes: Any) -> LunarBirthRecord:
  values: dict[str, Any] = {
    "year": 2000,
    "month": 4,
    "day": 15,
    "is_leap_month": True,
    "shichen": Dizhi.子,
    "gender": Gender.女,
  }
  values.update(changes)
  return LunarBirthRecord(**values)


def config() -> ChartConfig:
  return ChartConfig(
    leap_month_policy=LeapMonthPolicy.全月归本月,
    day_rollover=DayRollover.早晚子时同日,
    year_boundary=YearBoundary.立春,
  )


def calculation_input(**changes: Any) -> CalculationInput:
  values: dict[str, Any] = {
    "record": lunar_record(),
    "lunar_year": 2000,
    "month": 4,
    "day": 15,
    "is_leap_month": True,
    "shichen": Dizhi.子,
    "ganzhi_year": 1999,
    "config": config(),
    "lunar_algorithm": LunarAlgorithm.ALGO3,
    "lunar_algorithm_version": "0.8.0",
    "apparent_solar": False,
    "day_rolled": False,
    "ut1_jd": None,
    "lichun_jd": None,
  }
  selected = changes.get("config", values["config"])
  if isinstance(selected, ChartConfig) and selected.year_boundary is YearBoundary.立春:
    if "ut1_jd" not in changes:
      values["ut1_jd"] = 0.0
    if "lichun_jd" not in changes:
      values["lichun_jd"] = 0.0
  elif isinstance(selected, ChartConfig) and selected.year_boundary is YearBoundary.农历正月初一:
    if "ganzhi_year" not in changes:
      values["ganzhi_year"] = values["lunar_year"]
  values.update(changes)
  return CalculationInput(**values)


@pytest.mark.parametrize(
  "clock, expected",
  [
    (time(0), Dizhi.子),
    (time(0, 59, 59, 999999), Dizhi.子),
    (time(1), Dizhi.丑),
    (time(22, 59, 59, 999999), Dizhi.亥),
    (time(23), Dizhi.子),
    (time(23, 59, 59, 999999), Dizhi.子),
  ],
)
def test_both_sides_of_zishi(clock: time, expected: Dizhi) -> None:
  assert shichen_from_time(clock) is expected
  record = gregorian_record(birth_time=clock, time_precision=TimePrecision.微秒)
  assert record.shichen is expected
  assert record.birth_date == date(1988, 7, 1)


def test_every_shichen_boundary() -> None:
  expected = (
    Dizhi.丑,
    Dizhi.寅,
    Dizhi.卯,
    Dizhi.辰,
    Dizhi.巳,
    Dizhi.午,
    Dizhi.未,
    Dizhi.申,
    Dizhi.酉,
    Dizhi.戌,
    Dizhi.亥,
    Dizhi.子,
  )
  previous = (Dizhi.子, *expected[:-1])
  for hour, before, after in zip(range(1, 24, 2), previous, expected, strict=True):
    assert shichen_from_time(time(hour - 1, 59, 59, 999999)) is before
    assert shichen_from_time(time(hour)) is after


@pytest.mark.parametrize("bad", [None, "子", 0, datetime(2000, 1, 1)])
def test_clock_type(bad: Any) -> None:
  with pytest.raises(TypeError):
    shichen_from_time(bad)


@pytest.mark.parametrize("bad", [time(0, tzinfo=UTC), time(0, fold=1)])
def test_clock_does_not_hide_timezone_choice(bad: time) -> None:
  with pytest.raises(ValueError):
    shichen_from_time(bad)


def test_gregorian_original_and_explicit_offset() -> None:
  record = gregorian_record(longitude_deg=121.5, place="合成省", source="合成记录")
  resolved = record.resolve_time()
  assert resolved.offset == timedelta(hours=9)
  assert resolved.utc == datetime(1988, 7, 1, 3, tzinfo=UTC)
  assert record.birth_time == time(12)
  assert record.longitude_deg == 121.5
  assert record.place == "合成省"
  assert record.source == "合成记录"
  fixed = replace(record, timezone=FixedOffset(timedelta(hours=8))).resolve_time()
  assert fixed.utc == datetime(1988, 7, 1, 4, tzinfo=UTC)
  assert fixed.data is None


def test_unknown_and_historical_originals_are_preserved() -> None:
  record = gregorian_record(birth_time=None, time_precision=TimePrecision.日, gender=Gender.未知)
  assert record.shichen is None
  assert record.gender is Gender.未知
  with pytest.raises(ValueError, match="未知"):
    record.resolve_time()
  old = gregorian_record(birth_date=date(1900, 1, 1))
  assert old.birth_date.year == 1900
  with pytest.raises(ValueError, match="1972"):
    old.resolve_time()


@pytest.mark.parametrize(
  "changes, error",
  [
    ({"birth_date": datetime(2000, 1, 1)}, TypeError),
    ({"birth_date": "2000-01-01"}, TypeError),
    ({"timezone": "Asia/Shanghai"}, TypeError),
    ({"gender": "男"}, TypeError),
    ({"time_precision": "分"}, TypeError),
    ({"birth_time": None}, ValueError),
    ({"time_precision": TimePrecision.日}, ValueError),
    ({"birth_time": time(12, 1), "time_precision": TimePrecision.时}, ValueError),
    ({"birth_time": time(12, 0, 1)}, ValueError),
    ({"birth_time": time(12, 0, 0, 1), "time_precision": TimePrecision.秒}, ValueError),
    ({"longitude_deg": float("nan")}, ValueError),
    ({"longitude_deg": float("inf")}, ValueError),
    ({"longitude_deg": 180.1}, ValueError),
    ({"longitude_deg": -180.1}, ValueError),
    ({"longitude_deg": 10**400}, ValueError),
    ({"longitude_deg": -(10**400)}, ValueError),
    ({"longitude_deg": True}, TypeError),
    ({"longitude_deg": "120"}, TypeError),
    ({"place": ["合成省"]}, TypeError),
    ({"source": {}}, TypeError),
  ],
)
def test_gregorian_rejects_invalid_inputs(changes: dict[str, Any], error: type[Exception]) -> None:
  with pytest.raises(error):
    gregorian_record(**changes)


@pytest.mark.parametrize("precision", list(TimePrecision)[1:])
def test_known_time_precision(precision: TimePrecision) -> None:
  assert gregorian_record(time_precision=precision).time_precision is precision


def test_lunar_is_structural_not_a_calendar_converter() -> None:
  record = lunar_record(
    year=2000, month=12, day=30, is_leap_month=True, shichen=None, gender=Gender.未知
  )
  assert (record.year, record.month, record.day, record.is_leap_month) == (2000, 12, 30, True)
  assert record.shichen is None
  assert not hasattr(record, "resolve_time")
  for longitude in (-180, 180):
    assert lunar_record(longitude_deg=longitude).longitude_deg == longitude


@pytest.mark.parametrize("field, maximum", [("year", 9999), ("month", 12), ("day", 30)])
def test_lunar_ranges_and_types(field: str, maximum: int) -> None:
  for value in (0, maximum + 1):
    with pytest.raises(ValueError):
      lunar_record(**{field: value})
  for invalid in (True, 1.0, "1", None):
    with pytest.raises(TypeError):
      lunar_record(**{field: invalid})


@pytest.mark.parametrize("changes", [{"is_leap_month": 1}, {"shichen": "子"}, {"gender": "女"}])
def test_lunar_nominal_types(changes: dict[str, Any]) -> None:
  with pytest.raises(TypeError):
    lunar_record(**changes)


@pytest.mark.parametrize("longitude", [10**400, -(10**400)], ids=["positive", "negative"])
def test_lunar_rejects_unbounded_longitude(longitude: int) -> None:
  with pytest.raises(ValueError, match="经度"):
    lunar_record(longitude_deg=longitude)


def test_parsed_contract_and_independent_year_choice() -> None:
  value = calculation_input()
  assert value.lunar_year == 2000
  assert str(value.year_ganzhi) == "己卯"
  assert value.ganzhi_year == 1999
  assert value.gender is Gender.女
  assert value.yinyang is Yinyang.阴
  value.require_complete()
  assert calculation_input(ganzhi_year=2000).yinyang is Yinyang.阳
  for leap_month, day, year in product(LeapMonthPolicy, DayRollover, YearBoundary):
    choices = ChartConfig(leap_month_policy=leap_month, day_rollover=day, year_boundary=year)
    assert calculation_input(config=choices).config is choices


def test_partial_parsed_inputs_do_not_gain_defaults() -> None:
  for unknown_time, unknown_gender in ((True, False), (False, True), (True, True)):
    value = calculation_input(
      shichen=None if unknown_time else Dizhi.子,
      record=lunar_record(gender=Gender.未知 if unknown_gender else Gender.女),
    )
    with pytest.raises(ValueError, match="完整命盘"):
      value.require_complete()


@pytest.mark.parametrize("shichen", [Dizhi.子, Dizhi.午])
def test_unknown_original_time_cannot_become_known(shichen: Dizhi) -> None:
  originals = (
    gregorian_record(birth_time=None, time_precision=TimePrecision.日),
    lunar_record(shichen=None),
  )
  for leap_month, day, year in product(LeapMonthPolicy, DayRollover, YearBoundary):
    choices = ChartConfig(leap_month_policy=leap_month, day_rollover=day, year_boundary=year)
    for record in originals:
      with pytest.raises(ValueError, match="未知时辰"):
        calculation_input(record=record, shichen=shichen, config=choices)
      partial = calculation_input(record=record, shichen=None, config=choices)
      assert partial.record is record
      assert partial.shichen is None
      with pytest.raises(ValueError, match="完整命盘"):
        partial.require_complete()


@pytest.mark.parametrize(
  "record",
  [
    lunar_record(year=2000, month=12, day=30, shichen=Dizhi.子),
    gregorian_record(birth_time=time(23, 30)),
  ],
  ids=["lunar", "gregorian"],
)
@pytest.mark.parametrize("shichen", [None, Dizhi.丑])
def test_parsed_values_do_not_require_raw_calendar_equality(
  record: BirthRecord, shichen: Dizhi | None
) -> None:
  value = calculation_input(
    record=record, lunar_year=2001, month=1, day=1, is_leap_month=False, shichen=shichen
  )
  assert value.record is record
  assert (value.lunar_year, value.month, value.day) == (2001, 1, 1)
  assert value.shichen is shichen
  if shichen is None:
    with pytest.raises(ValueError, match="完整命盘"):
      value.require_complete()
  else:
    value.require_complete()


@pytest.mark.parametrize(
  "changes, error",
  [
    ({"record": {}}, TypeError),
    ({"config": None}, TypeError),
    ({"ganzhi_year": None}, TypeError),
    ({"ganzhi_year": 0}, ValueError),
    ({"lunar_year": True}, TypeError),
    ({"month": 13}, ValueError),
    ({"is_leap_month": 0}, TypeError),
    ({"shichen": "子"}, TypeError),
  ],
)
def test_parsed_input_validation(changes: dict[str, Any], error: type[Exception]) -> None:
  with pytest.raises(error):
    calculation_input(**changes)


def test_parsed_input_rejects_contradictory_states() -> None:
  """CalculationInput 拒绝互相矛盾的状态：口径与标志不一致不产生可算输入。"""
  with pytest.raises(ValueError, match="矛盾"):
    calculation_input(
      day_rolled=True,
      config=ChartConfig(
        leap_month_policy=LeapMonthPolicy.全月归本月,
        day_rollover=DayRollover.早晚子时同日,
        year_boundary=YearBoundary.立春,
      ),
    )
  with pytest.raises(ValueError, match="公历记录与经度"):
    calculation_input(apparent_solar=True)
  with pytest.raises(ValueError, match="干支纪年须等于农历年"):
    calculation_input(
      ganzhi_year=1999,
      config=ChartConfig(
        leap_month_policy=LeapMonthPolicy.全月归本月,
        day_rollover=DayRollover.晚子时归次日,
        year_boundary=YearBoundary.农历正月初一,
      ),
    )
  # 合法的真太阳时组合仍可构造：公历记录带经度
  gregorian_input = calculation_input(
    record=gregorian_record(longitude_deg=121.47),
    apparent_solar=True,
    config=ChartConfig(
      leap_month_policy=LeapMonthPolicy.全月归本月,
      day_rollover=DayRollover.晚子时归次日,
      year_boundary=YearBoundary.立春,
    ),
  )
  assert gregorian_input.apparent_solar is True


def test_parsed_input_day_rolled_needs_provable_late_zi() -> None:
  """day_rolled=True 需要原始记录能证明晚子时（公历 23 时），否则结果不可复现。"""
  with pytest.raises(ValueError, match="23 时的公历钟点"):
    calculation_input(
      day_rolled=True,  # 农历记录只有子时粒度
      config=ChartConfig(
        leap_month_policy=LeapMonthPolicy.全月归本月,
        day_rollover=DayRollover.晚子时归次日,
        year_boundary=YearBoundary.立春,
      ),
    )
  with pytest.raises(ValueError, match="23 时的公历钟点"):
    calculation_input(
      record=gregorian_record(birth_time=time(0, 30)),
      day_rolled=True,
      config=ChartConfig(
        leap_month_policy=LeapMonthPolicy.全月归本月,
        day_rollover=DayRollover.晚子时归次日,
        year_boundary=YearBoundary.立春,
      ),
    )
  value = calculation_input(
    record=gregorian_record(birth_time=time(23, 30)),
    day_rolled=True,
    config=ChartConfig(
      leap_month_policy=LeapMonthPolicy.全月归本月,
      day_rollover=DayRollover.晚子时归次日,
      year_boundary=YearBoundary.立春,
    ),
  )
  assert value.day_rolled is True


def test_frozen_inputs_and_nested_values() -> None:
  value = calculation_input()
  for instance, field, replacement in (
    (gregorian_record(), "source", "更改"),
    (lunar_record(), "is_leap_month", False),
    (value, "ganzhi_year", 2001),
    (value.record, "gender", Gender.男),
    (value.config, "year_boundary", YearBoundary.农历正月初一),
  ):
    with pytest.raises(FrozenInstanceError):
      setattr(instance, field, replacement)
  for chinese, english in (("男", "MALE"), ("女", "FEMALE"), ("未知", "UNKNOWN")):
    assert Gender.__members__[chinese] is Gender.__members__[english]
  for precision in TimePrecision:
    assert TimePrecision.__members__[precision.value] is precision
