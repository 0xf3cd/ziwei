"""核对卷一十八节的原引、主体、条目中须保留的语义片段与主题消费。"""

import json
import subprocess
import sys
from dataclasses import replace
from html import escape
from pathlib import Path
from typing import Any, cast

import pytest

from tools.installed_check import INTERPRETATION_ENTRY_COUNT
from tools.knowledge_reference import render_catalog
from ziwei.knowledge import load_catalog
from ziwei.knowledge.catalog import Catalog
from ziwei.knowledge.model import (
  Citation,
  Concept,
  ConceptKind,
  CurationStatus,
  EvidenceAspect,
  KnowledgeEntry,
  PremiseStatus,
  Source,
  SourceStatus,
  TextLayer,
)


@pytest.fixture
def reference() -> dict[str, Any]:
  return cast(
    dict[str, Any],
    json.loads(
      (Path(__file__).parent / "fixtures/juan1-interpretation-reference.json").read_text(
        encoding="utf-8"
      )
    ),
  )


def _check_entries(catalog: Catalog, reference: dict[str, Any]) -> None:
  source = catalog.get(reference["source_id"])
  assert isinstance(source, Source)
  assert source.lineage_id == "lineage.quanshu-wikisource"
  assert source.status is SourceStatus.已核 and source.layer is TextLayer.原文
  assert f"oldid={reference['revision']}" in source.url
  assert "纸本底本" in source.limits and "署名" in source.limits
  for name in (
    "文昌",
    "文曲",
    "流年昌曲",
    "左辅",
    "右弼",
    "天魁天钺",
    "禄存",
    "天马",
    "化禄",
    "化权",
    "化科",
    "化忌",
    "擎羊",
    "陀罗",
    "羊陀二星总论",
    "火星",
    "铃星",
    "羊陀火铃四星总论",
  ):
    assert name in source.claims
  for row in reference["entries"]:
    entry = catalog.get("entry.interpretation." + row["suffix"])
    assert isinstance(entry, KnowledgeEntry)
    assert entry.concept_ids == tuple(row["concept_ids"])
    assert entry.variant_ids == ()
    assert entry.citation_ids == tuple(c["id"] for c in row["citations"])
    expected_status = PremiseStatus.已明确 if row["kind"] == "nature" else PremiseStatus.待定
    assert entry.premise_status is expected_status
    assert entry.curation is CurationStatus.已整理 and not entry.show_by_default
    assert entry.statement and entry.premises and entry.limits and entry.recheck
    assert entry.recheck != "以后再研究。"
    assert entry.tracking_url == "https://github.com/0xf3cd/ziwei/issues/11"
    assert row["required"]["statement"] and row["required"]["premises"]
    for field, fragments in row["required"].items():
      value = getattr(entry, field)
      text = "\n".join(value) if isinstance(value, tuple) else value
      assert all(fragment in text for fragment in fragments), (entry.id, field)
    for expected in row["citations"]:
      citation = catalog.get(expected["id"])
      assert isinstance(citation, Citation)
      assert citation.source_id == source.id
      assert citation.layer is TextLayer.原文
      assert citation.aspects == (EvidenceAspect.解释,)
      assert citation.quote == expected["quote"] and citation.quote != entry.statement
      assert citation.locator == "诸星问答论/" + row["section"] + "/" + expected["part"]
      assert citation.limits
      spans = expected["spans"]
      assert all(0 <= s["start"] < s["end"] for s in spans)
      assert [s["line"] for s in spans] == list(range(spans[0]["line"], spans[-1]["line"] + 1))
      assert len(citation.quote) == sum(s["end"] - s["start"] for s in spans) + len(spans) - 1
    for concept_id in entry.concept_ids:
      assert entry in catalog.filter_entries(concept_id=concept_id, source_id=source.id)
  annual = catalog.get("entry.interpretation.liunian-changqu")
  assert isinstance(annual, KnowledgeEntry)
  assert len(annual.alternatives) == 2
  assert "年度禄存" in annual.alternatives[0] and "年度化禄" in annual.alternatives[1]
  assert all("待核" in option for option in annual.alternatives)


def test_reference_covers_eighteen_sections(reference: dict[str, Any]) -> None:
  rows = reference["entries"]
  assert len(rows) == len({r["suffix"] for r in rows}) == 33
  assert len({r["section"] for r in rows}) == 18
  citations = [c["id"] for r in rows for c in r["citations"]]
  assert len(citations) == len(set(citations)) == 34
  single = {"问流年昌曲若何？", "羊陀二星总论", "羊陀火铃四星总论"}
  for section in {r["section"] for r in rows}:
    kinds = [r["kind"] for r in rows if r["section"] == section]
    assert sorted(kinds) == (["condition"] if section in single else ["condition", "nature"])
  _check_entries(load_catalog(), reference)


def test_installed_count_matches_three_reference_groups(reference: dict[str, Any]) -> None:
  fixtures = Path(__file__).parent / "fixtures"
  groups = [reference["entries"]]
  for filename in ("interpretation-reference.json", "minor-interpretation-reference.json"):
    groups.append(json.loads((fixtures / filename).read_text(encoding="utf-8"))["entries"])
  assert sum(len(group) for group in groups) == INTERPRETATION_ENTRY_COUNT


@pytest.mark.parametrize("index", range(33))
def test_all_entries_survive_topic_selection_and_json(
  index: int, reference: dict[str, Any]
) -> None:
  catalog = load_catalog()
  row = reference["entries"][index]
  identifier = "entry.interpretation." + row["suffix"]
  for concept_id in row["concept_ids"]:
    topic = catalog.topic(concept_id)
    matched = topic.search_entries(row["citations"][0]["quote"])
    assert identifier in {e.id for e in matched}
    selected = topic.select_entries([identifier])
    document = json.loads(json.dumps(selected.to_dict(), ensure_ascii=False))
    assert len(document["entries"]) == 1
    entry = document["entries"][0]
    assert entry["concept_ids"] == row["concept_ids"] and not entry["show_by_default"]
    original = catalog.get(identifier)
    assert isinstance(original, KnowledgeEntry)
    for field in ("premises", "exceptions", "alternatives", "citation_ids"):
      assert entry[field] == list(getattr(original, field))
    assert entry["limits"] == original.limits and entry["recheck"] == original.recheck
    assert {c["id"]: c["quote"] for c in document["citations"]} == {
      c["id"]: c["quote"] for c in row["citations"]
    }
    assert [s["lineage_id"] for s in document["sources"]] == ["lineage.quanshu-wikisource"]


def test_new_topics_keep_annual_and_sihua_meanings_separate() -> None:
  catalog = load_catalog()
  (annual,) = catalog.find("流年昌曲")
  assert isinstance(annual, Concept) and annual.kind is ConceptKind.运限
  assert annual.related_ids == ("concept.star.wenchang", "concept.star.wenqu", "concept.liunian")
  assert [e.id for e in catalog.topic(annual.id).entries] == [
    "entry.interpretation.liunian-changqu"
  ]
  for name, suffix in (
    ("化祿", "hualu"),
    ("化權", "huaquan"),
    ("化科", "huake"),
    ("化忌", "huaji"),
  ):
    (concept,) = catalog.find(name)
    assert isinstance(concept, Concept) and concept.kind is ConceptKind.四化
    assert concept.id == "concept.sihua." + suffix
    assert catalog.find(concept.name) == (concept,)
    assert concept.related_ids == ("concept.sihua.shengnian", "concept.sihua.liunian")
    topic = catalog.topic(concept.id)
    assert len(topic.entries) == 2 and topic.variants == ()
    assert all(e.concept_ids == (concept.id,) for e in topic.entries)
  for concept_id in ("concept.sihua.shengnian", "concept.sihua.liunian", "concept.liunian"):
    assert not any(
      e.id.startswith("entry.interpretation.") for e in catalog.topic(concept_id).entries
    )
  for name in ("文昌", "文曲", "武曲", "贪狼"):
    (concept,) = catalog.find(name)
    entries = catalog.filter_entries(
      concept_id=concept.id, source_id="source.quanshu-juan1-wikisource"
    )
    assert len(entries) == 2 and all(e.concept_ids == (concept.id,) for e in entries)


@pytest.mark.parametrize(
  "suffix,field,old,new",
  [
    ("liunian-changqu", "concept_ids", "", "concept.star.wenchang"),
    ("wenqu-luchan", "concept_ids", "", "concept.sihua.huaji"),
    ("hualu-kequan", "concept_ids", "", "concept.sihua.shengnian"),
    ("huaquan-kelu", "concept_ids", "", "concept.sihua.liunian"),
    ("qingyang-rumiao", "concept_ids", "", "concept.sihua.huaji"),
    ("yangtuo-general", "concept_ids", "", "concept.sihua.huaji"),
    ("yangtuo-general", "concept_ids", "drop", ""),
    ("yangtuohuoling-general", "concept_ids", "drop", ""),
    ("yangtuohuoling-general", "concept_ids", "", "concept.star.wuqu"),
    ("yangtuohuoling-general", "concept_ids", "", "concept.star.tanlang"),
    ("liunian-changqu", "premises", "俱全", "无须齐全"),
    ("zuofu-zifu", "exceptions", "中局", "上局"),
    ("youbi-zifu", "exceptions", "下局", "上局"),
    ("kuiyue-xianbu", "exceptions", "四十以后", "任何年龄"),
    ("lucun-dushou", "premises", "无吉化", "有吉化"),
    ("tianma-erxian", "limits", "折鞭马", "吉马"),
    ("huoxing-tanlang", "premises", "三方无杀破", "无附加条件"),
    ("huoxing-tanlang", "statement", "中年后始兴", "少年即兴"),
    ("lingxing-tanlang", "statement", "官禄不宁", "官禄必吉"),
    ("huaji-sisha", "premises", "同宫又兼四杀共处", "单逢化忌"),
    ("liunian-changqu", "alternatives", "待核", "已定"),
    ("hualu-nature", "statement", "化禄节", "化忌节"),
    ("wenchang-nature", "premises", "文昌节答曰", "无关的非空文字"),
    ("liunian-changqu", "premises", "以流年科甲为主", "无须流年科甲"),
    ("yangtuo-general", "statement", "暗痣、眼痣", "其他结果"),
    ("yangtuohuoling-general", "statement", "一世招凶恶", "一世无凶恶"),
    ("lingxing-tanlang", "statement", "富贵不可论", "富贵"),
  ],
)
def test_check_rejects_misbinding_and_lost_conditions(
  reference: dict[str, Any], suffix: str, field: str, old: str, new: str
) -> None:
  catalog = load_catalog()
  _check_entries(catalog, reference)
  entry = catalog.get("entry.interpretation." + suffix)
  assert isinstance(entry, KnowledgeEntry)
  value = getattr(entry, field)
  if field == "concept_ids":
    changed = value[:-1] if old == "drop" else (*value, new)
  elif isinstance(value, str):
    assert old in value
    changed = value.replace(old, new)
  else:
    assert any(old in text for text in value)
    changed = tuple(text.replace(old, new) for text in value)
  changes: dict[str, Any] = {field: changed}
  damaged = replace(
    catalog,
    entries=tuple(replace(e, **changes) if e == entry else e for e in catalog.entries),
  )
  with pytest.raises(AssertionError):
    _check_entries(damaged, reference)


def test_check_rejects_same_section_statement_swap(reference: dict[str, Any]) -> None:
  catalog = load_catalog()
  _check_entries(catalog, reference)
  nature = catalog.get("entry.interpretation.hualu-nature")
  conditional = catalog.get("entry.interpretation.hualu-kequan")
  assert isinstance(nature, KnowledgeEntry) and isinstance(conditional, KnowledgeEntry)
  damaged = replace(
    catalog,
    entries=tuple(
      replace(entry, statement=conditional.statement) if entry == nature else entry
      for entry in catalog.entries
    ),
  )
  with pytest.raises(AssertionError, match=r"entry\.interpretation\.hualu-nature.*statement"):
    _check_entries(damaged, reference)


@pytest.mark.parametrize(
  "defect",
  [
    "character",
    "newline",
    "source",
    "lineage",
    "layer",
    "display",
    "status",
    "missing",
    "second-quote",
    "locator",
  ],
)
def test_check_rejects_source_and_record_damage(reference: dict[str, Any], defect: str) -> None:
  catalog = load_catalog()
  _check_entries(catalog, reference)
  citation = catalog.get("citation.quanshu-juan1.huoxing-tanlang")
  assert isinstance(citation, Citation)
  if defect == "locator":
    original = catalog.get("citation.quanshu-juan1.wenchang-nature")
    assert isinstance(original, Citation) and original.locator.endswith("答曰首分句")
    catalog = replace(
      catalog,
      citations=tuple(
        replace(c, locator=c.locator.replace("答曰首分句", "答曰末句")) if c == original else c
        for c in catalog.citations
      ),
    )
  elif defect in ("character", "newline", "source", "layer"):
    citation_changes: dict[str, dict[str, Any]] = {
      "character": {"quote": citation.quote.replace("贪", "貪")},
      "newline": {"quote": citation.quote.replace("\n\t", "")},
      "source": {"source_id": "source.quanshu-wikisource"},
      "layer": {"layer": TextLayer.今人说明},
    }
    changes = citation_changes[defect]
    catalog = replace(
      catalog,
      citations=tuple(replace(c, **changes) if c == citation else c for c in catalog.citations),
    )
  elif defect == "lineage":
    catalog = replace(
      catalog,
      sources=tuple(
        replace(s, lineage_id="lineage.synthetic-independent")
        if s.id == reference["source_id"]
        else s
        for s in catalog.sources
      ),
    )
  else:
    entry = catalog.get("entry.interpretation.lingxing-tanlang")
    assert isinstance(entry, KnowledgeEntry)
    entry_changes: dict[str, dict[str, Any]] = {
      "display": {"show_by_default": True, "premise_status": PremiseStatus.已明确},
      "status": {"premise_status": PremiseStatus.已明确},
      "missing": {},
      "second-quote": {"citation_ids": entry.citation_ids[:1]},
    }
    changes = entry_changes[defect]
    catalog = replace(
      catalog,
      entries=tuple(
        replace(e, **changes) if e == entry else e
        for e in catalog.entries
        if defect != "missing" or e != entry
      ),
    )
  with pytest.raises((AssertionError, KeyError)):
    _check_entries(catalog, reference)


def test_reference_html_preserves_quotes_and_shared_entry(reference: dict[str, Any]) -> None:
  html = render_catalog(load_catalog())
  for row in reference["entries"]:
    assert html.count('<section id="entry.interpretation.' + row["suffix"] + '">') == 1
    for citation in row["citations"]:
      assert html.count("<pre>" + escape(citation["quote"]) + "</pre>") == 1


@pytest.mark.parametrize("optimized", [False, True])
def test_new_topics_without_native_calendar(optimized: bool) -> None:
  program = """
import builtins,json,sys
sys.path.insert(0,sys.argv[1])
original=builtins.__import__
def guarded(name,*args,**kwargs):
  if name.startswith("celestial_calendar"):
    raise RuntimeError("native calendar requested")
  return original(name,*args,**kwargs)
builtins.__import__=guarded
from ziwei.knowledge import load_catalog
c=load_catalog()
for name,count in (("流年昌曲",1),("化祿",2),("火星",3)):
  concept,=c.find(name)
  entries=c.topic(concept.id).filter_entries(source_id="source.quanshu-juan1-wikisource")
  document=json.loads(json.dumps(c.select_entries([e.id for e in entries]).to_dict()))
  if len(document["entries"])!=count or not document["citations"]:
    raise RuntimeError("missing interpretations")
if any(n.startswith("celestial_calendar") for n in sys.modules):
  raise RuntimeError("native calendar loaded")
print("New interpretations without celestial: passed")
"""
  result = subprocess.run(
    [
      sys.executable,
      *(["-O"] if optimized else []),
      "-I",
      "-c",
      program,
      str(Path(__file__).resolve().parents[1] / "src"),
    ],
    check=True,
    capture_output=True,
    text=True,
  )
  assert result.stdout.strip() == "New interpretations without celestial: passed"
