"""互相独立的三个口径；本模块定义选择，不执行历法运算。"""

from dataclasses import dataclass
from enum import StrEnum


class LeapMonthPolicy(StrEnum):
  """闰月归属，影响按月安星；不改变原始农历记录。"""

  NEXT_MONTH = "全月归下月"
  CURRENT_MONTH = "全月归本月"
  SPLIT_MONTH = "上半月归本月、下半月归下月"
  全月归下月 = NEXT_MONTH
  全月归本月 = CURRENT_MONTH
  上半月归本月下半月归下月 = SPLIT_MONTH


class DayRollover(StrEnum):
  """子时换日；早子时为00:00至01:00，晚子时为23:00至24:00。"""

  LATE_ZI_NEXT_DAY = "晚子时归次日"
  SAME_CIVIL_DAY = "早晚子时同日"
  晚子时归次日 = LATE_ZI_NEXT_DAY
  早晚子时同日 = SAME_CIVIL_DAY


class YearBoundary(StrEnum):
  """干支换年界线；选立春不意味着已完成时标转换。"""

  LUNAR_NEW_YEAR = "农历正月初一"
  LICHUN = "立春"
  农历正月初一 = LUNAR_NEW_YEAR
  立春 = LICHUN


@dataclass(frozen=True, slots=True, kw_only=True)
class ChartConfig:
  """三项均须显式给出；没有具名或静默默认值。"""

  leap_month_policy: LeapMonthPolicy
  day_rollover: DayRollover
  year_boundary: YearBoundary

  def __post_init__(self) -> None:
    for value, expected in (
      (self.leap_month_policy, LeapMonthPolicy),
      (self.day_rollover, DayRollover),
      (self.year_boundary, YearBoundary),
    ):
      if not isinstance(value, expected):
        raise TypeError(f"口径须为 {expected.__name__} 成员")
