"""celestial-calendar 的具体适配；导入本模块不初始化 celestial。

公开函数在函数体内 `import celestial_calendar`，包导入与知识查询不会加载原生历法库。
所选农历算法、支持范围与 celestial 版本随解析结果保存；超出支持范围或闰月/日组合
不存在时显式失败。

时标合同（UT1 / UTC）
----------------------

celestial 的节气时刻是 UT1，民用输入是 UTC 或固定偏移；本模块只比较同一时标下的值。

- 立春比较：出生瞬间换算到 UT1 日数（`utc_to_ut1_jd`），与立春 UT1 时刻
  （`lichun_jd`）直接比较，不直接比较钟面数值。
- 换算使用 celestial 的 UTC→TT→UT1 出口，ΔT 固定使用 ALGO5。
- UTC转UT1与民用时刻解析均拒绝1972年以前的UTC瞬间；无需瞬间的纯民用排盘不受此下界限制。

真太阳时（apparent solar time）
--------------------------------

`apparent_solar` 调用 celestial 的 `apparent_solar_time`，以 UTC 民用时刻与东经经度换算
当地真太阳钟，返回年月日与当日小数。此处直接传入 UTC 钟面值，不修正 UT1-UTC 的亚秒差距；
取时辰时通常不影响。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from enum import StrEnum
from math import isfinite
from typing import Any, Final

from ziwei.timezone import _require_modern_utc


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

LICHUN_DATE_YEAR_RANGE: Final = (1972, 2200)
"""立春日期查询支持的公历年份，含端点；1972受UTC下界限制，2200是项目选定的末边界年份。"""

_EAST_EIGHT: Final = timezone(timedelta(hours=8))


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

  解析层先选民用钟或真太阳钟的日期，再应用子时换日，传入最终取用的日期标签。
  超出算法支持范围或日期不可表示时
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
      raise TypeError(f"{label}不接受 bool" if isinstance(value, bool) else f"{label}须为整数")
  if type(is_leap) is not bool:
    raise TypeError("闰月标志须为 bool")
  if year < _ALGORITHM_RANGE[algorithm][0] or year > _ALGORITHM_RANGE[algorithm][1]:
    raise ValueError(f"农历年{year}超出{LunarAlgorithm(algorithm).value}支持范围")
  if not 1 <= month <= 12:
    raise ValueError(f"农历月须在1至12之间：{month}")
  label = f"农历{year}年{'闰' if is_leap else '平'}{month}月"
  if day < 1:
    raise ValueError(f"{label}没有第{day}日")
  _, leap_month, month_lengths = lunar_year_info(algorithm, year)
  if is_leap and month != leap_month:
    raise ValueError(f"农历{year}年不存在闰{month}月")
  # 月长元组把闰月插在同名月之后：闰月与其后的平月下标都要后移一位。
  effective_month = month + (
    1 if leap_month is not None and (month > leap_month or (is_leap and month == leap_month)) else 0
  )
  if effective_month > len(month_lengths):
    raise ValueError(f"{label}不存在")
  if day > month_lengths[effective_month - 1]:
    raise ValueError(f"{label}没有第{day}日")


def _check_utc(utc: datetime) -> None:
  if type(utc) is not datetime:
    raise TypeError("UTC 时刻须为 datetime")
  if utc.tzinfo is None or utc.utcoffset() is None:
    raise ValueError("UTC 时刻须带时区")


def utc_to_ut1_jd(utc: datetime) -> float:
  """把 UTC 瞬间按 modelled-UT1 定义换算到 UT1 日数。

  上游 UTC→TT 使用闰秒表，TT→UT1 的 ΔT 固定为 ALGO5。
  下界按 UTC 瞬间判断，只支持1972年起；表末行之后沿用最后已知偏移。
  Python datetime不能表达23:59:60，本函数不接受闰秒本秒。
  """
  _check_utc(utc)
  utc_utc = utc.astimezone(UTC)
  _require_modern_utc(utc_utc)
  import celestial_calendar as celestial

  jde_tt = celestial.utc_to_jde(celestial.CivilDateTime(*utc_civil(utc_utc)))
  return celestial.ut1_to_jd(celestial.jde_to_ut1(jde_tt))


def lichun_jd(year: int) -> float:
  """公历年year内的立春UT1时刻（UT1日数）。

  jieqi_moment 返回的立春时刻为 UT1；返回日数可直接与 utc_to_ut1_jd 比较。
  立春在某公历年内，出生瞬间 ≥ 该年立春即归该干支年。
  """
  if type(year) is not int:
    raise TypeError("立春查询年份须为整数")
  import celestial_calendar as celestial

  moment = celestial.jieqi_moment(year, celestial.Jieqi.LICHUN)
  return celestial.ut1_to_jd(moment.moment_ut1)


def _midnight_ut1(day: date) -> float:
  return utc_to_ut1_jd(datetime(day.year, day.month, day.day, tzinfo=_EAST_EIGHT))


def lichun_date(year: int) -> date:
  """公历年内立春所在的UTC+08日期，按现有modelled-UT1/UTC合同换算。

  支持年份见LICHUN_DATE_YEAR_RANGE。返回整日标签，使用utc_to_ut1_jd中的闰秒与ΔT模型。
  """
  if type(year) is not int:
    raise TypeError(
      "立春日期查询年份不接受 bool" if isinstance(year, bool) else "立春日期查询年份须为整数"
    )
  first, last = LICHUN_DATE_YEAR_RANGE
  if not first <= year <= last:
    raise ValueError(f"立春日期查询年份须在{first}至{last}之间")
  target = lichun_jd(year)
  if not isfinite(target):
    raise ValueError("立春UT1日数须为有限数")
  selected = date(year, 2, 4)
  while target < _midnight_ut1(selected):
    selected -= timedelta(days=1)
  while target >= _midnight_ut1(selected + timedelta(days=1)):
    selected += timedelta(days=1)
  return selected


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
