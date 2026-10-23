"""分发包的身份、内容、摘要与保留格式。"""

from __future__ import annotations

import hashlib
import re
import shutil
import tarfile
from collections.abc import Sequence
from email.parser import Parser
from pathlib import Path
from zipfile import ZipFile

# sdist须能重建wheel并重跑全部检查。
SOURCE_FILES = (
  ".github/workflows/checks.yml",
  ".github/workflows/release.yml",
  "pyproject.toml",
  "uv.lock",
  "LICENSE",
  "README.md",
  "AGENTS.md",
  "src/ziwei/__init__.py",
  "src/ziwei/py.typed",
)
SOURCE_PATTERNS = (
  ".github/workflows/*.yml",
  ".github/workflows/*.yaml",
  "src/ziwei/**/*.py",
  "tools/*.py",
  "tests/**/*.py",
  "tests/fixtures/**/*.json",
  "tests/fixtures/**/*.md",
  "docs/**/*.md",
  "docs/**/*.py",
  "docs/**/*.inv",
)


def distribution_filenames(version: str) -> tuple[str, str]:
  """按sdist、wheel顺序返回ziwei纯Python发行的文件名。"""
  return f"ziwei-{version}.tar.gz", f"ziwei-{version}-py3-none-any.whl"


def source_members(root: Path) -> tuple[str, ...]:
  """列出sdist必须携带的工作树文件。"""
  members = set(SOURCE_FILES)
  for pattern in SOURCE_PATTERNS:
    members.update(path.relative_to(root).as_posix() for path in root.glob(pattern))
  return tuple(sorted(members))


def check_sdist(sdist: Path, expected_version: str, members: Sequence[str]) -> None:
  """校验sdist身份与内容，拒绝缺文件或夹带审阅材料。"""
  base = f"ziwei-{expected_version}"
  with tarfile.open(sdist) as archive:
    names = archive.getnames()
    stream = archive.extractfile(f"{base}/PKG-INFO") if f"{base}/PKG-INFO" in names else None
    if stream is None:
      raise ValueError("Sdist directory or PKG-INFO differs from project metadata")
    with stream:
      metadata = Parser().parsestr(stream.read().decode("utf-8"))
  if metadata["Name"] != "ziwei" or metadata["Version"] != expected_version:
    raise ValueError("Sdist identity differs from project metadata")
  missing = [member for member in members if f"{base}/{member}" not in names]
  if missing:
    raise ValueError(f"Sdist is missing: {', '.join(missing)}")
  if any(".review" in Path(name).parts for name in names):
    raise ValueError("Sdist carries review material")


def check_wheel(wheel: Path, expected_version: str) -> None:
  """校验wheel内容与元数据。"""
  with ZipFile(wheel) as archive:
    names = archive.namelist()
    metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
    if len(metadata_paths) != 1:
      raise ValueError("Wheel must contain one METADATA file")
    metadata = Parser().parsestr(archive.read(metadata_paths[0]).decode("utf-8"))
    if metadata["Name"] != "ziwei" or metadata["Version"] != expected_version:
      raise ValueError("Wheel identity differs from project metadata")
    if "ziwei/py.typed" not in names or "ziwei/__init__.py" not in names:
      raise ValueError("Wheel is missing the package or typing marker")
    if not any(name.endswith(".dist-info/licenses/LICENSE") for name in names):
      raise ValueError("Wheel is missing its license")


def built_artifacts(directory: Path) -> tuple[Path, Path]:
  """返回唯一的sdist与wheel。"""
  sdists = tuple(directory.glob("*.tar.gz"))
  wheels = tuple(directory.glob("*.whl"))
  if len(sdists) != 1 or len(wheels) != 1:
    raise ValueError("Expected one sdist and one wheel")
  return sdists[0], wheels[0]


def file_sha256(path: Path) -> str:
  """读取文件的SHA256。"""
  with path.open("rb") as stream:
    return hashlib.file_digest(stream, "sha256").hexdigest()


def checksum_text(names: tuple[str, str], hashes: tuple[str, str]) -> str:
  """按传入的sdist、wheel顺序生成两行SHA256SUMS。"""
  return "".join(f"{digest}  {name}\n" for name, digest in zip(names, hashes, strict=True))


def read_checksums(path: Path, names: tuple[str, str]) -> tuple[str, str]:
  """读取固定文件名和顺序的两条原始构建摘要。"""
  text = path.read_bytes().decode("utf-8")
  lines = text.splitlines()
  if len(lines) != 2:
    raise ValueError("Expected two original build checksums")
  digests: list[str] = []
  for line, name in zip(lines, names, strict=True):
    match = re.fullmatch(r"([0-9a-f]{64})  " + re.escape(name), line)
    if match is None:
      raise ValueError("Invalid original build checksum")
    digests.append(match[1])
  pair = digests[0], digests[1]
  if text != checksum_text(names, pair):
    raise ValueError("Invalid original build checksum format")
  return pair


def preserve_artifacts(hashes: dict[Path, str], destination: Path) -> None:
  """把已核两文件及原始摘要写入空目录，始终先sdist后wheel。"""
  if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
    raise ValueError("Artifact destination must be an empty directory")
  sdists = [path for path in hashes if path.name.endswith(".tar.gz")]
  wheels = [path for path in hashes if path.name.endswith(".whl")]
  if len(hashes) != 2 or len(sdists) != 1 or len(wheels) != 1:
    raise ValueError("Expected one sdist and one wheel")
  paths = sdists[0], wheels[0]
  destination.mkdir(parents=True, exist_ok=True)
  packages = destination / "packages"
  packages.mkdir()
  for path in paths:
    expected = hashes[path]
    if file_sha256(path) != expected:
      raise ValueError("Artifacts changed during installed consumption")
    copied = packages / path.name
    shutil.copyfile(path, copied)
    if file_sha256(copied) != expected:
      raise ValueError("Artifact copy differs from the verified bytes")
  (destination / "SHA256SUMS").write_bytes(
    checksum_text((paths[0].name, paths[1].name), (hashes[paths[0]], hashes[paths[1]])).encode(
      "utf-8"
    )
  )
