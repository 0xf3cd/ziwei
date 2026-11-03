"""从已安装的doushu公开子模块消费原对象。"""

import json
import pickle
import sys
from importlib import import_module
from importlib.metadata import distribution
from pathlib import Path


def main(version: str, expectations: Path, first: str) -> None:
  if first not in ("doushu", "ziwei"):
    raise ValueError("Unexpected import order")
  for name in (first, "ziwei" if first == "doushu" else "doushu"):
    package = import_module(name)
    if package.__file__ is None or not Path(package.__file__).resolve().is_relative_to(
      Path(sys.prefix).resolve()
    ):
      raise ValueError("Imported package outside the consumer environment")
    if distribution(name).version != version:
      raise ValueError("Installed primary and alias must have the same version")
  if distribution("doushu").requires != [f"ziwei=={version}"]:
    raise ValueError("Alias primary pin differs")
  names: dict[str, list[str]] = json.loads(expectations.read_text(encoding="utf-8"))
  golden = {
    "ziwei.birth": {"Gender", "BirthRecord", "LunarBirthRecord"},
    "ziwei.chart": {"ZiweiChart", "create_chart"},
    "ziwei.knowledge": {"load_catalog"},
    "ziwei.knowledge.catalog": {"Catalog", "Record"},
  }
  if any(not required <= set(names.get(module, [])) for module, required in golden.items()):
    raise ValueError("Installed alias expectations omit required API objects")
  count = 0
  for module, members in names.items():
    alias_name = "doushu" + module.removeprefix("ziwei")
    primary_name = module
    for target in (alias_name, primary_name) if first == "doushu" else (primary_name, alias_name):
      import_module(target)
    alias, primary = import_module(alias_name), import_module(primary_name)
    if {n for n in vars(alias) if not n.startswith("_")} != set(members):
      raise ValueError(f"Alias public names differ: {alias_name}")
    if any(getattr(alias, n) is not getattr(primary, n) for n in members):
      raise ValueError(f"Alias must forward original objects: {alias_name}")
    count += len(members)
  birth = import_module("doushu.birth")
  chart_api = import_module("doushu.chart")
  config = import_module("doushu.config")
  ganzhi = import_module("doushu.ganzhi")
  knowledge = import_module("doushu.knowledge")
  render = import_module("doushu.render")
  sihua = import_module("doushu.sihua")

  if pickle.loads(pickle.dumps(birth.Gender.女)) is not birth.Gender.女:
    raise ValueError("Alias enum identity did not survive pickle")
  if knowledge.load_catalog().get("concept.star.ziwei").id != "concept.star.ziwei":
    raise ValueError("Alias independent knowledge query differs")
  if any(n == "celestial_calendar" or n.startswith("celestial_calendar.") for n in sys.modules):
    raise ValueError("Alias import or knowledge query initialized the native calendar")
  record = birth.LunarBirthRecord(
    year=2024, month=1, day=1, is_leap_month=False, shichen=ganzhi.Dizhi.子, gender=birth.Gender.女
  )
  if (
    pickle.loads(pickle.dumps(record)) != record
    or type(record) is not import_module("ziwei.birth").LunarBirthRecord
  ):
    raise ValueError("Alias record did not retain its primary type through pickle")
  choices = config.ChartConfig(
    leap_month_policy=config.LeapMonthPolicy.全月归本月,
    day_rollover=config.DayRollover.早晚子时同日,
    year_boundary=config.YearBoundary.农历正月初一,
  )
  chart = chart_api.create_chart(record, choices, sihua_variant=sihua.SihuaVariant.排命盘口诀转录)
  if (
    type(chart) is not import_module("ziwei.chart").ZiweiChart
    or render.render_text(chart).splitlines()[0] != "火六局 · 大限逆行 · 虚岁首尾包含"
  ):
    raise ValueError("Alias chart differs from the documented input")
  print(
    f"Installed doushu {version}; {len(names)} modules/{count} original objects; first={first}; optimized={sys.flags.optimize}"
  )


if __name__ == "__main__":
  main(sys.argv[1], Path(sys.argv[2]), sys.argv[3])
