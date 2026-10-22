"""发布前置与产物验证须在任何安装或上传之前拒绝缺陷。"""

import io
import json
import sys
import tarfile
import time
from copy import deepcopy
from http.client import HTTPMessage
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from zipfile import ZipFile

import pytest

from tools import artifacts, release

VERSION = "0.1.0"
SHA = "a" * 40


@pytest.fixture
def bundle(tmp_path: Path) -> tuple[Path, release.Manifest]:
  built = tmp_path / "built"
  built.mkdir()
  sdist = built / f"ziwei-{VERSION}.tar.gz"
  with tarfile.open(sdist, "w:gz") as archive:
    texts = dict.fromkeys(artifacts.source_members(release.ROOT), "")
    texts["PKG-INFO"] = f"Name: ziwei\nVersion: {VERSION}\n"
    for name, text in texts.items():
      data = text.encode()
      member = tarfile.TarInfo(f"ziwei-{VERSION}/{name}")
      member.size = len(data)
      archive.addfile(member, io.BytesIO(data))
  wheel = built / f"ziwei-{VERSION}-py3-none-any.whl"
  with ZipFile(wheel, "w") as archive:
    archive.writestr(f"ziwei-{VERSION}.dist-info/METADATA", f"Name: ziwei\nVersion: {VERSION}\n")
    for name in (
      "ziwei/__init__.py",
      "ziwei/py.typed",
      f"ziwei-{VERSION}.dist-info/licenses/LICENSE",
    ):
      archive.writestr(name, "")
  directory = tmp_path / "bundle"
  artifacts.preserve_artifacts(
    {path: artifacts.file_sha256(path) for path in (sdist, wheel)}, directory
  )
  return directory, release.prepare_bundle(directory, VERSION, SHA)


@pytest.mark.parametrize(
  "defect",
  ["version", "placeholder", "prerelease", "sha", "short-sha", "uppercase", "ref", "injection"],
)
def test_release_identity_is_an_early_check_not_an_authorization(defect: str) -> None:
  release.validate_identity(
    VERSION, SHA, github_sha=SHA, github_ref="refs/heads/main", metadata_version=VERSION
  )
  version, source_sha, actual_sha, ref = VERSION, SHA, SHA, "refs/heads/main"
  match defect:
    case "version":
      version = "0.2.0"
    case "placeholder":
      version = "0.0.0"
    case "prerelease":
      version = "0.1.0rc1"
    case "sha":
      actual_sha = "b" * 40
    case "short-sha":
      source_sha = "a" * 7
    case "uppercase":
      source_sha = SHA.upper()
    case "ref":
      ref = "refs/tags/main"
    case "injection":
      version = "0.1.0; touch unwanted"
  with pytest.raises(ValueError):
    release.validate_identity(
      version, source_sha, github_sha=actual_sha, github_ref=ref, metadata_version=VERSION
    )


def test_prepared_bundle_preserves_original_checksums(
  bundle: tuple[Path, release.Manifest],
) -> None:
  directory, manifest = bundle
  assert release.read_manifest(directory) == manifest
  release.verify_bundle(directory, manifest)
  with pytest.raises(ValueError, match="already exists"):
    release.prepare_bundle(directory, VERSION, SHA)


@pytest.mark.parametrize(
  "defect",
  ["bytes", "checksum", "manifest", "extra", "missing", "symlink", "filename", "extra-metadata"],
)
def test_bundle_rejects_a_single_change(bundle: tuple[Path, release.Manifest], defect: str) -> None:
  directory, manifest = bundle
  release.verify_bundle(directory, manifest)
  wheel = directory / "packages" / manifest.filenames[1]
  match defect:
    case "bytes":
      wheel.write_bytes(b"changed")
    case "checksum":
      (directory / "SHA256SUMS").write_text("0" * 64)
    case "manifest":
      data = json.loads((directory / "release.json").read_text())
      data["wheel_sha256"] = "b" * 64
      (directory / "release.json").write_text(json.dumps(data))
    case "extra":
      (wheel.parent / "extra.whl").touch()
    case "missing":
      wheel.unlink()
    case "symlink":
      if sys.platform == "win32":
        pytest.skip("Windows symlink creation may require privileges")
      outside = directory.parent / "outside.whl"
      wheel.rename(outside)
      wheel.symlink_to(outside)
    case "filename":
      wheel.rename(wheel.with_name("other.whl"))
    case "extra-metadata":
      (directory / "unexpected").touch()
  with pytest.raises(ValueError):
    release.verify_bundle(directory, manifest)


def test_hashes_are_compared_to_build_outputs_not_only_the_manifest(
  bundle: tuple[Path, release.Manifest],
) -> None:
  directory, manifest = bundle
  changed = release.Manifest(VERSION, SHA, manifest.sdist_sha256, "b" * 64)
  with pytest.raises(ValueError, match="trusted build outputs"):
    release.verify_bundle(directory, changed)


def index_metadata(manifest: release.Manifest) -> dict[str, Any]:
  return {
    "info": {"name": "ziwei", "version": manifest.version},
    "urls": [
      {
        "filename": name,
        "digests": {"sha256": digest},
        "url": "https://test-files.pythonhosted.org/packages/file.whl",
      }
      for name, digest in zip(manifest.filenames, manifest.hashes, strict=True)
    ],
  }


@pytest.mark.parametrize(
  "defect",
  ["project", "version", "count", "duplicate", "hash", "digest-type", "url", "credentials"],
)
def test_testpypi_metadata_cannot_select_another_project_or_index(
  bundle: tuple[Path, release.Manifest], defect: str
) -> None:
  _, manifest = bundle
  data = index_metadata(manifest)
  assert release.testpypi_wheel_url(data, manifest).startswith(
    "https://test-files.pythonhosted.org/"
  )
  bad = deepcopy(data)
  match defect:
    case "project":
      bad["info"]["name"] = "other"
    case "version":
      bad["info"]["version"] = "0.2.0"
    case "count":
      bad["urls"].pop()
    case "duplicate":
      bad["urls"][1] = bad["urls"][0]
    case "hash":
      bad["urls"][1]["digests"]["sha256"] = "0" * 64
    case "digest-type":
      bad["urls"][1]["digests"] = "not an object"
    case "url":
      bad["urls"][1]["url"] = "https://files.pythonhosted.org/packages/file.whl"
    case "credentials":
      bad["urls"][1]["url"] = "https://user:password@test-files.pythonhosted.org/packages/file.whl"
  with pytest.raises(ValueError):
    release.testpypi_wheel_url(bad, manifest)


@pytest.mark.parametrize("corrupt", [False, True])
def test_testpypi_installs_only_after_verifying_the_download(
  bundle: tuple[Path, release.Manifest], monkeypatch: pytest.MonkeyPatch, corrupt: bool
) -> None:
  directory, manifest = bundle
  wheel_bytes = (directory / "packages" / manifest.filenames[1]).read_bytes()
  calls: list[str] = []
  consumed: list[str] = []

  def open_url(url: str, *, timeout: int) -> io.BytesIO:
    calls.append(url)
    assert timeout > 0
    if url.endswith("/json"):
      return io.BytesIO(json.dumps(index_metadata(manifest)).encode())
    return io.BytesIO(b"changed" if corrupt else wheel_bytes)

  def consume(wheel: Path, version: str, workdir: Path, *, root: Path) -> None:
    assert wheel.read_bytes() == wheel_bytes
    assert workdir != root == release.ROOT and version == VERSION
    consumed.append(version)

  monkeypatch.setattr(release, "urlopen", open_url)
  monkeypatch.setattr(release, "install_and_consume", consume)
  if corrupt:
    with pytest.raises(ValueError, match="Downloaded TestPyPI wheel"):
      release.verify_testpypi(manifest)
    assert not consumed
  else:
    release.verify_testpypi(manifest)
    assert consumed == [VERSION]
  assert calls[0] == f"https://test.pypi.org/pypi/ziwei/{VERSION}/json"
  assert len(calls) == 2


def test_testpypi_visibility_wait_is_bounded(
  bundle: tuple[Path, release.Manifest], monkeypatch: pytest.MonkeyPatch
) -> None:
  calls: list[str] = []
  sleeps: list[float] = []

  def absent(url: str, *, timeout: int) -> io.BytesIO:
    calls.append(url)
    raise HTTPError(url, 404, "Not found", HTTPMessage(), None)

  monkeypatch.setattr(release, "urlopen", absent)
  monkeypatch.setattr(time, "sleep", sleeps.append)
  with pytest.raises(HTTPError):
    release.verify_testpypi(bundle[1])
  assert len(calls) == 10 and sleeps == [3] * 9


@pytest.mark.parametrize("command", ["validate", "prepare", "consume", "verify-testpypi"])
def test_release_cli_keeps_the_same_identity_and_bytes(
  bundle: tuple[Path, release.Manifest],
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
  command: str,
) -> None:
  directory, manifest = bundle
  source = tmp_path / "source"
  source.mkdir()
  (source / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n')
  monkeypatch.setattr(release, "ROOT", source)
  for key, value in {
    "RELEASE_VERSION": VERSION,
    "RELEASE_SHA": SHA,
    "GITHUB_SHA": SHA,
    "GITHUB_REF": "refs/heads/main",
    "SDIST_SHA256": manifest.sdist_sha256,
    "WHEEL_SHA256": manifest.wheel_sha256,
    "GITHUB_OUTPUT": str(tmp_path / "outputs"),
  }.items():
    monkeypatch.setenv(key, value)
  if command == "prepare":
    (directory / "release.json").unlink()
  consumed: list[str] = []
  monkeypatch.setattr(release, "verify_testpypi", lambda *args: consumed.append("testpypi"))
  monkeypatch.setattr(sys, "argv", ["release", command, "--directory", str(directory)])
  events: list[str] = []
  verify = release.verify_bundle

  def observe_verify(path: Path, expected: release.Manifest) -> None:
    events.append("verify")
    verify(path, expected)

  def consume(*args: Any, **kwargs: Any) -> None:
    assert kwargs["root"] == source
    events.append("consume")
    consumed.append("consume")

  monkeypatch.setattr(release, "verify_bundle", observe_verify)
  monkeypatch.setattr(release, "install_and_consume", consume)
  release.main()
  if command == "prepare":
    assert f"source_sha={SHA}\n" in (tmp_path / "outputs").read_text()
  assert consumed == {"consume": ["consume"], "verify-testpypi": ["testpypi"]}.get(command, [])
  assert (
    events
    == {
      "validate": [],
      "prepare": ["verify"],
      "consume": ["verify", "consume", "verify"],
      "verify-testpypi": ["verify"],
    }[command]
  )


@pytest.mark.parametrize("status", [403, 429, 503])
def test_testpypi_does_not_retry_non_404_errors(
  bundle: tuple[Path, release.Manifest], monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
  calls: list[str] = []
  sleeps: list[float] = []

  def unavailable(url: str, *, timeout: int) -> io.BytesIO:
    calls.append(url)
    raise HTTPError(url, status, "Synthetic failure", HTTPMessage(), None)

  monkeypatch.setattr(release, "urlopen", unavailable)
  monkeypatch.setattr(time, "sleep", sleeps.append)
  with pytest.raises(HTTPError) as caught:
    release.verify_testpypi(bundle[1])
  assert caught.value.code == status
  assert calls == [f"https://test.pypi.org/pypi/ziwei/{VERSION}/json"]
  assert sleeps == []


@pytest.mark.parametrize("defect", ["fields", "type", "digest", "placeholder"])
def test_manifest_rejects_invalid_shape_and_values(
  bundle: tuple[Path, release.Manifest], defect: str
) -> None:
  directory, _ = bundle
  data = json.loads((directory / "release.json").read_text(encoding="utf-8"))
  expected = ""
  match defect:
    case "fields":
      data["extra"] = "x"
      expected = "manifest fields"
    case "type":
      data["version"] = 1
      expected = "must be strings"
    case "digest":
      data["wheel_sha256"] = "X" * 64
      expected = "lowercase SHA256"
    case "placeholder":
      data["version"] = "0.0.0"
      expected = "0.0.0 placeholder"
  (directory / "release.json").write_text(json.dumps(data), encoding="utf-8")
  with pytest.raises(ValueError, match=expected):
    release.read_manifest(directory)


@pytest.mark.skipif(
  sys.platform == "win32", reason="Windows symlink creation may require privileges"
)
@pytest.mark.parametrize("member", ["bundle", "packages", "SHA256SUMS", "release.json"])
def test_bundle_rejects_symlinks_at_every_level(
  bundle: tuple[Path, release.Manifest], member: str
) -> None:
  directory, manifest = bundle
  release.verify_bundle(directory, manifest)
  path = directory if member == "bundle" else directory / member
  target = directory.parent / (path.name + "-original")
  path.rename(target)
  path.symlink_to(target, target_is_directory=target.is_dir())
  with pytest.raises(ValueError, match="regular"):
    release.verify_bundle(directory, manifest)
