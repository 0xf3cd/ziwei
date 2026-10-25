"""真实解析到四化、大限的联动，年干与阴阳必须来自同一个年界选择。"""

from dataclasses import replace
from datetime import date, time, timedelta

import pytest

from ziwei.birth import Gender, GregorianBirthRecord, LunarBirthRecord, TimePrecision
from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, YearBoundary
from ziwei.decades import Direction, place_decades
from ziwei.ganzhi import Dizhi, Tiangan
from ziwei.resolver import resolve
from ziwei.sihua import SihuaVariant, shengnian_sihua
from ziwei.stars import Star, place_stars
from ziwei.timezone import FixedOffset

pytestmark = pytest.mark.usefixtures("unload_celestial")


@pytest.fixture
def choices() -> ChartConfig:
  return ChartConfig(
    leap_month_policy=LeapMonthPolicy.全月归本月,
    day_rollover=DayRollover.早晚子时同日,
    year_boundary=YearBoundary.农历正月初一,
  )


def _civil(day: date, clock: time) -> GregorianBirthRecord:
  return GregorianBirthRecord(
    birth_date=day,
    birth_time=clock,
    time_precision=TimePrecision.秒,
    timezone=FixedOffset(timedelta(hours=8)),
    gender=Gender.男,
  )


def test_1954_original_example_through_resolver(choices: ChartConfig) -> None:
  value = resolve(
    LunarBirthRecord(
      year=1954,
      month=9,
      day=7,
      is_leap_month=False,
      shichen=Dizhi.子,
      gender=Gender.男,
      source="匿名盘例：2007论坛转《排命盘口诀》",
    ),
    choices,
  )
  sihua = shengnian_sihua(value, SihuaVariant.排命盘口诀转录)
  assert (sihua.year_tiangan, sihua.lu, sihua.quan, sihua.ke, sihua.ji) == (
    Tiangan.甲,
    Star.廉贞,
    Star.破军,
    Star.武曲,
    Star.太阳,
  )
  periods = place_decades(value)
  assert [(p.dizhi, p.start_age, p.end_age) for p in periods[:2]] == [
    (Dizhi.戌, 6, 15),
    (Dizhi.亥, 16, 25),
  ]
  # 生年四化不替换星位，两个结果可按星曜身份关联，不能用宫位作唯一键。
  positions = {p.star: p.dizhi for p in place_stars(value)}
  assert positions[sihua.lu] is Dizhi.寅 and positions[sihua.ji] is Dizhi.未


def test_unknown_fields_only_block_operations_that_need_them(choices: ChartConfig) -> None:
  record = LunarBirthRecord(
    year=2024,
    month=1,
    day=1,
    is_leap_month=False,
    shichen=None,
    gender=Gender.未知,
  )
  value = resolve(record, choices)
  assert shengnian_sihua(value, SihuaVariant.王亭之讲义转录).year_tiangan is Tiangan.甲
  with pytest.raises(ValueError, match="时辰"):
    place_decades(value)
  known_hour = resolve(replace(record, shichen=Dizhi.子), choices)
  assert len(place_stars(known_hour)) == 28
  with pytest.raises(ValueError, match="性别"):
    place_decades(known_hour)
  with pytest.raises(TypeError):
    shengnian_sihua(None, SihuaVariant.排命盘口诀转录)  # type: ignore[arg-type]
  with pytest.raises(TypeError):
    place_decades(None)  # type: ignore[arg-type]


@pytest.mark.parametrize("variant", tuple(SihuaVariant))
def test_year_boundary_gap_changes_both_outputs(
  choices: ChartConfig,
  variant: SihuaVariant,
) -> None:
  record = _civil(date(2024, 2, 6), time(12))
  lunar = resolve(record, choices)
  spring = resolve(record, replace(choices, year_boundary=YearBoundary.立春))
  before = shengnian_sihua(lunar, variant)
  after = shengnian_sihua(spring, variant)
  assert lunar.lunar_year == spring.lunar_year == 2023
  assert (before.year_tiangan, after.year_tiangan) == (Tiangan.癸, Tiangan.甲)
  assert (before.lu, before.ji, after.lu, after.ji) == (
    Star.破军,
    Star.贪狼,
    Star.廉贞,
    Star.太阳,
  )
  assert place_decades(lunar)[0].direction is Direction.逆行
  assert place_decades(spring)[0].direction is Direction.顺行


def test_actual_lichun_second_sides_change_sihua_and_direction(choices: ChartConfig) -> None:
  choices = replace(choices, year_boundary=YearBoundary.立春)
  before = resolve(_civil(date(2024, 2, 4), time(16, 27, 6)), choices)
  after = resolve(_civil(date(2024, 2, 4), time(16, 27, 7)), choices)
  assert shengnian_sihua(before, SihuaVariant.排命盘口诀转录).lu is Star.破军
  assert shengnian_sihua(after, SihuaVariant.排命盘口诀转录).lu is Star.廉贞
  assert place_decades(before)[0].direction is Direction.逆行
  assert place_decades(after)[0].direction is Direction.顺行


@pytest.mark.parametrize("day", [15, 16])
@pytest.mark.parametrize("policy", tuple(LeapMonthPolicy))
def test_decades_use_selected_leap_month(
  choices: ChartConfig, day: int, policy: LeapMonthPolicy
) -> None:
  value = resolve(
    LunarBirthRecord(
      year=2020,
      month=4,
      day=day,
      is_leap_month=True,
      shichen=Dizhi.午,
      gender=Gender.女,
    ),
    replace(choices, leap_month_policy=policy),
  )
  following = policy is LeapMonthPolicy.全月归下月 or (
    policy is LeapMonthPolicy.上半月归本月下半月归下月 and day == 16
  )
  assert place_decades(value)[0].dizhi is (Dizhi.子 if following else Dizhi.亥)
  assert (place_decades(value)[0].start_age, place_decades(value)[0].end_age) == (
    (6, 15) if following else (5, 14)
  )
  assert place_decades(value)[0].direction is Direction.逆行
