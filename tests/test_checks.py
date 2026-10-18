"""开发检查必须发现的失败。"""

import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

from tools.check import check_documents, check_examples, check_wheel, document_errors, run


@pytest.fixture
def docs(tmp_path: Path) -> Path:
  (tmp_path / "docs").mkdir()
  (tmp_path / "docs/index.md").write_text("# 入口\n", encoding="utf-8")
  (tmp_path / "README.md").write_text("[指南](docs/index.md)\n", encoding="utf-8")
  return tmp_path


def test_valid_documents(docs: Path) -> None:
  check_documents(docs)


def test_empty_document_tree(tmp_path: Path) -> None:
  with pytest.raises(ValueError, match="docs must contain pages"):
    check_documents(tmp_path)


def test_docs_without_pages(docs: Path) -> None:
  (docs / "docs/index.md").unlink()
  (docs / "README.md").write_text("text\n", encoding="utf-8")
  with pytest.raises(ValueError, match="docs must contain pages"):
    check_documents(docs)


@pytest.mark.parametrize(
  "link", ["[missing](lost.md)", "![image](lost.png)", "[ref][r]\n\n[r]: lost.md"]
)
def test_broken_local_link(docs: Path, link: str) -> None:
  (docs / "README.md").write_text(link, encoding="utf-8")
  with pytest.raises(ValueError, match="Broken local link"):
    check_documents(docs)


def test_code_is_not_a_link(docs: Path) -> None:
  (docs / "README.md").write_text("`[sample](absent.md)`\n", encoding="utf-8")
  check_documents(docs)


def test_external_links_and_fragments(docs: Path) -> None:
  (docs / "README.md").write_text("[web](https://example.org) [anchor](#index)", encoding="utf-8")
  check_documents(docs)


def test_encoded_local_path(docs: Path) -> None:
  (docs / "a b.md").write_text("text", encoding="utf-8")
  (docs / "README.md").write_text("[file](a%20b.md)", encoding="utf-8")
  check_documents(docs)


def test_missing_readme(docs: Path) -> None:
  (docs / "README.md").unlink()
  assert any("Missing document" in error for error in document_errors(docs))


def test_command_failure_propagates(tmp_path: Path) -> None:
  with pytest.raises(subprocess.CalledProcessError) as caught:
    run((sys.executable, "-c", "raise SystemExit(7)"), cwd=tmp_path)
  assert caught.value.returncode == 7


@pytest.mark.parametrize(
  "report",
  [
    "",
    "Document: docs/contributing\n0 tests in 1 item.\n",
    "Document: docs/architecture\n2 tests in 1 item.\n",
  ],
)
def test_examples_cannot_be_empty(report: str) -> None:
  with pytest.raises(ValueError, match="docs/contributing"):
    check_examples(report)


@pytest.mark.parametrize("word", ["item", "items"])
def test_executed_examples(word: str) -> None:
  check_examples(f"Document: docs/contributing\n2 tests in 1 {word}.\n")


def test_document_word_in_doctest_group() -> None:
  check_examples(
    "Document: docs/contributing\n"
    "1 item passed all tests:\n   2 tests in Document: group\n2 tests in 1 item.\n"
  )


def test_other_document_counts_do_not_satisfy_contributing() -> None:
  report = (
    "Document: docs/contributing\n0 tests in 1 item.\nDocument: docs/index\n3 tests in 1 item.\n"
  )
  with pytest.raises(ValueError, match="docs/contributing"):
    check_examples(report)


@pytest.mark.parametrize(
  "missing", ["ziwei/__init__.py", "ziwei/py.typed", "a.dist-info/licenses/LICENSE"]
)
def test_incomplete_wheel(tmp_path: Path, missing: str) -> None:
  wheel = tmp_path / "test.whl"
  with ZipFile(wheel, "w") as archive:
    for path in ("ziwei/__init__.py", "ziwei/py.typed", "a.dist-info/licenses/LICENSE"):
      if path != missing:
        archive.writestr(path, "")
    archive.writestr("a.dist-info/METADATA", "Name: ziwei\nVersion: 0.0.0\n")
  with pytest.raises(ValueError, match="missing"):
    check_wheel(wheel, "0.0.0")


@pytest.mark.parametrize("name, version", [("ziwei", "9.0.0"), ("other", "0.0.0")])
def test_wrong_wheel_identity(tmp_path: Path, name: str, version: str) -> None:
  wheel = tmp_path / "test.whl"
  with ZipFile(wheel, "w") as archive:
    for path in ("ziwei/__init__.py", "ziwei/py.typed", "a.dist-info/licenses/LICENSE"):
      archive.writestr(path, "")
    archive.writestr("a.dist-info/METADATA", f"Name: {name}\nVersion: {version}\n")
  with pytest.raises(ValueError, match="identity"):
    check_wheel(wheel, "0.0.0")


@pytest.mark.parametrize("count", [0, 2])
def test_wheel_metadata_count(tmp_path: Path, count: int) -> None:
  wheel = tmp_path / "test.whl"
  with ZipFile(wheel, "w") as archive:
    for index in range(count):
      archive.writestr(f"{index}.dist-info/METADATA", "Name: ziwei\nVersion: 0.0.0\n")
  with pytest.raises(ValueError, match="one METADATA"):
    check_wheel(wheel, "0.0.0")
