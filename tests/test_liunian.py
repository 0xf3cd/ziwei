"""直接年支例、独立历书日期和本命组合分别检验流年。"""

import json
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

import pytest

from ziwei import calendar, liunian
from ziwei.birth import Gender, GregorianBirthRecord, LunarBirthRecord, TimePrecision
from ziwei.calendar import LunarAlgorithm
from ziwei.chart import create_chart, palace_view
from ziwei.config import ChartConfig, YearBoundary
from ziwei.ganzhi import Dizhi
from ziwei.liunian import (
  LIUNIAN_MINGGONG_RULE_ID,
  LiunianBoundary,
  LiunianYear,
  liunian_minggong,
  liunian_on_date,
)
from ziwei.palaces import PalaceName
from ziwei.sihua import SihuaVariant
from ziwei.timezone import FixedOffset

REFERENCE = json.loads(
  Path(__file__)
  .with_name("fixtures")
  .joinpath("liunian-reference.json")
  .read_text(encoding="utf-8")
)


@pytest.mark.parametrize(
  "year,expected", list(zip(range(2020, 2032), "子丑寅卯辰巳午未申酉戌亥", strict=True))
)
def test_year_branch_is_the_minggong(year: int, expected: str) -> None:
  assert liunian_minggong(year) is Dizhi(expected)


def test_direct_2025_observation_and_original_position_witnesses() -> None:
  modern = REFERENCE["position_sources"][1]
  assert modern["observed"] == modern["adopted"]
  assert liunian_minggong(modern["adopted"]["ganzhi_year"]) is Dizhi.巳
  for branch, quote in zip(tuple(Dizhi), REFERENCE["position_sources"][0]["quotes"], strict=True):
    assert quote == f"{branch.value}年太岁并小限到{branch.value}宫入庙化吉"
  assert liunian_minggong(1) is Dizhi.酉
  assert liunian_minggong(9999) is Dizhi.亥


@pytest.mark.parametrize("invalid", [True, False, 2024.0, "2024", None])
def test_pure_year_rejects_coercion(invalid: Any) -> None:
  with pytest.raises(TypeError):
    liunian_minggong(invalid)


@pytest.mark.parametrize("invalid", [0, -1, 10000])
def test_pure_year_rejects_out_of_range(invalid: int) -> None:
  with pytest.raises(ValueError):
    liunian_minggong(invalid)


@pytest.mark.parametrize("row", REFERENCE["project_expectations"])
@pytest.mark.parametrize(
  "algorithm", [LunarAlgorithm[name] for name in REFERENCE["project_lunar_algorithms"]]
)
def test_independent_calendar_dates_and_two_policy_orders(
  row: list[Any], algorithm: LunarAlgorithm
) -> None:
  day = date.fromisoformat(row[0])
  for boundary, expected in (
    (LiunianBoundary.正月初一日期, row[1]),
    (LiunianBoundary.立春日期, row[2]),
  ):
    result = liunian_on_date(
      day,
      boundary=boundary,
      lunar_algorithm=algorithm if boundary is LiunianBoundary.正月初一日期 else None,
    )
    assert result.ganzhi_year == expected
    assert result.boundary is boundary and type(result.boundary) is LiunianBoundary
    assert result.start <= day < result.end
    assert result.minggong is liunian_minggong(expected)
    assert result.rule_id == LIUNIAN_MINGGONG_RULE_ID


@pytest.mark.parametrize("source", REFERENCE["calendar_sources"])
def test_pmo_observations_keep_date_and_minute_precision_separate(source: dict[str, Any]) -> None:
  observed, adopted = source["observed"], source["adopted_dates"]
  assert source["page"] == 2 and source["published_precision"] == "minute"
  assert source["date_basis"] == "北京时间UTC+08"
  assert observed["lunar_new_year"] == adopted["lunar_new_year"]
  assert observed["lichun"].split()[0] == adopted["lichun_date"]
  for key, boundary, algorithm in (
    ("lunar_new_year", LiunianBoundary.正月初一日期, LunarAlgorithm.ALGO3),
    ("lichun_date", LiunianBoundary.立春日期, None),
  ):
    day = date.fromisoformat(adopted[key])
    result = liunian_on_date(day, boundary=boundary, lunar_algorithm=algorithm)
    assert result.start == day
    assert result.ganzhi_year == day.year


@pytest.mark.parametrize("boundary", tuple(LiunianBoundary))
def test_interval_end_belongs_to_the_next_year(boundary: LiunianBoundary) -> None:
  algorithm = LunarAlgorithm.ALGO3 if boundary is LiunianBoundary.正月初一日期 else None
  result = liunian_on_date(date(2024, 6, 1), boundary=boundary, lunar_algorithm=algorithm)
  assert (
    liunian_on_date(result.end - timedelta(days=1), boundary=boundary, lunar_algorithm=algorithm)
    == result
  )
  following = liunian_on_date(result.end, boundary=boundary, lunar_algorithm=algorithm)
  assert following.ganzhi_year == 2025 and following.start == result.end


@pytest.mark.parametrize("year", [1992, 2038, 2087])
def test_same_day_boundaries_are_an_equal_control(year: int) -> None:
  day = calendar.lichun_date(year)
  lunar = liunian_on_date(
    day, boundary=LiunianBoundary.正月初一日期, lunar_algorithm=LunarAlgorithm.ALGO3
  )
  solar = liunian_on_date(day, boundary=LiunianBoundary.立春日期)
  assert lunar.start == solar.start == day
  assert lunar.ganzhi_year == solar.ganzhi_year == year


def test_selected_algorithm_changes_dates_and_support() -> None:
  day = date(1916, 2, 3)
  readings = [
    liunian_on_date(day, boundary=LiunianBoundary.正月初一日期, lunar_algorithm=algorithm)
    for algorithm in LunarAlgorithm
  ]
  assert [r.ganzhi_year for r in readings] == [1916, 1915, 1916]
  with pytest.raises(ValueError):
    liunian_on_date(
      date(2150, 1, 1), boundary=LiunianBoundary.正月初一日期, lunar_algorithm=LunarAlgorithm.ALGO1
    )
  assert (
    liunian_on_date(
      date(2150, 1, 1), boundary=LiunianBoundary.正月初一日期, lunar_algorithm=LunarAlgorithm.ALGO3
    ).ganzhi_year
    == 2149
  )


@pytest.mark.parametrize(
  "algorithm,start,end,years",
  [
    (LunarAlgorithm.ALGO1, "1901-02-19", "2100-02-09", (1901, 2099)),
    (LunarAlgorithm.ALGO2, "0410-01-22", "2501-02-19", (410, 2500)),
    (LunarAlgorithm.ALGO3, "1600-02-15", "2200-02-15", (1600, 2199)),
  ],
)
def test_lunar_algorithm_complete_range_endpoints(
  algorithm: LunarAlgorithm, start: str, end: str, years: tuple[int, int]
) -> None:
  first, stop = date.fromisoformat(start), date.fromisoformat(end)
  low = liunian_on_date(first, boundary=LiunianBoundary.正月初一日期, lunar_algorithm=algorithm)
  high = liunian_on_date(
    stop - timedelta(days=1), boundary=LiunianBoundary.正月初一日期, lunar_algorithm=algorithm
  )
  assert (low.ganzhi_year, high.ganzhi_year) == years
  assert low.start == first and high.end == stop
  assert low.supported_year_range == high.supported_year_range == years
  assert low.lunar_algorithm is high.lunar_algorithm is algorithm
  for outside in (first - timedelta(days=1), stop):
    with pytest.raises(ValueError):
      liunian_on_date(outside, boundary=LiunianBoundary.正月初一日期, lunar_algorithm=algorithm)


def test_lichun_complete_range_endpoints() -> None:
  low = liunian_on_date(date(1972, 2, 5), boundary=LiunianBoundary.立春日期)
  high = liunian_on_date(date(2200, 2, 3), boundary=LiunianBoundary.立春日期)
  assert low.ganzhi_year == 1972 and low.start == date(1972, 2, 5)
  assert high.ganzhi_year == 2199 and high.end == date(2200, 2, 4)
  assert low.supported_year_range == high.supported_year_range == (1972, 2199)
  for outside in (
    date(1971, 12, 31),
    date(1972, 1, 1),
    date(1972, 2, 4),
    date(2200, 2, 4),
    date(2200, 12, 31),
    date(2201, 1, 1),
  ):
    with pytest.raises(ValueError, match="立春流年支持范围"):
      liunian_on_date(outside, boundary=LiunianBoundary.立春日期)


@pytest.mark.parametrize("year", range(1972, 2200))
def test_every_complete_lichun_year_keeps_its_interval(year: int) -> None:
  start = calendar.lichun_date(year)
  end = calendar.lichun_date(year + 1)
  reading = liunian_on_date(start, boundary=LiunianBoundary.立春日期)
  assert reading.ganzhi_year == year
  assert (reading.start, reading.end) == (start, end)
  assert liunian_on_date(end - timedelta(days=1), boundary=LiunianBoundary.立春日期) == reading
  if year < 2199:
    following = liunian_on_date(end, boundary=LiunianBoundary.立春日期)
    assert following.ganzhi_year == year + 1 and following.start == end


@pytest.mark.parametrize(
  "invalid", [datetime(2024, 2, 4), datetime(2024, 2, 4, tzinfo=UTC), "2024-02-04", None, True]
)
def test_date_input_does_not_discard_time(invalid: Any) -> None:
  with pytest.raises(TypeError):
    liunian_on_date(invalid, boundary=LiunianBoundary.立春日期)


@pytest.mark.parametrize(
  "invalid", [YearBoundary.农历正月初一, YearBoundary.立春, "正月初一日期", None, True]
)
def test_natal_boundary_or_string_is_not_a_liunian_boundary(invalid: Any) -> None:
  with pytest.raises(TypeError):
    liunian_on_date(date(2024, 2, 4), boundary=invalid)


def test_same_value_from_another_enum_is_rejected() -> None:
  OtherBoundary = StrEnum("OtherBoundary", {"LICHUN_DATE": "立春日期"})
  invalid: Any = OtherBoundary.LICHUN_DATE
  assert invalid == LiunianBoundary.立春日期
  with pytest.raises(TypeError):
    liunian_on_date(date(2024, 2, 4), boundary=invalid)


@pytest.mark.parametrize("day", [date.min, date.max])
@pytest.mark.parametrize("boundary", tuple(LiunianBoundary))
def test_python_date_extremes_fail_explicitly(day: date, boundary: LiunianBoundary) -> None:
  with pytest.raises(ValueError):
    liunian_on_date(
      day,
      boundary=boundary,
      lunar_algorithm=LunarAlgorithm.ALGO3 if boundary is LiunianBoundary.正月初一日期 else None,
    )


@pytest.mark.parametrize("invalid", [None, True, "混合", 0, LiunianBoundary.立春日期])
def test_lunar_algorithm_is_explicit_and_typed(invalid: Any) -> None:
  with pytest.raises(TypeError):
    liunian_on_date(
      date(2024, 2, 4), boundary=LiunianBoundary.正月初一日期, lunar_algorithm=invalid
    )


@pytest.mark.parametrize("algorithm", tuple(LunarAlgorithm))
def test_lichun_rejects_an_unused_algorithm(algorithm: LunarAlgorithm) -> None:
  with pytest.raises(TypeError, match="不使用农历算法"):
    liunian_on_date(date(2024, 2, 4), boundary=LiunianBoundary.立春日期, lunar_algorithm=algorithm)


def test_boundary_has_no_default_and_aliases_preserve_identity() -> None:
  with pytest.raises(TypeError):
    liunian_on_date(date(2024, 2, 4))  # type: ignore[call-arg]
  assert LiunianBoundary["正月初一日期"] is LiunianBoundary.LUNAR_NEW_YEAR
  assert LiunianBoundary["立春日期"] is LiunianBoundary.LICHUN_DATE
  assert len({boundary.rule_id for boundary in LiunianBoundary}) == 2


def test_new_unimplemented_boundary_is_not_substituted(monkeypatch: pytest.MonkeyPatch) -> None:
  FutureBoundary = StrEnum(
    "FutureBoundary", {"LUNAR_NEW_YEAR": "a", "LICHUN_DATE": "b", "OTHER": "c"}
  )
  monkeypatch.setattr(liunian, "LiunianBoundary", FutureBoundary)
  unsupported: Any = FutureBoundary["OTHER"]
  with pytest.raises(ValueError, match="尚未实现流年年界"):
    liunian_on_date(date(2024, 2, 4), boundary=unsupported)


def test_reading_is_frozen_and_metadata_is_derived(monkeypatch: pytest.MonkeyPatch) -> None:
  reading = liunian_on_date(date(2024, 2, 4), boundary=LiunianBoundary.立春日期)
  assert str(reading.year_ganzhi) == "甲辰" and reading.minggong is Dizhi.辰
  assert reading.date_basis == "UTC+08" and reading.precision == "date"
  assert (
    reading.lunar_algorithm is None and reading.celestial_version == calendar.celestial_version()
  )
  with pytest.raises(FrozenInstanceError):
    reading.ganzhi_year = 2023  # type: ignore[misc]
  with pytest.raises(TypeError):
    LiunianYear(
      ganzhi_year=2024,
      boundary=reading.boundary,
      start=reading.start,
      end=reading.end,
      lunar_algorithm=None,
      celestial_version="0.8.0",
      supported_year_range=(1, 9999),
    )  # type: ignore[call-arg]
  monkeypatch.setattr(calendar, "LICHUN_DATE_YEAR_RANGE", (1972, 2100))
  assert replace(reading).supported_year_range == (1972, 2099)
  assert reading.supported_year_range == (1972, 2199)
  with pytest.raises(ValueError):
    liunian_on_date(date(2100, 2, 4), boundary=LiunianBoundary.立春日期)


@pytest.mark.parametrize("algorithm", tuple(LunarAlgorithm))
def test_lunar_reading_keeps_date_basis_and_requires_algorithm(algorithm: LunarAlgorithm) -> None:
  reading = liunian_on_date(
    date(2024, 2, 10), boundary=LiunianBoundary.正月初一日期, lunar_algorithm=algorithm
  )
  assert reading.date_basis == "所选农历算法日期标签"
  assert reading.lunar_algorithm is algorithm
  with pytest.raises(TypeError, match="须显式指定 LunarAlgorithm"):
    replace(reading, lunar_algorithm=None)


@pytest.mark.parametrize(
  "changes,error",
  [
    ({"ganzhi_year": True}, TypeError),
    ({"ganzhi_year": 1971}, ValueError),
    ({"boundary": YearBoundary.农历正月初一}, TypeError),
    ({"start": datetime(2024, 2, 4)}, TypeError),
    ({"end": "2025-02-03"}, TypeError),
    ({"start": date(2023, 2, 4)}, ValueError),
    ({"end": date(2024, 12, 31)}, ValueError),
    ({"end": date(2024, 1, 1)}, ValueError),
    ({"celestial_version": 8}, TypeError),
    ({"celestial_version": " "}, ValueError),
    ({"lunar_algorithm": LunarAlgorithm.ALGO3}, TypeError),
  ],
)
def test_direct_reading_validates_structural_relationships(
  changes: dict[str, Any], error: type[Exception]
) -> None:
  reading = liunian_on_date(date(2024, 2, 4), boundary=LiunianBoundary.立春日期)
  with pytest.raises(error):
    replace(reading, **changes)


@pytest.mark.parametrize("natal_boundary", tuple(YearBoundary))
@pytest.mark.parametrize("boundary", tuple(LiunianBoundary))
@pytest.mark.parametrize(
  "day,before,after",
  [
    (date(2022, 2, 4), time(2), time(8)),
    (date(2024, 2, 4), time(10), time(18)),
  ],
)
@pytest.mark.parametrize("after_lichun", [False, True])
def test_natal_instant_and_liunian_date_do_not_share_configuration(
  chart_choices: ChartConfig,
  natal_boundary: YearBoundary,
  boundary: LiunianBoundary,
  day: date,
  before: time,
  after: time,
  after_lichun: bool,
) -> None:
  chart = create_chart(
    GregorianBirthRecord(
      birth_date=day,
      birth_time=after if after_lichun else before,
      time_precision=TimePrecision.分,
      timezone=FixedOffset(timedelta(hours=8)),
      gender=Gender.女,
    ),
    replace(chart_choices, year_boundary=natal_boundary),
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  result = liunian_on_date(
    day,
    boundary=boundary,
    lunar_algorithm=LunarAlgorithm.ALGO3 if boundary is LiunianBoundary.正月初一日期 else None,
  )
  assert result.ganzhi_year == (
    2023 if day.year == 2024 and boundary is LiunianBoundary.正月初一日期 else day.year
  )
  new_natal_year = after_lichun if natal_boundary is YearBoundary.立春 else day.year == 2022
  assert chart.calculation.ganzhi_year == (day.year if new_natal_year else day.year - 1)
  assert palace_view(chart, result.minggong).palace.dizhi is result.minggong


def test_existing_palace_query_overlays_different_natal_charts(chart_choices: ChartConfig) -> None:
  for record, natal_name in (
    (
      LunarBirthRecord(
        year=2024, month=1, day=1, is_leap_month=False, shichen=Dizhi.子, gender=Gender.女
      ),
      PalaceName.田宅,
    ),
    (
      LunarBirthRecord(
        year=1990, month=7, day=15, is_leap_month=False, shichen=Dizhi.未, gender=Gender.男
      ),
      PalaceName.官禄,
    ),
  ):
    chart = create_chart(record, chart_choices, sihua_variant=SihuaVariant.排命盘口诀转录)
    target = liunian_minggong(2025)
    assert target is Dizhi.巳
    view = palace_view(chart, target)
    assert view.palace.dizhi is target and view.palace.name is natal_name


def test_native_failure_is_not_replaced(monkeypatch: pytest.MonkeyPatch) -> None:
  def unavailable(*args: Any) -> Any:
    raise RuntimeError("native calendar unavailable")

  monkeypatch.setattr(calendar, "gregorian_to_lunar", unavailable)
  monkeypatch.setattr(calendar, "lichun_date", unavailable)
  for boundary, algorithm in (
    (LiunianBoundary.正月初一日期, LunarAlgorithm.ALGO3),
    (LiunianBoundary.立春日期, None),
  ):
    with pytest.raises(RuntimeError, match="native calendar unavailable"):
      liunian_on_date(date(2024, 2, 4), boundary=boundary, lunar_algorithm=algorithm)


def test_pure_year_and_knowledge_stay_independent_of_calendar() -> None:
  script = """
import sys
from ziwei.liunian import liunian_minggong
from ziwei.knowledge import load_catalog
if liunian_minggong(2025).value != '巳':
  raise ValueError('wrong position')
load_catalog()
for prefix in ('ziwei.calendar', 'ziwei.birth', 'ziwei.timezone', 'celestial_calendar', 'tzdata'):
  if any(n == prefix or n.startswith(prefix + '.') for n in sys.modules):
    raise ValueError('unexpected dependency: ' + prefix)
"""
  result = subprocess.run((sys.executable, "-I", "-c", script), capture_output=True, text=True)
  assert result.returncode == 0, result.stdout + result.stderr
