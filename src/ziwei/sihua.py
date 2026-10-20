"""生年干的两套完整四化表；不连带选择同一著作的历法或安星规则。

《排命盘口诀》取2007论坛所见转录，王亭之表取讲义「安四化星诀」的网页提取稿。
各表十干均来自自身的完整出处；具体行另以独立成文核对，不拼接不同作者的格子。
转录页、讲义提取稿不等于已校纸本，名称也不认证整个门派。出处与限度见知识目录。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from ziwei.ganzhi import Tiangan
from ziwei.stars import Star

if TYPE_CHECKING:
  from ziwei.birth import CalculationInput


class SihuaVariant(StrEnum):
  """只选择四化表，无默认；中文值说明实际核到的转录层。"""

  ZHONGYI999 = "排命盘口诀网页转录"
  WANGTINGZHI_LECTURE = "王亭之讲义转录"
  排命盘口诀转录 = ZHONGYI999
  王亭之讲义转录 = WANGTINGZHI_LECTURE

  @property
  def rule_id(self) -> str:
    """知识目录中整套十干表的标识，不与既有单行异文混用。"""
    return "variant.sihua." + self.name.lower().replace("_", "-")


@dataclass(frozen=True, slots=True)
class SihuaTable:
  """按甲至癸排列的十行，每行依次为禄、权、科、忌；复制调用方的序列。"""

  variant: SihuaVariant
  rows: tuple[tuple[Star, Star, Star, Star], ...]

  def __post_init__(self) -> None:
    if not isinstance(self.variant, SihuaVariant):
      raise TypeError("四化变体须为 SihuaVariant 成员")
    if isinstance(self.rows, str):
      raise TypeError("四化表须为星曜序列")
    rows = tuple(tuple(row) for row in self.rows)
    if len(rows) != 10 or any(len(row) != 4 for row in rows):
      raise ValueError("四化表须有十干，每干四颗星，依次为禄权科忌")
    for row in rows:
      if any(not isinstance(star, Star) for star in row):
        raise TypeError("四化星曜须为 Star 成员")
      if len(set(row)) != 4:
        raise ValueError("同一干的四化星曜不得重复")
    object.__setattr__(self, "rows", rows)

  @property
  def id(self) -> str:
    """该完整变体的规则标识。"""
    return self.variant.rule_id


# 两份完整转录分别保留，不以覆盖共有表的方式掩盖组合出处。引文另存知识目录。
SIHUA_TABLES: Final[tuple[SihuaTable, ...]] = (
  SihuaTable(
    SihuaVariant.ZHONGYI999,
    (
      (Star.廉贞, Star.破军, Star.武曲, Star.太阳),
      (Star.天机, Star.天梁, Star.紫微, Star.太阴),
      (Star.天同, Star.天机, Star.文昌, Star.廉贞),
      (Star.太阴, Star.天同, Star.天机, Star.巨门),
      (Star.贪狼, Star.太阴, Star.右弼, Star.天机),
      (Star.武曲, Star.贪狼, Star.天梁, Star.文曲),
      (Star.太阳, Star.武曲, Star.天同, Star.太阴),
      (Star.巨门, Star.太阳, Star.文曲, Star.文昌),
      (Star.天梁, Star.紫微, Star.左辅, Star.武曲),
      (Star.破军, Star.巨门, Star.太阴, Star.贪狼),
    ),
  ),
  SihuaTable(
    SihuaVariant.WANGTINGZHI_LECTURE,
    (
      (Star.廉贞, Star.破军, Star.武曲, Star.太阳),
      (Star.天机, Star.天梁, Star.紫微, Star.太阴),
      (Star.天同, Star.天机, Star.文昌, Star.廉贞),
      (Star.太阴, Star.天同, Star.天机, Star.巨门),
      (Star.贪狼, Star.太阴, Star.太阳, Star.天机),
      (Star.武曲, Star.贪狼, Star.天梁, Star.文曲),
      (Star.太阳, Star.武曲, Star.天府, Star.天同),
      (Star.巨门, Star.太阳, Star.文曲, Star.文昌),
      (Star.天梁, Star.紫微, Star.天府, Star.武曲),
      (Star.破军, Star.巨门, Star.太阴, Star.贪狼),
    ),
  ),
)


@dataclass(frozen=True, slots=True)
class SihuaResult:
  """保存所用年干、变体与四颗星；固定字段避免遗漏或重复四化标签，不包含星位。"""

  year_tiangan: Tiangan
  variant: SihuaVariant
  lu: Star
  quan: Star
  ke: Star
  ji: Star

  def __post_init__(self) -> None:
    if not isinstance(self.year_tiangan, Tiangan):
      raise TypeError("生年干须为 Tiangan 成员")
    if not isinstance(self.variant, SihuaVariant):
      raise TypeError("四化变体须为 SihuaVariant 成员")
    if any(not isinstance(star, Star) for star in (self.lu, self.quan, self.ke, self.ji)):
      raise TypeError("四化结果须使用 Star 成员")
    if len({self.lu, self.quan, self.ke, self.ji}) != 4:
      raise ValueError("同一干的四化星曜不得重复")

  @property
  def rule_id(self) -> str:
    """此次所选完整表在知识目录中的标识。"""
    return self.variant.rule_id


def sihua_for_stem(year_tiangan: Tiangan, variant: SihuaVariant) -> SihuaResult:
  """按生年干取禄权科忌；只需年干，不要求性别、时辰或星位。"""
  if not isinstance(year_tiangan, Tiangan):
    raise TypeError("生年干须为 Tiangan 成员")
  if not isinstance(variant, SihuaVariant):
    raise TypeError("四化变体须为 SihuaVariant 成员")
  tables = tuple(table for table in SIHUA_TABLES if table.variant is variant)
  if len(tables) != 1:
    raise ValueError(f"四化变体须恰有一份完整定义：{variant}")
  row = tables[0].rows[tuple(Tiangan).index(year_tiangan)]
  return SihuaResult(year_tiangan, variant, *row)


def shengnian_sihua(value: CalculationInput, variant: SihuaVariant) -> SihuaResult:
  """使用解析结果的年干；不改用农历年，不调用完整命盘校验。"""
  from ziwei.birth import CalculationInput

  if not isinstance(value, CalculationInput):
    raise TypeError("生年四化须使用 CalculationInput")
  return sihua_for_stem(value.year_ganzhi.tiangan, variant)
