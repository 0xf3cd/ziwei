"""解析层：原始出生记录+口径 -> 解析后的计算输入。

## 解析顺序

1. 时刻：只有立春口径或真太阳时（有经度）才调用 `resolve_time()`；正月初一口径加无经度
   纯民用路径不要求 UTC 不早于 1972。
2. 时辰：民用路径取记录钟面；真太阳时路径取真太阳钟（`apparent_solar`）的钟面。
   时辰所附民用日：民用路径取出生地当地民用日（`record.birth_date`），真太阳时路径取
   真太阳钟的民用日。
3. 农历日：由时辰所附民用日标签换算（`gregorian_to_lunar`），不随时刻或时区另选日期。
4. 子时换日：时辰为子且落在所附民用日 23:00-24:00（晚子时）时，`晚子时归次日` 取该日
   次日的农历日，`早晚子时同日` 不改；`day_rolled` 记录是否顺延。
5. 换年：立春 -> 出生瞬间按 modelled-UT1 换算（`utc_to_ut1_jd`）与立春时刻
   （`lichun_jd`）比较，左闭右开（出生瞬间等于立春时刻归新年）；正月初一 -> 按换日
   调整后的农历日所属年。
6. 未知时辰/性别可随解析输入保存；安星需要已知时辰，允许性别未知。完整命盘另要求性别已知。

## 失败边界

- 农历输入选立春口径：显式失败（农历记录没有瞬间与时区，无法与立春 UT1 时刻同标比较）。
- 1972 年前的公历记录需要瞬间（立春口径或真太阳时）时：显式失败（`resolve_time` 拒绝
  现代 UTC 合同之前的历史时刻）；正月初一口径加无经度路径不受影响。
- 请求的农历算法不支持该日期、闰月/日组合不存在、时辰未知但需要瞬间（立春口径或
  真太阳时——有经度但钟点未知）时：显式失败。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Final, cast

from ziwei.birth import BirthRecord, CalculationInput, GregorianBirthRecord, LunarBirthRecord
from ziwei.calendar import (
  LunarAlgorithm,
  apparent_solar,
  celestial_version,
  gregorian_to_lunar,
  lichun_jd,
  utc_to_ut1_jd,
  validate_lunar_date,
)
from ziwei.config import ChartConfig, DayRollover, YearBoundary
from ziwei.ganzhi import Dizhi
from ziwei.timezone import IanaTimezone, ResolvedTime


def _shichen_from_fraction(fraction: float) -> tuple[Dizhi, bool]:
  """由当日小数取时辰与是否晚子时（23:00-24:00，左闭右开）。"""
  hour = int(fraction * 24)
  return tuple(Dizhi)[((hour + 1) // 2) % 12], hour == 23


def _roll_lunar_date(algorithm: LunarAlgorithm, anchor: date) -> tuple[int, int, int, bool]:
  """取 anchor 次日（公历日+1）的农历日。"""
  year, month, day, is_leap = gregorian_to_lunar(algorithm, anchor + timedelta(days=1))
  return year, month, day, is_leap


def _resolve_gregorian(
  record: GregorianBirthRecord, config: ChartConfig, algorithm: LunarAlgorithm
) -> CalculationInput:
  need_instant = config.year_boundary is YearBoundary.立春 or record.longitude_deg is not None
  resolved = record.resolve_time() if need_instant and record.birth_time is not None else None
  late_zi = False
  if record.birth_time is None:
    if record.longitude_deg is not None:
      raise ValueError("真太阳时需要已知钟点")
    shichen = None
    anchor = record.birth_date
    apparent = False
  elif record.longitude_deg is not None:
    # 本分支 birth_time 非 None 且 need_instant 含经度，resolved 必已解析。
    solar_year, solar_month, solar_day, fraction = apparent_solar(
      cast(ResolvedTime, resolved).utc, record.longitude_deg
    )
    shichen, late_zi = _shichen_from_fraction(fraction)
    anchor = date(solar_year, solar_month, solar_day)
    apparent = True
  else:
    if isinstance(record.timezone, IanaTimezone):
      record.timezone.require_resolvable()
    shichen = record.shichen
    late_zi = record.birth_time.hour == 23
    anchor = record.birth_date
    apparent = False

  lunar_year, month, day, is_leap = gregorian_to_lunar(algorithm, anchor)
  rolled = False
  if shichen is Dizhi.子 and late_zi and config.day_rollover is DayRollover.晚子时归次日:
    lunar_year, month, day, is_leap = _roll_lunar_date(algorithm, anchor)
    rolled = True

  if config.year_boundary is YearBoundary.立春:
    if resolved is None:
      raise ValueError("立春换年需要已知钟点与时区")
    ut1_jd = utc_to_ut1_jd(resolved.utc)
    civil_year = record.birth_date.year
    moment = lichun_jd(civil_year)
    ganzhi_year = civil_year if ut1_jd >= moment else civil_year - 1
    lichun = moment
  else:
    ganzhi_year = lunar_year
    ut1_jd = None
    lichun = None

  return CalculationInput(
    record=record,
    lunar_year=lunar_year,
    month=month,
    day=day,
    is_leap_month=is_leap,
    shichen=shichen,
    ganzhi_year=ganzhi_year,
    config=config,
    lunar_algorithm=algorithm,
    lunar_algorithm_version=celestial_version(),
    apparent_solar=apparent,
    day_rolled=rolled,
    ut1_jd=ut1_jd,
    lichun_jd=lichun,
    resolved_time=resolved,
  )


def _resolve_lunar(
  record: LunarBirthRecord, config: ChartConfig, algorithm: LunarAlgorithm
) -> CalculationInput:
  if config.year_boundary is YearBoundary.立春:
    raise ValueError("农历输入不支持立春换年口径：记录没有瞬间与时区，无法与立春时刻同标比较")
  if record.longitude_deg is not None:
    raise ValueError("农历记录没有钟点与时区，无法应用真太阳时：请用公历记录或去掉经度")
  if record.shichen is Dizhi.子 and config.day_rollover is DayRollover.晚子时归次日:
    raise ValueError(
      "农历记录的子时无法判定早子时（00-01）或晚子时（23-24）；晚子时归次日需公历钟点"
    )
  validate_lunar_date(algorithm, record.year, record.month, record.day, record.is_leap_month)
  return CalculationInput(
    record=record,
    lunar_year=record.year,
    month=record.month,
    day=record.day,
    is_leap_month=record.is_leap_month,
    shichen=record.shichen,
    ganzhi_year=record.year,
    config=config,
    lunar_algorithm=algorithm,
    lunar_algorithm_version=celestial_version(),
    apparent_solar=False,
    day_rolled=False,
    ut1_jd=None,
    lichun_jd=None,
  )


DEFAULT_LUNAR_ALGORITHM: Final = LunarAlgorithm.ALGO3
"""默认农历算法：混合(1901-2099 与 HKO 表一致，范围 1600-2199)。"""


def resolve(
  record: BirthRecord,
  config: ChartConfig,
  lunar_algorithm: LunarAlgorithm = DEFAULT_LUNAR_ALGORITHM,
) -> CalculationInput:
  """把原始出生记录按口径解析为计算输入。

  农历算法为具名参数，默认 ALGO3（混合）；算法与版本随结果保存。公历记录按上述解析
  顺序换算农历日、应用子时换日并判定换年；农历记录直接取给定日期，只支持正月初一换年。
  """
  if not isinstance(record, BirthRecord):
    raise TypeError("须为公历或农历出生记录")
  if not isinstance(config, ChartConfig):
    raise TypeError("口径须为显式 ChartConfig")
  if not isinstance(lunar_algorithm, LunarAlgorithm):
    raise TypeError("农历算法须为 LunarAlgorithm 成员")
  if isinstance(record, LunarBirthRecord):
    return _resolve_lunar(record, config, lunar_algorithm)
  return _resolve_gregorian(record, config, lunar_algorithm)
