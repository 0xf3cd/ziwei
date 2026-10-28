"""《紫微斗数全书》卷二固定录文的十四主星七级亮度；不安星或解释吉凶。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from ziwei.ganzhi import Dizhi
from ziwei.stars import MAJOR_STARS, Star


class BrightnessLevel(StrEnum):
  """保留成表表头的七级原名；排列沿原表，不提供数值分数。"""

  MIAO = "庙"
  WANG = "旺"
  DEDI = "得地"
  LIYI = "利益"
  PINGHE = "平和"
  BUDEDI = "不得地"
  LUOXIAN = "落陷"
  庙 = MIAO
  旺 = WANG
  得地 = DEDI
  利益 = LIYI
  平和 = PINGHE
  不得地 = BUDEDI
  落陷 = LUOXIAN


class BrightnessTable(StrEnum):
  """具名表选择；固定电子录文不等于已核纸本，也不连带选择安星或历法规则。"""

  _table_id: str

  def __new__(cls, value: str, table_id: str | None = None) -> BrightnessTable:
    if table_id is None:
      raise ValueError("新增亮度表须显式指定知识标识")
    member = str.__new__(cls, value)
    member._value_ = value
    member._table_id = table_id
    return member

  QUANSHU_JUAN2 = "全书卷二固定录文", "variant.brightness.quanshu-juan2"
  全书卷二录文 = QUANSHU_JUAN2

  @property
  def table_id(self) -> str:
    """此次所选亮度表的知识标识，不是安星规则标识。"""
    return self._table_id


# oldid=1963110卷二“一 命宫”之前的七级成表；各行按子至亥，不用后文星曜条目补改。
_QUANSHU_LEVELS: Final[Mapping[Star, tuple[BrightnessLevel, ...]]] = MappingProxyType(
  {
    star: tuple(BrightnessLevel(value) for value in row.split())
    for star, row in (
      (Star.紫微, "平和 庙 旺 旺 得地 旺 庙 庙 旺 旺 得地 旺"),
      (Star.天机, "庙 落陷 得地 旺 利益 平和 庙 落陷 得地 旺 利益 平和"),
      (Star.太阳, "落陷 不得地 旺 庙 旺 旺 旺 得地 得地 平和 不得地 落陷"),
      (Star.武曲, "旺 庙 得地 利益 庙 平和 旺 庙 得地 利益 庙 平和"),
      (Star.天同, "旺 不得地 利益 平和 平和 庙 落陷 不得地 旺 平和 平和 庙"),
      (Star.廉贞, "平和 利益 庙 平和 利益 落陷 平和 利益 庙 平和 利益 落陷"),
      (Star.天府, "庙 庙 庙 得地 庙 得地 旺 庙 得地 旺 庙 得地"),
      (Star.太阴, "庙 庙 旺 落陷 落陷 落陷 不得地 不得地 利益 旺 旺 庙"),
      (Star.贪狼, "旺 庙 平和 利益 庙 落陷 旺 庙 平和 利益 庙 落陷"),
      (Star.巨门, "旺 不得地 庙 庙 落陷 旺 旺 不得地 庙 庙 落陷 旺"),
      (Star.天相, "庙 庙 庙 落陷 得地 得地 庙 得地 庙 落陷 得地 得地"),
      (Star.天梁, "庙 旺 庙 庙 庙 落陷 庙 旺 落陷 得地 庙 落陷"),
      (Star.七杀, "旺 庙 庙 旺 庙 平和 旺 庙 庙 旺 庙 平和"),
      (Star.破军, "庙 旺 得地 落陷 旺 平和 庙 旺 得地 落陷 旺 平和"),
    )
  }
)


def _brightness_level(star: Star, dizhi: Dizhi, table: BrightnessTable) -> BrightnessLevel | None:
  if not isinstance(star, Star) or not isinstance(dizhi, Dizhi):
    raise TypeError("亮度查询须使用 Star 与 Dizhi 成员")
  if not isinstance(table, BrightnessTable):
    raise TypeError("亮度表须为 BrightnessTable 成员")
  if table is not BrightnessTable.全书卷二录文:
    raise ValueError(f"尚未实现亮度表：{table}")
  if star not in MAJOR_STARS:
    return None
  return _QUANSHU_LEVELS[star][tuple(Dizhi).index(dizhi)]


@dataclass(frozen=True, slots=True)
class BrightnessReading:
  """一颗星的亮度读数；level为None只表示非主星不适用，不表示未请求或表格缺失。

  构造器核对类型及读数与所选表的一致性，不接受自填的其他等级。
  """

  star: Star
  dizhi: Dizhi
  table: BrightnessTable
  level: BrightnessLevel | None

  def __post_init__(self) -> None:
    if self.level is not None and not isinstance(self.level, BrightnessLevel):
      raise TypeError("亮度等级须为 BrightnessLevel 成员或 None")
    if self.level is not _brightness_level(self.star, self.dizhi, self.table):
      raise ValueError("亮度读数须与星曜、地支及所选表一致")

  @property
  def table_id(self) -> str:
    """所选表的知识标识，不复用StarPlacement.rule_id。"""
    return self.table.table_id


def star_brightness(star: Star, dizhi: Dizhi, *, table: BrightnessTable) -> BrightnessReading:
  """显式选择表，按星曜与地支取只读亮度；非主星的level为None。

  只接受枚举成员，错类型抛TypeError。主星格缺失显式失败，不填默认等级或不适用。
  本表仅为固定录文的十四主星子集，不采用原表的辅星格，也不随同书条目修正成表。
  """
  return BrightnessReading(star, dizhi, table, _brightness_level(star, dizhi, table))
