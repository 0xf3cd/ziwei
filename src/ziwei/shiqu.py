"""民用时刻的时区消歧；不做历法、真太阳时或子时换日。"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from importlib.resources import files
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True, slots=True)
class IanaShiqu:
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


@dataclass(frozen=True, slots=True)
class GudingShiqu:
  """显式固定偏移，绝对值须小于24小时；不替调用方套用地区夏令时。"""

  offset: timedelta

  def __post_init__(self) -> None:
    if type(self.offset) is not timedelta:
      raise TypeError("固定偏移须为 timedelta")
    if not -timedelta(days=1) < self.offset < timedelta(days=1):
      raise ValueError("固定偏移的绝对值须小于24小时")


@dataclass(frozen=True, slots=True)
class ShiquShuju:
  """实际使用的时区数据包版本和 IANA 发布版本。"""

  banben: str
  iana_banben: str

  def __post_init__(self) -> None:
    for value in (self.banben, self.iana_banben):
      if not isinstance(value, str):
        raise TypeError("时区数据版本须为字符串")
      if not value.strip():
        raise ValueError("时区数据版本不得为空")


def _check_wall(wall: datetime) -> None:
  if type(wall) is not datetime:
    raise TypeError("本地钟面须为 datetime")
  if wall.tzinfo is not None or wall.fold != 0:
    raise ValueError("本地钟面不得自带时区或 fold；消歧选择放在 IanaShiqu")


@dataclass(frozen=True, slots=True, kw_only=True)
class MinyongShike:
  """消歧后的时刻，保留钟面、UTC、偏移、请求与实际 fold、数据来源。

  只支持1972年起的 UTC；更早的原始出生记录可保存，但不向前外推现代时标合同。
  """

  bendishike: datetime
  utc: datetime
  offset: timedelta
  shiqu: IanaShiqu | GudingShiqu
  fold: int
  shuju: ShiquShuju | None

  def __post_init__(self) -> None:
    _check_wall(self.bendishike)
    if type(self.utc) is not datetime:
      raise TypeError("UTC 时刻须为 datetime")
    if self.utc.tzinfo is not UTC or self.utc.fold != 0:
      raise ValueError("UTC 时刻须显式使用 timezone.utc")
    if self.utc < datetime(1972, 1, 1, tzinfo=UTC):
      raise ValueError("1972年前的时刻须另定时标合同")
    GudingShiqu(self.offset)
    if type(self.fold) is not int or self.fold not in (0, 1):
      raise ValueError("实际 fold 须为0或1，不接受 bool")
    if not isinstance(self.shiqu, IanaShiqu | GudingShiqu):
      raise TypeError("时区须为 IanaShiqu 或 GudingShiqu")
    if isinstance(self.shiqu, IanaShiqu):
      if not isinstance(self.shuju, ShiquShuju):
        raise TypeError("IANA 时刻须记录 ShiquShuju")
      if self.shiqu.fold is not None and self.shiqu.fold != self.fold:
        raise ValueError("实际 fold 与请求不符")
    elif self.shuju is not None or self.fold != 0 or self.offset != self.shiqu.offset:
      raise ValueError("固定偏移不得带 IANA 数据或不同的偏移与 fold")
    if self.bendishike - self.utc.replace(tzinfo=None) != self.offset:
      raise ValueError("钟面、UTC 与偏移不一致")


class NonexistentTimeError(ValueError):
  """本地钟面处于时区跳时的间隙中，没有对应瞬间。"""


class AmbiguousTimeError(ValueError):
  """本地钟面有两个对应瞬间，需要显式选择 fold。"""


def _load_zone(key: str) -> tuple[ZoneInfo, ShiquShuju]:
  import tzdata  # type: ignore[import-untyped]

  try:
    with files("tzdata.zoneinfo").joinpath(*key.split("/")).open("rb") as stream:
      zone = ZoneInfo.from_file(stream, key=key)
  except (FileNotFoundError, IsADirectoryError, ValueError) as error:
    raise ZoneInfoNotFoundError(key) from error
  return zone, ShiquShuju(tzdata.__version__, tzdata.IANA_VERSION)


def resolve_minyong_shike(wall: datetime, shiqu: IanaShiqu | GudingShiqu) -> MinyongShike:
  """解析无时区钟面，拒绝间隙；重叠须给 fold，普通时刻不能请求 fold=1。

  IANA 数据只从已安装的 tzdata 包读取，不查系统库、不修改全局 TZPATH。
  资源读取只发生在此调用；固定偏移不读时区数据库。超出 datetime 范围显式失败。
  """
  _check_wall(wall)
  if not isinstance(shiqu, IanaShiqu | GudingShiqu):
    raise TypeError("时区须为 IanaShiqu 或 GudingShiqu")
  try:
    if isinstance(shiqu, GudingShiqu):
      utc = wall.replace(tzinfo=timezone(shiqu.offset)).astimezone(UTC)
      return MinyongShike(
        bendishike=wall, utc=utc, offset=shiqu.offset, shiqu=shiqu, fold=0, shuju=None
      )
    zone, shuju = _load_zone(shiqu.key)
    candidates: dict[int, tuple[datetime, timedelta]] = {}
    for fold in (0, 1):
      aware = wall.replace(tzinfo=zone, fold=fold)
      utc = aware.astimezone(UTC)
      back = utc.astimezone(zone)
      if back.replace(tzinfo=None) == wall and back.fold == fold:
        candidates[fold] = (utc, back.replace(tzinfo=None) - utc.replace(tzinfo=None))
    if not candidates:
      raise NonexistentTimeError("不存在的本地时刻")
    if len(candidates) == 2 and shiqu.fold is None:
      raise AmbiguousTimeError("歧义本地时刻须显式给出 fold")
    selected = shiqu.fold if shiqu.fold is not None else 0
    if selected not in candidates:
      raise ValueError("该本地时刻不支持请求的 fold")
    utc, offset = candidates[selected]
    return MinyongShike(
      bendishike=wall, utc=utc, offset=offset, shiqu=shiqu, fold=selected, shuju=shuju
    )
  except OverflowError as error:
    raise ValueError("时刻超出 datetime 支持范围") from error
