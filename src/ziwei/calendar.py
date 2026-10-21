"""celestial-calendar 0.8.0 的具体适配；导入本模块不初始化 celestial。

公开函数在函数体内 `import celestial_calendar`，包导入与知识查询不会加载原生历法库。
所选农历算法、支持范围与 celestial 版本随解析结果保存；超出支持范围或闰月/日组合
不存在时显式失败。

## 时标合同

celestial 的节气时刻是 UT1，民用输入是 UTC 或固定偏移；本模块只比较同一时标下的值。

- 立春比较：出生瞬间换算到 UT1 日数（`utc_to_ut1_jd`），与立春 UT1 时刻
  （`lichun_jd`）直接比较，不直接比较钟面数值。
- 换算采用 celestial 的 modelled-UT1 定义：TT=UTC+(ΔAT+32.184s)，UT1=TT-ΔT；
  ΔAT 取 1972 年起闰秒表（最后一步 2017-01-01 后恒 37s，与 celestial 的 leap_second
  表一致），ΔT 取 `delta_t` 的 DEFAULT 模型（ALGO5），在 TT 处估一次。该定义已与
  `chart_snapshot` 返回的 `jd_ut1` 在 1972-2099 网格对拍（亚毫秒级一致）。
- 1972 年以前的 UTC 时刻由解析层拒绝；本模块只在解析层已取得 UTC 瞬间时被调用。

## 真太阳时

`apparent_solar_time` 以 UTC 民用时刻与东经经度换算当地真太阳钟；结果仍为 UTC 标
民用时刻（保留 UT1-UTC 的亚秒差距，取时辰时通常不影响）。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from typing import Any, Final


class LunarAlgorithm(StrEnum):
  """农历算法的具名选项；算法与版本随解析结果保存。"""

  ALGO1 = "HKO 表"
  ALGO2 = "天文计算"
  ALGO3 = "混合"
  HKO表 = ALGO1
  天文计算 = ALGO2
  混合 = ALGO3


_ALGORITHM_RANGE: Final[dict[LunarAlgorithm, tuple[int, int]]] = {
  LunarAlgorithm.ALGO1: (1901, 2099),
  LunarAlgorithm.ALGO2: (410, 2500),
  LunarAlgorithm.ALGO3: (1600, 2199),
}
"""三种算法的农历年范围；与 celestial 的 supported_lunar_year_range 一致。"""

_DELTA_T_MODEL = "DEFAULT(ALGO5)"
"""立春比较固定使用的 ΔT 模型；与 celestial 的 jieqi_moment UT1 换算一致。"""


def celestial_version() -> str:
  """已安装 celestial-calendar 的版本字符串。"""
  import celestial_calendar as celestial

  return celestial.__version__


def supported_lunar_year_range(algorithm: LunarAlgorithm) -> tuple[int, int]:
  """所选农历算法的支持范围（农历年，含端点）。"""
  if not isinstance(algorithm, LunarAlgorithm):
    raise TypeError("农历算法须为 LunarAlgorithm 成员")
  return _ALGORITHM_RANGE[algorithm]


def _check_algorithm(algorithm: LunarAlgorithm) -> None:
  if not isinstance(algorithm, LunarAlgorithm):
    raise TypeError("农历算法须为 LunarAlgorithm 成员")


def _check_day(day: date) -> None:
  if type(day) is not date:
    raise TypeError("公历日期须为 date，不接受 datetime")


def _native_algorithm(algorithm: LunarAlgorithm, celestial: Any) -> Any:
  """把本仓算法枚举映射到 celestial 的 LunarAlgorithm 成员。"""
  return {
    LunarAlgorithm.ALGO1: celestial.LunarAlgorithm.ALGO1,
    LunarAlgorithm.ALGO2: celestial.LunarAlgorithm.ALGO2,
    LunarAlgorithm.ALGO3: celestial.LunarAlgorithm.ALGO3,
  }[algorithm]


def gregorian_to_lunar(algorithm: LunarAlgorithm, day: date) -> tuple[int, int, int, bool]:
  """公历日期标签换农历年月日与闰月标志。

  换算以传入的当地民用日标签为基准：民用路径传 `BirthRecord.birth_date`，真太阳时
  路径由解析层传真太阳钟的民用日（见 resolver）。超出算法支持范围或日期不可表示时
  抛ValueError；年历查询或原生转换的内部故障原样传播。
  """
  _check_algorithm(algorithm)
  _check_day(day)
  first_year, last_year = supported_lunar_year_range(algorithm)
  first_day, _, _ = lunar_year_info(algorithm, first_year)
  last_first_day, _, last_lengths = lunar_year_info(algorithm, last_year)
  end = last_first_day + timedelta(days=sum(last_lengths))
  if not first_day <= day < end:
    raise ValueError(f"公历日期{day}超出{algorithm.value}支持范围")
  import celestial_calendar as celestial

  lunar = celestial.gregorian_to_lunar(_native_algorithm(algorithm, celestial), day)
  return lunar.year, lunar.month, lunar.day, lunar.is_leap


def lunar_to_gregorian(
  algorithm: LunarAlgorithm, year: int, month: int, day: int, is_leap: bool
) -> date:
  """农历年月日与闰月标志换公历标签；组合不存在时抛ValueError，内部故障原样传播。"""
  validate_lunar_date(algorithm, year, month, day, is_leap)
  import celestial_calendar as celestial

  lunar = celestial.LunarDate(year, month, day, is_leap)
  return celestial.lunar_to_gregorian(_native_algorithm(algorithm, celestial), lunar).to_date()


def lunar_year_info(
  algorithm: LunarAlgorithm, year: int
) -> tuple[date, int | None, tuple[int, ...]]:
  """农历年的首日、闰月与逐月长（闰月直接排在同名月之后）。"""
  _check_algorithm(algorithm)
  import celestial_calendar as celestial

  info = celestial.lunar_year_info(_native_algorithm(algorithm, celestial), year)
  return info.first_day.to_date(), info.leap_month, info.month_lengths


def validate_lunar_date(
  algorithm: LunarAlgorithm, year: int, month: int, day: int, is_leap: bool
) -> None:
  """核对农历年月日与闰月组合存在于所选算法；不存在或超范围显式失败。"""
  _check_algorithm(algorithm)
  for value, label in ((year, "农历年"), (month, "农历月"), (day, "农历日")):
    if type(value) is not int:
      raise TypeError(f"{label}须为整数，不接受 bool")
  if type(is_leap) is not bool:
    raise TypeError("闰月标志须为 bool")
  if year < _ALGORITHM_RANGE[algorithm][0] or year > _ALGORITHM_RANGE[algorithm][1]:
    raise ValueError(f"农历年{year}超出{LunarAlgorithm(algorithm).value}支持范围")
  if not 1 <= month <= 12:
    raise ValueError(f"农历月须在1至12之间：{month}")
  if day < 1:
    raise ValueError(f"农历{year}年{month}月没有第{day}日")
  _, leap_month, month_lengths = lunar_year_info(algorithm, year)
  if is_leap and month != leap_month:
    raise ValueError(f"农历{year}年不存在闰{month}月")
  # 月长元组把闰月插在同名月之后：闰月与其后的平月下标都要后移一位。
  effective_month = month + (
    1 if leap_month is not None and (month > leap_month or (is_leap and month == leap_month)) else 0
  )
  if effective_month > len(month_lengths):
    raise ValueError(f"农历{year}年不存在第{month}月")
  if day > month_lengths[effective_month - 1]:
    raise ValueError(f"农历{year}年{month}月没有第{day}日")


#: 闰秒表（TAI-UTC，秒），1972-01-01 起；2017-01-01 后恒为 37 秒。
#: 与 celestial-calendar 的 leap_second 表一致（IERS 闰秒数据，公开资料）。
_LEAP_SECOND_TABLE: Final[tuple[tuple[date, int], ...]] = (
  (date(1972, 1, 1), 10),
  (date(1972, 7, 1), 11),
  (date(1973, 1, 1), 12),
  (date(1974, 1, 1), 13),
  (date(1975, 1, 1), 14),
  (date(1976, 1, 1), 15),
  (date(1977, 1, 1), 16),
  (date(1978, 1, 1), 17),
  (date(1979, 1, 1), 18),
  (date(1980, 1, 1), 19),
  (date(1981, 7, 1), 20),
  (date(1982, 7, 1), 21),
  (date(1983, 7, 1), 22),
  (date(1985, 7, 1), 23),
  (date(1988, 1, 1), 24),
  (date(1990, 1, 1), 25),
  (date(1991, 1, 1), 26),
  (date(1992, 7, 1), 27),
  (date(1993, 7, 1), 28),
  (date(1994, 7, 1), 29),
  (date(1996, 1, 1), 30),
  (date(1997, 7, 1), 31),
  (date(1999, 1, 1), 32),
  (date(2006, 1, 1), 33),
  (date(2009, 1, 1), 34),
  (date(2012, 7, 1), 35),
  (date(2015, 7, 1), 36),
  (date(2017, 1, 1), 37),
)


def _delta_at(day: date) -> int:
  """UTC 民用日的闰秒数；2017-01-01 后恒为 37。"""
  value = 37
  for boundary, leap in _LEAP_SECOND_TABLE:
    if day < boundary:
      break
    value = leap
  return value


def _civil_to_jd(year: int, month: int, day: int, fraction: float) -> float:
  """公历（无历标）转儒略日；fraction 为当日小数。"""
  a = (14 - month) // 12
  y = year + 4800 - a
  m = month + 12 * a - 3
  julian = day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
  return julian + fraction - 0.5


def _jd_to_civil(jd: float) -> tuple[int, int, int, float]:
  """儒略日转公历年月日与当日小数（与 _civil_to_jd 互逆）。"""
  adjusted = jd + 0.5
  z = int(adjusted)
  fraction = adjusted - z
  if z < 2299161:
    a = float(z)
  else:
    alpha = (z - 1867216.25) // 36524.25
    a = z + 1 + alpha - alpha // 4
  b = a + 1524
  c = (b - 122.1) // 365.25
  d = int(365.25 * c)
  e = (b - d) // 30.6001
  day_float = b - d - int(30.6001 * e) + fraction
  day = int(day_float)
  month = int(e) - 1 if e < 14 else int(e) - 13
  year = int(c) - 4716 if month > 2 else int(c) - 4715
  return year, month, day, day_float - day


def _days_in_year(year: int) -> int:
  return 366 if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0 else 365


def _decimal_year(jd: float) -> float:
  """儒略日对应的十进制公历年，供 delta_t 取 ΔT。"""
  year, month, day, fraction = _jd_to_civil(jd)
  day_of_year = int(_civil_to_jd(year, month, 1, 0) - _civil_to_jd(year, 1, 1, 0)) + day
  return year + (day_of_year - 1 + fraction) / _days_in_year(year)


def _check_utc(utc: datetime) -> None:
  if type(utc) is not datetime:
    raise TypeError("UTC 时刻须为 datetime")
  if utc.tzinfo is None or utc.utcoffset() is None:
    raise ValueError("UTC 时刻须带时区")


def utc_to_ut1_jd(utc: datetime) -> float:
  """把 UTC 瞬间按 modelled-UT1 定义换算到 UT1 日数。

  TT=UTC+(ΔAT+32.184s)，UT1=TT-ΔT；ΔT 在 TT 处估一次，固定 DEFAULT(ALGO5)。
  该值与 celestial 的 chart_snapshot(jd_ut1) 在 1972-2099 网格上一致（亚毫秒级）。
  """
  _check_utc(utc)
  utc_utc = utc.astimezone(UTC)
  if utc_utc < datetime(1972, 1, 1, tzinfo=UTC):
    raise ValueError("UTC 早于1972-01-01的时刻须另定时标合同")
  fraction = (
    utc_utc.hour * 3600 + utc_utc.minute * 60 + utc_utc.second + utc_utc.microsecond / 1e6
  ) / 86400.0
  jd_utc = _civil_to_jd(utc_utc.year, utc_utc.month, utc_utc.day, fraction)
  tt = jd_utc + (_delta_at(utc_utc.date()) + 32.184) / 86400.0
  import celestial_calendar as celestial

  delta_t = celestial.delta_t(_decimal_year(tt), celestial.DeltaTModel.DEFAULT)
  return tt - delta_t / 86400.0


def lichun_jd(year: int) -> float:
  """农历（干支）年 year 的立春 UT1 时刻（UT1 日数）。

  jieqi_moment 返回的立春时刻为 UT1；返回日数可直接与 utc_to_ut1_jd 比较。
  立春在某公历年内，出生瞬间 ≥ 该年立春即归该干支年。
  """
  if type(year) is not int:
    raise TypeError("立春查询年份须为整数")
  import celestial_calendar as celestial

  moment = celestial.jieqi_moment(year, celestial.Jieqi.LICHUN)
  return celestial.ut1_to_jd(moment.moment_ut1)


def utc_civil(utc: datetime) -> tuple[int, int, int, float]:
  """UTC 瞬间转民用年月日与当日小数，供真太阳时换算。"""
  _check_utc(utc)
  utc_utc = utc.astimezone(UTC)
  fraction = (
    utc_utc.hour * 3600 + utc_utc.minute * 60 + utc_utc.second + utc_utc.microsecond / 1e6
  ) / 86400.0
  return utc_utc.year, utc_utc.month, utc_utc.day, fraction


def apparent_solar(utc: datetime, longitude_deg: float) -> tuple[int, int, int, float]:
  """当地真太阳钟的年月日与当日小数；经度为东经正。"""
  _check_utc(utc)
  import celestial_calendar as celestial

  year, month, day, fraction = utc_civil(utc)
  result = celestial.apparent_solar_time(
    celestial.CivilDateTime(year, month, day, fraction), longitude_deg
  )
  return result.year, result.month, result.day, result.fraction
