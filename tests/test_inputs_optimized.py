"""不经 pytest 重写的子进程校验与导入隔离。"""

import subprocess
import sys
from pathlib import Path

import pytest

PUBLIC_CHECKS = r"""
from datetime import date, datetime, time, timedelta
from ziwei.birth import GregorianBirthRecord, LunarBirthRecord, CalculationInput, TimePrecision, Gender
from ziwei.config import ChartConfig, LeapMonthPolicy, DayRollover, YearBoundary
from ziwei.ganzhi import Dizhi, Ganzhi, year_ganzhi
from ziwei.timezone import IanaTimezone, FixedOffset, resolve_civil_time
config = ChartConfig(leap_month_policy=LeapMonthPolicy.全月归本月,
                     day_rollover=DayRollover.晚子时归次日, year_boundary=YearBoundary.立春)
record = LunarBirthRecord(year=2000, month=4, day=1, is_leap_month=False,
                          shichen=None, gender=Gender.未知)
unknown_time = LunarBirthRecord(year=2000, month=4, day=1, is_leap_month=False,
                               shichen=None, gender=Gender.男)
cases = [
  lambda: year_ganzhi(True), lambda: year_ganzhi(0),
  lambda: Ganzhi.from_str('甲丑'),
  lambda: ChartConfig(leap_month_policy=None, day_rollover=config.day_rollover,
                     year_boundary=config.year_boundary),
  lambda: IanaTimezone('../UTC'), lambda: IanaTimezone('UTC', True),
  lambda: FixedOffset(timedelta(days=1)),
  lambda: resolve_civil_time(datetime(1988, 4, 17, 2, 30), IanaTimezone('Asia/Shanghai')),
  lambda: resolve_civil_time(datetime(1988, 9, 11, 1, 30), IanaTimezone('Asia/Shanghai')),
  lambda: GregorianBirthRecord(birth_date=date(2000, 1, 1), birth_time=time(12),
                              time_precision=TimePrecision.分,
                              timezone=FixedOffset(timedelta(0)), gender='男'),
  lambda: LunarBirthRecord(year=True, month=4, day=1, is_leap_month=False,
                          shichen=None, gender=Gender.未知),
  lambda: CalculationInput(record=record, lunar_year=2000, month=4, day=1, is_leap_month=False,
                           shichen=None, ganzhi_year=2000, config=config).require_complete(),
  lambda: CalculationInput(record=unknown_time, lunar_year=2000, month=4, day=1, is_leap_month=False,
                           shichen=Dizhi.子, ganzhi_year=2000, config=config),
  lambda: LunarBirthRecord(year=2000, month=4, day=1, is_leap_month=False,
                          shichen=None, gender=Gender.男, longitude_deg=10**400),
]
for index, action in enumerate(cases):
  try:
    action()
  except (TypeError, ValueError):
    pass
  else:
    raise RuntimeError(f'public check {index} accepted invalid input')
print(f'checked={len(cases)}')
"""


@pytest.mark.parametrize("mode", [(), ("-O",)])
def test_public_validation_without_rewritten_assertions(
  tmp_path: Path, mode: tuple[str, ...]
) -> None:
  result = subprocess.run(
    (sys.executable, *mode, "-I", "-c", PUBLIC_CHECKS),
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr
  assert "checked=14" in result.stdout


def test_import_has_no_calendar_or_timezone_data_side_effects(tmp_path: Path) -> None:
  script = """
import sys
from importlib.abc import MetaPathFinder
class Block(MetaPathFinder):
  def find_spec(self, fullname, path=None, target=None):
    if fullname.split('.')[0] in ('celestial_calendar', 'tzdata', 'bazi'):
      raise RuntimeError('unexpected data or calendar import: ' + fullname)
sys.meta_path.insert(0, Block())
import ziwei
import ziwei.birth
import ziwei.config
import ziwei.ganzhi
import ziwei.timezone
print('isolated imports passed')
"""
  result = subprocess.run(
    (sys.executable, "-I", "-c", script),
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr
  assert "isolated imports passed" in result.stdout
