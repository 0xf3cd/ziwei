"""完整执行表、单行异文、来源与生成HTML必须保持各自的含义和关联。"""

import subprocess
import sys
from pathlib import Path

import pytest

from tools.knowledge_reference import check_knowledge_reference, render_catalog
from ziwei import sihua
from ziwei.birth import Gender
from ziwei.bureau import WuxingJu
from ziwei.decades import DECADE_RULE_ID, Direction, decade_periods
from ziwei.ganzhi import Dizhi, Tiangan
from ziwei.knowledge import load_catalog
from ziwei.knowledge.model import ConceptKind, RuleVariant, Source, SourceStatus
from ziwei.sihua import SIHUA_TABLES, SihuaTable
from ziwei.stars import Star


def test_rule_sources_and_existing_fragment_ids_are_separate() -> None:
  catalog = load_catalog()
  for table in SIHUA_TABLES:
    variant = catalog.get(table.id)
    assert isinstance(variant, RuleVariant)
    assert variant.implementation == "ziwei.sihua.sihua_for_stem"
    assert catalog.references(table.id)
    assert all(q.source_id in {s.id for s in catalog.sources} for q in catalog.references(table.id))
  decade = catalog.get(DECADE_RULE_ID)
  assert isinstance(decade, RuleVariant) and decade.implementation == "ziwei.decades.decade_periods"
  assert catalog.list_concepts(kind=ConceptKind.运限)[0].id == "concept.decades"
  period = decade_periods(Dizhi.子, WuxingJu.水二局, Tiangan.甲, Gender.男)[0]
  assert period.direction is Direction.顺行 and catalog.references(period.rule_id)
  assert {q.source_id for q in catalog.references(DECADE_RULE_ID)} == {
    "source.zhongyi999-paimingpan",
    "source.zhongzhou-wangtingzhi",
  }
  old = catalog.get("variant.sihua.geng-jiuqian-zhongzhou")
  assert isinstance(old, RuleVariant) and old.implementation is None
  assert catalog.filter_entries(show_by_default=True) == ()
  for name in ("source.zhongyi999-paimingpan", "source.zhongzhou-5shubook"):
    source = catalog.get(name)
    assert isinstance(source, Source) and source.status is SourceStatus.待核


@pytest.mark.parametrize("section", ["implemented-sihua", "implemented-decades"])
@pytest.mark.parametrize("defect", ["value", "missing", "anchor"])
def test_actual_html_rejects_new_reference_defects(
  tmp_path: Path, section: str, defect: str
) -> None:
  page = tmp_path / "docs/knowledge-reference.html"
  page.parent.mkdir()
  before, after = render_catalog(load_catalog()).split(f'<section id="{section}">')
  if defect == "value":
    if section == "implemented-sihua":
      after = after.replace("<td>武曲</td>", "<td>天府</td>", 1)
    else:
      after = after.replace("寅：2-11", "寅：2-12", 1)
  elif defect == "missing":
    start = after.index("<tr><td>")
    end = after.index("</tr>", start) + len("</tr>")
    after = after[:start] + after[end:]
  page.write_text(
    before + f'<section id="{section if defect != "anchor" else "fake"}">' + after,
    encoding="utf-8",
  )
  with pytest.raises(ValueError, match="Rule reference differs"):
    check_knowledge_reference(tmp_path)


def test_reference_generation_uses_the_executable_table(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  page = tmp_path / "docs/knowledge-reference.html"
  page.parent.mkdir()
  catalog = load_catalog()
  original = render_catalog(catalog)
  page.write_text(original, encoding="utf-8")
  table = SIHUA_TABLES[0]
  row = (Star.廉贞, Star.破军, Star.天府, Star.太阳)
  changed = SihuaTable(table.variant, (row, *table.rows[1:]))
  monkeypatch.setattr(sihua, "SIHUA_TABLES", (changed, *SIHUA_TABLES[1:]))
  with pytest.raises(ValueError, match="implemented-sihua"):
    check_knowledge_reference(tmp_path)
  rendered = render_catalog(catalog)
  assert rendered != original
  page.write_text(rendered, encoding="utf-8")
  check_knowledge_reference(tmp_path)


def test_knowledge_and_pure_rules_do_not_load_native_calendar() -> None:
  root = Path(__file__).resolve().parents[1]
  script = """
import sys
sys.path.insert(0, sys.argv[1])
from ziwei.knowledge import load_catalog
from ziwei.sihua import SihuaVariant, sihua_for_stem
from ziwei.decades import decade_periods
from ziwei.ganzhi import Tiangan, Dizhi
from ziwei.bureau import WuxingJu
from ziwei.birth import Gender
catalog = load_catalog()
result = sihua_for_stem(Tiangan.壬, SihuaVariant.排命盘口诀转录)
periods = decade_periods(Dizhi.子, WuxingJu.水二局, Tiangan.甲, Gender.男)
if not catalog.references(result.rule_id) or not catalog.references(periods[0].rule_id):
  raise ValueError('missing source association')
if any(n.startswith('celestial_calendar') for n in sys.modules):
  raise ValueError('native calendar initialized')
"""
  result = subprocess.run(
    (sys.executable, "-I", "-c", script, str(root / "src")), capture_output=True, text=True
  )
  assert result.returncode == 0, result.stdout + result.stderr
