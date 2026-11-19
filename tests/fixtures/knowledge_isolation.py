"""知识查询不加载出生、时区与原生历法边界，且输入校验不依赖assert。

程序故意传入错误类型来检查运行时校验，所以不做静态类型检查。
"""

# mypy: ignore-errors
# ruff: noqa: E402, I001

import sys
from importlib.abc import MetaPathFinder


class Block(MetaPathFinder):
  def find_spec(self, fullname, path=None, target=None):
    if fullname.split(".")[0] in (
      "celestial_calendar",
      "tzdata",
      "zoneinfo",
      "bazi",
    ) or fullname in ("ziwei.birth", "ziwei.timezone", "ziwei.chart", "ziwei.calendar"):
      raise RuntimeError("knowledge tried to initialize a foreign boundary: " + fullname)


sys.meta_path.insert(0, Block())
from dataclasses import replace
import json
from ziwei.config import DayRollover
from ziwei.knowledge import load_catalog
from ziwei.knowledge.model import Concept, ConceptKind

c = load_catalog()
if len(c.find("庚干四化")) != 3 or not c.references("entry.tianma.year-branch"):
  raise RuntimeError("knowledge lookup did not run")
topic = c.topic("concept.star.tiankong")
if [entry.id for entry in topic.search_entries("前一位丑宫即安天空")] != [
  "entry.star.tiankong-year"
]:
  raise RuntimeError("independent topic or quote search did not run")
if (
  json.loads(json.dumps(c.select_entries([topic.entries[0].id]).to_dict()))["entries"][0][
    "premises"
  ]
  == []
):
  raise RuntimeError("knowledge JSON lost its premises")
cases = [
  lambda: Concept(id="concept.x", name="x", kind="星曜"),
  lambda: Concept(id="not an id", name="x", kind=ConceptKind.星曜),
  lambda: replace(c, concepts=(*c.concepts, c.concepts[0])),
  lambda: replace(c, citations=(replace(c.citations[0], source_id="source.unknown"),)),
  lambda: c.filter_entries(show_by_default=1),
  lambda: c.filter_entries(show_by_default=0),
  lambda: replace(c.entries[0], show_by_default=1),
  lambda: replace(c.entries[0], show_by_default=None),
  lambda: replace(
    c,
    variants=tuple(
      replace(item, option=DayRollover.晚子时归次日)
      if item.id == "variant.leap-month.current"
      else item
      for item in c.variants
    ),
  ),
  lambda: replace(c.citations[0], layer="原文"),
  lambda: c.topic("source.quanshu-wikisource"),
  lambda: c.search_entries("  "),
  lambda: c.search_entries("闰月", show_by_default=1),
  lambda: c.select_entries("entry.star.tiankong-year"),
  lambda: c.select_entries(["concept.star.tiankong"]),
]
for action in cases:
  try:
    action()
  except (TypeError, ValueError, KeyError):
    pass
  else:
    raise RuntimeError("knowledge accepted invalid input")
print("knowledge isolated and checked=" + str(len(cases)))
