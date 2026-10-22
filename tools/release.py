"""校验首发身份、保留产物与测试站取回物；不执行上传。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.artifacts import (
  check_sdist,
  check_wheel,
  checksum_text,
  distribution_filenames,
  file_sha256,
  read_checksums,
  source_members,
)
from tools.consumption import install_and_consume

ROOT = Path(__file__).resolve().parents[1]


def validate_release_format(version: str, source_sha: str) -> None:
  """拒绝占位版本、非规范版本号和不完整的小写源码SHA。"""
  if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version):
    raise ValueError("Release version must have three canonical numeric components")
  if version == "0.0.0":
    raise ValueError("Release version cannot be the 0.0.0 placeholder")
  if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
    raise ValueError("Release SHA must be a full lowercase source SHA")


def validate_identity(
  version: str, source_sha: str, *, github_sha: str, github_ref: str, metadata_version: str
) -> None:
  """在构建前核本次main运行身份；不代替服务端部署规则。"""
  validate_release_format(version, source_sha)
  if version != metadata_version:
    raise ValueError("Release version differs from candidate project metadata")
  if source_sha != github_sha:
    raise ValueError("Release SHA must equal this workflow's full source SHA")
  if github_ref != "refs/heads/main":
    raise ValueError("Release early check requires refs/heads/main")


@dataclass(frozen=True, slots=True)
class Manifest:
  """固定发行身份与构建后、消费前记录的两文件摘要。"""

  version: str
  source_sha: str
  sdist_sha256: str
  wheel_sha256: str

  def __post_init__(self) -> None:
    validate_release_format(self.version, self.source_sha)
    if any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in self.hashes):
      raise ValueError("Artifact digests must be lowercase SHA256")

  @property
  def filenames(self) -> tuple[str, str]:
    """按sdist、wheel顺序返回本次文件名。"""
    return distribution_filenames(self.version)

  @property
  def hashes(self) -> tuple[str, str]:
    """按sdist、wheel顺序返回摘要。"""
    return self.sdist_sha256, self.wheel_sha256


def read_manifest(directory: Path) -> Manifest:
  """读取固定字段的发布清单；清单本身不是可信摘要来源。"""
  data = json.loads((directory / "release.json").read_text(encoding="utf-8"))
  fields = {"version", "source_sha", "sdist_sha256", "wheel_sha256"}
  if not isinstance(data, dict) or data.keys() != fields:
    raise ValueError("Invalid release manifest fields")
  if any(not isinstance(value, str) for value in data.values()):
    raise ValueError("Release manifest values must be strings")
  return Manifest(**data)


def verify_bundle(directory: Path, expected: Manifest) -> None:
  """按独立传入的build输出核清单、文件身份和实际字节。"""
  if directory.is_symlink() or not directory.is_dir():
    raise ValueError("Artifact bundle must be a regular directory")
  packages = directory / "packages"
  if packages.is_symlink() or not packages.is_dir():
    raise ValueError("Artifact packages must be a regular directory")
  if {path.name for path in directory.iterdir()} != {"packages", "SHA256SUMS", "release.json"}:
    raise ValueError("Unexpected artifact bundle members")
  for path in (directory / "SHA256SUMS", directory / "release.json"):
    if path.is_symlink() or not path.is_file():
      raise ValueError("Artifact metadata must be regular files")
  if read_manifest(directory) != expected:
    raise ValueError("Manifest differs from trusted build outputs")
  if {path.name for path in packages.iterdir()} != set(expected.filenames):
    raise ValueError("Expected exactly the release sdist and wheel")
  expected_sums = checksum_text(expected.filenames, expected.hashes).encode("utf-8")
  if (directory / "SHA256SUMS").read_bytes() != expected_sums:
    raise ValueError("Checksum file differs from trusted build outputs")
  for name, digest in zip(expected.filenames, expected.hashes, strict=True):
    path = packages / name
    if path.is_symlink() or not path.is_file() or file_sha256(path) != digest:
      raise ValueError("Artifact bytes differ from trusted build outputs")
  check_sdist(packages / expected.filenames[0], expected.version, source_members(ROOT))
  check_wheel(packages / expected.filenames[1], expected.version)


def prepare_bundle(directory: Path, version: str, source_sha: str) -> Manifest:
  """把门禁保留的原始摘要与本次源码身份配对，不重建产物。"""
  digests = read_checksums(directory / "SHA256SUMS", distribution_filenames(version))
  manifest = Manifest(version, source_sha, digests[0], digests[1])
  path = directory / "release.json"
  if path.exists() or path.is_symlink():
    raise ValueError("Release manifest already exists")
  path.write_text(json.dumps(asdict(manifest), sort_keys=True) + "\n", encoding="utf-8")
  verify_bundle(directory, manifest)
  return manifest


def testpypi_wheel_url(data: object, expected: Manifest) -> str:
  """核测试站项目与版本的两文件摘要，返回官方文件站上的wheel URL。"""
  if not isinstance(data, dict) or not isinstance(data.get("info"), dict):
    raise ValueError("Invalid TestPyPI metadata")
  if data["info"].get("name") != "ziwei" or data["info"].get("version") != expected.version:
    raise ValueError("TestPyPI project identity differs")
  files = data.get("urls")
  if not isinstance(files, list) or len(files) != 2:
    raise ValueError("Expected two TestPyPI files")
  indexed: dict[str, dict[str, Any]] = {}
  for item in files:
    if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
      raise ValueError("Invalid TestPyPI file metadata")
    if item["filename"] in indexed:
      raise ValueError("Duplicate TestPyPI filename")
    indexed[item["filename"]] = item
  if set(indexed) != set(expected.filenames):
    raise ValueError("TestPyPI filenames differ from the verified artifacts")
  for name, digest in zip(expected.filenames, expected.hashes, strict=True):
    digests = indexed[name].get("digests")
    if not isinstance(digests, dict) or digests.get("sha256") != digest:
      raise ValueError("TestPyPI digests differ from the verified artifacts")
  url = indexed[expected.filenames[1]].get("url")
  if not isinstance(url, str):
    raise ValueError("TestPyPI wheel URL is missing")
  parsed = urlsplit(url)
  if (
    parsed.scheme != "https"
    or parsed.netloc != "test-files.pythonhosted.org"
    or not parsed.path.startswith("/packages/")
    or parsed.query
    or parsed.fragment
  ):
    raise ValueError("TestPyPI wheel must come from its official file host")
  return url


def verify_testpypi(expected: Manifest) -> None:
  """有界等待测试站元数据，核取回wheel后按锁定依赖双模式消费。"""
  url = f"https://test.pypi.org/pypi/ziwei/{expected.version}/json"
  for attempt in range(10):
    try:
      with urlopen(url, timeout=20) as response:
        data = json.load(response)
      break
    except HTTPError as error:
      retry = error.code == 404 and attempt < 9
      error.close()
      if not retry:
        raise
      time.sleep(3)
  download = testpypi_wheel_url(data, expected)
  with tempfile.TemporaryDirectory(prefix="ziwei-testpypi-", dir=os.environ.get("SCRATCH")) as tmp:
    directory = Path(tmp)
    wheel = directory / expected.filenames[1]
    with urlopen(download, timeout=30) as response, wheel.open("wb") as output:
      while chunk := response.read(1024 * 1024):
        output.write(chunk)
    if file_sha256(wheel) != expected.wheel_sha256:
      raise ValueError("Downloaded TestPyPI wheel differs from verified bytes")
    install_and_consume(wheel, expected.version, directory, root=ROOT)


def main() -> None:
  """选择身份校验、清单写入或安装消费阶段，不执行上传。"""
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
    "command",
    choices=("validate", "prepare", "consume", "verify-testpypi"),
    help="validate核身份；prepare写清单与构建输出；consume或verify-testpypi核产物并安装消费",
  )
  parser.add_argument(
    "--directory", type=Path, default=Path("dist"), help="门禁保留的产物目录（默认dist）"
  )
  args = parser.parse_args()
  version, source_sha = os.environ["RELEASE_VERSION"], os.environ["RELEASE_SHA"]
  metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
  validate_identity(
    version,
    source_sha,
    github_sha=os.environ["GITHUB_SHA"],
    github_ref=os.environ["GITHUB_REF"],
    metadata_version=metadata["version"],
  )
  if args.command == "validate":
    return
  if args.command == "prepare":
    manifest = prepare_bundle(args.directory, version, source_sha)
    outputs = {
      **asdict(manifest),
      "sdist_name": manifest.filenames[0],
      "wheel_name": manifest.filenames[1],
    }
    if output := os.environ.get("GITHUB_OUTPUT"):
      with Path(output).open("a", encoding="utf-8") as stream:
        stream.writelines(f"{key}={value}\n" for key, value in outputs.items())
    print(json.dumps(outputs, sort_keys=True))
    return
  expected = Manifest(version, source_sha, os.environ["SDIST_SHA256"], os.environ["WHEEL_SHA256"])
  verify_bundle(args.directory, expected)
  if args.command == "consume":
    with tempfile.TemporaryDirectory(prefix="ziwei-consume-", dir=os.environ.get("SCRATCH")) as tmp:
      install_and_consume(
        args.directory.resolve() / "packages" / expected.filenames[1],
        expected.version,
        Path(tmp),
        root=ROOT,
      )
    verify_bundle(args.directory, expected)
  else:
    verify_testpypi(expected)


if __name__ == "__main__":
  main()
