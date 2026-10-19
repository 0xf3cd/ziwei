"""干支值与六十甲子表；出处及使用限度见文档的干支来源节。"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class Yinyang(StrEnum):
  """阴阳。"""

  YIN = "阴"
  YANG = "阳"
  阴 = YIN
  阳 = YANG


class Tiangan(StrEnum):
  """十天干，按甲至癸排列。"""

  JIA = "甲"
  YI = "乙"
  BING = "丙"
  DING = "丁"
  WU = "戊"
  JI = "己"
  GENG = "庚"
  XIN = "辛"
  REN = "壬"
  GUI = "癸"
  甲 = JIA
  乙 = YI
  丙 = BING
  丁 = DING
  戊 = WU
  己 = JI
  庚 = GENG
  辛 = XIN
  壬 = REN
  癸 = GUI

  @property
  def yinyang(self) -> Yinyang:
    """天干序号奇阳偶阴（甲的序号为一）。"""
    return Yinyang.阳 if tuple(Tiangan).index(self) % 2 == 0 else Yinyang.阴


class Dizhi(StrEnum):
  """十二地支，按子至亥排列。"""

  ZI = "子"
  CHOU = "丑"
  YIN = "寅"
  MAO = "卯"
  CHEN = "辰"
  SI = "巳"
  WU = "午"
  WEI = "未"
  SHEN = "申"
  YOU = "酉"
  XU = "戌"
  HAI = "亥"
  子 = ZI
  丑 = CHOU
  寅 = YIN
  卯 = MAO
  辰 = CHEN
  巳 = SI
  午 = WU
  未 = WEI
  申 = SHEN
  酉 = YOU
  戌 = XU
  亥 = HAI


@dataclass(frozen=True, slots=True)
class Ganzhi:
  """同阴阳的天干地支组合；不接受甲丑等非六十甲子组合。"""

  tiangan: Tiangan
  dizhi: Dizhi

  def __post_init__(self) -> None:
    if not isinstance(self.tiangan, Tiangan) or not isinstance(self.dizhi, Dizhi):
      raise TypeError("干支须使用 Tiangan 与 Dizhi 成员")
    if tuple(Tiangan).index(self.tiangan) % 2 != tuple(Dizhi).index(self.dizhi) % 2:
      raise ValueError("天干与地支的阴阳须相同")

  def __str__(self) -> str:
    return self.tiangan.value + self.dizhi.value

  @classmethod
  def from_str(cls, value: str) -> "Ganzhi":
    """从两个中文字构造干支；类型错误抛 TypeError，非法组合抛 ValueError。"""
    if not isinstance(value, str):
      raise TypeError("干支须为字符串")
    if len(value) != 2:
      raise ValueError("干支须为两个字")
    return cls(Tiangan(value[0]), Dizhi(value[1]))


# 香港天文台《天干和地支》表二：https://www.hko.gov.hk/tc/gts/time/stemsandbranches.htm
JIAZI: Final[tuple[Ganzhi, ...]] = tuple(
  Ganzhi.from_str(value)
  for value in (
    "甲子",
    "乙丑",
    "丙寅",
    "丁卯",
    "戊辰",
    "己巳",
    "庚午",
    "辛未",
    "壬申",
    "癸酉",
    "甲戌",
    "乙亥",
    "丙子",
    "丁丑",
    "戊寅",
    "己卯",
    "庚辰",
    "辛巳",
    "壬午",
    "癸未",
    "甲申",
    "乙酉",
    "丙戌",
    "丁亥",
    "戊子",
    "己丑",
    "庚寅",
    "辛卯",
    "壬辰",
    "癸巳",
    "甲午",
    "乙未",
    "丙申",
    "丁酉",
    "戊戌",
    "己亥",
    "庚子",
    "辛丑",
    "壬寅",
    "癸卯",
    "甲辰",
    "乙巳",
    "丙午",
    "丁未",
    "戊申",
    "己酉",
    "庚戌",
    "辛亥",
    "壬子",
    "癸丑",
    "甲寅",
    "乙卯",
    "丙辰",
    "丁巳",
    "戊午",
    "己未",
    "庚申",
    "辛酉",
    "壬戌",
    "癸亥",
  )
)
"""以甲子为首的六十甲子，不另维护第二份年干支序列。"""

# 纪年锚取香港天文台1984年对照表首行，不代表该民用年内任一出生都属甲子年。
# https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T1984c.txt
NIAN_GANZHI: Final[tuple[tuple[int, Ganzhi], ...]] = tuple(
  (1984 + index, ganzhi) for index, ganzhi in enumerate(JIAZI)
)
"""1984起的一个纪年周期，由六十甲子定义生成。"""


def nian_ganzhi(ganzhi_nian: int) -> Ganzhi:
  """查已确定纪年编号的干支；接受1至9999，不判断出生时刻应属哪一年。

  正月初一或立春换年须由历法解析层先决定纪年编号，不能直接用出生公历年代替。
  """
  if type(ganzhi_nian) is not int:
    raise TypeError("干支纪年编号须为整数，不接受 bool")
  if not 1 <= ganzhi_nian <= 9999:
    raise ValueError("干支纪年编号须在1至9999之间")
  return NIAN_GANZHI[(ganzhi_nian - NIAN_GANZHI[0][0]) % len(NIAN_GANZHI)][1]


阴阳 = Yinyang
天干 = Tiangan
地支 = Dizhi
干支 = Ganzhi
