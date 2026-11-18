"""独立阅读、正文检索与JSON消费；合成目录用于查询边界。"""

import json
from dataclasses import asdict, replace
from datetime import date
from typing import Any

import pytest

from ziwei.knowledge import load_catalog, 加载目录
from ziwei.knowledge.catalog import Catalog, 知识目录
from ziwei.knowledge.model import (
  Concept,
  ConceptKind,
  CurationStatus,
  KnowledgeEntry,
  PremiseStatus,
)


def test_read_leap_topic_and_compare_sources() -> None:
  catalog = load_catalog()
  topic = catalog.topic("concept.policy.leap-month")
  assert topic.entries == catalog.filter_entries(concept_id="concept.policy.leap-month")
  assert tuple(entry.id for entry in topic.entries) == (
    "entry.tianma.month-branch",
    "entry.leap-month.current",
    "entry.leap-month.next",
    "entry.leap-month.split",
    "entry.leap-month.month-stars-scope",
    "entry.star.month-policy-composition",
  )
  assert topic.get("concept.palace.minggong") == catalog.get("concept.palace.minggong")
  assert "entry.palace.minggong-shengong" not in {entry.id for entry in topic.entries}
  same_text = topic.get("entry.tianma.month-branch")
  assert isinstance(same_text, KnowledgeEntry)
  assert "按一路文本计" in same_text.limits
  source_ids = {c.source_id for c in topic.references(same_text.id)}
  sources = {source.lineage_id for source in topic.sources if source.id in source_ids}
  assert sources == {"lineage.jingcheng-golla", "lineage.zhongyi999-paimingpan"}
  for entry in topic.entries:
    assert entry.premises and entry.limits and entry.recheck
    assert not entry.show_by_default
    assert topic.references(entry.id) == catalog.references(entry.id)


def test_ambiguous_names_keep_separate_readings() -> None:
  catalog = load_catalog()
  variants = catalog.find("庚干四化")
  assert len(variants) == 3
  readings = [
    catalog.select_entries([item.id for item in catalog.filter_entries(variant_id=v.id)])
    for v in variants
  ]
  assert all(reading.entries and reading.citations for reading in readings)
  assert len({reading.entries[0].statement for reading in readings}) == 3
  assert catalog.find(" 天馬 ") == catalog.find("天马")
  assert catalog.find("ziwei") == catalog.find("ZIWEI") == catalog.find("紫微")
  assert catalog.find("没有此星") == ()


@pytest.mark.parametrize(
  "text,identifier",
  [
    ("六辛逢虎马", "entry.star.kuiyue-quanshu-pending"),
    ("春節", "entry.year-boundary.lunar-new-year"),
    ("春节", "entry.year-boundary.lunar-new-year"),
    ("前一位丑宫即安天空", "entry.star.tiankong-year"),
  ],
)
def test_real_body_and_quote_search(text: str, identifier: str) -> None:
  catalog = load_catalog()
  matches = catalog.search_entries(text)
  assert identifier in {entry.id for entry in matches}
  if text == "六辛逢虎马":
    (entry,) = matches
    assert text not in entry.statement
    assert any(text in citation.quote for citation in catalog.references(entry.id))
  assert catalog.search_entries(" " + text + " ") == matches
  assert catalog.search_entries("没有任何相同正文xyz") == ()


def test_search_intersection_and_order() -> None:
  catalog = load_catalog()
  filters: dict[str, Any] = dict(
    concept_id="concept.policy.leap-month",
    variant_id="variant.tianma.month-branch",
    source_id="source.zhongyi999-paimingpan",
    premise_status=PremiseStatus.已明确,
    show_by_default=False,
    curation=CurationStatus.已整理,
  )
  result = catalog.search_entries("月", **filters)
  assert [entry.id for entry in result] == ["entry.tianma.month-branch"]
  assert catalog.search_entries("月", **{**filters, "show_by_default": True}) == ()
  matches = catalog.search_entries("月")
  ids = {entry.id for entry in matches}
  assert matches == tuple(entry for entry in catalog.entries if entry.id in ids)


@pytest.mark.parametrize(
  "field",
  [
    "statement",
    "premises",
    "exceptions",
    "alternatives",
    "limits",
    "recheck",
    "quote",
    "locator",
    "citation_limits",
  ],
)
def test_each_search_field_and_no_cross_field_matches(field: str) -> None:
  catalog = load_catalog().select_entries(["entry.star.tiankong-year"])
  (entry,) = catalog.entries
  (citation,) = catalog.citations
  token = "UniqueNeedle"
  if field in ("quote", "locator", "citation_limits"):
    change: dict[str, Any] = {field.removeprefix("citation_"): token}
    citation = replace(citation, **change)
  else:
    value: Any = token
    if field in ("premises", "exceptions"):
      value = (token,)
    if field == "alternatives":
      value = (token, "other")
    entry = replace(entry, **{field: value})
  catalog = replace(catalog, entries=(entry,), citations=(citation,))
  assert catalog.search_entries("  UNIQUENEEDLE ") == (entry,)
  entry = replace(entry, statement="FieldEnd", limits="FieldStart")
  catalog = replace(catalog, entries=(entry,))
  assert catalog.search_entries("FieldEndFieldStart") == ()


def test_search_does_not_convert_scripts_or_search_names() -> None:
  catalog = load_catalog().select_entries(["entry.star.tiankong-year"])
  entry = replace(
    catalog.entries[0],
    statement="OnlyTraditional繁體",
    premises=("premise",),
    limits="limit",
    recheck="recheck",
  )
  catalog = replace(
    catalog,
    entries=(entry,),
    concepts=tuple(replace(c, name="NameOnly") for c in catalog.concepts),
  )
  assert catalog.search_entries("繁體") == (entry,)
  assert catalog.search_entries("繁体") == ()
  assert catalog.search_entries("NameOnly") == ()


@pytest.mark.parametrize("field", ["definition", "scope"])
def test_search_does_not_search_variant_descriptions(field: str) -> None:
  catalog = load_catalog()
  change: dict[str, Any] = {field: "VariantOnlyNeedle"}
  variant = replace(catalog.variants[0], **change)
  catalog = replace(catalog, variants=(variant, *catalog.variants[1:]))
  assert catalog.search_entries("VariantOnlyNeedle") == ()


@pytest.mark.parametrize("field", ["premises", "exceptions", "alternatives"])
def test_search_does_not_join_sequence_elements(field: str) -> None:
  catalog = load_catalog().select_entries(["entry.star.tiankong-year"])
  change: dict[str, Any] = {field: ("ElementEnd", "ElementStart")}
  entry = replace(catalog.entries[0], **change)
  catalog = replace(catalog, entries=(entry,))
  assert catalog.search_entries("ElementStart") == (entry,)
  assert catalog.search_entries("ElementEndElementStart") == ()


@pytest.mark.parametrize("index", [1, 2])
@pytest.mark.parametrize("field", ["quote", "locator", "limits"])
def test_search_all_citations_after_filtering_entries_by_source(index: int, field: str) -> None:
  catalog = load_catalog().select_entries(["entry.star.tiankong-year"])
  first = catalog.citations[0]
  other_source = replace(catalog.sources[0], id="source.other")
  citations = [
    first,
    replace(first, id="citation.other-second", source_id=other_source.id),
    replace(first, id="citation.other-third", source_id=other_source.id),
  ]
  change: dict[str, Any] = {field: "OtherSourceNeedle"}
  citations[index] = replace(citations[index], **change)
  entry = replace(catalog.entries[0], citation_ids=tuple(item.id for item in citations))
  catalog = replace(
    catalog,
    entries=(entry,),
    citations=tuple(citations),
    sources=(*catalog.sources, other_source),
  )
  assert catalog.search_entries("OtherSourceNeedle") == (entry,)
  assert catalog.search_entries("OtherSourceNeedle", source_id=first.source_id) == (entry,)


def test_selection_closes_variant_school_and_concept_references() -> None:
  catalog = load_catalog()
  identifiers = ["entry.liunian.sihua-wangtingzhi-lecture", "entry.brightness.quanshu-juan2"]
  selected = catalog.select_entries([*reversed(identifiers), identifiers[0]])
  assert selected.entries == tuple(item for item in catalog.entries if item.id in identifiers)
  assert selected.get("concept.school.zhongzhou") == catalog.get("concept.school.zhongzhou")
  for name in (
    "紫微",
    "天机",
    "太阳",
    "武曲",
    "天同",
    "廉贞",
    "天府",
    "太阴",
    "贪狼",
    "巨门",
    "天相",
    "天梁",
    "七杀",
    "破军",
  ):
    assert selected.find(name) == catalog.find(name)
  for concept in selected.concepts:
    for identifier in concept.related_ids:
      assert selected.get(identifier) == catalog.get(identifier)
  for group in ("concepts", "variants", "sources", "citations", "entries"):
    ids = {item.id for item in getattr(selected, group)}
    assert getattr(selected, group) == tuple(
      item for item in getattr(catalog, group) if item.id in ids
    )
  empty = catalog.select_entries([])
  assert empty.records == ()
  assert all(not value for value in empty.to_dict().values())


def test_topic_empty_content_outgoing_cycles_and_unreferenced_variant() -> None:
  concept = Concept(id="concept.a", name="A", kind=ConceptKind.宫位, related_ids=("concept.b",))
  other = replace(concept, id="concept.b", name="B", related_ids=("concept.a",))
  inbound = replace(concept, id="concept.c", name="C")
  variant = replace(
    load_catalog().variants[0],
    concept_ids=("concept.a",),
    school_ids=(),
    option=None,
  )
  catalog = Catalog(
    concepts=(other, inbound, concept),
    variants=(variant,),
    entries=(),
    sources=(),
    citations=(),
  )
  topic = catalog.topic("concept.a")
  assert topic.concepts == (other, concept)
  assert topic.variants == (variant,)
  assert topic.entries == ()
  assert topic.citations == ()
  assert topic.sources == ()
  assert catalog.topic("concept.c").concepts == (other, inbound, concept)


@pytest.mark.parametrize("query", ["", "  ", None, 1, b"text"])
def test_search_rejects_invalid_query(query: Any) -> None:
  with pytest.raises((TypeError, ValueError)):
    load_catalog().search_entries(query)


@pytest.mark.parametrize(
  "identifier,error",
  [
    ("Nope", ValueError),
    ("concept.missing", KeyError),
    ("entry.star.tiankong-year", ValueError),
    (None, TypeError),
  ],
)
def test_topic_rejects_invalid_identifier(identifier: Any, error: type[Exception]) -> None:
  with pytest.raises(error):
    load_catalog().topic(identifier)


@pytest.mark.parametrize(
  "identifiers,error",
  [
    ("entry.star.tiankong-year", TypeError),
    (None, TypeError),
    ([1], TypeError),
    (["Nope"], ValueError),
    (["entry.missing"], KeyError),
    (["concept.star.ziwei"], ValueError),
  ],
)
def test_selection_rejects_invalid_identifiers(
  identifiers: Any,
  error: type[Exception],
) -> None:
  with pytest.raises(error):
    load_catalog().select_entries(identifiers)


def _check_document(document: dict[str, Any], catalog: Catalog) -> None:
  expected = json.loads(json.dumps(asdict(catalog), default=date.isoformat))
  assert document == expected


@pytest.mark.parametrize("concept_id", [concept.id for concept in load_catalog().concepts])
def test_every_topic_preserves_entries_and_exported_fields(concept_id: str) -> None:
  catalog = load_catalog()
  topic = catalog.topic(concept_id)
  assert topic.get(concept_id) == catalog.get(concept_id)
  assert topic.entries == catalog.filter_entries(concept_id=concept_id)
  _check_document(topic.to_dict(), topic)


def test_json_consumer_preserves_every_field_and_returns_independent_containers() -> None:
  catalog = load_catalog()
  document: dict[str, Any] = catalog.to_dict()
  assert json.loads(json.dumps(document, ensure_ascii=False)) == document
  _check_document(document, catalog)
  assert document["sources"][0]["checked_on"] is None or isinstance(
    document["sources"][0]["checked_on"], str
  )
  assert any(v["option"] is None for v in document["variants"])
  assert any(e["alternatives"] == [] for e in document["entries"])
  document["concepts"][0]["related_ids"].clear()
  document["entries"][0]["premises"].clear()
  _check_document(catalog.to_dict(), catalog)


@pytest.mark.parametrize("defect", ["source", "premises", "lineage", "concept", "quote"])
def test_json_consumer_rejects_wrong_bindings_and_lost_context(defect: str) -> None:
  catalog = load_catalog().topic("concept.policy.leap-month")
  document: dict[str, Any] = catalog.to_dict()
  if defect == "source":
    citation = document["citations"][0]
    citation["source_id"] = next(
      source["id"] for source in document["sources"] if source["id"] != citation["source_id"]
    )
  elif defect == "premises":
    document["entries"][0]["premises"] = []
  elif defect == "lineage":
    document["sources"][0]["lineage_id"] = "lineage.invented-independent"
  elif defect == "concept":
    document["concepts"] = []
  else:
    document["citations"][0]["quote"] += "。"
  with pytest.raises(AssertionError):
    _check_document(document, catalog)


def test_chinese_names_are_original_objects() -> None:
  assert 加载目录 is load_catalog
  assert 知识目录 is Catalog
  for chinese, english in (
    ("读取主题", "topic"),
    ("检索条目", "search_entries"),
    ("选取条目", "select_entries"),
    ("转为字典", "to_dict"),
  ):
    assert getattr(知识目录, chinese) is getattr(Catalog, english)
  catalog = 加载目录()
  result = catalog.读取主题("concept.star.tiankong")
  assert result.检索条目("子年") == result.entries
  assert result.转为字典()["entries"][0]["id"] == "entry.star.tiankong-year"
