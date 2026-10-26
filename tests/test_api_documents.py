"""拒绝被渲染成正文的 API 指令及缺失的签名。"""

import re
import shutil
from pathlib import Path

import pytest

from tools import check
from tools.check import check_api_reference


@pytest.fixture
def api_tree(tmp_path: Path) -> Path:
  source = tmp_path / "src/ziwei"
  source.mkdir(parents=True)
  (source / "sample.py").write_text(
    "class Value:\n  def check(self):\n    pass\ndef resolve():\n  pass\n", encoding="utf-8"
  )
  (tmp_path / "docs").mkdir()
  return tmp_path


def test_rendered_api_signatures(api_tree: Path) -> None:
  (api_tree / "docs/api.html").write_text(
    '<dt id="ziwei.sample.Value"></dt><dt id="ziwei.sample.Value.check"></dt>'
    '<dt id="ziwei.sample.resolve"></dt>',
    encoding="utf-8",
  )
  check_api_reference(api_tree, api_tree)


@pytest.mark.parametrize(
  "content",
  [
    "",
    "<p>.. py:class:: Value</p>",
    '<p>id="ziwei.sample.Value"</p>',
    '<dt id="ziwei.sample.Value"></dt><dt id="ziwei.sample.resolve"></dt>',
    '<div id="ziwei.sample.Value"></div>',
    '<span id="ziwei.sample.Value"></span><a id="ziwei.sample.Value.check"></a>'
    '<p id="ziwei.sample.resolve"></p>',
  ],
)
def test_plain_directives_or_missing_methods_are_rejected(api_tree: Path, content: str) -> None:
  (api_tree / "docs/api.html").write_text(content, encoding="utf-8")
  with pytest.raises(ValueError, match="missing signatures"):
    check_api_reference(api_tree, api_tree)


def test_api_gate_cannot_pass_with_no_source(api_tree: Path) -> None:
  (api_tree / "src/ziwei/sample.py").write_text("_internal = 1\n", encoding="utf-8")
  with pytest.raises(ValueError, match="No public API"):
    check_api_reference(api_tree, api_tree)


def test_nested_package_and_its_init_are_checked(api_tree: Path) -> None:
  package = api_tree / "src/ziwei/knowledge"
  package.mkdir()
  (package / "__init__.py").write_text("def load_catalog():\n  pass\n", encoding="utf-8")
  (package / "catalog.py").write_text(
    "class Catalog:\n  def find(self):\n    pass\n", encoding="utf-8"
  )
  path = api_tree / "docs/api.html"
  base = (
    '<dt id="ziwei.sample.Value"></dt><dt id="ziwei.sample.Value.check"></dt>'
    '<dt id="ziwei.sample.resolve"></dt>'
  )
  path.write_text(base, encoding="utf-8")
  with pytest.raises(ValueError, match="knowledge"):
    check_api_reference(api_tree, api_tree)
  path.write_text(
    base + '<dt id="ziwei.knowledge.load_catalog"></dt>'
    '<dt id="ziwei.knowledge.catalog.Catalog"></dt>'
    '<dt id="ziwei.knowledge.catalog.Catalog.find"></dt>',
    encoding="utf-8",
  )
  check_api_reference(api_tree, api_tree)


@pytest.mark.parametrize(
  "module,namespace",
  [
    ("knowledge/__init__.py", "ziwei.knowledge"),
    ("__init__.py", "ziwei"),
  ],
)
def test_init_api_is_required_without_another_nested_module(
  api_tree: Path, module: str, namespace: str
) -> None:
  source = api_tree / "src/ziwei" / module
  source.parent.mkdir(parents=True, exist_ok=True)
  source.write_text("def lookup():\n  pass\n", encoding="utf-8")
  page = api_tree / "docs/api.html"
  base = (
    '<dt id="ziwei.sample.Value"></dt><dt id="ziwei.sample.Value.check"></dt>'
    '<dt id="ziwei.sample.resolve"></dt>'
  )
  page.write_text(base, encoding="utf-8")
  with pytest.raises(ValueError, match=re.escape(namespace)):
    check_api_reference(api_tree, api_tree)
  page.write_text(base + f'<dt id="{namespace}.lookup"></dt>', encoding="utf-8")
  check_api_reference(api_tree, api_tree)


@pytest.mark.parametrize("annotation", ["TypeAlias", "typing.TypeAlias"])
def test_explicit_type_alias_has_a_real_api_signature(api_tree: Path, annotation: str) -> None:
  (api_tree / "src/ziwei/sample.py").write_text(
    f"import typing\nfrom typing import TypeAlias\nPublic: {annotation} = str | int\n"
    f"_private: {annotation} = str\n",
    encoding="utf-8",
  )
  page = api_tree / "docs/api.html"
  page.write_text('<p>id="ziwei.sample.Public"</p>', encoding="utf-8")
  with pytest.raises(ValueError, match=r"ziwei\.sample\.Public"):
    check_api_reference(api_tree, api_tree)
  page.write_text('<dt id="ziwei.sample.Public"></dt>', encoding="utf-8")
  check_api_reference(api_tree, api_tree)


@pytest.mark.parametrize("annotation", ["Final", "Final[int]", "typing.Final[str]"])
@pytest.mark.parametrize("comment", [False, True])
@pytest.mark.parametrize("prefix", ["", "# a\u2028b\n", "# a\fb\n", "# a\x85b\n"])
def test_documented_final_is_public_but_unmarked_assignments_are_not(
  api_tree: Path, annotation: str, comment: bool, prefix: str
) -> None:
  public = (
    f"#: 公开值。\nPublic: {annotation} = 1\n"
    if comment
    else f'Public: {annotation} = 1\n"""公开值。"""\n'
  )
  (api_tree / "src/ziwei/sample.py").write_text(
    "from typing import Final\nimport typing\n"
    + prefix
    + "def resolve():\n  pass\n"
    + public
    + f'_private: {annotation} = 2\n"""内部值。"""\n'
    f"Implementation: {annotation} = 3\nordinary = 4\n"
    f"#: 与下一项隔行，不是其说明\n\nSeparated: {annotation} = 5\n"
    f"# 普通注释\nUndocumented: {annotation} = 6\n",
    encoding="utf-8",
  )
  page = api_tree / "docs/api.html"
  page.write_text(
    '<dt id="ziwei.sample.resolve"></dt><p id="ziwei.sample.Public"></p>', encoding="utf-8"
  )
  with pytest.raises(ValueError, match=r"ziwei\.sample\.Public"):
    check_api_reference(api_tree, api_tree)
  page.write_text(
    '<dt id="ziwei.sample.resolve"></dt><dt id="ziwei.sample.Public"></dt>'
    '<dt id="extra.enum.member"></dt>',
    encoding="utf-8",
  )
  check_api_reference(api_tree, api_tree)


def _build_api(source: Path, output: Path) -> Path:
  with pytest.MonkeyPatch.context() as patch:
    patch.setattr(check, "ROOT", source)
    check.sphinx_report(output)
  return output / "html"


@pytest.fixture(scope="module")
def rendered_api(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
  root = Path(__file__).resolve().parents[1]
  source = tmp_path_factory.mktemp("api-source")
  shutil.copytree(root / "docs", source / "docs")
  shutil.copytree(root / "tools", source / "tools", ignore=shutil.ignore_patterns("__pycache__"))
  shutil.copyfile(root / "README.md", source / "README.md")
  shutil.copyfile(root / "LICENSE", source / "LICENSE")
  output = _build_api(source, tmp_path_factory.mktemp("api-build"))
  check_api_reference(output)
  return source, output


def _check_module_headings(output: Path) -> None:
  page = (output / "docs/api.html").read_text(encoding="utf-8")
  headings = {
    re.sub(r"<[^>]+>", "", heading).removesuffix("¶").strip()
    for heading in re.findall(r"<h[1-6]\b[^>]*>(.*?)</h[1-6]>", page, flags=re.DOTALL)
  }
  missing = {
    title
    for title in ("时标合同", "真太阳时", "解析顺序", "失败边界")
    if not any(heading == title or heading.startswith(title + "（") for heading in headings)
  }
  if missing:
    raise ValueError("API HTML is missing module headings: " + ", ".join(sorted(missing)))


def test_real_module_docstrings_render_as_headings(rendered_api: tuple[Path, Path]) -> None:
  _, output = rendered_api
  _check_module_headings(output)


def test_real_html_loads_the_document_layout_stylesheet(rendered_api: tuple[Path, Path]) -> None:
  source, output = rendered_api
  for page in ("api", "knowledge-reference", "chart"):
    html = (output / f"docs/{page}.html").read_text(encoding="utf-8")
    assert re.search(r'<link\b[^>]*href="\.\./_static/layout\.css(?:\?[^"\s]*)?"', html)
  assert (output / "_static/layout.css").read_bytes() == (
    source / "docs/_static/layout.css"
  ).read_bytes()


@pytest.mark.parametrize("markdown_module", [None, "ziwei.calendar", "ziwei.resolver"])
def test_module_heading_guard_distinguishes_rest_from_literal_markdown(
  rendered_api: tuple[Path, Path], tmp_path: Path, markdown_module: str | None
) -> None:
  baseline, _ = rendered_api
  source = tmp_path / "source"
  shutil.copytree(baseline, source)
  with (source / "docs/conf.py").open("a", encoding="utf-8") as config:
    config.write(
      f"\nmarkdown_module = {markdown_module!r}\n"
      "def module_heading_probe(app, what, name, obj, options, lines):\n"
      "  titles = {'ziwei.calendar': ('时标合同', '真太阳时'),\n"
      "            'ziwei.resolver': ('解析顺序', '失败边界')}.get(name, ())\n"
      "  text = '\\n'.join(lines) + '\\n'\n"
      "  for index, title in enumerate(titles):\n"
      "    rendered_title = f'{title}（{name}-{index}）'\n"
      "    heading = '## ' + title if name == markdown_module else rendered_title + '\\n' + '-' * 64\n"
      "    text, count = re.subn(r'(?m)^(?:## )?' + re.escape(title)\n"
      "                          + r'(?:（[^\\n]*）)?\\n(?:[-=~^]+\\n)?', heading + '\\n', text)\n"
      "    assert count == 1, (name, title, count)\n"
      "  lines[:] = text.splitlines()\n"
      "original_setup = setup\n"
      "def setup(app):\n"
      "  original_setup(app)\n"
      "  app.connect('autodoc-process-docstring', module_heading_probe)\n"
    )
  output = _build_api(source, tmp_path / "build")
  check_api_reference(output)
  if markdown_module is None:
    _check_module_headings(output)
  else:
    title = "时标合同" if markdown_module == "ziwei.calendar" else "解析顺序"
    assert f"## {title}" in (output / "docs/api.html").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match=title):
      _check_module_headings(output)


@pytest.mark.parametrize(
  "target",
  [
    "ziwei.decades.DECADE_RULE_ID",
    "ziwei.config.POLICY_ENUMS",
    "ziwei.birth.BirthRecord",
    "ziwei.birth.shichen_from_time",
  ],
)
def test_removing_real_api_declaration_is_rejected(
  rendered_api: tuple[Path, Path], tmp_path: Path, target: str
) -> None:
  baseline, _ = rendered_api
  source = tmp_path / "source"
  shutil.copytree(baseline, source)
  page = source / "docs/api.md"
  original = page.read_text(encoding="utf-8")
  if target == "ziwei.birth.shichen_from_time":
    changed, count = re.subn(r", shichen_from_time(?=\n)", "", original)
  else:
    changed, count = re.subn(
      rf"(?m)^\.\. autodata:: {re.escape(target)}\n(?:   :[^\n]*\n)*",
      "",
      original,
    )
  assert count == 1
  page.write_text(changed, encoding="utf-8")
  output = _build_api(source, tmp_path / "build")
  with pytest.raises(ValueError, match=re.escape(target)):
    check_api_reference(output)
