"""知识记录的值类型；来源核验、前提与展示资格各有自己的状态。"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Literal, TypeVar
from urllib.parse import urlsplit

from ziwei.config import PolicyOption

_T = TypeVar("_T")


class ConceptKind(StrEnum):
  """概念分类，不据此推断星曜性质。"""

  STAR = "星曜"
  PALACE = "宫位"
  SIHUA = "四化"
  WUXINGJU = "五行局"
  POLICY = "口径"
  SCHOOL = "流派"
  星曜 = STAR
  宫位 = PALACE
  四化 = SIHUA
  五行局 = WUXINGJU
  口径 = POLICY
  流派 = SCHOOL


class TextLayer(StrEnum):
  """区分原文、译文、今人说明与仓内撰写的陈述。"""

  ORIGINAL = "原文"
  COMMENTARY = "注释"
  TRANSLATION = "译文"
  MODERN = "今人说明"
  EDITORIAL = "仓内说明"
  原文 = ORIGINAL
  注释 = COMMENTARY
  译文 = TRANSLATION
  今人说明 = MODERN
  仓内说明 = EDITORIAL


class EvidenceAspect(StrEnum):
  """一处引文回答的是哪一层问题。"""

  SYSTEM = "系统归属"
  RULE = "规则"
  METHOD = "查法"
  系统归属 = SYSTEM
  规则 = RULE
  查法 = METHOD


class SourceStatus(StrEnum):
  """已核仅指所列版本与定位，不认证祖本或安星规则。"""

  VERIFIED = "所列版本已核"
  UNVERIFIED = "版本待核"
  已核 = VERIFIED
  待核 = UNVERIFIED


class PremiseStatus(StrEnum):
  """前提是否已表达清楚，不回答某张盘是否满足。"""

  COMPLETE = "前提已明确"
  UNRESOLVED = "前提待定"
  已明确 = COMPLETE
  待定 = UNRESOLVED


class DisplayEligibility(StrEnum):
  """由整理者显式指定，不由出处状态自动推导。"""

  DEFAULT = "可默认展示"
  WITHHELD = "暂不默认展示"
  可默认展示 = DEFAULT
  暂不默认展示 = WITHHELD


class CurationStatus(StrEnum):
  """整理进度与来源可信度分开。"""

  DRAFT = "待整理"
  CURATED = "已整理"
  待整理 = DRAFT
  已整理 = CURATED


def _text(value: str, label: str) -> None:
  if not isinstance(value, str):
    raise TypeError(f"{label}须为字符串")
  if not value.strip():
    raise ValueError(f"{label}不可为空")


def _identifier(value: str, prefix: str | None = None) -> None:
  _text(value, "标识")
  if not re.fullmatch(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+", value):
    raise ValueError(f"标识须为小写 ASCII 分段名称：{value}")
  if prefix is not None and not value.startswith(prefix + "."):
    raise ValueError(f"标识须以 {prefix}. 开头")


def _enum(value: object, expected: type[StrEnum]) -> None:
  if not isinstance(value, expected):
    raise TypeError(f"须为 {expected.__name__} 成员")


def _freeze(values: Sequence[_T], expected: type[_T], label: str) -> tuple[_T, ...]:
  if isinstance(values, str | bytes) or not isinstance(values, Sequence):
    raise TypeError(f"{label}须为序列")
  result = tuple(values)
  if any(not isinstance(value, expected) for value in result):
    raise TypeError(f"{label}成员须为 {expected.__name__}")
  return result


def _strings(values: Sequence[str], label: str, prefix: str | None = None) -> tuple[str, ...]:
  result = _freeze(values, str, label)
  for value in result:
    _text(value, label)
    if prefix is not None:
      _identifier(value, prefix)
  if len(set(result)) != len(result):
    raise ValueError(f"{label}不可重复")
  return result


def _url(value: str) -> None:
  _text(value, "URL")
  parsed = urlsplit(value)
  if (
    parsed.scheme not in ("https", "http")
    or not parsed.hostname
    or parsed.username is not None
    or any(character.isspace() for character in value)
  ):
    raise ValueError("URL须为不含凭证的HTTP(S)绝对地址")


@dataclass(frozen=True, slots=True, kw_only=True)
class Concept:
  """稳定身份、显示名称及关系；改名不改变标识。"""

  id: str
  name: str
  kind: ConceptKind
  aliases: tuple[str, ...] = ()
  related_ids: tuple[str, ...] = ()
  options: tuple[PolicyOption, ...] = ()

  def __post_init__(self) -> None:
    _identifier(self.id, "concept")
    _text(self.name, "名称")
    _enum(self.kind, ConceptKind)
    object.__setattr__(self, "aliases", _strings(self.aliases, "别名"))
    object.__setattr__(self, "related_ids", _strings(self.related_ids, "关联概念", "concept"))
    options = _freeze(self.options, StrEnum, "关联口径")
    if any(not isinstance(option, PolicyOption) for option in options):
      raise TypeError("关联口径须为已实现的口径枚举成员")
    if len(set(options)) != len(options):
      raise ValueError("关联口径不可重复")
    if options and self.kind is not ConceptKind.POLICY:
      raise ValueError("只有口径概念能关联配置选项")
    object.__setattr__(self, "options", options)


@dataclass(frozen=True, slots=True, kw_only=True)
class RuleVariant:
  """一项有名称、定义和适用范围的规则。

  option可关联历法口径选项；implementation保存实现中公开函数或对象的路径字符串，
  查询知识时不会按这个路径导入模块或执行计算。
  """

  id: str
  name: str
  definition: str
  scope: str
  concept_ids: tuple[str, ...]
  tracking_url: str
  aliases: tuple[str, ...] = ()
  school_ids: tuple[str, ...] = ()
  conditions: tuple[str, ...] = ()
  option: PolicyOption | None = None
  implementation: str | None = None

  def __post_init__(self) -> None:
    _identifier(self.id, "variant")
    for value in (self.name, self.definition, self.scope):
      _text(value, "变体说明")
    _url(self.tracking_url)
    for name, prefix in (("concept_ids", "concept"), ("school_ids", "concept")):
      object.__setattr__(self, name, _strings(getattr(self, name), name, prefix))
    if not self.concept_ids:
      raise ValueError("变体须关联概念")
    object.__setattr__(self, "aliases", _strings(self.aliases, "别名"))
    object.__setattr__(self, "conditions", _strings(self.conditions, "条件"))
    if self.option is not None and not isinstance(self.option, PolicyOption):
      raise TypeError("option须为已实现的口径枚举成员")
    if self.implementation is not None:
      _text(self.implementation, "实现路径")
      if not re.fullmatch(r"ziwei(?:\.[a-z][a-z0-9_]*)+", self.implementation):
        raise ValueError("实现路径须为ziwei包内的公开对象路径")


@dataclass(frozen=True, slots=True, kw_only=True)
class Source:
  """所列版本的出处。checked_on是核验尝试日期，是否已核由status记录。

  谱系键只归并同路转录，不认证祖本独立性。
  """

  id: str
  title: str
  edition: str
  url: str
  layer: TextLayer
  lineage_id: str
  provenance: str
  claims: str
  limits: str
  rights: str
  status: SourceStatus
  authors: tuple[str, ...] = ()
  checked_on: date | None = None

  def __post_init__(self) -> None:
    _identifier(self.id, "source")
    _identifier(self.lineage_id, "lineage")
    for value in (self.title, self.edition, self.provenance, self.claims, self.limits, self.rights):
      _text(value, "来源说明")
    _url(self.url)
    _enum(self.layer, TextLayer)
    _enum(self.status, SourceStatus)
    object.__setattr__(self, "authors", _strings(self.authors, "作者"))
    if self.checked_on is not None and type(self.checked_on) is not date:
      raise TypeError("核验日期须为date或None")
    if self.status is SourceStatus.VERIFIED and self.checked_on is None:
      raise ValueError("已核来源须有核验日期")


@dataclass(frozen=True, slots=True, kw_only=True)
class Citation:
  """一处定位与原文；不规范化字形、标点或口诀。"""

  id: str
  source_id: str
  locator: str
  quote: str
  layer: TextLayer
  aspects: tuple[EvidenceAspect, ...]
  limits: str

  def __post_init__(self) -> None:
    _identifier(self.id, "citation")
    _identifier(self.source_id, "source")
    _enum(self.layer, TextLayer)
    for value in (self.locator, self.quote, self.limits):
      _text(value, "引文说明")
    aspects = _freeze(self.aspects, EvidenceAspect, "支持层次")
    if not aspects or len(set(aspects)) != len(aspects):
      raise ValueError("支持层次须非空且不重复")
    object.__setattr__(self, "aspects", aspects)


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeEntry:
  """整理者的有条件陈述；逐字引文放Citation。chart_match恒为未评估，不判断命盘。"""

  id: str
  statement: str
  concept_ids: tuple[str, ...]
  variant_ids: tuple[str, ...]
  citation_ids: tuple[str, ...]
  premises: tuple[str, ...]
  premise_status: PremiseStatus
  display: DisplayEligibility
  curation: CurationStatus
  limits: str
  exceptions: tuple[str, ...] = ()
  alternatives: tuple[str, ...] = ()
  recheck: str = ""
  tracking_url: str = ""
  chart_match: Literal["未评估"] = field(default="未评估", init=False)

  def __post_init__(self) -> None:
    _identifier(self.id, "entry")
    _text(self.statement, "陈述")
    _text(self.limits, "限度")
    for value, expected in (
      (self.premise_status, PremiseStatus),
      (self.display, DisplayEligibility),
      (self.curation, CurationStatus),
    ):
      _enum(value, expected)
    for name, prefix in (
      ("concept_ids", "concept"),
      ("variant_ids", "variant"),
      ("citation_ids", "citation"),
    ):
      object.__setattr__(self, name, _strings(getattr(self, name), name, prefix))
    for name in ("premises", "exceptions", "alternatives"):
      object.__setattr__(self, name, _strings(getattr(self, name), name))
    if not self.concept_ids or not self.premises:
      raise ValueError("条目须有概念与显式前提")
    if len(self.alternatives) == 1:
      raise ValueError("并列读法至少两种")
    if not isinstance(self.recheck, str) or not isinstance(self.tracking_url, str):
      raise TypeError("翻案条件与跟踪URL须为字符串")
    if self.tracking_url:
      _url(self.tracking_url)
    if self.display is DisplayEligibility.DEFAULT:
      if (
        self.premise_status is not PremiseStatus.COMPLETE
        or self.curation is not CurationStatus.CURATED
      ):
        raise ValueError("默认展示须前提明确且完成整理")
    else:
      _text(self.recheck, "翻案条件")
      _url(self.tracking_url)
