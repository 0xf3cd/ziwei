"""运行仓库检查。"""

from __future__ import annotations

import ast
import os
import re
import shutil
import sys
import tempfile
import tomllib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

# 直接运行tools/check.py时，脚本目录而非仓根在sys.path首位。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.artifacts import (
  built_artifacts,
  check_sdist,
  check_wheel,
  file_sha256,
  preserve_artifacts,
  source_members,
)
from tools.consumption import install_and_consume, run
from tools.knowledge_reference import check_knowledge_reference

ROOT = Path(__file__).resolve().parents[1]


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
  """核公开定义、类型别名和有变量说明的 Final 常量的真实 HTML 签名。"""
  expected: set[str] = set()
  for module in (root / "src/ziwei").rglob("*.py"):
    parts = module.relative_to(root / "src").with_suffix("").parts
    namespace = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
    nodes = ast.parse(module.read_text(encoding="utf-8")).body
    for index, node in enumerate(nodes):
      if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        annotation = node.annotation
        if isinstance(annotation, ast.Subscript):
          annotation = annotation.value
        kind = annotation.id if isinstance(annotation, ast.Name) else None
        if (
          isinstance(annotation, ast.Attribute)
          and isinstance(annotation.value, ast.Name)
          and annotation.value.id == "typing"
        ):
          kind = annotation.attr
        following = nodes[index + 1] if index + 1 < len(nodes) else None
        documented = (
          isinstance(following, ast.Expr)
          and isinstance(following.value, ast.Constant)
          and isinstance(following.value.value, str)
        )
        if (
          kind == "TypeAlias" or (kind == "Final" and documented)
        ) and not node.target.id.startswith("_"):
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


def check_distribution(directory: Path, *, artifacts_dir: Path | None = None) -> None:
  """从锁定后端构建sdist→wheel、隔离消费，可显式保留同一份已核产物。"""
  metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
  version = metadata["version"]
  # 旧的 SOURCES.txt 会把已从清单删除的文件带回 sdist，掩盖清单变化。
  for stale in ROOT.glob("src/*.egg-info"):
    shutil.rmtree(stale)
  artifacts = directory / "artifacts"
  run((sys.executable, "-m", "build", "--no-isolation", "--outdir", str(artifacts)), cwd=ROOT)
  sdist, wheel = built_artifacts(artifacts)
  hashes = {path: file_sha256(path) for path in (sdist, wheel)}
  check_sdist(sdist, version, source_members(ROOT))
  check_wheel(wheel, version)
  run((sys.executable, "-m", "twine", "check", str(sdist), str(wheel)), cwd=ROOT)
  install_and_consume(wheel, version, directory, root=ROOT)
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
      ),
      cwd=ROOT,
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
    run((sys.executable, *arguments), cwd=ROOT)
  check_documents()
  with tempfile.TemporaryDirectory(
    prefix="ziwei-check-", dir=os.environ.get("SCRATCH")
  ) as temporary:
    directory = Path(temporary)
    check_examples(sphinx_report(directory))
    check_api_reference(directory / "html")
    check_knowledge_reference(directory / "html")
    check_distribution(directory, artifacts_dir=artifacts_dir)
  print("All checks passed.")


if __name__ == "__main__":
  import argparse

  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
    "--artifacts-dir",
    type=Path,
    help="把已核sdist、wheel与SHA256SUMS保存到此目录；目录须不存在或为空",
  )
  main(artifacts_dir=parser.parse_args().artifacts_dir)
