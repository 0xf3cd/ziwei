"""发布前置与产物验证须在任何安装或上传之前拒绝缺陷。"""

import io
import json
import os
import re
import subprocess
import sys
import tarfile
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest
import yaml

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


@pytest.fixture
def publish_script() -> str:
  workflow: dict[str, Any] = yaml.load(
    (release.ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8"),
    Loader=yaml.BaseLoader,
  )
  steps = [
    step for step in workflow["jobs"]["publish-pypi"]["steps"] if step.get("id") == "verify-bytes"
  ]
  assert len(steps) == 1 and steps[0]["shell"] == "bash"
  script: str = steps[0]["run"]
  return script


def change_bundle(directory: Path, expected: release.Manifest, defect: str) -> release.Manifest:
  packages = directory / "packages"
  sdist, wheel = (packages / name for name in expected.filenames)
  match defect:
    case "valid":
      pass
    case "sdist-bytes" | "wheel-bytes":
      (sdist if defect == "sdist-bytes" else wheel).write_bytes(b"changed")
    case "build-digest":
      expected = replace(expected, wheel_sha256="b" * 64)
    case "checksum":
      (directory / "SHA256SUMS").write_text("0" * 64)
    case "crlf":
      sums = directory / "SHA256SUMS"
      sums.write_bytes(sums.read_bytes().replace(b"\n", b"\r\n"))
    case "manifest-digest" | "manifest-sha" | "manifest-version":
      field, value = {
        "manifest-digest": ("wheel_sha256", "b" * 64),
        "manifest-sha": ("source_sha", "b" * 40),
        "manifest-version": ("version", "0.2.0"),
      }[defect]
      data = asdict(expected)
      data[field] = value
      (directory / "release.json").write_text(json.dumps(data), encoding="utf-8")
    case "extra":
      (packages / "extra.whl").touch()
    case "missing-sdist" | "missing-wheel":
      (sdist if defect == "missing-sdist" else wheel).unlink()
    case (
      "sdist-symlink"
      | "wheel-symlink"
      | "packages-symlink"
      | "bundle-symlink"
      | "checksum-symlink"
      | "manifest-symlink"
    ):
      path = {
        "sdist-symlink": sdist,
        "wheel-symlink": wheel,
        "packages-symlink": packages,
        "bundle-symlink": directory,
        "checksum-symlink": directory / "SHA256SUMS",
        "manifest-symlink": directory / "release.json",
      }[defect]
      target = directory.parent / (path.name + "-original")
      path.rename(target)
      path.symlink_to(target, target_is_directory=target.is_dir())
    case "filename":
      wheel.rename(wheel.with_name("other.whl"))
    case "extra-metadata":
      (directory / "unexpected").touch()
    case "wheel-identity" | "wheel-typing":
      with ZipFile(wheel) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
      if defect == "wheel-identity":
        contents[f"ziwei-{VERSION}.dist-info/METADATA"] = (
          f"Name: other\nVersion: {VERSION}\n".encode()
        )
      else:
        del contents["ziwei/py.typed"]
      with ZipFile(wheel, "w") as archive:
        for name, content in contents.items():
          archive.writestr(name, content)
      expected = replace(expected, wheel_sha256=artifacts.file_sha256(wheel))
      # 模拟build输出与字节一致但内部语义有错；可信输入不从待验元数据读取。
      (directory / "release.json").write_text(json.dumps(asdict(expected)), encoding="utf-8")
      (directory / "SHA256SUMS").write_bytes(
        artifacts.checksum_text(expected.filenames, expected.hashes).encode("utf-8")
      )
    case _:
      raise AssertionError(f"Unknown bundle defect: {defect}")
  return expected


def verify_and_mark_upload(directory: Path, expected: release.Manifest, marker: Path) -> None:
  release.verify_bundle(directory, expected)
  marker.write_text("called", encoding="utf-8")


def run_publish_script(
  script: str, directory: Path, expected: release.Manifest, marker: Path
) -> subprocess.CompletedProcess[str]:
  return subprocess.run(
    ["bash", "--noprofile", "--norc", "-xc", script + '\nprintf called > "$UPLOAD_MARKER"\n'],
    cwd=directory.parent,
    env={
      "PATH": os.defpath,
      "LC_ALL": "C",
      "DIST_DIR": str(directory),
      "RELEASE_VERSION": expected.version,
      "SDIST_NAME": expected.filenames[0],
      "WHEEL_NAME": expected.filenames[1],
      "SDIST_SHA256": expected.sdist_sha256,
      "WHEEL_SHA256": expected.wheel_sha256,
      "UPLOAD_MARKER": str(marker),
    },
    capture_output=True,
    text=True,
    timeout=10,
  )


@pytest.mark.parametrize(
  "defect, python_error, bash_rejection",
  [
    ("valid", None, None),
    ("sdist-bytes", "Artifact bytes differ", "sha256sum --check --strict"),
    ("wheel-bytes", "Artifact bytes differ", "sha256sum --check --strict"),
    ("build-digest", "Manifest differs", "sha256sum --check --strict"),
    ("missing-sdist", "Expected exactly the release sdist and wheel", "[[ 1 -eq 2 ]]"),
    ("missing-wheel", "Expected exactly the release sdist and wheel", "[[ 1 -eq 2 ]]"),
    ("extra", "Expected exactly the release sdist and wheel", "[[ 3 -eq 2 ]]"),
    ("sdist-symlink", "Artifact bytes differ", "[[ ! -L {sdist} ]]"),
    ("wheel-symlink", "Artifact bytes differ", "[[ ! -L {wheel} ]]"),
    ("packages-symlink", "Artifact packages must be a regular directory", "[[ ! -L {packages} ]]"),
    ("bundle-symlink", "Artifact bundle must be a regular directory", "[[ ! -L {directory} ]]"),
    ("filename", "Expected exactly the release sdist and wheel", "[[ -f {wheel} ]]"),
    # 发布Bash只核packages字节，以下额外合同由build和consume的Python核验承担。
    ("checksum", "Checksum file differs", None),
    ("crlf", "Checksum file differs", None),
    ("manifest-digest", "Manifest differs", None),
    ("manifest-sha", "Manifest differs", None),
    ("manifest-version", "Manifest differs", None),
    ("extra-metadata", "Unexpected artifact bundle members", None),
    ("checksum-symlink", "Artifact metadata must be regular files", None),
    ("manifest-symlink", "Artifact metadata must be regular files", None),
    ("wheel-identity", "Wheel identity differs", None),
    ("wheel-typing", "Wheel is missing the package or typing marker", None),
  ],
)
def test_bundle_contracts_at_both_real_entrypoints(
  bundle: tuple[Path, release.Manifest],
  publish_script: str,
  tmp_path: Path,
  defect: str,
  python_error: str | None,
  bash_rejection: str | None,
) -> None:
  if sys.platform == "win32" and defect.endswith("-symlink"):
    pytest.skip("Windows symlink creation may require privileges")
  directory, expected = bundle
  python_marker, bash_marker = tmp_path / "python-upload", tmp_path / "bash-upload"
  verify_and_mark_upload(directory, expected, python_marker)
  assert python_marker.read_text(encoding="utf-8") == "called"
  python_marker.unlink()
  if sys.platform == "linux":
    baseline = run_publish_script(publish_script, directory, expected, bash_marker)
    assert baseline.returncode == 0, baseline.stderr
    assert bash_marker.read_text(encoding="utf-8") == "called"
    bash_marker.unlink()

  expected = change_bundle(directory, expected, defect)
  if python_error is None:
    verify_and_mark_upload(directory, expected, python_marker)
  else:
    with pytest.raises(ValueError, match=re.escape(python_error)):
      verify_and_mark_upload(directory, expected, python_marker)
  assert python_marker.exists() is (python_error is None)

  if sys.platform == "linux":
    result = run_publish_script(publish_script, directory, expected, bash_marker)
    assert result.returncode == (0 if bash_rejection is None else 1), result.stderr
    assert bash_marker.exists() is (bash_rejection is None)
    if bash_rejection is None:
      assert bash_marker.read_text(encoding="utf-8") == "called"
    else:
      trace = [
        line.removeprefix("+ ") for line in result.stderr.splitlines() if line.startswith("+ ")
      ]
      if bash_rejection == "sha256sum --check --strict":
        assert bash_rejection in trace, result.stderr
        changed_name = expected.filenames[0 if defect == "sdist-bytes" else 1]
        assert f"{directory / 'packages' / changed_name}: FAILED" in result.stdout
        assert "1 computed checksum did NOT match" in result.stderr
      else:
        assert trace[-1] == bash_rejection.format(
          directory=directory,
          packages=directory / "packages",
          sdist=directory / "packages" / expected.filenames[0],
          wheel=directory / "packages" / expected.filenames[1],
        ), result.stderr


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
