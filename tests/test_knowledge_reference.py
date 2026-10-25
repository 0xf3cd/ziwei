"""参考页必须有真实锚点、完整正文与来自定义的表值。"""

import re
import shutil
import subprocess
import sys
from dataclasses import replace
from enum import StrEnum
from html import escape
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from docs import conf
from tools import knowledge_reference
from tools.knowledge_reference import (
  KnowledgeTargets,
  _member_text,
  _value,
  check_knowledge_reference,
  render_catalog,
)
from ziwei import config, ganzhi, stars
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
  "defect",
  ["missing", "fake", "duplicate", "quote", "premise", "policy", "jiazi", "nayin", "wuhu"],
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
  elif defect == "jiazi":
    before, after = text.split('<section id="implemented-jiazi">')
    text = before + '<section id="implemented-jiazi">' + after.replace("甲子", "假值")
  elif defect == "nayin":
    before, after = text.split('<section id="implemented-nayin">')
    text = before + '<section id="implemented-nayin">' + after.replace("甲子乙丑=金", "甲子乙丑=火")
  else:
    before, after = text.split('<section id="implemented-wuhu">')
    text = before + '<section id="implemented-wuhu">' + after.replace("甲己起丙寅", "甲己起戊寅")
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


@pytest.mark.parametrize(
  "identifier,member",
  [
    ("variant.leap-month.current", "definition"),
    ("variant.leap-month.current", "option"),
    ("source.lifedna-flying", "checked_on"),
    ("source.jingcheng-golla", "checked_on"),
    ("source.lifedna-flying", "authors"),
    ("concept.wuxingju", "kind"),
    ("concept.sihua.shengnian", "kind"),
    ("concept.sihua.shengnian", "aliases"),
    ("entry.tianma.month-branch", "id"),
  ],
)
def test_gate_rejects_missing_field_even_when_value_remains(
  html: Path, identifier: str, member: str
) -> None:
  page = html / "docs/knowledge-reference.html"
  text = page.read_text(encoding="utf-8")
  start = text.index(f'<section id="{identifier}">')
  end = text.index("</section>", start)
  section, count = re.subn(
    rf"<dt>{member}</dt><dd>.*?</dd>\n?", "", text[start:end], count=1, flags=re.S
  )
  assert count == 1
  page.write_text(text[:start] + section + text[end:], encoding="utf-8")
  with pytest.raises(ValueError, match="lost or changed fields"):
    check_knowledge_reference(html)


@pytest.mark.parametrize("defect", ["swap", "rename", "duplicate", "identical", "order", "none"])
def test_gate_rejects_wrong_field_association(html: Path, defect: str) -> None:
  page = html / "docs/knowledge-reference.html"
  text = page.read_text(encoding="utf-8")
  if defect == "swap":
    text = (
      text.replace("<dt>premises</dt>", "<dt>@@</dt>")
      .replace("<dt>exceptions</dt>", "<dt>premises</dt>")
      .replace("<dt>@@</dt>", "<dt>exceptions</dt>")
    )
  elif defect == "rename":
    text = text.replace("<dt>status</dt>", "<dt>layer</dt>")
  elif defect == "duplicate":
    text = text.replace("<dt>name</dt>", "<dt>name</dt><dd>重复</dd><dt>name</dt>", 1)
  elif defect in ("identical", "order"):
    pairs = re.findall(r"<dt>.*?</dt><dd>.*?</dd>", text)
    assert len(pairs) > 1
    if defect == "identical":
      text = text.replace(pairs[0], pairs[0] * 2, 1)
    else:
      text = (
        text.replace(pairs[0], "@@", 1).replace(pairs[1], pairs[0], 1).replace("@@", pairs[1], 1)
      )
  else:
    text = text.replace("<dt>option</dt><dd>（无）</dd>", "<dt>option</dt><dd></dd>", 1)
  page.write_text(text, encoding="utf-8")
  with pytest.raises(ValueError, match="lost or changed fields"):
    check_knowledge_reference(html)


@pytest.mark.parametrize("defect", ["label", "duplicate", "order"])
def test_policy_table_checks_the_enum_value_association(html: Path, defect: str) -> None:
  page = html / "docs/knowledge-reference.html"
  text = page.read_text(encoding="utf-8")
  start = text.index('<section id="implemented-policies">')
  end = text.index("</section>", start)
  section = text[start:end]
  rows = re.findall(r"<tr>.*?</tr>", section)
  assert len(rows) > 1
  if defect == "label":
    section = section.replace("<td>LeapMonthPolicy</td>", "<td>DayRollover</td>", 1)
  elif defect == "duplicate":
    section = section.replace(rows[1], rows[0], 1)
  else:
    section = (
      section.replace(rows[0], "@@", 1).replace(rows[1], rows[0], 1).replace("@@", rows[1], 1)
    )
  page.write_text(text[:start] + section + text[end:], encoding="utf-8")
  with pytest.raises(ValueError, match="Policy reference differs"):
    check_knowledge_reference(html)


@pytest.mark.parametrize("value", [True, 1, object()])
def test_unknown_field_types_are_not_silently_rendered_as_none(value: object) -> None:
  with pytest.raises(TypeError, match="Unsupported knowledge field type"):
    _value(value, set())
  with pytest.raises(TypeError, match="Unsupported knowledge field type"):
    _member_text(value)


@pytest.mark.parametrize(
  "quote",
  [
    "前段\n\n後段",
    "*前段* <>&\n\n    後段  ",
    "前段\n\n```\n````\n\n後段",
  ],
)
def test_multiline_quote_survives_the_real_sphinx_pipeline(tmp_path: Path, quote: str) -> None:
  root = Path(__file__).resolve().parents[1]
  source = tmp_path / "source"
  (source / "docs").mkdir(parents=True)
  for name in ("conf.py", "python-stdlib.inv"):
    shutil.copyfile(root / "docs" / name, source / "docs" / name)
  (source / "docs/index.md").write_text(
    "# 入口\n\n```{toctree}\nknowledge-reference\n```\n", encoding="utf-8"
  )
  (source / "docs/knowledge-reference.md").write_text("# 参考\n", encoding="utf-8")
  script = r"""
import sys
from pathlib import Path
from dataclasses import replace
root, source, output, quote = sys.argv[1:]
sys.path[:0] = [root, str(Path(root) / 'src')]
from ziwei.knowledge import data
data.CITATIONS = (replace(data.CITATIONS[0], quote=quote), *data.CITATIONS[1:])
from sphinx.cmd.build import main
raise SystemExit(main(['-E', '-a', '-n', '-W', '-q', '-b', 'html', '-c',
                      str(Path(source) / 'docs'), source, output]))
"""
  output = tmp_path / "html"
  result = subprocess.run(
    (sys.executable, "-I", "-c", script, str(root), str(source), str(output), quote),
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stdout + result.stderr
  catalog = load_catalog()
  catalog = replace(
    catalog, citations=(replace(catalog.citations[0], quote=quote), *catalog.citations[1:])
  )
  check_knowledge_reference(output, catalog)
  parser = KnowledgeTargets()
  parser.feed((output / "docs/knowledge-reference.html").read_text(encoding="utf-8"))
  assert dict(parser.members[catalog.citations[0].id])["quote"] == quote


def test_generation_reads_actual_definitions(html: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  catalog = load_catalog()
  monkeypatch.setattr(
    config,
    "POLICY_ENUMS",
    (StrEnum("LeapMonthPolicy", {"EXAMPLE": "测试替代口径"}), *config.POLICY_ENUMS[1:]),
  )
  monkeypatch.setattr(ganzhi, "JIAZI", tuple(reversed(ganzhi.JIAZI)))
  generated = render_catalog(catalog)
  assert "测试替代口径" in generated
  assert " ".join(str(item) for item in ganzhi.JIAZI) in generated
  with pytest.raises(ValueError, match="Policy reference differs"):
    check_knowledge_reference(html, catalog)
  (html / "docs/knowledge-reference.html").write_text(generated, encoding="utf-8")
  check_knowledge_reference(html, catalog)


@pytest.mark.parametrize(
  "rule_id, star",
  [
    ("variant.star.huoling-forward", None),
    ("variant.star.ziwei-bureau-day", None),
    ("variant.star.huoling-forward", "火星"),
  ],
)
def test_missing_numeric_group_fails_even_after_regeneration(
  html: Path, monkeypatch: pytest.MonkeyPatch, rule_id: str, star: str | None
) -> None:
  catalog = load_catalog()
  rows = knowledge_reference._star_rows()
  assert any(row[0] == rule_id and row[1] != "规则" for row in rows)
  monkeypatch.setattr(
    knowledge_reference,
    "_star_rows",
    lambda: [
      row
      for row in rows
      if row[0] != rule_id or row[1] == "规则" or (star is not None and row[2] != star)
    ],
  )
  (html / "docs/knowledge-reference.html").write_text(render_catalog(catalog), encoding="utf-8")
  with pytest.raises(ValueError, match="Star reference missing numeric coverage:") as error:
    check_knowledge_reference(html, catalog)
  assert rule_id in str(error.value)
  if star is not None:
    assert str((rule_id, star)) in str(error.value)


def test_new_rule_without_numeric_reference_is_rejected_by_reference_check(
  html: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  catalog = load_catalog()
  extra = replace(stars.STAR_RULES[0], id="variant.star.synthetic-uncovered")
  monkeypatch.setattr(stars, "STAR_RULES", (*stars.STAR_RULES, extra))
  (html / "docs/knowledge-reference.html").write_text(render_catalog(catalog), encoding="utf-8")
  with pytest.raises(ValueError, match="Star reference missing numeric coverage:") as error:
    check_knowledge_reference(html, catalog)
  assert extra.id in str(error.value)


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
