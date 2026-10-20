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
  if value is None:
    return "（无）"
  raise TypeError(f"Unsupported knowledge field type: {type(value).__name__}")


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
  for enumeration in config.POLICY_ENUMS:
    for option in enumeration:
      parts.append(f"<tr><td>{enumeration.__name__}</td><td>{escape(option.value)}</td></tr>")
  parts.append("</table></section>")
  parts.append('<section id="implemented-jiazi"><h2>六十甲子</h2><p>')
  parts.append(" ".join(str(item) for item in ganzhi.JIAZI))
  parts.append("</p></section>")
  parts.append('<section id="implemented-nayin"><h2>六十甲子纳音五行</h2><p>')
  pairs = (
    f"{ganzhi.JIAZI[index * 2]}{ganzhi.JIAZI[index * 2 + 1]}={ganzhi.NAYIN_ELEMENT[index].value}"
    for index in range(len(ganzhi.NAYIN_ELEMENT))
  )
  parts.append(" ".join(pairs))
  parts.append("</p></section>")
  parts.append('<section id="implemented-wuhu"><h2>五虎遁起寅</h2><p>')
  parts.append(
    "、".join(
      f"{pair[0][0].value}{pair[0][1].value}起{pair[1].value}寅" for pair in ganzhi.WUHU_YIN
    )
  )
  parts.append("</p></section>")
  return "\n".join(parts)


class KnowledgeTargets(HTMLParser):
  """保存实际元素、分节正文与链接，不接受注释或正文中的伪锚点。"""

  def __init__(self) -> None:
    super().__init__()
    self.targets: dict[str, list[str]] = {}
    self.text: dict[str, str] = {}
    self.links: list[str] = []
    self.members: dict[str, list[tuple[str, str]]] = {}
    self.rows: dict[str, list[tuple[str, ...]]] = {}
    self._sections: list[str | None] = []
    self._member_tag: str | None = None
    self._member_text: list[str] = []
    self._member_name = ""
    self._row: list[str] | None = None
    self._cell: list[str] | None = None

  def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    attributes = dict(attrs)
    identifier = attributes.get("id")
    if identifier is not None:
      self.targets.setdefault(identifier, []).append(tag)
    if tag == "section":
      self._sections.append(identifier)
    if tag in ("dt", "dd"):
      self._member_tag = tag
      self._member_text = []
    if tag == "tr":
      self._row = []
    if tag == "td" and self._row is not None:
      self._cell = []
    if tag == "a":
      href = attributes.get("href")
      if href is not None:
        self.links.append(href)

  def handle_endtag(self, tag: str) -> None:
    if tag == "td" and self._cell is not None and self._row is not None:
      self._row.append("".join(self._cell))
      self._cell = None
    if tag == "tr" and self._row is not None:
      if self._sections and self._sections[-1] is not None:
        self.rows.setdefault(self._sections[-1], []).append(tuple(self._row))
      self._row = None
    if tag == self._member_tag:
      text = "".join(self._member_text)
      if tag == "dt":
        self._member_name = text
      elif self._sections and self._sections[-1] is not None:
        self.members.setdefault(self._sections[-1], []).append((self._member_name, text))
        self._member_name = ""
      self._member_tag = None
      self._member_text = []
    if tag == "section" and self._sections:
      self._sections.pop()

  def handle_data(self, data: str) -> None:
    if self._cell is not None:
      self._cell.append(data)
    if self._member_tag is not None:
      self._member_text.append(data)
    for section in self._sections:
      if section is not None:
        self.text[section] = self.text.get(section, "") + data


def _member_text(value: object) -> str:
  if isinstance(value, str):
    return value
  if isinstance(value, date):
    return value.isoformat()
  if isinstance(value, tuple):
    return "、".join(_member_text(item) for item in value) or "（无）"
  if value is None:
    return "（无）"
  raise TypeError(f"Unsupported knowledge field type: {type(value).__name__}")


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
    expected = [
      (member.name, _member_text(getattr(record, member.name))) for member in fields(record)
    ]
    if parser.members.get(record.id) != expected:
      raise ValueError(f"Knowledge HTML lost or changed fields: {record.id}")
  options = [
    (enumeration.__name__, option.value)
    for enumeration in config.POLICY_ENUMS
    for option in enumeration
  ]
  if parser.rows.get("implemented-policies") != options:
    raise ValueError("Policy reference differs from definition")
  if " ".join(str(item) for item in ganzhi.JIAZI) not in parser.text.get("implemented-jiazi", ""):
    raise ValueError("Jiazi reference differs from definition")
  nayin = " ".join(
    f"{ganzhi.JIAZI[index * 2]}{ganzhi.JIAZI[index * 2 + 1]}={ganzhi.NAYIN_ELEMENT[index].value}"
    for index in range(len(ganzhi.NAYIN_ELEMENT))
  )
  if nayin not in parser.text.get("implemented-nayin", ""):
    raise ValueError("Nayin reference differs from definition")
  wuhu = "、".join(
    f"{pair[0][0].value}{pair[0][1].value}起{pair[1].value}寅" for pair in ganzhi.WUHU_YIN
  )
  if wuhu not in parser.text.get("implemented-wuhu", ""):
    raise ValueError("Wuhu reference differs from definition")
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
