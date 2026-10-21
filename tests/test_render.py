"""显示只读、同宫多星保全和等宽终端列宽；不把显示当计算参考。"""

import json
from dataclasses import replace
from unicodedata import east_asian_width

import pytest

from ziwei.chart import ZiweiChart
from ziwei.ganzhi import Dizhi
from ziwei.render import render_text
from ziwei.serialization import dumps_chart, loads_chart


def test_grid_shows_twelve_palaces_and_all_stars(lunar_chart: ZiweiChart) -> None:
  before = dumps_chart(lunar_chart)
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
  assert dumps_chart(lunar_chart) == before
  rows = [line for line in text.splitlines() if line.startswith(("+", "|"))]
  widths = {sum(2 if east_asian_width(c) in ("W", "F") else 1 for c in row) for row in rows}
  assert len(widths) == 1
  top = rows[1]
  assert top.index("己巳") < top.index("庚午") < top.index("辛未") < top.index("壬申")


def test_render_does_not_interpolate_untrusted_metadata(lunar_chart: ZiweiChart) -> None:
  record = replace(lunar_chart.calculation.record, place="\x1b[31m\ud800", source="\n\x00控制字符")
  chart = replace(lunar_chart, calculation=replace(lunar_chart.calculation, record=record))
  text = render_text(loads_chart(dumps_chart(chart)))
  assert "\x1b" not in text and "\x00" not in text and "\ud800" not in text
  assert text == render_text(lunar_chart)


def test_render_uses_stored_palaces_not_name_sorting(lunar_chart: ZiweiChart) -> None:
  data = json.loads(dumps_chart(lunar_chart))
  assert sum(p.dizhi is Dizhi.戌 for p in lunar_chart.stars) >= 3
  assert data["palaces"][0]["dizhi"] == "戌"
  assert "紫微" in render_text(lunar_chart) and "天相" in render_text(lunar_chart)


def test_render_rejects_non_chart() -> None:
  with pytest.raises(TypeError):
    render_text(None)  # type: ignore[arg-type]
