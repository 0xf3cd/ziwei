"""从已有命盘查询指定虚岁的小限、童限与大限。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ziwei.decades import Decade
from ziwei.tongxian import Tongxian, TongxianBoundary, tongxian_at_age
from ziwei.xiaoxian import Xiaoxian, xiaoxian_at_age

if TYPE_CHECKING:
  from ziwei.chart import ZiweiChart


@dataclass(frozen=True, slots=True, kw_only=True)
class Yunxian:
  """同一虚岁的小限、童限与大限读数。"""

  xiaoxian: Xiaoxian
  tongxian: Tongxian
  decade: Decade | None

  def __post_init__(self) -> None:
    if not isinstance(self.xiaoxian, Xiaoxian) or not isinstance(self.tongxian, Tongxian):
      raise TypeError("运限须使用 Xiaoxian 与 Tongxian 读数")
    if self.decade is not None and not isinstance(self.decade, Decade):
      raise TypeError("大限须为 Decade 或 None")
    age = self.xiaoxian.age
    start = self.tongxian.ju.number
    if age != self.tongxian.age:
      raise ValueError("小限与童限须查询同一虚岁")
    if age > start + 119:
      raise ValueError("虚岁超出本命盘十二大限的范围")
    if age < start:
      if self.decade is not None:
        raise ValueError("首限开始前不得给出大限")
    elif (
      self.decade is None
      or not self.decade.start_age <= age <= self.decade.end_age
      or self.decade.start_age % 10 != start
    ):
      raise ValueError("大限区间须与虚岁及五行局一致")


def yunxian_at_age(chart: ZiweiChart, age: int, *, tongxian_boundary: TongxianBoundary) -> Yunxian:
  """查询已有命盘在指定虚岁的三套运限读数。

  小限始终给出，童限按tongxian_boundary选定的年龄范围给出。
  首大限开始前decade为None，超过盘内十二大限范围时抛ValueError。
  """
  from ziwei.chart import ZiweiChart

  if not isinstance(chart, ZiweiChart):
    raise TypeError("运限并读须使用 ZiweiChart")
  value = chart.calculation
  small = xiaoxian_at_age(value.year_ganzhi.dizhi, value.gender, age)
  child = tongxian_at_age(chart.palaces[0].dizhi, chart.bureau, age, boundary=tongxian_boundary)
  decade = next(
    (period for period in chart.decades if period.start_age <= age <= period.end_age), None
  )
  return Yunxian(xiaoxian=small, tongxian=child, decade=decade)
