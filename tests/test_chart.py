"""独立原例、注明手推的合成例与组件联动分别验证。"""

import sys
from collections.abc import Iterator
from dataclasses import FrozenInstanceError, replace
from datetime import date, time, timedelta
from importlib.util import find_spec
from itertools import product
from typing import Any, Never

import pytest

from ziwei import chart as module
from ziwei.birth import Gender, GregorianBirthRecord, LunarBirthRecord, TimePrecision
from ziwei.bureau import WuxingJu
from ziwei.calendar import LunarAlgorithm, supported_lunar_year_range
from ziwei.chart import ZiweiChart, create_chart
from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, TianmaRule, YearBoundary
from ziwei.decades import Direction, place_decades
from ziwei.ganzhi import Dizhi
from ziwei.palaces import (
  PalaceName,
  effective_month,
  minggong_dizhi,
  shengong_dizhi,
  twelve_palaces,
)
from ziwei.resolver import resolve
from ziwei.sihua import SihuaVariant, shengnian_sihua
from ziwei.stars import Star, place_stars
from ziwei.timezone import FixedOffset, IanaTimezone


@pytest.fixture(autouse=True)
def _unload_celestial() -> Iterator[None]:
  yield
  for name in tuple(sys.modules):
    if name.startswith("celestial_calendar"):
      del sys.modules[name]


def test_external_1954_full_chart(
  lunar_chart: ZiweiChart, expected_1954: dict[Star, Dizhi]
) -> None:
  """http://www.zhongyi999.com.cn/thread-1744-1-1.html，举例1-13步；底本未核。

  1954九月初七子时男命，甲午、火六局、命身同戌。第22步正文列前九限，末三限按规则推得，表23图未核。
  年马/月马此例相同，不用于证明切换。只验证已实现的28星，其他星曜不纳入。
  """
  assert lunar_chart.bureau is WuxingJu.火六局
  assert lunar_chart.shengong is Dizhi.戌
  assert lunar_chart.palaces[0].name is PalaceName.命宫
  assert [p.dizhi.value for p in lunar_chart.palaces] == list("戌酉申未午巳辰卯寅丑子亥")
  assert [str(p.ganzhi) for p in lunar_chart.palaces] == [
    "甲戌",
    "癸酉",
    "壬申",
    "辛未",
    "庚午",
    "己巳",
    "戊辰",
    "丁卯",
    "丙寅",
    "丁丑",
    "丙子",
    "乙亥",
  ]
  assert {p.star: p.dizhi for p in lunar_chart.stars} == expected_1954
  assert (
    lunar_chart.sihua.lu,
    lunar_chart.sihua.quan,
    lunar_chart.sihua.ke,
    lunar_chart.sihua.ji,
  ) == (
    Star.廉贞,
    Star.破军,
    Star.武曲,
    Star.太阳,
  )
  assert [(p.dizhi.value, p.start_age, p.end_age) for p in lunar_chart.decades[:9]] == [
    ("戌", 6, 15),
    ("亥", 16, 25),
    ("子", 26, 35),
    ("丑", 36, 45),
    ("寅", 46, 55),
    ("卯", 56, 65),
    ("辰", 66, 75),
    ("巳", 76, 85),
    ("午", 86, 95),
  ]
  assert [(p.dizhi.value, p.start_age, p.end_age) for p in lunar_chart.decades[9:]] == [
    ("未", 96, 105),
    ("申", 106, 115),
    ("酉", 116, 125),
  ]
  assert lunar_chart.decades[0].direction is Direction.顺行


def test_same_external_case_gregorian_entry(lunar_chart: ZiweiChart) -> None:
  """同页明确给出1954-10-03 00:00；+08:00为测试选择，原文没有时区，不解析UTC。

  公历和农历入口是同一个外部命例，不能计为两张独立原盘。
  """
  record = GregorianBirthRecord(
    birth_date=date(1954, 10, 3),
    birth_time=time(0),
    time_precision=TimePrecision.时,
    timezone=FixedOffset(timedelta(hours=8)),
    gender=Gender.男,
  )
  result = create_chart(
    record, lunar_chart.calculation.config, sihua_variant=lunar_chart.sihua.variant
  )
  assert (result.calculation.lunar_year, result.calculation.month, result.calculation.day) == (
    1954,
    9,
    7,
  )
  assert result.stars == lunar_chart.stars
  assert result.palaces == lunar_chart.palaces
  assert result.decades == lunar_chart.decades
  assert result.calculation.resolved_time is None


def test_hand_derived_synthetic_chart(chart_choices: ChartConfig) -> None:
  """合成甲子年正月初一子时女命；据已登记口诀手推，不是外部原盘。

  寅宫起正月子时命身皆寅，甲年起丙寅，炉中火为火六局；局六日一补五，寅逆五再顺一为酉。
  主星按《全书》固定偏移推得，甲女逆限。此例区分年马寅与月马申。
  """
  record = LunarBirthRecord(
    year=1984, month=1, day=1, is_leap_month=False, shichen=Dizhi.子, gender=Gender.女
  )
  value = create_chart(
    record,
    replace(chart_choices, tianma_rule=TianmaRule.年支天马),
    sihua_variant=SihuaVariant.王亭之讲义转录,
  )
  assert str(value.palaces[0].ganzhi) == "丙寅"
  assert value.shengong is Dizhi.寅 and value.bureau is WuxingJu.火六局
  assert "".join(p.dizhi.value for p in value.stars[:14]) == "酉申午巳辰丑未申酉戌亥子丑巳"
  assert value.stars[-1].dizhi is Dizhi.寅
  assert "".join(p.dizhi.value for p in value.decades) == "寅丑子亥戌酉申未午巳辰卯"
  assert value.decades[0].direction is Direction.逆行


@pytest.mark.parametrize(
  "leap,rollover,boundary,horse,variant",
  list(
    product(
      tuple(LeapMonthPolicy),
      tuple(DayRollover),
      tuple(YearBoundary),
      tuple(TianmaRule),
      tuple(SihuaVariant),
    )
  ),
)
def test_configuration_composition(
  leap: LeapMonthPolicy,
  rollover: DayRollover,
  boundary: YearBoundary,
  horse: TianmaRule,
  variant: SihuaVariant,
) -> None:
  """合成闰月与晚子时组合，核组件使用同一解析结果；不称独立历法参考。"""
  choices = ChartConfig(
    leap_month_policy=leap, day_rollover=rollover, year_boundary=boundary, tianma_rule=horse
  )
  record = GregorianBirthRecord(
    birth_date=date(2023, 4, 6),
    birth_time=time(23),
    time_precision=TimePrecision.时,
    timezone=FixedOffset(timedelta(hours=8)),
    gender=Gender.男,
  )
  result = create_chart(record, choices, sihua_variant=variant)
  value = result.calculation
  month = effective_month(value.month, value.day, value.is_leap_month, leap)
  assert result.palaces[0].dizhi is minggong_dizhi(month, Dizhi.子)
  assert result.shengong is shengong_dizhi(month, Dizhi.子)
  assert result.stars == place_stars(value)
  assert result.sihua == shengnian_sihua(value, variant)
  assert result.decades == place_decades(value)
  assert value.day_rolled is (rollover is DayRollover.晚子时归次日)
  assert (value.resolved_time is not None) is (boundary is YearBoundary.立春)


@pytest.mark.parametrize("algorithm", tuple(LunarAlgorithm))
@pytest.mark.parametrize("endpoint", [0, 1])
def test_algorithm_endpoints(
  chart_choices: ChartConfig, algorithm: LunarAlgorithm, endpoint: int
) -> None:
  year = supported_lunar_year_range(algorithm)[endpoint]
  record = LunarBirthRecord(
    year=year, month=1, day=1, is_leap_month=False, shichen=Dizhi.午, gender=Gender.女
  )
  result = create_chart(
    record, chart_choices, sihua_variant=SihuaVariant.排命盘口诀转录, lunar_algorithm=algorithm
  )
  assert result.calculation.lunar_year == year
  assert result.calculation.supported_lunar_year_range == supported_lunar_year_range(algorithm)


@pytest.mark.parametrize("missing", ["shichen", "gender"])
def test_complete_entry_rejects_unknown(chart_choices: ChartConfig, missing: str) -> None:
  record = LunarBirthRecord(
    year=2024,
    month=1,
    day=1,
    is_leap_month=False,
    shichen=None if missing == "shichen" else Dizhi.子,
    gender=Gender.未知 if missing == "gender" else Gender.男,
  )
  with pytest.raises(ValueError, match="已知时辰与性别"):
    create_chart(record, chart_choices, sihua_variant=SihuaVariant.排命盘口诀转录)


def test_chart_is_frozen_and_copies_sequences(lunar_chart: ZiweiChart) -> None:
  stars = list(lunar_chart.stars)
  result = replace(lunar_chart, stars=stars)  # type: ignore[arg-type]
  stars.clear()
  assert len(result.stars) == 28
  with pytest.raises(FrozenInstanceError):
    result.shengong = Dizhi.寅  # type: ignore[misc]


@pytest.mark.parametrize(
  "field,bad,error,location",
  [
    ("palaces", (), ValueError, "十二宫数量不符"),
    ("stars", (), ValueError, "星位数量不符"),
    ("decades", (), ValueError, "大限数量不符"),
    ("shengong", Dizhi.子, ValueError, "身宫"),
    ("bureau", WuxingJu.水二局, ValueError, "五行局"),
    ("calculation", None, TypeError, "CalculationInput"),
    ("sihua", None, TypeError, "四化"),
    ("palaces", ["命宫"], TypeError, "palaces"),
    ("shengong", "戌", TypeError, "身宫"),
  ],
)
def test_chart_rejects_bad_parts(
  lunar_chart: ZiweiChart, field: str, bad: Any, error: type[Exception], location: str
) -> None:
  with pytest.raises(error, match=location):
    replace(lunar_chart, **{field: bad})


def test_partial_calculation_cannot_form_complete_chart(civil_chart: ZiweiChart) -> None:
  old = replace(civil_chart.calculation, resolved_time=None)
  assert old.resolved_time is None
  assert place_stars(old) == civil_chart.stars
  with pytest.raises(ValueError, match="存在性"):
    replace(civil_chart, calculation=old)


def test_create_calls_complete_guard(
  chart_choices: ChartConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
  from ziwei.birth import CalculationInput

  def reject(self: CalculationInput) -> None:
    raise ValueError("guard reached")

  monkeypatch.setattr(CalculationInput, "require_complete", reject)
  record = LunarBirthRecord(
    year=2024, month=1, day=1, is_leap_month=False, shichen=Dizhi.子, gender=Gender.男
  )
  with pytest.raises(ValueError, match="guard reached"):
    module.create_chart(record, chart_choices, sihua_variant=SihuaVariant.排命盘口诀转录)


def test_actual_lichun_second_neighbors(chart_choices: ChartConfig) -> None:
  """既有celestial适配的立春相邻秒联动；不是独立外部命例。"""
  choices = replace(chart_choices, year_boundary=YearBoundary.立春)
  record = GregorianBirthRecord(
    birth_date=date(2024, 2, 4),
    birth_time=time(16, 27, 6),
    time_precision=TimePrecision.秒,
    timezone=FixedOffset(timedelta(hours=8)),
    gender=Gender.女,
  )
  before = create_chart(record, choices, sihua_variant=SihuaVariant.王亭之讲义转录)
  after = create_chart(
    replace(record, birth_time=time(16, 27, 7)), choices, sihua_variant=SihuaVariant.王亭之讲义转录
  )
  assert before.calculation.ganzhi_year == 2023
  assert after.calculation.ganzhi_year == 2024
  assert before.sihua.year_tiangan != after.sihua.year_tiangan
  assert before.calculation.lichun_jd == after.calculation.lichun_jd


@pytest.mark.parametrize("boundary", tuple(YearBoundary))
def test_solar_time_crossing_date_is_preserved(
  chart_choices: ChartConfig, boundary: YearBoundary
) -> None:
  """合成民用3月10日00:20、经度100度，真太阳钟落在3月9日亥时。"""
  record = GregorianBirthRecord(
    birth_date=date(2024, 3, 10),
    birth_time=time(0, 20),
    time_precision=TimePrecision.分,
    timezone=FixedOffset(timedelta(hours=8)),
    gender=Gender.男,
    longitude_deg=100.0,
  )
  result = create_chart(
    record,
    replace(chart_choices, year_boundary=boundary),
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  value = result.calculation
  assert value.apparent_solar and value.resolved_time is not None
  assert (value.month, value.day, value.shichen) == (1, 29, Dizhi.亥)
  stored_record = value.record
  assert isinstance(stored_record, GregorianBirthRecord) and stored_record.birth_date == date(
    2024, 3, 10
  )


@pytest.mark.parametrize("defect", ["apparent", "shichen", "resolved"])
def test_civil_chart_combination_policy_rejects_mismatches(
  civil_chart: ZiweiChart, defect: str
) -> None:
  value = civil_chart.calculation
  if defect == "apparent":
    value = replace(value, record=replace(value.record, longitude_deg=100.0))
  elif defect == "shichen":
    value = replace(value, shichen=Dizhi.巳)
  else:
    resolved = value.resolved_time
    assert resolved is not None
    value = replace(
      value, resolved_time=replace(resolved, zone=FixedOffset(resolved.offset), data=None, fold=0)
    )
  with pytest.raises(ValueError):
    replace(civil_chart, calculation=value)


def test_chart_rejects_unrolled_civil_late_zi(chart_choices: ChartConfig) -> None:
  record = GregorianBirthRecord(
    birth_date=date(2024, 11, 2),
    birth_time=time(23, 30),
    time_precision=TimePrecision.分,
    timezone=FixedOffset(timedelta(hours=8)),
    gender=Gender.男,
  )
  valid = create_chart(
    record,
    replace(chart_choices, day_rollover=DayRollover.晚子时归次日),
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  assert valid.calculation.day_rolled
  with pytest.raises(ValueError, match="晚子时顺延须与民用钟点和换日口径一致"):
    replace(valid, calculation=replace(valid.calculation, day_rolled=False))


@pytest.mark.parametrize("change", ["nonfinite", "longitude", "lunar-zi", "instant", "type"])
def test_chart_rejects_inconsistent_calculation(
  lunar_chart: ZiweiChart, civil_chart: ZiweiChart, change: str
) -> None:
  value = lunar_chart.calculation
  if change == "nonfinite":
    value = replace(civil_chart.calculation, ut1_jd=float("nan"))
  elif change == "longitude":
    value = replace(value, record=replace(value.record, longitude_deg=100.0))
  elif change == "lunar-zi":
    value = replace(value, config=replace(value.config, day_rollover=DayRollover.晚子时归次日))
  elif change == "instant":
    value = replace(value, resolved_time=civil_chart.calculation.resolved_time)
  else:
    with pytest.raises(TypeError):
      replace(value, resolved_time="not a ResolvedTime")  # type: ignore[arg-type]
    return
  # 低层值不核完整盘关系，组合入口仍须拒绝矛盾。
  with pytest.raises(ValueError):
    replace(lunar_chart, calculation=value)


def test_same_string_palace_fields_are_not_domain_members(lunar_chart: ZiweiChart) -> None:
  with pytest.raises(TypeError, match="领域枚举"):
    replace(lunar_chart.palaces[0], dizhi="戌")  # type: ignore[arg-type]


@pytest.mark.parametrize("missing", ["shichen", "gender"])
def test_direct_chart_rejects_unknown(lunar_chart: ZiweiChart, missing: str) -> None:
  record = replace(
    lunar_chart.calculation.record,
    **({"shichen": None} if missing == "shichen" else {"gender": Gender.未知}),
  )
  value = replace(
    lunar_chart.calculation,
    record=record,
    shichen=None if missing == "shichen" else lunar_chart.calculation.shichen,
  )
  with pytest.raises(ValueError, match="已知时辰与性别"):
    replace(lunar_chart, calculation=value)


def test_component_sequence_errors_locate_first_difference(lunar_chart: ZiweiChart) -> None:
  branches = tuple(Dizhi)
  wrong: dict[str, tuple[Any, str]] = {
    "palaces": (twelve_palaces(Dizhi.子, lunar_chart.calculation.year_ganzhi.tiangan), "十二宫"),
    "stars": (
      tuple(
        replace(p, dizhi=branches[(branches.index(p.dizhi) + 1) % 12]) for p in lunar_chart.stars
      ),
      "星位",
    ),
    "decades": (tuple(reversed(lunar_chart.decades)), "大限"),
  }
  for field, (items, label) in wrong.items():
    with pytest.raises(ValueError, match=rf"{label}\[0\].*应为.*实际为"):
      replace(lunar_chart, **{field: items})
  with pytest.raises(ValueError, match=r"身宫.*应为戌.*实际为子"):
    replace(lunar_chart, shengong=Dizhi.子)
  with pytest.raises(ValueError, match=r"五行局.*应为火六局.*实际为水二局"):
    replace(lunar_chart, bureau=WuxingJu.水二局)
  other = shengnian_sihua(
    replace(lunar_chart.calculation, ganzhi_year=1955, lunar_year=1955),
    lunar_chart.sihua.variant,
  )
  with pytest.raises(ValueError, match=r"四化.*生年干.*应为.*实际为"):
    replace(lunar_chart, sihua=other)


@pytest.mark.parametrize(
  "policy,day,ming_ganzhi,bureau,ziwei,left,right",
  [
    (LeapMonthPolicy.全月归本月, 15, "乙卯", WuxingJu.水二局, Dizhi.申, Dizhi.巳, Dizhi.酉),
    (LeapMonthPolicy.全月归本月, 16, "乙卯", WuxingJu.水二局, Dizhi.酉, Dizhi.巳, Dizhi.酉),
    (LeapMonthPolicy.全月归下月, 15, "丙辰", WuxingJu.土五局, Dizhi.辰, Dizhi.午, Dizhi.申),
    (LeapMonthPolicy.全月归下月, 16, "丙辰", WuxingJu.土五局, Dizhi.酉, Dizhi.午, Dizhi.申),
    (
      LeapMonthPolicy.上半月归本月下半月归下月,
      15,
      "乙卯",
      WuxingJu.水二局,
      Dizhi.申,
      Dizhi.巳,
      Dizhi.酉,
    ),
    (
      LeapMonthPolicy.上半月归本月下半月归下月,
      16,
      "丙辰",
      WuxingJu.土五局,
      Dizhi.酉,
      Dizhi.午,
      Dizhi.申,
    ),
  ],
)
def test_hand_derived_leap_boundary_frame(
  chart_choices: ChartConfig,
  policy: LeapMonthPolicy,
  day: int,
  ming_ganzhi: str,
  bureau: WuxingJu,
  ziwei: Dizhi,
  left: Dizhi,
  right: Dizhi,
) -> None:
  """合成癸卯年闰二月子时女命；非外部原盘。

  按已登记口诀手推：癸年甲寅，二月子时命身皆卯、乙卯水二局；三月皆辰、丙辰土五局。
  水二局十五补一得申、十六得酉；土五局十五得辰、十六补四得酉。阴女顺限。
  """
  record = LunarBirthRecord(
    year=2023, month=2, day=day, is_leap_month=True, shichen=Dizhi.子, gender=Gender.女
  )
  choices = replace(chart_choices, leap_month_policy=policy)
  value = resolve(record, choices)
  result = create_chart(record, choices, sihua_variant=SihuaVariant.排命盘口诀转录)
  assert str(result.palaces[0].ganzhi) == ming_ganzhi
  assert result.shengong.value == ming_ganzhi[1] and result.bureau is bureau
  for positions in (result.stars, place_stars(value)):
    stars = {p.star: p.dizhi for p in positions}
    assert (stars[Star.紫微], stars[Star.左辅], stars[Star.右弼]) == (ziwei, left, right)
  for periods in (result.decades, place_decades(value)):
    assert periods[0].dizhi.value == ming_ganzhi[1]
    assert periods[0].start_age == bureau.number
    assert periods[0].direction is Direction.顺行


def test_low_level_entry_requirements_remain_separate(lunar_chart: ZiweiChart) -> None:
  value = replace(
    lunar_chart.calculation, record=replace(lunar_chart.calculation.record, gender=Gender.未知)
  )
  assert place_stars(value) == lunar_chart.stars
  with pytest.raises(ValueError, match="性别"):
    place_decades(value)
  value = replace(value, shichen=None)
  with pytest.raises(ValueError, match="安星需要已知时辰"):
    place_stars(value)
  with pytest.raises(ValueError, match="起大限需要已知时辰"):
    place_decades(value)
  with pytest.raises(TypeError, match="CalculationInput"):
    place_stars(None)  # type: ignore[arg-type]
  with pytest.raises(TypeError, match="CalculationInput"):
    place_decades(None)  # type: ignore[arg-type]


def test_other_year_sihua_is_rejected(lunar_chart: ZiweiChart, civil_chart: ZiweiChart) -> None:
  with pytest.raises(ValueError, match="生年干"):
    replace(lunar_chart, sihua=civil_chart.sihua)


def test_persistence_surface_is_removed() -> None:
  assert find_spec("ziwei.serialization") is None
  assert not hasattr(module, "recalculate")
  assert "software_version" not in ZiweiChart.__dataclass_fields__


@pytest.mark.parametrize("fold", [None, 0, 1])
@pytest.mark.parametrize(
  "day,clock",
  [
    (date(2000, 6, 1), time(12)),
    (date(1988, 4, 17), time(2, 30)),
    (date(1988, 9, 11), time(1, 30)),
  ],
)
def test_pure_civil_chart_preserves_unchecked_fold(
  chart_choices: ChartConfig,
  monkeypatch: pytest.MonkeyPatch,
  fold: int | None,
  day: date,
  clock: time,
) -> None:
  def unexpected_instant(_: GregorianBirthRecord) -> Never:
    raise AssertionError("pure civil path resolved an instant")

  monkeypatch.setattr(GregorianBirthRecord, "resolve_time", unexpected_instant)
  timezone = IanaTimezone("Asia/Shanghai", fold)
  record = GregorianBirthRecord(
    birth_date=day,
    birth_time=clock,
    time_precision=TimePrecision.分,
    timezone=timezone,
    gender=Gender.男,
  )
  result = create_chart(record, chart_choices, sihua_variant=SihuaVariant.排命盘口诀转录)
  assert result.calculation.record is record
  assert record.timezone is timezone and timezone.fold == fold
  assert result.calculation.resolved_time is None


@pytest.mark.parametrize("path", ["lichun", "solar"])
@pytest.mark.parametrize("fold", [None, 0, 1])
def test_chart_distinguishes_requested_and_actual_fold(
  chart_choices: ChartConfig, path: str, fold: int | None
) -> None:
  timezone = IanaTimezone("Asia/Shanghai", fold)
  record = GregorianBirthRecord(
    birth_date=date(2000, 6, 1),
    birth_time=time(12),
    time_precision=TimePrecision.分,
    timezone=timezone,
    gender=Gender.男,
    longitude_deg=120.0 if path == "solar" else None,
  )
  choices = replace(
    chart_choices,
    year_boundary=YearBoundary.立春 if path == "lichun" else YearBoundary.农历正月初一,
  )
  if fold == 1:
    with pytest.raises(ValueError, match="fold"):
      create_chart(record, choices, sihua_variant=SihuaVariant.排命盘口诀转录)
  else:
    result = create_chart(record, choices, sihua_variant=SihuaVariant.排命盘口诀转录)
    assert result.calculation.record is record
    assert record.timezone is timezone and timezone.fold == fold
    resolved = result.calculation.resolved_time
    assert resolved is not None and resolved.fold == 0
    assert isinstance(resolved.zone, IanaTimezone) and resolved.zone.fold == fold


def test_solar_late_zi_rollover_at_solar_date(chart_choices: ChartConfig) -> None:
  """合成例：民用3月10日00:20、105度对应真太阳晚子时；不是独立原盘。"""
  record = GregorianBirthRecord(
    birth_date=date(2024, 3, 10),
    birth_time=time(0, 20),
    time_precision=TimePrecision.分,
    timezone=FixedOffset(timedelta(hours=8)),
    gender=Gender.男,
    longitude_deg=105.0,
  )
  same = create_chart(record, chart_choices, sihua_variant=SihuaVariant.排命盘口诀转录)
  rolled = create_chart(
    record,
    replace(chart_choices, day_rollover=DayRollover.晚子时归次日),
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  assert same.calculation.apparent_solar and rolled.calculation.apparent_solar
  assert same.calculation.shichen is rolled.calculation.shichen is Dizhi.子
  assert (same.calculation.month, same.calculation.day, same.calculation.day_rolled) == (
    1,
    29,
    False,
  )
  assert (rolled.calculation.month, rolled.calculation.day, rolled.calculation.day_rolled) == (
    2,
    1,
    True,
  )
