"""真实日级见证和合成午夜窗口各自验证时区与时标。"""

from datetime import date, datetime, timedelta, timezone
from math import nextafter
from typing import Any

import pytest

from ziwei import calendar


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
