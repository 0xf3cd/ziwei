"""童限六宫定位与起限当岁边界选择。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from ziwei.bureau import WuxingJu
from ziwei.ganzhi import Dizhi
from ziwei.palaces import PalaceName, palace_dizhi

TONGXIAN_RULE_ID: Final = "variant.tongxian.six-palaces"
"""一至六岁按本命宫名定位的规则标识。"""
TONGXIAN_PALACES: Final = (
  PalaceName.命宫,
  PalaceName.财帛,
  PalaceName.疾厄,
  PalaceName.夫妻,
  PalaceName.福德,
  PalaceName.官禄,
)
"""一至六岁对应的本命宫名。"""


class TongxianBoundary(StrEnum):
  """童限是否包含首大限起限当岁的两种选择。"""

  BEFORE_DECADE = "起限当岁不含"
  THROUGH_DECADE_START = "起限当岁包含"
  起限当岁不含 = BEFORE_DECADE
  起限当岁包含 = THROUGH_DECADE_START

  @property
  def rule_id(self) -> str:
    """衔接解释的标识，与六宫定位规则分别记录。"""
    return {
      TongxianBoundary.BEFORE_DECADE: "variant.tongxian.before-decade",
      TongxianBoundary.THROUGH_DECADE_START: "variant.tongxian.through-decade-start",
    }[self]

  @property
  def definition(self) -> str:
    """所选边界的适用年龄及并读规则。"""
    return {
      TongxianBoundary.BEFORE_DECADE: (
        "仓内读法：童限适用于一岁至局数减一岁，起限当岁停止；小限始终独立计算。"
      ),
      TongxianBoundary.THROUGH_DECADE_START: (
        "仓内读法：童限适用于一岁至局数岁，起限当岁与首大限并存；小限始终独立计算。"
      ),
    }[self]


def _check_age(age: int) -> None:
  if type(age) is not int:
    raise TypeError("童限虚岁不接受 bool" if isinstance(age, bool) else "童限虚岁须为整数")
  if age < 1:
    raise ValueError("童限虚岁须为正整数")


def tongxian_palace(age: int) -> PalaceName:
  """查询一至六岁对应的本命宫名；七岁起抛NotImplementedError。"""
  _check_age(age)
  if age > len(TONGXIAN_PALACES):
    raise NotImplementedError("六宫映射只定义一至六岁")
  return TONGXIAN_PALACES[age - 1]


@dataclass(frozen=True, slots=True, kw_only=True)
class Tongxian:
  """所选边界下的童限读数；超过适用年龄时宫名与地支均为None。"""

  minggong: Dizhi
  ju: WuxingJu
  age: int
  boundary: TongxianBoundary
  palace_name: PalaceName | None = field(init=False)
  dizhi: Dizhi | None = field(init=False)

  def __post_init__(self) -> None:
    if not isinstance(self.minggong, Dizhi):
      raise TypeError("童限命宫须为 Dizhi 成员")
    if not isinstance(self.ju, WuxingJu):
      raise TypeError("童限五行局须为 WuxingJu 成员")
    if not isinstance(self.boundary, TongxianBoundary):
      raise TypeError("童限边界须显式使用 TongxianBoundary 成员")
    _check_age(self.age)
    last_age = self.ju.number - int(self.boundary is TongxianBoundary.BEFORE_DECADE)
    name = tongxian_palace(self.age) if self.age <= last_age else None
    position = palace_dizhi(self.minggong, name) if name is not None else None
    object.__setattr__(self, "palace_name", name)
    object.__setattr__(self, "dizhi", position)

  @property
  def rule_id(self) -> str:
    """六宫定位的规则标识；衔接解释另见boundary.rule_id。"""
    return TONGXIAN_RULE_ID


def tongxian_at_age(
  minggong: Dizhi, ju: WuxingJu, age: int, *, boundary: TongxianBoundary
) -> Tongxian:
  """按命宫、五行局、虚岁和边界查询童限。

  超过所选边界的适用年龄时，返回的宫名与地支均为None。
  """
  return Tongxian(minggong=minggong, ju=ju, age=age, boundary=boundary)
