"""童限六宫定位，以及现代大限起运框架下两种显式的当岁读法。

六宫口诀见《全书》卷二与《捷览》第53章录文，传承独立性未核。
停止关联大限、期间参看小限见《精成》PDF第507页，目前只核到一路现代文本。
当岁包含性未由原文裁定，两个边界均为仓内解释，不是两种已认证古法。
《捷览》录文另提七八九岁，不能把本模块最晚六岁停止的现代框架当成该录文的完整规则。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from ziwei.bureau import WuxingJu
from ziwei.ganzhi import Dizhi
from ziwei.palaces import PalaceName, palace_dizhi

TONGXIAN_RULE_ID: Final = "variant.tongxian.six-palaces"
"""一至六岁按本命宫名定位的规则标识，不包含停止条件。"""
TONGXIAN_PALACES: Final = (
  PalaceName.命宫,
  PalaceName.财帛,
  PalaceName.疾厄,
  PalaceName.夫妻,
  PalaceName.福德,
  PalaceName.官禄,
)
"""一至六岁的本命宫名；不按地支固定、不作周期循环。"""


class TongxianBoundary(StrEnum):
  """《精成》现代停止框架的两种仓内解释；调用者须显式选择，无默认。"""

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
    """所选读法的适用年龄及与小限、大限的关系；不声称是文献明文。"""
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
    raise TypeError("童限虚岁须为整数，不接受 bool")
  if age < 1:
    raise ValueError("童限虚岁须为正整数")


def tongxian_palace(age: int) -> PalaceName:
  """取一至六岁本命宫名；七岁以后抛NotImplementedError，不猜后续古法宫序。"""
  _check_age(age)
  if age > len(TONGXIAN_PALACES):
    raise NotImplementedError("六宫映射只定义一至六岁；七岁以后的古法宫序未核定")
  return TONGXIAN_PALACES[age - 1]


@dataclass(frozen=True, slots=True, kw_only=True)
class Tongxian:
  """现代具名边界下的童限读数；不适用时宫名与地支同为None，不替换为小限。"""

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
  """先判所选现代边界是否适用，再作六宫定位；边界必填，不要求性别或出生资料。

  超过所选适用年龄返回空宫位读数，不触发低层七岁未定义错误；非法输入仍显式失败。
  """
  return Tongxian(minggong=minggong, ju=ju, age=age, boundary=boundary)
