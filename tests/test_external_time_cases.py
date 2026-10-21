"""外部分钟历书、经验均时差与手推组件组成的合成取证；不是完整外部原盘。"""

import sys
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from math import cos, pi, sin

import pytest

from ziwei.birth import Gender, GregorianBirthRecord, TimePrecision
from ziwei.bureau import WuxingJu
from ziwei.calendar import apparent_solar, lichun_jd, utc_to_ut1_jd
from ziwei.chart import create_chart
from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, TianmaRule, YearBoundary
from ziwei.decades import Direction
from ziwei.ganzhi import Dizhi
from ziwei.sihua import SihuaVariant
from ziwei.stars import Star
from ziwei.timezone import FixedOffset


@pytest.fixture(autouse=True)
def _unload_celestial() -> Iterator[None]:
  yield
  for name in tuple(sys.modules):
    if name.startswith("celestial_calendar"):
      del sys.modules[name]


@pytest.fixture
def choices() -> ChartConfig:
  return ChartConfig(
    leap_month_policy=LeapMonthPolicy.全月归本月,
    day_rollover=DayRollover.早晚子时同日,
    year_boundary=YearBoundary.农历正月初一,
    tianma_rule=TianmaRule.年支天马,
  )


def test_lichun_matches_hko_minute_with_conservative_window() -> None:
  """HKO 24SolarTerms_2024.xml第三行：02/04 16:27香港时间；不认证秒级边界。

  https://www.hko.gov.hk/en/gts/astronomy/data/files/24SolarTerms_2024.xml
  页面https://www.hko.gov.hk/en/gts/astronomy/Solar_Term.htm说明时区及资料来源。
  """
  minute = datetime(2024, 2, 4, 8, 27, tzinfo=UTC)
  assert abs(lichun_jd(2024) - utc_to_ut1_jd(minute)) * 86400 < 60


@pytest.mark.parametrize("clock", [time(16, 20), time(16, 35)])
@pytest.mark.parametrize("boundary", list(YearBoundary))
def test_hko_lichun_synthetic_components(
  choices: ChartConfig, clock: time, boundary: YearBoundary
) -> None:
  """HKO T2024e.txt给02/04为腊月廿五、02/10为正月初一。

  https://www.hko.gov.hk/en/gts/time/calendar/text/files/T2024e.txt
  两时刻同属申，距16:27分别7和8分钟。农历十二月从寅宫起正月，顺行11步到丑宫；
  申时从丑宫逆行8步得命宫巳，顺行8步得身宫酉。
  按五虎遁，癸年从甲寅顺数到丁巳，纳音属土，为土五局；甲年从丙寅顺数到己巳，纳音属木，为木三局。
  土五局廿五日：25除以5得商5，无需补数，从寅宫起数第5宫到午。
  木三局廿五日：补2至27，除以3得商9，从寅宫起数第9宫到戌；补数2为偶数，再顺行2步到子。
  """
  record = GregorianBirthRecord(
    birth_date=date(2024, 2, 4),
    birth_time=clock,
    time_precision=TimePrecision.分,
    timezone=FixedOffset(timedelta(hours=8)),
    gender=Gender.男,
  )
  chart = create_chart(
    record, replace(choices, year_boundary=boundary), sihua_variant=SihuaVariant.排命盘口诀转录
  )
  value = chart.calculation
  new = boundary is YearBoundary.立春 and clock == time(16, 35)
  assert (value.lunar_year, value.month, value.day, value.is_leap_month) == (2023, 12, 25, False)
  assert value.shichen is Dizhi.申
  assert str(value.year_ganzhi) == ("甲辰" if new else "癸卯")
  assert str(chart.palaces[0].ganzhi) == ("己巳" if new else "丁巳")
  assert chart.shengong is Dizhi.酉
  assert chart.bureau is (WuxingJu.木三局 if new else WuxingJu.土五局)
  assert "".join(p.dizhi.value for p in chart.stars[:14]) == (
    "子亥酉申未辰辰巳午未申酉戌寅" if new else "午巳卯寅丑戌戌亥子丑寅卯辰申"
  )
  positions = {p.star: p.dizhi for p in chart.stars}
  assert positions[Star.禄存] is (Dizhi.寅 if new else Dizhi.子)
  assert positions[Star.天马] is (Dizhi.寅 if new else Dizhi.巳)
  assert positions[Star.火星] is (Dizhi.戌 if new else Dizhi.巳)
  assert positions[Star.铃星] is Dizhi.午
  assert (chart.sihua.lu, chart.sihua.quan, chart.sihua.ke, chart.sihua.ji) == (
    (Star.廉贞, Star.破军, Star.武曲, Star.太阳)
    if new
    else (Star.破军, Star.巨门, Star.太阴, Star.贪狼)
  )
  assert chart.decades[0].start_age == (3 if new else 5)
  assert chart.decades[0].direction is (Direction.顺行 if new else Direction.逆行)
  assert "".join(p.dizhi.value for p in chart.decades) == (
    "巳午未申酉戌亥子丑寅卯辰" if new else "巳辰卯寅丑子亥戌酉申未午"
  )


def test_solar_clock_matches_corrected_spencer_for_selected_case() -> None:
  """pvlib校正Spencer71五项式，固定365与0.0000075；不声称全域60秒精度。

  https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.solarposition.equation_of_time_spencer71.html
  日序采用UTC小时的日中插值；公式不读celestial太阳位置。
  """
  utc = datetime(2024, 11, 2, 16, 20, tzinfo=UTC)
  doy_in = utc.timetuple().tm_yday + (utc.hour + utc.minute / 60 + utc.second / 3600 - 12) / 24
  angle = 2 * pi * (doy_in - 1) / 365
  eot_minutes = (
    1440
    / (2 * pi)
    * (
      0.0000075
      + 0.001868 * cos(angle)
      - 0.032077 * sin(angle)
      - 0.014615 * cos(2 * angle)
      - 0.040849 * sin(2 * angle)
    )
  )
  independent = utc.replace(tzinfo=None) + timedelta(hours=100 / 15, minutes=eot_minutes)
  assert independent.date() == date(2024, 11, 2)
  assert time(23, 15) < independent.time() < time(23, 18)
  year, month, day, fraction = apparent_solar(utc, 100.0)
  actual = datetime(year, month, day) + timedelta(days=fraction)
  assert abs((actual - independent).total_seconds()) < 60


@pytest.mark.parametrize("rollover", list(DayRollover))
def test_independent_solar_late_zi_components(choices: ChartConfig, rollover: DayRollover) -> None:
  """HKO T2024e.txt：11/02十月初二、11/03初三。独立太阳钟约前日23:16，离子时界约16分。

  农历十月从寅宫起正月，顺行9步到亥，子时不移动，命宫与身宫同亥。
  甲年亥宫为乙亥，纳音山头火，为火六局。
  初二补4至6，除以6得商1，从寅宫起数第1宫仍在寅；补数4为偶数，顺行4步到午。
  初三补3至6，除以6得商1仍在寅；补数3为奇数，逆行3步到亥。日标签能区分两种子时口径。
  """
  record = GregorianBirthRecord(
    birth_date=date(2024, 11, 3),
    birth_time=time(0, 20),
    time_precision=TimePrecision.分,
    timezone=FixedOffset(timedelta(hours=8)),
    gender=Gender.男,
    longitude_deg=100.0,
  )
  chart = create_chart(
    record, replace(choices, day_rollover=rollover), sihua_variant=SihuaVariant.排命盘口诀转录
  )
  rolled = rollover is DayRollover.晚子时归次日
  value = chart.calculation
  assert (value.lunar_year, value.month, value.day, value.is_leap_month) == (
    2024,
    10,
    3 if rolled else 2,
    False,
  )
  assert value.apparent_solar and value.day_rolled is rolled and value.shichen is Dizhi.子
  assert str(chart.palaces[0].ganzhi) == "乙亥" and chart.shengong is Dizhi.亥
  assert chart.bureau is WuxingJu.火六局
  assert "".join(p.dizhi.value for p in chart.stars[:14]) == (
    "亥戌申未午卯巳午未申酉戌亥卯" if rolled else "午巳卯寅丑戌戌亥子丑寅卯辰申"
  )
  assert chart.decades[0].start_age == 6 and chart.decades[0].direction is Direction.顺行
