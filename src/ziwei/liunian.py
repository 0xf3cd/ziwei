"""按目标年支定位流年命宫，并分别按初一或立春日期确定纪年。"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Literal

from ziwei.ganzhi import Dizhi, Ganzhi, year_ganzhi

if TYPE_CHECKING:
  from ziwei.calendar import LunarAlgorithm

LIUNIAN_MINGGONG_RULE_ID: Final = "variant.liunian.year-branch"
"""目标流年地支落同支宫的规则标识。"""


class LiunianBoundary(StrEnum):
  """流年日期查询的年界选项。"""

  LUNAR_NEW_YEAR = "正月初一日期"
  LICHUN_DATE = "立春日期"
  正月初一日期 = LUNAR_NEW_YEAR
  立春日期 = LICHUN_DATE

  @property
  def rule_id(self) -> str:
    """所选日期年界的规则标识。"""
    return {
      LiunianBoundary.LUNAR_NEW_YEAR: "variant.liunian.lunar-new-year",
      LiunianBoundary.LICHUN_DATE: "variant.liunian.lichun-date",
    }[self]


def liunian_minggong(ganzhi_year: int) -> Dizhi:
  """已确定纪年1至9999的流年命宫地支。"""
  return year_ganzhi(ganzhi_year).dizhi


def _checked_algorithm(
  boundary: LiunianBoundary, algorithm: LunarAlgorithm | None
) -> LunarAlgorithm | None:
  from ziwei.calendar import LunarAlgorithm

  if not isinstance(boundary, LiunianBoundary):
    raise TypeError("流年年界须为 LiunianBoundary 成员")
  if boundary is LiunianBoundary.LUNAR_NEW_YEAR:
    if not isinstance(algorithm, LunarAlgorithm):
      raise TypeError("正月初一日期须显式指定 LunarAlgorithm")
    return algorithm
  if boundary is LiunianBoundary.LICHUN_DATE:
    if algorithm is not None:
      raise TypeError("立春日期不使用农历算法")
    return None
  raise ValueError("尚未实现流年年界")


def _supported_year_range(algorithm: LunarAlgorithm | None) -> tuple[int, int]:
  from ziwei.calendar import LICHUN_DATE_YEAR_RANGE, supported_lunar_year_range

  if algorithm is not None:
    return supported_lunar_year_range(algorithm)
  first, final_boundary = LICHUN_DATE_YEAR_RANGE
  return first, final_boundary - 1


@dataclass(frozen=True, slots=True, kw_only=True)
class LiunianYear:
  """按日换年的干支年区间，start含、end不含；构造只校验字段关系，不重算历法。"""

  ganzhi_year: int
  boundary: LiunianBoundary
  start: datetime.date
  end: datetime.date
  lunar_algorithm: LunarAlgorithm | None
  celestial_version: str
  supported_year_range: tuple[int, int] = field(init=False)
  precision: Literal["date"] = field(init=False, default="date")

  def __post_init__(self) -> None:
    year_ganzhi(self.ganzhi_year)
    algorithm = _checked_algorithm(self.boundary, self.lunar_algorithm)
    supported = _supported_year_range(algorithm)
    if not supported[0] <= self.ganzhi_year <= supported[1]:
      raise ValueError("干支年超出所选流年年界支持范围")
    if type(self.start) is not datetime.date or type(self.end) is not datetime.date:
      raise TypeError("流年区间端点须为 date，不接受 datetime")
    if (
      self.start >= self.end
      or self.start.year != self.ganzhi_year
      or self.end.year != self.ganzhi_year + 1
    ):
      raise ValueError("流年区间须始于所归纪年并终于下一纪年")
    if not isinstance(self.celestial_version, str):
      raise TypeError("celestial版本须为字符串")
    if not self.celestial_version.strip():
      raise ValueError("celestial版本不可为空")
    object.__setattr__(self, "supported_year_range", tuple(supported))

  @property
  def year_ganzhi(self) -> Ganzhi:
    """所归纪年的干支。"""
    return year_ganzhi(self.ganzhi_year)

  @property
  def minggong(self) -> Dizhi:
    """流年命宫地支。"""
    return liunian_minggong(self.ganzhi_year)

  @property
  def rule_id(self) -> str:
    """流年命宫定位的规则标识。"""
    return LIUNIAN_MINGGONG_RULE_ID

  @property
  def date_basis(self) -> str:
    """区间端点的日期基准；农历标签的具体基准见lunar_algorithm。"""
    if self.boundary is LiunianBoundary.LICHUN_DATE:
      return "UTC+08"
    return "所选农历算法日期标签"


def liunian_on_date(
  day: datetime.date,
  *,
  boundary: LiunianBoundary,
  lunar_algorithm: LunarAlgorithm | None = None,
) -> LiunianYear:
  """按显式年界查询日期所归的干支年及完整区间。

  初一路径必须指定农历算法，输入为该算法基准的公历日期标签；立春路径只收UTC+08日期，
  不接受农历算法。两个路径都拒绝datetime。范围外抛ValueError，原生历法故障原样传播。
  """
  from ziwei.calendar import (
    celestial_version,
    gregorian_to_lunar,
    lichun_date,
    lunar_year_info,
  )

  if type(day) is not datetime.date:
    raise TypeError("流年日期须为 date，不接受 datetime")
  algorithm = _checked_algorithm(boundary, lunar_algorithm)
  if algorithm is not None:
    year, _, _, _ = gregorian_to_lunar(algorithm, day)
    start, _, lengths = lunar_year_info(algorithm, year)
    end = start + datetime.timedelta(days=sum(lengths))
  else:
    first, last = _supported_year_range(algorithm)
    if not first <= day.year <= last + 1:
      raise ValueError("日期超出立春流年支持范围")
    current_boundary = lichun_date(day.year)
    year = day.year if day >= current_boundary else day.year - 1
    if not first <= year <= last:
      raise ValueError("日期超出立春流年支持范围")
    start = current_boundary if year == day.year else lichun_date(year)
    end = lichun_date(year + 1) if year == day.year else current_boundary
  return LiunianYear(
    ganzhi_year=year,
    boundary=boundary,
    start=start,
    end=end,
    lunar_algorithm=algorithm,
    celestial_version=celestial_version(),
  )
