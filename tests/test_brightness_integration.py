"""亮度查询、知识、参考与两种显示；合成盘不冒称独立完整生辰盘。"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from unicodedata import east_asian_width
from xml.etree.ElementTree import fromstring

import pytest

from tools.knowledge_reference import _brightness_rows, check_knowledge_reference, render_catalog
from ziwei import brightness
from ziwei.birth import Gender, LunarBirthRecord
from ziwei.brightness import BrightnessLevel, BrightnessTable, star_brightness
from ziwei.chart import ZiweiChart, chart_brightness, create_chart, palace_view
from ziwei.config import ChartConfig
from ziwei.ganzhi import Dizhi
from ziwei.knowledge import load_catalog
from ziwei.knowledge.model import (
  Citation,
  ConceptKind,
  KnowledgeEntry,
  RuleVariant,
  Source,
  SourceStatus,
)
from ziwei.render import render_svg, render_text
from ziwei.sihua import SihuaVariant
from ziwei.stars import MAJOR_STARS, Star

TABLE = BrightnessTable.全书卷二录文
SVG = "{http://www.w3.org/2000/svg}"
pytestmark = pytest.mark.usefixtures("unload_celestial")


@pytest.fixture
def brightness_chart(chart_choices: ChartConfig) -> ZiweiChart:
  return create_chart(
    LunarBirthRecord(
      year=2024, month=1, day=1, is_leap_month=False, shichen=Dizhi.子, gender=Gender.女
    ),
    chart_choices,
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )


def test_chart_readings_preserve_positions_and_are_available_by_palace(
  brightness_chart: ZiweiChart,
) -> None:
  before = brightness_chart.stars
  readings = chart_brightness(brightness_chart, table=TABLE)
  assert len(readings) == len(Star)
  assert sum(item.level is not None for item in readings) == 14
  assert sum(item.level is None for item in readings) == 16
  assert tuple((item.star, item.dizhi) for item in readings) == tuple(
    (item.star, item.dizhi) for item in before
  )
  assert all(item.table is TABLE for item in readings)
  for branch in Dizhi:
    view = palace_view(brightness_chart, branch)
    assert tuple(
      star_brightness(item.star, item.dizhi, table=TABLE) for item in view.stars
    ) == tuple(reading for reading in readings if reading.dizhi is branch)
  assert brightness_chart.stars is before


def test_both_displays_show_the_named_table_without_changing_star_labels(
  brightness_chart: ZiweiChart,
) -> None:
  plain = render_text(brightness_chart)
  text = render_text(brightness_chart, brightness_table=TABLE)
  assert plain == render_text(brightness_chart, brightness_table=None)
  assert TABLE.value not in plain
  assert text.splitlines()[0] == plain.splitlines()[0] + " · " + TABLE.value
  for reading in chart_brightness(brightness_chart, table=TABLE):
    if reading.level is not None:
      assert any(
        reading.star.value in line and " (" + reading.level.value + ")" in line
        for line in text.splitlines()[1:]
      )
  original = render_svg(brightness_chart)
  assert original == render_svg(brightness_chart, brightness_table=None)
  assert "brightness" not in original
  root = fromstring(render_svg(brightness_chart, brightness_table=TABLE, selected_palace=Dizhi.子))
  table_label = root.find(f".//{SVG}text[@class='brightness-table']")
  assert table_label is not None and table_label.text == TABLE.value
  assert len(root.findall(f".//{SVG}text[@class='brightness']")) == 14
  assert [node.text for node in root.findall(f".//{SVG}text[@class='star']")] == [
    node.text for node in fromstring(original).findall(f".//{SVG}text[@class='star']")
  ]


@pytest.mark.parametrize("ambiguous_width", [1, 2])
def test_brightness_text_grid_aligns_with_both_ambiguous_width_conventions(
  brightness_chart: ZiweiChart, ambiguous_width: int
) -> None:
  lines = render_text(brightness_chart, brightness_table=TABLE).splitlines()[1:]
  widths = {
    sum(
      2 if (kind := east_asian_width(char)) in ("W", "F") else ambiguous_width if kind == "A" else 1
      for char in line
    )
    for line in lines
  }
  assert len(widths) == 1


@pytest.mark.parametrize(
  "year,month,day,hour", [(2024, 1, 1, Dizhi.子), (1954, 10, 1, Dizhi.酉), (1984, 2, 2, Dizhi.酉)]
)
def test_svg_brightness_has_separate_rows_and_column_and_vertical_clearance(
  chart_choices: ChartConfig, year: int, month: int, day: int, hour: Dizhi
) -> None:
  chart = create_chart(
    LunarBirthRecord(
      year=year, month=month, day=day, is_leap_month=False, shichen=hour, gender=Gender.女
    ),
    chart_choices,
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  root = fromstring(render_svg(chart, brightness_table=TABLE))
  for cell in root.findall(SVG + "g"):
    if "data-dizhi" not in cell.attrib:
      continue
    divider = cell.find(SVG + "line")
    assert divider is not None
    labels = cell.findall(f"{SVG}text[@class='star']")
    grades = cell.findall(f"{SVG}text[@class='brightness']")
    for node, size in ((item, 19) for item in labels):
      units = sum(1 if east_asian_width(char) in ("W", "F") else 0.6 for char in node.text or "")
      assert float(node.attrib["x"]) % 112 + units * size < 128
    for grade in grades:
      x, y = float(grade.attrib["x"]), float(grade.attrib["y"])
      corresponding = next(
        item
        for item in labels
        if item.attrib["x"] == grade.attrib["x"]
        and float(item.attrib["y"]) < y
        and y - float(item.attrib["y"]) < 28
      )
      assert float(corresponding.attrib["y"]) + 19 * 0.3 < y - 13
      assert y + 13 * 0.3 < float(divider.attrib["y1"])
      following = [float(item.attrib["y"]) for item in labels if float(item.attrib["y"]) > y]
      assert not following or y + 13 * 0.3 < min(following) - 19
      assert x in (16, 128)
      assert grade.text in {level.value for level in BrightnessLevel}


@pytest.mark.parametrize("invalid", [False, 0, "全书卷二录文", [], Star.紫微])
def test_display_table_selection_is_not_coerced(brightness_chart: ZiweiChart, invalid: Any) -> None:
  for display in (render_text, render_svg):
    with pytest.raises(TypeError):
      display(brightness_chart, brightness_table=invalid)
  with pytest.raises(TypeError):
    chart_brightness(brightness_chart, table=invalid)
  with pytest.raises(TypeError):
    chart_brightness(invalid, table=TABLE)


def test_knowledge_links_table_original_words_and_source_limits() -> None:
  catalog = load_catalog()
  concept = catalog.list_concepts(kind=ConceptKind.亮度)
  assert len(concept) == 1 and concept[0].id == "concept.brightness.major-star-levels"
  variant = catalog.get(TABLE.table_id)
  assert isinstance(variant, RuleVariant)
  assert (
    variant.name == TABLE.value and variant.implementation == "ziwei.brightness.star_brightness"
  )
  assert set(variant.concept_ids) == {concept[0].id, *(star.concept_id for star in MAJOR_STARS)}
  entry = catalog.get("entry.brightness.quanshu-juan2")
  assert isinstance(entry, KnowledgeEntry) and entry.show_by_default is False
  assert "底本未核" in entry.limits
  assert "暂停相关公开结果" in entry.recheck
  references = catalog.references(TABLE.table_id)
  assert {item.id for item in references} == set(entry.citation_ids)
  original = catalog.get("citation.quanshu.brightness-table")
  assert isinstance(original, Citation)
  assert (
    original.quote == "|   |庙       |旺       |得地     |利益     |平和     |不得地   |落陷     |"
  )
  assert "十四主星168格" in original.limits
  for identifier, status in (
    ("source.quanshu-wikisource", SourceStatus.已核),
    ("source.wangtingzhi-bazilives-brightness", SourceStatus.待核),
  ):
    source = catalog.get(identifier)
    assert isinstance(source, Source) and source.status is status
  assert "source.wangtingzhi-bazilives-brightness" in {item.source_id for item in references}


@pytest.mark.parametrize("defect", ["missing-row", "wrong-cell", "missing-section"])
def test_generated_brightness_reference_rejects_lost_or_changed_cells(
  tmp_path: Path, defect: str
) -> None:
  rows = _brightness_rows()
  assert len(rows) == 168
  assert (TABLE.table_id, TABLE.value, "紫微", "辰", "得地") in rows
  markup = render_catalog(load_catalog())
  folder = tmp_path / "docs"
  folder.mkdir()
  page = folder / "knowledge-reference.html"
  page.write_text(markup, encoding="utf-8")
  check_knowledge_reference(tmp_path)
  before, section = markup.split('<section id="implemented-brightness">', 1)
  if defect == "missing-row":
    section = re.sub(r"<tr><td>.*?</tr>", "", section, count=1)
  elif defect == "wrong-cell":
    section = section.replace("<td>平和</td>", "<td>庙</td>", 1)
  else:
    before = before.replace('id="implemented-brightness"', 'id="absent"')
    section = section.replace("<h2>", '<h2 id="absent">', 1)
  separator = (
    '<section id="absent">'
    if defect == "missing-section"
    else '<section id="implemented-brightness">'
  )
  page.write_text(before + separator + section, encoding="utf-8")
  with pytest.raises(ValueError, match="implemented-brightness"):
    check_knowledge_reference(tmp_path)


def test_brightness_reference_rejects_an_inapplicable_reading(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  original_query = star_brightness

  def inapplicable(star: Star, branch: Dizhi, *, table: BrightnessTable) -> Any:
    return original_query(Star.红鸾, branch, table=table)

  monkeypatch.setattr(brightness, "star_brightness", inapplicable)
  with pytest.raises(ValueError, match="主星亮度参考缺格"):
    _brightness_rows()


@pytest.mark.parametrize("mode", [(), ("-O",)])
def test_brightness_validation_and_knowledge_do_not_require_native_calendar(
  tmp_path: Path, mode: tuple[str, ...]
) -> None:
  script = r"""
import sys
from importlib.abc import MetaPathFinder
class Block(MetaPathFinder):
  def find_spec(self, fullname, path=None, target=None):
    if fullname.split('.')[0] in ('celestial_calendar', 'tzdata', 'zoneinfo') or fullname in (
        'ziwei.birth', 'ziwei.calendar', 'ziwei.chart', 'ziwei.timezone'):
      raise RuntimeError('unexpected boundary: ' + fullname)
sys.meta_path.insert(0, Block())
from ziwei.brightness import BrightnessReading, BrightnessLevel, BrightnessTable, star_brightness
from ziwei.ganzhi import Dizhi
from ziwei.stars import Star
from ziwei.knowledge import load_catalog
table = BrightnessTable.全书卷二录文
if star_brightness(Star.紫微, Dizhi.辰, table=table).level is not BrightnessLevel.得地:
  raise RuntimeError('wrong brightness')
if not load_catalog().references(table.table_id):
  raise RuntimeError('missing table references')
cases = [lambda: star_brightness('紫微', Dizhi.辰, table=table),
         lambda: star_brightness(Star.紫微, '辰', table=table),
         lambda: star_brightness(Star.紫微, Dizhi.辰, table='全书'),
         lambda: BrightnessReading(Star.紫微, Dizhi.辰, table, None),
         lambda: BrightnessReading(Star.红鸾, Dizhi.子, table, BrightnessLevel.平和)]
for action in cases:
  try:
    action()
  except (TypeError, ValueError):
    pass
  else:
    raise RuntimeError('accepted invalid brightness')
print('brightness isolated; checked=5')
"""
  result = subprocess.run(
    (sys.executable, *mode, "-I", "-c", script),
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stdout + result.stderr
  assert "brightness isolated; checked=5" in result.stdout
