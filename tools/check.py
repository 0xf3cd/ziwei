"""运行仓库检查。"""

from __future__ import annotations

import ast
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from collections.abc import Sequence
from email.parser import Parser
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

from markdown_it import MarkdownIt

# 直接运行tools/check.py时，脚本目录而非仓根在sys.path首位。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.knowledge_reference import check_knowledge_reference

ROOT = Path(__file__).resolve().parents[1]
# sdist 须能重建 wheel 并重跑全部检查：源码、测试、工具、文档、锁文件与约定。
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
  "tests/*.py",
  "docs/**/*.md",
  "docs/**/*.py",
  "docs/**/*.inv",
)


def run(command: Sequence[str], *, cwd: Path = ROOT) -> None:
  """执行命令并传播失败。"""
  print(f"+ {' '.join(command)}", flush=True)
  subprocess.run(command, cwd=cwd, check=True)


def document_errors(root: Path) -> tuple[str, ...]:
  """检查文档树与本地文件链接。"""
  errors: list[str] = []
  pages = (root / "README.md", *sorted((root / "docs").rglob("*.md")))
  if not (root / "docs").is_dir() or len(pages) == 1:
    errors.append("docs must contain pages")

  parser = MarkdownIt("commonmark")
  for page in pages:
    if not page.is_file():
      errors.append(f"Missing document: {page.relative_to(root)}")
      continue
    for token in parser.parse(page.read_text(encoding="utf-8")):
      for child in token.children or ():
        target = child.attrGet("href") if child.type == "link_open" else child.attrGet("src")
        if not isinstance(target, str) or not target:
          continue
        url = urlsplit(target)
        if url.scheme or url.netloc or not url.path:
          continue
        if not (page.parent / unquote(url.path)).exists():
          errors.append(f"Broken local link in {page.relative_to(root)}: {target}")
  return tuple(errors)


def check_documents(root: Path = ROOT) -> None:
  """拒绝不完整的文档树。"""
  errors = document_errors(root)
  if errors:
    raise ValueError("\n".join(errors))


def check_examples(report: str) -> None:
  """要求贡献指南有已执行的例子。"""
  marker = "Document: docs/contributing\n"
  section = re.split(r"(?m)^Document: ", report.partition(marker)[2], maxsplit=1)[0]
  if not re.search(r"(?m)^[1-9]\d* tests? in \d+ items?\.$", section):
    raise ValueError("No executed documentation examples in docs/contributing")


class ApiTargets(HTMLParser):
  """收集真正签名元素的标识，不接受渲染成正文的指令文字。"""

  def __init__(self) -> None:
    super().__init__()
    self.targets: set[str] = set()

  def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    if tag == "dt":
      target = dict(attrs).get("id")
      if target is not None:
        self.targets.add(target)


def check_api_reference(directory: Path, root: Path = ROOT) -> None:
  """要求公开类、函数、方法及显式类型别名出现在生成的API签名里。"""
  expected: set[str] = set()
  for module in (root / "src/ziwei").rglob("*.py"):
    parts = module.relative_to(root / "src").with_suffix("").parts
    namespace = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
    for node in ast.parse(module.read_text(encoding="utf-8")).body:
      if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        annotation = node.annotation
        is_type_alias = (isinstance(annotation, ast.Name) and annotation.id == "TypeAlias") or (
          isinstance(annotation, ast.Attribute)
          and annotation.attr == "TypeAlias"
          and isinstance(annotation.value, ast.Name)
          and annotation.value.id == "typing"
        )
        if is_type_alias and not node.target.id.startswith("_"):
          expected.add(f"{namespace}.{node.target.id}")
      if isinstance(node, ast.ClassDef | ast.FunctionDef) and not node.name.startswith("_"):
        name = f"{namespace}.{node.name}"
        expected.add(name)
        if isinstance(node, ast.ClassDef):
          expected.update(
            f"{name}.{member.name}"
            for member in node.body
            if isinstance(member, ast.FunctionDef) and not member.name.startswith("_")
          )
  if not expected:
    raise ValueError("No public API definitions found")
  parser = ApiTargets()
  parser.feed((directory / "docs/api.html").read_text(encoding="utf-8"))
  missing = expected - parser.targets
  if missing:
    raise ValueError("API HTML is missing signatures: " + ", ".join(sorted(missing)))


def source_members(root: Path) -> tuple[str, ...]:
  """列出 sdist 必须携带的工作树文件。"""
  members = set(SOURCE_FILES)
  for pattern in SOURCE_PATTERNS:
    members.update(path.relative_to(root).as_posix() for path in root.glob(pattern))
  return tuple(sorted(members))


def check_sdist(sdist: Path, expected_version: str, members: Sequence[str]) -> None:
  """校验 sdist 身份与内容，拒绝缺文件或夹带审阅材料。"""
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
  if any(name.startswith(f"{base}/.review/") for name in names):
    raise ValueError("Sdist carries review material")


def check_wheel(wheel: Path, expected_version: str) -> None:
  """校验 wheel 内容与元数据。"""
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
  """返回唯一的 sdist 与 wheel。"""
  sdists = tuple(directory.glob("*.tar.gz"))
  wheels = tuple(directory.glob("*.whl"))
  if len(sdists) != 1 or len(wheels) != 1:
    raise ValueError("Expected one sdist and one wheel")
  return sdists[0], wheels[0]


def file_sha256(path: Path) -> str:
  """读取文件的SHA256。"""
  with path.open("rb") as stream:
    return hashlib.file_digest(stream, "sha256").hexdigest()


def install_and_consume(wheel: Path, version: str, directory: Path) -> None:
  """在仓外新环境安装锁定依赖与指定wheel，执行普通和优化模式消费。"""
  if directory.resolve().is_relative_to(ROOT.resolve()):
    raise ValueError("Installed consumption must run outside the repository")
  requirements = directory / "runtime.txt"
  run(
    (
      "uv",
      "export",
      "--locked",
      "--no-dev",
      "--no-emit-project",
      "--no-editable",
      "--output-file",
      str(requirements),
    )
  )
  environment = directory / "consumer"
  run(("uv", "venv", "--python", sys.executable, str(environment)))
  python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
  run(
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
      str(requirements),
    )
  )
  run(("uv", "pip", "install", "--python", str(python), "--no-deps", str(wheel)))
  for mode in ((), ("-O",)):
    run(
      (str(python), *mode, "-I", str(ROOT / "tools/installed_check.py"), version),
      cwd=directory,
    )


def preserve_artifacts(hashes: dict[Path, str], destination: Path) -> None:
  """把已核两文件及原始摘要写入空目录；拒绝覆盖或消费后的篡改。"""
  if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
    raise ValueError("Artifact destination must be an empty directory")
  destination.mkdir(parents=True, exist_ok=True)
  packages = destination / "packages"
  packages.mkdir()
  for path, expected in hashes.items():
    if file_sha256(path) != expected:
      raise ValueError("Artifacts changed during installed consumption")
    copied = packages / path.name
    shutil.copyfile(path, copied)
    if file_sha256(copied) != expected:
      raise ValueError("Artifact copy differs from the verified bytes")
  (destination / "SHA256SUMS").write_text(
    "".join(f"{digest}  {path.name}\n" for path, digest in hashes.items()), encoding="utf-8"
  )


def check_distribution(directory: Path, *, artifacts_dir: Path | None = None) -> None:
  """从锁定后端构建sdist→wheel、隔离消费，可显式保留同一份已核产物。"""
  metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
  version = metadata["version"]
  # 旧的 SOURCES.txt 会把已从清单删除的文件带回 sdist，掩盖清单变化。
  for stale in ROOT.glob("src/*.egg-info"):
    shutil.rmtree(stale)
  artifacts = directory / "artifacts"
  run((sys.executable, "-m", "build", "--no-isolation", "--outdir", str(artifacts)))
  sdist, wheel = built_artifacts(artifacts)
  hashes = {path: file_sha256(path) for path in (sdist, wheel)}
  check_sdist(sdist, version, source_members(ROOT))
  check_wheel(wheel, version)
  run((sys.executable, "-m", "twine", "check", str(sdist), str(wheel)))
  install_and_consume(wheel, version, directory)
  if any(file_sha256(path) != digest for path, digest in hashes.items()):
    raise ValueError("Artifacts changed during installed consumption")
  if artifacts_dir is not None:
    preserve_artifacts(hashes, artifacts_dir)


def sphinx_report(directory: Path) -> str:
  """严格构建 HTML 与 doctest，返回 doctest 报告。"""
  for builder in ("html", "doctest"):
    run(
      (
        sys.executable,
        "-m",
        "sphinx",
        "-E",
        "-a",
        "-n",
        "-W",
        "--keep-going",
        "-b",
        builder,
        "-c",
        "docs",
        ".",
        str(directory / builder),
      )
    )
  return (directory / "doctest/output.txt").read_text(encoding="utf-8")


def main(*, artifacts_dir: Path | None = None) -> None:
  """运行全部检查，失败即停止。"""
  commands = (
    ("-m", "ruff", "check", "."),
    ("-m", "ruff", "format", "--check", "."),
    ("-m", "mypy"),
    ("-m", "pytest", "--cov", "--cov-report=term-missing"),
    # pytest 在 -O 下仍重写测试断言；这里只忽略其他模块的断言禁用警告。
    (
      "-O",
      "-m",
      "pytest",
      "-W",
      "ignore:assertions not in test modules or plugins:pytest.PytestConfigWarning",
    ),
  )
  for arguments in commands:
    run((sys.executable, *arguments))
  check_documents()
  with tempfile.TemporaryDirectory(
    prefix="ziwei-check-", dir=os.environ.get("SCRATCH")
  ) as temporary:
    directory = Path(temporary)
    check_examples(sphinx_report(directory))
    check_api_reference(directory / "html")
    check_knowledge_reference(directory / "html")
    if artifacts_dir is None:
      check_distribution(directory)
    else:
      check_distribution(directory, artifacts_dir=artifacts_dir)
  print("All checks passed.")


if __name__ == "__main__":
  import argparse

  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--artifacts-dir", type=Path, help="保留已核产物与SHA256SUMS的空目录")
  main(artifacts_dir=parser.parse_args().artifacts_dir)
