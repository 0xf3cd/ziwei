"""从真实解析路径到星位的联动；独立28星例不由本仓算法生成。"""

from dataclasses import replace
from datetime import date, time, timedelta

import pytest

from ziwei import stars
from ziwei.birth import (
  CalculationInput,
  Gender,
  GregorianBirthRecord,
  LunarBirthRecord,
  TimePrecision,
)
from ziwei.bureau import WuxingJu
from ziwei.calendar import LunarAlgorithm
from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, TianmaRule, YearBoundary
from ziwei.ganzhi import Dizhi
from ziwei.resolver import resolve
from ziwei.stars import Star, StarPlacement, place_major_stars, place_stars
from ziwei.timezone import FixedOffset

pytestmark = pytest.mark.usefixtures("unload_celestial")


@pytest.fixture
def choices() -> ChartConfig:
  return ChartConfig(
    leap_month_policy=LeapMonthPolicy.全月归本月,
    day_rollover=DayRollover.早晚子时同日,
    year_boundary=YearBoundary.农历正月初一,
  )


def _positions(value: CalculationInput) -> dict[Star, Dizhi]:
  result = place_stars(value)
  assert len(result) == 30
  assert tuple(item.star for item in result) == tuple(Star)
  return {item.star: item.dizhi for item in result}


def _civil(day: date, clock: time, longitude: float | None = None) -> GregorianBirthRecord:
  return GregorianBirthRecord(
    birth_date=day,
    birth_time=clock,
    time_precision=TimePrecision.秒,
    timezone=FixedOffset(timedelta(hours=8)),
    gender=Gender.未知,
    longitude_deg=longitude,
  )


def test_independent_1954_ninth_month_seventh_day_zi(
  choices: ChartConfig, expected_1954: dict[Star, Dizhi]
) -> None:
  """2007论坛转《排命盘口诀》末段第1至13步，原著/底本未核。

  http://www.zhongyi999.com.cn/thread-1744-1-1.html
  匿名农历1954九月初七子时、火六局；正月初一换年、早晚子时同日、月马，无地点或时区。
  本例年马与月马同在申，不能区分切换；切换由另一个不同三合组的年/月支用例验证。
  """
  record = LunarBirthRecord(
    year=1954,
    month=9,
    day=7,
    is_leap_month=False,
    shichen=Dizhi.子,
    gender=Gender.男,
    source="匿名盘例：2007论坛转《排命盘口诀》排命盘举例第1至13步",
  )
  value = resolve(record, replace(choices, tianma_rule=TianmaRule.月支天马))
  expected = expected_1954
  actual = _positions(value)
  assert {star: actual[star] for star in expected} == expected
  assert len(set(expected.values())) < len(expected)  # 同宫不丢星。
  assert _positions(replace(value, config=choices)) == actual  # 此例两种马相同，另例辨选择。


def test_default_year_horse_and_explicit_month_horse_are_recorded(choices: ChartConfig) -> None:
  record = LunarBirthRecord(
    year=2024,
    month=1,
    day=7,
    is_leap_month=False,
    shichen=Dizhi.子,
    gender=Gender.未知,
  )
  value = resolve(record, choices)
  year = place_stars(value)  # 辰年取寅；正月寅支取申，非同三合组。
  month = place_stars(replace(value, config=replace(choices, tianma_rule=TianmaRule.月支天马)))
  year_ma = next(position for position in year if position.star is Star.天马)
  month_ma = next(position for position in month if position.star is Star.天马)
  assert (year_ma.dizhi, month_ma.dizhi) == (Dizhi.寅, Dizhi.申)
  assert year_ma.rule_id == "variant.tianma.year-branch"
  assert month_ma.rule_id == "variant.tianma.month-branch"
  assert tuple(p for p in year if p.star is not Star.天马) == tuple(
    p for p in month if p.star is not Star.天马
  )
  assert choices.tianma_rule is TianmaRule.年支天马
  assert place_stars(value) == year  # 后续配置选择不改变已返回的值。
  assert value.gender is Gender.未知  # 安星不依赖性别。


@pytest.mark.parametrize("defect", ["missing", "duplicate"])
def test_internal_bad_composition_is_rejected(
  choices: ChartConfig, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
  record = LunarBirthRecord(
    year=2024, month=1, day=1, is_leap_month=False, shichen=Dizhi.子, gender=Gender.未知
  )
  value = resolve(record, choices)
  original = stars.place_hour_stars(Dizhi.子)
  broken = original[:-1] if defect == "missing" else (original[0], original[0], *original[2:])
  monkeypatch.setattr(stars, "place_hour_stars", lambda _: broken)
  with pytest.raises(ValueError, match="覆盖全部星曜且每颗只出现一次"):
    stars.place_stars(value)


def test_unknown_internal_tianma_selection_is_not_month_horse(choices: ChartConfig) -> None:
  record = LunarBirthRecord(
    year=2024, month=1, day=1, is_leap_month=False, shichen=Dizhi.子, gender=Gender.未知
  )
  value = resolve(record, choices)
  invalid = replace(choices)
  object.__setattr__(invalid, "tianma_rule", object())
  with pytest.raises(ValueError, match="不支持的天马查法"):
    stars.place_stars(replace(value, config=invalid))


@pytest.mark.parametrize("day", [15, 16])
@pytest.mark.parametrize("policy", tuple(LeapMonthPolicy))
def test_leap_fourth_month_all_policies_day15_day16(
  choices: ChartConfig,
  policy: LeapMonthPolicy,
  day: int,
) -> None:
  record = LunarBirthRecord(
    year=2020,
    month=4,
    day=day,
    is_leap_month=True,
    shichen=Dizhi.午,
    gender=Gender.未知,
  )
  value = resolve(
    record, replace(choices, leap_month_policy=policy, tianma_rule=TianmaRule.月支天马)
  )
  following = policy is LeapMonthPolicy.全月归下月 or (
    policy is LeapMonthPolicy.上半月归本月下半月归下月 and day == 16
  )
  expected = (Dizhi.申, Dizhi.午, Dizhi.申) if following else (Dizhi.未, Dizhi.未, Dizhi.亥)
  positions = _positions(value)
  assert tuple(positions[star] for star in (Star.左辅, Star.右弼, Star.天马)) == expected
  # 非闰月记录若使用相同月份和日数，应给出相同星位；闰月生日不加上前一个月的天数。
  plain = replace(record, month=5 if following else 4, is_leap_month=False)
  assert positions == _positions(resolve(plain, value.config))
  assert value.day == day


def test_unknown_hour_and_leap_twelfth_fail_without_partial_result(choices: ChartConfig) -> None:
  record = LunarBirthRecord(
    year=2024,
    month=1,
    day=1,
    is_leap_month=False,
    shichen=None,
    gender=Gender.未知,
  )
  unknown = resolve(record, choices)
  with pytest.raises(ValueError, match="时辰"):
    place_stars(unknown)
  known = replace(unknown, record=replace(record, shichen=Dizhi.子), shichen=Dizhi.子)
  # 合成的已解析形状，只检安星组合拒绝无对应月，不冒称历法中存在闰十二月。
  unavailable = replace(
    known,
    month=12,
    is_leap_month=True,
    config=replace(choices, leap_month_policy=LeapMonthPolicy.全月归下月),
  )
  with pytest.raises(ValueError, match="闰十二月"):
    place_stars(unavailable)
  assert len(place_major_stars(WuxingJu.火六局, 1)) == 14


def test_late_zi_changes_ziwei_not_only_resolver_fields(choices: ChartConfig) -> None:
  record = _civil(date(1988, 7, 1), time(23, 30))
  same = _positions(resolve(record, choices))
  late = _positions(resolve(record, replace(choices, day_rollover=DayRollover.晚子时归次日)))
  assert same[Star.紫微] is Dizhi.辰  # 戊年五月子时火六局十八日
  assert late[Star.紫微] is Dizhi.子  # 十九日
  assert same[Star.左辅] is late[Star.左辅] is Dizhi.申


def test_year_policy_inside_spring_festival_lichun_gap(choices: ChartConfig) -> None:
  record = _civil(date(2024, 2, 6), time(12))
  lunar = _positions(resolve(record, choices))
  lichun = _positions(resolve(record, replace(choices, year_boundary=YearBoundary.立春)))
  assert (lunar[Star.禄存], lichun[Star.禄存]) == (Dizhi.子, Dizhi.寅)
  assert (lunar[Star.天魁], lichun[Star.天魁]) == (Dizhi.卯, Dizhi.丑)
  assert (lunar[Star.天马], lichun[Star.天马]) == (Dizhi.巳, Dizhi.寅)


def test_actual_lichun_second_sides_change_stem_and_branch_stars(choices: ChartConfig) -> None:
  choices = replace(choices, year_boundary=YearBoundary.立春)
  # 钉版模型的立春在上海约16:27:06.44；秒级钟点在同一时标下夹住该瞬间。
  before = _positions(resolve(_civil(date(2024, 2, 4), time(16, 27, 6)), choices))
  after = _positions(resolve(_civil(date(2024, 2, 4), time(16, 27, 7)), choices))
  assert (before[Star.禄存], after[Star.禄存]) == (Dizhi.子, Dizhi.寅)
  assert (before[Star.天马], after[Star.天马]) == (Dizhi.巳, Dizhi.寅)
  assert (before[Star.火星], after[Star.火星]) == (Dizhi.巳, Dizhi.戌)


def test_apparent_solar_crosses_day_month_and_hour(choices: ChartConfig) -> None:
  civil = _civil(date(2024, 3, 10), time(0, 20))
  solar = replace(civil, longitude_deg=100.0)
  plain_positions = _positions(resolve(civil, choices))
  solar_positions = _positions(resolve(solar, choices))
  assert (plain_positions[Star.左辅], solar_positions[Star.左辅]) == (Dizhi.巳, Dizhi.辰)
  assert (plain_positions[Star.文曲], solar_positions[Star.文曲]) == (Dizhi.辰, Dizhi.卯)
  assert (plain_positions[Star.紫微], solar_positions[Star.紫微]) == (Dizhi.酉, Dizhi.巳)


@pytest.mark.parametrize(
  "algorithm,year,ma",
  [
    (LunarAlgorithm.ALGO1, 1901, Dizhi.亥),
    (LunarAlgorithm.ALGO1, 2099, Dizhi.巳),
    (LunarAlgorithm.ALGO2, 410, Dizhi.申),
    (LunarAlgorithm.ALGO2, 2500, Dizhi.寅),
    (LunarAlgorithm.ALGO3, 1600, Dizhi.寅),
    (LunarAlgorithm.ALGO3, 2199, Dizhi.巳),
  ],
)
def test_calendar_algorithm_endpoints_reach_placement(
  choices: ChartConfig,
  algorithm: LunarAlgorithm,
  year: int,
  ma: Dizhi,
) -> None:
  record = LunarBirthRecord(
    year=year,
    month=1,
    day=1,
    is_leap_month=False,
    shichen=Dizhi.午,
    gender=Gender.未知,
  )
  value = resolve(record, choices, lunar_algorithm=algorithm)
  positions = _positions(value)
  assert value.lunar_algorithm is algorithm and value.lunar_algorithm_version == "0.8.0"
  assert positions[Star.左辅] is Dizhi.辰
  assert positions[Star.右弼] is Dizhi.戌
  assert positions[Star.天马] is ma


@pytest.mark.parametrize(
  "algorithm,year",
  [
    (LunarAlgorithm.ALGO1, 1900),
    (LunarAlgorithm.ALGO1, 2100),
    (LunarAlgorithm.ALGO2, 409),
    (LunarAlgorithm.ALGO2, 2501),
    (LunarAlgorithm.ALGO3, 1599),
    (LunarAlgorithm.ALGO3, 2200),
  ],
)
def test_outside_algorithm_range_never_yields_positions(
  choices: ChartConfig,
  algorithm: LunarAlgorithm,
  year: int,
) -> None:
  record = LunarBirthRecord(
    year=year,
    month=1,
    day=1,
    is_leap_month=False,
    shichen=Dizhi.午,
    gender=Gender.未知,
  )
  with pytest.raises(ValueError, match="超出"):
    place_stars(resolve(record, choices, lunar_algorithm=algorithm))


def test_placement_does_not_mutate_or_reinterpret_input(choices: ChartConfig) -> None:
  record = LunarBirthRecord(
    year=2024,
    month=1,
    day=7,
    is_leap_month=False,
    shichen=Dizhi.午,
    gender=Gender.未知,
  )
  value = resolve(record, choices)
  snapshot = replace(value)
  result: tuple[StarPlacement, ...] = place_stars(value)
  assert value == snapshot
  assert record is value.record
  assert result == place_stars(value)
