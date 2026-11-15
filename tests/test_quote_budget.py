"""现代作品的逐字引文按谱系计总量，计入范围取自完整目录。

谱系归组（同一作品的各家转载并入一条谱系）由整理者判断，本检查只核字数。
同时改动谱系、来源文本层与引文文本层三个字段，可以绕过豁免判断。
"""

from dataclasses import replace

import pytest

from ziwei.knowledge import load_catalog
from ziwei.knowledge.catalog import Catalog
from ziwei.knowledge.model import Source, TextLayer

LIMIT = 90
# 古籍与历书的原文录文不计入。
EXEMPT_LINEAGES = frozenset(
  {
    "lineage.quanshu-wikisource",
    "lineage.jielan-tianji",
    "lineage.pmo-calendar",
    "lineage.yuanhai-changxian",
  }
)
# 规则建立时已超过上限的谱系，以当时总量为上限，只降不升。
HISTORICAL_CAPS = {
  "lineage.zhongzhou-wangtingzhi": 309,
  "lineage.jingcheng-golla": 229,
  "lineage.zhongyi999-paimingpan": 124,
  "lineage.andy-sanfang-sizheng": 111,
}


def quote_totals(catalog: Catalog) -> dict[str, int]:
  sources = {source.id: source for source in catalog.sources}
  totals: dict[str, int] = {}
  for citation in catalog.citations:
    source = sources[citation.source_id]
    if source.lineage_id in EXEMPT_LINEAGES:
      if TextLayer.原文 is not source.layer or TextLayer.原文 is not citation.layer:
        raise ValueError(f"{source.lineage_id}只豁免原文录文，{citation.id}不是原文")
      continue
    totals[source.lineage_id] = totals.get(source.lineage_id, 0) + len(citation.quote)
  return totals


def check_quote_budget(catalog: Catalog) -> None:
  totals = quote_totals(catalog)
  errors = [
    f"{lineage}逐字引文共{total}字，超过上限{HISTORICAL_CAPS.get(lineage, LIMIT)}字；"
    "缩短或删去该谱系的引文"
    for lineage, total in sorted(totals.items())
    if total > HISTORICAL_CAPS.get(lineage, LIMIT)
  ]
  for lineage, cap in HISTORICAL_CAPS.items():
    total = totals.get(lineage, 0)
    if total <= LIMIT:
      errors.append(f"{lineage}已降到{total}字，从HISTORICAL_CAPS移出")
    elif total < cap:
      errors.append(f"{lineage}已降到{total}字，把HISTORICAL_CAPS中的上限同步改为{total}")
  if errors:
    raise ValueError("\n".join(errors))


def with_citation(
  catalog: Catalog,
  source: Source,
  quote: str,
  layer: TextLayer = TextLayer.今人说明,
) -> Catalog:
  template = catalog.citations[0]
  citation = replace(
    template,
    id=f"citation.synthetic-{len(catalog.citations)}",
    source_id=source.id,
    quote=quote,
    layer=layer,
  )
  sources = catalog.sources
  if source not in sources:
    sources = (*sources, source)
  return replace(catalog, sources=sources, citations=(*catalog.citations, citation))


def existing_source(catalog: Catalog, source_id: str) -> Source:
  source = catalog.get(source_id)
  assert isinstance(source, Source)
  return source


def new_source(catalog: Catalog, lineage_id: str, layer: TextLayer = TextLayer.今人说明) -> Source:
  template = existing_source(catalog, "source.click108-liunian")
  return replace(
    template, id=f"source.synthetic-{len(catalog.sources)}", lineage_id=lineage_id, layer=layer
  )


def test_catalog_quotes_stay_within_lineage_limits() -> None:
  check_quote_budget(load_catalog())


@pytest.mark.parametrize(
  ("defect", "reason"),
  [
    ("grow-historical-source", "超过上限229字"),
    ("new-lineage", "超过上限90字"),
    ("join-historical-lineage", "超过上限309字"),
    ("grow-small-lineage", "超过上限90字"),
    ("modern-in-exempt-lineage", "只豁免原文录文"),
    ("relineage-into-exempt", "只豁免原文录文"),
  ],
)
def test_quote_budget_rejects_unaccounted_quotes(defect: str, reason: str) -> None:
  catalog = load_catalog()
  if defect == "grow-historical-source":
    catalog = with_citation(catalog, existing_source(catalog, "source.jingcheng-pdf"), "字" * 500)
  elif defect == "new-lineage":
    catalog = with_citation(catalog, new_source(catalog, "lineage.synthetic"), "字" * 91)
  elif defect == "join-historical-lineage":
    source = new_source(catalog, "lineage.zhongzhou-wangtingzhi")
    catalog = with_citation(catalog, source, "短引")
  elif defect == "grow-small-lineage":
    room = LIMIT - quote_totals(catalog)["lineage.click108-liunian"]
    catalog = with_citation(
      catalog, new_source(catalog, "lineage.click108-liunian"), "字" * (room + 1)
    )
  elif defect == "modern-in-exempt-lineage":
    source = existing_source(catalog, "source.quanshu-wikisource")
    catalog = with_citation(catalog, source, "今人短引", TextLayer.今人说明)
  else:
    catalog = replace(
      catalog,
      sources=tuple(
        replace(s, lineage_id="lineage.quanshu-wikisource") if s.id == "source.jingcheng-pdf" else s
        for s in catalog.sources
      ),
    )
  with pytest.raises(ValueError, match=reason):
    check_quote_budget(catalog)


def test_raising_a_historical_cap_without_new_quotes_is_rejected(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setitem(HISTORICAL_CAPS, "lineage.zhongzhou-wangtingzhi", 400)
  with pytest.raises(ValueError, match="同步改为309"):
    check_quote_budget(load_catalog())


@pytest.mark.parametrize("control", ["short-new-lineage", "exempt-original", "reprint-to-limit"])
def test_quote_budget_accepts_counted_and_exempt_material(control: str) -> None:
  catalog = load_catalog()
  if control == "short-new-lineage":
    catalog = with_citation(catalog, new_source(catalog, "lineage.synthetic"), "字" * LIMIT)
  elif control == "exempt-original":
    source = existing_source(catalog, "source.quanshu-juan1-wikisource")
    catalog = with_citation(catalog, source, "字" * 300, TextLayer.原文)
  else:
    # 同一作品的另一份转载并入原谱系，补到正好90字。
    room = LIMIT - quote_totals(catalog)["lineage.click108-liunian"]
    catalog = with_citation(catalog, new_source(catalog, "lineage.click108-liunian"), "字" * room)
  check_quote_budget(catalog)


@pytest.mark.parametrize(
  ("lineage", "cut"), [("lineage.zhongzhou-wangtingzhi", 1), ("lineage.andy-sanfang-sizheng", 30)]
)
def test_a_shortened_historical_lineage_must_update_its_cap(
  lineage: str, cut: int, monkeypatch: pytest.MonkeyPatch
) -> None:
  catalog = load_catalog()
  longest = max(
    (c for c in catalog.citations if existing_source(catalog, c.source_id).lineage_id == lineage),
    key=lambda citation: len(citation.quote),
  )
  catalog = replace(
    catalog,
    citations=tuple(
      replace(c, quote=c.quote[:-cut]) if c == longest else c for c in catalog.citations
    ),
  )
  reduced = HISTORICAL_CAPS[lineage] - cut
  with pytest.raises(ValueError, match=f"同步改为{reduced}" if reduced > LIMIT else "移出"):
    check_quote_budget(catalog)
  if reduced > LIMIT:
    monkeypatch.setitem(HISTORICAL_CAPS, lineage, reduced)
  else:
    monkeypatch.delitem(HISTORICAL_CAPS, lineage)
  check_quote_budget(catalog)
