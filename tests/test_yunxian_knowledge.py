"""运限文献、项目边界及未决知识分别保留身份，不升级来源或默认展示。"""

import json
from importlib import import_module
from pathlib import Path

from tools.knowledge_reference import KnowledgeTargets, render_catalog
from ziwei.config import POLICY_ENUMS
from ziwei.knowledge import load_catalog
from ziwei.knowledge.model import (
  Citation,
  KnowledgeEntry,
  PremiseStatus,
  RuleVariant,
  Source,
  TextLayer,
)
from ziwei.tongxian import TONGXIAN_PALACES, TONGXIAN_RULE_ID, TongxianBoundary
from ziwei.xiaoxian import XIAOXIAN_RULE_ID, XIAOXIAN_STARTS


def test_implemented_ids_resolve_without_extending_natal_policy_options() -> None:
  catalog = load_catalog()
  assert len(POLICY_ENUMS) == 3
  for identifier in (XIAOXIAN_RULE_ID, TONGXIAN_RULE_ID, *(b.rule_id for b in TongxianBoundary)):
    variant = catalog.get(identifier)
    assert isinstance(variant, RuleVariant)
    assert variant.option is None and not variant.school_ids
    assert variant.implementation is not None
    module, name = variant.implementation.rsplit(".", 1)
    assert callable(getattr(import_module(module), name))
    assert catalog.references(identifier)
  for boundary in TongxianBoundary:
    variant = catalog.get(boundary.rule_id)
    entry = catalog.get(boundary.rule_id.replace("variant.", "entry.", 1))
    assert isinstance(variant, RuleVariant) and isinstance(entry, KnowledgeEntry)
    assert entry.statement == variant.definition == boundary.definition
    assert entry.show_by_default is False
    assert entry.premise_status is PremiseStatus.已明确
    assert "仓内解释" in entry.limits and "一路" in entry.limits
    assert {q.source_id for q in catalog.references(variant.id)} == {"source.jingcheng-pdf"}


def test_literal_pdf_quotes_and_conservative_lineage() -> None:
  reference = json.loads(
    Path(__file__).with_name("fixtures").joinpath("xiaoxian-tongxian-reference.json").read_text()
  )
  catalog = load_catalog()
  source = catalog.get("source.jingcheng-pdf")
  old = catalog.get("source.jingcheng-golla")
  assert isinstance(source, Source) and isinstance(old, Source)
  assert source.lineage_id == old.lineage_id
  assert source.url == reference["pdf_url"]
  assert reference["pdf_sha256"] in source.edition
  assert "版次未核" in source.edition
  for suffix, key in (
    ("xiaoxian", "quote_xiaoxian"),
    ("tongxian-stop", "quote_stop"),
    ("tongxian-xiaoxian", "quote_parallel"),
  ):
    citation = catalog.get("citation.jingcheng." + suffix)
    assert isinstance(citation, Citation)
    assert citation.layer is TextLayer.今人说明
    assert citation.quote == reference[key]


def test_classical_pending_is_queryable_but_not_executable_or_default() -> None:
  catalog = load_catalog()
  entry = catalog.get("entry.tongxian.classical-unresolved")
  variant = catalog.get("variant.tongxian.jielan-unresolved")
  assert isinstance(entry, KnowledgeEntry) and isinstance(variant, RuleVariant)
  assert variant.implementation is None and variant.option is None
  assert entry.premise_status is PremiseStatus.待定
  assert not entry.show_by_default and entry.alternatives and entry.recheck
  assert "六岁后" in entry.statement and "现代" in entry.statement
  assert "命图未见" in entry.limits
  assert any(q.id == "citation.jielan.tongxian-age3" for q in catalog.references(entry.id))
  assert not catalog.filter_entries(show_by_default=True)


def test_generated_tables_keep_each_actual_policy_range() -> None:
  parser = KnowledgeTargets()
  parser.feed(render_catalog(load_catalog()))
  assert len(parser.rows["implemented-xiaoxian"]) == len(XIAOXIAN_STARTS) + 1
  assert len(parser.rows["implemented-tongxian"]) == len(TONGXIAN_PALACES) + 1
  rows = parser.rows["implemented-tongxian-boundaries"]
  assert len(rows) == 11
  assert (
    "起限当岁不含",
    "火六局",
    "1-5",
    "不保留童限",
    TongxianBoundary.起限当岁不含.rule_id,
  ) in rows
  assert ("起限当岁包含", "火六局", "1-6", "并存", TongxianBoundary.起限当岁包含.rule_id) in rows
