"""命宫、身宫、十二宫与宫干。

命宫与身宫由农历生月与生时定：从寅宫起正月顺数至生月，再自该宫起子时，逆数至生时安命、
顺数至生时安身（《紫微斗數全書》卷二《安身命例》，维基文库修订1963110；同法见王亭之中州派
《紫微斗数初级讲义》安命身宫诀）。十二宫自命宫起逆排，宫名与顺序依《安十二宫例》。
宫干由年干经五虎遁定寅宫干，其余各宫顺十天干排布（《起五行寅例》）。

显示用的宫位名不改变计算结果；身宫是叠在某宫上的标记，不是第十三个宫。
"""

from dataclasses import dataclass
from enum import StrEnum

from ziwei.config import LeapMonthPolicy
from ziwei.ganzhi import Dizhi, Ganzhi, Tiangan, palace_stems, year_ganzhi


def effective_month(month: int, day: int, is_leap: bool, policy: LeapMonthPolicy) -> int:
  """按闰月口径确定有效生月归属。

  《全书》安身命例以闰月全月归下月；LifeDNA 列全月归本月与十六日起算次月的口径。
  只返回有效月序（1至12）；闰十二月按归下月口径无对应有效月（不合成「来年正月」
  无出处规则）时显式失败。
  """
  if not isinstance(policy, LeapMonthPolicy):
    raise TypeError("闰月口径须为 LeapMonthPolicy 成员")
  if type(month) is not int:
    raise TypeError("农历生月须为整数，不接受 bool")
  if not 1 <= month <= 12:
    raise ValueError("农历生月须在1至12之间")
  if type(day) is not int:
    raise TypeError("农历日须为整数，不接受 bool")
  if day < 1:
    raise ValueError("农历日须为正整数")
  if type(is_leap) is not bool:
    raise TypeError("闰月标志须为 bool")
  if policy is LeapMonthPolicy.全月归下月:
    effective = month + 1 if is_leap else month
  elif policy is LeapMonthPolicy.上半月归本月下半月归下月:
    effective = month + 1 if is_leap and day >= 16 else month
  else:
    effective = month
  if effective > 12:
    raise ValueError("闰十二月按该口径无对应命宫月（不合成来年正月规则）")
  return effective


class PalaceName(StrEnum):
  """十二宫名，按《安十二宫例》顺序；现代常用名作中文别名。"""

  MINGGONG = "命宫"
  XIONGDI = "兄弟"
  QIQIE = "妻妾"
  ZINV = "子女"
  CAIBO = "财帛"
  JIE = "疾厄"
  QIANYI = "迁移"
  NUPU = "奴仆"
  GUANLU = "官禄"
  TIANZHAI = "田宅"
  FUDE = "福德"
  FUMU = "父母"
  命宫 = MINGGONG
  兄弟 = XIONGDI
  妻妾 = QIQIE
  夫妻 = QIQIE
  子女 = ZINV
  财帛 = CAIBO
  疾厄 = JIE
  迁移 = QIANYI
  奴仆 = NUPU
  仆役 = NUPU
  交友 = NUPU
  官禄 = GUANLU
  事业 = GUANLU
  田宅 = TIANZHAI
  福德 = FUDE
  父母 = FUMU


@dataclass(frozen=True, slots=True)
class Palace:
  """一宫的地支、宫干与宫名；宫名只是显示，不改变计算。"""

  dizhi: Dizhi
  tiangan: Tiangan
  name: PalaceName

  @property
  def ganzhi(self) -> Ganzhi:
    """该宫干支。"""
    return Ganzhi(self.tiangan, self.dizhi)


def month_palace_index(month: int) -> int:
  """农历生月对应的地支下标（子为0、寅为2，正月返回2）；只接受1至12。"""
  if type(month) is not int:
    raise TypeError("农历生月须为整数，不接受 bool")
  if not 1 <= month <= 12:
    raise ValueError("农历生月须在1至12之间")
  return (2 + (month - 1)) % 12


def minggong_dizhi(month: int, shichen: Dizhi) -> Dizhi:
  """命宫地支：自寅宫顺数至生月，再自该宫起子时逆数至生时。"""
  if not isinstance(shichen, Dizhi):
    raise TypeError("时辰须为 Dizhi 成员")
  return tuple(Dizhi)[(month_palace_index(month) - tuple(Dizhi).index(shichen)) % 12]


def shengong_dizhi(month: int, shichen: Dizhi) -> Dizhi:
  """身宫地支：自寅宫顺数至生月，再自该宫起子时顺数至生时。"""
  if not isinstance(shichen, Dizhi):
    raise TypeError("时辰须为 Dizhi 成员")
  return tuple(Dizhi)[(month_palace_index(month) + tuple(Dizhi).index(shichen)) % 12]


def _stem_for(stems: tuple[Tiangan, ...], dizhi: Dizhi) -> Tiangan:
  """按寅起偏移取宫干；stems 第0项是寅宫。"""
  return stems[(tuple(Dizhi).index(dizhi) - 2) % 12]


def twelve_palaces(minggong: Dizhi, year_tiangan: Tiangan) -> tuple[Palace, ...]:
  """十二宫，自命宫起逆排；宫干由五虎遁定寅宫干后顺十天干排布。

  返回顺序为命宫、兄弟、妻妾、子女、财帛、疾厄、迁移、奴仆、官禄、田宅、福德、父母。
  """
  if not isinstance(minggong, Dizhi):
    raise TypeError("命宫须为 Dizhi 成员")
  if not isinstance(year_tiangan, Tiangan):
    raise TypeError("年干须为 Tiangan 成员")
  dizhi = tuple(Dizhi)
  stems = palace_stems(year_tiangan)
  start = dizhi.index(minggong)
  return tuple(
    Palace(
      dizhi=dizhi[(start - offset) % 12],
      tiangan=_stem_for(stems, dizhi[(start - offset) % 12]),
      name=tuple(PalaceName)[offset],
    )
    for offset in range(12)
  )


def palace_ganzhi(minggong: Dizhi, ganzhi_year: int) -> Ganzhi:
  """命宫干支：由年干经五虎遁与命宫地支定。"""
  if not isinstance(minggong, Dizhi):
    raise TypeError("命宫须为 Dizhi 成员")
  year = year_ganzhi(ganzhi_year)
  return Ganzhi(_stem_for(palace_stems(year.tiangan), minggong), minggong)
