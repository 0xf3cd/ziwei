"""发布前置与产物验证须在任何安装或上传之前拒绝缺陷。"""

import io
import json
import sys
import tarfile
from pathlib import Path
from typing import Any
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
  [
    "bytes",
    "checksum",
    "crlf",
    "manifest",
    "extra",
    "missing",
    "symlink",
    "filename",
    "extra-metadata",
  ],
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
    case "crlf":
      sums = directory / "SHA256SUMS"
      sums.write_bytes(sums.read_bytes().replace(b"\n", b"\r\n"))
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
  with pytest.raises(
    ValueError, match="Checksum file differs" if defect in ("checksum", "crlf") else None
  ):
    release.verify_bundle(directory, manifest)


def test_hashes_are_compared_to_build_outputs_not_only_the_manifest(
  bundle: tuple[Path, release.Manifest],
) -> None:
  directory, manifest = bundle
  changed = release.Manifest(VERSION, SHA, manifest.sdist_sha256, "b" * 64)
  with pytest.raises(ValueError, match="trusted build outputs"):
    release.verify_bundle(directory, changed)


@pytest.mark.parametrize("command", ["validate", "prepare", "consume"])
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
  assert consumed == (["consume"] if command == "consume" else [])
  assert (
    events
    == {
      "validate": [],
      "prepare": ["verify"],
      "consume": ["verify", "consume", "verify"],
    }[command]
  )


def test_removed_index_command_is_rejected(
  monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
  monkeypatch.setattr(sys, "argv", ["release", "verify-testpypi"])
  with pytest.raises(SystemExit) as caught:
    release.main()
  assert caught.value.code == 2
  assert "invalid choice" in capsys.readouterr().err


@pytest.mark.parametrize("defect", ["fields", "type", "digest", "placeholder", "source-sha"])
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
    case "source-sha":
      data["source_sha"] = "short"
      expected = "full lowercase source SHA"
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


@pytest.mark.parametrize(
  "version, source_sha, message",
  [
    ("0.0.0", SHA, "0.0.0 placeholder"),
    ("0.1.0rc1", SHA, "canonical numeric components"),
    ("01.2.3", SHA, "canonical numeric components"),
    (VERSION, "short", "full lowercase source SHA"),
    (VERSION, SHA.upper(), "full lowercase source SHA"),
  ],
)
def test_identity_format_is_checked_even_when_the_context_matches(
  version: str, source_sha: str, message: str
) -> None:
  with pytest.raises(ValueError, match=message):
    release.validate_identity(
      version,
      source_sha,
      github_sha=source_sha,
      github_ref="refs/heads/main",
      metadata_version=version,
    )
