"""文档构建配置。"""

from importlib import metadata
from pathlib import Path

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
