"""记录往返保真、严格拒绝与恢复不求值；不把往返计为计算正确性。"""

import json
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import replace
from datetime import date, time, timedelta
from pathlib import Path
from typing import Any

import pytest

from ziwei.birth import Gender, GregorianBirthRecord, TimePrecision
from ziwei.chart import ZiweiChart, create_chart, recalculate
from ziwei.config import ChartConfig, YearBoundary
from ziwei.serialization import SCHEMA_VERSION, dumps_chart, loads_chart
from ziwei.sihua import SihuaVariant
from ziwei.timezone import FixedOffset, IanaTimezone


@pytest.fixture(autouse=True)
def _unload_celestial() -> Iterator[None]:
  yield
  for name in tuple(sys.modules):
    if name.startswith("celestial_calendar"):
      del sys.modules[name]


@pytest.mark.parametrize("which", ["lunar_chart", "civil_chart"])
def test_roundtrip_preserves_every_stored_value(request: pytest.FixtureRequest, which: str) -> None:
  chart: ZiweiChart = request.getfixturevalue(which)
  payload = dumps_chart(chart)
  restored = loads_chart(payload)
  assert restored == chart
  assert dumps_chart(restored) == payload
  assert json.loads(payload)["schema_version"] == SCHEMA_VERSION
  assert recalculate(restored) == chart


@pytest.mark.parametrize("longitude", [None, 116, 116.0, -0.0, 0.0])
def test_numeric_and_text_fidelity(chart_choices: ChartConfig, longitude: float | None) -> None:
  record = GregorianBirthRecord(
    birth_date=date(2024, 7, 1),
    birth_time=time(12, 0, 0, 1),
    time_precision=TimePrecision.微秒,
    timezone=FixedOffset(timedelta(hours=8, microseconds=1)),
    gender=Gender.女,
    longitude_deg=longitude,
    place="江苏省\x1b[31m\ud800",
    source="合成\n记录\x00",
  )
  chart = create_chart(
    record,
    replace(chart_choices, year_boundary=YearBoundary.立春),
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  text = dumps_chart(chart)
  assert text.isascii()  # 孤立代理也可作为转义数据保全，不尝试直接UTF-8编码它。
  restored = loads_chart(text)
  assert type(restored.calculation.record.longitude_deg) is type(longitude)
  assert repr(restored.calculation.record.longitude_deg) == repr(longitude)
  assert restored.calculation.record.place == record.place
  assert restored.calculation.record.source == record.source
  resolved = restored.calculation.resolved_time
  assert resolved is not None
  assert resolved.offset == timedelta(hours=8, microseconds=1)
  assert restored == chart
  assert dumps_chart(restored) == text


def test_actual_and_requested_fold_are_distinct(civil_chart: ZiweiChart) -> None:
  restored = loads_chart(dumps_chart(civil_chart))
  record = restored.calculation.record
  resolved = restored.calculation.resolved_time
  assert isinstance(record, GregorianBirthRecord) and isinstance(record.timezone, IanaTimezone)
  assert record.timezone.fold == 1
  assert resolved is not None and resolved.fold == 1 and resolved.data is not None
  assert resolved.offset == timedelta(hours=8)
  assert resolved.local_time.microsecond == 123456


def test_unambiguous_requested_fold_none_is_preserved(chart_choices: ChartConfig) -> None:
  record = GregorianBirthRecord(
    birth_date=date(2024, 7, 1),
    birth_time=time(12),
    time_precision=TimePrecision.时,
    timezone=IanaTimezone("Asia/Shanghai"),
    gender=Gender.男,
  )
  chart = create_chart(
    record,
    replace(chart_choices, year_boundary=YearBoundary.立春),
    sihua_variant=SihuaVariant.王亭之讲义转录,
  )
  restored = loads_chart(dumps_chart(chart)).calculation.resolved_time
  assert restored is not None and restored.fold == 0
  assert isinstance(restored.zone, IanaTimezone) and restored.zone.fold is None


@pytest.mark.parametrize("which", ["lunar_chart", "civil_chart"])
def test_restore_in_fresh_process_without_native_or_tzdata(
  request: pytest.FixtureRequest,
  which: str,
  tmp_path: Path,
) -> None:
  payload = dumps_chart(request.getfixturevalue(which))
  code = """
import builtins, sys
original = builtins.__import__
def blocked(name, *args, **kwargs):
  if name.startswith(('celestial_calendar', 'tzdata')):
    raise RuntimeError('restore tried to initialize calendar or timezone data')
  return original(name, *args, **kwargs)
builtins.__import__ = blocked
from ziwei.serialization import loads_chart, dumps_chart
text = sys.stdin.read()
value = loads_chart(text)
if dumps_chart(value) != text:
  raise ValueError('not preserved')
if any(n.startswith(('celestial_calendar', 'tzdata')) for n in sys.modules):
  raise RuntimeError('native module loaded')
print('RESTORE_ONLY_OK')
"""
  run = subprocess.run(
    [sys.executable, "-c", code],
    cwd=tmp_path,
    input=payload,
    capture_output=True,
    text=True,
    check=False,
  )
  assert run.returncode == 0, run.stderr
  assert run.stdout.strip() == "RESTORE_ONLY_OK"


@pytest.mark.parametrize(
  "path,bad",
  [
    (("schema_version",), True),
    (("schema_version",), 2),
    (("schema_version",), 1.0),
    (("schema_version",), "1"),
    (("software_version",), ""),
    (("record", "gender"), "UNKNOWN"),
    (("record", "year"), True),
    (("record", "month"), "9"),
    (("record", "day"), 0),
    (("record", "is_leap_month"), 0),
    (("record", "shichen"), None),
    (("record", "longitude_deg"), True),
    (("record", "source"), []),
    (("calculation", "month"), 1),
    (("calculation", "day"), 8),
    (("calculation", "lunar_year"), 5000),
    (("calculation", "ganzhi_year"), 1955),
    (("calculation", "apparent_solar"), 1),
    (("calculation", "day_rolled"), True),
    (("calculation", "ut1_jd"), 1),
    (("calculation", "shichen"), "丑"),
    (("calculation", "lunar_algorithm"), "ALGO3"),
    (("calculation", "supported_lunar_year_range"), [True, 2199]),
    (("calculation", "supported_lunar_year_range"), [1, 9999]),
    (("calculation", "config", "tianma_rule"), "unknown"),
    (("calculation", "config", "year_boundary"), "立春"),
    (("shengong",), "子"),
    (("bureau",), "水二局"),
    (("palaces", 0, "name"), "父母"),
    (("palaces", 0, "tiangan"), "丙"),
    (("stars", 0, "dizhi"), "子"),
    (("stars", -1, "rule_id"), "variant.tianma.year-branch"),
    (("stars", 0, "star"), "天机"),
    (("stars", 0, "rule_id"), "unknown"),
    (("sihua", "rule_id"), "unknown"),
    (("sihua", "ke"), "天府"),
    (("sihua", "year_tiangan"), "乙"),
    (("decades", 0, "rule_id"), "unknown"),
    (("decades", 0, "age_convention"), "周岁"),
    (("decades", 0, "start_age"), True),
    (("decades", 0, "end_age"), 16),
    (("decades", 0, "direction"), "逆行"),
  ],
)
def test_rejects_corrupted_lunar_record(
  lunar_chart: ZiweiChart, path: tuple[Any, ...], bad: Any
) -> None:
  data = json.loads(dumps_chart(lunar_chart))
  target = data
  for key in path[:-1]:
    target = target[key]
  target[path[-1]] = bad
  with pytest.raises(ValueError):
    loads_chart(json.dumps(data))


@pytest.mark.parametrize(
  "path",
  [
    (),
    ("record",),
    ("calculation",),
    ("calculation", "config"),
    ("palaces", 0),
    ("stars", 0),
    ("sihua",),
    ("decades", 0),
  ],
)
@pytest.mark.parametrize("change", ["missing", "extra", "nonobject"])
def test_every_object_has_strict_fields(
  lunar_chart: ZiweiChart, path: tuple[Any, ...], change: str
) -> None:
  data = json.loads(dumps_chart(lunar_chart))
  target = data
  for key in path:
    target = target[key]
  if change == "missing":
    target.pop(next(iter(target)))
  elif change == "extra":
    target["unexpected"] = "value"
  elif path:
    parent = data
    for key in path[:-1]:
      parent = parent[key]
    parent[path[-1]] = []
  else:
    data = []
  with pytest.raises(ValueError):
    loads_chart(json.dumps(data))


@pytest.mark.parametrize("field", ["palaces", "stars", "decades"])
@pytest.mark.parametrize("defect", ["missing", "duplicate", "reversed", "notarray"])
def test_complete_ordered_sequences_required(
  lunar_chart: ZiweiChart, field: str, defect: str
) -> None:
  data = json.loads(dumps_chart(lunar_chart))
  parts = data[field]
  if defect == "missing":
    parts.pop()
  elif defect == "duplicate":
    parts[-1] = parts[0]
  elif defect == "reversed":
    parts.reverse()
  else:
    data[field] = {}
  with pytest.raises(ValueError):
    loads_chart(json.dumps(data))


@pytest.mark.parametrize(
  "payload",
  [
    "null",
    "[]",
    "{",
    '{"schema_version":1,"schema_version":1}',
    '{"schema_version":NaN}',
    '{"schema_version":Infinity}',
    '{"schema_version":-Infinity}',
    '{"schema_version":1e999}',
    '{"schema_version":' + "9" * 5000 + "}",
    "[" * 2000 + "]" * 2000,
  ],
)
def test_invalid_json_has_valueerror_exit(payload: str) -> None:
  with pytest.raises(ValueError):
    loads_chart(payload)


@pytest.mark.parametrize(
  "path,bad",
  [
    (("calculation", "resolved_time"), None),
    (("calculation", "resolved_time", "fold"), True),
    (("calculation", "resolved_time", "fold"), 0),
    (("calculation", "resolved_time", "offset_microseconds"), 28800000001),
    (("calculation", "resolved_time", "data"), None),
    (("calculation", "resolved_time", "data", "iana_version"), ""),
    (("calculation", "resolved_time", "utc"), "1988-09-10T17:30:00.123456"),
    (("calculation", "resolved_time", "local_time"), "1988-09-12T01:30:00.123456"),
    (("calculation", "resolved_time", "unexpected"), 1),
    (("calculation", "ganzhi_year"), 1987),
    (("record", "timezone", "fold"), False),
    (("record", "timezone", "extra"), None),
    (("record", "time_precision"), "时"),
    (("record", "birth_time"), None),
    (("record", "birth_date"), "19880911"),
    (("record", "timezone", "kind"), "unknown"),
  ],
)
def test_resolved_time_rejects_inconsistent_data(
  civil_chart: ZiweiChart, path: tuple[Any, ...], bad: Any
) -> None:
  data = json.loads(dumps_chart(civil_chart))
  target = data
  for key in path[:-1]:
    target = target[key]
  target[path[-1]] = bad
  with pytest.raises(ValueError):
    loads_chart(json.dumps(data))


def test_missing_data_fields_rejected(civil_chart: ZiweiChart) -> None:
  data = json.loads(dumps_chart(civil_chart))
  del data["calculation"]["resolved_time"]["data"]["package_version"]
  with pytest.raises(ValueError):
    loads_chart(json.dumps(data))


@pytest.mark.parametrize("other", [9, 10])
def test_duplicate_nested_key_is_rejected(lunar_chart: ZiweiChart, other: int) -> None:
  text = dumps_chart(lunar_chart).replace('"month": 9,', f'"month": {other}, "month": 9,', 1)
  with pytest.raises(ValueError):
    loads_chart(text)


def test_non_string_inputs_rejected() -> None:
  with pytest.raises(TypeError):
    loads_chart(b"{}")  # type: ignore[arg-type]
  with pytest.raises(TypeError):
    dumps_chart(None)  # type: ignore[arg-type]


def test_string_subclass_with_valid_json_is_rejected(lunar_chart: ZiweiChart) -> None:
  class StringSubclass(str):
    pass

  payload = dumps_chart(lunar_chart)
  assert loads_chart(payload) == lunar_chart
  with pytest.raises(TypeError, match="命盘JSON须为str"):
    loads_chart(StringSubclass(payload))


@pytest.mark.parametrize(
  "kind", ["lunar-instant", "calendar", "zone-object", "zone-kind", "noncanonical-instant"]
)
def test_additional_wire_boundaries(
  lunar_chart: ZiweiChart, civil_chart: ZiweiChart, kind: str
) -> None:
  data = json.loads(
    dumps_chart(lunar_chart if kind in ("lunar-instant", "calendar") else civil_chart)
  )
  if kind == "lunar-instant":
    data["calculation"]["resolved_time"] = json.loads(dumps_chart(civil_chart))["calculation"][
      "resolved_time"
    ]
  elif kind == "calendar":
    data["record"]["calendar"] = "unknown"
  elif kind == "zone-object":
    data["record"]["timezone"] = []
  elif kind == "zone-kind":
    data["record"]["timezone"] = {"kind": "unknown", "offset_microseconds": 0}
  else:
    data["calculation"]["resolved_time"]["utc"] = "19880910T17:30:00.123456+00:00"
  with pytest.raises(ValueError):
    loads_chart(json.dumps(data))


def test_unverified_leap_flag_is_preserved_then_recalculation_rejects(
  civil_chart: ZiweiChart,
) -> None:
  data = json.loads(dumps_chart(civil_chart))
  data["calculation"]["is_leap_month"] = not data["calculation"]["is_leap_month"]
  restored = loads_chart(json.dumps(data))
  assert restored.calculation.is_leap_month != civil_chart.calculation.is_leap_month
  with pytest.raises(ValueError, match="不一致"):
    recalculate(restored)


def test_unavailable_iana_key_has_valueerror_on_recalculation(civil_chart: ZiweiChart) -> None:
  data = json.loads(dumps_chart(civil_chart))
  data["record"]["timezone"]["key"] = "Nowhere/Land"
  restored = loads_chart(json.dumps(data))
  with pytest.raises(ValueError, match="IANA 时区不可用"):
    recalculate(restored)
  assert dumps_chart(restored) == json.dumps(data, ensure_ascii=True, allow_nan=False, indent=2)


def test_pure_civil_path_keeps_unchecked_fold_request(chart_choices: ChartConfig) -> None:
  record = GregorianBirthRecord(
    birth_date=date(2000, 6, 1),
    birth_time=time(12),
    time_precision=TimePrecision.时,
    timezone=IanaTimezone("Asia/Shanghai", fold=1),
    gender=Gender.男,
  )
  chart = create_chart(record, chart_choices, sihua_variant=SihuaVariant.排命盘口诀转录)
  restored = loads_chart(dumps_chart(chart))
  assert restored.calculation.resolved_time is None
  assert restored.calculation.record == record and recalculate(restored) == chart
  with pytest.raises(ValueError, match="fold"):
    create_chart(
      record,
      replace(chart_choices, year_boundary=YearBoundary.立春),
      sihua_variant=SihuaVariant.排命盘口诀转录,
    )
