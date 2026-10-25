"""解析层的测试：三口径、真太阳时、立春时标合同与失败边界。"""

import subprocess
import sys
from dataclasses import replace
from datetime import date, time, timedelta
from errno import ENAMETOOLONG
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from struct import error as StructError
from struct import pack
from zoneinfo import ZoneInfoNotFoundError

import pytest

from ziwei import timezone as timezone_module
from ziwei.birth import (
  Gender,
  GregorianBirthRecord,
  LunarBirthRecord,
  TimePrecision,
)
from ziwei.calendar import (
  LunarAlgorithm,
  lichun_jd,
  lunar_year_info,
  supported_lunar_year_range,
  utc_to_ut1_jd,
)
from ziwei.chart import create_chart
from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, YearBoundary
from ziwei.ganzhi import Dizhi, Ganzhi
from ziwei.palaces import effective_month, minggong_dizhi
from ziwei.resolver import resolve
from ziwei.sihua import SihuaVariant
from ziwei.timezone import AmbiguousTimeError, FixedOffset, IanaTimezone, NonexistentTimeError

pytestmark = pytest.mark.usefixtures("unload_celestial")


def call_time_entry(entry: str, record: GregorianBirthRecord, choices: ChartConfig) -> None:
  if entry == "civil":
    record.resolve_time()
  elif entry == "resolve":
    resolve(record, choices)
  elif entry == "chart":
    create_chart(record, choices, sihua_variant=SihuaVariant.排命盘口诀转录)
  else:
    raise ValueError(entry)


@pytest.mark.parametrize("entry", ["civil", "resolve", "chart"])
@pytest.mark.parametrize("year", list(YearBoundary))
@pytest.mark.parametrize("longitude", [None, 120.0])
@pytest.mark.parametrize("key", ["UTC/x", "Etc/UTC/x", "Asia/Shanghai/x"])
def test_file_used_as_directory_is_unknown_timezone(
  entry: str,
  year: YearBoundary,
  longitude: float | None,
  key: str,
) -> None:
  record = gregorian(date(1988, 7, 1), time(12), IanaTimezone(key), longitude_deg=longitude)
  with pytest.raises(ZoneInfoNotFoundError, match=key) as caught:
    call_time_entry(entry, record, config(year=year))
  assert type(caught.value) is ZoneInfoNotFoundError
  # 文件被用作目录时，Windows可报告FileNotFoundError，POSIX通常报告NotADirectoryError。
  assert isinstance(caught.value.__cause__, NotADirectoryError | FileNotFoundError)


@pytest.mark.parametrize("entry", ["civil", "resolve", "chart"])
@pytest.mark.parametrize("year", list(YearBoundary))
@pytest.mark.parametrize("longitude", [None, 120.0])
@pytest.mark.parametrize(
  "key",
  [
    pytest.param("A" * 300, id="long-component"),
    pytest.param("Asia/" + "x" * 300, id="long-nested-component"),
  ],
)
def test_long_timezone_key_keeps_resource_cause(
  entry: str,
  year: YearBoundary,
  longitude: float | None,
  key: str,
) -> None:
  record = gregorian(date(1988, 7, 1), time(12), IanaTimezone(key), longitude_deg=longitude)
  with pytest.raises(ZoneInfoNotFoundError, match=key) as caught:
    call_time_entry(entry, record, config(year=year))
  cause = caught.value.__cause__
  assert type(caught.value) is ZoneInfoNotFoundError
  assert isinstance(cause, OSError)
  assert cause.errno == ENAMETOOLONG or isinstance(cause, FileNotFoundError)


@pytest.mark.parametrize("entry", ["civil", "resolve", "chart"])
@pytest.mark.parametrize("year", list(YearBoundary))
@pytest.mark.parametrize("longitude", [None, 120.0])
def test_missing_timezone_subpackage_keeps_import_cause(
  entry: str,
  year: YearBoundary,
  longitude: float | None,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  assert timezone_module.current_timezone_data().package_version
  monkeypatch.setitem(sys.modules, "tzdata.zoneinfo", None)
  record = gregorian(date(1988, 7, 1), time(12), longitude_deg=longitude)
  with pytest.raises(ZoneInfoNotFoundError, match=r"缺少tzdata.*Asia/Shanghai") as caught:
    call_time_entry(entry, record, config(year=year))
  cause = caught.value.__cause__
  assert type(caught.value) is ZoneInfoNotFoundError
  assert isinstance(cause, ModuleNotFoundError) and cause.name == "tzdata.zoneinfo"


@pytest.mark.parametrize("entry", ["civil", "resolve", "chart"])
@pytest.mark.parametrize("year", list(YearBoundary))
@pytest.mark.parametrize("longitude", [None, 120.0])
@pytest.mark.parametrize("fault", ["unknown-key", "invalid-tzif", "truncated-tzif"])
def test_resource_failures_share_type_and_keep_cause(
  entry: str,
  year: YearBoundary,
  longitude: float | None,
  fault: str,
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  key = "No/Such_Zone" if fault == "unknown-key" else "Asia/Shanghai"
  if fault != "unknown-key":
    resource = tmp_path / "Asia/Shanghai"
    resource.parent.mkdir()
    resource.write_bytes(
      b"invalid"
      if fault == "invalid-tzif"
      else b"TZif\0" + bytes(15) + pack(">6l", 0, 0, 0, 0, 1, 4)
    )
    monkeypatch.setattr(timezone_module, "files", lambda package: tmp_path)
  record = gregorian(date(1988, 7, 1), time(12), IanaTimezone(key), longitude_deg=longitude)
  with pytest.raises(ZoneInfoNotFoundError, match=key) as caught:
    call_time_entry(entry, record, config(year=year))
  assert type(caught.value) is ZoneInfoNotFoundError
  cause = (
    FileNotFoundError
    if fault == "unknown-key"
    else (ValueError if fault == "invalid-tzif" else StructError)
  )
  assert isinstance(caught.value.__cause__, cause)
  assert ("标识不存在" if fault == "unknown-key" else "资源无效") in str(caught.value)


@pytest.mark.parametrize("entry", ["civil", "resolve", "chart"])
@pytest.mark.parametrize("year", list(YearBoundary))
@pytest.mark.parametrize("longitude", [None, 120.0])
@pytest.mark.parametrize("mode", [(), ("-O",)])
def test_real_missing_package_import_in_isolated_process(
  entry: str,
  year: YearBoundary,
  longitude: float | None,
  mode: tuple[str, ...],
  tmp_path: Path,
) -> None:
  """-S让已安装的tzdata真实不可导入；失败须发生在历法依赖加载之前。"""
  source = Path(__file__).resolve().parents[1] / "src"
  action = {
    "civil": "record.resolve_time()",
    "resolve": "resolve(record, choices)",
    "chart": "create_chart(record, choices, sihua_variant=SihuaVariant.排命盘口诀转录)",
  }[entry]
  script = f"""
import sys
sys.path.insert(0, {str(source)!r})
from datetime import date, time, datetime, timedelta
from zoneinfo import ZoneInfoNotFoundError
from ziwei.birth import GregorianBirthRecord, TimePrecision, Gender
from ziwei.config import ChartConfig, LeapMonthPolicy, DayRollover, YearBoundary
from ziwei.timezone import IanaTimezone, FixedOffset, resolve_civil_time
from ziwei.resolver import resolve
from ziwei.chart import create_chart
from ziwei.sihua import SihuaVariant
record = GregorianBirthRecord(birth_date=date(1988,7,1), birth_time=time(12),
  time_precision=TimePrecision.分, timezone=IanaTimezone('Asia/Shanghai'), gender=Gender.男,
  longitude_deg={longitude!r})
choices = ChartConfig(leap_month_policy=LeapMonthPolicy.全月归本月,
  day_rollover=DayRollover.早晚子时同日, year_boundary=YearBoundary({year.value!r}))
try:
  {action}
except ZoneInfoNotFoundError as error:
  cause = error.__cause__
  if not isinstance(cause, ModuleNotFoundError) or cause.name != 'tzdata':
    raise RuntimeError('wrong missing-package cause')
  if 'Asia/Shanghai' not in str(error) or 'tzdata' not in str(error):
    raise RuntimeError('missing resource context')
else:
  raise RuntimeError('missing package accepted')
if 'celestial_calendar' in sys.modules:
  raise RuntimeError('failure reached native calendar')
resolve_civil_time(datetime(1988,7,1,12), FixedOffset(timedelta(hours=8)))
print('missing package rejected; fixed offset independent')
"""
  result = subprocess.run(
    (sys.executable, *mode, "-I", "-S", "-c", script),
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stdout + result.stderr
  assert "missing package rejected; fixed offset independent" in result.stdout


@pytest.mark.parametrize("year", list(YearBoundary))
@pytest.mark.parametrize("longitude", [None, 120.0])
@pytest.mark.parametrize("entry", ["resolve", "chart"])
def test_resource_is_read_once_per_iana_entry(
  year: YearBoundary,
  longitude: float | None,
  entry: str,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  calls: list[str] = []

  def counted(package: str) -> Traversable:
    calls.append(package)
    return files(package)

  monkeypatch.setattr(timezone_module, "files", counted)
  record = gregorian(date(1988, 7, 1), time(12), longitude_deg=longitude)
  call_time_entry(entry, record, config(year=year))
  assert calls == ["tzdata.zoneinfo"]
  calls.clear()
  call_time_entry(
    entry, replace(record, timezone=FixedOffset(timedelta(hours=8))), config(year=year)
  )
  assert calls == []


def test_unknown_clock_does_not_consume_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
  def forbidden(package: str) -> Traversable:
    raise RuntimeError("unknown clock must not read timezone")

  monkeypatch.setattr(timezone_module, "files", forbidden)
  record = gregorian(date(1950, 1, 1), None, IanaTimezone("No/Such_Zone"))
  value = resolve(record, config())
  assert value.shichen is None and value.resolved_time is None
  with pytest.raises(ValueError, match="完整命盘需要"):
    call_time_entry("chart", record, config())
  with pytest.raises(ValueError, match="立春换年需要已知钟点"):
    call_time_entry("chart", record, config(year=YearBoundary.立春))
  with pytest.raises(ValueError, match="真太阳时需要已知钟点"):
    resolve(replace(record, longitude_deg=120.0), config())


@pytest.mark.parametrize(
  "day, clock, kind",
  [
    (date(1988, 4, 17), time(2, 30), "gap"),
    (date(1988, 9, 11), time(1, 30), "overlap"),
    (date(1988, 7, 1), time(12), "ordinary"),
  ],
)
@pytest.mark.parametrize("fold", [None, 0, 1])
@pytest.mark.parametrize(
  "year, longitude",
  [
    (YearBoundary.农历正月初一, None),
    (YearBoundary.立春, None),
    (YearBoundary.农历正月初一, 120.0),
    (YearBoundary.立春, 120.0),
  ],
)
def test_label_only_and_instant_paths_have_distinct_dst_contracts(
  day: date,
  clock: time,
  kind: str,
  fold: int | None,
  year: YearBoundary,
  longitude: float | None,
) -> None:
  record = gregorian(day, clock, IanaTimezone("Asia/Shanghai", fold), longitude_deg=longitude)
  plain = year is YearBoundary.农历正月初一 and longitude is None
  error: type[ValueError] | None = None
  if not plain:
    if kind == "gap":
      error = NonexistentTimeError
    elif kind == "overlap" and fold is None:
      error = AmbiguousTimeError
    elif kind == "ordinary" and fold == 1:
      error = ValueError
  for entry in ("resolve", "chart"):
    if error is not None:
      with pytest.raises(error):
        call_time_entry(entry, record, config(year=year))
    else:
      call_time_entry(entry, record, config(year=year))
  if plain:
    value = resolve(record, config(year=year))
    assert isinstance(value.record, GregorianBirthRecord)
    assert value.resolved_time is None and value.record.timezone == record.timezone
    assert value.shichen is record.shichen


def config(
  leap: LeapMonthPolicy = LeapMonthPolicy.全月归本月,
  rollover: DayRollover = DayRollover.晚子时归次日,
  year: YearBoundary = YearBoundary.农历正月初一,
) -> ChartConfig:
  return ChartConfig(leap_month_policy=leap, day_rollover=rollover, year_boundary=year)


def gregorian(
  birth_date: date,
  birth_time: time | None,
  timezone: object = IanaTimezone("Asia/Shanghai"),
  gender: Gender = Gender.男,
  **changes: object,
) -> GregorianBirthRecord:
  values: dict[str, object] = {
    "birth_date": birth_date,
    "birth_time": birth_time,
    "time_precision": TimePrecision.分 if birth_time is not None else TimePrecision.日,
    "timezone": timezone,
    "gender": gender,
  }
  values.update(changes)
  return GregorianBirthRecord(**values)  # type: ignore[arg-type]


def test_gregorian_lunar_new_year_boundary() -> None:
  """正月初一口径：农历日与年干支来自农历年。"""
  value = resolve(
    gregorian(date(1988, 7, 1), time(12)),
    config(),
  )
  assert (value.lunar_year, value.month, value.day) == (1988, 5, 18)
  assert value.shichen is Dizhi.午
  assert value.ganzhi_year == 1988
  assert value.year_ganzhi == Ganzhi.from_str("戊辰")
  assert value.ut1_jd is None and value.lichun_jd is None
  assert value.apparent_solar is False and value.day_rolled is False
  assert value.lunar_algorithm is LunarAlgorithm.ALGO3


def test_between_lunar_new_year_and_lichun() -> None:
  """立春与春节之间：正月初一口径取旧年，立春口径用出生公历年的立春判新年。"""
  record = gregorian(date(2024, 2, 10), time(12))  # 2024-02-10 为甲辰年正月初一
  with_lunar = resolve(record, config(year=YearBoundary.农历正月初一))
  assert with_lunar.ganzhi_year == 2024
  assert with_lunar.year_ganzhi == Ganzhi.from_str("甲辰")
  with_lichun = resolve(record, config(year=YearBoundary.立春))
  assert with_lichun.ganzhi_year == 2024
  assert with_lichun.year_ganzhi == Ganzhi.from_str("甲辰")
  before = gregorian(date(2024, 2, 3), time(12))  # 立春(2-4 08:27 UT1)之前
  with_lichun_before = resolve(before, config(year=YearBoundary.立春))
  assert with_lichun_before.ganzhi_year == 2023
  assert with_lichun_before.year_ganzhi == Ganzhi.from_str("癸卯")
  inside = gregorian(date(2024, 2, 6), time(12))  # 立春之后、正月初一之前：两口径分歧
  inside_lunar = resolve(inside, config(year=YearBoundary.农历正月初一))
  assert inside_lunar.ganzhi_year == 2023
  assert inside_lunar.year_ganzhi == Ganzhi.from_str("癸卯")
  inside_lichun = resolve(inside, config(year=YearBoundary.立春))
  assert inside_lichun.lunar_year == 2023 and inside_lichun.lichun_jd == lichun_jd(2024)
  assert inside_lichun.ganzhi_year == 2024
  assert inside_lichun.year_ganzhi == Ganzhi.from_str("甲辰")


def test_lichun_instants_same_scale_both_sides() -> None:
  """立春瞬间两侧（同一时标 UT1）：2024 立春 UT1 约 08:27，上海 16/17 点分别在其前后。"""
  before = resolve(
    gregorian(date(2024, 2, 4), time(16)),
    config(year=YearBoundary.立春),
  )
  after = resolve(
    gregorian(date(2024, 2, 4), time(17)),
    config(year=YearBoundary.立春),
  )
  assert before.ganzhi_year == 2023
  assert after.ganzhi_year == 2024
  assert before.ut1_jd is not None and before.lichun_jd is not None
  assert after.ut1_jd is not None
  assert before.ut1_jd < before.lichun_jd < after.ut1_jd
  assert before.lichun_jd == after.lichun_jd


def test_lichun_equal_instant_belongs_to_new_year(monkeypatch: pytest.MonkeyPatch) -> None:
  """出生瞬间等于立春时刻（左闭右开）归新年。"""
  import ziwei.resolver as resolver_module

  record = gregorian(date(2024, 2, 4), time(16, 27))
  utc = record.resolve_time().utc
  monkeypatch.setattr(resolver_module, "lichun_jd", lambda year: utc_to_ut1_jd(utc))
  value = resolve(record, config(year=YearBoundary.立春))
  assert value.ganzhi_year == 2024
  # 立春时刻推迟一秒：同一瞬间落在立春前，归旧年
  monkeypatch.setattr(resolver_module, "lichun_jd", lambda year: utc_to_ut1_jd(utc) + 1.0 / 86400.0)
  before = resolve(record, config(year=YearBoundary.立春))
  assert before.ganzhi_year == 2023
  assert value.ut1_jd is not None and value.lichun_jd is not None


def test_lichun_adjacent_minutes_both_sides() -> None:
  """库内部对照：16:27与16:28在立春两侧，输入相隔一分钟，不是相邻秒。"""
  before = resolve(
    gregorian(date(2024, 2, 4), time(16, 27)),
    config(year=YearBoundary.立春),
  )
  after = resolve(
    gregorian(date(2024, 2, 4), time(16, 28)),
    config(year=YearBoundary.立春),
  )
  assert before.ganzhi_year == 2023
  assert after.ganzhi_year == 2024


def test_late_zi_rollover_policies() -> None:
  """子时两口径：晚子时归次日顺延一农历日，早晚子时同日不改。"""
  record = gregorian(date(1988, 7, 1), time(23, 30))
  late = resolve(record, config(rollover=DayRollover.晚子时归次日))
  same = resolve(record, config(rollover=DayRollover.早晚子时同日))
  assert (late.month, late.day, late.day_rolled) == (5, 19, True)
  assert (same.month, same.day, same.day_rolled) == (5, 18, False)
  assert late.shichen is Dizhi.子


def test_early_zi_not_rolled() -> None:
  """早子时(00:00-01:00)不因晚子时归次日顺延。"""
  record = gregorian(date(1988, 7, 1), time(0, 30))
  value = resolve(record, config(rollover=DayRollover.晚子时归次日))
  assert (value.month, value.day, value.day_rolled) == (5, 18, False)


def test_chuxi_late_zi_rolls_into_next_lunar_year() -> None:
  """除夕晚子时归次日：农历日顺延到正月初一，换年取换日后的农历年。"""
  record = gregorian(date(2024, 2, 9), time(23, 30))  # 癸卯年腊月三十
  late = resolve(record, config(rollover=DayRollover.晚子时归次日))
  same = resolve(record, config(rollover=DayRollover.早晚子时同日))
  assert (late.lunar_year, late.month, late.day, late.day_rolled) == (2024, 1, 1, True)
  assert late.ganzhi_year == 2024
  assert (same.lunar_year, same.month, same.day, same.day_rolled) == (2023, 12, 30, False)
  assert same.ganzhi_year == 2023


def test_apparent_solar_anchor_uses_solar_date() -> None:
  """真太阳时跨日：时辰所附民用日取真太阳钟日期，农历日随之（而非出生地民用日）。"""
  record = gregorian(
    date(2024, 3, 10),
    time(0, 20),
    timezone=FixedOffset(timedelta(hours=8)),
    longitude_deg=100.0,
  )
  value = resolve(record, config())
  # 真太阳日 2024-03-09 → 农历 2024-1-29；若 anchor 用出生地 3-10 则农历为 2024-2-1
  assert value.apparent_solar is True
  assert value.shichen is Dizhi.亥
  assert (value.lunar_year, value.month, value.day) == (2024, 1, 29)


def test_apparent_solar_late_zi_still_rolls() -> None:
  """真太阳路径的晚子时判定：真太阳钟 23:30 为晚子时，晚子时归次日仍顺延。"""
  record = gregorian(
    date(2024, 2, 9),
    time(23, 30),
    timezone=FixedOffset(timedelta(hours=8)),
    longitude_deg=120.0,
  )
  late = resolve(record, config(rollover=DayRollover.晚子时归次日))
  same = resolve(record, config(rollover=DayRollover.早晚子时同日))
  assert late.apparent_solar is True
  assert late.shichen is Dizhi.子
  assert (late.lunar_year, late.month, late.day, late.day_rolled) == (2024, 1, 1, True)
  assert (same.lunar_year, same.month, same.day, same.day_rolled) == (2023, 12, 30, False)


def test_unknown_time_with_longitude_rejected() -> None:
  """有经度但时辰未知：真太阳时无法计算，显式失败而非静默走民用路径。"""
  record = gregorian(date(1988, 7, 1), None, longitude_deg=121.47)
  with pytest.raises(ValueError, match="钟点"):
    resolve(record, config())


def test_civil_path_rejects_invalid_iana() -> None:
  """纯民用路径也验证 IANA 时区标识可解析：无效标识显式失败，不静默进时辰计算。"""
  record = gregorian(date(1988, 7, 1), time(12), timezone=IanaTimezone("No/Such_Zone"))
  with pytest.raises(ZoneInfoNotFoundError, match="No/Such_Zone"):
    resolve(record, config())


def test_civil_path_rejects_non_tzif_iana() -> None:
  """纯民用路径拒绝 tzdata 中非时区的文件（如 leapseconds），与需瞬间路径一致。"""
  record = gregorian(date(1988, 7, 1), time(12), timezone=IanaTimezone("leapseconds"))
  with pytest.raises(ZoneInfoNotFoundError, match="leapseconds"):
    resolve(record, config())


def test_leap_twelfth_month_next_month_policy_rejected() -> None:
  """闰十二月按归下月口径无对应安星月：显式失败，不合成来年正月规则。"""
  with pytest.raises(ValueError, match="闰十二月"):
    effective_month(12, 1, True, LeapMonthPolicy.全月归下月)
  with pytest.raises(ValueError, match="闰十二月"):
    effective_month(12, 16, True, LeapMonthPolicy.上半月归本月下半月归下月)


@pytest.mark.parametrize(
  "changes, error",
  [
    ({"month": 0}, ValueError),
    ({"month": 13}, ValueError),
    ({"month": 1.0}, TypeError),
    ({"day": 0}, ValueError),
    ({"day": True}, TypeError),
    ({"is_leap": 1}, TypeError),
  ],
)
def test_effective_month_validates_inputs(
  changes: dict[str, object], error: type[Exception]
) -> None:
  """effective_month 校验入参类型与值域，不把错误推迟到宫位计算。"""
  base: dict[str, object] = dict(month=2, day=4, is_leap=True, policy=LeapMonthPolicy.全月归本月)
  base.update(changes)
  with pytest.raises(error):
    effective_month(**base)  # type: ignore[arg-type]


def test_apparent_solar_morning_changes_shichen_without_changing_date() -> None:
  """东经120度07:45+08的真太阳钟仍在当日辰时；此例不跨当地日界。"""
  record = gregorian(
    date(2024, 2, 4),
    time(7, 45),
    timezone=FixedOffset(timedelta(hours=8)),
    longitude_deg=120.0,
  )
  value = resolve(record, config())
  assert value.apparent_solar is True
  assert value.ut1_jd is None  # 正月初一口径不记录立春比较用的 UT1 日数
  assert value.shichen is Dizhi.辰  # 真太阳 07:31 附近 → 辰时
  assert (value.lunar_year, value.month, value.day, value.day_rolled) == (2023, 12, 25, False)


def test_apparent_solar_uses_record_longitude() -> None:
  value = resolve(
    gregorian(date(1988, 7, 1), time(12), longitude_deg=121.47),
    config(),
  )
  assert value.apparent_solar is True
  assert value.shichen is Dizhi.午


def test_lunar_record_new_year_boundary() -> None:
  """农历记录直接取给定日期，只支持正月初一换年。"""
  lunar = LunarBirthRecord(
    year=1988, month=5, day=18, is_leap_month=False, shichen=Dizhi.午, gender=Gender.女
  )
  value = resolve(lunar, config())
  assert (value.lunar_year, value.month, value.day) == (1988, 5, 18)
  assert value.ganzhi_year == 1988
  assert value.apparent_solar is False and value.day_rolled is False


def test_lunar_record_zi_needs_civil_clock_for_late_zi_rollover() -> None:
  """农历记录的子时无钟点粒度：晚子时归次日无法判定早晚，显式失败；早晚子时同日可行。"""
  lunar = LunarBirthRecord(
    year=1988, month=5, day=18, is_leap_month=False, shichen=Dizhi.子, gender=Gender.女
  )
  with pytest.raises(ValueError, match="晚子时归次日"):
    resolve(lunar, config(rollover=DayRollover.晚子时归次日))
  same = resolve(lunar, config(rollover=DayRollover.早晚子时同日))
  assert (same.month, same.day, same.day_rolled) == (5, 18, False)


def test_lunar_record_with_longitude_rejected() -> None:
  """农历记录带经度但无钟点与时区：真太阳时无法应用，显式失败而非静默忽略。"""
  lunar = LunarBirthRecord(
    year=1988,
    month=5,
    day=18,
    is_leap_month=False,
    shichen=Dizhi.午,
    gender=Gender.女,
    longitude_deg=121.47,
  )
  with pytest.raises(ValueError, match="真太阳时"):
    resolve(lunar, config())


def test_lunar_record_rejects_lichun() -> None:
  lunar = LunarBirthRecord(
    year=1988, month=5, day=18, is_leap_month=False, shichen=Dizhi.午, gender=Gender.女
  )
  with pytest.raises(ValueError, match="立春"):
    resolve(lunar, config(year=YearBoundary.立春))


def test_lunar_record_rejects_nonexistent_date() -> None:
  lunar = LunarBirthRecord(
    year=2023, month=1, day=30, is_leap_month=False, shichen=Dizhi.午, gender=Gender.男
  )
  with pytest.raises(ValueError, match="没有第30日"):
    resolve(lunar, config())


@pytest.mark.parametrize(
  "policy, expected_month",
  [
    (LeapMonthPolicy.全月归本月, 2),
    (LeapMonthPolicy.全月归下月, 3),
    (LeapMonthPolicy.上半月归本月下半月归下月, 2),
  ],
)
def test_leap_month_policies_affect_minggong(policy: LeapMonthPolicy, expected_month: int) -> None:
  """闰月三口径：2023 闰二月初四出生，命宫/身宫随有效生月变化。"""
  # 2023-03-25 = 闰二月初四
  value = resolve(
    gregorian(date(2023, 3, 25), time(12)),
    config(leap=policy),
  )
  assert value.is_leap_month is True
  effective = effective_month(value.month, value.day, value.is_leap_month, policy)
  assert effective == expected_month
  # 有效生月不同则命宫不同（同年同日同时）
  assert value.shichen is not None
  assert minggong_dizhi(effective, value.shichen) is (Dizhi.酉 if expected_month == 2 else Dizhi.戌)


@pytest.mark.parametrize("algorithm", list(LunarAlgorithm))
def test_late_zi_only_requires_final_date_in_algorithm_range(algorithm: LunarAlgorithm) -> None:
  start_year, end_year = supported_lunar_year_range(algorithm)
  first, _, _ = lunar_year_info(algorithm, start_year)
  end_first, _, lengths = lunar_year_info(algorithm, end_year)
  last = end_first + timedelta(days=sum(lengths) - 1)
  before = gregorian(first - timedelta(days=1), time(23, 30))
  value = resolve(before, config(), algorithm)
  assert (value.lunar_year, value.month, value.day, value.day_rolled) == (start_year, 1, 1, True)
  with pytest.raises(ValueError, match=r"超出.*支持范围"):
    resolve(before, config(rollover=DayRollover.早晚子时同日), algorithm)
  end = gregorian(last, time(23, 30))
  same = resolve(end, config(rollover=DayRollover.早晚子时同日), algorithm)
  assert (same.lunar_year, same.month, same.day, same.day_rolled) == (
    end_year,
    12,
    lengths[-1],
    False,
  )
  with pytest.raises(ValueError, match=r"超出.*支持范围"):
    resolve(end, config(), algorithm)


@pytest.mark.parametrize("algorithm", list(LunarAlgorithm))
def test_late_zi_rejects_unrepresentable_next_day(algorithm: LunarAlgorithm) -> None:
  record = gregorian(date.max, time(23, 30))
  with pytest.raises(ValueError, match="晚子时顺延超出可表示日期范围"):
    resolve(record, config(), algorithm)


@pytest.mark.parametrize("algorithm", list(LunarAlgorithm))
def test_solar_final_date_uses_solar_not_civil_anchor(
  monkeypatch: pytest.MonkeyPatch, algorithm: LunarAlgorithm
) -> None:
  from ziwei import resolver as module

  first, _, _ = lunar_year_info(algorithm, supported_lunar_year_range(algorithm)[0])
  monkeypatch.setattr(
    module, "apparent_solar", lambda *args: (first.year, first.month, first.day - 1, 23.5 / 24)
  )
  record = gregorian(date(2024, 11, 3), time(0, 20), longitude_deg=100.0)
  value = resolve(record, config(), algorithm)
  assert (value.lunar_year, value.month, value.day) == (
    supported_lunar_year_range(algorithm)[0],
    1,
    1,
  )
  assert value.apparent_solar and value.day_rolled and value.shichen is Dizhi.子


@pytest.mark.parametrize("algorithm", list(LunarAlgorithm))
def test_solar_late_zi_rejects_final_date_above_algorithm_range(
  monkeypatch: pytest.MonkeyPatch, algorithm: LunarAlgorithm
) -> None:
  from ziwei import resolver as module

  end_year = supported_lunar_year_range(algorithm)[1]
  first, _, lengths = lunar_year_info(algorithm, end_year)
  last = first + timedelta(days=sum(lengths) - 1)
  monkeypatch.setattr(
    module, "apparent_solar", lambda *args: (last.year, last.month, last.day, 23.5 / 24)
  )
  record = gregorian(date(2024, 11, 3), time(0, 20), longitude_deg=100.0)
  same = resolve(record, config(rollover=DayRollover.早晚子时同日), algorithm)
  assert (same.lunar_year, same.month, same.day) == (end_year, 12, lengths[-1])
  assert same.apparent_solar and not same.day_rolled and same.shichen is Dizhi.子
  with pytest.raises(ValueError, match=r"超出.*支持范围"):
    resolve(record, config(), algorithm)


def test_leap_month_split_boundary_day16() -> None:
  """上半月归本月下半月归下月以十六日为界。"""
  lunar = LunarBirthRecord(
    year=2023, month=2, day=16, is_leap_month=True, shichen=Dizhi.午, gender=Gender.男
  )
  value = resolve(lunar, config(leap=LeapMonthPolicy.上半月归本月下半月归下月))
  assert (
    effective_month(value.month, value.day, True, LeapMonthPolicy.上半月归本月下半月归下月) == 3
  )
  lunar15 = LunarBirthRecord(
    year=2023, month=2, day=15, is_leap_month=True, shichen=Dizhi.午, gender=Gender.男
  )
  value15 = resolve(lunar15, config(leap=LeapMonthPolicy.上半月归本月下半月归下月))
  assert (
    effective_month(value15.month, value15.day, True, LeapMonthPolicy.上半月归本月下半月归下月) == 2
  )


def test_pre_1972_civil_path_works_without_instant() -> None:
  """1972 前的公历记录：正月初一+无经度纯民用路径不需要瞬间。"""
  record = gregorian(date(1960, 7, 1), time(12), timezone=FixedOffset(timedelta(hours=8)))
  value = resolve(record, config())
  assert value.lunar_year == 1960
  assert value.ut1_jd is None
  assert value.year_ganzhi == Ganzhi.from_str("庚子")  # 1960 庚子


def test_pre_1972_lichun_and_true_solar_rejected() -> None:
  """1972 前的公历记录需要瞬间（立春口径或真太阳时）时显式失败。"""
  record = gregorian(date(1960, 2, 4), time(12), timezone=FixedOffset(timedelta(hours=8)))
  with pytest.raises(ValueError, match="1972"):
    resolve(record, config(year=YearBoundary.立春))
  with pytest.raises(ValueError, match="1972"):
    resolve(gregorian(date(1960, 7, 1), time(12), longitude_deg=120.0), config())


def test_unknown_time_with_lichun_rejected() -> None:
  record = gregorian(date(1988, 7, 1), None)
  value = resolve(record, config())
  assert value.shichen is None
  with pytest.raises(ValueError, match="钟点"):
    resolve(record, config(year=YearBoundary.立春))


def test_algorithm_parameter_is_recorded() -> None:
  record = gregorian(date(1988, 7, 1), time(12))
  value = resolve(record, config(), lunar_algorithm=LunarAlgorithm.ALGO1)
  assert value.lunar_algorithm is LunarAlgorithm.ALGO1
  assert value.lunar_algorithm_version


def test_resolve_rejects_wrong_types() -> None:
  with pytest.raises(TypeError, match="出生记录"):
    resolve("1988", config())  # type: ignore[arg-type]
  record = gregorian(date(1988, 7, 1), time(12))
  with pytest.raises(TypeError, match="口径"):
    resolve(record, "config")  # type: ignore[arg-type]
  with pytest.raises(TypeError, match="农历算法"):
    resolve(record, config(), lunar_algorithm="ALGO3")  # type: ignore[arg-type]
