"""按生年支、性别和正整数虚岁计算小限宫位。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from ziwei.ganzhi import Dizhi

if TYPE_CHECKING:
  from ziwei.birth import Gender

XIAOXIAN_RULE_ID: Final = "variant.xiaoxian.year-branch-gender"
"""四组起宫、男顺女逆的小限规则标识。"""
XIAOXIAN_DEFINITION: Final = (
  "按生年支三合组定一岁起宫，男命按地支顺行、女命逆行，每岁一宫。年龄用正整数虚岁。"
)
"""小限定位定义；起宫取XIAOXIAN_STARTS。"""
XIAOXIAN_STARTS: Final = (
  ((Dizhi.寅, Dizhi.午, Dizhi.戌), Dizhi.辰),
  ((Dizhi.申, Dizhi.子, Dizhi.辰), Dizhi.戌),
  ((Dizhi.巳, Dizhi.酉, Dizhi.丑), Dizhi.未),
  ((Dizhi.亥, Dizhi.卯, Dizhi.未), Dizhi.丑),
)
"""生年支组与对应的一岁小限地支。"""


@dataclass(frozen=True, slots=True, kw_only=True)
class Xiaoxian:
  """指定虚岁的小限宫位及计算输入。"""

  year_dizhi: Dizhi
  gender: Gender
  age: int
  dizhi: Dizhi = field(init=False)

  def __post_init__(self) -> None:
    from ziwei.birth import Gender

    if not isinstance(self.year_dizhi, Dizhi):
      raise TypeError("小限生年支须为 Dizhi 成员")
    if not isinstance(self.gender, Gender):
      raise TypeError("小限性别须为 Gender 成员")
    if self.gender is Gender.未知:
      raise ValueError("小限需要已知性别")
    if type(self.age) is not int:
      raise TypeError("小限虚岁须为整数，不接受 bool")
    if self.age < 1:
      raise ValueError("小限虚岁须为正整数")
    start = next(start for group, start in XIAOXIAN_STARTS if self.year_dizhi in group)
    branches = tuple(Dizhi)
    step = 1 if self.gender is Gender.男 else -1
    position = branches[(branches.index(start) + step * (self.age - 1)) % len(branches)]
    object.__setattr__(self, "dizhi", position)

  @property
  def rule_id(self) -> str:
    """本读数使用的定位规则标识。"""
    return XIAOXIAN_RULE_ID


def xiaoxian_at_age(year_dizhi: Dizhi, gender: Gender, age: int) -> Xiaoxian:
  """按生年支、已知性别和正整数虚岁查询小限。"""
  return Xiaoxian(year_dizhi=year_dizhi, gender=gender, age=age)
