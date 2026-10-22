"""开发检查必须发现的失败。"""

import io
import re
import subprocess
import sys
import tarfile
import tomllib
from collections.abc import Sequence
from importlib.metadata import distribution
from pathlib import Path
from zipfile import ZipFile

import pytest
from packaging.specifiers import SpecifierSet

from tools import check
from tools.check import (
  built_artifacts,
  check_documents,
  check_examples,
  check_sdist,
  check_wheel,
  document_errors,
  run,
  source_members,
)

PKG_INFO = "Name: ziwei\nVersion: 0.0.0\n"
SOURCE = (
  "pyproject.toml",
  "src/ziwei/__init__.py",
  "src/ziwei/py.typed",
  "tools/check.py",
  ".github/workflows/checks.yml",
  ".github/workflows/release.yml",
)


@pytest.fixture
def docs(tmp_path: Path) -> Path:
  (tmp_path / "docs").mkdir()
  (tmp_path / "docs/index.md").write_text("# 入口\n", encoding="utf-8")
  (tmp_path / "README.md").write_text("[指南](docs/index.md)\n", encoding="utf-8")
  return tmp_path


def write_sdist(path: Path, members: dict[str, str], base: str = "ziwei-0.0.0") -> Path:
  with tarfile.open(path, "w:gz") as archive:
    for name, text in members.items():
      data = text.encode("utf-8")
      info = tarfile.TarInfo(f"{base}/{name}")
      info.size = len(data)
      archive.addfile(info, io.BytesIO(data))
  return path


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


def test_links_resolve_from_the_linking_page(docs: Path) -> None:
  (docs / "docs/guide").mkdir()
  (docs / "docs/guide/other.md").write_text("text\n", encoding="utf-8")
  page = docs / "docs/guide/intro.md"
  page.write_text("[兄弟](other.md) [上级](../index.md) [根](../../README.md)\n", encoding="utf-8")
  check_documents(docs)
  page.write_text("[不在本目录](index.md)\n", encoding="utf-8")
  with pytest.raises(ValueError, match=r"intro\.md: index\.md"):
    check_documents(docs)


def test_existing_non_markdown_targets(docs: Path) -> None:
  (docs / "docs/figure.png").write_bytes(b"")
  (docs / "LICENSE").write_text("MIT\n", encoding="utf-8")
  (docs / "README.md").write_text("![图](docs/figure.png) [许可](LICENSE)\n", encoding="utf-8")
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


def test_source_members_follow_the_tree(tmp_path: Path) -> None:
  for path in (
    "pyproject.toml",
    "src/ziwei/__init__.py",
    "src/ziwei/py.typed",
    "src/ziwei/stars/main.py",
    "tools/check.py",
    "tools/helper.sh",
    "tests/test_a.py",
    "docs/conf.py",
    "docs/python-stdlib.inv",
    "docs/index.md",
    "docs/guide/page.md",
    "docs/notes.txt",
  ):
    (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / path).touch()
  members = source_members(tmp_path)
  assert members == tuple(sorted(members))
  assert {
    "uv.lock",
    "src/ziwei/stars/main.py",
    "docs/guide/page.md",
    "docs/python-stdlib.inv",
    "tests/test_a.py",
  } <= set(members)
  assert {"tools/helper.sh", "docs/notes.txt"}.isdisjoint(members)


def test_valid_sdist(tmp_path: Path) -> None:
  members = {"PKG-INFO": PKG_INFO, **dict.fromkeys(SOURCE, "")}
  check_sdist(write_sdist(tmp_path / "ziwei-0.0.0.tar.gz", members), "0.0.0", SOURCE)


@pytest.mark.parametrize("missing", SOURCE)
def test_incomplete_sdist(tmp_path: Path, missing: str) -> None:
  members = {"PKG-INFO": PKG_INFO, **dict.fromkeys(set(SOURCE) - {missing}, "")}
  with pytest.raises(ValueError, match=f"missing: .*{re.escape(missing)}"):
    check_sdist(write_sdist(tmp_path / "ziwei-0.0.0.tar.gz", members), "0.0.0", SOURCE)


@pytest.mark.parametrize("name, version", [("ziwei", "9.0.0"), ("other", "0.0.0")])
def test_wrong_sdist_identity(tmp_path: Path, name: str, version: str) -> None:
  members = {"PKG-INFO": f"Name: {name}\nVersion: {version}\n", **dict.fromkeys(SOURCE, "")}
  with pytest.raises(ValueError, match="identity"):
    check_sdist(write_sdist(tmp_path / "ziwei-0.0.0.tar.gz", members), "0.0.0", SOURCE)


@pytest.mark.parametrize("base, with_metadata", [("ziwei-9.0.0", True), ("ziwei-0.0.0", False)])
def test_sdist_without_versioned_metadata(tmp_path: Path, base: str, with_metadata: bool) -> None:
  members = dict.fromkeys(SOURCE, "")
  if with_metadata:
    members["PKG-INFO"] = PKG_INFO
  with pytest.raises(ValueError, match="PKG-INFO"):
    check_sdist(write_sdist(tmp_path / "ziwei-0.0.0.tar.gz", members, base), "0.0.0", SOURCE)


def test_sdist_review_material_rejected(tmp_path: Path) -> None:
  members = {"PKG-INFO": PKG_INFO, ".review/notes.md": "x", **dict.fromkeys(SOURCE, "")}
  with pytest.raises(ValueError, match="review material"):
    check_sdist(write_sdist(tmp_path / "ziwei-0.0.0.tar.gz", members), "0.0.0", SOURCE)


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


@pytest.mark.parametrize(
  "names",
  [
    (),
    ("a.whl",),
    ("a.tar.gz",),
    ("a.whl", "b.whl", "a.tar.gz"),
    ("a.tar.gz", "b.tar.gz", "a.whl"),
  ],
)
def test_built_artifacts_require_one_pair(tmp_path: Path, names: tuple[str, ...]) -> None:
  for name in names:
    (tmp_path / name).touch()
  with pytest.raises(ValueError, match="one sdist and one wheel"):
    built_artifacts(tmp_path)


def test_built_artifacts_pair(tmp_path: Path) -> None:
  for name in ("ziwei-0.0.0.tar.gz", "ziwei-0.0.0-py3-none-any.whl"):
    (tmp_path / name).touch()
  assert built_artifacts(tmp_path) == (
    tmp_path / "ziwei-0.0.0.tar.gz",
    tmp_path / "ziwei-0.0.0-py3-none-any.whl",
  )


def test_distribution_dispatches_both_isolated_modes_outside_repository(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  calls: list[tuple[tuple[str, ...], Path]] = []
  source = tmp_path / "source"
  source.mkdir()
  (source / "pyproject.toml").write_bytes((check.ROOT / "pyproject.toml").read_bytes())
  monkeypatch.setattr(check, "ROOT", source)
  artifacts = tmp_path / "artifacts"
  artifacts.mkdir()
  sdist, wheel = artifacts / "ziwei.tar.gz", artifacts / "ziwei.whl"
  sdist.write_bytes(b"source")
  wheel.write_bytes(b"wheel")

  def fake_run(command: Sequence[str], *, cwd: Path = check.ROOT) -> None:
    calls.append((tuple(command), cwd))

  monkeypatch.setattr(check, "run", fake_run)
  monkeypatch.setattr(check, "built_artifacts", lambda path: (sdist, wheel))
  monkeypatch.setattr(check, "source_members", lambda path: ())
  monkeypatch.setattr(check, "check_sdist", lambda *args: None)
  monkeypatch.setattr(check, "check_wheel", lambda *args: None)
  check.check_distribution(tmp_path)
  python = (
    tmp_path / "consumer" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
  )
  script = str(check.ROOT / "tools/installed_check.py")
  version = tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8"))["project"][
    "version"
  ]
  assert calls[-2:] == [
    ((str(python), "-I", script, version), tmp_path),
    ((str(python), "-O", "-I", script, version), tmp_path),
  ]
  assert tmp_path != check.ROOT and not tmp_path.is_relative_to(check.ROOT)
  assert str(wheel) in calls[-3][0]
  assert "--no-deps" in calls[-3][0]
  assert "--require-hashes" in calls[-4][0]
  assert "--locked" in calls[-6][0] and "--no-emit-project" in calls[-6][0]
  assert "--no-isolation" in calls[0][0]


def test_build_backend_is_explicitly_in_the_locked_development_group() -> None:
  metadata = tomllib.loads((check.ROOT / "pyproject.toml").read_text(encoding="utf-8"))
  assert set(metadata["build-system"]["requires"]) <= set(metadata["dependency-groups"]["dev"])


def test_current_installed_metadata_matches_the_project() -> None:
  project = tomllib.loads((check.ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
  installed = distribution("ziwei")
  assert installed.metadata["Name"] == project["name"] == "ziwei"
  assert installed.version == project["version"]
  assert SpecifierSet(installed.metadata["Requires-Python"]) == SpecifierSet(
    project["requires-python"]
  )
  assert set(installed.requires or ()) == set(project["dependencies"])
  assert set(installed.metadata.get_all("Classifier") or ()) == set(project["classifiers"])
  assert set(installed.metadata.get_all("Project-URL") or ()) == {
    f"{name}, {url}" for name, url in project["urls"].items()
  }


def test_distribution_rejects_changes_during_consumption(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  artifacts = tmp_path / "artifacts"
  artifacts.mkdir()
  sdist, wheel = artifacts / "a.tar.gz", artifacts / "a.whl"
  sdist.write_bytes(b"source")
  wheel.write_bytes(b"wheel")
  monkeypatch.setattr(check, "run", lambda *args, **kwargs: None)
  monkeypatch.setattr(check, "check_sdist", lambda *args: None)
  monkeypatch.setattr(check, "check_wheel", lambda *args: None)
  monkeypatch.setattr(check, "install_and_consume", lambda *args: wheel.write_bytes(b"changed"))
  with pytest.raises(ValueError, match="changed during"):
    check.check_distribution(tmp_path, artifacts_dir=tmp_path / "kept")
  assert not (tmp_path / "kept").exists()


def test_retained_artifacts_preserve_the_pre_consumption_bytes(tmp_path: Path) -> None:
  files = (tmp_path / "a.tar.gz", tmp_path / "a.whl")
  for path in files:
    path.write_bytes(path.name.encode())
  hashes = {path: check.file_sha256(path) for path in files}
  kept = tmp_path / "kept"
  check.preserve_artifacts(hashes, kept)
  for path, digest in hashes.items():
    assert check.file_sha256(kept / "packages" / path.name) == digest
  assert len((kept / "SHA256SUMS").read_text().splitlines()) == 2
  with pytest.raises(ValueError, match="empty directory"):
    check.preserve_artifacts(hashes, kept)


def test_retaining_an_already_changed_file_fails(tmp_path: Path) -> None:
  path = tmp_path / "a.whl"
  path.write_bytes(b"original")
  original = check.file_sha256(path)
  path.write_bytes(b"changed")
  with pytest.raises(ValueError, match="changed during"):
    check.preserve_artifacts({path: original}, tmp_path / "kept")
  assert not (tmp_path / "kept/SHA256SUMS").exists()


def test_installed_consumption_refuses_a_repository_directory() -> None:
  with pytest.raises(ValueError, match="outside the repository"):
    check.install_and_consume(Path("a.whl"), "0.1.0", check.ROOT / "build/consumer")


def test_main_runs_every_gate_in_order(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
  calls: list[object] = []

  def fake_run(command: Sequence[str], *, cwd: Path = check.ROOT) -> None:
    calls.append(tuple(command[1:]))

  def fake_report(directory: Path) -> str:
    calls.append("sphinx_report")
    return "report"

  monkeypatch.setattr(check, "run", fake_run)
  monkeypatch.setattr(check, "check_documents", lambda: calls.append("check_documents"))
  monkeypatch.setattr(check, "sphinx_report", fake_report)
  monkeypatch.setattr(check, "check_examples", lambda report: calls.append(("examples", report)))
  monkeypatch.setattr(check, "check_api_reference", lambda directory: calls.append("api_reference"))
  monkeypatch.setattr(
    check, "check_knowledge_reference", lambda directory: calls.append("knowledge_reference")
  )
  monkeypatch.setattr(check, "check_distribution", lambda directory: calls.append("distribution"))
  monkeypatch.setenv("SCRATCH", str(tmp_path))
  check.main()
  assert calls == [
    ("-m", "ruff", "check", "."),
    ("-m", "ruff", "format", "--check", "."),
    ("-m", "mypy"),
    ("-m", "pytest", "--cov", "--cov-report=term-missing"),
    (
      "-O",
      "-m",
      "pytest",
      "-W",
      "ignore:assertions not in test modules or plugins:pytest.PytestConfigWarning",
    ),
    "check_documents",
    "sphinx_report",
    ("examples", "report"),
    "api_reference",
    "knowledge_reference",
    "distribution",
  ]


def test_main_stops_at_the_first_failure(monkeypatch: pytest.MonkeyPatch) -> None:
  calls: list[object] = []

  def fake_run(command: Sequence[str], *, cwd: Path = check.ROOT) -> None:
    calls.append(tuple(command[1:3]))
    if "mypy" in command:
      raise subprocess.CalledProcessError(1, command)

  monkeypatch.setattr(check, "run", fake_run)
  monkeypatch.setattr(check, "check_documents", lambda: calls.append("check_documents"))
  with pytest.raises(subprocess.CalledProcessError):
    check.main()
  assert calls[-1] == ("-m", "mypy")
  assert "check_documents" not in calls
