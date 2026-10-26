"""命宫、身宫、十二宫与宫干。

命宫与身宫由农历生月与生时定：从寅宫起正月顺数至生月，再自该宫起子时，逆数至生时安命、
顺数至生时安身（《紫微斗數全書》卷二《安身命例》，维基文库修订1963110；同法见王亭之中州派
《紫微斗数初级讲义》安命身宫诀）。十二宫自命宫起逆排，宫名与顺序依《安十二宫例》。
宫干由年干经五虎遁定寅宫干，其余各宫顺十天干排布（《起五行寅例》）。

显示用的宫位名不改变计算结果；身宫是叠在某宫上的标记，不是第十三个宫。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final, cast

from ziwei.bureau import WuxingJu, bureau_of
from ziwei.config import LeapMonthPolicy
from ziwei.ganzhi import Dizhi, Ganzhi, Tiangan, palace_stems, year_ganzhi

if TYPE_CHECKING:
  from ziwei.birth import CalculationInput

OPPOSITE_RULE_ID: Final = "variant.palace.opposite"
"""对宫关系在知识目录中的标识。"""
SANFANG_SIZHENG_RULE_ID: Final = "variant.palace.sanfang-sizheng"
"""三方四正四成员关系在知识目录中的标识。"""


def opposite_dizhi(dizhi: Dizhi) -> Dizhi:
  """返回对宫地支，即十二宫环上相隔六宫的位置。

  NTNU个人空间《名詞解釋》与安迪《紫微斗數解盤：三方四正的應用》均支持此对宫关系；
  只据所见现代网页，不认证古籍底本。来源与短引见知识目录。
  """
  if not isinstance(dizhi, Dizhi):
    raise TypeError("宫位地支须为 Dizhi 成员")
  order = tuple(Dizhi)
  return order[(order.index(dizhi) + 6) % 12]


def sanfang_sizheng(dizhi: Dizhi) -> tuple[Dizhi, Dizhi, Dizhi, Dizhi]:
  """返回本宫、两个三合宫与对宫，不借星或解释吉凶。

  顺序固定为本宫、地支序偏移+4、偏移+8、对宫；地支序按子丑寅卯排列并循环，这是项目API约定。
  两份现代网页的命宫与夫妻宫例支持这四个成员，不规定此顺序，也不用于定义单独的“三方”称谓。
  """
  if not isinstance(dizhi, Dizhi):
    raise TypeError("宫位地支须为 Dizhi 成员")
  order = tuple(Dizhi)
  start = order.index(dizhi)
  return dizhi, order[(start + 4) % 12], order[(start + 8) % 12], opposite_dizhi(dizhi)


def effective_month(month: int, day: int, is_leap: bool, policy: LeapMonthPolicy) -> int:
  """按所选闰月归属规则，返回安星使用的月份（1至12）。

  《紫微斗數全書》的安身命例将闰月全月算作下月；LifeDNA网站还列出全月算作本月、
  或初一至十五算作本月而十六日起算作下月的方式。
  闰十二月若需要算作下月（包括按前后半月归属时的十六日起），会因没有第13月而抛错，
  不自行改作来年正月，因为所据规则没有说明这种处理方式。

  只核月1至12、日1至30等基本值域；真实月长与闰月是否存在由历法适配核验。
  """
  if not isinstance(policy, LeapMonthPolicy):
    raise TypeError("闰月口径须为 LeapMonthPolicy 成员")
  if type(month) is not int:
    raise TypeError("农历生月须为整数，不接受 bool")
  if not 1 <= month <= 12:
    raise ValueError("农历生月须在1至12之间")
  if type(day) is not int:
    raise TypeError("农历日须为整数，不接受 bool")
  if not 1 <= day <= 30:
    raise ValueError("农历日须在1至30之间")
  if type(is_leap) is not bool:
    raise TypeError("闰月标志须为 bool")
  if policy is LeapMonthPolicy.全月归下月:
    effective = month + 1 if is_leap else month
  elif policy is LeapMonthPolicy.上半月归本月下半月归下月:
    effective = month + 1 if is_leap and day >= 16 else month
  elif policy is LeapMonthPolicy.全月归本月:
    effective = month
  else:
    raise ValueError(f"尚未实现的闰月口径：{policy.value}")
  if effective > 12:
    raise ValueError("闰十二月按该口径无对应安星月（不合成来年正月规则）")
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
  """一宫的地支、宫干与宫名；构造时核枚举类型与干支配对，宫名不改变计算。"""

  dizhi: Dizhi
  tiangan: Tiangan
  name: PalaceName

  def __post_init__(self) -> None:
    for name, kind in (("dizhi", Dizhi), ("tiangan", Tiangan), ("name", PalaceName)):
      if not isinstance(getattr(self, name), kind):
        raise TypeError(f"宫位{name}须为{kind.__name__}成员（领域枚举）")
    Ganzhi(self.tiangan, self.dizhi)

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


@dataclass(frozen=True, slots=True)
class _ChartFrame:
  month: int
  minggong: Dizhi
  bureau: WuxingJu


def _chart_frame(value: CalculationInput) -> _ChartFrame:
  """推导安星月份、命宫与五行局；调用方先核输入类型与已知时辰，允许性别未知。"""
  month = effective_month(
    value.month, value.day, value.is_leap_month, value.config.leap_month_policy
  )
  minggong = minggong_dizhi(month, cast(Dizhi, value.shichen))
  return _ChartFrame(month, minggong, bureau_of(palace_ganzhi(minggong, value.ganzhi_year)))
