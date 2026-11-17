"""不经pytest断言重写，在普通与-O模式下核公开输入校验。

程序故意传入错误类型来检查运行时校验，所以不做静态类型检查。
"""

# mypy: ignore-errors
# ruff: noqa: I001

from datetime import date, datetime, time, timedelta
from ziwei.birth import (
  GregorianBirthRecord,
  LunarBirthRecord,
  CalculationInput,
  TimePrecision,
  Gender,
)
from ziwei.bureau import bureau_of
from ziwei.calendar import (
  LunarAlgorithm,
  supported_lunar_year_range,
  utc_to_ut1_jd,
  validate_lunar_date,
)
from ziwei.config import ChartConfig, LeapMonthPolicy, DayRollover, YearBoundary
from ziwei.ganzhi import Dizhi, Ganzhi, year_ganzhi
from ziwei.chart import LiunianView, liunian_view
from ziwei.liunian import LiunianStars, liunian_stars
from ziwei.palaces import minggong_dizhi, month_palace_index
from ziwei.resolver import resolve
from ziwei.timezone import IanaTimezone, FixedOffset, resolve_civil_time
from ziwei.stars import lucun_yangtuo_dizhi

config = ChartConfig(
  leap_month_policy=LeapMonthPolicy.全月归本月,
  day_rollover=DayRollover.晚子时归次日,
  year_boundary=YearBoundary.立春,
)
plain = ChartConfig(
  leap_month_policy=LeapMonthPolicy.全月归本月,
  day_rollover=DayRollover.晚子时归次日,
  year_boundary=YearBoundary.农历正月初一,
)
record = LunarBirthRecord(
  year=2000, month=4, day=1, is_leap_month=False, shichen=None, gender=Gender.未知
)
unknown_time = LunarBirthRecord(
  year=2000, month=4, day=1, is_leap_month=False, shichen=None, gender=Gender.男
)
complete = dict(
  lunar_algorithm=LunarAlgorithm.ALGO3,
  lunar_algorithm_version="0.8.0",
  apparent_solar=False,
  day_rolled=False,
  ut1_jd=None,
  lichun_jd=None,
)
cases = [
  lambda: year_ganzhi(True),
  lambda: year_ganzhi(0),
  lambda: Ganzhi.from_str("甲丑"),
  lambda: ChartConfig(
    leap_month_policy=None, day_rollover=config.day_rollover, year_boundary=config.year_boundary
  ),
  lambda: IanaTimezone("../UTC"),
  lambda: IanaTimezone("UTC", True),
  lambda: FixedOffset(timedelta(days=1)),
  lambda: resolve_civil_time(datetime(1988, 4, 17, 2, 30), IanaTimezone("Asia/Shanghai")),
  lambda: resolve_civil_time(datetime(1988, 9, 11, 1, 30), IanaTimezone("Asia/Shanghai")),
  lambda: GregorianBirthRecord(
    birth_date=date(2000, 1, 1),
    birth_time=time(12),
    time_precision=TimePrecision.分,
    timezone=FixedOffset(timedelta(0)),
    gender="男",
  ),
  lambda: LunarBirthRecord(
    year=True, month=4, day=1, is_leap_month=False, shichen=None, gender=Gender.未知
  ),
  lambda: CalculationInput(
    record=record,
    lunar_year=2000,
    month=4,
    day=1,
    is_leap_month=False,
    shichen=None,
    ganzhi_year=2000,
    config=plain,
    **complete,
  ).require_complete(),
  lambda: CalculationInput(
    record=unknown_time,
    lunar_year=2000,
    month=4,
    day=1,
    is_leap_month=False,
    shichen=Dizhi.子,
    ganzhi_year=2000,
    config=plain,
    **complete,
  ),
  lambda: CalculationInput(
    record=record,
    lunar_year=2000,
    month=4,
    day=1,
    is_leap_month=False,
    shichen=None,
    ganzhi_year=2000,
    config=config,
    **complete,
  ),
  lambda: LunarBirthRecord(
    year=2000,
    month=4,
    day=1,
    is_leap_month=False,
    shichen=None,
    gender=Gender.男,
    longitude_deg=10**400,
  ),
  lambda: supported_lunar_year_range("ALGO3"),
  lambda: utc_to_ut1_jd(datetime(2024, 2, 4, 8, 0)),
  lambda: validate_lunar_date(LunarAlgorithm.ALGO3, 2023, 1, 30, False),
  lambda: month_palace_index(0),
  lambda: minggong_dizhi(1, "子"),
  lambda: bureau_of("甲子"),
  lambda: resolve("1988", plain),
  lambda: resolve(record, config),
  lambda: lucun_yangtuo_dizhi("甲"),
  lambda: liunian_stars(True),
  lambda: LiunianStars(0),
  lambda: liunian_view(None, 2025),
  lambda: LiunianView(liunian=liunian_stars(2025), natal=None),
]
for index, action in enumerate(cases):
  try:
    action()
  except (TypeError, ValueError):
    pass
  else:
    raise RuntimeError(f"public check {index} accepted invalid input")
print(f"checked={len(cases)}")
