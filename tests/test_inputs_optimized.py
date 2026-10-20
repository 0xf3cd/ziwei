"""不经 pytest 重写的子进程校验与导入隔离。"""

import subprocess
import sys
from pathlib import Path

import pytest

PUBLIC_CHECKS = r"""
from datetime import date, datetime, time, timedelta
from ziwei.birth import GregorianBirthRecord, LunarBirthRecord, CalculationInput, TimePrecision, Gender
from ziwei.bureau import bureau_of
from ziwei.calendar import LunarAlgorithm, supported_lunar_year_range, utc_to_ut1_jd, validate_lunar_date
from ziwei.config import ChartConfig, LeapMonthPolicy, DayRollover, YearBoundary
from ziwei.ganzhi import Dizhi, Ganzhi, year_ganzhi
from ziwei.palaces import minggong_dizhi, month_palace_index
from ziwei.resolver import resolve
from ziwei.timezone import IanaTimezone, FixedOffset, resolve_civil_time
config = ChartConfig(leap_month_policy=LeapMonthPolicy.全月归本月,
                     day_rollover=DayRollover.晚子时归次日, year_boundary=YearBoundary.立春)
plain = ChartConfig(leap_month_policy=LeapMonthPolicy.全月归本月,
                    day_rollover=DayRollover.晚子时归次日, year_boundary=YearBoundary.农历正月初一)
record = LunarBirthRecord(year=2000, month=4, day=1, is_leap_month=False,
                          shichen=None, gender=Gender.未知)
unknown_time = LunarBirthRecord(year=2000, month=4, day=1, is_leap_month=False,
                               shichen=None, gender=Gender.男)
complete = dict(lunar_algorithm=LunarAlgorithm.ALGO3, lunar_algorithm_version='0.8.0',
                apparent_solar=False, day_rolled=False, ut1_jd=None, lichun_jd=None)
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
                           shichen=None, ganzhi_year=2000, config=plain, **complete).require_complete(),
  lambda: CalculationInput(record=unknown_time, lunar_year=2000, month=4, day=1, is_leap_month=False,
                           shichen=Dizhi.子, ganzhi_year=2000, config=plain, **complete),
  lambda: CalculationInput(record=record, lunar_year=2000, month=4, day=1, is_leap_month=False,
                           shichen=None, ganzhi_year=2000, config=config, **complete),
  lambda: LunarBirthRecord(year=2000, month=4, day=1, is_leap_month=False,
                          shichen=None, gender=Gender.男, longitude_deg=10**400),
  lambda: supported_lunar_year_range('ALGO3'),
  lambda: utc_to_ut1_jd(datetime(2024, 2, 4, 8, 0)),
  lambda: validate_lunar_date(LunarAlgorithm.ALGO3, 2023, 1, 30, False),
  lambda: month_palace_index(0),
  lambda: minggong_dizhi(1, '子'),
  lambda: bureau_of('甲子'),
  lambda: resolve('1988', plain),
  lambda: resolve(record, config),
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
  assert "checked=23" in result.stdout


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
import ziwei.calendar
import ziwei.palaces
import ziwei.bureau
import ziwei.resolver
from ziwei.knowledge import load_catalog
catalog = load_catalog()
if not catalog.find('天馬') or not catalog.references('entry.tianma.year-branch'):
  raise RuntimeError('independent knowledge lookup failed')
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


@pytest.mark.parametrize("mode", [(), ("-O",)])
def test_knowledge_is_independent_and_validates_without_asserts(
  tmp_path: Path, mode: tuple[str, ...]
) -> None:
  script = r"""
import sys
from importlib.abc import MetaPathFinder
class Block(MetaPathFinder):
  def find_spec(self, fullname, path=None, target=None):
    if fullname.split('.')[0] in ('celestial_calendar', 'tzdata', 'zoneinfo', 'bazi') or fullname in (
        'ziwei.birth', 'ziwei.timezone', 'ziwei.chart', 'ziwei.calendar'):
      raise RuntimeError('knowledge tried to initialize a foreign boundary: ' + fullname)
sys.meta_path.insert(0, Block())
from dataclasses import replace
from ziwei.config import DayRollover
from ziwei.knowledge import load_catalog
from ziwei.knowledge.model import Concept, ConceptKind
c = load_catalog()
if len(c.find('庚干四化')) != 3 or not c.references('entry.tianma.year-branch'):
  raise RuntimeError('knowledge lookup did not run')
cases = [
  lambda: Concept(id='concept.x', name='x', kind='星曜'),
  lambda: Concept(id='not an id', name='x', kind=ConceptKind.星曜),
  lambda: replace(c, concepts=(*c.concepts, c.concepts[0])),
  lambda: replace(c, citations=(replace(c.citations[0], source_id='source.unknown'),)),
  lambda: c.filter_entries(default_only=1),
  lambda: replace(c, variants=tuple(
    replace(item, option=DayRollover.晚子时归次日) if item.id == 'variant.leap-month.current' else item
    for item in c.variants)),
  lambda: replace(c.citations[0], layer='原文'),
]
for action in cases:
  try:
    action()
  except (TypeError, ValueError, KeyError):
    pass
  else:
    raise RuntimeError('knowledge accepted invalid input')
print('knowledge isolated and checked=' + str(len(cases)))
"""
  result = subprocess.run(
    (sys.executable, *mode, "-I", "-c", script),
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr
  assert "checked=7" in result.stdout
