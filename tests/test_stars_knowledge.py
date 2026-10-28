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
from ziwei.bureau import WuxingJu
from ziwei.config import POLICY_ENUMS, TianmaRule
from ziwei.ganzhi import Dizhi, Tiangan
from ziwei.knowledge import load_catalog
from ziwei.knowledge.data import _star_entries
from ziwei.knowledge.model import Concept, ConceptKind, RuleVariant, Source, SourceStatus

# 用字面值固定规则ID对应的星曜，否则执行定义与目录一起错绑时，期望也会跟着改变。
# 新增规则另加期望，不改已有规则的ID与星曜对应关系。
EXPECTED_RULE_STARS = {
  "variant.star.ziwei-bureau-day": (stars.Star.紫微,),
  "variant.star.ziwei-series": (
    stars.Star.天机,
    stars.Star.太阳,
    stars.Star.武曲,
    stars.Star.天同,
    stars.Star.廉贞,
  ),
  "variant.star.tianfu-reflection": (stars.Star.天府,),
  "variant.star.tianfu-series": (
    stars.Star.太阴,
    stars.Star.贪狼,
    stars.Star.巨门,
    stars.Star.天相,
    stars.Star.天梁,
    stars.Star.七杀,
    stars.Star.破军,
  ),
  "variant.star.fubi-effective-month": (stars.Star.左辅, stars.Star.右弼),
  "variant.star.wenchang-wenqu-hour": (stars.Star.文昌, stars.Star.文曲),
  "variant.star.kuiyue-modern": (stars.Star.天魁, stars.Star.天钺),
  "variant.star.lucun-stem": (stars.Star.禄存,),
  "variant.star.yangtuo-lucun": (stars.Star.擎羊, stars.Star.陀罗),
  "variant.star.huoling-forward": (stars.Star.火星, stars.Star.铃星),
  "variant.star.kongjie-hour": (stars.Star.地空, stars.Star.地劫),
  "variant.tianma.year-branch": (stars.Star.天马,),
  "variant.tianma.month-branch": (stars.Star.天马,),
  "variant.star.hongluan-tianxi-year-branch": (stars.Star.红鸾, stars.Star.天喜),
}


def _pure_star_positions() -> tuple[stars.StarPlacement, ...]:
  return (
    *stars.place_major_stars(WuxingJu.火六局, 7),
    *stars.place_month_stars(1),
    *stars.place_hour_stars(Dizhi.子),
    *stars.place_stem_stars(Tiangan.甲),
    *stars.place_fire_bell(Dizhi.辰, Dizhi.子),
    *stars.place_hongluan_tianxi(Dizhi.辰),
  )


@pytest.mark.parametrize("identifier,members", EXPECTED_RULE_STARS.items())
def test_existing_star_rule_identities_keep_their_meaning(
  identifier: str, members: tuple[stars.Star, ...]
) -> None:
  rules = tuple(rule for rule in stars.STAR_RULES if rule.id == identifier)
  assert len(rules) == 1
  assert set(rules[0].stars) == set(members)
  variant = load_catalog().get(identifier)
  assert isinstance(variant, RuleVariant)
  assert set(variant.concept_ids) == {star.concept_id for star in members}


def test_low_level_positions_keep_existing_rule_identities() -> None:
  positions = _pure_star_positions()
  expected = {
    star: identifier
    for identifier, members in EXPECTED_RULE_STARS.items()
    for star in members
    if star is not stars.Star.天马
  }
  assert len(positions) == len(expected)
  assert {position.star: position.rule_id for position in positions} == expected


@pytest.mark.parametrize(
  "choice,identifier",
  [
    (TianmaRule.年支天马, "variant.tianma.year-branch"),
    (TianmaRule.月支天马, "variant.tianma.month-branch"),
  ],
)
def test_tianma_choices_keep_distinct_rule_identities(choice: TianmaRule, identifier: str) -> None:
  rules = tuple(rule for rule in stars.STAR_RULES if rule.tianma_rule is choice)
  assert len(rules) == 1
  assert rules[0].id == identifier


def test_rule_display_names_do_not_change_position_identities(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  original = _pure_star_positions()
  rules = stars.STAR_RULES
  renamed = tuple(replace(rule, name=f"显示名{index}") for index, rule in enumerate(rules))
  monkeypatch.setattr(stars, "STAR_RULES", renamed)
  assert all(before.name != after.name for before, after in zip(rules, renamed, strict=True))
  assert _pure_star_positions() == original


def test_every_star_and_rule_is_queryable_without_birth() -> None:
  catalog = load_catalog()
  assert len(catalog.list_concepts(kind=ConceptKind.星曜)) == 30
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


def test_rule_meaning_does_not_include_configuration_defaults() -> None:
  for rule in stars.STAR_RULES:
    assert all("默认" not in text for text in (rule.definition, rule.scope, *rule.conditions))


@pytest.mark.parametrize(
  "change,error_encoding",
  [
    ("append", None),
    ("rename", None),
    ("display-name", None),
    ("alias", None),
    ("rule-name", None),
    ("missing-id", None),
    ("missing-id", "ascii"),
  ],
)
def test_star_concepts_have_explicit_identity(
  tmp_path: Path, change: str, error_encoding: str | None
) -> None:
  source = tmp_path / "src"
  shutil.copytree(
    Path(__file__).resolve().parents[1] / "src/ziwei",
    source / "ziwei",
    ignore=shutil.ignore_patterns("__pycache__"),
  )
  path = source / "ziwei/stars.py"
  code = path.read_text(encoding="utf-8")
  marker = "  紫微 = ZIWEI"
  assert code.count(marker) == 1
  if change == "rename":
    code = code.replace("  ZIWEI = ", "  ZIWEI_RENAMED = ").replace(
      marker, "  紫微 = ZIWEI_RENAMED"
    )
  elif change == "display-name":
    code = code.replace('ZIWEI = "紫微",', 'ZIWEI = "紫微（显示名）",')
  elif change == "alias":
    code = code.replace(marker, "  新增别名 = ZIWEI\n" + marker)
  elif change == "rule-name":
    code = code.replace('"紫微系固定关系"', '"紫微系显示名"')
  else:
    member = '  FUTURE = "测试星", "concept.star.future"\n'
    if change == "missing-id":
      member = '  FUTURE = "测试星"\n'
    code = code.replace(marker, member + marker)
  path.write_text(code, encoding="utf-8")
  check = """
import sys
sys.path.insert(0, sys.argv[1])
if sys.argv[3]:
  sys.stderr.reconfigure(encoding=sys.argv[3], errors='backslashreplace')
try:
  from ziwei.stars import Star
except ValueError as error:
  if sys.argv[2] != 'missing-id' or str(error) != '新增星曜须显式指定知识标识':
    raise
  print('MISSING_ID_REJECTED')
  raise SystemExit(0)
if sys.argv[2] == 'missing-id':
  raise RuntimeError('missing identity accepted')
from ziwei.knowledge import load_catalog
catalog = load_catalog()
for star in Star:
  if catalog.get(star.concept_id).name != star.value:
    raise RuntimeError('star concept mismatch')
if Star.紫微.concept_id != 'concept.star.ziwei':
  raise RuntimeError('renamed member changed identity')
if sys.argv[2] == 'rename' and Star.紫微.name != 'ZIWEI_RENAMED':
  raise RuntimeError('rename was not applied')
if sys.argv[2] == 'display-name' and Star.紫微.value != '紫微（显示名）':
  raise RuntimeError('display name was not changed')
if sys.argv[2] == 'alias' and Star.新增别名 is not Star.紫微:
  raise RuntimeError('alias was not added')
if sys.argv[2] == 'rule-name':
  rule = catalog.get('variant.star.ziwei-series')
  if rule.name != '紫微系显示名' or 'concept.star.tianji' not in rule.concept_ids:
    raise RuntimeError('rule display name changed identity')
print('CONCEPTS_OK', len(Star))
"""
  result = subprocess.run(
    [
      sys.executable,
      "-I",
      *(["-O"] if sys.flags.optimize else []),
      "-c",
      check,
      str(source),
      change,
      error_encoding or "",
    ],
    cwd=tmp_path,
    text=True,
    capture_output=True,
    check=False,
  )
  assert result.returncode == 0, result.stdout + result.stderr
  expected = (
    "MISSING_ID_REJECTED"
    if change == "missing-id"
    else f"CONCEPTS_OK {31 if change == 'append' else 30}"
  )
  assert result.stdout.strip() == expected


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
  entry = catalog.filter_entries(variant_id="variant.tianma.month-branch")[0]
  assert "同文" in entry.limits and "一路文本" in entry.limits
  assert "citation.zhongyi999.tianma-month" in entry.citation_ids
  assert entry.alternatives == ()
  forum = catalog.get("source.zhongyi999-paimingpan")
  assert isinstance(forum, Source) and forum.status is SourceStatus.待核
  assert forum.lineage_id == "lineage.zhongyi999-paimingpan"
  assert "citation.zhongyi999.tianma-year" in {
    item.id for item in catalog.references("entry.tianma.year-branch")
  }


def test_modern_short_quotes_stay_below_budget_per_lineage() -> None:
  catalog = load_catalog()
  lengths: dict[str, int] = {}
  for source in catalog.sources:
    if source.id in (
      "source.zhongzhou-wangtingzhi",
      "source.zhongzhou-5shubook",
      "source.jingcheng-golla",
      "source.jielan-tianji",
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
  shutil.copytree(root / "docs/_static", source / "docs/_static")
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
