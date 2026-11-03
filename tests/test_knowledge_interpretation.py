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
from ziwei.knowledge.model import (
  Citation,
  EvidenceAspect,
  KnowledgeEntry,
  PremiseStatus,
  Source,
  SourceStatus,
  TextLayer,
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


def test_interpretation_quotes_conditions_and_display(reference: dict[str, Any]) -> None:
  catalog = load_catalog()
  selected = catalog.filter_entries(source_id=reference["source_id"])
  assert {entry.id for entry in selected} == {item["id"] for item in reference["entries"]}
  for expected in reference["entries"]:
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
    assert entry.show_by_default is False
    assert entry.recheck and entry.tracking_url == reference["tracking_url"]
    assert citation.quote == expected["quote"]
    assert citation.locator == expected["locator"]
    assert citation.source_id == reference["source_id"]
    assert citation.layer is TextLayer.原文
    assert citation.aspects == (EvidenceAspect.解释,)
    assert catalog.references(entry.id) == (citation,)
    assert entry not in catalog.filter_entries(show_by_default=True)


@pytest.mark.parametrize(
  "name,concept_id", [("紫微", "concept.star.ziwei"), ("天府", "concept.star.tianfu")]
)
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


@pytest.mark.parametrize("defect", ["quote", "premise", "missing"])
def test_reference_gate_rejects_interpretation_damage(
  tmp_path: Path, reference: dict[str, Any], defect: str
) -> None:
  (tmp_path / "docs").mkdir()
  html = render_catalog(load_catalog())
  item = reference["entries"][-1]
  if defect == "quote":
    html = html.replace(escape(item["quote"]), "伪引文", 1)
  elif defect == "premise":
    html = html.replace(escape(item["premises"][-1]), "漏掉条件", 1)
  else:
    html = html.replace(f'id="{item["id"]}"', 'id="missing"', 1)
  (tmp_path / "docs/knowledge-reference.html").write_text(html, encoding="utf-8")
  with pytest.raises(ValueError):
    check_knowledge_reference(tmp_path)


@pytest.mark.parametrize("optimized", [False, True])
def test_interpretation_query_without_calendar(optimized: bool) -> None:
  command = [sys.executable, *(["-O"] if optimized else []), "-I"]
  command.append(str(Path(__file__).parent / "fixtures/interpretation_smoke.py"))
  result = subprocess.run(command, capture_output=True, text=True, check=True)
  assert result.stdout.strip() == "Interpretation query without celestial: passed"
