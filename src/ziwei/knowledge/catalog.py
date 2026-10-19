"""小型不可变目录；不读取文件、出生资料或历法后端。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias, TypeVar

from ziwei.knowledge.model import (
  Citation,
  Concept,
  ConceptKind,
  CurationStatus,
  DisplayEligibility,
  EvidenceAspect,
  KnowledgeEntry,
  PremiseStatus,
  RuleVariant,
  Source,
  SourceStatus,
  _enum,
  _freeze,
  _identifier,
  _text,
)

Record: TypeAlias = Concept | RuleVariant | Source | Citation | KnowledgeEntry
_R = TypeVar("_R", bound=Record)


def _filter_enum(value: StrEnum | None, expected: type[StrEnum]) -> None:
  if value is not None:
    _enum(value, expected)


@dataclass(frozen=True, slots=True, kw_only=True)
class Catalog:
  """构造时拒绝重复标识与悬空引用；查询不推断规则或命盘适用性。"""

  version: str
  concepts: tuple[Concept, ...]
  variants: tuple[RuleVariant, ...]
  sources: tuple[Source, ...]
  citations: tuple[Citation, ...]
  entries: tuple[KnowledgeEntry, ...]

  def __post_init__(self) -> None:
    _text(self.version, "语料版本")
    for name, expected in (
      ("concepts", Concept),
      ("variants", RuleVariant),
      ("sources", Source),
      ("citations", Citation),
      ("entries", KnowledgeEntry),
    ):
      object.__setattr__(self, name, _freeze(getattr(self, name), expected, name))
    ids = [record.id for record in self.records]
    if len(set(ids)) != len(ids):
      raise ValueError("重复标识")
    for concept in self.concepts:
      for target in concept.related_ids:
        self._require(target, Concept)
    for variant in self.variants:
      for target in variant.concept_ids:
        self._require(target, Concept)
      for target in variant.school_ids:
        school = self._require(target, Concept)
        if school.kind is not ConceptKind.SCHOOL:
          raise ValueError("流派引用须指向流派概念")
    for citation in self.citations:
      self._require(citation.source_id, Source)
    for entry in self.entries:
      for group, expected in (
        (entry.concept_ids, Concept),
        (entry.variant_ids, RuleVariant),
        (entry.citation_ids, Citation),
      ):
        for target in group:
          self._require(target, expected)
      if entry.display is DisplayEligibility.DEFAULT and (
        not entry.citation_ids
        or any(
          self._require(citation.source_id, Source).status is not SourceStatus.VERIFIED
          for citation in self.references(entry.id)
        )
      ):
        raise ValueError("默认展示条目须引用已核来源；来源已核本身不授予展示资格")

  @property
  def records(self) -> tuple[Record, ...]:
    """按概念、变体、来源、引文、条目顺序返回完整记录。"""
    return (*self.concepts, *self.variants, *self.sources, *self.citations, *self.entries)

  def get(self, identifier: str) -> Record:
    """按稳定标识查记录；未知标识抛KeyError，不按名称替代。"""
    _identifier(identifier)
    for record in self.records:
      if record.id == identifier:
        return record
    raise KeyError(identifier)

  def _require(self, identifier: str, expected: type[_R]) -> _R:
    record = self.get(identifier)
    if not isinstance(record, expected):
      raise ValueError(f"引用 {identifier} 须指向 {expected.__name__}")
    return record

  def list_concepts(self, *, kind: ConceptKind | None = None) -> tuple[Concept, ...]:
    """列概念，可按种类过滤。"""
    _filter_enum(kind, ConceptKind)
    return tuple(item for item in self.concepts if kind is None or item.kind is kind)

  def list_variants(
    self, *, concept_id: str | None = None, school_id: str | None = None
  ) -> tuple[RuleVariant, ...]:
    """按概念或流派筛选变体；不挑选默认流派。"""
    if concept_id is not None:
      self._require(concept_id, Concept)
    if school_id is not None:
      school = self._require(school_id, Concept)
      if school.kind is not ConceptKind.SCHOOL:
        raise ValueError("school_id须为流派概念")
    return tuple(
      item
      for item in self.variants
      if (concept_id is None or concept_id in item.concept_ids)
      and (school_id is None or school_id in item.school_ids)
    )

  def find(self, name: str) -> tuple[Concept | RuleVariant, ...]:
    """按完整名称或显式别名查找；忽略首尾空白和大小写，歧义返回全部匹配。"""
    _text(name, "查询名称")
    key = name.strip().casefold()
    items: tuple[Concept | RuleVariant, ...] = (*self.concepts, *self.variants)
    return tuple(
      item
      for item in items
      if any(key == label.strip().casefold() for label in (item.name, *item.aliases))
    )

  def references(self, identifier: str) -> tuple[Citation, ...]:
    """独立查看记录的引用；概念与变体汇集关联条目，按目录顺序去重。"""
    record = self.get(identifier)
    if isinstance(record, Source):
      return tuple(item for item in self.citations if item.source_id == identifier)
    if isinstance(record, Citation):
      return (record,)
    ids: set[str] = set()
    for entry in self.entries:
      if identifier == entry.id or identifier in (*entry.concept_ids, *entry.variant_ids):
        ids.update(entry.citation_ids)
    return tuple(item for item in self.citations if item.id in ids)

  def filter_entries(
    self,
    *,
    concept_id: str | None = None,
    variant_id: str | None = None,
    source_id: str | None = None,
    premise_status: PremiseStatus | None = None,
    display: DisplayEligibility | None = None,
    curation: CurationStatus | None = None,
    default_only: bool = False,
  ) -> tuple[KnowledgeEntry, ...]:
    """所有过滤条件取交集；默认返回检索记录，default_only也不判命盘。"""
    for value, expected in ((concept_id, Concept), (variant_id, RuleVariant), (source_id, Source)):
      if value is not None:
        self._require(value, expected)
    for value, expected_enum in (
      (premise_status, PremiseStatus),
      (display, DisplayEligibility),
      (curation, CurationStatus),
    ):
      _filter_enum(value, expected_enum)
    if not isinstance(default_only, bool):
      raise TypeError("default_only须为bool")
    return tuple(
      item
      for item in self.entries
      if (concept_id is None or concept_id in item.concept_ids)
      and (variant_id is None or variant_id in item.variant_ids)
      and (
        source_id is None
        or any(citation.source_id == source_id for citation in self.references(item.id))
      )
      and (premise_status is None or item.premise_status is premise_status)
      and (display is None or item.display is display)
      and (curation is None or item.curation is curation)
      and (not default_only or item.display is DisplayEligibility.DEFAULT)
    )

  def filter_sources(
    self,
    *,
    status: SourceStatus | None = None,
    aspect: EvidenceAspect | None = None,
    lineage_id: str | None = None,
  ) -> tuple[Source, ...]:
    """按核验状态、支持层次或谱系键筛来源；谱系键不计作独立来源数。"""
    _filter_enum(status, SourceStatus)
    _filter_enum(aspect, EvidenceAspect)
    if lineage_id is not None:
      _identifier(lineage_id, "lineage")
    return tuple(
      item
      for item in self.sources
      if (status is None or item.status is status)
      and (lineage_id is None or item.lineage_id == lineage_id)
      and (
        aspect is None or any(aspect in citation.aspects for citation in self.references(item.id))
      )
    )
