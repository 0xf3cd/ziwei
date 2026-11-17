"""在改写过的stars源码副本上导入星曜，核概念标识不随成员名、显示名或别名变化。

程序导入的是测试临时改写的源码副本，所以不做静态类型检查。
"""

# mypy: ignore-errors

import sys

sys.path.insert(0, sys.argv[1])
if sys.argv[3]:
  sys.stderr.reconfigure(encoding=sys.argv[3], errors="backslashreplace")
try:
  from ziwei.stars import Star
except ValueError as error:
  if sys.argv[2] != "missing-id" or str(error) != "新增星曜须显式指定知识标识":
    raise
  print("MISSING_ID_REJECTED")
  raise SystemExit(0) from None
if sys.argv[2] == "missing-id":
  raise RuntimeError("missing identity accepted")
from ziwei.knowledge import load_catalog

catalog = load_catalog()
for star in Star:
  if catalog.get(star.concept_id).name != star.value:
    raise RuntimeError("star concept mismatch")
if Star.紫微.concept_id != "concept.star.ziwei":
  raise RuntimeError("renamed member changed identity")
if sys.argv[2] == "rename" and Star.紫微.name != "ZIWEI_RENAMED":
  raise RuntimeError("rename was not applied")
if sys.argv[2] == "display-name" and Star.紫微.value != "紫微（显示名）":
  raise RuntimeError("display name was not changed")
if sys.argv[2] == "alias" and Star.新增别名 is not Star.紫微:
  raise RuntimeError("alias was not added")
if sys.argv[2] == "rule-name":
  rule = catalog.get("variant.star.ziwei-series")
  if rule.name != "紫微系显示名" or "concept.star.tianji" not in rule.concept_ids:
    raise RuntimeError("rule display name changed identity")
print("CONCEPTS_OK", len(Star))
