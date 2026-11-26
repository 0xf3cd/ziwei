"""按受测树写出与真实构建形状相同的sdist与wheel，供制品检查的正负例使用。"""

import base64
import hashlib
import io
import tarfile
from collections.abc import Sequence
from pathlib import Path
from zipfile import ZipFile

from tools import artifacts


def apply_changes(contents: dict[str, bytes], changes: dict[str, bytes | None] | None) -> None:
  """值为None表示删去该成员，其余为新增或替换。"""
  for name, data in (changes or {}).items():
    if data is None:
      del contents[name]
    else:
      contents[name] = data


def build_sdist(
  path: Path,
  root: Path,
  members: Sequence[str],
  version: str,
  changes: dict[str, bytes | None] | None = None,
  base: str | None = None,
) -> Path:
  """以@开头的名字不放在版本目录下。"""
  base = base or f"ziwei-{version}"
  contents = {name: (root / name).read_bytes() for name in members}
  contents.update(dict.fromkeys(artifacts.SDIST_GENERATED, b""))
  contents["PKG-INFO"] = f"Name: ziwei\nVersion: {version}\n".encode()
  apply_changes(contents, changes)
  with tarfile.open(path, "w:gz") as archive:
    for name, data in contents.items():
      info = tarfile.TarInfo(name[1:] if name.startswith("@") else f"{base}/{name}")
      info.size = len(data)
      archive.addfile(info, io.BytesIO(data))
  return path


def build_wheel(
  path: Path,
  root: Path,
  version: str,
  changes: dict[str, bytes | None] | None = None,
  metadata: str | None = None,
) -> Path:
  """按最终内容重算RECORD，负例不会只因旧摘要失败。"""
  info = f"ziwei-{version}.dist-info"
  contents = {name: (root / "src" / name).read_bytes() for name in artifacts.package_files(root)}
  contents[f"{info}/licenses/LICENSE"] = (root / "LICENSE").read_bytes()
  contents[f"{info}/METADATA"] = (metadata or f"Name: ziwei\nVersion: {version}\n").encode()
  contents[f"{info}/WHEEL"] = b"Wheel-Version: 1.0\n"
  contents[f"{info}/top_level.txt"] = b"ziwei\n"
  apply_changes(contents, changes)
  rows = [f"{name},sha256={_digest(data)},{len(data)}" for name, data in contents.items()] + [
    f"{info}/RECORD,,"
  ]
  contents[f"{info}/RECORD"] = ("\n".join(rows) + "\n").encode()
  with ZipFile(path, "w") as archive:
    for name, data in contents.items():
      archive.writestr(name, data)
  return path


def _digest(data: bytes) -> str:
  return base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
