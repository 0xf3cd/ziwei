"""三个独立历法口径与安星规则选择；本模块不执行计算。"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, TypeAlias, get_args


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


#: 独立口径枚举成员的并集，不提供默认口径。
PolicyOption: TypeAlias = LeapMonthPolicy | DayRollover | YearBoundary
#: 从PolicyOption派生的口径枚举类型，供校验与参考页共用。
POLICY_ENUMS: Final[tuple[type[StrEnum], ...]] = get_args(PolicyOption)


class TianmaRule(StrEnum):
  """天马查法；年马为具名默认，月马保留单源证据限度。"""

  YEAR_BRANCH = "年支天马"
  MONTH_BRANCH = "月支天马"
  年支天马 = YEAR_BRANCH
  月支天马 = MONTH_BRANCH


@dataclass(frozen=True, slots=True, kw_only=True)
class ChartConfig:
  """三个历法口径必填；天马默认按年支，可显式改为月支。"""

  leap_month_policy: LeapMonthPolicy
  day_rollover: DayRollover
  year_boundary: YearBoundary
  tianma_rule: TianmaRule = TianmaRule.YEAR_BRANCH

  def __post_init__(self) -> None:
    for value, expected in (
      (self.leap_month_policy, LeapMonthPolicy),
      (self.day_rollover, DayRollover),
      (self.year_boundary, YearBoundary),
      (self.tianma_rule, TianmaRule),
    ):
      if not isinstance(value, expected):
        raise TypeError(f"口径须为 {expected.__name__} 成员")
