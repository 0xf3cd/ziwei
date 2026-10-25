"""开发检查必须发现的失败。"""

import io
import os
import re
import shutil
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

from tools import artifacts, check, consumption
from tools.artifacts import (
  built_artifacts,
  check_sdist,
  check_wheel,
  source_members,
)
from tools.check import check_documents, check_examples, document_errors
from tools.consumption import run

PKG_INFO = "Name: ziwei\nVersion: 0.0.0\n"
SOURCE = (
  "pyproject.toml",
  "src/ziwei/__init__.py",
  "src/ziwei/py.typed",
  "tools/check.py",
  "tests/unit/test_nested.py",
  ".github/workflows/checks.yml",
  ".github/workflows/release.yml",
)


@pytest.mark.parametrize("mode", [(), ("-O",)])
def test_calendar_cleanup_fixture_is_opt_in_and_cleans_after_each_test(
  tmp_path: Path,
  mode: tuple[str, ...],
) -> None:
  """加载真实共享fixture：选用模块清理，未选用模块保留导入哨兵。"""
  source = Path(__file__).with_name("conftest.py")
  (tmp_path / "conftest.py").write_text(
    "from importlib.util import spec_from_file_location, module_from_spec\n"
    f"spec = spec_from_file_location('production_conftest', {str(source)!r})\n"
    "module = module_from_spec(spec)\nspec.loader.exec_module(module)\n"
    "unload_celestial = module.unload_celestial\n",
    encoding="utf-8",
  )
  for selected in (True, False):
    label = "selected" if selected else "unselected"
    marker = 'pytestmark = pytest.mark.usefixtures("unload_celestial")' if selected else ""
    comparison = "not in" if selected else "in"
    (tmp_path / f"test_{label}.py").write_text(
      "import sys\nfrom types import ModuleType\nimport pytest\n"
      f"{marker}\n"
      "def test_a_install_sentinel():\n"
      "  sys.modules['celestial_calendar.scope_probe'] = ModuleType('celestial_calendar.scope_probe')\n"
      "def test_b_observe_teardown_scope():\n"
      f"  assert 'celestial_calendar.scope_probe' {comparison} sys.modules\n",
      encoding="utf-8",
    )
  result = subprocess.run(
    (
      sys.executable,
      *mode,
      "-B",
      "-I",
      "-m",
      "pytest",
      "--confcutdir",
      str(tmp_path),
      "-p",
      "no:cacheprovider",
      "-q",
      str(tmp_path),
    ),
    cwd=tmp_path,
    env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stdout + result.stderr
  assert "4 passed" in result.stdout


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


@pytest.fixture
def sphinx_source(tmp_path: Path) -> Path:
  """隔离文档只提供输入；命令、严格参数和失败传播仍来自生产入口。"""
  source = tmp_path / "source"
  (source / "docs").mkdir(parents=True)
  (source / "docs/conf.py").write_text(
    'extensions = ["sphinx.ext.doctest"]\nmaster_doc = "index"\n', encoding="utf-8"
  )
  (source / "index.rst").write_text(
    "Production fixture\n==================\n\nproduction-fixture-marker\n\n"
    ".. doctest::\n\n   >>> 2 + 2\n   4\n",
    encoding="utf-8",
  )
  return source


def test_real_sphinx_entry_builds_both_outputs(
  sphinx_source: Path,
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setattr(check, "ROOT", sphinx_source)
  output = tmp_path / "output"
  report = check.sphinx_report(output)
  assert "production-fixture-marker" in (output / "html/index.html").read_text(encoding="utf-8")
  assert report == (output / "doctest/output.txt").read_text(encoding="utf-8")
  assert "Document: index" in report and "1 test" in report
  assert "0 failures in tests" in report


@pytest.mark.parametrize(
  "fault, builder",
  [
    ("directive-warning", "html"),
    ("reference-warning", "html"),
    ("doctest-warning", "doctest"),
    ("doctest-failure", "doctest"),
  ],
)
def test_real_sphinx_entry_propagates_builder_failure(
  sphinx_source: Path,
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
  fault: str,
  builder: str,
) -> None:
  page = sphinx_source / "index.rst"
  text = page.read_text(encoding="utf-8")
  if fault == "directive-warning":
    text += "\n.. unknown-production-directive::\n"
  elif fault == "reference-warning":
    text += "\n:py:class:`unknown_production_module.MissingType`\n"
  elif fault == "doctest-failure":
    text = text.replace("   4\n", "   5\n")
  else:
    config = sphinx_source / "docs/conf.py"
    config.write_text(
      config.read_text(encoding="utf-8")
      + """
from sphinx.util import logging
def warn_doctest(app):
  if app.builder.name == "doctest":
    logging.getLogger(__name__).warning("doctest-only-warning")
def setup(app):
  app.connect("builder-inited", warn_doctest)
""",
      encoding="utf-8",
    )
  page.write_text(text, encoding="utf-8")
  monkeypatch.setattr(check, "ROOT", sphinx_source)
  output = tmp_path / "output"
  with pytest.raises(subprocess.CalledProcessError) as caught:
    check.sphinx_report(output)
  assert caught.value.returncode == 1
  command = caught.value.cmd
  assert command[command.index("-b") + 1] == builder
  if builder == "doctest":
    assert (output / "html/index.html").is_file()
    if fault == "doctest-failure":
      assert "1 failure" in (output / "doctest/output.txt").read_text(encoding="utf-8")
  else:
    assert not (output / "doctest").exists()


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
    "tests/unit/test_nested.py",
    "docs/conf.py",
    "docs/python-stdlib.inv",
    "docs/index.md",
    "docs/guide/page.md",
    "docs/notes.txt",
    ".github/workflows/checks.yml",
    ".github/workflows/release.yml",
    ".github/workflows/extra.yaml",
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
    "tests/unit/test_nested.py",
    ".github/workflows/checks.yml",
    ".github/workflows/release.yml",
    ".github/workflows/extra.yaml",
  } <= set(members)
  assert {"tools/helper.sh", "docs/notes.txt"}.isdisjoint(members)


def test_real_source_members_include_the_workflow_consumed_by_tests() -> None:
  assert {".github/workflows/checks.yml", ".github/workflows/release.yml"} <= set(
    source_members(check.ROOT)
  )


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


@pytest.mark.parametrize("name", [".review/notes.md", "ziwei-0.0.0/.review", "other/.review/note"])
def test_sdist_review_material_is_rejected_outside_the_version_root(
  tmp_path: Path, name: str
) -> None:
  path = write_sdist(
    tmp_path / "ziwei-0.0.0.tar.gz", {"PKG-INFO": PKG_INFO, **dict.fromkeys(SOURCE, "")}
  )
  with tarfile.open(path) as archive:
    members = []
    for member in archive.getmembers():
      stream = archive.extractfile(member)
      assert stream is not None
      with stream:
        members.append((member, stream.read()))
  with tarfile.open(path, "w:gz") as archive:
    for member, data in members:
      archive.addfile(member, io.BytesIO(data))
    extra = tarfile.TarInfo(name)
    extra.size = 1
    archive.addfile(extra, io.BytesIO(b"x"))
  with pytest.raises(ValueError, match="review material"):
    check_sdist(path, "0.0.0", SOURCE)


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
  monkeypatch.setattr(consumption, "run", fake_run)
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
  assert calls[1] == ((sys.executable, "-m", "twine", "check", str(sdist), str(wheel)), source)
  assert calls[2] == (
    (
      "uv",
      "export",
      "--locked",
      "--no-dev",
      "--no-emit-project",
      "--no-editable",
      "--output-file",
      str(tmp_path / "runtime.txt"),
    ),
    source,
  )
  assert calls[4] == (
    (
      "uv",
      "pip",
      "install",
      "--python",
      str(python),
      "--require-hashes",
      "--default-index",
      "https://pypi.org/simple",
      "--requirements",
      str(tmp_path / "runtime.txt"),
    ),
    source,
  )


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
  source = tmp_path / "source"
  source.mkdir()
  (source / "pyproject.toml").write_bytes((check.ROOT / "pyproject.toml").read_bytes())
  monkeypatch.setattr(check, "ROOT", source)
  artifacts = tmp_path / "artifacts"
  artifacts.mkdir()
  sdist, wheel = artifacts / "a.tar.gz", artifacts / "a.whl"
  sdist.write_bytes(b"source")
  wheel.write_bytes(b"wheel")
  monkeypatch.setattr(check, "run", lambda *args, **kwargs: None)
  monkeypatch.setattr(check, "check_sdist", lambda *args: None)
  monkeypatch.setattr(check, "check_wheel", lambda *args: None)
  monkeypatch.setattr(
    check, "install_and_consume", lambda *args, **kwargs: wheel.write_bytes(b"changed")
  )
  with pytest.raises(ValueError, match="changed during"):
    check.check_distribution(tmp_path, artifacts_dir=tmp_path / "kept")
  assert not (tmp_path / "kept").exists()


def test_retained_artifacts_preserve_the_pre_consumption_bytes(tmp_path: Path) -> None:
  files = (tmp_path / "a.tar.gz", tmp_path / "a.whl")
  for path in files:
    path.write_bytes(path.name.encode())
  hashes = {path: artifacts.file_sha256(path) for path in reversed(files)}
  kept = tmp_path / "kept"
  artifacts.preserve_artifacts(hashes, kept)
  for path, digest in hashes.items():
    assert artifacts.file_sha256(kept / "packages" / path.name) == digest
  assert (kept / "SHA256SUMS").read_bytes() == "".join(
    f"{hashes[path]}  {path.name}\n" for path in files
  ).encode()
  with pytest.raises(ValueError, match="empty directory"):
    artifacts.preserve_artifacts(hashes, kept)


def test_retaining_an_already_changed_file_fails(tmp_path: Path) -> None:
  sdist = tmp_path / "a.tar.gz"
  sdist.write_bytes(b"source")
  path = tmp_path / "a.whl"
  path.write_bytes(b"original")
  original = artifacts.file_sha256(path)
  path.write_bytes(b"changed")
  with pytest.raises(ValueError, match="changed during"):
    artifacts.preserve_artifacts(
      {sdist: artifacts.file_sha256(sdist), path: original}, tmp_path / "kept"
    )
  assert not (tmp_path / "kept/SHA256SUMS").exists()


def test_copy_corruption_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  files = tmp_path / "a.tar.gz", tmp_path / "a.whl"
  for path in files:
    path.write_bytes(b"original")
  hashes = {path: artifacts.file_sha256(path) for path in files}
  monkeypatch.setattr(shutil, "copyfile", lambda src, dst: dst.write_bytes(b"corrupt"))
  with pytest.raises(ValueError, match="Artifact copy differs"):
    artifacts.preserve_artifacts(hashes, tmp_path / "kept")
  assert not (tmp_path / "kept/SHA256SUMS").exists()


@pytest.mark.parametrize(
  "defect", [None, "count", "name", "order", "uppercase", "crlf", "no-newline"]
)
def test_checksum_contract(tmp_path: Path, defect: str | None) -> None:
  names = "ziwei-0.1.0.tar.gz", "ziwei-0.1.0-py3-none-any.whl"
  hashes = "a" * 64, "b" * 64
  text = artifacts.checksum_text(names, hashes)
  path = tmp_path / "SHA256SUMS"
  path.write_bytes(text.encode())
  assert artifacts.read_checksums(path, names) == hashes
  match defect:
    case "count":
      text += "extra\n"
    case "name":
      text = text.replace(names[1], "other.whl")
    case "order":
      text = "\n".join(reversed(text.splitlines())) + "\n"
    case "uppercase":
      text = text.replace("a" * 64, "A" * 64)
    case "crlf":
      text = text.replace("\n", "\r\n")
    case "no-newline":
      text = text.rstrip("\n")
  path.write_bytes(text.encode())
  if defect is None:
    assert artifacts.read_checksums(path, names) == hashes
  else:
    with pytest.raises(ValueError, match="build checksum"):
      artifacts.read_checksums(path, names)


def test_installed_consumption_refuses_a_repository_directory() -> None:
  with pytest.raises(ValueError, match="outside the repository"):
    consumption.install_and_consume(
      Path("a.whl"), "0.1.0", check.ROOT / "build/consumer", root=check.ROOT
    )


@pytest.mark.parametrize("retain", [False, True])
def test_main_runs_every_gate_in_order(
  monkeypatch: pytest.MonkeyPatch, tmp_path: Path, retain: bool
) -> None:
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
  monkeypatch.setattr(
    check,
    "check_distribution",
    lambda directory, *, artifacts_dir=None: calls.append(("distribution", artifacts_dir)),
  )
  monkeypatch.setenv("SCRATCH", str(tmp_path))
  destination = tmp_path / "kept" if retain else None
  check.main(artifacts_dir=destination)
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
    ("distribution", destination),
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
