"""组合不可变本命盘；构造器核对组件关系，不重新执行历法或时区解析。"""

from dataclasses import dataclass
from datetime import datetime, time
from math import isfinite
from typing import TypeVar, cast

from ziwei.birth import BirthRecord, CalculationInput, LunarBirthRecord
from ziwei.bureau import WuxingJu
from ziwei.calendar import LunarAlgorithm
from ziwei.config import ChartConfig, DayRollover, YearBoundary
from ziwei.decades import Decade, place_decades
from ziwei.ganzhi import Dizhi
from ziwei.palaces import (
  Palace,
  _chart_frame,
  shengong_dizhi,
  twelve_palaces,
)
from ziwei.resolver import DEFAULT_LUNAR_ALGORITHM, resolve
from ziwei.sihua import SihuaResult, SihuaVariant, shengnian_sihua
from ziwei.stars import StarPlacement, place_stars

_T = TypeVar("_T")


def _check_component_sequence(
  actual: tuple[_T, ...], expected: tuple[_T, ...], component: str
) -> None:
  if len(actual) != len(expected):
    raise ValueError(f"{component}数量不符：应为{len(expected)}，实际为{len(actual)}")
  for index, (item, wanted) in enumerate(zip(actual, expected, strict=True)):
    if item != wanted:
      raise ValueError(f"{component}[{index}]与计算输入不符：应为{wanted!r}，实际为{item!r}")


def _check_calculation(value: CalculationInput) -> None:
  """核完整盘计算输入的一致性，不读取历法或时区数据。"""
  value.require_complete()
  for jd in (value.ut1_jd, value.lichun_jd):
    if jd is not None and not isfinite(jd):
      raise ValueError("UT1 日数须为有限值")
  record = value.record
  if isinstance(record, LunarBirthRecord):
    if record.longitude_deg is not None or value.config.year_boundary is YearBoundary.立春:
      raise ValueError("农历记录不能提供真太阳时或立春比较所需瞬间")
    if record.shichen is Dizhi.子 and value.config.day_rollover is DayRollover.晚子时归次日:
      raise ValueError("农历子时记录无法区分早晚子时")
    if (
      (value.lunar_year, value.month, value.day, value.is_leap_month, value.shichen)
      != (record.year, record.month, record.day, record.is_leap_month, record.shichen)
      or value.apparent_solar
      or value.day_rolled
    ):
      raise ValueError("农历解析值须保全原始农历记录")
  else:
    need_instant = (
      value.config.year_boundary is YearBoundary.立春 or record.longitude_deg is not None
    )
    if need_instant != (value.resolved_time is not None):
      raise ValueError("已解析时刻的存在性须与公历记录和口径一致")
    if value.apparent_solar != (record.longitude_deg is not None):
      raise ValueError("真太阳时路径须与公历记录的经度选择一致")
    if value.resolved_time is not None and (
      value.resolved_time.local_time
      != datetime.combine(record.birth_date, cast(time, record.birth_time))
      or value.resolved_time.zone != record.timezone
    ):
      raise ValueError("已解析时刻须对应原始钟面和时区选择")
    if not value.apparent_solar:
      if value.shichen is not record.shichen:
        raise ValueError("民用路径的解析时辰须与原始钟点一致")
      rolled = (
        record.birth_time is not None
        and record.birth_time.hour == 23
        and value.config.day_rollover is DayRollover.晚子时归次日
      )
      if value.day_rolled != rolled:
        raise ValueError("晚子时顺延须与民用钟点和换日口径一致")
    if value.config.year_boundary is YearBoundary.立春:
      before = cast(float, value.ut1_jd) < cast(float, value.lichun_jd)
      if value.ganzhi_year != record.birth_date.year - int(before):
        raise ValueError("干支纪年须与已存立春比较关系一致")
  if isinstance(record, LunarBirthRecord) and value.resolved_time is not None:
    raise ValueError("农历记录不得携带已解析民用时刻")


@dataclass(frozen=True, slots=True, kw_only=True)
class ZiweiChart:
  """完整本命盘，按规则表与算术核对组件，不重做历法或时区解析。

  宫位按宫名序，星曜按Star枚举顺序，大限按起限先后（自命宫起，随顺逆）；序列复制为元组。
  直接构造不重新核验calculation中的公历与农历对应、UT1或IANA偏移；从原始记录排盘使用create_chart。
  """

  calculation: CalculationInput
  palaces: tuple[Palace, ...]
  shengong: Dizhi
  bureau: WuxingJu
  stars: tuple[StarPlacement, ...]
  sihua: SihuaResult
  decades: tuple[Decade, ...]

  def __post_init__(self) -> None:
    if not isinstance(self.calculation, CalculationInput):
      raise TypeError("命盘须使用 CalculationInput")
    if not isinstance(self.shengong, Dizhi) or not isinstance(self.bureau, WuxingJu):
      raise TypeError("身宫与五行局须使用领域枚举")
    if not isinstance(self.sihua, SihuaResult):
      raise TypeError("四化须使用 SihuaResult")
    for name, kind in (("palaces", Palace), ("stars", StarPlacement), ("decades", Decade)):
      items = tuple(getattr(self, name))
      if any(not isinstance(item, kind) for item in items):
        raise TypeError(f"{name}须使用对应的领域记录")
      object.__setattr__(self, name, items)
    value = self.calculation
    _check_calculation(value)
    frame = _chart_frame(value)
    shichen = cast(Dizhi, value.shichen)
    _check_component_sequence(
      self.palaces, twelve_palaces(frame.minggong, value.year_ganzhi.tiangan), "十二宫"
    )
    shengong = shengong_dizhi(frame.month, shichen)
    if self.shengong is not shengong:
      raise ValueError(f"身宫与计算输入不符：应为{shengong.value}，实际为{self.shengong.value}")
    if self.bureau is not frame.bureau:
      raise ValueError(f"五行局与命宫干支不符：应为{frame.bureau.value}，实际为{self.bureau.value}")
    _check_component_sequence(self.stars, place_stars(value), "星位")
    sihua = shengnian_sihua(value, self.sihua.variant)
    if self.sihua != sihua:
      raise ValueError(f"四化与解析后的生年干及规则不符：应为{sihua!r}，实际为{self.sihua!r}")
    _check_component_sequence(self.decades, place_decades(value), "大限")


def create_chart(
  record: BirthRecord,
  config: ChartConfig,
  *,
  sihua_variant: SihuaVariant,
  lunar_algorithm: LunarAlgorithm = DEFAULT_LUNAR_ALGORITHM,
) -> ZiweiChart:
  """解析原始记录并组合完整盘；时辰、性别或所请求口径不可用时整次失败。"""
  value = resolve(record, config, lunar_algorithm)
  value.require_complete()
  frame = _chart_frame(value)
  shichen = cast(Dizhi, value.shichen)
  return ZiweiChart(
    calculation=value,
    palaces=twelve_palaces(frame.minggong, value.year_ganzhi.tiangan),
    shengong=shengong_dizhi(frame.month, shichen),
    bureau=frame.bureau,
    stars=place_stars(value),
    sihua=shengnian_sihua(value, sihua_variant),
    decades=place_decades(value),
  )
