"""拒绝被渲染成正文的 API 指令及缺失的签名。"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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
def test_documented_final_is_public_but_unmarked_assignments_are_not(
  api_tree: Path, annotation: str
) -> None:
  (api_tree / "src/ziwei/sample.py").write_text(
    f'from typing import Final\nimport typing\nPublic: {annotation} = 1\n"""公开值。"""\n'
    f'_private: {annotation} = 2\n"""内部值。"""\n'
    f"Implementation: {annotation} = 3\nordinary = 4\n",
    encoding="utf-8",
  )
  page = api_tree / "docs/api.html"
  page.write_text('<p id="ziwei.sample.Public"></p>', encoding="utf-8")
  with pytest.raises(ValueError, match=r"ziwei\.sample\.Public"):
    check_api_reference(api_tree, api_tree)
  page.write_text(
    '<dt id="ziwei.sample.Public"></dt><dt id="extra.enum.member"></dt>', encoding="utf-8"
  )
  check_api_reference(api_tree, api_tree)


def _build_api(source: Path, output: Path) -> None:
  result = subprocess.run(
    [
      sys.executable,
      "-m",
      "sphinx",
      "-E",
      "-a",
      "-n",
      "-W",
      "--keep-going",
      "-b",
      "html",
      "-c",
      str(source / "docs"),
      str(source),
      str(output),
    ],
    cwd=Path(__file__).resolve().parents[1],
    check=False,
    text=True,
    capture_output=True,
  )
  assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture(scope="module")
def rendered_api(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
  root = Path(__file__).resolve().parents[1]
  source = tmp_path_factory.mktemp("api-source")
  shutil.copytree(root / "docs", source / "docs")
  shutil.copyfile(root / "README.md", source / "README.md")
  shutil.copyfile(root / "LICENSE", source / "LICENSE")
  output = tmp_path_factory.mktemp("api-html")
  _build_api(source, output)
  check_api_reference(output)
  return source, output


@pytest.mark.parametrize(
  "target",
  ["ziwei.serialization.SCHEMA_VERSION", "ziwei.config.POLICY_ENUMS", "ziwei.birth.BirthRecord"],
)
def test_removing_real_autodata_is_rejected(
  rendered_api: tuple[Path, Path], tmp_path: Path, target: str
) -> None:
  baseline, _ = rendered_api
  source = tmp_path / "source"
  shutil.copytree(baseline, source)
  page = source / "docs/api.md"
  original = page.read_text()
  changed, count = re.subn(
    rf"(?m)^\.\. autodata:: {re.escape(target)}\n(?:   :[^\n]*\n)*",
    "",
    original,
  )
  assert count == 1
  page.write_text(changed)
  output = tmp_path / "html"
  _build_api(source, output)
  with pytest.raises(ValueError, match=re.escape(target)):
    check_api_reference(output)
