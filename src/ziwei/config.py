"""配置闰月归属、子时换日、换年界线及天马查法；本模块只保存选择，不执行计算。"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, TypeAlias, get_args


class LeapMonthPolicy(StrEnum):
  """选择安星时把闰月算作哪个月，不改变原始农历记录。

  可以全月按本月、全月按下月，或初一至十五按本月、十六日起按下月计算。
  """

  NEXT_MONTH = "全月归下月"
  CURRENT_MONTH = "全月归本月"
  SPLIT_MONTH = "上半月归本月、下半月归下月"
  全月归下月 = NEXT_MONTH
  全月归本月 = CURRENT_MONTH
  上半月归本月下半月归下月 = SPLIT_MONTH


class DayRollover(StrEnum):
  """选择晚子时是否改用次日的农历日期。

  早子时为00:00至01:00，晚子时为23:00至24:00；两个区间均含起点、不含终点。
  早晚子时同日时保留当日日期；晚子时归次日时，23:00起改用次日日期。
  """

  LATE_ZI_NEXT_DAY = "晚子时归次日"
  SAME_CIVIL_DAY = "早晚子时同日"
  晚子时归次日 = LATE_ZI_NEXT_DAY
  早晚子时同日 = SAME_CIVIL_DAY


class YearBoundary(StrEnum):
  """选择干支纪年在农历正月初一还是立春时更换。

  本枚举只记录选择。选择立春时，解析层仍须把出生时刻与立春时刻换算到同一时标后比较。
  """

  LUNAR_NEW_YEAR = "农历正月初一"
  LICHUN = "立春"
  农历正月初一 = LUNAR_NEW_YEAR
  立春 = LICHUN


#: 闰月归属、子时换日和换年界线三个枚举的联合类型；这三项均无默认值。
PolicyOption: TypeAlias = LeapMonthPolicy | DayRollover | YearBoundary
#: 从PolicyOption取得这三个枚举的类型，供输入校验和参考页共用。
POLICY_ENUMS: Final[tuple[type[StrEnum], ...]] = get_args(PolicyOption)


class TianmaRule(StrEnum):
  """选择按年支还是农历生月对应的地支安天马。

  默认按年支；也可选择月支天马，来源与同文限度见知识目录。闰月用哪个月由LeapMonthPolicy决定。
  """

  YEAR_BRANCH = "年支天马"
  MONTH_BRANCH = "月支天马"
  年支天马 = YEAR_BRANCH
  月支天马 = MONTH_BRANCH


@dataclass(frozen=True, slots=True, kw_only=True)
class ChartConfig:
  """保存历法口径与天马查法。

  构造时必须分别指定闰月归属、子时换日和换年界线，这三项没有默认值。
  天马查法可以省略，默认按年支安天马，也可改为按农历生月对应的地支安天马。
  """

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
