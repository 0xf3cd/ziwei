"""亮度校验与亮度知识不需要原生历法，且输入校验不依赖assert。

程序故意传入错误类型来检查运行时校验，所以不做静态类型检查。
"""

# mypy: ignore-errors
# ruff: noqa: E402, I001

import sys
from importlib.abc import MetaPathFinder


class Block(MetaPathFinder):
  def find_spec(self, fullname, path=None, target=None):
    if fullname.split(".")[0] in ("celestial_calendar", "tzdata", "zoneinfo") or fullname in (
      "ziwei.birth",
      "ziwei.calendar",
      "ziwei.chart",
      "ziwei.timezone",
    ):
      raise RuntimeError("unexpected boundary: " + fullname)


sys.meta_path.insert(0, Block())
from ziwei.brightness import BrightnessReading, BrightnessLevel, BrightnessTable, star_brightness
from ziwei.ganzhi import Dizhi
from ziwei.stars import Star
from ziwei.knowledge import load_catalog

table = BrightnessTable.全书卷二录文
if star_brightness(Star.紫微, Dizhi.辰, table=table).level is not BrightnessLevel.得地:
  raise RuntimeError("wrong brightness")
if not load_catalog().references(table.table_id):
  raise RuntimeError("missing table references")
cases = [
  lambda: star_brightness("紫微", Dizhi.辰, table=table),
  lambda: star_brightness(Star.紫微, "辰", table=table),
  lambda: star_brightness(Star.紫微, Dizhi.辰, table="全书"),
  lambda: BrightnessReading(Star.紫微, Dizhi.辰, table, None),
  lambda: BrightnessReading(Star.红鸾, Dizhi.子, table, BrightnessLevel.平和),
]
for action in cases:
  try:
    action()
  except (TypeError, ValueError):
    pass
  else:
    raise RuntimeError("accepted invalid brightness")
print("brightness isolated; checked=5")
