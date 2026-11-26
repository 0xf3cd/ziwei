"""读取结果JSON不加载出生、时区、排盘与原生历法边界，且校验在python -O下仍有效。

参数是一份结果JSON文件的路径。
"""

# ruff: noqa: E402

import sys
from collections.abc import Sequence
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType


class Block(MetaPathFinder):
  def find_spec(
    self, fullname: str, path: Sequence[str] | None = None, target: ModuleType | None = None
  ) -> ModuleSpec | None:
    if fullname.split(".")[0] in (
      "celestial_calendar",
      "tzdata",
      "zoneinfo",
      "bazi",
    ) or fullname in (
      "ziwei.birth",
      "ziwei.timezone",
      "ziwei.chart",
      "ziwei.calendar",
      "ziwei.resolver",
    ):
      raise RuntimeError("result reading tried to initialize a foreign boundary: " + fullname)
    return None


sys.meta_path.insert(0, Block())
from ziwei.result import loads

text = Path(sys.argv[1]).read_text(encoding="utf-8")
result = loads(text)
stars = {item.star: item.dizhi for item in result.stars}
if len(result.palaces) != 12 or result.sihua.lu not in stars or not result.liunian:
  raise RuntimeError("result reading lost readings")
for year in result.liunian:
  if year.sihua is not None and year.sihua.ji not in stars:
    raise RuntimeError("annual sihua lost its natal star")
try:
  loads(text.replace('"age_convention": "虚岁"', '"age_convention": "周岁"'))
except ValueError:
  pass
else:
  raise RuntimeError("result reading accepted a wrong age convention")
