"""五节解释的原引、多概念、条件与独立查询。"""

import json
import subprocess
import sys
from dataclasses import replace
from html import escape
from pathlib import Path
from typing import Any, cast

import pytest

from tools import installed_check
from tools.knowledge_reference import render_catalog
from ziwei.knowledge import load_catalog
from ziwei.knowledge.catalog import Catalog
from ziwei.knowledge.model import (
  Citation,
  CurationStatus,
  EvidenceAspect,
  KnowledgeEntry,
  PremiseStatus,
)


@pytest.fixture
def minor_reference() -> dict[str, Any]:
  return cast(
    dict[str, Any],
    json.loads(
      (Path(__file__).parent / "fixtures/minor-interpretation-reference.json").read_text(
        encoding="utf-8"
      )
    ),
  )


def _check_minor(catalog: Catalog, reference: dict[str, Any]) -> None:
  assert catalog.find("天空") == ()
  for row in reference["entries"]:
    entry = catalog.get("entry.interpretation." + row["suffix"])
    assert isinstance(entry, KnowledgeEntry)
    assert entry.concept_ids == tuple("concept.star." + name for name in row["concepts"])
    assert entry.variant_ids == ()
    assert entry.statement == row["statement"]
    assert entry.premises == tuple(row["premises"])
    assert entry.exceptions == tuple(row["exceptions"])
    assert entry.premise_status is PremiseStatus[row["premise_status"]]
    assert entry.curation is CurationStatus.已整理 and not entry.show_by_default
    assert entry.limits and entry.recheck and entry.recheck != "以后再研究。"
    assert entry.tracking_url == "https://github.com/0xf3cd/ziwei/issues/11"
    expected_citations: tuple[str, ...] = ("citation.quanshu-juan1." + row["suffix"],)
    if row["suffix"].startswith("kongjie-"):
      expected_citations += ("citation.quanshu.kongjie", "citation.jielan.tiankong-year")
    assert entry.citation_ids == expected_citations
    citations = catalog.references(entry.id)
    assert {c.id for c in citations} == set(expected_citations)
    citation = catalog.get(expected_citations[0])
    assert isinstance(citation, Citation)
    assert citation.source_id == reference["source_id"]
    assert citation.aspects == (EvidenceAspect.解释,)
    assert citation.quote == row["quote"]
    assert citation.locator == "诸星问答论/" + row["section"] + "/" + row["part"]
    assert len(citation.quote) == row["end"] - row["start"] and row["start"] >= 0
    for concept_id in entry.concept_ids:
      assert entry in catalog.filter_entries(
        concept_id=concept_id, source_id=reference["source_id"]
      )


def test_five_sections_each_have_nature_and_condition(minor_reference: dict[str, Any]) -> None:
  rows = minor_reference["entries"]
  assert len(rows) == len({row["suffix"] for row in rows}) == 10
  assert len({row["section"] for row in rows}) == 5
  for section in {row["section"] for row in rows}:
    assert {row["kind"] for row in rows if row["section"] == section} == {"nature", "condition"}
  _check_minor(load_catalog(), minor_reference)


@pytest.mark.parametrize("index", range(10))
@pytest.mark.parametrize(
  "defect", ["quote", "concept", "premise", "exception", "status", "display", "missing"]
)
def test_minor_checks_reject_damage(
  minor_reference: dict[str, Any], index: int, defect: str
) -> None:
  catalog = load_catalog()
  _check_minor(catalog, minor_reference)
  row = minor_reference["entries"][index]
  identifier = "entry.interpretation." + row["suffix"]
  if defect == "quote":
    catalog = replace(
      catalog,
      citations=tuple(
        replace(c, quote="错误原文") if c.id == "citation.quanshu-juan1." + row["suffix"] else c
        for c in catalog.citations
      ),
    )
  elif defect == "missing":
    catalog = replace(catalog, entries=tuple(e for e in catalog.entries if e.id != identifier))
  else:
    changes: dict[str, Any]
    if defect == "concept":
      changes = {"concept_ids": ("concept.star.ziwei",)}
    elif defect == "premise":
      changes = {"premises": ("缺失条件",)}
    elif defect == "exception":
      changes = {"exceptions": ("错误例外",)}
    elif defect == "status":
      changes = {
        "premise_status": PremiseStatus.待定
        if row["premise_status"] == "已明确"
        else PremiseStatus.已明确,
      }
    else:
      changes = {"show_by_default": True, "premise_status": PremiseStatus.已明确}
    catalog = replace(
      catalog,
      entries=tuple(replace(e, **changes) if e.id == identifier else e for e in catalog.entries),
    )
  with pytest.raises((AssertionError, KeyError)):
    _check_minor(catalog, minor_reference)


def test_minor_reference_html_and_local_name(minor_reference: dict[str, Any]) -> None:
  catalog = load_catalog()
  html = render_catalog(catalog)
  for row in minor_reference["entries"]:
    assert html.count('<section id="entry.interpretation.' + row["suffix"] + '">') == 1
    assert html.count("<pre>" + escape(row["quote"]) + "</pre>") == 1
  assert catalog.find("天空") == ()
  assert tuple(s.id for s in catalog.filter_sources(aspect=EvidenceAspect.解释)) == (
    "source.quanshu-juan1-wikisource",
  )
  rule_citation = catalog.get("citation.quanshu.kongjie")
  assert isinstance(rule_citation, Citation)
  assert rule_citation.aspects == (EvidenceAspect.规则, EvidenceAspect.查法)


@pytest.mark.parametrize("optimized", [False, True])
def test_minor_query_without_native_calendar(optimized: bool) -> None:
  program = """
import builtins,sys
sys.path.insert(0,sys.argv[1])
original=builtins.__import__
def guarded(name,*args,**kwargs):
  if name.startswith("celestial_calendar"):
    raise RuntimeError("native calendar requested")
  return original(name,*args,**kwargs)
builtins.__import__=guarded
from ziwei.knowledge import load_catalog
c=load_catalog()
for name in ("天哭","天虚","天伤","天使","天刑","天姚","地空","地劫"):
  concept,=c.find(name)
  if len(c.filter_entries(concept_id=concept.id,source_id="source.quanshu-juan1-wikisource"))!=2:
    raise RuntimeError("missing minor interpretations")
if any(n.startswith("celestial_calendar") for n in sys.modules):
  raise RuntimeError("native calendar loaded")
print("Minor interpretations without celestial: passed")
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
  assert result.stdout.strip() == "Minor interpretations without celestial: passed"


@pytest.mark.parametrize("index", range(10))
@pytest.mark.parametrize(
  "defect", ["quote", "concept", "status", "display", "missing", "unknown-replacement"]
)
def test_installed_minor_consumer_rejects_damage(
  minor_reference: dict[str, Any],
  index: int,
  defect: str,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  installed_check.check_knowledge()
  catalog = load_catalog()
  row = minor_reference["entries"][index]
  identifier = "entry.interpretation." + row["suffix"]
  if defect == "quote":
    catalog = replace(
      catalog,
      citations=tuple(
        replace(c, quote="错误原文") if c.id == "citation.quanshu-juan1." + row["suffix"] else c
        for c in catalog.citations
      ),
    )
  elif defect == "missing":
    catalog = replace(catalog, entries=tuple(e for e in catalog.entries if e.id != identifier))
  else:
    changes: dict[str, Any]
    if defect == "concept":
      changes = {"concept_ids": ("concept.star.ziwei",)}
    elif defect == "status":
      changes = {
        "premise_status": PremiseStatus.待定
        if row["premise_status"] == "已明确"
        else PremiseStatus.已明确,
      }
    elif defect == "display":
      changes = {"show_by_default": True, "premise_status": PremiseStatus.已明确}
    else:
      changes = {"id": "entry.synthetic-unknown-minor"}
    catalog = replace(
      catalog,
      entries=tuple(replace(e, **changes) if e.id == identifier else e for e in catalog.entries),
    )
  monkeypatch.setattr(installed_check, "load_catalog", lambda: catalog)
  with pytest.raises(ValueError, match="interpretation"):
    installed_check.check_knowledge()


def test_global_tiankong_alias_is_rejected(minor_reference: dict[str, Any]) -> None:
  catalog = load_catalog()
  _check_minor(catalog, minor_reference)
  polluted = replace(
    catalog,
    concepts=tuple(
      replace(c, aliases=(*c.aliases, "天空")) if c.id == "concept.star.dikong" else c
      for c in catalog.concepts
    ),
  )
  with pytest.raises(AssertionError):
    _check_minor(polluted, minor_reference)
