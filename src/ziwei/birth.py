"""原始出生记录与解析后计算输入；本模块不转换公历和农历。"""

import math
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum

from ziwei.config import PaipanConfig
from ziwei.ganzhi import Dizhi, Ganzhi, Yinyang, nian_ganzhi
from ziwei.shiqu import GudingShiqu, IanaShiqu, MinyongShike, resolve_minyong_shike


class Xingbie(StrEnum):
  """出生记录中的性别，未知不代填。"""

  NAN = "男"
  NV = "女"
  WEIZHI = "未知"
  男 = NAN
  女 = NV
  未知 = WEIZHI


class ShijianJingdu(StrEnum):
  """原始民用钟点的记录精度；仅有日期时使用日。"""

  RI = "日"
  SHI = "时"
  FEN = "分"
  MIAO = "秒"
  WEIMIAO = "微秒"
  日 = RI
  时 = SHI
  分 = FEN
  秒 = MIAO
  微秒 = WEIMIAO


def shichen_from_time(shijian: time) -> Dizhi:
  """按无时区民用钟面取时辰，区间左闭右开；不改变日期或应用换日口径。

  依据香港天文台《天干和地支》表三，子时跨23:00至次日01:00。
  """
  if type(shijian) is not time:
    raise TypeError("钟点须为 time")
  if shijian.tzinfo is not None or shijian.fold != 0:
    raise ValueError("钟点不得携带时区或 fold")
  return tuple(Dizhi)[((shijian.hour + 1) // 2) % 12]


def _check_metadata(jingdu_deg: float | None, didian: str | None, laiyuan: str | None) -> None:
  if jingdu_deg is not None:
    if isinstance(jingdu_deg, bool) or not isinstance(jingdu_deg, int | float):
      raise TypeError("经度须为数值或 None")
    if not math.isfinite(jingdu_deg) or not -180 <= jingdu_deg <= 180:
      raise ValueError("经度须为-180至180之间的有限值，东经为正")
  for value in (didian, laiyuan):
    if value is not None and not isinstance(value, str):
      raise TypeError("地点与来源说明须为字符串或 None")


def _check_nongli(nian: int, yue: int, ri: int, runyue: bool, shichen: Dizhi | None) -> None:
  for value, maximum, name in ((nian, 9999, "年"), (yue, 12, "月"), (ri, 30, "日")):
    if type(value) is not int:
      raise TypeError(f"农历{name}须为整数，不接受 bool")
    if not 1 <= value <= maximum:
      raise ValueError(f"农历{name}须在1至{maximum}之间")
  if type(runyue) is not bool:
    raise TypeError("闰月标志须为 bool")
  if shichen is not None and not isinstance(shichen, Dizhi):
    raise TypeError("时辰须为 Dizhi 成员或 None")


@dataclass(frozen=True, slots=True, kw_only=True)
class GongliBirthRecord:
  """原始公历日期、钟点、精度与时区；不携带派生的年干支。

  shijian=None 表示时辰未知，精度须为日。经度仅保存，不在此执行真太阳时换算。
  """

  riqi: date
  shijian: time | None
  shijian_jingdu: ShijianJingdu
  shiqu: IanaShiqu | GudingShiqu
  xingbie: Xingbie
  jingdu_deg: float | None = None
  didian: str | None = None
  laiyuan: str | None = None

  def __post_init__(self) -> None:
    if type(self.riqi) is not date:
      raise TypeError("公历日期须为 date，不接受 datetime")
    if not isinstance(self.shijian_jingdu, ShijianJingdu):
      raise TypeError("精度须为 ShijianJingdu 成员")
    if not isinstance(self.shiqu, IanaShiqu | GudingShiqu):
      raise TypeError("时区须为 IanaShiqu 或 GudingShiqu")
    if not isinstance(self.xingbie, Xingbie):
      raise TypeError("性别须为 Xingbie 成员")
    _check_metadata(self.jingdu_deg, self.didian, self.laiyuan)
    if self.shijian is None:
      if self.shijian_jingdu is not ShijianJingdu.日:
        raise ValueError("钟点未知时精度须为日")
      return
    shichen_from_time(self.shijian)
    if self.shijian_jingdu is ShijianJingdu.日:
      raise ValueError("日精度的记录不得携带钟点")
    components = (self.shijian.minute, self.shijian.second, self.shijian.microsecond)
    lower = {
      ShijianJingdu.时: components,
      ShijianJingdu.分: components[1:],
      ShijianJingdu.秒: components[2:],
      ShijianJingdu.微秒: (),
    }
    if any(lower[self.shijian_jingdu]):
      raise ValueError("钟点包含低于所声明记录精度的分量")

  @property
  def shichen(self) -> Dizhi | None:
    """原始民用钟面的时辰；未应用真太阳时或换日口径。"""
    return None if self.shijian is None else shichen_from_time(self.shijian)

  def resolve_time(self) -> MinyongShike:
    """消歧民用钟点；未知钟点或不支持的历史时标显式失败。"""
    if self.shijian is None:
      raise ValueError("出生钟点未知，不能解析民用时刻")
    return resolve_minyong_shike(datetime.combine(self.riqi, self.shijian), self.shiqu)


@dataclass(frozen=True, slots=True, kw_only=True)
class NongliBirthRecord:
  """原始农历年月日、闰月标志与时辰；只核值域，不核该月存在性及月长。"""

  nian: int
  yue: int
  ri: int
  runyue: bool
  shichen: Dizhi | None
  xingbie: Xingbie
  jingdu_deg: float | None = None
  didian: str | None = None
  laiyuan: str | None = None

  def __post_init__(self) -> None:
    _check_nongli(self.nian, self.yue, self.ri, self.runyue, self.shichen)
    if not isinstance(self.xingbie, Xingbie):
      raise TypeError("性别须为 Xingbie 成员")
    _check_metadata(self.jingdu_deg, self.didian, self.laiyuan)


ChushengJilu = GongliBirthRecord | NongliBirthRecord
"""公历与农历的原始出生记录，保留各自不同的输入信息。"""


@dataclass(frozen=True, slots=True, kw_only=True)
class JisuanInput:
  """解析层的输出形状；本批不提供从原始记录生成它的历法转换器。

  ganzhi_nian 是解析层按所选换年口径得到的纪年编号，不一定等于 nongli_nian。
  原始记录和实际口径随值保存；阴阳及年干支由该编号派生，不维护可互相矛盾的副本。
  """

  jilu: ChushengJilu
  nongli_nian: int
  yue: int
  ri: int
  runyue: bool
  shichen: Dizhi | None
  ganzhi_nian: int
  koujing: PaipanConfig

  def __post_init__(self) -> None:
    if not isinstance(self.jilu, GongliBirthRecord | NongliBirthRecord):
      raise TypeError("原始记录须为公历或农历出生记录")
    _check_nongli(self.nongli_nian, self.yue, self.ri, self.runyue, self.shichen)
    nian_ganzhi(self.ganzhi_nian)
    if not isinstance(self.koujing, PaipanConfig):
      raise TypeError("口径须为显式 PaipanConfig")

  @property
  def xingbie(self) -> Xingbie:
    """保留原始记录的性别，不代填未知项。"""
    return self.jilu.xingbie

  @property
  def nian_ganzhi(self) -> Ganzhi:
    """按已经确定的干支纪年编号查表。"""
    return nian_ganzhi(self.ganzhi_nian)

  @property
  def yinyang(self) -> Yinyang:
    """用于性别阴阳组合的年干阴阳，不作性别推断。"""
    return self.nian_ganzhi.tiangan.yinyang

  def require_complete(self) -> None:
    """拒绝未知时辰或性别，供完整命盘入口调用；本方法不排盘。"""
    if self.shichen is None or self.xingbie is Xingbie.未知:
      raise ValueError("完整命盘需要已知时辰与性别")
