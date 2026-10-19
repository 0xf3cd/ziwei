"""民用时刻的时区消歧；不做历法、真太阳时或子时换日。"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from importlib.resources import files
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True, slots=True)
class IanaTimezone:
  """IANA 标识与显式重叠选择；fold 为0（较早）或1（较晚），未选择为 None。"""

  key: str
  fold: int | None = None

  def __post_init__(self) -> None:
    if not isinstance(self.key, str):
      raise TypeError("IANA 标识须为字符串")
    if not re.fullmatch(r"[A-Za-z0-9_+\-]+(?:/[A-Za-z0-9_+\-]+)*", self.key):
      raise ValueError("IANA 标识须为不含路径跳转的相对标识")
    if self.fold is not None:
      if type(self.fold) is not int:
        raise TypeError("fold 须为整数或 None，不接受 bool")
      if self.fold not in (0, 1):
        raise ValueError("fold 只能为0或1")


def _check_offset(offset: timedelta) -> None:
  if type(offset) is not timedelta:
    raise TypeError("固定偏移须为 timedelta")
  if not -timedelta(days=1) < offset < timedelta(days=1):
    raise ValueError("固定偏移的绝对值须小于24小时")


@dataclass(frozen=True, slots=True)
class FixedOffset:
  """显式固定偏移，绝对值须小于24小时；不替调用方套用地区夏令时。"""

  offset: timedelta

  def __post_init__(self) -> None:
    _check_offset(self.offset)


@dataclass(frozen=True, slots=True)
class TimezoneData:
  """实际使用的时区数据包版本和 IANA 发布版本。"""

  package_version: str
  iana_version: str

  def __post_init__(self) -> None:
    for value in (self.package_version, self.iana_version):
      if not isinstance(value, str):
        raise TypeError("时区数据版本须为字符串")
      if not value.strip():
        raise ValueError("时区数据版本不得为空")


def _check_wall(wall: datetime) -> None:
  if type(wall) is not datetime:
    raise TypeError("本地钟面须为 datetime")
  if wall.tzinfo is not None or wall.fold != 0:
    raise ValueError("本地钟面不得自带时区或 fold；消歧选择放在 IanaTimezone")


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedTime:
  """消歧后的时刻，保留钟面、UTC、偏移、请求与实际 fold、数据来源。

  只支持1972年起的 UTC；更早的原始出生记录可保存，但不向前外推现代时标合同。
  """

  local_time: datetime
  utc: datetime
  offset: timedelta
  zone: IanaTimezone | FixedOffset
  fold: int
  data: TimezoneData | None

  def __post_init__(self) -> None:
    _check_wall(self.local_time)
    if type(self.utc) is not datetime:
      raise TypeError("UTC 时刻须为 datetime")
    if self.utc.tzinfo is not UTC or self.utc.fold != 0:
      raise ValueError("UTC 时刻须显式使用 timezone.utc")
    if self.utc < datetime(1972, 1, 1, tzinfo=UTC):
      raise ValueError("UTC 早于1972-01-01的时刻须另定时标合同")
    _check_offset(self.offset)
    if type(self.fold) is not int or self.fold not in (0, 1):
      raise ValueError("实际 fold 须为0或1，不接受 bool")
    if not isinstance(self.zone, IanaTimezone | FixedOffset):
      raise TypeError("时区须为 IanaTimezone 或 FixedOffset")
    if isinstance(self.zone, IanaTimezone):
      if not isinstance(self.data, TimezoneData):
        raise TypeError("IANA 时刻须记录 TimezoneData")
      if self.zone.fold is not None and self.zone.fold != self.fold:
        raise ValueError("实际 fold 与请求不符")
    elif self.data is not None or self.fold != 0 or self.offset != self.zone.offset:
      raise ValueError("固定偏移不得带 IANA 数据或不同的偏移与 fold")
    if self.local_time - self.utc.replace(tzinfo=None) != self.offset:
      raise ValueError("钟面、UTC 与偏移不一致")


class NonexistentTimeError(ValueError):
  """本地钟面处于时区跳时的间隙中，没有对应瞬间。"""


class AmbiguousTimeError(ValueError):
  """本地钟面有两个对应瞬间，需要显式选择 fold。"""


def _load_zone(key: str) -> tuple[ZoneInfo, TimezoneData]:
  import tzdata  # type: ignore[import-untyped]

  try:
    resource = files("tzdata.zoneinfo").joinpath(*key.split("/"))
    if not resource.is_file():
      raise ZoneInfoNotFoundError(key)
    with resource.open("rb") as stream:
      zone = ZoneInfo.from_file(stream, key=key)
  except (FileNotFoundError, IsADirectoryError, ValueError) as error:
    raise ZoneInfoNotFoundError(key) from error
  return zone, TimezoneData(tzdata.__version__, tzdata.IANA_VERSION)


def resolve_civil_time(wall: datetime, zone: IanaTimezone | FixedOffset) -> ResolvedTime:
  """解析无时区钟面，拒绝间隙；重叠须给 fold，普通时刻不能请求 fold=1。

  IANA 数据只从已安装的 tzdata 包读取，不查系统库、不修改全局 TZPATH。
  资源读取只发生在此调用；固定偏移不读时区数据库。超出 datetime 范围显式失败。
  """
  _check_wall(wall)
  if not isinstance(zone, IanaTimezone | FixedOffset):
    raise TypeError("时区须为 IanaTimezone 或 FixedOffset")
  try:
    if isinstance(zone, FixedOffset):
      utc = wall.replace(tzinfo=timezone(zone.offset)).astimezone(UTC)
      return ResolvedTime(
        local_time=wall, utc=utc, offset=zone.offset, zone=zone, fold=0, data=None
      )
    iana_zone, data = _load_zone(zone.key)
    candidates: dict[int, tuple[datetime, timedelta]] = {}
    for fold in (0, 1):
      aware = wall.replace(tzinfo=iana_zone, fold=fold)
      utc = aware.astimezone(UTC)
      back = utc.astimezone(iana_zone)
      if back.replace(tzinfo=None) == wall and back.fold == fold:
        candidates[fold] = (utc, back.replace(tzinfo=None) - utc.replace(tzinfo=None))
    if not candidates:
      raise NonexistentTimeError("不存在的本地时刻")
    if len(candidates) == 2 and zone.fold is None:
      raise AmbiguousTimeError("歧义本地时刻须显式给出 fold")
    selected = zone.fold if zone.fold is not None else 0
    if selected not in candidates:
      raise ValueError("该本地时刻不支持请求的 fold")
    utc, offset = candidates[selected]
    return ResolvedTime(
      local_time=wall, utc=utc, offset=offset, zone=zone, fold=selected, data=data
    )
  except OverflowError as error:
    raise ValueError("时刻超出 datetime 支持范围") from error
