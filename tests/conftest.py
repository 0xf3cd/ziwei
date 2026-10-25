"""整盘测试的合成输入，以及外部1954例的28星期望。"""

import sys
from collections.abc import Iterator
from datetime import date, time

import pytest

from ziwei.birth import Gender, GregorianBirthRecord, LunarBirthRecord, TimePrecision
from ziwei.chart import ZiweiChart, create_chart
from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, TianmaRule, YearBoundary
from ziwei.ganzhi import Dizhi
from ziwei.sihua import SihuaVariant
from ziwei.stars import Star
from ziwei.timezone import IanaTimezone


@pytest.fixture
def unload_celestial() -> Iterator[None]:
  """只清理显式选用模块的历法导入，避免污染安装入口的同进程导入隔离检查。"""
  yield
  for name in tuple(sys.modules):
    if name.startswith("celestial_calendar"):
      del sys.modules[name]


@pytest.fixture
def chart_choices() -> ChartConfig:
  return ChartConfig(
    leap_month_policy=LeapMonthPolicy.全月归本月,
    day_rollover=DayRollover.早晚子时同日,
    year_boundary=YearBoundary.农历正月初一,
    tianma_rule=TianmaRule.月支天马,
  )


@pytest.fixture
def lunar_chart(chart_choices: ChartConfig) -> ZiweiChart:
  return create_chart(
    LunarBirthRecord(
      year=1954,
      month=9,
      day=7,
      is_leap_month=False,
      shichen=Dizhi.子,
      gender=Gender.男,
      source="匿名例甲：论坛转录《排命盘口诀》",
    ),
    chart_choices,
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )


@pytest.fixture
def civil_chart(chart_choices: ChartConfig) -> ZiweiChart:
  from dataclasses import replace

  return create_chart(
    GregorianBirthRecord(
      birth_date=date(1988, 9, 11),
      birth_time=time(1, 30, 0, 123456),
      time_precision=TimePrecision.微秒,
      timezone=IanaTimezone("Asia/Shanghai", fold=1),
      gender=Gender.女,
      place="江苏省",
      source="合成夏令时重叠例",
    ),
    replace(chart_choices, year_boundary=YearBoundary.立春),
    sihua_variant=SihuaVariant.王亭之讲义转录,
  )


@pytest.fixture
def expected_1954() -> dict[Star, Dizhi]:
  """2007论坛《排命盘口诀》排命盘举例第1至13步中已实现的28星；原著/底本未核。"""
  return {
    Star.紫微: Dizhi.戌,
    Star.天机: Dizhi.酉,
    Star.太阳: Dizhi.未,
    Star.武曲: Dizhi.午,
    Star.天同: Dizhi.巳,
    Star.廉贞: Dizhi.寅,
    Star.天府: Dizhi.午,
    Star.太阴: Dizhi.未,
    Star.贪狼: Dizhi.申,
    Star.巨门: Dizhi.酉,
    Star.天相: Dizhi.戌,
    Star.天梁: Dizhi.亥,
    Star.七杀: Dizhi.子,
    Star.破军: Dizhi.辰,
    Star.文昌: Dizhi.戌,
    Star.文曲: Dizhi.辰,
    Star.火星: Dizhi.丑,
    Star.铃星: Dizhi.卯,
    Star.地空: Dizhi.亥,
    Star.地劫: Dizhi.亥,
    Star.左辅: Dizhi.子,
    Star.右弼: Dizhi.寅,
    Star.天马: Dizhi.申,
    Star.禄存: Dizhi.寅,
    Star.擎羊: Dizhi.卯,
    Star.陀罗: Dizhi.丑,
    Star.天魁: Dizhi.丑,
    Star.天钺: Dizhi.未,
  }
