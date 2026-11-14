"""本批现代短引按完整谱系核增量，旧引文冻结但不据此认证旧总量合规。"""

import hashlib
import json
from dataclasses import replace

import pytest

from ziwei.knowledge import load_catalog
from ziwei.knowledge.catalog import Catalog
from ziwei.knowledge.model import Citation, Source

# e13e3ff中受影响谱系全部(id, source_id, quote)排序后的UTF-8紧凑JSON摘要。
BASELINES = {
  "lineage.jielan-tianji": (
    208,
    "69e353692ebde8273f92a4472b2b2c1d94dc305742ad1e5d93fbd25c849dd430",
  ),
  "lineage.zhongzhou-wangtingzhi": (
    276,
    "4e8354ea5dc7669b08b08ae79417619966bf0fef7ad4a641d77ae4c3b6ccfa27",
  ),
  "lineage.iluck-natal-stars": (
    0,
    "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
  ),
  "lineage.yunling-shangshi": (
    0,
    "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
  ),
}
ADDITIONS = {
  "citation.jielan.kuxu": ("source.jielan-kuxu-tianji", "lineage.jielan-tianji", "哭逆巨行虚顺未"),
  "citation.jielan.tiankong-year": (
    "source.jielan-tiankong-tianji",
    "lineage.jielan-tianji",
    "前一位丑宫即安天空",
  ),
  "citation.iluck.kuxu": (
    "source.iluck-year-branch",
    "lineage.iluck-natal-stars",
    "天哭位于申宫。\n天虚位于辰宫。",
  ),
  "citation.iluck.shangshi": (
    "source.iluck-shangshi",
    "lineage.iluck-natal-stars",
    "天殇星永远位于交友宫。\n天使星永远位于疾厄宫。",
  ),
  "citation.yunling.shangshi": (
    "source.yunling-shangshi",
    "lineage.yunling-shangshi",
    "天伤星固定安在交友宫，天使固定安在疾厄宫。",
  ),
  "citation.zhongzhou.shangshi-swap": (
    "source.zhongzhou-mdyixue-lower",
    "lineage.zhongzhou-wangtingzhi",
    "凡阳男阴女皆依此诀，但若为阴男阳女，则改为天伤居疾厄，天使居仆役。",
  ),
}


def _check_quote_increment(catalog: Catalog, additions: dict[str, tuple[str, str, str]]) -> None:
  sources = {s.id: s.lineage_id for s in catalog.sources}
  for identifier, (source_id, lineage, quote) in additions.items():
    citation = catalog.get(identifier)
    assert isinstance(citation, Citation)
    assert citation.source_id == source_id and citation.quote == quote
    assert sources[source_id] == lineage and lineage in BASELINES
  for lineage, (before, digest) in BASELINES.items():
    citations = [c for c in catalog.citations if sources[c.source_id] == lineage]
    old = sorted((c.id, c.source_id, c.quote) for c in citations if c.id not in additions)
    serialized = json.dumps(old, ensure_ascii=False, separators=(",", ":")).encode()
    assert hashlib.sha256(serialized).hexdigest() == digest
    assert sum(len(row[2]) for row in old) == before
    added = {identifier for identifier, row in additions.items() if row[1] == lineage}
    assert {c.id for c in citations} == {row[0] for row in old} | added
    increment = sum(len(additions[identifier][2]) for identifier in added)
    assert increment <= 90
    assert sum(len(c.quote) for c in citations) == before + increment


def test_added_modern_quotes_have_complete_lineage_accounting() -> None:
  _check_quote_increment(load_catalog(), ADDITIONS)


@pytest.mark.parametrize("defect", ["over-budget", "unlisted-source", "relineage", "old-quote"])
def test_increment_gate_rejects_unaccounted_quotes(defect: str) -> None:
  catalog = load_catalog()
  _check_quote_increment(catalog, ADDITIONS)
  additions = dict(ADDITIONS)
  template = catalog.get("citation.jielan.kuxu")
  assert isinstance(template, Citation)
  if defect in ("over-budget", "unlisted-source"):
    source = catalog.get(template.source_id)
    assert isinstance(source, Source)
    new_source = replace(source, id="source.synthetic-same-lineage")
    quote = "字" * 91 if defect == "over-budget" else "同谱系另源短引"
    extra = replace(template, id="citation.synthetic-extra", source_id=new_source.id, quote=quote)
    catalog = replace(
      catalog, sources=(*catalog.sources, new_source), citations=(*catalog.citations, extra)
    )
    if defect == "over-budget":
      additions[extra.id] = (new_source.id, new_source.lineage_id, quote)
  elif defect == "relineage":
    catalog = replace(
      catalog,
      sources=tuple(
        replace(s, lineage_id="lineage.synthetic-independent") if s.id == template.source_id else s
        for s in catalog.sources
      ),
    )
  else:
    catalog = replace(
      catalog,
      citations=tuple(
        replace(c, quote="改动旧引文") if c.id == "citation.jielan.xiaoxian" else c
        for c in catalog.citations
      ),
    )
  with pytest.raises(AssertionError):
    _check_quote_increment(catalog, additions)


def test_increment_gate_accepts_declared_small_new_source() -> None:
  catalog = load_catalog()
  source = catalog.get("source.jielan-kuxu-tianji")
  citation = catalog.get("citation.jielan.kuxu")
  assert isinstance(source, Source) and isinstance(citation, Citation)
  extra_source = replace(source, id="source.synthetic-declared")
  extra = replace(
    citation, id="citation.synthetic-declared", source_id=extra_source.id, quote="短引"
  )
  catalog = replace(
    catalog, sources=(*catalog.sources, extra_source), citations=(*catalog.citations, extra)
  )
  additions = {**ADDITIONS, extra.id: (extra_source.id, extra_source.lineage_id, extra.quote)}
  _check_quote_increment(catalog, additions)
