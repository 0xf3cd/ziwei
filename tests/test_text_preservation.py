"""字符准入只排除会被 JSON 合并的相邻代理对。"""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from ziwei.chart import ZiweiChart
from ziwei.serialization import dumps_chart, loads_chart

PAIR = "\ud800\udc00"
TEXTS = ("\ud800", "\udfff", "\udc00\ud800", "\U00010000", "江苏省", "a\x00\x1b\n\x1f")
HISTORY = Path(__file__).parent / "fixtures/v010/instant-iana.json"


@pytest.mark.parametrize("which", ["lunar_chart", "civil_chart"])
@pytest.mark.parametrize("field", ["place", "source"])
@pytest.mark.parametrize("text", TEXTS)
def test_accepted_birth_text_has_three_way_preservation(
  request: pytest.FixtureRequest, which: str, field: str, text: str
) -> None:
  chart: ZiweiChart = request.getfixturevalue(which)
  changes: dict[str, Any] = {field: text}
  record = replace(chart.calculation.record, **changes)
  original = replace(chart, calculation=replace(chart.calculation, record=record))
  saved = dumps_chart(original)
  restored = loads_chart(saved)
  assert getattr(original.calculation.record, field) == text
  assert getattr(restored.calculation.record, field) == text
  assert restored == original and dumps_chart(restored) == saved


@pytest.mark.parametrize("which", ["lunar_chart", "civil_chart"])
@pytest.mark.parametrize("field", ["place", "source"])
@pytest.mark.parametrize("text", [PAIR, "前" + PAIR, PAIR + "后", "\udbff\udfff"])
def test_birth_boundary_rejects_adjacent_pairs(
  request: pytest.FixtureRequest, which: str, field: str, text: str
) -> None:
  chart: ZiweiChart = request.getfixturevalue(which)
  changes: dict[str, Any] = {field: text}
  with pytest.raises(ValueError, match="相邻"):
    replace(chart.calculation.record, **changes)


def _string_paths(value: Any, path: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
  if isinstance(value, str):
    return [path]
  if isinstance(value, dict):
    return [p for key, member in value.items() for p in _string_paths(member, (*path, key))]
  if isinstance(value, list):
    return [p for key, member in enumerate(value) for p in _string_paths(member, (*path, key))]
  return []


@pytest.mark.parametrize("path", _string_paths(json.loads(HISTORY.read_text())))
def test_loading_checks_every_string_leaf_before_constructing(path: tuple[Any, ...]) -> None:
  data = json.loads(HISTORY.read_text())
  target = data
  for key in path[:-1]:
    target = target[key]
  target[path[-1]] = PAIR
  with pytest.raises(ValueError, match="相邻"):
    loads_chart(json.dumps(data, ensure_ascii=False))


def test_loading_checks_object_keys_too() -> None:
  data = json.loads(HISTORY.read_text())
  data[PAIR] = None
  with pytest.raises(ValueError, match="相邻"):
    loads_chart(json.dumps(data, ensure_ascii=False))


@pytest.mark.parametrize("field", ["software", "calendar", "package", "iana"])
@pytest.mark.parametrize("text", [PAIR, *TEXTS])
def test_saving_checks_all_caller_controlled_text(
  civil_chart: ZiweiChart, field: str, text: str
) -> None:
  value = civil_chart.calculation
  if field == "software":
    original = replace(civil_chart, software_version=text)
  elif field == "calendar":
    original = replace(civil_chart, calculation=replace(value, lunar_algorithm_version=text))
  else:
    resolved = value.resolved_time
    assert resolved is not None and resolved.data is not None
    key = "package_version" if field == "package" else "iana_version"
    value = replace(
      value, resolved_time=replace(resolved, data=replace(resolved.data, **{key: text}))
    )
    original = replace(civil_chart, calculation=value)
  if text == PAIR:
    with pytest.raises(ValueError, match="相邻"):
      dumps_chart(original)
  else:
    saved = dumps_chart(original)
    restored = loads_chart(saved)
    assert restored == original and dumps_chart(restored) == saved


def test_already_merged_old_escape_pair_cannot_be_guessed_back() -> None:
  data = json.loads(HISTORY.read_text())
  data["record"]["source"] = PAIR
  restored = loads_chart(json.dumps(data))
  assert restored.calculation.record.source == "\U00010000"
  assert restored.calculation.record.source != PAIR
