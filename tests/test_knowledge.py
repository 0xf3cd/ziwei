"""知识记录、状态分离、引用与独立查询。合成夹具不作为规则来源。"""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime
from typing import Any, cast

import pytest

from ziwei.config import DayRollover, LeapMonthPolicy, YearBoundary
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
    id="concept.synthetic",
    name="合成概念",
    aliases=("别名", "Alias"),
    kind=ConceptKind.口径,
    options=(LeapMonthPolicy.全月归本月,),
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
    layer=TextLayer.原文,
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
  assert catalog.version == "2026.10.19.2"
  assert {item.kind for item in catalog.concepts} == set(ConceptKind)
  assert len({item.id for item in catalog.records}) == len(catalog.records)
  assert catalog.find("天馬") == catalog.find("tianma")
  assert len(catalog.find("庚干四化")) == 3
  assert catalog.filter_entries(default_only=True) == ()
  pending = catalog.filter_entries(premise_status=PremiseStatus.待定)
  assert [item.id for item in pending] == ["entry.leap-month.month-stars-scope"]
  assert pending[0].alternatives == ("闰月例只约束命宫与身宫", "闰月例同时约束其他月系星")
  month = catalog.get("entry.tianma.month-branch")
  assert isinstance(month, KnowledgeEntry)
  assert month.premise_status is PremiseStatus.已明确
  assert month.alternatives == ()
  assert "不看节气" in month.statement
  for simplified, traditional in (
    ("闰月", "閏月"),
    ("子时", "子時"),
    ("年马", "年馬"),
    ("月马", "月馬"),
  ):
    assert catalog.find(simplified) == catalog.find(traditional)
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
  assert catalog.list_variants(concept_id="concept.school.synthetic") == catalog.variants
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
  assert catalog.filter_entries(concept_id="concept.school.synthetic") == catalog.entries
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
  with pytest.raises(KeyError, match=r"lineage\.other"):
    catalog.filter_sources(lineage_id="lineage.other")


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
  assert both.references("concept.school.synthetic") == catalog.citations
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


def test_variant_option_must_belong_to_its_concept(catalog: Catalog) -> None:
  variant = catalog.variants[0]
  with pytest.raises(ValueError, match="所关联概念"):
    replace(catalog, variants=(replace(variant, option=DayRollover.晚子时归次日),))
  with pytest.raises(ValueError, match="所关联概念"):
    replace(catalog, concepts=(replace(catalog.concepts[0], options=()), catalog.concepts[1]))
  with pytest.raises(ValueError, match="只有口径"):
    replace(catalog.concepts[0], kind=ConceptKind.星曜)
  with pytest.raises(ValueError, match="不可重复"):
    replace(catalog.concepts[0], options=(LeapMonthPolicy.全月归本月,) * 2)
  with pytest.raises(TypeError, match="口径枚举"):
    replace(catalog.concepts[0], options=(ConceptKind.口径,))  # type: ignore[arg-type]
  options = [LeapMonthPolicy.全月归本月]
  concept = replace(catalog.concepts[0], options=options)  # type: ignore[arg-type]
  options.clear()
  assert concept.options == (LeapMonthPolicy.全月归本月,)


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


def test_one_source_can_distinguish_original_text_and_commentary(catalog: Catalog) -> None:
  original = catalog.citations[0]
  annotation = replace(original, id="citation.annotation", layer=TextLayer.注释)
  entry = replace(catalog.entries[0], citation_ids=(original.id, annotation.id))
  mixed = replace(catalog, citations=(original, annotation), entries=(entry,))
  assert mixed.references(entry.id) == (original, annotation)
  assert [citation.layer for citation in mixed.references(entry.id)] == [
    TextLayer.原文,
    TextLayer.注释,
  ]
  assert mixed.sources[0].layer is TextLayer.原文
  with pytest.raises(TypeError):
    replace(original, layer="注释")  # type: ignore[arg-type]


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


def test_builtin_filters_intersect_individually_nonempty_sets() -> None:
  catalog = load_catalog()
  leap = "concept.policy.leap-month"
  school = "concept.school.zhongzhou"
  assert catalog.list_variants(concept_id=leap)
  assert catalog.list_variants(school_id=school)
  assert catalog.list_variants(concept_id=leap, school_id=school) == ()
  assert [
    variant.id
    for variant in catalog.list_variants(concept_id="concept.sihua.shengnian", school_id=school)
  ] == ["variant.sihua.geng-jiuqian-zhongzhou"]
  assert catalog.filter_entries(concept_id="concept.star.tianma")
  assert catalog.filter_entries(source_id="source.lifedna-flying")
  assert (
    catalog.filter_entries(concept_id="concept.star.tianma", source_id="source.lifedna-flying")
    == ()
  )
  assert catalog.filter_entries(variant_id="variant.leap-month.next")
  assert (
    catalog.filter_entries(concept_id="concept.star.tianma", variant_id="variant.leap-month.next")
    == ()
  )
  assert catalog.filter_sources(aspect=EvidenceAspect.系统归属)
  assert catalog.filter_sources(lineage_id="lineage.lifedna-flying")
  assert (
    catalog.filter_sources(aspect=EvidenceAspect.系统归属, lineage_id="lineage.lifedna-flying")
    == ()
  )
  assert "entry.tianma.month-branch" in {
    entry.id for entry in catalog.filter_entries(concept_id=leap)
  }


@pytest.mark.parametrize("simplified,traditional", [("命宫", "命宮"), ("天马", "天馬")])
def test_builtin_name_aliases_are_identical(simplified: str, traditional: str) -> None:
  catalog = load_catalog()
  assert catalog.find(simplified) == catalog.find(traditional)
  assert catalog.find(simplified)
  assert catalog.find("閏月歸屬") == ()
  assert catalog.find("晚子時") == ()


def test_option_can_match_a_later_concept_and_have_multiple_variants(catalog: Catalog) -> None:
  first = replace(
    catalog.variants[0], concept_ids=("concept.school.synthetic", "concept.synthetic")
  )
  second = replace(first, id="variant.second")
  shared = replace(catalog, variants=(first, second))
  assert shared.list_variants(concept_id="concept.synthetic") == (first, second)
  assert first.option is second.option is LeapMonthPolicy.全月归本月
  year = Concept(
    id="concept.year-boundary", name="合成换年", kind=ConceptKind.口径, options=tuple(YearBoundary)
  )
  variant = replace(
    first,
    id="variant.year-boundary",
    concept_ids=(year.id,),
    school_ids=(),
    option=YearBoundary.立春,
  )
  extended = replace(
    shared, concepts=(*shared.concepts, year), variants=(*shared.variants, variant)
  )
  assert extended.list_variants(concept_id=year.id) == (variant,)


def test_all_catalog_sequences_and_variant_relations_are_isolated(catalog: Catalog) -> None:
  for name in ("variants", "sources", "citations", "entries"):
    values = list(getattr(catalog, name))
    changes: dict[str, Any] = {name: values}
    copied = replace(catalog, **changes)
    values.clear()
    assert getattr(copied, name) == getattr(catalog, name)
    assert isinstance(getattr(copied, name), tuple)
  variant = catalog.variants[0]
  for name in ("concept_ids", "school_ids", "aliases"):
    values = list(getattr(variant, name))
    changes = {name: values}
    copied_variant = replace(variant, **changes)
    values.clear()
    assert getattr(copied_variant, name) == getattr(variant, name)
    assert isinstance(getattr(copied_variant, name), tuple)


def test_record_text_layers_are_independent(catalog: Catalog) -> None:
  source = replace(catalog.sources[0], layer=TextLayer.今人说明)
  citation = replace(catalog.citations[0], layer=TextLayer.注释)
  entry = replace(catalog.entries[0], layer=TextLayer.仓内说明)
  mixed = replace(catalog, sources=(source,), citations=(citation,), entries=(entry,))
  assert mixed.references(entry.id)[0].layer is TextLayer.注释
  assert mixed.sources[0].layer is TextLayer.今人说明
  assert mixed.entries[0].layer is TextLayer.仓内说明


@pytest.mark.parametrize(
  "member,alias",
  [
    (ConceptKind.STAR, "星曜"),
    (ConceptKind.PALACE, "宫位"),
    (ConceptKind.SIHUA, "四化"),
    (ConceptKind.WUXINGJU, "五行局"),
    (ConceptKind.POLICY, "口径"),
    (ConceptKind.SCHOOL, "流派"),
    (TextLayer.ORIGINAL, "原文"),
    (TextLayer.COMMENTARY, "注释"),
    (TextLayer.TRANSLATION, "译文"),
    (TextLayer.MODERN, "今人说明"),
    (TextLayer.EDITORIAL, "仓内说明"),
    (EvidenceAspect.SYSTEM, "系统归属"),
    (EvidenceAspect.RULE, "规则"),
    (EvidenceAspect.METHOD, "查法"),
    (SourceStatus.VERIFIED, "已核"),
    (SourceStatus.UNVERIFIED, "待核"),
    (PremiseStatus.COMPLETE, "已明确"),
    (PremiseStatus.UNRESOLVED, "待定"),
    (DisplayEligibility.DEFAULT, "可默认展示"),
    (DisplayEligibility.WITHHELD, "暂不默认展示"),
    (CurationStatus.DRAFT, "待整理"),
    (CurationStatus.CURATED, "已整理"),
  ],
)
def test_knowledge_chinese_alias_is_the_canonical_member(member: Any, alias: str) -> None:
  assert getattr(type(member), alias) is member
