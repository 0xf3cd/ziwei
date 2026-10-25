"""celestial 适配与时标合同的测试。"""

from datetime import UTC, date, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from typing import Never

import pytest

from ziwei import calendar as implementation
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

pytestmark = pytest.mark.usefixtures("unload_celestial")


# IERS Leap_Second.dat（查阅2026-10-24）：生效日、MJD、TAI-UTC；首行是基线。
# https://hpiers.obspm.fr/iers/bul/bulc/Leap_Second.dat
# NIST插入日加一天与该生效日相符，不从生产表生成预期。
# https://www.nist.gov/pml/time-and-frequency-division/time-realization/leap-seconds
LEAP_SECOND_REFERENCE = (
  ("1972-01-01", 41317, 10),
  ("1972-07-01", 41499, 11),
  ("1973-01-01", 41683, 12),
  ("1974-01-01", 42048, 13),
  ("1975-01-01", 42413, 14),
  ("1976-01-01", 42778, 15),
  ("1977-01-01", 43144, 16),
  ("1978-01-01", 43509, 17),
  ("1979-01-01", 43874, 18),
  ("1980-01-01", 44239, 19),
  ("1981-07-01", 44786, 20),
  ("1982-07-01", 45151, 21),
  ("1983-07-01", 45516, 22),
  ("1985-07-01", 46247, 23),
  ("1988-01-01", 47161, 24),
  ("1990-01-01", 47892, 25),
  ("1991-01-01", 48257, 26),
  ("1992-07-01", 48804, 27),
  ("1993-07-01", 49169, 28),
  ("1994-07-01", 49534, 29),
  ("1996-01-01", 50083, 30),
  ("1997-07-01", 50630, 31),
  ("1999-01-01", 51179, 32),
  ("2006-01-01", 53736, 33),
  ("2009-01-01", 54832, 34),
  ("2012-07-01", 56109, 35),
  ("2015-07-01", 57204, 36),
  ("2017-01-01", 57754, 37),
)


def test_leap_second_table_matches_independent_history() -> None:
  expected = tuple((date.fromisoformat(day), offset) for day, _, offset in LEAP_SECOND_REFERENCE)
  assert expected == implementation._LEAP_SECOND_TABLE


@pytest.mark.parametrize("label, mjd, offset", LEAP_SECOND_REFERENCE)
@pytest.mark.parametrize("seconds", [-1, 0, 1])
def test_each_leap_second_effective_boundary(
  label: str,
  mjd: int,
  offset: int,
  seconds: int,
) -> None:
  """独立历史值核偏移，公开换算核接入；模型复算不当作实测UT1。"""
  boundary = date.fromisoformat(label)
  assert (boundary - date(1858, 11, 17)).days == mjd
  instant = datetime.combine(boundary, datetime.min.time(), UTC) + timedelta(seconds=seconds)
  if offset == 10 and seconds < 0:
    with pytest.raises(ValueError, match="1972"):
      utc_to_ut1_jd(instant)
    return
  expected_offset = offset - 1 if seconds < 0 else offset
  assert implementation._delta_at(instant.date()) == expected_offset
  import celestial_calendar as celestial

  tt = instant + timedelta(seconds=expected_offset + 32.184)
  start = datetime(tt.year, 1, 1, tzinfo=UTC)
  end = datetime(tt.year + 1, 1, 1, tzinfo=UTC)
  decimal_year = tt.year + (tt - start) / (end - start)
  delta_t = celestial.delta_t(decimal_year, celestial.DeltaTModel.DEFAULT)
  expected = mjd + 2400000.5 + (seconds + expected_offset + 32.184 - delta_t) / 86400
  assert abs(utc_to_ut1_jd(instant) - expected) * 86400 < 0.0001


def test_future_offset_uses_last_known_value_not_a_prediction() -> None:
  assert implementation._delta_at(date(2099, 6, 30)) == 37


def test_utc_lower_bound_compares_instants_not_local_date() -> None:
  from datetime import timezone

  with pytest.raises(ValueError, match="1972"):
    utc_to_ut1_jd(datetime(1972, 1, 1, 0, 30, tzinfo=timezone(timedelta(hours=8))))


def test_version_is_installed_package() -> None:
  assert celestial_version() == version("celestial-calendar")


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
  import celestial_calendar as celestial

  native = celestial.supported_lunar_year_range(getattr(celestial.LunarAlgorithm, algorithm.name))
  assert (native.start, native.end) == (start, end)
  guide = (Path(__file__).resolve().parents[1] / "docs/calendar.md").read_text(encoding="utf-8")
  assert f"| `{algorithm.name}` {algorithm.value} | {start}\N{EN DASH}{end} |" in guide


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


@pytest.mark.parametrize("is_leap,day", [(False, 0), (True, 0), (False, 31), (True, 30)])
def test_lunar_day_error_locates_year_month_and_leap(is_leap: bool, day: int) -> None:
  label = f"农历2023年{'闰' if is_leap else '平'}2月没有第{day}日"
  with pytest.raises(ValueError, match=label):
    validate_lunar_date(LunarAlgorithm.ALGO3, 2023, 2, day, is_leap)


def test_missing_leap_month_error_locates_year_and_month() -> None:
  with pytest.raises(ValueError, match="农历2023年不存在闰3月"):
    validate_lunar_date(LunarAlgorithm.ALGO3, 2023, 3, 1, True)


def test_validate_lunar_date_accepts_plain_month_after_leap() -> None:
  """闰月之后的平月取真实月长：2023 闰二月，四月三十（2023-06-17）与腊月三十（2024-02-09）都在。"""
  validate_lunar_date(LunarAlgorithm.ALGO3, 2023, 4, 30, False)
  validate_lunar_date(LunarAlgorithm.ALGO3, 2023, 12, 30, False)


def test_validate_lunar_date_rejects_short_plain_month_after_leap() -> None:
  """闰月之后的平月取真实月长：2023 六月只有 29 天，三十不存在。"""
  with pytest.raises(ValueError, match="没有第30日"):
    validate_lunar_date(LunarAlgorithm.ALGO3, 2023, 6, 30, False)


@pytest.mark.parametrize("day", [0, -1, -3])
def test_validate_lunar_date_rejects_nonpositive_day(day: int) -> None:
  """农历日的下界校验：0 与负数都不存在，显式失败。"""
  with pytest.raises(ValueError, match="没有第"):
    validate_lunar_date(LunarAlgorithm.ALGO3, 2024, 1, day, False)


@pytest.mark.parametrize(
  "changes, error",
  [
    ({"year": True}, TypeError),
    ({"month": True}, TypeError),
    ({"day": True}, TypeError),
    ({"is_leap": 1}, TypeError),
  ],
)
def test_validate_lunar_date_rejects_wrong_types(
  changes: dict[str, object], error: type[Exception]
) -> None:
  """农历日期校验拒绝 bool 与非预期类型，不把 1/True 静默当作合法输入。"""
  base: dict[str, object] = dict(
    algorithm=LunarAlgorithm.ALGO3, year=2023, month=2, day=1, is_leap=False
  )
  base.update(changes)
  with pytest.raises(error):
    validate_lunar_date(**base)  # type: ignore[arg-type]


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
  with pytest.raises(ValueError, match=r"超出.*支持范围"):
    gregorian_to_lunar(LunarAlgorithm.ALGO1, date(1900, 1, 1))


@pytest.mark.parametrize(
  "algorithm, upper, day",
  [
    (LunarAlgorithm.ALGO1, 2099, date(2099, 6, 30)),
    (LunarAlgorithm.ALGO2, 2500, date(2500, 6, 30)),
    (LunarAlgorithm.ALGO3, 2199, date(2199, 6, 30)),
  ],
)
def test_upper_range_endpoint_converts(algorithm: LunarAlgorithm, upper: int, day: date) -> None:
  """支持范围上端点可换算：往返一致且落在上端点年。"""
  lunar = gregorian_to_lunar(algorithm, day)
  assert lunar[0] == upper
  assert lunar_to_gregorian(algorithm, *lunar) == day


@pytest.mark.parametrize(
  "algorithm, day",
  [
    (LunarAlgorithm.ALGO1, date(2100, 6, 30)),
    (LunarAlgorithm.ALGO2, date(2501, 6, 30)),
    (LunarAlgorithm.ALGO3, date(2200, 6, 30)),
  ],
)
def test_above_upper_range_endpoint_fails(algorithm: LunarAlgorithm, day: date) -> None:
  """超上界年份显式失败。"""
  with pytest.raises(ValueError, match=r"超出.*支持范围"):
    gregorian_to_lunar(algorithm, day)


@pytest.mark.parametrize("algorithm", list(LunarAlgorithm))
def test_exact_gregorian_coverage_and_adjacent_dates(algorithm: LunarAlgorithm) -> None:
  first_year, last_year = supported_lunar_year_range(algorithm)
  first, _, _ = lunar_year_info(algorithm, first_year)
  last_first, _, lengths = lunar_year_info(algorithm, last_year)
  last = last_first + timedelta(days=sum(lengths) - 1)
  assert gregorian_to_lunar(algorithm, first) == (first_year, 1, 1, False)
  assert gregorian_to_lunar(algorithm, last) == (last_year, 12, lengths[-1], False)
  for outside in (first - timedelta(days=1), last + timedelta(days=1)):
    with pytest.raises(ValueError, match=r"超出.*支持范围"):
      gregorian_to_lunar(algorithm, outside)


@pytest.mark.parametrize("conversion", ["gregorian_to_lunar", "lunar_to_gregorian"])
@pytest.mark.parametrize("fail_at", ["conversion", "lunar_year_info"])
def test_internal_calendar_failures_propagate_unchanged(
  monkeypatch: pytest.MonkeyPatch, conversion: str, fail_at: str
) -> None:
  import celestial_calendar as celestial

  operation = conversion if fail_at == "conversion" else fail_at
  injected = celestial.CelestialError(operation, "synthetic internal failure", recorded=True)

  def fail(*args: object) -> Never:
    raise injected

  monkeypatch.setattr(celestial, operation, fail)
  with pytest.raises(celestial.CelestialError) as caught:
    if conversion == "gregorian_to_lunar":
      gregorian_to_lunar(LunarAlgorithm.混合, date(2024, 2, 10))
    else:
      lunar_to_gregorian(LunarAlgorithm.混合, 2024, 1, 1, False)
  assert caught.value is injected


@pytest.mark.parametrize(
  "year, month, day, leap, message",
  [
    (2023, 1, 30, False, "没有第30日"),
    (2023, 3, 1, True, "不存在闰3月"),
    (1599, 1, 1, False, "超出"),
  ],
)
def test_lunar_conversion_rejects_invalid_combinations_before_native_call(
  monkeypatch: pytest.MonkeyPatch, year: int, month: int, day: int, leap: bool, message: str
) -> None:
  import celestial_calendar as celestial

  def unexpected(*args: object) -> Never:
    raise AssertionError("invalid input reached native conversion")

  monkeypatch.setattr(celestial, "lunar_to_gregorian", unexpected)
  with pytest.raises(ValueError, match=message):
    lunar_to_gregorian(LunarAlgorithm.混合, year, month, day, leap)


def test_ut1_conversion_matches_chart_snapshot() -> None:
  """八个选定时刻的同依赖模型对照；不证明全域精度或真实地球自转时标。"""
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
  assert worst_seconds < 0.01  # 八个选定时刻的模型回归阈值，不是全域精度保证。


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


def test_ut1_conversion_rejects_pre_1972() -> None:
  """1972 前没有现代 UTC 闰秒合同，公开函数显式失败而非静默给错值。"""
  with pytest.raises(ValueError, match="1972"):
    utc_to_ut1_jd(datetime(1960, 7, 1, tzinfo=UTC))
  with pytest.raises(ValueError, match="1972"):
    utc_to_ut1_jd(datetime(1971, 12, 31, 23, 0, tzinfo=UTC))


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
