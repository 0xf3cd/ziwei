"""从知识记录与可执行定义生成参考页，检查实际HTML中的内容和链接。"""

from dataclasses import fields
from datetime import date
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from ziwei import config, ganzhi
from ziwei.knowledge import load_catalog
from ziwei.knowledge.catalog import Catalog


def _value(value: object, ids: set[str]) -> str:
  if isinstance(value, str):
    text = escape(value)
    if value in ids:
      return f'<a href="#{value}">{text}</a>'
    return f'<a href="{text}">{text}</a>' if value.startswith(("https://", "http://")) else text
  if isinstance(value, tuple):
    return "、".join(_value(item, ids) for item in value) or "（无）"
  if isinstance(value, date):
    return value.isoformat()
  return "（无）"


def render_catalog(catalog: Catalog) -> str:
  """生成具有稳定记录锚点的HTML；原引文只作HTML转义。"""
  ids = {record.id for record in catalog.records}
  parts = [f"<p>语料版本：{escape(catalog.version)}</p>"]
  for title, records in (
    ("概念", catalog.concepts),
    ("变体", catalog.variants),
    ("来源", catalog.sources),
    ("引文", catalog.citations),
    ("条目", catalog.entries),
  ):
    parts.append(f"<h2>{title}</h2>")
    for record in records:
      parts.append(f'<section id="{record.id}"><h3>{record.id}</h3><dl>')
      for member in fields(record):
        value = getattr(record, member.name)
        rendered = f"<pre>{escape(value)}</pre>" if member.name == "quote" else _value(value, ids)
        parts.append(f"<dt>{member.name}</dt><dd>{rendered}</dd>")
      parts.append("</dl></section>")
  parts.append('<section id="implemented-policies"><h2>已实现的口径选项</h2><table>')
  for enumeration in (config.LeapMonthPolicy, config.DayRollover, config.YearBoundary):
    for option in enumeration:
      parts.append(f"<tr><td>{enumeration.__name__}</td><td>{escape(option.value)}</td></tr>")
  parts.append("</table></section>")
  parts.append('<section id="implemented-jiazi"><h2>六十甲子</h2><p>')
  parts.append(" ".join(str(item) for item in ganzhi.JIAZI))
  parts.append("</p></section>")
  return "\n".join(parts)


class KnowledgeTargets(HTMLParser):
  """保存实际元素、分节正文与链接，不接受注释或正文中的伪锚点。"""

  def __init__(self) -> None:
    super().__init__()
    self.targets: dict[str, list[str]] = {}
    self.text: dict[str, str] = {}
    self.links: list[str] = []
    self._sections: list[str | None] = []

  def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    attributes = dict(attrs)
    identifier = attributes.get("id")
    if identifier is not None:
      self.targets.setdefault(identifier, []).append(tag)
    if tag == "section":
      self._sections.append(identifier)
    if tag == "a":
      href = attributes.get("href")
      if href is not None:
        self.links.append(href)

  def handle_endtag(self, tag: str) -> None:
    if tag == "section" and self._sections:
      self._sections.pop()

  def handle_data(self, data: str) -> None:
    for section in self._sections:
      if section is not None:
        self.text[section] = self.text.get(section, "") + data


def check_knowledge_reference(directory: Path, catalog: Catalog | None = None) -> None:
  """核所有记录的实际正文、锚点、稳定引用，以及口径和甲子表的定义来源。"""
  if catalog is None:
    catalog = load_catalog()
  page = directory / "docs/knowledge-reference.html"
  parser = KnowledgeTargets()
  parser.feed(page.read_text(encoding="utf-8"))
  for record in catalog.records:
    if parser.targets.get(record.id) != ["section"]:
      raise ValueError(f"Missing or duplicate knowledge target: {record.id}")
    text = parser.text.get(record.id, "")
    for member in fields(record):
      value = getattr(record, member.name)
      values = value if isinstance(value, tuple) else (value,)
      for part in values:
        if isinstance(part, str | date) and str(part) not in text:
          raise ValueError(f"Knowledge HTML lost {record.id}.{member.name}")
  for enumeration in (config.LeapMonthPolicy, config.DayRollover, config.YearBoundary):
    for option in enumeration:
      if option.value not in parser.text.get("implemented-policies", ""):
        raise ValueError(f"Policy reference differs from definition: {option.value}")
  if " ".join(str(item) for item in ganzhi.JIAZI) not in parser.text.get("implemented-jiazi", ""):
    raise ValueError("Jiazi reference differs from definition")
  ids = {record.id for record in catalog.records}
  for document in directory.rglob("*.html"):
    links = KnowledgeTargets()
    links.feed(document.read_text(encoding="utf-8"))
    for href in links.links:
      url = urlsplit(href)
      fragment = unquote(url.fragment)
      if (
        url.scheme
        or url.netloc
        or not fragment.startswith(("concept.", "variant.", "source.", "citation.", "entry."))
      ):
        continue
      target = document.parent / unquote(url.path) if url.path else document
      if target.resolve() != page.resolve() or fragment not in ids:
        raise ValueError(f"Unknown knowledge reference in {document.name}: {href}")
