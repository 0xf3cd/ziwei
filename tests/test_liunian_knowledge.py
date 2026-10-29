"""流年定位、年界和历书各保留对应的支持层次。"""

import json
from importlib import import_module
from pathlib import Path

from ziwei.config import POLICY_ENUMS, YearBoundary
from ziwei.knowledge import load_catalog
from ziwei.knowledge.model import (
  Citation,
  Concept,
  CurationStatus,
  DisplayEligibility,
  KnowledgeEntry,
  PremiseStatus,
  RuleVariant,
  Source,
  SourceStatus,
)
from ziwei.liunian import (
  LIUNIAN_MINGGONG_RULE_ID,
  LiunianBoundary,
  liunian_minggong,
  liunian_on_date,
)


def test_rule_ids_link_to_separate_natal_and_liunian_concepts() -> None:
  catalog = load_catalog()
  flow = catalog.get("concept.policy.liunian-year-boundary")
  natal = catalog.get("concept.policy.year-boundary")
  assert isinstance(flow, Concept) and isinstance(natal, Concept)
  assert flow.options == () and natal.options == tuple(YearBoundary)
  assert len(POLICY_ENUMS) == 3
  for boundary, definition in (
    (LiunianBoundary.正月初一日期, "citation.click108.liunian-new-year"),
    (LiunianBoundary.立春日期, "citation.iztro.liunian-lichun-date"),
  ):
    variant = catalog.get(boundary.rule_id)
    assert isinstance(variant, RuleVariant) and variant.option is None
    assert variant.implementation == "ziwei.liunian.liunian_on_date"
    assert "concept.policy.liunian-year-boundary" in variant.concept_ids
    assert "concept.policy.year-boundary" not in variant.concept_ids
    assert {citation.id for citation in catalog.references(variant.id)} == {
      definition,
      "citation.pmo.liunian-2022",
      "citation.pmo.liunian-2024",
    }
    module, name = variant.implementation.rsplit(".", 1)
    assert getattr(import_module(module), name) is liunian_on_date
  position = catalog.get(LIUNIAN_MINGGONG_RULE_ID)
  assert isinstance(position, RuleVariant)
  assert position.implementation == "ziwei.liunian.liunian_minggong"
  module, name = position.implementation.rsplit(".", 1)
  assert getattr(import_module(module), name) is liunian_minggong
  assert {q.source_id for q in catalog.references(position.id)} == {
    "source.quanshu-juan3-wikisource",
    "source.click108-liunian",
  }
  assert not catalog.filter_entries(default_only=True)


def test_entries_keep_their_scope_status_and_witnesses() -> None:
  catalog = load_catalog()
  for suffix, variant, concepts, citations in (
    (
      "year-branch",
      LIUNIAN_MINGGONG_RULE_ID,
      ("concept.liunian",),
      {"citation.quanshu.liunian-position", "citation.click108.liunian-position"},
    ),
    (
      "lunar-new-year",
      LiunianBoundary.正月初一日期.rule_id,
      ("concept.policy.liunian-year-boundary", "concept.liunian"),
      {
        "citation.click108.liunian-new-year",
        "citation.pmo.liunian-2022",
        "citation.pmo.liunian-2024",
      },
    ),
    (
      "lichun-date",
      LiunianBoundary.立春日期.rule_id,
      ("concept.policy.liunian-year-boundary", "concept.liunian"),
      {
        "citation.iztro.liunian-lichun-date",
        "citation.pmo.liunian-2022",
        "citation.pmo.liunian-2024",
      },
    ),
  ):
    entry = catalog.get("entry.liunian." + suffix)
    assert isinstance(entry, KnowledgeEntry)
    assert entry.concept_ids == concepts and entry.variant_ids == (variant,)
    assert set(entry.citation_ids) == citations
    assert entry.premise_status is PremiseStatus.已明确
    assert entry.display is DisplayEligibility.暂不默认展示
    assert entry.curation is CurationStatus.已整理 and entry.chart_match == "未评估"
    assert entry.premises and entry.limits and entry.recheck
    assert entry.tracking_url == "https://github.com/0xf3cd/ziwei/issues/56"
  software = catalog.get("citation.iztro.liunian-lichun-date")
  assert isinstance(software, Citation)
  assert software.source_id == "source.iztro-liunian-date"
  assert software.quote == "if (solarYmd < liChunYmd) {"
  for year in (2022, 2024):
    calendar = catalog.get(f"citation.pmo.liunian-{year}")
    assert isinstance(calendar, Citation)
    assert calendar.source_id == f"source.pmo-calendar-{year}"


def test_literal_witnesses_match_original_citations_and_metadata() -> None:
  reference = json.loads(
    Path(__file__)
    .with_name("fixtures")
    .joinpath("liunian-reference.json")
    .read_text(encoding="utf-8")
  )
  catalog = load_catalog()
  ancient, modern = reference["position_sources"]
  for data in (ancient, modern):
    source = catalog.get(data["source_id"])
    assert isinstance(source, Source) and source.status is SourceStatus.已核
    assert source.url == data["url"] and data["snapshot_sha256"] in source.edition
  for identifier, quote in (
    ("citation.quanshu.liunian-position", ancient["quotes"][0]),
    ("citation.click108.liunian-position", modern["quotes"][1]),
    ("citation.click108.liunian-new-year", modern["quotes"][0]),
  ):
    citation = catalog.get(identifier)
    assert isinstance(citation, Citation) and citation.quote == quote
  source = catalog.get(modern["source_id"])
  assert isinstance(source, Source)
  assert source.authors == (modern["author"],)
  assert modern["published"] in source.edition and modern["modified"] in source.edition
  software = catalog.get("source.iztro-liunian-date")
  assert isinstance(software, Source)
  assert all(record["commit"] in software.edition for record in reference["software_chain"])
  assert reference["software_chain"][-1]["file_sha256"] in software.edition
  for record in reference["software_chain"][:2]:
    assert record["version_basis"] == "package.json at the fixed commit; not a release-tag mapping"
    assert f"该提交package.json版本{record['version']}" in software.edition
    assert record["commit"] in record["version_url"]
  for data in reference["calendar_sources"]:
    calendar_source = catalog.get(data["source_id"])
    assert isinstance(calendar_source, Source)
    assert calendar_source.url == data["url"]
    assert data["snapshot_sha256"] in calendar_source.edition
