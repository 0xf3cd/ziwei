"""五行局。

五行局由命宫干支的纳音五行定：水二局、木三局、金四局、土五局、火六局。
《紫微斗數全書》卷二《安身命例》以「丙寅丁卯炉中火」断火局（维基文库修订1963110），
同页局图以水二局、木三局、金四局、土五局、火六局分列；王亭之中州派《紫微斗数初级讲义》
定五行局一节同样列举水二木三金四土五火六。局数即大限首限起始虚岁。
"""

from enum import StrEnum

from ziwei.ganzhi import Ganzhi, Wuxing, nayin


class WuxingJu(StrEnum):
  """具名五行局；局数即大限首限起始虚岁。"""

  SHUI_ER = "水二局"
  MU_SAN = "木三局"
  JIN_SI = "金四局"
  TU_WU = "土五局"
  HUO_LIU = "火六局"
  水二局 = SHUI_ER
  木三局 = MU_SAN
  金四局 = JIN_SI
  土五局 = TU_WU
  火六局 = HUO_LIU

  @property
  def number(self) -> int:
    """局数（水二木三金四土五火六），即大限首限起始虚岁。"""
    return tuple(WuxingJu).index(self) + 2


_BUREAU_BY_ELEMENT: dict[Wuxing, WuxingJu] = {
  Wuxing.水: WuxingJu.SHUI_ER,
  Wuxing.木: WuxingJu.MU_SAN,
  Wuxing.金: WuxingJu.JIN_SI,
  Wuxing.土: WuxingJu.TU_WU,
  Wuxing.火: WuxingJu.HUO_LIU,
}


def bureau_of(minggong_ganzhi: Ganzhi) -> WuxingJu:
  """由命宫干支的纳音五行定五行局。"""
  if not isinstance(minggong_ganzhi, Ganzhi):
    raise TypeError("五行局须查命宫干支")
  return _BUREAU_BY_ELEMENT[nayin(minggong_ganzhi)]


def bureau_number(ju: WuxingJu) -> int:
  """局数（水二木三金四土五火六）。"""
  if not isinstance(ju, WuxingJu):
    raise TypeError("五行局须为 WuxingJu 成员")
  return ju.number
