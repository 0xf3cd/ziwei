"""构建、校验与消费同版doushu转发wheel。"""

from __future__ import annotations

import argparse
import ast
import base64
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from email.parser import BytesParser
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from packaging.specifiers import SpecifierSet

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.artifacts import file_sha256
from tools.consumption import run

ROOT = Path(__file__).resolve().parents[1]
INTERNAL_MODULES = {"ziwei", "ziwei._frame", "ziwei.knowledge.data"}
ROOT_SOURCE = '"""ziwei的同版别名入口。"""\n\nimport ziwei as _ziwei\n'
README = """# doushu（斗数）

`doushu`是[ziwei](https://github.com/0xf3cd/ziwei)的安装与导入别名，提供紫微斗数排盘和有出处的知识查询。
它安装同版本的`ziwei`，从对应子模块转发公开函数、类型、枚举与数据，不包含另一套排盘实现。

```sh
python -m pip install doushu
```

```python
from doushu.knowledge import load_catalog

print(load_catalog().get("concept.star.ziwei").id)
```

输出为`concept.star.ziwei`。排盘所需的出生资料与口径配置见[完整命盘指南](https://0xf3cd.github.io/ziwei/docs/chart.html)。
原有`ziwei.*`导入继续可用，两种路径的公开对象相同。
请从对应子模块路径导入，不依赖包入口自动加载子模块；公开模块见[API参考](https://0xf3cd.github.io/ziwei/docs/api.html)。

只提供纯Python wheel，Python与平台范围和主包相同；主包的原生历法依赖仍有平台限制。
使用独立虚拟环境，详见[安装要求](https://github.com/0xf3cd/ziwei#安装要求)。
"""


def project(root: Path) -> dict[str, Any]:
  """读取主包的唯一发行配置。"""
  value: dict[str, Any] = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
  result: dict[str, Any] = value["project"]
  return result


def wheel_name(version: str) -> str:
  """拒绝非规范版本，并返回固定的纯wheel文件名。"""
  if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version):
    raise ValueError("Alias version must have three canonical numeric components")
  return f"doushu-{version}-py3-none-any.whl"


def module_file(root: Path, module: str) -> Path:
  path = root / "src" / Path(*module.split("."))
  return path / "__init__.py" if path.is_dir() else path.with_suffix(".py")


def public_exports(root: Path) -> dict[str, tuple[str, ...]]:
  """按API模块分类，从所属源码读取公开定义与有说明的数据。"""
  modules = re.findall(
    r"(?m)^\.\. automodule:: (ziwei\.[\w.]+)$",
    (root / "docs/api.md").read_text(encoding="utf-8"),
  )
  actual = {
    ".".join(path.relative_to(root / "src").with_suffix("").parts).removesuffix(".__init__")
    for path in (root / "src/ziwei").rglob("*.py")
  }
  if not modules or len(set(modules)) != len(modules) or actual != set(modules) | INTERNAL_MODULES:
    raise ValueError("Every source module must be classified as public or internal")
  result = {}
  for module in modules:
    source = module_file(root, module).read_text(encoding="utf-8")
    nodes, lines = ast.parse(source).body, source.splitlines()
    names = []
    for index, node in enumerate(nodes):
      if isinstance(
        node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
      ) and not node.name.startswith("_"):
        names.append(node.name)
      if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
        continue
      annotation = node.annotation
      if isinstance(annotation, ast.Subscript):
        annotation = annotation.value
      if isinstance(annotation, ast.Attribute):
        kind = annotation.attr
      else:
        kind = annotation.id if isinstance(annotation, ast.Name) else ""
      following = nodes[index + 1] if index + 1 < len(nodes) else None
      documented = (
        isinstance(following, ast.Expr)
        and isinstance(following.value, ast.Constant)
        and isinstance(following.value.value, str)
      ) or (node.lineno > 1 and lines[node.lineno - 2].lstrip().startswith("#:"))
      if not node.target.id.startswith("_") and (
        kind == "TypeAlias" or (kind == "Final" and documented)
      ):
        names.append(node.target.id)
    result[module] = tuple(sorted(names))
  return result


def forwarding_sources(root: Path) -> dict[str, bytes]:
  """生成显式同名导入，不在别名中定义领域对象。"""
  result = {"doushu/__init__.py": ROOT_SOURCE.encode(), "doushu/py.typed": b""}
  for module, names in public_exports(root).items():
    path = module_file(root, module).relative_to(root / "src").as_posix()
    path = "doushu" + path.removeprefix("ziwei")
    body = f"from {module} import (\n" + "".join(f"  {n} as {n},\n" for n in names) + ")\n"
    result[path] = body.encode()
  return result


def check_alias_wheel(wheel: Path, version: str, *, root: Path = ROOT) -> None:
  """核精确成员、转发语法、元数据与逐成员RECORD。"""
  if wheel.name != wheel_name(version) or wheel.is_symlink() or not wheel.is_file():
    raise ValueError("Alias wheel identity or file type differs")
  info = f"doushu-{version}.dist-info"
  source = forwarding_sources(root)
  expected = {
    **source,
    f"{info}/licenses/LICENSE": (root / "LICENSE").read_text(encoding="utf-8").encode(),
    f"{info}/top_level.txt": b"doushu\n",
  }
  members = {*expected, f"{info}/METADATA", f"{info}/WHEEL", f"{info}/RECORD"}
  with ZipFile(wheel) as archive:
    names = archive.namelist()
    if len(names) != len(set(names)) or set(names) != members:
      raise ValueError("Alias wheel member inventory differs")
    for name, content in expected.items():
      actual = archive.read(name)
      if actual != content:
        raise ValueError(f"Alias source or license differs: {name}")
      if name.endswith(".py") and name != "doushu/__init__.py":
        nodes = ast.parse(actual).body
        if len(nodes) != 1 or not isinstance(nodes[0], ast.ImportFrom):
          raise ValueError("Alias modules must only forward explicit names")
        statement = nodes[0]
        if statement.level or not statement.module or not statement.module.startswith("ziwei."):
          raise ValueError("Alias must import the primary module")
        if any(n.name != n.asname or n.name.startswith("_") for n in statement.names):
          raise ValueError("Alias must preserve public object names")
    metadata = BytesParser().parsebytes(archive.read(f"{info}/METADATA"))
    primary = project(root)
    fields = {
      "Name": "doushu",
      "Version": version,
      "License-Expression": primary["license"],
      "License-File": "LICENSE",
      "Description-Content-Type": "text/markdown",
      "Requires-Dist": f"ziwei=={version}",
    }
    if any(metadata.get_all(k) != [v] for k, v in fields.items()):
      raise ValueError("Alias metadata or exact primary dependency differs")
    python_specs = metadata.get_all("Requires-Python") or []
    if len(python_specs) != 1 or SpecifierSet(python_specs[0]) != SpecifierSet(
      primary["requires-python"]
    ):
      raise ValueError("Alias supported Python versions differ")
    payload = metadata.get_payload(decode=True)
    # Windows元数据可能写CRLF；文本比对统一换行，RECORD仍校验归档原字节。
    if (
      metadata.get_all("Provides-Extra")
      or not isinstance(payload, bytes)
      or payload.replace(b"\r\n", b"\n") != README.encode()
    ):
      raise ValueError("Alias extras or README differs")
    if sorted(metadata.get_all("Classifier") or ()) != sorted(primary["classifiers"]):
      raise ValueError("Alias supported Python classifiers differ")
    urls = [f"{key}, {value}" for key, value in primary["urls"].items()]
    if sorted(metadata.get_all("Project-URL") or ()) != sorted(urls):
      raise ValueError("Alias project URLs differ")
    tags = BytesParser().parsebytes(archive.read(f"{info}/WHEEL"))
    if any(
      tags.get_all(k) != [v]
      for k, v in {"Wheel-Version": "1.0", "Root-Is-Purelib": "true", "Tag": "py3-none-any"}.items()
    ):
      raise ValueError("Alias must be a pure Python wheel")
    records = list(csv.reader(io.StringIO(archive.read(f"{info}/RECORD").decode())))
    if any(len(row) != 3 for row in records) or len(records) != len(members):
      raise ValueError("Malformed alias RECORD")
    if {row[0] for row in records} != members:
      raise ValueError("Alias RECORD member inventory differs")
    for name, digest, size in records:
      if name == f"{info}/RECORD":
        if digest or size:
          raise ValueError("Alias RECORD must not hash itself")
        continue
      content = archive.read(name)
      actual_digest = (
        base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
      )
      if digest != "sha256=" + actual_digest or size != str(len(content)):
        raise ValueError("Alias RECORD digest or size differs")


def build_alias(directory: Path, *, root: Path = ROOT) -> Path:
  """用主配置和锁定后端构建一次别名wheel。"""
  directory.mkdir()
  source = directory / "source"
  source.mkdir()
  for name, content in forwarding_sources(root).items():
    path = source / "src" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
  # 许可证统一为LF，避免Windows checkout与Linux工件仅因换行不同而校验失败。
  (source / "LICENSE").write_bytes((root / "LICENSE").read_text(encoding="utf-8").encode())
  (source / "README.md").write_bytes(README.encode())
  primary = project(root)
  metadata = {
    **{
      k: primary[k]
      for k in ("version", "requires-python", "license", "license-files", "classifiers")
    },
    "name": "doushu",
    "description": "紫微斗数ziwei的同版安装与导入别名",
    "readme": "README.md",
    "dependencies": [f"ziwei=={primary['version']}"],
  }
  backend = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["build-system"]
  config = "[build-system]\n" + "".join(f"{k} = {json.dumps(v)}\n" for k, v in backend.items())
  config += "\n[project]\n" + "".join(
    f"{k} = {json.dumps(v, ensure_ascii=False)}\n" for k, v in metadata.items()
  )
  config += "\n[project.urls]\n" + "".join(
    f"{k} = {json.dumps(v)}\n" for k, v in primary["urls"].items()
  )
  config += '\n[tool.setuptools.packages.find]\nwhere = ["src"]\nnamespaces = false\n'
  config += '\n[tool.setuptools.package-data]\ndoushu = ["py.typed"]\n'
  (source / "pyproject.toml").write_text(config, encoding="utf-8")
  output = directory / "built"
  run(
    (
      sys.executable,
      "-m",
      "build",
      "--wheel",
      "--no-isolation",
      "--outdir",
      str(output),
      str(source),
    ),
    cwd=root,
  )
  wheel = output / wheel_name(primary["version"])
  if set(output.iterdir()) != {wheel}:
    raise ValueError("Expected exactly one built alias wheel")
  check_alias_wheel(wheel, primary["version"], root=root)
  run((sys.executable, "-m", "twine", "check", str(wheel)), cwd=root)
  return wheel


def preserve_alias(wheel: Path, digest: str, directory: Path) -> None:
  """保留消费前记录的原字节，不覆盖已有材料。"""
  if directory.is_symlink() or (
    directory.exists() and (not directory.is_dir() or any(directory.iterdir()))
  ):
    raise ValueError("Alias destination must be an empty regular directory")
  if file_sha256(wheel) != digest:
    raise ValueError("Alias changed during consumption")
  directory.mkdir(parents=True, exist_ok=True)
  packages = directory / "packages"
  packages.mkdir()
  shutil.copyfile(wheel, packages / wheel.name)
  if file_sha256(packages / wheel.name) != digest:
    raise ValueError("Alias copy differs")
  (directory / "SHA256SUMS").write_bytes(f"{digest}  {wheel.name}\n".encode())


def read_alias_checksum(directory: Path, version: str) -> str:
  """读取单wheel的构建摘要，仅供构建输出阶段使用。"""
  text = (directory / "SHA256SUMS").read_bytes().decode()
  match = re.fullmatch(r"([0-9a-f]{64})  " + re.escape(wheel_name(version)) + r"\n", text)
  if match is None:
    raise ValueError("Invalid original alias checksum")
  return match[1]


def verify_alias_bundle(directory: Path, version: str, digest: str, *, root: Path = ROOT) -> Path:
  """用独立构建输出核保留目录及内部合同。"""
  name = wheel_name(version)
  packages = directory / "packages"
  for path in (directory, packages):
    if path.is_symlink() or not path.is_dir():
      raise ValueError("Alias bundle must contain regular directories")
  if {p.name for p in directory.iterdir()} != {"packages", "SHA256SUMS"}:
    raise ValueError("Unexpected alias bundle members")
  sums = directory / "SHA256SUMS"
  if sums.is_symlink() or not sums.is_file() or read_alias_checksum(directory, version) != digest:
    raise ValueError("Alias checksum differs from trusted build output")
  wheel = packages / name
  if (
    {p.name for p in packages.iterdir()} != {name}
    or wheel.is_symlink()
    or not wheel.is_file()
    or file_sha256(wheel) != digest
  ):
    raise ValueError("Alias bytes differ from trusted build output")
  check_alias_wheel(wheel, version, root=root)
  return wheel


def documented_exports(root: Path) -> dict[str, list[str]]:
  """独立从API文档取安装消费的预期公开名字。"""
  text = (root / "docs/api.md").read_text(encoding="utf-8")
  result = {
    match[1]: match[2].split(", ")
    for match in re.finditer(r"(?m)^\.\. automodule:: (ziwei\.[\w.]+)\n\s+:members: ([^\n]+)", text)
  }
  for name in re.findall(r"(?m)^\.\. autodata:: (ziwei\.[\w.]+)$", text):
    module, _, member = name.rpartition(".")
    result[module].append(member)
  return result


def consume_alias(wheel: Path, version: str, directory: Path, *, root: Path = ROOT) -> None:
  """在已有同次主包的仓外环境中安装别名，双模式、双导入顺序消费。"""
  if directory.resolve().is_relative_to(root.resolve()):
    raise ValueError("Alias consumption must run outside the repository")
  python = directory / "consumer" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
  run(("uv", "pip", "install", "--python", str(python), "--no-deps", str(wheel)), cwd=root)
  run(("uv", "pip", "check", "--python", str(python)), cwd=root)
  expectations = directory / "doushu-public-api.json"
  expectations.write_text(json.dumps(documented_exports(root)), encoding="utf-8")
  for mode in ((), ("-O",)):
    for first in ("doushu", "ziwei"):
      run(
        (
          str(python),
          *mode,
          "-I",
          str(root / "tools/doushu_installed_check.py"),
          version,
          str(expectations),
          first,
        ),
        cwd=directory,
      )


def check_alias_typing(directory: Path) -> None:
  """用锁定mypy检查仓外安装的类型，要求正例通过、误用按预期诊断拒绝。"""
  python = directory / "consumer" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
  config = directory / "mypy.ini"
  config.write_text("[mypy]\nstrict = true\n", encoding="utf-8")
  source = directory / "alias_typing.py"
  positive = (
    "from doushu.birth import Gender, LunarBirthRecord\n"
    "from doushu.chart import ZiweiChart, create_chart\n"
    "from doushu.config import ChartConfig\n"
    "from doushu.ganzhi import Dizhi\n"
    "from doushu.knowledge import load_catalog\n"
    "from doushu.knowledge.catalog import Catalog, Record\n"
    "from doushu.sihua import SihuaVariant\n"
    "from ziwei.birth import Gender as PrimaryGender\n"
    "from ziwei.chart import ZiweiChart as PrimaryChart\n"
    "def gender(value: PrimaryGender) -> Gender:\n  return value\n"
    "def chart(record: LunarBirthRecord, choices: ChartConfig) -> PrimaryChart:\n"
    "  result: ZiweiChart = create_chart(record, choices, sihua_variant=SihuaVariant.排命盘口诀转录)\n  return result\n"
    "catalog: Catalog = load_catalog()\n"
    "entry: Record = catalog.get('concept.star.ziwei')\n"
    "record = LunarBirthRecord(year=2024, month=1, day=1, is_leap_month=False, "
    "shichen=Dizhi.子, gender=Gender.女)\n"
    "from doushu.birth import 出生记录, 农历出生记录\n"
    "from doushu.ganzhi import 地支\n"
    "from doushu.liunian import 流年星曜\n"
    "from ziwei.liunian import LiunianStars\n"
    "def annual(value: LiunianStars) -> 流年星曜:\n  return value\n"
    "reading: 流年星曜 = 流年星曜(2024)\n"
    "position: 地支 = reading.陀罗\n"
    "chinese_record: 出生记录 = 农历出生记录(year=2024, month=1, day=1, "
    "is_leap_month=False, shichen=地支.子, gender=Gender.未知)\n"
    "from doushu.chart import liunian_palaces, 流年宫位\n"
    "from doushu.liunian import 流年四化\n"
    "from doushu.stars import Star\n"
    "from ziwei.chart import LiunianPalaceView\n"
    "annual_marks: 流年四化 = 流年四化(2030, variant=SihuaVariant.王亭之讲义转录)\n"
    "annual_ke: Star = annual_marks.化科\n"
    "def annual_rows(value: PrimaryChart) -> tuple[流年宫位, ...]:\n"
    "  return liunian_palaces(value, 2030, sihua_variant=SihuaVariant.王亭之讲义转录)\n"
    "def annual_row(value: 流年宫位) -> LiunianPalaceView:\n  return value\n"
  )
  env = {k: v for k, v in os.environ.items() if k not in {"MYPYPATH", "PYTHONPATH"}}
  env["PYTHONUTF8"] = "1"
  env["PYTHONIOENCODING"] = "utf-8"
  command = (
    sys.executable,
    "-m",
    "mypy",
    "--config-file",
    str(config),
    "--no-incremental",
    "--show-traceback",
    "--python-executable",
    str(python),
    str(source),
  )
  for text, code, diagnostic in (
    (positive, 0, ""),
    (positive.replace("year=2024", "year='bad'"), 1, "[arg-type]"),
    (positive + "reading.陁罗\n", 1, "[attr-defined]"),
    (positive + "reading.陀罗 = 地支.子\n", 1, "[misc]"),
    (positive + "地支.不存在\n", 1, "[attr-defined]"),
    (positive + "流年星曜(纪年=2024)\n", 1, "[call-arg]"),
    (positive + "流年四化(2030)\n", 1, "[call-arg]"),
    (positive + "annual_marks.化科 = Star.天府\n", 1, "[misc]"),
  ):
    source.write_text(text, encoding="utf-8")
    result = subprocess.run(command, cwd=directory, env=env, capture_output=True, encoding="utf-8")
    for output in (result.stdout, result.stderr):
      print(output.encode("ascii", errors="backslashreplace").decode("ascii"), flush=True)
    if result.returncode not in (0, 1) or "INTERNAL ERROR" in result.stdout + result.stderr:
      raise ValueError("Installed alias typing failed: mypy crashed")
    if result.returncode != code or (code == 1 and diagnostic not in result.stdout):
      raise ValueError("Installed alias typing returned an unexpected exit code or diagnostic")


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("command", choices=("build", "prepare"))
  parser.add_argument("--directory", type=Path, default=Path("dist-doushu"))
  args = parser.parse_args()
  version = project(ROOT)["version"]
  if args.command == "build":
    with tempfile.TemporaryDirectory(prefix="doushu-build-", dir=os.environ.get("SCRATCH")) as tmp:
      wheel = build_alias(Path(tmp) / "build")
      preserve_alias(wheel, file_sha256(wheel), args.directory)
  digest = read_alias_checksum(args.directory, version)
  verify_alias_bundle(args.directory, version, digest)
  outputs = {"doushu_wheel_name": wheel_name(version), "doushu_wheel_sha256": digest}
  if output := os.environ.get("GITHUB_OUTPUT"):
    with Path(output).open("a", encoding="utf-8") as stream:
      stream.writelines(f"{key}={value}\n" for key, value in outputs.items())
  print(json.dumps(outputs, sort_keys=True))


if __name__ == "__main__":
  main()
