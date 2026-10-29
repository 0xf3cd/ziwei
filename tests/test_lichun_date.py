"""真实日级见证和合成午夜窗口各自验证时区与时标。"""

import json
from datetime import date, datetime, timedelta, timezone
from math import nextafter
from pathlib import Path
from typing import Any

import pytest

from ziwei import calendar

REFERENCE = json.loads(
  Path(__file__)
  .with_name("fixtures")
  .joinpath("liunian-reference.json")
  .read_text(encoding="utf-8")
)


def test_hko_witnesses_keep_the_two_independent_date_examples() -> None:
  assert {item["adopted"]["lichun_date"] for item in REFERENCE["lichun_date_witnesses"]} == {
    "1972-02-05",
    "2021-02-03",
  }


@pytest.mark.parametrize(
  "year,expected",
  [
    (1972, date(1972, 2, 5)),
    (2022, date(2022, 2, 4)),
    (2024, date(2024, 2, 4)),
    (2200, date(2200, 2, 4)),
  ],
)
def test_real_lichun_dates(year: int, expected: date) -> None:
  assert calendar.lichun_date(year) == expected


@pytest.mark.parametrize("year", range(1972, 2201))
def test_supported_dates_contain_the_modelled_ut1_moment(year: int) -> None:
  day = calendar.lichun_date(year)
  assert day in (date(year, 2, 3), date(year, 2, 4), date(year, 2, 5))
  midnight = datetime.combine(day, datetime.min.time(), timezone(timedelta(hours=8)))
  target = calendar.lichun_jd(year)
  assert (
    calendar.utc_to_ut1_jd(midnight)
    <= target
    < calendar.utc_to_ut1_jd(midnight + timedelta(days=1))
  )
  if year < 2200:
    assert (calendar.lichun_date(year + 1) - day).days in (365, 366)


@pytest.mark.parametrize(
  "witness",
  REFERENCE["lichun_date_witnesses"],
)
def test_hko_date_level_witnesses(witness: dict[str, Any]) -> None:
  assert witness["observed"] == witness["adopted"]
  assert witness["published_precision"] == "date"
  assert witness["date_basis"] == "香港标准时间UTC+08"
  day = date.fromisoformat(witness["adopted"]["lichun_date"])
  assert calendar.lichun_date(day.year) == day


@pytest.mark.parametrize("invalid", [True, 2024.0, "2024", None])
def test_year_type_is_checked(invalid: Any) -> None:
  with pytest.raises(TypeError):
    calendar.lichun_date(invalid)


@pytest.mark.parametrize("year", [1971, 2201, 0, 9999])
def test_adapter_year_range_is_explicit(year: int) -> None:
  with pytest.raises(ValueError, match="1972至2200"):
    calendar.lichun_date(year)


@pytest.mark.parametrize("year", [2022, 2024])
def test_subsecond_midnight_gap_distinguishes_ut1_from_utc(
  monkeypatch: pytest.MonkeyPatch, year: int
) -> None:
  day = date(year, 2, 4)
  local_midnight = datetime(year, 2, 4, tzinfo=timezone(timedelta(hours=8)))
  correct = calendar.utc_to_ut1_jd(local_midnight)
  wrong = calendar._civil_to_jd(year, 2, 3, 16 / 24)
  target = correct + (wrong - correct) / 2
  assert min(correct, wrong) < target < max(correct, wrong)
  monkeypatch.setattr(calendar, "lichun_jd", lambda _: target)
  expected = day if target >= correct else day - timedelta(days=1)
  assert calendar.lichun_date(year) == expected
  assert expected != (day if target >= wrong else day - timedelta(days=1))


@pytest.mark.parametrize("side,offset", [("before", -1), ("equal", 0), ("after", 0)])
@pytest.mark.parametrize("year", [2022, 2024])
def test_utc_midnight_is_inclusive(
  monkeypatch: pytest.MonkeyPatch, year: int, side: str, offset: int
) -> None:
  target = calendar.utc_to_ut1_jd(datetime(year, 2, 4, tzinfo=timezone(timedelta(hours=8))))
  if side == "before":
    target = nextafter(target, float("-inf"))
  elif side == "after":
    target = nextafter(target, float("inf"))
  monkeypatch.setattr(calendar, "lichun_jd", lambda _: target)
  assert calendar.lichun_date(year) == date(year, 2, 4) + timedelta(days=offset)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_native_moment_is_rejected(
  monkeypatch: pytest.MonkeyPatch, invalid: float
) -> None:
  monkeypatch.setattr(calendar, "lichun_jd", lambda _: invalid)
  with pytest.raises(ValueError, match="有限数"):
    calendar.lichun_date(2024)
