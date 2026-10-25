"""钉版时区数据、间隙、重叠与拒绝行为。"""

import sys
import zoneinfo
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from errno import EIO
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

from ziwei import timezone as implementation
from ziwei.timezone import (
  AmbiguousTimeError,
  FixedOffset,
  IanaTimezone,
  NonexistentTimeError,
  ResolvedTime,
  TimezoneData,
  current_timezone_data,
  resolve_civil_time,
)


def test_historical_china_summer_time_and_versions() -> None:
  result = resolve_civil_time(datetime(1988, 7, 1, 12), IanaTimezone("Asia/Shanghai"))
  assert result.offset == timedelta(hours=9)
  assert result.utc == datetime(1988, 7, 1, 3, tzinfo=UTC)
  assert result.data is not None
  assert result.data.package_version == version("tzdata")
  assert result.data.iana_version == "2026e"
  winter = resolve_civil_time(datetime(1988, 1, 1, 12), IanaTimezone("Asia/Shanghai"))
  assert winter.offset == timedelta(hours=8)


def test_both_real_shanghai_overlap_instants() -> None:
  wall = datetime(1988, 9, 11, 1, 30)
  with pytest.raises(AmbiguousTimeError):
    resolve_civil_time(wall, IanaTimezone("Asia/Shanghai"))
  for fold, hour, offset in ((0, 16, 9), (1, 17, 8)):
    result = resolve_civil_time(wall, IanaTimezone("Asia/Shanghai", fold=fold))
    assert result.utc == datetime(1988, 9, 10, hour, 30, tzinfo=UTC)
    assert result.local_time == wall
    assert result.offset == timedelta(hours=offset)
    assert isinstance(result.zone, IanaTimezone)
    assert result.fold == result.zone.fold == fold


@pytest.mark.parametrize(
  "wall, offsets",
  [
    (datetime(1988, 4, 17, 1, 59, 59, 999999), (8,)),
    (datetime(1988, 4, 17, 2), ()),
    (datetime(1988, 4, 17, 2, 59, 59, 999999), ()),
    (datetime(1988, 4, 17, 3), (9,)),
    (datetime(1988, 9, 11, 0, 59, 59, 999999), (9,)),
    (datetime(1988, 9, 11, 1), (9, 8)),
    (datetime(1988, 9, 11, 1, 59, 59, 999999), (9, 8)),
    (datetime(1988, 9, 11, 2), (8,)),
  ],
)
@pytest.mark.parametrize("fold", [None, 0, 1])
def test_shanghai_transition_boundaries(
  wall: datetime, offsets: tuple[int, ...], fold: int | None
) -> None:
  error: type[ValueError] | None = None
  if not offsets:
    error = NonexistentTimeError
  elif len(offsets) == 2 and fold is None:
    error = AmbiguousTimeError
  elif len(offsets) == 1 and fold == 1:
    error = ValueError
  if error is not None:
    with pytest.raises(error) as caught:
      resolve_civil_time(wall, IanaTimezone("Asia/Shanghai", fold))
    assert type(caught.value) is error
  else:
    result = resolve_civil_time(wall, IanaTimezone("Asia/Shanghai", fold))
    assert result.offset == timedelta(hours=offsets[fold or 0])
    assert result.fold == (fold or 0)


@pytest.mark.parametrize(
  "key, wall",
  [
    ("Asia/Shanghai", datetime(1988, 4, 17, 2, 30)),
    ("America/New_York", datetime(2020, 3, 8, 2, 30)),
    ("Australia/Lord_Howe", datetime(2020, 10, 4, 2, 15)),
    ("Pacific/Apia", datetime(2011, 12, 30, 12)),
  ],
)
@pytest.mark.parametrize("fold", [None, 0, 1])
def test_gap_is_not_shifted(key: str, wall: datetime, fold: int | None) -> None:
  with pytest.raises(NonexistentTimeError):
    resolve_civil_time(wall, IanaTimezone(key, fold))


def test_python_documentation_overlap_golden() -> None:
  # Python3.11 zoneinfo文档 Using ZoneInfo：洛杉矶2020-11-01 01:00的两个偏移。
  # https://docs.python.org/3.11/library/zoneinfo.html#using-zoneinfo
  wall = datetime(2020, 11, 1, 1)
  a = resolve_civil_time(wall, IanaTimezone("America/Los_Angeles", 0))
  b = resolve_civil_time(wall, IanaTimezone("America/Los_Angeles", 1))
  assert a.utc == datetime(2020, 11, 1, 8, tzinfo=UTC)
  assert b.utc == datetime(2020, 11, 1, 9, tzinfo=UTC)


def test_ordinary_time_does_not_accept_spurious_fold() -> None:
  wall = datetime(2000, 1, 1, 12)
  a = resolve_civil_time(wall, IanaTimezone("Asia/Shanghai"))
  b = resolve_civil_time(wall, IanaTimezone("Asia/Shanghai", 0))
  assert a.utc == b.utc
  assert a.fold == 0
  assert isinstance(a.zone, IanaTimezone)
  assert a.zone.fold is None
  with pytest.raises(ValueError, match="fold"):
    resolve_civil_time(wall, IanaTimezone("Asia/Shanghai", 1))


def test_explicit_offset_is_not_replaced_by_region_rules(monkeypatch: pytest.MonkeyPatch) -> None:
  def forbidden(key: str) -> None:
    raise RuntimeError("固定偏移不得读时区文件")

  monkeypatch.setattr(implementation, "_load_zone", forbidden)
  result = resolve_civil_time(datetime(1988, 7, 1, 12), FixedOffset(timedelta(hours=8)))
  assert result.utc == datetime(1988, 7, 1, 4, tzinfo=UTC)
  assert result.data is None


def test_package_data_wins_over_poisoned_system_data(tmp_path: Path) -> None:
  original = zoneinfo.TZPATH
  target = tmp_path / "Asia/Shanghai"
  target.parent.mkdir()
  target.write_bytes(files("tzdata.zoneinfo").joinpath("UTC").read_bytes())
  try:
    zoneinfo.reset_tzpath((str(tmp_path),))
    zoneinfo.ZoneInfo.clear_cache()
    wall = datetime(1988, 7, 1, 12)
    assert wall.replace(tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")).utcoffset() == timedelta(0)
    before = zoneinfo.TZPATH
    result = resolve_civil_time(wall, IanaTimezone("Asia/Shanghai"))
    assert result.offset == timedelta(hours=9)
    assert before == zoneinfo.TZPATH
  finally:
    zoneinfo.reset_tzpath(original)
    zoneinfo.ZoneInfo.clear_cache()


def test_missing_data_fails_without_system_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setitem(sys.modules, "tzdata", None)
  with pytest.raises(zoneinfo.ZoneInfoNotFoundError) as caught:
    resolve_civil_time(datetime(2000, 1, 1), IanaTimezone("Asia/Shanghai"))
  assert isinstance(caught.value.__cause__, ModuleNotFoundError)


def test_cached_resource_does_not_hide_missing_version_package(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  resolve_civil_time(datetime(2000, 1, 1), IanaTimezone("Asia/Shanghai"))
  assert "tzdata.zoneinfo" in sys.modules
  monkeypatch.setitem(sys.modules, "tzdata", None)
  with pytest.raises(ModuleNotFoundError):
    current_timezone_data()
  with pytest.raises(zoneinfo.ZoneInfoNotFoundError, match="缺少tzdata") as caught:
    IanaTimezone("Asia/Shanghai").require_resolvable()
  assert isinstance(caught.value.__cause__, ModuleNotFoundError)


@pytest.mark.parametrize(
  "error",
  [
    PermissionError("denied"),
    OSError(EIO, "read failed"),
    RuntimeError("runtime"),
    ModuleNotFoundError("unrelated", name="unrelated"),
  ],
)
def test_unrelated_loading_faults_are_not_translated(
  monkeypatch: pytest.MonkeyPatch,
  error: Exception,
) -> None:
  def fail(package: str) -> None:
    raise error

  monkeypatch.setattr(implementation, "files", fail)
  with pytest.raises(type(error)) as caught:
    IanaTimezone("UTC").require_resolvable()
  assert caught.value is error


@pytest.mark.parametrize("key", ["Does/NotExist", "Asia", "leapseconds"])
def test_unknown_zone(key: str) -> None:
  with pytest.raises(zoneinfo.ZoneInfoNotFoundError):
    resolve_civil_time(datetime(2000, 1, 1), IanaTimezone(key))


@pytest.mark.parametrize(
  "resource_error, error",
  [(IsADirectoryError, zoneinfo.ZoneInfoNotFoundError), (PermissionError, PermissionError)],
  ids=["directory", "unreadable-file"],
)
def test_zone_resource_errors_are_distinct(
  monkeypatch: pytest.MonkeyPatch, resource_error: type[OSError], error: type[Exception]
) -> None:
  class Resource:
    def joinpath(self, *parts: str) -> "Resource":
      return self

    def is_dir(self) -> bool:
      return resource_error is IsADirectoryError

    def open(self, mode: str) -> None:
      raise resource_error("资源不可作为时区文件打开")

  monkeypatch.setattr(implementation, "files", lambda package: Resource())
  with pytest.raises(error):
    resolve_civil_time(datetime(2000, 1, 1), IanaTimezone("Asia"))


@pytest.mark.parametrize(
  "key",
  [
    "",
    "/etc/localtime",
    "../UTC",
    "Asia/../UTC",
    "Asia//Shanghai",
    "Asia\\Shanghai",
    "C:/UTC",
    "UTC\x00",
  ],
)
def test_iana_path_validation(key: str) -> None:
  with pytest.raises(ValueError):
    IanaTimezone(key)


def test_package_timezone_keys_pass_identifier_validation() -> None:
  keys = files("tzdata").joinpath("zones").read_text(encoding="utf-8").splitlines()
  assert keys
  for key in keys:
    assert IanaTimezone(key).key == key


@pytest.mark.parametrize("key", [None, 8, ["UTC"]])
def test_iana_type_validation(key: Any) -> None:
  with pytest.raises(TypeError):
    IanaTimezone(key)


@pytest.mark.parametrize(
  "fold, error", [(True, TypeError), ("0", TypeError), (-1, ValueError), (2, ValueError)]
)
def test_fold_validation(fold: Any, error: type[Exception]) -> None:
  with pytest.raises(error):
    IanaTimezone("UTC", fold)


@pytest.mark.parametrize("offset", [timedelta(days=1), -timedelta(days=1)])
def test_offset_range(offset: timedelta) -> None:
  with pytest.raises(ValueError):
    FixedOffset(offset)


@pytest.mark.parametrize("offset", [8, "08:00", None])
def test_offset_type(offset: Any) -> None:
  with pytest.raises(TypeError):
    FixedOffset(offset)


@pytest.mark.parametrize("wall", ["2000-01-01", None])
def test_wall_type(wall: Any) -> None:
  with pytest.raises(TypeError):
    resolve_civil_time(wall, FixedOffset(timedelta(0)))


@pytest.mark.parametrize("wall", [datetime(2000, 1, 1, tzinfo=UTC), datetime(2000, 1, 1, fold=1)])
def test_wall_cannot_hide_its_own_choice(wall: datetime) -> None:
  with pytest.raises(ValueError):
    resolve_civil_time(wall, IanaTimezone("UTC"))


def test_timezone_type() -> None:
  invalid: Any = "UTC"
  with pytest.raises(TypeError):
    resolve_civil_time(datetime(2000, 1, 1), invalid)


def test_utc_epoch_and_datetime_overflow() -> None:
  with pytest.raises(ValueError, match="1972"):
    resolve_civil_time(datetime(1972, 1, 1), FixedOffset(timedelta(hours=8)))
  assert resolve_civil_time(datetime(1972, 1, 1), IanaTimezone("UTC")).utc.year == 1972
  with pytest.raises(ValueError, match="支持范围"):
    resolve_civil_time(datetime(9999, 12, 31, 23), FixedOffset(timedelta(hours=-8)))
  with pytest.raises(ValueError, match="支持范围"):
    resolve_civil_time(datetime(9999, 12, 31, 23), IanaTimezone("Etc/GMT+8"))


@pytest.mark.parametrize(
  "version_value, error", [(None, TypeError), (1, TypeError), ("", ValueError), (" ", ValueError)]
)
def test_data_version_validation(version_value: Any, error: type[Exception]) -> None:
  with pytest.raises(error):
    TimezoneData(version_value, "2026e")
  with pytest.raises(error):
    TimezoneData("2026.5", version_value)


def test_result_is_frozen_and_consistent() -> None:
  value = resolve_civil_time(datetime(2000, 1, 1, 12), IanaTimezone("Asia/Shanghai"))
  for instance, field, replacement in (
    (value, "fold", 1),
    (value.zone, "key", "UTC"),
    (value.data, "package_version", "other"),
    (FixedOffset(timedelta(0)), "offset", timedelta(hours=8)),
  ):
    with pytest.raises(FrozenInstanceError):
      setattr(instance, field, replacement)
  cases: tuple[tuple[dict[str, Any], type[Exception]], ...] = (
    ({"utc": "not a datetime"}, TypeError),
    ({"utc": datetime(2000, 1, 1)}, ValueError),
    ({"utc": datetime(1900, 1, 1, tzinfo=UTC)}, ValueError),
    ({"offset": timedelta(hours=1)}, ValueError),
    ({"zone": "UTC"}, TypeError),
    ({"fold": True}, ValueError),
    ({"data": None}, TypeError),
    ({"zone": IanaTimezone("Asia/Shanghai", 1)}, ValueError),
    ({"zone": FixedOffset(value.offset)}, ValueError),
  )
  for changes, error in cases:
    with pytest.raises(error):
      replace(value, **changes)
  assert isinstance(value, ResolvedTime)


def test_result_copy_does_not_reload_timezone_data(monkeypatch: pytest.MonkeyPatch) -> None:
  value = resolve_civil_time(datetime(2000, 1, 1, 12), IanaTimezone("Asia/Shanghai"))

  def forbidden(name: str) -> None:
    raise RuntimeError("值记录构造不得重新读取时区规则")

  monkeypatch.setattr(implementation, "_load_zone", forbidden)
  monkeypatch.setattr(implementation, "files", forbidden)
  assert replace(value) == value
