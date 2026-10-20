"""可执行规则、知识查询与生成参考页的关联。"""

import importlib
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tools.knowledge_reference import check_knowledge_reference, render_catalog
from ziwei import stars
from ziwei.config import POLICY_ENUMS, TianmaRule
from ziwei.ganzhi import Dizhi
from ziwei.knowledge import load_catalog
from ziwei.knowledge.data import _star_entries
from ziwei.knowledge.model import Concept, ConceptKind, RuleVariant, Source, SourceStatus


def test_every_star_and_rule_is_queryable_without_birth() -> None:
  catalog = load_catalog()
  assert len(catalog.list_concepts(kind=ConceptKind.星曜)) == 28
  for star in stars.Star:
    concept = catalog.get(star.concept_id)
    assert isinstance(concept, Concept)
    assert concept.name == star.value
    assert concept in catalog.find(star.value)
    assert catalog.references(star.concept_id)
  for rule in stars.STAR_RULES:
    variant = catalog.get(rule.id)
    assert isinstance(variant, RuleVariant)
    assert variant.implementation == rule.implementation
    assert variant.definition == rule.definition
    assert variant.concept_ids == tuple(star.concept_id for star in rule.stars)
    module, _, name = rule.implementation.rpartition(".")
    assert callable(getattr(importlib.import_module(module), name))
    assert catalog.references(rule.id)
  assert len(POLICY_ENUMS) == 3
  assert all(not isinstance(TianmaRule.年支天马, enumeration) for enumeration in POLICY_ENUMS)
  assert catalog.filter_entries(default_only=True) == ()


def test_source_bindings_follow_stable_rule_identity_not_order() -> None:
  original = {entry.id: entry for entry in _star_entries(stars.STAR_RULES)}
  reordered = {entry.id: entry for entry in _star_entries(tuple(reversed(stars.STAR_RULES)))}
  assert reordered == original
  wen = reordered["entry.star.wenchang-wenqu-hour"]
  kuiyue = reordered["entry.star.kuiyue-modern"]
  assert wen.citation_ids == (
    "citation.quanshu.wenchang-wenqu",
    "citation.zhongzhou.fubi-wen-kongjie",
  )
  assert (
    wen.limits
    == "《全书》的子时、丑时例与中州派讲义按时辰安星的口诀相合；本规则不把出生钟点换算为时辰。"
  )
  assert kuiyue.citation_ids == (
    "citation.zhongzhou.kuiyue-lucun",
    "citation.jingcheng.kuiyue-modern",
  )
  assert (
    kuiyue.limits
    == "现代表采用中州派讲义与《精成》所列位置，两者歌诀同文，不据此认定不同字句的版本各有两路独立出处。《全书》的辛、丙丁两行另记待核。"
  )


def test_month_composition_is_queryable_once_by_minggong() -> None:
  catalog = load_catalog()
  matches = catalog.filter_entries(concept_id="concept.palace.minggong")
  assert sum(entry.id == "entry.star.month-policy-composition" for entry in matches) == 1
  entry = catalog.get("entry.star.month-policy-composition")
  assert entry in matches


@pytest.mark.parametrize("defect", ["missing", "extra", "duplicate"])
def test_source_bindings_reject_rule_set_drift(defect: str) -> None:
  original = stars.STAR_RULES
  if defect == "missing":
    changed = original[1:]
  elif defect == "extra":
    changed = (*original, replace(original[0], id="variant.star.unbound"))
  else:
    changed = (*original, original[0])
  with pytest.raises(ValueError, match="来源绑定须逐项一致"):
    _star_entries(changed)


def test_pending_quanshu_is_not_executed_and_modern_evidence_is_not_upgraded() -> None:
  catalog = load_catalog()
  pending = catalog.get("variant.star.kuiyue-quanshu-pending")
  assert isinstance(pending, RuleVariant) and pending.implementation is None
  assert pending.id not in {rule.id for rule in stars.STAR_RULES}
  quotes = "".join(citation.quote for citation in catalog.references(pending.id))
  assert "六辛逢虎马" in quotes and "丙丁猪狗位" in quotes and "壬癸免蛇藏" in quotes
  assert "天空" not in {item.name for item in catalog.list_concepts(kind=ConceptKind.星曜)}
  assert catalog.find("天空") == ()
  old = catalog.get("source.zhongzhou-wangtingzhi")
  new = catalog.get("source.zhongzhou-5shubook")
  assert isinstance(old, Source) and isinstance(new, Source)
  assert old.lineage_id == new.lineage_id
  assert old.status is new.status is SourceStatus.待核
  month = catalog.get("source.jingcheng-golla")
  assert isinstance(month, Source) and month.status is SourceStatus.待核
  assert "单源" in catalog.filter_entries(variant_id="variant.tianma.month-branch")[0].limits


def test_modern_short_quotes_stay_below_budget_per_lineage() -> None:
  catalog = load_catalog()
  lengths: dict[str, int] = {}
  for source in catalog.sources:
    if source.id in (
      "source.zhongzhou-wangtingzhi",
      "source.zhongzhou-5shubook",
      "source.jingcheng-golla",
    ):
      lengths[source.lineage_id] = lengths.get(source.lineage_id, 0) + sum(
        len(citation.quote) for citation in catalog.references(source.id)
      )
  assert lengths and all(length <= 90 for length in lengths.values())


@pytest.mark.parametrize(
  "invalid", ["", "ziwei.stars._private", "os.system", "ziwei.stars.fn()", 1]
)
def test_implementation_path_is_data_only_and_public(invalid: Any) -> None:
  variant = load_catalog().variants[0]
  with pytest.raises((ValueError, TypeError)):
    replace(variant, implementation=invalid)


@pytest.mark.parametrize("defect", ["value", "association", "anchor"])
def test_actual_star_html_rejects_changed_table_or_target(tmp_path: Path, defect: str) -> None:
  page = tmp_path / "docs/knowledge-reference.html"
  page.parent.mkdir()
  before, after = render_catalog(load_catalog()).split('<section id="implemented-stars">')
  if defect == "value":
    after = after.replace(
      "<td>水二局/1日</td><td>紫微</td><td>丑</td>", "<td>水二局/1日</td><td>紫微</td><td>寅</td>"
    )
  elif defect == "association":
    after = after.replace("<td>水二局/1日</td><td>紫微</td>", "<td>水二局/1日</td><td>天府</td>")
  page.write_text(
    before
    + ('<section id="fake-stars">' if defect == "anchor" else '<section id="implemented-stars">')
    + after,
    encoding="utf-8",
  )
  with pytest.raises(ValueError, match="Star reference differs"):
    check_knowledge_reference(tmp_path)


def test_star_reference_generation_reads_executable_data(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  page = tmp_path / "docs/knowledge-reference.html"
  page.parent.mkdir()
  original = render_catalog(load_catalog())
  page.write_text(original, encoding="utf-8")
  monkeypatch.setattr(stars, "_LUCUN_BY_STEM", (Dizhi.子, *stars._LUCUN_BY_STEM[1:]))
  with pytest.raises(ValueError, match="Star reference differs"):
    check_knowledge_reference(tmp_path)
  changed = render_catalog(load_catalog())
  assert original != changed
  page.write_text(changed, encoding="utf-8")
  check_knowledge_reference(tmp_path)


def test_star_table_through_real_sphinx_and_representative_html_defects(tmp_path: Path) -> None:
  root = Path(__file__).resolve().parents[1]
  source = tmp_path / "source"
  (source / "docs").mkdir(parents=True)
  for name in ("conf.py", "python-stdlib.inv"):
    shutil.copyfile(root / "docs" / name, source / "docs" / name)
  (source / "docs/index.md").write_text(
    "# 入口\n\n```{toctree}\nknowledge-reference\n```\n",
    encoding="utf-8",
  )
  (source / "docs/knowledge-reference.md").write_text("# 参考\n", encoding="utf-8")
  output = tmp_path / "html"
  script = r"""
import sys
from pathlib import Path
root, source, output = sys.argv[1:]
sys.path[:0] = [root, str(Path(root) / 'src')]
from sphinx.cmd.build import main
raise SystemExit(main(['-E', '-a', '-n', '-W', '-q', '-b', 'html', '-c',
                      str(Path(source) / 'docs'), source, output]))
"""
  result = subprocess.run(
    (sys.executable, "-I", "-c", script, str(root), str(source), str(output)),
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stdout + result.stderr
  check_knowledge_reference(output)
  page = output / "docs/knowledge-reference.html"
  original = page.read_text(encoding="utf-8")
  for old, new in (
    ("<td>水二局/1日</td><td>紫微</td><td>丑</td>", "<td>水二局/1日</td><td>紫微</td><td>寅</td>"),
    ('id="implemented-stars"', 'id="fake-stars"'),
  ):
    changed = original.replace(old, new)
    assert changed != original
    page.write_text(changed, encoding="utf-8")
    with pytest.raises(ValueError, match="Star reference differs"):
      check_knowledge_reference(output)
