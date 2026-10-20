"""命宫起大限：局数起限，阳男阴女顺行、阴男阳女逆行，每限十年。

2007论坛《排命盘口诀》大限段明确使用虚岁，并以3至12、13至22等首尾包含的区间举例；
王亭之讲义图四的金四局4至13、14至23另作对照。只生成岁数标签，不算公历起止日期，
也不规定生日、立春或正月初一换岁。年干取解析层所选年界的结果，性别未知时拒绝起限。
出生年干与阴阳的选择，不等于计算虚岁在哪一天增加。出生类型在计算时才加载，保持知识查询隔离。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Literal

from ziwei.bureau import WuxingJu, bureau_of
from ziwei.ganzhi import Dizhi, Tiangan, Yinyang
from ziwei.palaces import effective_month, minggong_dizhi, palace_ganzhi

if TYPE_CHECKING:
  from ziwei.birth import CalculationInput, Gender

DECADE_RULE_ID: Final = "variant.decades.xusui-inclusive"
DECADE_DEFINITION: Final = (
  "命宫起限，以五行局数为首限起始虚岁，每限十年，起止岁数均包含；"
  "阳男阴女按地支顺行，阴男阳女逆行。只给岁数标签，不换算日期或指定换岁日。"
)


class Direction(StrEnum):
  """地支方向：顺行按子丑寅……亥，逆行相反。"""

  FORWARD = "顺行"
  REVERSE = "逆行"
  顺行 = FORWARD
  逆行 = REVERSE


@dataclass(frozen=True, slots=True)
class Decade:
  """一限的地支、方向及首尾包含的虚岁区间；不表示周岁或实际日期。"""

  dizhi: Dizhi
  direction: Direction
  start_age: int
  end_age: int
  rule_id: str = field(init=False, default=DECADE_RULE_ID)
  age_convention: Literal["虚岁"] = field(init=False, default="虚岁")

  def __post_init__(self) -> None:
    if not isinstance(self.dizhi, Dizhi) or not isinstance(self.direction, Direction):
      raise TypeError("大限须使用 Dizhi 与 Direction 成员")
    if type(self.start_age) is not int or type(self.end_age) is not int:
      raise TypeError("大限岁数须为整数，不接受 bool")
    if self.start_age < 2 or self.end_age != self.start_age + 9:
      raise ValueError("大限起始岁数至少为二，首尾包含共十年")


def decade_direction(year_tiangan: Tiangan, gender: Gender) -> Direction:
  """由生年干阴阳和已知性别定顺逆；未知性别显式失败。"""
  from ziwei.birth import Gender

  if not isinstance(year_tiangan, Tiangan):
    raise TypeError("生年干须为 Tiangan 成员")
  if not isinstance(gender, Gender):
    raise TypeError("性别须为 Gender 成员")
  if gender is Gender.未知:
    raise ValueError("起大限需要已知性别")
  forward = (year_tiangan.yinyang is Yinyang.阳) == (gender is Gender.男)
  return Direction.FORWARD if forward else Direction.REVERSE


def decade_periods(
  minggong: Dizhi, ju: WuxingJu, year_tiangan: Tiangan, gender: Gender
) -> tuple[Decade, ...]:
  """从命宫生成十二限，走满十二地支一次；不为首限之前的年龄补小限或童限。"""
  if not isinstance(minggong, Dizhi):
    raise TypeError("命宫须为 Dizhi 成员")
  if not isinstance(ju, WuxingJu):
    raise TypeError("五行局须为 WuxingJu 成员")
  direction = decade_direction(year_tiangan, gender)
  step = 1 if direction is Direction.FORWARD else -1
  branches = tuple(Dizhi)
  start = branches.index(minggong)
  return tuple(
    Decade(
      branches[(start + step * index) % 12],
      direction,
      ju.number + 10 * index,
      ju.number + 10 * index + 9,
    )
    for index in range(12)
  )


def place_decades(value: CalculationInput) -> tuple[Decade, ...]:
  """由解析结果定命宫与局数后起限；要求时辰和性别已知，不执行历法换算。"""
  from ziwei.birth import CalculationInput

  if not isinstance(value, CalculationInput):
    raise TypeError("起大限须使用 CalculationInput")
  if value.shichen is None:
    raise ValueError("起大限需要已知时辰")
  month = effective_month(
    value.month, value.day, value.is_leap_month, value.config.leap_month_policy
  )
  minggong = minggong_dizhi(month, value.shichen)
  ju = bureau_of(palace_ganzhi(minggong, value.ganzhi_year))
  return decade_periods(minggong, ju, value.year_ganzhi.tiangan, value.gender)
