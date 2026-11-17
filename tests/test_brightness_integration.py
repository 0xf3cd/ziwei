"""亮度查询、知识、参考与两种显示；合成盘不冒称独立完整生辰盘。"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from unicodedata import east_asian_width

import pytest

from tools.knowledge_reference import _brightness_rows, check_knowledge_reference, render_catalog
from ziwei import brightness
from ziwei.birth import Gender, LunarBirthRecord
from ziwei.brightness import BrightnessTable, star_brightness
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
from ziwei.render import render_text
from ziwei.sihua import SihuaVariant
from ziwei.stars import MAJOR_STARS, Star

FIXTURES = Path(__file__).parent / "fixtures"

TABLE = BrightnessTable.全书卷二录文
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
  assert sum(item.level is None for item in readings) == len(Star) - 14
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


def test_text_display_shows_the_named_table_without_changing_star_labels(
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


@pytest.mark.parametrize("invalid", [False, 0, "全书卷二录文", [], Star.紫微])
def test_display_table_selection_is_not_coerced(brightness_chart: ZiweiChart, invalid: Any) -> None:
  with pytest.raises(TypeError):
    render_text(brightness_chart, brightness_table=invalid)
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
  result = subprocess.run(
    (sys.executable, *mode, "-I", str(FIXTURES / "brightness_isolation.py")),
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stdout + result.stderr
  assert "brightness isolated; checked=5" in result.stdout
