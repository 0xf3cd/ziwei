"""《捷览》两条年支直接例、口诀十二支展开与合成集成分别验收，不称完整外部盘。"""

from dataclasses import replace
from datetime import date, time, timedelta
from typing import Any
from xml.etree.ElementTree import fromstring

import pytest

from tools.knowledge_reference import _star_rows
from ziwei.birth import Gender, GregorianBirthRecord, LunarBirthRecord, TimePrecision
from ziwei.chart import create_chart, palace_view
from ziwei.config import ChartConfig, TianmaRule, YearBoundary
from ziwei.ganzhi import Dizhi, Ganzhi, Tiangan
from ziwei.knowledge import load_catalog
from ziwei.knowledge.model import (
  Citation,
  KnowledgeEntry,
  RuleVariant,
  Source,
  SourceStatus,
  TextLayer,
)
from ziwei.render import render_svg, render_text
from ziwei.sihua import SihuaVariant
from ziwei.stars import Star, place_hongluan_tianxi, place_stars
from ziwei.timezone import FixedOffset

RULE_ID = "variant.star.hongluan-tianxi-year-branch"
YEAR_PAIRS = (
  "卯酉",
  "寅申",
  "丑未",
  "子午",
  "亥巳",
  "戌辰",
  "酉卯",
  "申寅",
  "未丑",
  "午子",
  "巳亥",
  "辰戌",
)
JIELAN_SOURCE = {
  "source_id": "source.jielan-tianji",
  "url": "https://tianjihq.com/zh-CN/learn/books/ziwei-jielan/29",
  "locator": "卷之一，第29章安红鸾天喜星诀，甲子及乙丑例",
  "retrieved_at_utc": "2026-10-27T23:20:25.410133+00:00",
  "snapshot_sha256": "5c5a922f716d6372eb9755e6031e19dcfe0af87ad334b663fcacf819234c0c16",
  "observed_text": "假如甲子年生人，即在 卯宫安红鸾，酉宫安天喜。如乙丑年生人，则逆行寅宫安红鸾，申宫安天喜，余仿此。",
  "configuration": "只提供生年干支；完整出生年月日时、历法与时区配置、换年界线、其他星曜位置未提供。",
  "comparison": "只对齐年支定位规则，不声称完整排盘配置已对齐；未提供不作空值或差异。",
  "lineage_limit": "同章另引《全书》；不作两条独立传承。纸本版次及录文忠实度未核。",
}
# 各行依次为原文生年、外部观测与项目采用预期，分开保存，不按来源多数生成预期。
JIELAN_CASES = (
  ("甲子", {"红鸾": "卯", "天喜": "酉"}, {"红鸾": "卯", "天喜": "酉"}),
  ("乙丑", {"红鸾": "寅", "天喜": "申"}, {"红鸾": "寅", "天喜": "申"}),
)


@pytest.mark.parametrize("year,expected", list(zip(tuple(Dizhi), YEAR_PAIRS, strict=True)))
def test_twelve_branches_expanded_from_quanshu(year: Dizhi, expected: str) -> None:
  """按《全书》卯起子年逆数、对宫天喜展开；除子丑两例外，不冒称来源逐格列出。"""
  positions = place_hongluan_tianxi(year)
  assert tuple(p.star for p in positions) == (Star.红鸾, Star.天喜)
  assert tuple(p.dizhi for p in positions) == tuple(Dizhi(value) for value in expected)
  assert tuple(p.rule_id for p in positions) == (RULE_ID, RULE_ID)


def test_reference_has_both_stars_for_all_twelve_branches() -> None:
  rows = [row for row in _star_rows() if row[0] == RULE_ID and row[1] != "规则"]
  assert len(rows) == 24
  assert set(rows) == {
    (RULE_ID, year.value, star, branch)
    for year, pair in zip(tuple(Dizhi), YEAR_PAIRS, strict=True)
    for star, branch in zip(("红鸾", "天喜"), pair, strict=True)
  }


@pytest.mark.parametrize("invalid", [None, True, 0, "子", Tiangan.甲, Star.红鸾])
def test_year_branch_is_not_coerced(invalid: Any) -> None:
  with pytest.raises(TypeError, match="生年支须为 Dizhi 成员"):
    place_hongluan_tianxi(invalid)


def test_frozen_jielan_direct_observations_and_adopted_expectations() -> None:
  catalog = load_catalog()
  source = catalog.get(JIELAN_SOURCE["source_id"])
  assert isinstance(source, Source) and source.status is SourceStatus.已核
  assert source.url == JIELAN_SOURCE["url"] and JIELAN_SOURCE["snapshot_sha256"] in source.edition
  assert source.checked_on == date.fromisoformat(JIELAN_SOURCE["retrieved_at_utc"][:10])
  assert source.lineage_id == "lineage.jielan-tianji" and source.layer is TextLayer.原文
  assert "甲子、乙丑两条直接例" in source.claims
  assert "未载换年界线" in source.limits and "没有完整生辰盘例" in source.limits
  assert "不作互不知晓的独立传承" in source.provenance
  citation = catalog.get("citation.jielan.hongluan-tianxi-examples")
  assert isinstance(citation, Citation) and citation.quote == JIELAN_SOURCE["observed_text"]
  assert JIELAN_SOURCE["locator"] in citation.locator
  assert "Article.description" in citation.locator
  for year, external_observation, adopted_expected in JIELAN_CASES:
    assert external_observation == adopted_expected
    branch = Ganzhi.from_str(year).dizhi
    actual = {p.star.value: p.dizhi.value for p in place_hongluan_tianxi(branch)}
    assert actual == adopted_expected


def test_quanshu_hongluan_tianxi_quote_preserves_original_text() -> None:
  citation = load_catalog().get("citation.quanshu.hongluan-tianxi")
  assert isinstance(citation, Citation)
  assert citation.source_id == "source.quanshu-wikisource"
  assert citation.quote == "卯上起子逆数之，数到当生太岁支，坐守此宫红鸾位，对宫天喜不差移，"
  assert citation.layer is TextLayer.原文
  assert "安红鸾天喜诀前四句" in citation.locator
  assert "不收后四句吉凶" in citation.limits and "不据此另定换年界线" in citation.limits


def test_hongluan_tianxi_knowledge_keeps_source_and_year_boundary_limits() -> None:
  catalog = load_catalog()
  variant = catalog.get(RULE_ID)
  entry = catalog.get("entry.star.hongluan-tianxi-year-branch")
  assert isinstance(variant, RuleVariant) and isinstance(entry, KnowledgeEntry)
  assert variant.definition == entry.statement == "卯宫起子年，逆数到生年支安红鸾，红鸾对宫安天喜。"
  assert variant.implementation == "ziwei.stars.place_hongluan_tianxi"
  assert variant.concept_ids == ("concept.star.hongluan", "concept.star.tianxi")
  assert variant.tracking_url == entry.tracking_url == "https://github.com/0xf3cd/ziwei/issues/54"
  assert [citation.source_id for citation in catalog.references(entry.id)] == [
    "source.quanshu-wikisource",
    "source.jielan-tianji",
  ]
  assert "本命" in entry.premises[0] and "不另设年界" in entry.premises[1]
  assert "独立传承" in entry.limits and "完整生辰外部盘例未取得" in entry.limits
  assert "捷览" in entry.recheck and "中州" not in entry.recheck
  assert catalog.find("紅鸞")[0].id == Star.红鸾.concept_id


@pytest.mark.usefixtures("unload_celestial")
@pytest.mark.parametrize("horse", tuple(TianmaRule))
@pytest.mark.parametrize(
  "boundary,year,expected",
  [(YearBoundary.农历正月初一, "癸卯", "子午"), (YearBoundary.立春, "甲辰", "亥巳")],
)
def test_resolved_year_boundary_is_consumed_without_a_two_star_boundary(
  chart_choices: ChartConfig, horse: TianmaRule, boundary: YearBoundary, year: str, expected: str
) -> None:
  """2024立春与正月初一之间的合成输入；不是外部完整生辰盘。"""
  record = GregorianBirthRecord(
    birth_date=date(2024, 2, 5),
    birth_time=time(12),
    time_precision=TimePrecision.分,
    timezone=FixedOffset(timedelta(hours=8)),
    gender=Gender.女,
  )
  chart = create_chart(
    record,
    replace(chart_choices, year_boundary=boundary, tianma_rule=horse),
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  assert chart.calculation.lunar_year == 2023
  assert str(chart.calculation.year_ganzhi) == year
  assert tuple(p.dizhi.value for p in chart.stars if p.star in (Star.红鸾, Star.天喜)) == tuple(
    expected
  )
  assert place_stars(chart.calculation) == chart.stars


@pytest.mark.usefixtures("unload_celestial")
def test_two_stars_reach_complete_chart_palace_queries_and_both_displays(
  chart_choices: ChartConfig,
) -> None:
  """合成乙丑正月初一子时，只借直接年支例的两星位置，不称外部完整盘验证。"""
  chart = create_chart(
    LunarBirthRecord(
      year=1985, month=1, day=1, is_leap_month=False, shichen=Dizhi.子, gender=Gender.女
    ),
    chart_choices,
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  assert len(chart.stars) == len({p.star for p in chart.stars}) == len(Star)
  assert {p.star for p in chart.stars} == set(Star)
  text = render_text(chart)
  root = fromstring(render_svg(chart))
  namespace = "{http://www.w3.org/2000/svg}"
  for star, branch in ((Star.红鸾, Dizhi.寅), (Star.天喜, Dizhi.申)):
    placement = next(p for p in chart.stars if p.star is star)
    assert placement.dizhi is branch and placement.rule_id == RULE_ID
    assert any(p is placement for p in palace_view(chart, branch).stars)
    assert text.count(star.value) == 1
    cell = root.find(f"{namespace}g[@data-dizhi='{branch.name.lower()}']")
    assert cell is not None
    assert [node.text for node in cell if node.get("class") == "star"].count(star.value) == 1
