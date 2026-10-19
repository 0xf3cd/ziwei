"""独立知识目录；显式加载语料，不导入命盘或历法适配。"""

from ziwei.knowledge.catalog import Catalog


def load_catalog() -> Catalog:
  """构造内置不可变目录；不联网、读文件或计算命盘。"""
  from ziwei.knowledge.data import CATALOG_VERSION, CITATIONS, CONCEPTS, ENTRIES, SOURCES, VARIANTS

  return Catalog(
    version=CATALOG_VERSION,
    concepts=CONCEPTS,
    variants=VARIANTS,
    sources=SOURCES,
    citations=CITATIONS,
    entries=ENTRIES,
  )
