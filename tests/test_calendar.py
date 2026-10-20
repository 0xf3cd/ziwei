"""celestial 适配与时标合同的测试。"""

import sys
from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest

from ziwei.calendar import (
  LunarAlgorithm,
  apparent_solar,
  celestial_version,
  gregorian_to_lunar,
  lichun_jd,
  lunar_to_gregorian,
  lunar_year_info,
  supported_lunar_year_range,
  utc_civil,
  utc_to_ut1_jd,
  validate_lunar_date,
)


@pytest.fixture(autouse=True)
def _unload_celestial() -> Iterator[None]:
  """测试后卸载 celestial_calendar，避免污染安装隔离检查的同进程断言。"""
  yield
  for name in [name for name in sys.modules if name.startswith("celestial_calendar")]:
    del sys.modules[name]


def test_version_is_installed_package() -> None:
  assert celestial_version() == "0.8.0"


@pytest.mark.parametrize(
  "algorithm, start, end",
  [
    (LunarAlgorithm.ALGO1, 1901, 2099),
    (LunarAlgorithm.ALGO2, 410, 2500),
    (LunarAlgorithm.ALGO3, 1600, 2199),
  ],
)
def test_supported_ranges_match_documentation(
  algorithm: LunarAlgorithm, start: int, end: int
) -> None:
  assert supported_lunar_year_range(algorithm) == (start, end)


def test_gregorian_lunar_round_trip() -> None:
  for algorithm in LunarAlgorithm:
    for day in (date(1901, 3, 1), date(1988, 7, 1), date(2000, 2, 5), date(2024, 12, 31)):
      lunar = gregorian_to_lunar(algorithm, day)
      assert lunar_to_gregorian(algorithm, *lunar) == day


def test_lunar_year_info_month_lengths_and_leap() -> None:
  first_day, leap_month, lengths = lunar_year_info(LunarAlgorithm.ALGO3, 2023)
  assert first_day == date(2023, 1, 22)
  assert leap_month == 2
  assert lengths == (29, 30, 29, 29, 30, 30, 29, 30, 30, 29, 30, 29, 30)


def test_validate_lunar_date_accepts_leap_month() -> None:
  validate_lunar_date(LunarAlgorithm.ALGO3, 2023, 2, 29, True)


@pytest.mark.parametrize(
  "args, message",
  [
    ((LunarAlgorithm.ALGO3, 2023, 1, 30, False), "没有第30日"),
    ((LunarAlgorithm.ALGO3, 2023, 3, 1, True), "不存在闰3月"),
    ((LunarAlgorithm.ALGO1, 1900, 1, 1, False), "超出"),
    ((LunarAlgorithm.ALGO3, 2023, 13, 1, False), "1至12之间"),
  ],
)
def test_validate_lunar_date_rejects_nonexistent(args: tuple[object, ...], message: str) -> None:
  algorithm, year, month, day, is_leap = args
  with pytest.raises(ValueError, match=message):
    validate_lunar_date(algorithm, year, month, day, is_leap)  # type: ignore[arg-type]


def test_gregorian_out_of_algorithm_coverage_fails() -> None:
  import celestial_calendar

  with pytest.raises(celestial_calendar.CelestialError):
    gregorian_to_lunar(LunarAlgorithm.ALGO1, date(1900, 1, 1))


def test_ut1_conversion_matches_chart_snapshot() -> None:
  """modelled-UT1 定义与 chart_snapshot.jd_ut1 在 1972-2099 网格上一致（亚毫秒级）。"""
  import celestial_calendar as celestial

  location = celestial.GeoLocation(31.2, 121.5)
  worst_seconds = 0.0
  for year, month, day, hour in (
    (1972, 1, 1, 0),
    (1975, 7, 15, 12),
    (1988, 7, 1, 3),
    (2000, 2, 4, 23),
    (2017, 1, 1, 0),
    (2024, 2, 4, 8),
    (2050, 6, 30, 12),
    (2099, 6, 30, 12),
  ):
    utc = datetime(year, month, day, hour, tzinfo=UTC)
    mine = utc_to_ut1_jd(utc)
    snapshot = celestial.chart_snapshot(
      celestial.CivilDateTime(year, month, day, hour / 24.0),
      celestial.CivilScale.UTC,
      location,
      celestial.HouseSystem.WHOLE_SIGN,
      celestial.DeltaTModel.DEFAULT,
    )
    worst_seconds = max(worst_seconds, abs(mine - snapshot.times.jd_ut1) * 86400.0)
  assert worst_seconds < 0.01  # 10 毫秒容差，实测亚毫秒


def test_lichun_jd_is_ut1_comparable() -> None:
  """立春 UT1 时刻与同一瞬间的 utc_to_ut1_jd 一致。"""
  import celestial_calendar as celestial

  moment = celestial.jieqi_moment(2024, celestial.Jieqi.LICHUN)
  assert lichun_jd(2024) == pytest.approx(celestial.ut1_to_jd(moment.moment_ut1), abs=1e-12)


def test_utc_civil_fraction() -> None:
  assert utc_civil(datetime(2024, 2, 4, 12, 0, tzinfo=UTC)) == (2024, 2, 4, 0.5)


def test_apparent_solar_crosses_midnight() -> None:
  """真太阳时跨日：东八区深夜 UTC 对应当地真太阳次日清晨。"""
  result = apparent_solar(datetime(2024, 2, 4, 23, 45, tzinfo=UTC), 120.0)
  year, month, day, fraction = result
  assert (year, month, day) == (2024, 2, 5)
  assert 7 <= fraction * 24 < 8  # 约 07:31


def test_utc_input_requires_timezone() -> None:
  with pytest.raises(ValueError, match="时区"):
    utc_to_ut1_jd(datetime(2024, 2, 4, 8, 0))


def test_import_celestial_only_on_use() -> None:
  """导入 ziwei 子模块不初始化 celestial；首次调用适配函数才加载。"""
  import subprocess
  import sys

  script = (
    "import sys\n"
    "from ziwei.calendar import supported_lunar_year_range, LunarAlgorithm\n"
    "loaded = any(name == 'celestial_calendar' for name in sys.modules)\n"
    "r = supported_lunar_year_range(LunarAlgorithm.ALGO3)\n"
    "print(loaded, r)\n"
  )
  result = subprocess.run(
    (sys.executable, "-I", "-c", script), capture_output=True, text=True, check=False
  )
  assert result.returncode == 0, result.stderr
  assert result.stdout.split() == ["False", "(1600,", "2199)"]
