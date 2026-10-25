"""文档构建配置。"""

import re
import sys
from importlib import metadata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

from tools.knowledge_reference import KnowledgeTargets, render_catalog
from ziwei.knowledge import load_catalog

project = "ziwei"
release = metadata.version("ziwei")
language = "zh_CN"
extensions = ["myst_parser", "sphinx.ext.doctest", "sphinx.ext.autodoc", "sphinx.ext.intersphinx"]
intersphinx_mapping = {
  "python": (
    "https://docs.python.org/3.11/",
    str(Path(__file__).with_name("python-stdlib.inv")),
  )
}
root_doc = "docs/index"
exclude_patterns = [
  ".venv/**",
  ".review/**",
  ".git/**",
  ".pytest_cache/**",
  ".mypy_cache/**",
  ".ruff_cache/**",
  "build/**",
  "dist/**",
  "AGENTS.md",
]
myst_heading_anchors = 6
nitpicky = True
html_theme = "alabaster"
html_title = f"ziwei {release}（开发版）"
html_static_path = ["_static"]
html_css_files = ["layout.css"]


def insert_knowledge_reference(app: Sphinx, docname: str, source: list[str]) -> None:
  """仅在参考页展开记录，Markdown源文件不维护第二份语料或规则表。"""
  if docname == "docs/knowledge-reference":
    rendered = render_catalog(load_catalog())
    fence = "`" * max(3, max((len(run) for run in re.findall(r"`+", rendered)), default=0) + 1)
    source[0] += f"\n{fence}{{raw}} html\n{rendered}\n{fence}\n"


def register_knowledge_targets(app: Sphinx, env: BuildEnvironment) -> None:
  """把生成HTML中的实际锚点提供给MyST，不关闭未知引用警告。"""
  targets = KnowledgeTargets()
  targets.feed(render_catalog(load_catalog()))
  slugs = env.metadata.setdefault("docs/knowledge-reference", {}).setdefault("myst_slugs", {})
  for identifier, tags in targets.targets.items():
    if tags == ["section"]:
      slugs[identifier] = (None, identifier, identifier)


def setup(app: Sphinx) -> None:
  """注册定义生成的知识参考页。"""
  app.connect("source-read", insert_knowledge_reference)
  app.connect("env-updated", register_knowledge_targets)
