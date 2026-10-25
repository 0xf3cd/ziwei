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
  """要求项目入口、完整盘指南和贡献指南各有已执行的例子。"""
  for document in ("README", "docs/chart", "docs/contributing"):
    marker = f"Document: {document}\n"
    section = re.split(r"(?m)^Document: ", report.partition(marker)[2], maxsplit=1)[0]
    if not re.search(r"(?m)^[1-9]\d* tests? in \d+ items?\.$", section):
      raise ValueError(f"No executed documentation examples in {document}")


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
  """检查公开定义、类型别名与带说明的 Final 常量是否出现在生成的 API 签名中。"""
  expected: set[str] = set()
  for module in (root / "src/ziwei").rglob("*.py"):
    parts = module.relative_to(root / "src").with_suffix("").parts
    namespace = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
    source = module.read_text(encoding="utf-8")
    lines = source.split("\n")
    nodes = ast.parse(source).body
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
        ) or (node.lineno > 1 and lines[node.lineno - 2].lstrip().startswith("#:"))
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
  directory = directory.resolve()
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
        "-d",
        str(directory / ".doctrees" / builder),
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


def check_documentation(directory: Path) -> None:
  """在不存在或为空的目录中构建并核验站点，不删除已有内容。"""
  if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
    raise ValueError(f"Documentation output must be an empty directory or not exist: {directory}")
  check_documents(ROOT)
  check_examples(sphinx_report(directory))
  html = directory / "html"
  check_api_reference(html, ROOT)
  check_knowledge_reference(html)
  if not (html / "docs/index.html").is_file():
    raise ValueError("Missing documentation entry point: docs/index.html")
  (html / "index.html").write_text(
    '<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
    '<meta http-equiv="refresh" content="0; url=docs/index.html">\n'
    "<title>ziwei</title>\n</head>\n<body>\n"
    '<a href="docs/index.html">文档入口</a>\n</body>\n</html>\n',
    encoding="utf-8",
  )


def main(*, artifacts_dir: Path | None = None, docs_dir: Path | None = None) -> None:
  """运行全部检查，或只构建并核验文档；失败即停止。"""
  if docs_dir is not None:
    if artifacts_dir is not None:
      raise ValueError("docs_dir and artifacts_dir are mutually exclusive")
    check_documentation(docs_dir.resolve())
    print("Documentation checks passed.")
    return
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
  with tempfile.TemporaryDirectory(
    prefix="ziwei-check-", dir=os.environ.get("SCRATCH")
  ) as temporary:
    directory = Path(temporary)
    check_documentation(directory)
    check_distribution(directory, artifacts_dir=artifacts_dir)
  print("All checks passed.")


if __name__ == "__main__":
  import argparse

  parser = argparse.ArgumentParser(description=__doc__)
  outputs = parser.add_mutually_exclusive_group()
  outputs.add_argument(
    "--artifacts-dir",
    type=Path,
    help="把已核sdist、wheel与SHA256SUMS保存到此目录；目录须不存在或为空",
  )
  outputs.add_argument(
    "--docs-dir",
    type=Path,
    help="仅构建并核验文档，输出html与doctest子目录；目录须不存在或为空，不自动清理",
  )
  arguments = parser.parse_args()
  main(artifacts_dir=arguments.artifacts_dir, docs_dir=arguments.docs_dir)
