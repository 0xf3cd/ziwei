"""互相独立的三个口径；本模块定义选择，不执行历法运算。"""

from dataclasses import dataclass
from enum import StrEnum


class RunyueGuishu(StrEnum):
  """闰月归属，影响按月安星；不改变原始农历记录。"""

  XIAYUE = "全月归下月"
  BENYUE = "全月归本月"
  BANYUE = "上半月归本月、下半月归下月"
  全月归下月 = XIAYUE
  全月归本月 = BENYUE
  上半月归本月下半月归下月 = BANYUE


class ZishiHuanri(StrEnum):
  """子时换日；早子时为00:00至01:00，晚子时为23:00至24:00。"""

  WANZI_CIRI = "晚子时归次日"
  ZAOWAN_TONGRI = "早晚子时同日"
  晚子时归次日 = WANZI_CIRI
  早晚子时同日 = ZAOWAN_TONGRI


class Huannian(StrEnum):
  """干支换年界线；选立春不意味着已完成时标转换。"""

  ZHENGYUE_CHUYI = "农历正月初一"
  LICHUN = "立春"
  农历正月初一 = ZHENGYUE_CHUYI
  立春 = LICHUN


@dataclass(frozen=True, slots=True, kw_only=True)
class PaipanConfig:
  """三项均须显式给出；没有具名或静默默认值。"""

  runyue_guishu: RunyueGuishu
  zishi_huanri: ZishiHuanri
  huannian: Huannian

  def __post_init__(self) -> None:
    for value, expected in (
      (self.runyue_guishu, RunyueGuishu),
      (self.zishi_huanri, ZishiHuanri),
      (self.huannian, Huannian),
    ):
      if not isinstance(value, expected):
        raise TypeError(f"口径须为 {expected.__name__} 成员")
