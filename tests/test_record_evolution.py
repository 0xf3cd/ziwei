"""在源码副本实际扩默认星集；旧盘仍按原星集恢复、保存和求值。"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

CHECK = """
import json, sys
from dataclasses import replace
sys.path.insert(0, sys.argv[1])
from ziwei import stars
from ziwei.chart import create_chart, recalculate
from ziwei.serialization import loads_chart, dumps_chart, UnsupportedSchemaVersionError
from pathlib import Path
text = Path(sys.argv[2]).read_text()
old = loads_chart(text)
expected = int(sys.argv[3])
assert len(stars.Star) == expected
assert len(stars.place_stars(old.calculation)) == expected
assert len(old.stars) == 28
assert replace(old) == old
assert dumps_chart(old) == text
assert recalculate(old).stars == old.stars
for broken in (old.stars[:-1], old.stars[::-1], (*old.stars[:-1], old.stars[0])):
  try:
    replace(old, stars=broken)
  except ValueError:
    pass
  else:
    raise AssertionError('incomplete historical group accepted')
current = create_chart(old.calculation.record, old.calculation.config, sihua_variant=old.sihua.variant)
assert len(current.stars) == expected
if expected == 29:
  try:
    dumps_chart(current)
  except ValueError as error:
    assert 'schema 1' in str(error)
  else:
    raise AssertionError('schema 1 expanded silently')
  raw = json.loads(text)
  raw['stars'].append({'star': '测试星', 'dizhi': '子', 'rule_id': 'variant.test.future'})
  try:
    loads_chart(json.dumps(raw))
  except ValueError as error:
    assert not isinstance(error, UnsupportedSchemaVersionError)
  else:
    raise AssertionError('schema 1 accepted the future group')
print('EVOLUTION_OK', expected)
"""


@pytest.mark.parametrize("future", [False, True])
def test_real_default_expansion_does_not_expand_historical_schema(
  tmp_path: Path, future: bool
) -> None:
  source = tmp_path / "src"
  shutil.copytree(
    ROOT / "src/ziwei", source / "ziwei", ignore=shutil.ignore_patterns("__pycache__")
  )
  if future:
    path = source / "ziwei/stars.py"
    code = path.read_text()
    marker = "  紫微 = ZIWEI"
    assert code.count(marker) == 1
    code = code.replace(
      marker, '  FUTURE = "测试星", "concept.star.future"\n  测试星 = FUTURE\n' + marker
    )
    marker = "  return _place_natal_stars_v1(value)"
    assert code.count(marker) == 2
    code = code.replace(
      marker, "  return (*_place_natal_stars_v1(value), _placement(Star.测试星, Dizhi.子))", 1
    )
    marker = "  if stars != _NATAL_STARS_V1:"
    assert code.count(marker) == 1
    code = code.replace(
      marker,
      "  if stars == (*_NATAL_STARS_V1, Star.测试星):\n    return place_stars(value)\n" + marker,
    )
    code += """
STAR_RULES = (*STAR_RULES, StarRule(
  'variant.test.future', '测试', (Star.测试星,), '隔离演进例', 'ziwei.stars.place_stars'))
"""
    path.write_text(code)
  result = subprocess.run(
    [
      sys.executable,
      "-I",
      *(["-O"] if sys.flags.optimize else []),
      "-c",
      f"exec(compile({CHECK!r}, '<evolution>', 'exec', optimize=0))",
      str(source),
      str(ROOT / "tests/fixtures/v010/lunar.json"),
      "29" if future else "28",
    ],
    cwd=tmp_path,
    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    text=True,
    capture_output=True,
    check=True,
  )
  assert result.stdout.strip() == f"EVOLUTION_OK {29 if future else 28}"
