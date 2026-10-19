"""参考页必须有真实锚点、完整正文与来自定义的表值。"""

from dataclasses import replace
from enum import StrEnum
from html import escape
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from docs import conf
from tools.knowledge_reference import KnowledgeTargets, check_knowledge_reference, render_catalog
from ziwei import config, ganzhi
from ziwei.knowledge import load_catalog


@pytest.fixture
def html(tmp_path: Path) -> Path:
  (tmp_path / "docs").mkdir()
  page = tmp_path / "docs/knowledge-reference.html"
  page.write_text(
    '<section id="outer">' + render_catalog(load_catalog()) + "</section>", encoding="utf-8"
  )
  return tmp_path


def test_actual_html_and_relative_stable_links(html: Path) -> None:
  (html / "docs/nested").mkdir()
  (html / "docs/nested/example.html").write_text(
    '<a href="../knowledge-reference.html#entry.tianma.year-branch">条目</a>'
    '<a href="https://example.org/#entry.unknown">外链</a><a href="#other">其他锚</a>',
    encoding="utf-8",
  )
  check_knowledge_reference(html)


@pytest.mark.parametrize(
  "defect", ["missing", "fake", "duplicate", "quote", "premise", "policy", "jiazi"]
)
def test_knowledge_gate_rejects_representative_defects(html: Path, defect: str) -> None:
  page = html / "docs/knowledge-reference.html"
  text = page.read_text(encoding="utf-8")
  catalog = load_catalog()
  identifier = catalog.records[0].id
  if defect == "missing":
    text = text.replace(f'id="{identifier}"', 'id="absent"', 1)
  elif defect == "fake":
    text = text.replace(f'<section id="{identifier}">', f'<div id="{identifier}">', 1)
  elif defect == "duplicate":
    text += f'<span id="{identifier}"></span>'
  elif defect == "quote":
    text = text.replace(escape(catalog.citations[0].quote), "伪引文")
  elif defect == "premise":
    text = text.replace(catalog.entries[0].premises[0], "漏掉前提")
  elif defect == "policy":
    before, after = text.split('<section id="implemented-policies">')
    text = (
      before
      + '<section id="implemented-policies">'
      + after.replace(config.LeapMonthPolicy.全月归下月.value, "假值")
    )
  else:
    before, after = text.split('<section id="implemented-jiazi">')
    text = before + '<section id="implemented-jiazi">' + after.replace("甲子", "假值")
  page.write_text(text, encoding="utf-8")
  with pytest.raises(ValueError, match=r"target|lost|definition"):
    check_knowledge_reference(html)


@pytest.mark.parametrize(
  "href",
  [
    "knowledge-reference.html#entry.unknown",
    "other.html#entry.tianma.year-branch",
    "knowledge-reference.html#citation.unknown",
    "#concept.unknown",
  ],
)
def test_unknown_reference_or_wrong_page_rejected(html: Path, href: str) -> None:
  (html / "docs/guide.html").write_text(f'<a href="{href}">坏引用</a>', encoding="utf-8")
  with pytest.raises(ValueError, match="Unknown knowledge reference"):
    check_knowledge_reference(html)


def test_generation_reads_actual_definitions(html: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  catalog = load_catalog()
  monkeypatch.setattr(
    config, "LeapMonthPolicy", StrEnum("LeapMonthPolicy", {"EXAMPLE": "测试替代口径"})
  )
  monkeypatch.setattr(ganzhi, "JIAZI", tuple(reversed(ganzhi.JIAZI)))
  generated = render_catalog(catalog)
  assert "测试替代口径" in generated
  assert " ".join(str(item) for item in ganzhi.JIAZI) in generated
  with pytest.raises(ValueError, match="Policy reference differs"):
    check_knowledge_reference(html, catalog)
  (html / "docs/knowledge-reference.html").write_text(generated, encoding="utf-8")
  check_knowledge_reference(html, catalog)


def test_quote_markup_and_whitespace_survive_rendering(html: Path) -> None:
  catalog = load_catalog()
  quote = "  原字<>&\n*標記*  "
  citation = replace(catalog.citations[0], quote=quote)
  catalog = replace(catalog, citations=(citation, *catalog.citations[1:]))
  generated = render_catalog(catalog)
  assert "&lt;&gt;&amp;" in generated
  parser = KnowledgeTargets()
  parser.feed("<section>无名外层" + generated + "</section></section><a>无链接</a>")
  assert quote in parser.text[citation.id]
  (html / "docs/knowledge-reference.html").write_text(generated, encoding="utf-8")
  check_knowledge_reference(html, catalog)


def test_sphinx_hook_only_expands_reference_page() -> None:
  page = ["# 测试"]
  conf.insert_knowledge_reference(cast(Any, None), "docs/knowledge", page)
  assert page == ["# 测试"]
  conf.insert_knowledge_reference(cast(Any, None), "docs/knowledge-reference", page)
  assert "entry.tianma.year-branch" in page[0]
  calls: list[tuple[str, object]] = []

  class App:
    def connect(self, event: str, callback: object) -> None:
      calls.append((event, callback))

  conf.setup(cast(Any, App()))
  assert calls == [
    ("source-read", conf.insert_knowledge_reference),
    ("env-updated", conf.register_knowledge_targets),
  ]
  environment = SimpleNamespace(metadata={})
  conf.register_knowledge_targets(cast(Any, App()), cast(Any, environment))
  slugs = environment.metadata["docs/knowledge-reference"]["myst_slugs"]
  assert slugs["entry.tianma.year-branch"] == (
    None,
    "entry.tianma.year-branch",
    "entry.tianma.year-branch",
  )
  assert "entry.unknown" not in slugs
