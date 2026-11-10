"""解释知识的固定短引、条件、归属与独立消费。"""

import json
import subprocess
import sys
from dataclasses import replace
from html import escape
from pathlib import Path
from typing import Any, cast

import pytest

from tools.knowledge_reference import check_knowledge_reference, render_catalog
from ziwei.knowledge import load_catalog
from ziwei.knowledge.catalog import Catalog
from ziwei.knowledge.model import (
  Citation,
  CurationStatus,
  EvidenceAspect,
  KnowledgeEntry,
  PremiseStatus,
  Source,
  SourceStatus,
  TextLayer,
)

MAJOR_STARS = (
  ("紫微", "concept.star.ziwei"),
  ("天府", "concept.star.tianfu"),
  ("天机", "concept.star.tianji"),
  ("太阳", "concept.star.taiyang"),
  ("武曲", "concept.star.wuqu"),
  ("天同", "concept.star.tiantong"),
  ("廉贞", "concept.star.lianzhen"),
  ("太阴", "concept.star.taiyin"),
  ("贪狼", "concept.star.tanlang"),
  ("巨门", "concept.star.jumen"),
  ("天相", "concept.star.tianxiang"),
  ("天梁", "concept.star.tianliang"),
  ("七杀", "concept.star.qisha"),
  ("破军", "concept.star.pojun"),
)


@pytest.fixture
def reference() -> dict[str, Any]:
  value = json.loads(
    (Path(__file__).parent / "fixtures/interpretation-reference.json").read_text(encoding="utf-8")
  )
  return cast(dict[str, Any], value)


def test_interpretation_source_and_shared_lineage(reference: dict[str, Any]) -> None:
  catalog = load_catalog()
  source = catalog.get(reference["source_id"])
  assert isinstance(source, Source)
  assert source.url == reference["url"]
  assert f"oldid={reference['revision']}" in source.edition
  assert source.status is SourceStatus.已核
  assert source.layer is TextLayer.原文
  assert source.checked_on is not None
  assert source.lineage_id == reference["lineage_id"]
  assert "纸本底本" in source.limits and "署名" in source.limits
  assert catalog.filter_sources(aspect=EvidenceAspect.解释) == (source,)
  assert {item.id for item in catalog.filter_sources(lineage_id=source.lineage_id)} == {
    reference["source_id"],
    "source.quanshu-wikisource",
    "source.quanshu-juan3-wikisource",
  }


def test_reference_covers_each_major_star_twice(reference: dict[str, Any]) -> None:
  rows = reference["entries"]
  assert len(rows) == len({row["id"] for row in rows}) == 28
  assert len({row["citation_id"] for row in rows}) == 28
  assert {row["concept_id"] for row in rows} == {concept_id for _, concept_id in MAJOR_STARS}
  for _, concept_id in MAJOR_STARS:
    selected = [row for row in rows if row["concept_id"] == concept_id]
    assert len(selected) == 2
    assert {row["kind"] for row in selected} == {"nature", "condition"}
    for row in selected:
      assert (row["kind"] == "nature") == row["id"].endswith("-nature")
      expected = (
        "已明确"
        if row["kind"] == "nature" or row["id"] == "entry.interpretation.wuqu-tianfu"
        else "待定"
      )
      assert row["premise_status"] == expected


def _check_interpretations(catalog: Catalog, reference: dict[str, Any]) -> None:
  selected = catalog.filter_entries(source_id=reference["source_id"])
  assert {entry.id for entry in selected} == {item["id"] for item in reference["entries"]}
  for expected in reference["entries"]:
    assert 0 <= expected["quote_start"] < expected["quote_end"]
    assert len(expected["quote"]) == expected["quote_end"] - expected["quote_start"]
    entry = catalog.get(expected["id"])
    citation = catalog.get(expected["citation_id"])
    assert isinstance(entry, KnowledgeEntry) and isinstance(citation, Citation)
    assert entry.concept_ids == (expected["concept_id"],)
    assert entry.variant_ids == ()
    assert entry.citation_ids == (citation.id,)
    assert entry.statement == expected["statement"]
    assert entry.premises == tuple(expected["premises"])
    assert entry.exceptions == tuple(expected["exceptions"])
    assert entry.premise_status is PremiseStatus[expected["premise_status"]]
    assert entry.curation is CurationStatus.已整理
    assert entry.show_by_default is False
    assert entry.recheck and entry.tracking_url == reference["tracking_url"]
    assert entry.recheck == expected["recheck"]
    assert entry.limits == expected["limits"]
    assert citation.quote == expected["quote"]
    assert citation.locator == expected["locator"]
    assert citation.limits == expected["citation_limits"]
    assert citation.source_id == reference["source_id"]
    assert citation.layer is TextLayer.原文
    assert citation.aspects == (EvidenceAspect.解释,)
    assert catalog.references(entry.id) == (citation,)
    assert entry not in catalog.filter_entries(show_by_default=True)


def test_interpretation_quotes_conditions_and_display(reference: dict[str, Any]) -> None:
  _check_interpretations(load_catalog(), reference)


@pytest.mark.parametrize("name,concept_id", MAJOR_STARS)
def test_star_query_retains_placement_and_interpretation(
  name: str, concept_id: str, reference: dict[str, Any]
) -> None:
  catalog = load_catalog()
  (concept,) = catalog.find(name)
  assert concept.id == concept_id
  expected = {item["id"] for item in reference["entries"] if item["concept_id"] == concept_id}
  selected = catalog.filter_entries(concept_id=concept_id, source_id=reference["source_id"])
  assert {entry.id for entry in selected} == expected
  assert len(catalog.filter_entries(concept_id=concept_id)) > len(selected)


@pytest.mark.parametrize("name,concept_id", MAJOR_STARS[2:])
@pytest.mark.parametrize("defect", ["quote", "concept", "premise", "status", "display", "missing"])
def test_reference_rejects_new_star_damage(
  name: str, concept_id: str, defect: str, reference: dict[str, Any]
) -> None:
  catalog = load_catalog()
  row = next(
    row
    for row in reference["entries"]
    if row["concept_id"] == concept_id and row["kind"] == "condition"
  )
  entry = catalog.get(row["id"])
  assert isinstance(entry, KnowledgeEntry)
  if defect == "quote":
    catalog = replace(
      catalog,
      citations=tuple(
        replace(item, quote="错误原文") if item.id == row["citation_id"] else item
        for item in catalog.citations
      ),
    )
  elif defect == "missing":
    catalog = replace(catalog, entries=tuple(item for item in catalog.entries if item != entry))
  else:
    identifier = entry.id
    changes: dict[str, Any]
    if defect == "concept":
      changes = {"concept_ids": ("concept.star.ziwei",)}
    elif defect == "premise":
      changes = {"premises": entry.premises[:-1]}
    elif defect == "status":
      changes = {
        "premise_status": (
          PremiseStatus.待定
          if entry.premise_status is PremiseStatus.已明确
          else PremiseStatus.已明确
        )
      }
    else:
      identifier = next(
        row["id"]
        for row in reference["entries"]
        if row["concept_id"] == concept_id and row["kind"] == "nature"
      )
      changes = {"show_by_default": True}
    catalog = replace(
      catalog,
      entries=tuple(
        replace(item, **changes) if item.id == identifier else item for item in catalog.entries
      ),
    )
  with pytest.raises(AssertionError):
    _check_interpretations(catalog, reference)


@pytest.mark.parametrize("suffix", ["taiyang-fubi", "tiantong-fuzuo-birth", "qisha-changqu-fubi"])
def test_reference_rejects_lost_adjacent_condition(suffix: str, reference: dict[str, Any]) -> None:
  catalog = load_catalog()
  identifier = f"entry.interpretation.{suffix}"
  catalog = replace(
    catalog,
    entries=tuple(
      replace(item, exceptions=()) if item.id == identifier else item for item in catalog.entries
    ),
  )
  with pytest.raises(AssertionError):
    _check_interpretations(catalog, reference)


@pytest.mark.parametrize("index", range(28))
def test_reference_rejects_placeholder_recheck(index: int, reference: dict[str, Any]) -> None:
  catalog = load_catalog()
  identifier = reference["entries"][index]["id"]
  catalog = replace(
    catalog,
    entries=tuple(
      replace(item, recheck="以后再研究。") if item.id == identifier else item
      for item in catalog.entries
    ),
  )
  with pytest.raises(AssertionError):
    _check_interpretations(catalog, reference)


@pytest.mark.parametrize("defect", ["entry-limits", "citation-limits", "curation"])
def test_reference_rejects_incomplete_curation(defect: str, reference: dict[str, Any]) -> None:
  catalog = load_catalog()
  identifier = "entry.interpretation.tianji-tianliang"
  if defect == "citation-limits":
    catalog = replace(
      catalog,
      citations=tuple(
        replace(item, limits="仅记录天机。")
        if item.id == "citation.quanshu-juan1.tianji-tianliang"
        else item
        for item in catalog.citations
      ),
    )
  else:
    changes: dict[str, Any]
    if defect == "curation":
      changes = {"curation": CurationStatus.待整理}
    else:
      changes = {"limits": "仅记录天机。"}
    catalog = replace(
      catalog,
      entries=tuple(
        replace(item, **changes) if item.id == identifier else item for item in catalog.entries
      ),
    )
  with pytest.raises(AssertionError):
    _check_interpretations(catalog, reference)


def test_interpretation_aspect_rejects_string(reference: dict[str, Any]) -> None:
  citation = load_catalog().get(reference["entries"][0]["citation_id"])
  assert isinstance(citation, Citation)
  with pytest.raises(TypeError):
    replace(citation, aspects=(cast(Any, "解释"),))


def test_interpretation_reference_contains_quotes_and_conditions(reference: dict[str, Any]) -> None:
  html = render_catalog(load_catalog())
  for item in reference["entries"]:
    assert html.count(f'<section id="{item["id"]}">') == 1
    assert html.count(f"<pre>{escape(item['quote'])}</pre>") == 1
    assert all(escape(premise) in html for premise in item["premises"])
    assert all(escape(exception) in html for exception in item["exceptions"])


@pytest.mark.parametrize("defect", ["quote", "premise", "exception", "missing"])
def test_reference_gate_rejects_interpretation_damage(
  tmp_path: Path, reference: dict[str, Any], defect: str
) -> None:
  (tmp_path / "docs").mkdir()
  html = render_catalog(load_catalog())
  item = next(
    row for row in reference["entries"] if row["id"] == "entry.interpretation.tiantong-fuzuo-birth"
  )
  if defect == "quote":
    html = html.replace(escape(item["quote"]), "伪引文", 1)
  elif defect == "premise":
    html = html.replace(escape(item["premises"][-1]), "漏掉条件", 1)
  elif defect == "exception":
    html = html.replace(escape(item["exceptions"][0]), "漏掉例外", 1)
  else:
    html = html.replace(f'id="{item["id"]}"', 'id="missing"', 1)
  (tmp_path / "docs/knowledge-reference.html").write_text(html, encoding="utf-8")
  with pytest.raises(ValueError):
    check_knowledge_reference(tmp_path)


@pytest.mark.parametrize("optimized", [False, True])
def test_interpretation_query_without_calendar(optimized: bool) -> None:
  command = [sys.executable, *(["-O"] if optimized else []), "-I"]
  command.append(str(Path(__file__).parent / "fixtures/interpretation_smoke.py"))
  command.append(str(Path(__file__).resolve().parents[1] / "src"))
  result = subprocess.run(command, capture_output=True, text=True, check=True)
  message, checked = result.stdout.splitlines()
  assert message == "Interpretation query without celestial: passed"
  identifiers = json.loads(checked)
  assert len(identifiers) == 14
  assert set(identifiers) == {concept_id for _, concept_id in MAJOR_STARS}


def test_interpretation_query_rejects_wrong_source(tmp_path: Path) -> None:
  command = [
    sys.executable,
    "-I",
    str(Path(__file__).parent / "fixtures/interpretation_smoke.py"),
    str(tmp_path),
  ]
  result = subprocess.run(command, capture_output=True, text=True, check=False)
  assert result.returncode == 1
  assert "imported an unexpected source" in result.stderr
