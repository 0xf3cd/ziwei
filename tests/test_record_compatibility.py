"""固定发行文件验证保全；恢复、再次保存与重新求值分别验收。"""

import ast
import hashlib
import importlib
import json
import math
import subprocess
import sys
from dataclasses import replace
from datetime import date, datetime, time
from enum import StrEnum
from pathlib import Path
from typing import Any

import pytest

from ziwei import calendar
from ziwei import chart as chart_module
from ziwei import stars as stars_module
from ziwei.birth import CalculationInput
from ziwei.chart import recalculate
from ziwei.knowledge import load_catalog
from ziwei.serialization import UnsupportedSchemaVersionError, dumps_chart, loads_chart
from ziwei.sihua import SihuaVariant
from ziwei.stars import STAR_RULES, Star

FIXTURES = Path(__file__).parent / "fixtures/v010"
PROVENANCE = json.loads((FIXTURES / "provenance.json").read_text())
CASES = tuple(PROVENANCE["cases"])


def _assert_stored_values(actual: Any, expected: Any) -> None:
  if isinstance(expected, dict):
    for key, value in expected.items():
      if isinstance(actual, dict):
        member = actual[key]
      elif key in ("calendar", "kind"):
        member = {
          "GregorianBirthRecord": "公历",
          "LunarBirthRecord": "农历",
          "IanaTimezone": "IANA",
          "FixedOffset": "固定偏移",
        }[type(actual).__name__]
      elif key == "offset_microseconds":
        offset = actual.offset
        member = (offset.days * 86400 + offset.seconds) * 1_000_000 + offset.microseconds
      else:
        member = getattr(actual, key)
      _assert_stored_values(member, value)
  elif isinstance(expected, list):
    assert isinstance(actual, tuple)
    assert len(actual) == len(expected)
    for member, value in zip(actual, expected, strict=True):
      _assert_stored_values(member, value)
  else:
    if isinstance(actual, StrEnum):
      actual = actual.value
    elif isinstance(actual, date | datetime | time):
      actual = actual.isoformat()
    assert type(actual) is type(expected)
    assert actual == expected
    if isinstance(expected, float):
      assert math.copysign(1, actual) == math.copysign(1, expected)


@pytest.mark.parametrize("name", CASES)
def test_published_file_restores_every_stored_value(name: str) -> None:
  raw = json.loads((FIXTURES / f"{name}.json").read_text())
  chart = loads_chart((FIXTURES / f"{name}.json").read_text())
  actual = {key: getattr(chart, key) for key in raw if key not in ("schema_version", "record")}
  actual.update(schema_version=1, record=chart.calculation.record)
  _assert_stored_values(actual, raw)
  assert chart.software_version == "0.1.0" and len(chart.stars) == 28


@pytest.mark.parametrize("name", CASES)
def test_published_file_resaves_original_bytes(name: str) -> None:
  original = (FIXTURES / f"{name}.json").read_bytes()
  assert dumps_chart(loads_chart(original.decode("ascii"))).encode("ascii") == original


@pytest.mark.parametrize("name", CASES)
def test_published_file_recalculates_without_changing_original(name: str) -> None:
  text = (FIXTURES / f"{name}.json").read_text()
  original = loads_chart(text)
  result = recalculate(original)
  assert result.calculation == original.calculation
  assert result.stars == original.stars
  assert result.palaces == original.palaces and result.sihua == original.sihua
  assert result.decades == original.decades
  assert dumps_chart(original) == text


def test_history_sources_and_identifiers_are_fixed() -> None:
  for name, digest in PROVENANCE["sha256"].items():
    assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == digest
  baseline = json.loads((FIXTURES / "identifiers.json").read_text())
  for qualified, expected in baseline["enum_values"].items():
    module, name = qualified.rsplit(".", 1)
    kind = getattr(importlib.import_module(module), name)
    for member, value in expected.items():
      assert kind[member].value == value
  concepts = {star.value: star.concept_id for star in Star}
  assert concepts.items() >= baseline["star_concepts"].items()
  rules = {rule.id: [star.value for star in rule.stars] for rule in STAR_RULES}
  for rule_id, stars in baseline["star_rules"].items():
    assert rules[rule_id] == stars
  for variant in SihuaVariant:
    if variant.value in baseline["sihua_rules"]:
      assert variant.rule_id == baseline["sihua_rules"][variant.value]
  from ziwei.decades import DECADE_RULE_ID

  assert baseline["decade_rule"] == DECADE_RULE_ID
  catalog = load_catalog()
  for identifier in baseline["knowledge_ids"]:
    assert catalog.get(identifier).id == identifier


def test_all_historical_files_restore_without_generation_or_resources(tmp_path: Path) -> None:
  code = """
import builtins, sys, zoneinfo, _zoneinfo
from pathlib import Path
real_import = builtins.__import__
def guard(name, *args, **kwargs):
  if name.split('.')[0] in ('celestial_calendar', 'tzdata'):
    raise RuntimeError('resource import attempted: ' + name)
  return real_import(name, *args, **kwargs)
def reject(*args, **kwargs):
  raise RuntimeError('generation or timezone resource access attempted')
builtins.__import__ = guard
zoneinfo.ZoneInfo = _zoneinfo.ZoneInfo = reject
from ziwei import chart, resolver
chart.create_chart = chart.recalculate = resolver.resolve = reject
from ziwei.serialization import loads_chart
for name in sys.argv[2:]:
  restored = loads_chart((Path(sys.argv[1]) / (name + '.json')).read_text())
  if len(restored.stars) != 28 or restored.software_version != '0.1.0':
    raise RuntimeError('historical values changed')
if any(n.split('.')[0] in ('celestial_calendar', 'tzdata') for n in sys.modules):
  raise RuntimeError('resource was loaded')
print('RESTORE_ONLY_OK', len(sys.argv[2:]))
"""
  result = subprocess.run(
    [
      sys.executable,
      *(["-O"] if sys.flags.optimize else []),
      "-c",
      code,
      str(FIXTURES.resolve()),
      *CASES,
    ],
    cwd=tmp_path,
    text=True,
    capture_output=True,
    check=True,
  )
  assert result.stdout.strip() == f"RESTORE_ONLY_OK {len(CASES)}"


@pytest.mark.parametrize("version", [0, 2, 999, -1])
def test_unknown_schema_precedes_new_fields_and_components(version: int) -> None:
  data = json.loads((FIXTURES / "lunar.json").read_text())
  data.update(schema_version=version, future_component={"new_field": []})
  with pytest.raises(UnsupportedSchemaVersionError) as error:
    loads_chart(json.dumps(data))
  assert error.value.schema_version == version


def test_known_schema_rejects_new_component_as_content_not_version() -> None:
  data = json.loads((FIXTURES / "lunar.json").read_text())
  data["future_component"] = {}
  with pytest.raises(ValueError) as error:
    loads_chart(json.dumps(data))
  assert not isinstance(error.value, UnsupportedSchemaVersionError)
  assert error.value.__cause__ is not None


@pytest.mark.parametrize("bounds", [(1, 9999), (1900, 2100), (2001, 2100)])
def test_current_range_changes_do_not_reinterpret_history(
  monkeypatch: pytest.MonkeyPatch, bounds: tuple[int, int]
) -> None:
  monkeypatch.setitem(calendar._ALGORITHM_RANGE, calendar.LunarAlgorithm.混合, bounds)
  text = (FIXTURES / "lunar.json").read_text()
  restored = loads_chart(text)
  assert restored.calculation.supported_lunar_year_range == (1600, 2199)
  assert dumps_chart(restored) == text
  if bounds[0] > 2000:
    with pytest.raises(ValueError, match="当前算法支持范围"):
      recalculate(restored)
  else:
    result = recalculate(restored)
    assert result.stars == restored.stars and result.decades == restored.decades
    assert result.calculation.supported_lunar_year_range == bounds


@pytest.mark.parametrize("bounds", [[1, 9999], [1950, 2050], [2000, 2000]])
def test_legal_historical_range_is_preserved_without_certifying_source(bounds: list[int]) -> None:
  data = json.loads((FIXTURES / "lunar.json").read_text())
  data["calculation"]["supported_lunar_year_range"] = bounds
  restored = loads_chart(json.dumps(data))
  assert restored.calculation.supported_lunar_year_range == tuple(bounds)
  assert json.loads(dumps_chart(restored))["calculation"]["supported_lunar_year_range"] == bounds
  assert recalculate(restored).stars == restored.stars


@pytest.mark.parametrize(
  "bounds",
  [
    [],
    [1600],
    [1600, 2199, 2200],
    [True, 2199],
    [1600.0, 2199],
    [2199, 1600],
    [0, 2199],
    [1, 10000],
    [2001, 2199],
  ],
)
def test_invalid_range_snapshot_is_rejected(bounds: Any) -> None:
  data = json.loads((FIXTURES / "lunar.json").read_text())
  data["calculation"]["supported_lunar_year_range"] = bounds
  with pytest.raises(ValueError):
    loads_chart(json.dumps(data))


def test_range_snapshot_copies_callers_sequence() -> None:
  value = loads_chart((FIXTURES / "lunar.json").read_text()).calculation
  bounds = [1600, 2199]
  copy = replace(value, supported_lunar_year_range=bounds)  # type: ignore[arg-type]
  bounds.clear()
  assert copy.supported_lunar_year_range == (1600, 2199)


def test_restoration_keeps_unavailable_dependency_version() -> None:
  data = json.loads((FIXTURES / "lunar.json").read_text())
  data["calculation"]["lunar_algorithm_version"] = "unavailable"
  restored = loads_chart(json.dumps(data))
  assert restored.calculation.lunar_algorithm_version == "unavailable"
  with pytest.raises(ValueError, match="celestial 版本不可用"):
    recalculate(restored)


def test_history_never_calls_current_default_star_entry(monkeypatch: pytest.MonkeyPatch) -> None:
  def reject(*args: Any, **kwargs: Any) -> Any:
    raise RuntimeError("current default star entry called")

  monkeypatch.setattr(chart_module, "place_stars", reject)
  monkeypatch.setattr(stars_module, "place_stars", reject)
  text = (FIXTURES / "lunar.json").read_text()
  original = loads_chart(text)
  assert replace(original) == original
  assert recalculate(original).stars == original.stars
  assert dumps_chart(original) == text


def test_v010_constructor_does_not_require_new_snapshot_keyword() -> None:
  value = loads_chart((FIXTURES / "lunar.json").read_text()).calculation
  legacy = CalculationInput(
    record=value.record,
    lunar_year=value.lunar_year,
    month=value.month,
    day=value.day,
    is_leap_month=value.is_leap_month,
    shichen=value.shichen,
    ganzhi_year=value.ganzhi_year,
    config=value.config,
    lunar_algorithm=value.lunar_algorithm,
    lunar_algorithm_version=value.lunar_algorithm_version,
    apparent_solar=value.apparent_solar,
    day_rolled=value.day_rolled,
    ut1_jd=value.ut1_jd,
    lichun_jd=value.lichun_jd,
    resolved_time=value.resolved_time,
  )
  assert legacy == value and legacy.supported_lunar_year_range == (1600, 2199)


def test_reproduction_constants_match_fixed_provenance() -> None:
  tree = ast.parse((FIXTURES / "generate.py").read_text())
  constants = {
    node.targets[0].id: ast.literal_eval(node.value)
    for node in tree.body
    if isinstance(node, ast.Assign)
    and isinstance(node.targets[0], ast.Name)
    and node.targets[0].id in ("SOURCE_SHA", "WHEEL_SHA256")
  }
  assert constants == {
    "SOURCE_SHA": PROVENANCE["source_sha"],
    "WHEEL_SHA256": PROVENANCE["wheel_sha256"],
  }


@pytest.mark.parametrize("key", ["ut1_jd", "lichun_jd"])
def test_julian_days_require_float_but_do_not_certify_astronomy(key: str) -> None:
  data = json.loads((FIXTURES / "instant-iana.json").read_text())
  data["calculation"][key] = 1
  with pytest.raises(ValueError):
    loads_chart(json.dumps(data))
  data = json.loads((FIXTURES / "instant-iana.json").read_text())
  for field in ("ut1_jd", "lichun_jd"):
    data["calculation"][field] -= 10_000_000.0
  restored = loads_chart(json.dumps(data))
  assert getattr(restored.calculation, key) == data["calculation"][key] < 0
  with pytest.raises(ValueError, match="重算结果"):
    recalculate(restored)


@pytest.mark.parametrize(
  "key",
  ["bad\nkey", "bad\x1b[31mkey", "a" * 2000, "汉" * 2000],
  ids=["newline", "escape", "long-ascii", "long-chinese"],
)
def test_content_error_diagnostic_is_escaped_bounded_and_chained(key: str) -> None:
  data = json.loads((FIXTURES / "lunar.json").read_text())
  data[key] = "\ud800\udc00"
  with pytest.raises(ValueError) as raised:
    loads_chart(json.dumps(data, ensure_ascii=False))
  diagnostic = str(raised.value)
  assert len(diagnostic) < 300
  assert "\n" not in diagnostic and "\x1b" not in diagnostic
  assert raised.value.__cause__ is not None
  assert key in str(raised.value.__cause__)
