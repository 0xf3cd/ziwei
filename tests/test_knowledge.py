"""知识记录、状态分离、引用与独立查询。合成夹具不作为规则来源。"""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime
from typing import Any, cast

import pytest

from ziwei.config import DayRollover, LeapMonthPolicy
from ziwei.knowledge import load_catalog
from ziwei.knowledge.catalog import Catalog, Record
from ziwei.knowledge.model import (
  Citation,
  Concept,
  ConceptKind,
  CurationStatus,
  DisplayEligibility,
  EvidenceAspect,
  KnowledgeEntry,
  PremiseStatus,
  RuleVariant,
  Source,
  SourceStatus,
  TextLayer,
)


@pytest.fixture
def catalog() -> Catalog:
  concept = Concept(
    id="concept.synthetic", name="合成概念", aliases=("别名", "Alias"), kind=ConceptKind.口径
  )
  school = Concept(id="concept.school.synthetic", name="合成流派", kind=ConceptKind.流派)
  variant = RuleVariant(
    id="variant.synthetic",
    name="合成变体",
    aliases=("别名",),
    definition="仅作结构测试",
    scope="合成材料",
    concept_ids=(concept.id,),
    school_ids=(school.id,),
    conditions=("测试前提",),
    option=LeapMonthPolicy.全月归本月,
    tracking_url="https://example.org/rule",
  )
  source = Source(
    id="source.synthetic",
    title="合成来源",
    authors=("合成作者",),
    edition="合成版",
    url="https://example.org/source",
    layer=TextLayer.原文,
    lineage_id="lineage.synthetic",
    provenance="合成谱系",
    claims="只测试记录",
    limits="不是领域证据",
    rights="合成文本",
    status=SourceStatus.已核,
    checked_on=date(2000, 1, 1),
  )
  citation = Citation(
    id="citation.synthetic",
    source_id=source.id,
    locator="合成定位",
    quote="合成原文",
    aspects=(EvidenceAspect.查法,),
    limits="不是原典",
  )
  entry = KnowledgeEntry(
    id="entry.synthetic",
    statement="合成陈述",
    concept_ids=(concept.id,),
    variant_ids=(variant.id,),
    citation_ids=(citation.id,),
    premises=("合成前提",),
    premise_status=PremiseStatus.已明确,
    display=DisplayEligibility.可默认展示,
    curation=CurationStatus.已整理,
    limits="不用于命盘",
  )
  return Catalog(
    version="synthetic.1",
    concepts=(concept, school),
    variants=(variant,),
    sources=(source,),
    citations=(citation,),
    entries=(entry,),
  )


def test_builtin_corpus_retains_versions_and_unresolved_premises() -> None:
  catalog = load_catalog()
  assert catalog.version == "2026.10.19.1"
  assert {item.kind for item in catalog.concepts} == set(ConceptKind)
  assert len({item.id for item in catalog.records}) == len(catalog.records)
  assert catalog.find("天馬") == catalog.find("tianma")
  assert len(catalog.find("庚干四化")) == 3
  assert catalog.filter_entries(default_only=True) == ()
  pending = catalog.filter_entries(premise_status=PremiseStatus.待定)
  assert [item.id for item in pending] == ["entry.tianma.month-branch"]
  assert pending[0].alternatives == ("由农历月序对应月支", "由节令月建确定月支")
  assert all(item.chart_match == "未评估" for item in catalog.entries)
  assert all(item.recheck and item.tracking_url for item in catalog.entries)
  assert {item.status for item in catalog.sources} == {SourceStatus.已核, SourceStatus.待核}
  citations = {item.id: item for item in catalog.citations}
  assert citations["citation.quanshu.geng"].quote == "庚日武阴同为首"
  assert citations["citation.quanshu.ren"].quote == "壬梁紫府武宿是"
  assert citations["citation.quanshu.tianma-text"].quote == "寅午戍人马居申"
  assert "1963110" in catalog.sources[0].edition
  assert "oldid=1963110" in catalog.sources[0].url
  assert {
    item.option for item in catalog.variants if isinstance(item.option, LeapMonthPolicy)
  } == set(LeapMonthPolicy)
  assert {item.option for item in catalog.variants if isinstance(item.option, DayRollover)} == set(
    DayRollover
  )
  assert load_catalog() == catalog


def test_queries_preserve_alias_ambiguity_and_intersection(catalog: Catalog) -> None:
  assert catalog.find(" ALIAS ") == (catalog.concepts[0],)
  assert catalog.find("别名") == (catalog.concepts[0], catalog.variants[0])
  assert catalog.find("不存在") == ()
  assert catalog.list_concepts() == catalog.concepts
  assert catalog.list_concepts(kind=ConceptKind.流派) == (catalog.concepts[1],)
  assert catalog.list_concepts(kind=ConceptKind.星曜) == ()
  assert catalog.list_variants() == catalog.variants
  assert (
    catalog.list_variants(concept_id="concept.synthetic", school_id="concept.school.synthetic")
    == catalog.variants
  )
  assert catalog.list_variants(concept_id="concept.school.synthetic") == ()
  assert catalog.filter_entries() == catalog.entries
  assert (
    catalog.filter_entries(
      concept_id="concept.synthetic",
      variant_id="variant.synthetic",
      source_id="source.synthetic",
      premise_status=PremiseStatus.已明确,
      display=DisplayEligibility.可默认展示,
      curation=CurationStatus.已整理,
      default_only=True,
    )
    == catalog.entries
  )
  assert catalog.filter_entries(concept_id="concept.school.synthetic") == ()
  assert catalog.filter_entries(display=DisplayEligibility.暂不默认展示) == ()
  assert catalog.filter_entries(premise_status=PremiseStatus.待定) == ()
  assert catalog.filter_entries(curation=CurationStatus.待整理) == ()
  assert catalog.filter_sources() == catalog.sources
  assert (
    catalog.filter_sources(
      status=SourceStatus.已核, aspect=EvidenceAspect.查法, lineage_id="lineage.synthetic"
    )
    == catalog.sources
  )
  assert catalog.filter_sources(status=SourceStatus.待核) == ()
  assert catalog.filter_sources(aspect=EvidenceAspect.规则) == ()
  assert catalog.filter_sources(lineage_id="lineage.other") == ()


@pytest.mark.parametrize(
  "identifier",
  [
    "concept.synthetic",
    "variant.synthetic",
    "source.synthetic",
    "citation.synthetic",
    "entry.synthetic",
  ],
)
def test_independent_references(catalog: Catalog, identifier: str) -> None:
  assert catalog.get(identifier).id == identifier
  assert catalog.references(identifier) == catalog.citations


def test_references_deduplicate_in_catalog_order(catalog: Catalog) -> None:
  first = catalog.entries[0]
  second = replace(first, id="entry.second")
  both = replace(catalog, entries=(first, second))
  assert both.references("concept.synthetic") == catalog.citations
  assert both.references("concept.school.synthetic") == ()
  assert both.filter_entries(source_id="source.synthetic") == (first, second)


def test_four_statuses_do_not_upgrade_each_other(catalog: Catalog) -> None:
  entry = replace(
    catalog.entries[0],
    display=DisplayEligibility.暂不默认展示,
    premise_status=PremiseStatus.待定,
    curation=CurationStatus.待整理,
    recheck="核合成例",
    tracking_url="https://example.org/recheck",
    alternatives=("读法一", "读法二"),
  )
  held = replace(catalog, entries=(entry,))
  assert held.sources[0].status is SourceStatus.已核
  assert held.filter_entries(default_only=True) == ()
  understood = replace(
    held,
    entries=(replace(entry, premise_status=PremiseStatus.已明确, curation=CurationStatus.已整理),),
  )
  assert understood.filter_entries(default_only=True) == ()
  assert understood.entries[0].chart_match == "未评估"
  assert catalog.filter_entries(default_only=True)[0].chart_match == "未评估"
  with pytest.raises(TypeError):
    KnowledgeEntry(
      **{
        **{
          name: getattr(entry, name)
          for name in (
            "id",
            "statement",
            "concept_ids",
            "variant_ids",
            "citation_ids",
            "premises",
            "premise_status",
            "display",
            "curation",
            "limits",
          )
        },
        "chart_match": "满足",
      }
    )


def test_frozen_records_isolate_input_sequences(catalog: Catalog) -> None:
  aliases = ["外部别名"]
  related = ["concept.school.synthetic"]
  concept = replace(catalog.concepts[0], aliases=aliases, related_ids=related)  # type: ignore[arg-type]
  aliases.clear()
  related.clear()
  assert concept.aliases == ("外部别名",)
  assert concept.related_ids == ("concept.school.synthetic",)
  for record in catalog.records:
    with pytest.raises(FrozenInstanceError):
      cast(Any, record).id = "changed.id"
  concepts = list(catalog.concepts)
  copied = replace(catalog, concepts=concepts)  # type: ignore[arg-type]
  concepts.clear()
  assert copied.concepts == catalog.concepts
  entry = catalog.entries[0]
  for field in (
    "concept_ids",
    "variant_ids",
    "citation_ids",
    "premises",
    "exceptions",
    "alternatives",
  ):
    values = list(getattr(entry, field))
    changes: dict[str, Any] = {field: values}
    copy = replace(entry, **changes)
    values.clear()
    assert isinstance(getattr(copy, field), tuple)
  authors = ["外部作者"]
  source = replace(catalog.sources[0], authors=authors)  # type: ignore[arg-type]
  authors.clear()
  assert source.authors == ("外部作者",)
  aspects = [EvidenceAspect.规则]
  citation = replace(catalog.citations[0], aspects=aspects)  # type: ignore[arg-type]
  aspects.clear()
  assert citation.aspects == (EvidenceAspect.规则,)
  conditions = ["外部条件"]
  variant = replace(catalog.variants[0], conditions=conditions)  # type: ignore[arg-type]
  conditions.clear()
  assert variant.conditions == ("外部条件",)


@pytest.mark.parametrize(
  "identifier",
  ["CONCEPT.x", "concept.中文", "concept..x", "concept_x", " concept.x ", "source.other", ""],
)
def test_invalid_concept_identifiers(catalog: Catalog, identifier: str) -> None:
  with pytest.raises(ValueError):
    replace(catalog.concepts[0], id=identifier)


@pytest.mark.parametrize(
  "field,value,error",
  [
    ("name", " ", ValueError),
    ("name", None, TypeError),
    ("kind", "口径", TypeError),
    ("aliases", "文字不是别名序列", TypeError),
    ("aliases", {"别名"}, TypeError),
    ("aliases", (False,), TypeError),
    ("aliases", ("",), ValueError),
    ("aliases", ("重复", "重复"), ValueError),
    ("related_ids", ("source.synthetic",), ValueError),
  ],
)
def test_invalid_concept_fields(
  catalog: Catalog, field: str, value: Any, error: type[Exception]
) -> None:
  with pytest.raises(error):
    replace(catalog.concepts[0], **{field: value})


@pytest.mark.parametrize(
  "url",
  [
    "relative",
    "ftp://example.org",
    "https:///lost",
    "https://user@example.org",
    "https://example.org/a b",
  ],
)
def test_invalid_source_urls(catalog: Catalog, url: str) -> None:
  with pytest.raises(ValueError):
    replace(catalog.sources[0], url=url)


@pytest.mark.parametrize(
  "field,value,error",
  [
    ("status", "所列版本已核", TypeError),
    ("layer", "原文", TypeError),
    ("checked_on", None, ValueError),
    ("checked_on", datetime(2000, 1, 1), TypeError),
    ("authors", "作者", TypeError),
    ("lineage_id", "source.synthetic", ValueError),
    ("claims", "", ValueError),
    ("limits", None, TypeError),
  ],
)
def test_invalid_source_fields(
  catalog: Catalog, field: str, value: Any, error: type[Exception]
) -> None:
  with pytest.raises(error):
    replace(catalog.sources[0], **{field: value})


def test_unverified_source_can_retain_an_attempt_date_or_no_date(catalog: Catalog) -> None:
  source = replace(catalog.sources[0], status=SourceStatus.待核, checked_on=None)
  assert source.checked_on is None
  assert replace(source, checked_on=date(2001, 1, 1)).status is SourceStatus.待核


@pytest.mark.parametrize(
  "field,value,error",
  [
    ("aspects", (), ValueError),
    ("aspects", (EvidenceAspect.规则, EvidenceAspect.规则), ValueError),
    ("aspects", ("规则",), TypeError),
    ("quote", "", ValueError),
    ("source_id", "concept.synthetic", ValueError),
  ],
)
def test_invalid_citations(
  catalog: Catalog, field: str, value: Any, error: type[Exception]
) -> None:
  with pytest.raises(error):
    replace(catalog.citations[0], **{field: value})


@pytest.mark.parametrize(
  "field,value,error",
  [
    ("concept_ids", (), ValueError),
    ("concept_ids", ("entry.other",), ValueError),
    ("option", "全月归本月", TypeError),
    ("scope", "", ValueError),
  ],
)
def test_invalid_variants(catalog: Catalog, field: str, value: Any, error: type[Exception]) -> None:
  with pytest.raises(error):
    replace(catalog.variants[0], **{field: value})


@pytest.mark.parametrize(
  "field,value,error",
  [
    ("concept_ids", (), ValueError),
    ("premises", (), ValueError),
    ("alternatives", ("只有一读",), ValueError),
    ("premise_status", PremiseStatus.待定, ValueError),
    ("curation", CurationStatus.待整理, ValueError),
    ("layer", "仓内说明", TypeError),
    ("display", "可默认展示", TypeError),
    ("recheck", [], TypeError),
    ("tracking_url", [], TypeError),
    ("tracking_url", "relative", ValueError),
  ],
)
def test_invalid_entries(catalog: Catalog, field: str, value: Any, error: type[Exception]) -> None:
  with pytest.raises(error):
    replace(catalog.entries[0], **{field: value})


def test_withheld_entries_require_action_and_tracking(catalog: Catalog) -> None:
  with pytest.raises(ValueError, match="翻案条件"):
    replace(catalog.entries[0], display=DisplayEligibility.暂不默认展示)
  with pytest.raises(ValueError, match="URL"):
    replace(catalog.entries[0], display=DisplayEligibility.暂不默认展示, recheck="查原段")
  value = replace(catalog.entries[0], recheck="额外说明", tracking_url="https://example.org/track")
  assert value.display is DisplayEligibility.可默认展示


def test_duplicate_and_dangling_references_rejected(catalog: Catalog) -> None:
  with pytest.raises(ValueError, match="重复标识"):
    replace(catalog, concepts=(catalog.concepts[0], *catalog.concepts))
  for field, record in (
    ("concepts", replace(catalog.concepts[0], related_ids=("concept.unknown",))),
    ("variants", replace(catalog.variants[0], concept_ids=("concept.unknown",))),
    ("variants", replace(catalog.variants[0], school_ids=("concept.unknown",))),
    ("citations", replace(catalog.citations[0], source_id="source.unknown")),
    ("entries", replace(catalog.entries[0], concept_ids=("concept.unknown",))),
    ("entries", replace(catalog.entries[0], variant_ids=("variant.unknown",))),
    ("entries", replace(catalog.entries[0], citation_ids=("citation.unknown",))),
  ):
    with pytest.raises(KeyError):
      changes: dict[str, Any] = {field: (record,)}
      replace(catalog, **changes)
  with pytest.raises(ValueError, match="流派概念"):
    replace(catalog, variants=(replace(catalog.variants[0], school_ids=("concept.synthetic",)),))
  with pytest.raises(TypeError):
    replace(catalog, entries=(catalog.sources[0],))  # type: ignore[arg-type]


def test_default_eligibility_needs_explicit_verified_citations(catalog: Catalog) -> None:
  with pytest.raises(ValueError, match="已核来源"):
    replace(catalog, entries=(replace(catalog.entries[0], citation_ids=()),))
  with pytest.raises(ValueError, match="已核来源"):
    replace(catalog, sources=(replace(catalog.sources[0], status=SourceStatus.待核),))


def test_dangling_citation_is_rejected_even_without_entries(catalog: Catalog) -> None:
  with pytest.raises(KeyError):
    replace(
      catalog,
      entries=(),
      citations=(replace(catalog.citations[0], source_id="source.unknown"),),
    )


@pytest.mark.parametrize(
  "operation",
  [
    lambda c: c.get("entry.unknown"),
    lambda c: c.references("entry.unknown"),
    lambda c: c.filter_entries(source_id="source.unknown"),
    lambda c: c.filter_entries(source_id="concept.synthetic"),
    lambda c: c.filter_entries(default_only=1),
    lambda c: c.filter_entries(display="可默认展示"),
    lambda c: c.filter_sources(status="所列版本已核"),
    lambda c: c.filter_sources(aspect="查法"),
    lambda c: c.filter_sources(lineage_id="不是标识"),
    lambda c: c.list_concepts(kind="星曜"),
    lambda c: c.list_variants(concept_id="concept.unknown"),
    lambda c: c.list_variants(school_id="concept.synthetic"),
    lambda c: c.find(" "),
    lambda c: c.find(3),
    lambda c: c.get(None),
  ],
)
def test_invalid_query_inputs(catalog: Catalog, operation: Any) -> None:
  with pytest.raises((TypeError, ValueError, KeyError)):
    operation(catalog)


def test_quotes_are_not_normalized(catalog: Catalog) -> None:
  quote = "  舊字『戍』，\n原標記 * 不變。  "
  citation = replace(catalog.citations[0], quote=quote)
  assert replace(catalog, citations=(citation,)).references("entry.synthetic")[0].quote == quote


def test_empty_catalog_is_valid_but_does_not_resolve(catalog: Catalog) -> None:
  empty = Catalog(version="empty", concepts=(), variants=(), sources=(), citations=(), entries=())
  assert empty.records == ()
  assert empty.find("查询") == ()
  assert empty.filter_entries() == ()
  assert empty.filter_sources() == ()
  assert empty.list_variants() == ()
  assert empty.list_concepts() == ()
  with pytest.raises(ValueError):
    replace(catalog, version="")


def test_record_union_is_public() -> None:
  record: Record = load_catalog().concepts[0]
  assert record.id.startswith("concept.")
