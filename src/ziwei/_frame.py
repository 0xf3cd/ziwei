"""安星月份、命宫与五行局的包内共享推导，供命盘、安星与大限入口使用。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from ziwei.bureau import WuxingJu, bureau_of
from ziwei.ganzhi import Dizhi
from ziwei.palaces import effective_month, minggong_dizhi, palace_ganzhi

if TYPE_CHECKING:
  from ziwei.birth import CalculationInput


@dataclass(frozen=True, slots=True)
class ChartFrame:
  month: int
  minggong: Dizhi
  bureau: WuxingJu


def chart_frame(value: CalculationInput) -> ChartFrame:
  """推导安星月份、命宫与五行局；调用方先核输入类型与已知时辰，允许性别未知。"""
  month = effective_month(
    value.month, value.day, value.is_leap_month, value.config.leap_month_policy
  )
  minggong = minggong_dizhi(month, cast(Dizhi, value.shichen))
  return ChartFrame(month, minggong, bureau_of(palace_ganzhi(minggong, value.ganzhi_year)))
