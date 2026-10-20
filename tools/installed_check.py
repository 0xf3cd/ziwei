"""隔离验证已安装的包。"""

import sys
from datetime import UTC, date, datetime, time, timedelta
from importlib import import_module
from importlib.metadata import distribution
from pathlib import Path

import ziwei
from ziwei.birth import CalculationInput, Gender, GregorianBirthRecord, TimePrecision
from ziwei.calendar import LunarAlgorithm
from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, YearBoundary
from ziwei.ganzhi import Dizhi
from ziwei.knowledge import load_catalog
from ziwei.knowledge.model import PremiseStatus
from ziwei.timezone import AmbiguousTimeError, IanaTimezone, NonexistentTimeError


def check_inputs() -> None:
  """消费已安装的出生输入与时区数据，不触发历法初始化。"""
  record = GregorianBirthRecord(
    birth_date=date(1988, 7, 1),
    birth_time=time(12),
    time_precision=TimePrecision.分,
    timezone=IanaTimezone("Asia/Shanghai"),
    gender=Gender.男,
  )
  result = record.resolve_time()
  dependency = distribution("tzdata")
  if f"tzdata=={dependency.version}" not in (distribution("ziwei").requires or ()):
    raise ValueError("Installed timezone data differs from the declared pin")
  if result.data is None or result.data.package_version != dependency.version:
    raise ValueError("Timezone data provenance is missing or inconsistent")
  if result.data.iana_version != import_module("tzdata").IANA_VERSION:
    raise ValueError("Timezone IANA release differs from the installed data")
  if result.offset != timedelta(hours=9) or result.utc != datetime(1988, 7, 1, 3, tzinfo=UTC):
    raise ValueError("Installed timezone data did not resolve Shanghai summer time")
  for birth_date, clock, error in (
    (date(1988, 4, 17), time(2, 30), NonexistentTimeError),
    (date(1988, 9, 11), time(1, 30), AmbiguousTimeError),
  ):
    try:
      GregorianBirthRecord(
        birth_date=birth_date,
        birth_time=clock,
        time_precision=TimePrecision.分,
        timezone=IanaTimezone("Asia/Shanghai"),
        gender=Gender.男,
      ).resolve_time()
    except error:
      pass
    else:
      raise ValueError("Installed timezone validation accepted an unresolved local time")
  choices = ChartConfig(
    leap_month_policy=LeapMonthPolicy.全月归本月,
    day_rollover=DayRollover.晚子时归次日,
    year_boundary=YearBoundary.农历正月初一,
  )
  # 合成计算输入只检验消费合同，不作为历法转换或参考盘例。
  value = CalculationInput(
    record=record,
    lunar_year=2000,
    month=1,
    day=1,
    is_leap_month=False,
    shichen=Dizhi.子,
    ganzhi_year=2000,
    config=choices,
    lunar_algorithm=LunarAlgorithm.ALGO3,
    lunar_algorithm_version="0.8.0",
    apparent_solar=False,
    day_rolled=False,
    ut1_jd=None,
    lichun_jd=None,
  )
  value.require_complete()


def check_calendar() -> None:
  """消费已安装包的历法适配与安星基础；会加载 celestial 原生库，须在隔离检查之后。"""
  from ziwei.bureau import WuxingJu, bureau_of
  from ziwei.calendar import celestial_version
  from ziwei.palaces import effective_month, minggong_dizhi, palace_ganzhi
  from ziwei.resolver import resolve

  if celestial_version() != "0.8.0":
    raise ValueError("Installed celestial-calendar version differs from the declared pin")
  record = GregorianBirthRecord(
    birth_date=date(1988, 7, 1),
    birth_time=time(12),
    time_precision=TimePrecision.分,
    timezone=IanaTimezone("Asia/Shanghai"),
    gender=Gender.男,
  )
  choices = ChartConfig(
    leap_month_policy=LeapMonthPolicy.全月归本月,
    day_rollover=DayRollover.晚子时归次日,
    year_boundary=YearBoundary.农历正月初一,
  )
  value = resolve(record, choices)
  if (value.lunar_year, value.month, value.day) != (1988, 5, 18):
    raise ValueError("Installed resolver produced a wrong lunar date")
  if str(value.year_ganzhi) != "戊辰":
    raise ValueError("Installed resolver produced a wrong ganzhi year")
  effective = effective_month(
    value.month, value.day, value.is_leap_month, choices.leap_month_policy
  )
  if value.shichen is None or minggong_dizhi(effective, value.shichen) != Dizhi.子:
    raise ValueError("Installed palace rule produced a wrong minggong")
  if bureau_of(palace_ganzhi(Dizhi.子, value.ganzhi_year)) is not WuxingJu.JIN_SI:
    raise ValueError("Installed bureau rule produced a wrong wuxingju")


def main(expected_version: str) -> None:
  """检查身份、导入路径及原生历法库隔离。"""
  metadata = distribution("ziwei")
  origin = Path(str(ziwei.__file__)).resolve()
  if not origin.is_relative_to(Path(sys.prefix).resolve()):
    raise ValueError("Imported ziwei from outside the consumer environment")
  if metadata.version != expected_version:
    raise ValueError("Installed version differs from the built version")
  if not origin.with_name("py.typed").is_file():
    raise ValueError("Installed package is missing py.typed")
  check_knowledge()
  check_inputs()
  if any(
    name == "celestial_calendar" or name.startswith("celestial_calendar.") for name in sys.modules
  ):
    raise ValueError("Import initialized the calendar adapter")
  check_calendar()
  print(f"Installed ziwei {metadata.version}; optimized={sys.flags.optimize}")


def check_knowledge() -> None:
  """消费安装包中的语料、别名、前提与原文引用，不只检查导入成功。"""
  catalog = load_catalog()
  if not catalog.version or not catalog.find("天馬") or len(catalog.find("庚干四化")) != 3:
    raise ValueError("Installed knowledge corpus or aliases are incomplete")
  pending = catalog.filter_entries(premise_status=PremiseStatus.待定)
  if not pending or any(item.chart_match != "未评估" or not item.alternatives for item in pending):
    raise ValueError("Installed knowledge lost unresolved premises")
  references = catalog.references("entry.tianma.year-branch")
  if not references or references[0].quote != "论本生年支":
    raise ValueError("Installed knowledge citation differs from its source")


if __name__ == "__main__":
  main(sys.argv[1])
