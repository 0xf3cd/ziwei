"""显示只读、同宫多星保全和等宽终端列宽；不把显示当计算参考。"""

from copy import deepcopy
from dataclasses import asdict, replace
from unicodedata import east_asian_width

import pytest

from ziwei.birth import Gender, LunarBirthRecord
from ziwei.chart import ZiweiChart, create_chart
from ziwei.config import ChartConfig
from ziwei.ganzhi import Dizhi
from ziwei.render import render_text
from ziwei.sihua import SihuaVariant


def test_grid_shows_twelve_palaces_and_all_stars(lunar_chart: ZiweiChart) -> None:
  before = asdict(lunar_chart)
  text = render_text(lunar_chart)
  assert text.endswith("\n")
  for palace in lunar_chart.palaces:
    assert text.count(palace.name.value) == 1
    assert str(palace.ganzhi) in text
  for star in lunar_chart.stars:
    assert text.count(star.star.value) == 1
  for decade in lunar_chart.decades:
    assert f"{decade.start_age}-{decade.end_age}虚岁" in text
  assert text.count("身宫") == 1
  assert "命宫 甲戌 身宫" in text
  assert all(label in text for label in ("廉贞[禄]", "破军[权]", "武曲[科]", "太阳[忌]"))
  assert asdict(lunar_chart) == before
  rows = [line for line in text.splitlines() if line.startswith(("+", "|"))]
  widths = {sum(2 if east_asian_width(c) in ("W", "F") else 1 for c in row) for row in rows}
  assert len(widths) == 1
  top = rows[1]
  assert top.index("己巳") < top.index("庚午") < top.index("辛未") < top.index("壬申")


def test_header_and_each_palace_consume_stored_age_convention(lunar_chart: ZiweiChart) -> None:
  chart = deepcopy(lunar_chart)
  units = tuple(branch.value + "龄" for branch in Dizhi)
  for decade, unit in zip(chart.decades, units, strict=True):
    object.__setattr__(decade, "age_convention", unit)
  text = render_text(chart)
  assert units[0] in text.splitlines()[0]
  assert text.count(units[0]) == 2
  assert all(text.count(unit) == 1 for unit in units[1:])
  assert "虚岁" not in text
  assert all(decade.age_convention == "虚岁" for decade in lunar_chart.decades)


@pytest.mark.parametrize("surrogate", ["\ud800", "\udc00", "\ud800\udc00"])
def test_render_does_not_interpolate_untrusted_metadata(
  lunar_chart: ZiweiChart, surrogate: str
) -> None:
  record = replace(
    lunar_chart.calculation.record, place="\x1b[31m" + surrogate, source="\n\x00控制字符"
  )
  chart = replace(lunar_chart, calculation=replace(lunar_chart.calculation, record=record))
  text = render_text(chart)
  assert "\x1b" not in text and "\x00" not in text and surrogate not in text
  assert text == render_text(lunar_chart)


def test_render_uses_stored_palaces_not_name_sorting(lunar_chart: ZiweiChart) -> None:
  assert sum(p.dizhi is Dizhi.戌 for p in lunar_chart.stars) >= 3
  assert lunar_chart.palaces[0].dizhi is Dizhi.戌
  assert "紫微" in render_text(lunar_chart) and "天相" in render_text(lunar_chart)


def test_render_rejects_non_chart() -> None:
  with pytest.raises(TypeError):
    render_text(None)  # type: ignore[arg-type]


def test_body_palace_marker_is_not_always_on_minggong(chart_choices: ChartConfig) -> None:
  result = create_chart(
    LunarBirthRecord(
      year=1984, month=1, day=1, is_leap_month=False, shichen=Dizhi.丑, gender=Gender.女
    ),
    chart_choices,
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  assert result.palaces[0].dizhi is Dizhi.丑 and result.shengong is Dizhi.卯
  marked = [
    cell.strip()
    for line in render_text(result).splitlines()
    for cell in line.split("|")
    if "身宫" in cell
  ]
  assert marked == ["福德 丁卯 身宫"]
