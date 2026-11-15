"""无原生历法时安星与知识查询可用，且输入校验不依赖assert。

程序故意传入错误类型来检查运行时校验，所以不做静态类型检查。
"""

# mypy: ignore-errors
# ruff: noqa: E402, I001

import sys
from importlib.abc import MetaPathFinder


class Block(MetaPathFinder):
  def find_spec(self, fullname, path=None, target=None):
    if fullname.split(".")[0] in ("celestial_calendar", "tzdata"):
      raise RuntimeError("unexpected native or timezone import: " + fullname)


sys.meta_path.insert(0, Block())
from dataclasses import replace
from ziwei.birth import CalculationInput, LunarBirthRecord, Gender
from ziwei.calendar import LunarAlgorithm
from ziwei.config import ChartConfig, LeapMonthPolicy, DayRollover, YearBoundary
from ziwei.bureau import WuxingJu
from ziwei.ganzhi import Dizhi
from ziwei.stars import (
  Star,
  StarPlacement,
  StarRule,
  place_fire_bell,
  place_hongluan_tianxi,
  place_hour_stars,
  place_major_stars,
  place_month_stars,
  place_stars,
  place_stem_stars,
  place_tianku_tianxu,
  place_tianshang_tianshi,
  tianfu_dizhi,
  tianma_dizhi,
  ziwei_dizhi,
)
from ziwei.knowledge import load_catalog

config = ChartConfig(
  leap_month_policy=LeapMonthPolicy.全月归本月,
  day_rollover=DayRollover.早晚子时同日,
  year_boundary=YearBoundary.农历正月初一,
)
record = LunarBirthRecord(
  year=2000, month=1, day=1, is_leap_month=False, shichen=Dizhi.子, gender=Gender.未知
)
value = CalculationInput(
  record=record,
  lunar_year=2000,
  month=1,
  day=1,
  is_leap_month=False,
  shichen=Dizhi.子,
  ganzhi_year=2000,
  config=config,
  lunar_algorithm=LunarAlgorithm.ALGO3,
  lunar_algorithm_version="0.8.0",
  apparent_solar=False,
  day_rolled=False,
  ut1_jd=None,
  lichun_jd=None,
)
if len(place_stars(value)) != len(Star) or not load_catalog().find("紫微"):
  raise RuntimeError("pure placement or independent lookup did not run")
cases = [
  lambda: ziwei_dizhi(WuxingJu.水二局, True),
  lambda: StarRule("id", "name", ["紫微"], "definition", "implementation"),
  lambda: StarRule("id", "name", [Star.紫微, Star.紫微], "definition", "implementation"),
  lambda: StarRule("id", "name", [Star.紫微], "definition", "implementation", conditions=[None]),
  lambda: ziwei_dizhi(WuxingJu.水二局, 31),
  lambda: ziwei_dizhi("水二局", 1),
  lambda: place_month_stars(13),
  lambda: place_month_stars(True),
  lambda: place_hour_stars("子"),
  lambda: place_stem_stars("甲"),
  lambda: place_fire_bell("辰", Dizhi.卯),
  lambda: place_fire_bell(Dizhi.辰, None),
  lambda: place_hongluan_tianxi("子"),
  lambda: place_tianku_tianxu("子"),
  lambda: place_tianshang_tianshi("寅"),
  lambda: tianma_dizhi("子"),
  lambda: tianfu_dizhi("子"),
  lambda: place_stars(replace(value, shichen=None)),
  lambda: place_stars(None),
  lambda: replace(config, tianma_rule="年支天马"),
  lambda: replace(config, month_star_leap_month_policy=True),
  lambda: StarPlacement(Star.天刑, Dizhi.酉, "variant.star.fubi-effective-month"),
  lambda: StarPlacement(Star.天马, Dizhi.寅, place_major_stars(WuxingJu.水二局, 1)[0].rule_id),
  lambda: StarPlacement("紫微", Dizhi.寅, "variant.unknown"),
]
for action in cases:
  try:
    action()
  except (TypeError, ValueError):
    pass
  else:
    raise RuntimeError("validation accepted invalid input")
print("checked=" + str(len(cases)))
