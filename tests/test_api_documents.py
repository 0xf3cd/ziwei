"""拒绝被渲染成正文的 API 指令及缺失的签名。"""

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
