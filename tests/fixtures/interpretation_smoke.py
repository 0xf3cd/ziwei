"""独立进程在原生历法不可导入时读取解释知识。"""

import importlib.abc
import sys


class BlockCalendar(importlib.abc.MetaPathFinder):
  def find_spec(self, fullname: str, *args: object, **kwargs: object) -> None:
    if fullname == "celestial_calendar" or fullname.startswith("celestial_calendar."):
      raise RuntimeError("Knowledge query attempted to load celestial")


sys.meta_path.insert(0, BlockCalendar())

from ziwei.knowledge import load_catalog  # noqa: E402
from ziwei.knowledge.model import EvidenceAspect  # noqa: E402

catalog = load_catalog()
sources = catalog.filter_sources(aspect=EvidenceAspect.解释)
if len(sources) != 1 or sources[0].id != "source.quanshu-juan1-wikisource":
  raise ValueError("Interpretation source query failed")
for name in ("紫微", "天府"):
  (concept,) = catalog.find(name)
  entries = catalog.filter_entries(concept_id=concept.id, source_id=sources[0].id)
  if len(entries) != 2 or any(entry.show_by_default for entry in entries):
    raise ValueError("Interpretation entries or default display changed")
if any(
  name == "celestial_calendar" or name.startswith("celestial_calendar.") for name in sys.modules
):
  raise ValueError("Knowledge query loaded celestial")
print("Interpretation query without celestial: passed")
