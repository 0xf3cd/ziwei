"""分发包的身份、内容、摘要与保留格式。"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
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
  "MANIFEST.in",
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
  "tests/**/*.json",
  "docs/**/*.md",
  "docs/**/*.py",
  "docs/**/*.inv",
  "docs/**/*.css",
)
# setuptools据源码另生成、随sdist分发的文件。
SDIST_GENERATED = (
  "PKG-INFO",
  "setup.cfg",
  "src/ziwei.egg-info/PKG-INFO",
  "src/ziwei.egg-info/SOURCES.txt",
  "src/ziwei.egg-info/dependency_links.txt",
  "src/ziwei.egg-info/requires.txt",
  "src/ziwei.egg-info/top_level.txt",
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


def check_sdist(sdist: Path, expected_version: str, members: Sequence[str], root: Path) -> None:
  """校验sdist身份与精确文件集合，源码成员须与受测工作树逐字节相同。"""
  base = f"ziwei-{expected_version}"
  with tarfile.open(sdist) as archive:
    entries = archive.getmembers()
    if any(not (entry.isfile() or entry.isdir()) for entry in entries):
      raise ValueError("Sdist may only contain files and directories")
    files = {entry.name: entry for entry in entries if entry.isfile()}

    def read(name: str) -> bytes:
      stream = archive.extractfile(files[f"{base}/{name}"])
      if stream is None:
        raise ValueError(f"Sdist member is not a regular file: {name}")
      with stream:
        return stream.read()

    if f"{base}/PKG-INFO" not in files:
      raise ValueError("Sdist directory or PKG-INFO differs from project metadata")
    metadata = Parser().parsestr(read("PKG-INFO").decode("utf-8"))
    if metadata["Name"] != "ziwei" or metadata["Version"] != expected_version:
      raise ValueError("Sdist identity differs from project metadata")
    expected = {f"{base}/{name}" for name in (*members, *SDIST_GENERATED)}
    missing = sorted(name.removeprefix(f"{base}/") for name in expected - files.keys())
    if missing:
      raise ValueError(f"Sdist is missing: {', '.join(missing)}")
    extra = sorted(files.keys() - expected)
    if extra:
      raise ValueError(f"Sdist carries unexpected files: {', '.join(extra)}")
    for name in members:
      if read(name) != (root / name).read_bytes():
        raise ValueError(f"Sdist file differs from the tested source: {name}")


def package_files(root: Path) -> tuple[str, ...]:
  """列出主包wheel应携带的源码文件，路径相对src。"""
  source = root / "src"
  return tuple(
    sorted(
      path.relative_to(source).as_posix()
      for path in (source / "ziwei").rglob("*")
      if path.is_file()
      and "__pycache__" not in path.parts
      and (path.suffix == ".py" or path.name == "py.typed")
    )
  )


def check_record(archive: ZipFile, members: set[str], record: str) -> None:
  """核RECORD逐成员列出摘要与大小，且不为自身记摘要。"""
  rows = list(csv.reader(io.StringIO(archive.read(record).decode("utf-8"))))
  if any(len(row) != 3 for row in rows) or len(rows) != len(members):
    raise ValueError("Malformed wheel RECORD")
  if {row[0] for row in rows} != members:
    raise ValueError("Wheel RECORD member inventory differs")
  for name, digest, size in rows:
    if name == record:
      if digest or size:
        raise ValueError("Wheel RECORD must not hash itself")
      continue
    content = archive.read(name)
    actual = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
    if digest != "sha256=" + actual or size != str(len(content)):
      raise ValueError(f"Wheel RECORD digest or size differs: {name}")


def check_wheel(wheel: Path, expected_version: str, root: Path) -> None:
  """校验wheel身份与精确成员，包文件与许可证须与受测工作树逐字节相同。"""
  info = f"ziwei-{expected_version}.dist-info"
  expected = {name: (root / "src" / name).read_bytes() for name in package_files(root)}
  expected[f"{info}/licenses/LICENSE"] = (root / "LICENSE").read_bytes()
  generated = {f"{info}/{name}" for name in ("METADATA", "WHEEL", "RECORD", "top_level.txt")}
  members = {*expected, *generated}
  with ZipFile(wheel) as archive:
    names = archive.namelist()
    if len(names) != len(set(names)):
      raise ValueError("Wheel repeats a member")
    missing = sorted(members - set(names))
    if missing:
      raise ValueError(f"Wheel is missing: {', '.join(missing)}")
    extra = sorted(set(names) - members)
    if extra:
      raise ValueError(f"Wheel carries unexpected files: {', '.join(extra)}")
    metadata = Parser().parsestr(archive.read(f"{info}/METADATA").decode("utf-8"))
    if metadata["Name"] != "ziwei" or metadata["Version"] != expected_version:
      raise ValueError("Wheel identity differs from project metadata")
    for name, content in expected.items():
      if archive.read(name) != content:
        raise ValueError(f"Wheel file differs from the tested source: {name}")
    check_record(archive, members, f"{info}/RECORD")


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
