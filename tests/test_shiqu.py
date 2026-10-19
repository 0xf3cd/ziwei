"""钉版时区数据、间隙、重叠与拒绝行为。"""

import sys
import zoneinfo
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

from ziwei import shiqu as implementation
from ziwei.shiqu import (
  AmbiguousTimeError,
  GudingShiqu,
  IanaShiqu,
  MinyongShike,
  NonexistentTimeError,
  ShiquShuju,
  resolve_minyong_shike,
)


def test_historical_china_summer_time_and_versions() -> None:
  result = resolve_minyong_shike(datetime(1988, 7, 1, 12), IanaShiqu("Asia/Shanghai"))
  assert result.offset == timedelta(hours=9)
  assert result.utc == datetime(1988, 7, 1, 3, tzinfo=UTC)
  assert result.shuju is not None
  assert result.shuju.banben == version("tzdata")
  assert result.shuju.iana_banben == "2026e"
  winter = resolve_minyong_shike(datetime(1988, 1, 1, 12), IanaShiqu("Asia/Shanghai"))
  assert winter.offset == timedelta(hours=8)


def test_both_real_shanghai_overlap_instants() -> None:
  wall = datetime(1988, 9, 11, 1, 30)
  with pytest.raises(AmbiguousTimeError):
    resolve_minyong_shike(wall, IanaShiqu("Asia/Shanghai"))
  for fold, hour, offset in ((0, 16, 9), (1, 17, 8)):
    result = resolve_minyong_shike(wall, IanaShiqu("Asia/Shanghai", fold=fold))
    assert result.utc == datetime(1988, 9, 10, hour, 30, tzinfo=UTC)
    assert result.bendishike == wall
    assert result.offset == timedelta(hours=offset)
    assert isinstance(result.shiqu, IanaShiqu)
    assert result.fold == result.shiqu.fold == fold


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
    resolve_minyong_shike(wall, IanaShiqu(key, fold))


def test_python_documentation_overlap_golden() -> None:
  # Python3.11 zoneinfo文档 Using ZoneInfo：洛杉矶2020-11-01 01:00的两个偏移。
  # https://docs.python.org/3.11/library/zoneinfo.html#using-zoneinfo
  wall = datetime(2020, 11, 1, 1)
  a = resolve_minyong_shike(wall, IanaShiqu("America/Los_Angeles", 0))
  b = resolve_minyong_shike(wall, IanaShiqu("America/Los_Angeles", 1))
  assert a.utc == datetime(2020, 11, 1, 8, tzinfo=UTC)
  assert b.utc == datetime(2020, 11, 1, 9, tzinfo=UTC)


def test_ordinary_time_does_not_accept_spurious_fold() -> None:
  wall = datetime(2000, 1, 1, 12)
  a = resolve_minyong_shike(wall, IanaShiqu("Asia/Shanghai"))
  b = resolve_minyong_shike(wall, IanaShiqu("Asia/Shanghai", 0))
  assert a.utc == b.utc
  assert a.fold == 0
  assert isinstance(a.shiqu, IanaShiqu)
  assert a.shiqu.fold is None
  with pytest.raises(ValueError, match="fold"):
    resolve_minyong_shike(wall, IanaShiqu("Asia/Shanghai", 1))


def test_explicit_offset_is_not_replaced_by_region_rules(monkeypatch: pytest.MonkeyPatch) -> None:
  def forbidden(key: str) -> None:
    raise RuntimeError("固定偏移不得读时区文件")

  monkeypatch.setattr(implementation, "_load_zone", forbidden)
  result = resolve_minyong_shike(datetime(1988, 7, 1, 12), GudingShiqu(timedelta(hours=8)))
  assert result.utc == datetime(1988, 7, 1, 4, tzinfo=UTC)
  assert result.shuju is None


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
    result = resolve_minyong_shike(wall, IanaShiqu("Asia/Shanghai"))
    assert result.offset == timedelta(hours=9)
    assert before == zoneinfo.TZPATH
  finally:
    zoneinfo.reset_tzpath(original)
    zoneinfo.ZoneInfo.clear_cache()


def test_missing_data_fails_without_system_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setitem(sys.modules, "tzdata", None)
  with pytest.raises(ModuleNotFoundError):
    resolve_minyong_shike(datetime(2000, 1, 1), IanaShiqu("Asia/Shanghai"))


@pytest.mark.parametrize("key", ["Does/NotExist", "Asia", "leapseconds"])
def test_unknown_zone(key: str) -> None:
  with pytest.raises(zoneinfo.ZoneInfoNotFoundError):
    resolve_minyong_shike(datetime(2000, 1, 1), IanaShiqu(key))


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
    IanaShiqu(key)


@pytest.mark.parametrize("key", [None, 8, ["UTC"]])
def test_iana_type_validation(key: Any) -> None:
  with pytest.raises(TypeError):
    IanaShiqu(key)


@pytest.mark.parametrize(
  "fold, error", [(True, TypeError), ("0", TypeError), (-1, ValueError), (2, ValueError)]
)
def test_fold_validation(fold: Any, error: type[Exception]) -> None:
  with pytest.raises(error):
    IanaShiqu("UTC", fold)


@pytest.mark.parametrize("offset", [timedelta(days=1), -timedelta(days=1)])
def test_offset_range(offset: timedelta) -> None:
  with pytest.raises(ValueError):
    GudingShiqu(offset)


@pytest.mark.parametrize("offset", [8, "08:00", None])
def test_offset_type(offset: Any) -> None:
  with pytest.raises(TypeError):
    GudingShiqu(offset)


@pytest.mark.parametrize("wall", ["2000-01-01", None])
def test_wall_type(wall: Any) -> None:
  with pytest.raises(TypeError):
    resolve_minyong_shike(wall, GudingShiqu(timedelta(0)))


@pytest.mark.parametrize("wall", [datetime(2000, 1, 1, tzinfo=UTC), datetime(2000, 1, 1, fold=1)])
def test_wall_cannot_hide_its_own_choice(wall: datetime) -> None:
  with pytest.raises(ValueError):
    resolve_minyong_shike(wall, IanaShiqu("UTC"))


def test_timezone_type() -> None:
  invalid: Any = "UTC"
  with pytest.raises(TypeError):
    resolve_minyong_shike(datetime(2000, 1, 1), invalid)


def test_utc_epoch_and_datetime_overflow() -> None:
  with pytest.raises(ValueError, match="1972"):
    resolve_minyong_shike(datetime(1972, 1, 1), GudingShiqu(timedelta(hours=8)))
  assert resolve_minyong_shike(datetime(1972, 1, 1), IanaShiqu("UTC")).utc.year == 1972
  with pytest.raises(ValueError, match="支持范围"):
    resolve_minyong_shike(datetime(9999, 12, 31, 23), GudingShiqu(timedelta(hours=-8)))
  with pytest.raises(ValueError, match="支持范围"):
    resolve_minyong_shike(datetime(9999, 12, 31, 23), IanaShiqu("Etc/GMT+8"))


@pytest.mark.parametrize(
  "version_value, error", [(None, TypeError), (1, TypeError), ("", ValueError), (" ", ValueError)]
)
def test_data_version_validation(version_value: Any, error: type[Exception]) -> None:
  with pytest.raises(error):
    ShiquShuju(version_value, "2026e")
  with pytest.raises(error):
    ShiquShuju("2026.5", version_value)


def test_result_is_frozen_and_consistent() -> None:
  value = resolve_minyong_shike(datetime(2000, 1, 1, 12), IanaShiqu("Asia/Shanghai"))
  for instance, field, replacement in (
    (value, "fold", 1),
    (value.shiqu, "key", "UTC"),
    (value.shuju, "banben", "other"),
    (GudingShiqu(timedelta(0)), "offset", timedelta(hours=8)),
  ):
    with pytest.raises(FrozenInstanceError):
      setattr(instance, field, replacement)
  cases: tuple[tuple[dict[str, Any], type[Exception]], ...] = (
    ({"utc": "not a datetime"}, TypeError),
    ({"utc": datetime(2000, 1, 1)}, ValueError),
    ({"utc": datetime(1900, 1, 1, tzinfo=UTC)}, ValueError),
    ({"offset": timedelta(hours=1)}, ValueError),
    ({"shiqu": "UTC"}, TypeError),
    ({"fold": True}, ValueError),
    ({"shuju": None}, TypeError),
    ({"shiqu": IanaShiqu("Asia/Shanghai", 1)}, ValueError),
    ({"shiqu": GudingShiqu(value.offset)}, ValueError),
  )
  for changes, error in cases:
    with pytest.raises(error):
      replace(value, **changes)
  assert isinstance(value, MinyongShike)
