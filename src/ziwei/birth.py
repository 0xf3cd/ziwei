"""原始出生记录与解析后计算输入；本模块不转换公历和农历。"""

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum

from ziwei.calendar import LunarAlgorithm
from ziwei.config import ChartConfig, DayRollover, YearBoundary
from ziwei.ganzhi import Dizhi, Ganzhi, Yinyang, year_ganzhi
from ziwei.timezone import FixedOffset, IanaTimezone, ResolvedTime, resolve_civil_time


class Gender(StrEnum):
  """出生记录中的性别，未知不代填。"""

  MALE = "男"
  FEMALE = "女"
  UNKNOWN = "未知"
  男 = MALE
  女 = FEMALE
  未知 = UNKNOWN


class TimePrecision(StrEnum):
  """原始民用钟点的记录精度；仅有日期时使用日。"""

  DAY = "日"
  HOUR = "时"
  MINUTE = "分"
  SECOND = "秒"
  MICROSECOND = "微秒"
  日 = DAY
  时 = HOUR
  分 = MINUTE
  秒 = SECOND
  微秒 = MICROSECOND


def shichen_from_time(clock: time) -> Dizhi:
  """按无时区民用钟面取时辰；不改变日期或应用换日口径。

  时辰范围取香港天文台《天干和地支》表三，子时跨23:00至次日01:00；本接口采用左闭右开区间。
  """
  if type(clock) is not time:
    raise TypeError("钟点须为 time")
  if clock.tzinfo is not None or clock.fold != 0:
    raise ValueError("钟点不得携带时区或 fold")
  return tuple(Dizhi)[((clock.hour + 1) // 2) % 12]


def _check_metadata(longitude_deg: float | None, place: str | None, source: str | None) -> None:
  if longitude_deg is not None:
    if isinstance(longitude_deg, bool) or not isinstance(longitude_deg, int | float):
      raise TypeError("经度须为数值或 None")
    if not -180 <= longitude_deg <= 180:
      raise ValueError("经度须为-180至180之间的有限值，东经为正")
  for value in (place, source):
    if value is not None and not isinstance(value, str):
      raise TypeError("地点与来源说明须为字符串或 None")


def _check_lunar_date(
  year: int, month: int, day: int, is_leap_month: bool, shichen: Dizhi | None
) -> None:
  for value, maximum, name in ((year, 9999, "年"), (month, 12, "月"), (day, 30, "日")):
    if type(value) is not int:
      raise TypeError(f"农历{name}须为整数，不接受 bool")
    if not 1 <= value <= maximum:
      raise ValueError(f"农历{name}须在1至{maximum}之间")
  if type(is_leap_month) is not bool:
    raise TypeError("闰月标志须为 bool")
  if shichen is not None and not isinstance(shichen, Dizhi):
    raise TypeError("时辰须为 Dizhi 成员或 None")


@dataclass(frozen=True, slots=True, kw_only=True)
class GregorianBirthRecord:
  """原始公历日期、钟点、精度与时区；不携带派生的年干支。

  birth_time=None 表示钟点未知，精度须为日。经度仅保存，不在此执行真太阳时换算。
  """

  birth_date: date
  birth_time: time | None
  time_precision: TimePrecision
  timezone: IanaTimezone | FixedOffset
  gender: Gender
  longitude_deg: float | None = None
  place: str | None = None
  source: str | None = None

  def __post_init__(self) -> None:
    if type(self.birth_date) is not date:
      raise TypeError("公历日期须为 date，不接受 datetime")
    if not isinstance(self.time_precision, TimePrecision):
      raise TypeError("精度须为 TimePrecision 成员")
    if not isinstance(self.timezone, IanaTimezone | FixedOffset):
      raise TypeError("时区须为 IanaTimezone 或 FixedOffset")
    if not isinstance(self.gender, Gender):
      raise TypeError("性别须为 Gender 成员")
    _check_metadata(self.longitude_deg, self.place, self.source)
    if self.birth_time is None:
      if self.time_precision is not TimePrecision.日:
        raise ValueError("钟点未知时精度须为日")
      return
    shichen_from_time(self.birth_time)
    if self.time_precision is TimePrecision.日:
      raise ValueError("日精度的记录不得携带钟点")
    components = (self.birth_time.minute, self.birth_time.second, self.birth_time.microsecond)
    lower = {
      TimePrecision.时: components,
      TimePrecision.分: components[1:],
      TimePrecision.秒: components[2:],
      TimePrecision.微秒: (),
    }
    if any(lower[self.time_precision]):
      raise ValueError("钟点包含低于所声明记录精度的分量")

  @property
  def shichen(self) -> Dizhi | None:
    """原始民用钟面的时辰；未应用真太阳时或换日口径。"""
    return None if self.birth_time is None else shichen_from_time(self.birth_time)

  def resolve_time(self) -> ResolvedTime:
    """消歧民用钟点；未知钟点或不支持的历史时标显式失败。"""
    if self.birth_time is None:
      raise ValueError("出生钟点未知，不能解析民用时刻")
    return resolve_civil_time(datetime.combine(self.birth_date, self.birth_time), self.timezone)


@dataclass(frozen=True, slots=True, kw_only=True)
class LunarBirthRecord:
  """原始农历年月日、闰月标志与时辰；只核值域，不核该月存在性及月长。"""

  year: int
  month: int
  day: int
  is_leap_month: bool
  shichen: Dizhi | None
  gender: Gender
  longitude_deg: float | None = None
  place: str | None = None
  source: str | None = None

  def __post_init__(self) -> None:
    _check_lunar_date(self.year, self.month, self.day, self.is_leap_month, self.shichen)
    if not isinstance(self.gender, Gender):
      raise TypeError("性别须为 Gender 成员")
    _check_metadata(self.longitude_deg, self.place, self.source)


BirthRecord = GregorianBirthRecord | LunarBirthRecord
"""公历与农历的原始出生记录，保留各自不同的输入信息。"""


@dataclass(frozen=True, slots=True, kw_only=True)
class CalculationInput:
  """解析层的输出形状；本批由 resolver 从原始记录生成。

  ganzhi_year 是解析层按所选换年口径得到的纪年编号，不一定等于 lunar_year。
  原始记录和实际口径随值保存；阴阳及年干支由该编号派生，不维护可互相矛盾的副本。
  原始时辰未知时，解析时辰不得变为已知。
  lunar_algorithm 与 lunar_algorithm_version 记录所用农历算法及 celestial 版本；
  apparent_solar 记录是否采用真太阳时路径；day_rolled 记录晚子时归次日是否顺延；
  ut1_jd 与 lichun_jd 记录立春换年所比较的出生瞬间与立春时刻（UT1 日数），
  纯民用正月初一路径为 None。
  """

  record: BirthRecord
  lunar_year: int
  month: int
  day: int
  is_leap_month: bool
  shichen: Dizhi | None
  ganzhi_year: int
  config: ChartConfig
  lunar_algorithm: LunarAlgorithm
  lunar_algorithm_version: str
  apparent_solar: bool
  day_rolled: bool
  ut1_jd: float | None
  lichun_jd: float | None

  def __post_init__(self) -> None:
    if not isinstance(self.record, BirthRecord):
      raise TypeError("原始记录须为公历或农历出生记录")
    _check_lunar_date(self.lunar_year, self.month, self.day, self.is_leap_month, self.shichen)
    if self.record.shichen is None and self.shichen is not None:
      raise ValueError("原始记录的未知时辰不得变为已知")
    year_ganzhi(self.ganzhi_year)
    if not isinstance(self.config, ChartConfig):
      raise TypeError("口径须为显式 ChartConfig")
    if not isinstance(self.lunar_algorithm, LunarAlgorithm):
      raise TypeError("农历算法须为 LunarAlgorithm 成员")
    if not isinstance(self.lunar_algorithm_version, str) or not self.lunar_algorithm_version:
      raise ValueError("农历算法版本不得为空")
    for value, label in (
      (self.apparent_solar, "真太阳时路径"),
      (self.day_rolled, "晚子时顺延"),
    ):
      if type(value) is not bool:
        raise TypeError(f"{label}标志须为 bool")
    for instant, label in ((self.ut1_jd, "出生瞬间"), (self.lichun_jd, "立春时刻")):
      if instant is not None and not isinstance(instant, float):
        raise TypeError(f"{label} UT1 日数须为 float 或 None")
    if self.config.year_boundary is YearBoundary.立春 and self.ut1_jd is None:
      raise ValueError("立春换年必须记录出生瞬间的 UT1 日数")
    if self.ut1_jd is not None and self.lichun_jd is None:
      raise ValueError("记录出生瞬间时必须同时记录立春时刻")
    if self.lichun_jd is not None and self.config.year_boundary is not YearBoundary.立春:
      raise ValueError("立春时刻只属于立春换年口径")
    if self.day_rolled and self.shichen is not Dizhi.子:
      raise ValueError("晚子时顺延只发生在子时")
    if self.day_rolled and self.config.day_rollover is DayRollover.早晚子时同日:
      raise ValueError("晚子时顺延与早晚子时同日口径矛盾")
    if self.apparent_solar and (
      not isinstance(self.record, GregorianBirthRecord) or self.record.longitude_deg is None
    ):
      raise ValueError("真太阳时路径需要公历记录与经度")
    if (
      self.config.year_boundary is YearBoundary.农历正月初一 and self.ganzhi_year != self.lunar_year
    ):
      raise ValueError("正月初一换年口径下干支纪年须等于农历年")

  @property
  def gender(self) -> Gender:
    """保留原始记录的性别，不代填未知项。"""
    return self.record.gender

  @property
  def year_ganzhi(self) -> Ganzhi:
    """按已经确定的干支纪年编号查表。"""
    return year_ganzhi(self.ganzhi_year)

  @property
  def yinyang(self) -> Yinyang:
    """用于性别阴阳组合的年干阴阳，不作性别推断。"""
    return self.year_ganzhi.tiangan.yinyang

  def require_complete(self) -> None:
    """拒绝未知时辰或性别，供完整命盘入口调用；本方法不排盘。"""
    if self.shichen is None or self.gender is Gender.未知:
      raise ValueError("完整命盘需要已知时辰与性别")
