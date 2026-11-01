"""年度直接例、外部十干表与合成本命叠读分别检验。"""

import json
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from ziwei.birth import Gender, LunarBirthRecord
from ziwei.calendar import LunarAlgorithm
from ziwei.chart import LiunianView, ZiweiChart, create_chart, liunian_view, palace_view
from ziwei.config import ChartConfig
from ziwei.ganzhi import Dizhi, Tiangan, year_ganzhi
from ziwei.knowledge import load_catalog
from ziwei.knowledge.model import Citation, KnowledgeEntry, RuleVariant, Source, SourceStatus
from ziwei.liunian import (
  LIUNIAN_STARS_DEFINITION,
  LIUNIAN_STARS_RULE_ID,
  LiunianBoundary,
  LiunianStars,
  liunian_on_date,
  liunian_stars,
)
from ziwei.palaces import PalaceName
from ziwei.sihua import SihuaVariant
from ziwei.stars import STAR_RULES, Star, StarPlacement, lucun_yangtuo_dizhi, place_stem_stars

REFERENCE = json.loads(
  Path(__file__).with_name("fixtures").joinpath("liunian-stars-reference.json").read_text()
)


@pytest.mark.parametrize("year", range(2024, 2034))
def test_external_ten_stem_table_and_natal_compatibility(year: int) -> None:
  reading = liunian_stars(year)
  stem = year_ganzhi(year).tiangan
  expected = tuple(Dizhi(value) for value in REFERENCE["table"][stem.value])
  assert reading.ganzhi_year == year and reading.year_ganzhi == year_ganzhi(year)
  assert (reading.lucun, reading.qingyang, reading.tuoluo) == expected
  assert lucun_yangtuo_dizhi(stem) == expected
  natal = place_stem_stars(stem)
  assert tuple(p.star for p in natal) == (Star.天魁, Star.天钺, Star.禄存, Star.擎羊, Star.陀罗)
  assert tuple(p.dizhi for p in natal[2:]) == expected
  assert tuple(p.rule_id for p in natal[2:]) == (
    "variant.star.lucun-stem",
    "variant.star.yangtuo-lucun",
    "variant.star.yangtuo-lucun",
  )
  assert reading.rule_id == LIUNIAN_STARS_RULE_ID
  assert all(rule.id != reading.rule_id for rule in STAR_RULES)
  with pytest.raises(ValueError):
    StarPlacement(Star.禄存, reading.lucun, reading.rule_id)


@pytest.mark.parametrize("example", REFERENCE["direct_examples"])
def test_direct_examples_keep_source_ganzhi_separate_from_project_year(
  example: dict[str, Any],
) -> None:
  year = example["project_ganzhi_year"]
  assert str(year_ganzhi(year)) == example["ganzhi"]
  result = liunian_stars(year)
  assert [result.lucun.value, result.qingyang.value, result.tuoluo.value] == example["positions"]
  assert example["year_note"]


@pytest.mark.parametrize("invalid", [True, False, 2024.0, "2024", None, Tiangan.甲])
def test_annual_year_rejects_coercion_in_factory_and_constructor(invalid: Any) -> None:
  for constructor in (liunian_stars, LiunianStars):
    with pytest.raises(TypeError):
      constructor(invalid)


@pytest.mark.parametrize("invalid", [0, -1, 10000])
def test_annual_year_rejects_out_of_range(invalid: int) -> None:
  for constructor in (liunian_stars, LiunianStars):
    with pytest.raises(ValueError):
      constructor(invalid)


@pytest.mark.parametrize("year", [1, 9999])
def test_annual_year_endpoints(year: int) -> None:
  result = liunian_stars(year)
  assert [result.lucun.value, result.qingyang.value, result.tuoluo.value] == REFERENCE["table"][
    year_ganzhi(year).tiangan.value
  ]


@pytest.mark.parametrize("invalid", ["甲", Dizhi.子, True, 0, None])
def test_shared_relation_requires_typed_stem(invalid: Any) -> None:
  with pytest.raises(TypeError):
    lucun_yangtuo_dizhi(invalid)


def test_reading_is_frozen_and_positions_cannot_be_supplied() -> None:
  result = liunian_stars(2012)
  assert result.qingyang is Dizhi.子
  assert liunian_stars(2013).tuoluo is Dizhi.亥
  with pytest.raises(FrozenInstanceError):
    result.ganzhi_year = 2013  # type: ignore[misc]
  with pytest.raises(TypeError):
    LiunianStars(2012, lucun=Dizhi.子)  # type: ignore[call-arg]
  assert replace(result, ganzhi_year=2013) == liunian_stars(2013)


@pytest.mark.parametrize("month", range(1, 13))
def test_twelve_natal_minggong_and_twelve_target_branches(
  chart_choices: ChartConfig,
  month: int,
) -> None:
  chart = create_chart(
    LunarBirthRecord(
      year=2024, month=month, day=1, is_leap_month=False, shichen=Dizhi.子, gender=Gender.女
    ),
    chart_choices,
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  assert chart.palaces[0].dizhi is tuple(Dizhi)[(month + 1) % 12]
  original = (chart.calculation, chart.palaces, chart.stars, chart.sihua, chart.decades)
  for year, branch in zip(range(2020, 2032), Dizhi, strict=True):
    view = liunian_view(chart, year)
    assert view.liunian == liunian_stars(year)
    expected_palace = next(p for p in chart.palaces if p.dizhi is branch)
    assert view.natal.palace is expected_palace
    assert view.natal.stars == tuple(p for p in chart.stars if p.dizhi is branch)
    assert all(any(p is original for original in chart.stars) for p in view.natal.stars)
    assert view.natal == palace_view(chart, branch)
    assert view.natal.is_shengong is (branch is chart.shengong)
    for name in ("lu", "quan", "ke", "ji"):
      star = getattr(chart.sihua, name)
      assert getattr(view.natal, name) is (
        star if any(p.star is star for p in view.natal.stars) else None
      )
  assert original == (chart.calculation, chart.palaces, chart.stars, chart.sihua, chart.decades)


def test_overlay_uses_annual_not_birth_stem_and_keeps_natal_name(lunar_chart: ZiweiChart) -> None:
  view = liunian_view(lunar_chart, 2025)
  assert lunar_chart.calculation.year_ganzhi.tiangan is Tiangan.甲
  assert view.liunian.year_ganzhi.tiangan is Tiangan.乙
  assert (view.liunian.lucun, view.liunian.qingyang, view.liunian.tuoluo) == (
    Dizhi.卯,
    Dizhi.辰,
    Dizhi.寅,
  )
  assert view.natal.palace.dizhi is Dizhi.巳 and view.natal.palace.name is PalaceName.疾厄
  assert liunian_view(lunar_chart, 1954).liunian.lucun is next(
    p.dizhi for p in lunar_chart.stars if p.star is Star.禄存
  )
  with pytest.raises(FrozenInstanceError):
    view.natal = palace_view(lunar_chart, Dizhi.子)  # type: ignore[misc]
  with pytest.raises(ValueError, match="本命宫支"):
    replace(view, natal=palace_view(lunar_chart, Dizhi.子))


@pytest.mark.parametrize("invalid", [None, True, "chart"])
def test_overlay_rejects_invalid_chart_and_component_types(
  lunar_chart: ZiweiChart,
  invalid: Any,
) -> None:
  with pytest.raises(TypeError):
    liunian_view(invalid, 2025)
  with pytest.raises(TypeError):
    LiunianView(liunian=invalid, natal=palace_view(lunar_chart, Dizhi.巳))
  with pytest.raises(TypeError):
    LiunianView(liunian=liunian_stars(2025), natal=invalid)


def test_date_boundary_result_selects_the_annual_stem(lunar_chart: ZiweiChart) -> None:
  lunar = liunian_on_date(
    date(2024, 2, 4), boundary=LiunianBoundary.正月初一日期, lunar_algorithm=LunarAlgorithm.混合
  )
  solar = liunian_on_date(date(2024, 2, 4), boundary=LiunianBoundary.立春日期)
  assert (lunar.ganzhi_year, solar.ganzhi_year) == (2023, 2024)
  for year, expected in (
    (lunar, (Dizhi.子, Dizhi.丑, Dizhi.亥)),
    (solar, (Dizhi.寅, Dizhi.卯, Dizhi.丑)),
  ):
    view = liunian_view(lunar_chart, year.ganzhi_year)
    assert (view.liunian.lucun, view.liunian.qingyang, view.liunian.tuoluo) == expected
    assert view.natal.palace.dizhi is year.minggong


def test_annual_rule_and_aliases_are_reachable_from_existing_star_concepts() -> None:
  catalog = load_catalog()
  variant = catalog.get(LIUNIAN_STARS_RULE_ID)
  assert isinstance(variant, RuleVariant) and variant.definition == LIUNIAN_STARS_DEFINITION
  for name in ("流禄", "流祿", "流羊", "流陀"):
    assert catalog.find(name) == (variant,)
  for star in (Star.禄存, Star.擎羊, Star.陀罗):
    assert variant in catalog.list_variants(concept_id=star.concept_id)
  entry = catalog.get("entry.liunian.lucun-yangtuo")
  assert isinstance(entry, KnowledgeEntry) and not entry.show_by_default
  assert entry.statement == variant.definition and entry.recheck
  for identifier, source in (("source.jingcheng-chapter10", "source.jingcheng-golla"),):
    new, old = catalog.get(identifier), catalog.get(source)
    assert isinstance(new, Source) and isinstance(old, Source)
    assert new.lineage_id == old.lineage_id and new.status is SourceStatus.待核
  for example in REFERENCE["direct_examples"]:
    assert any(c.quote == example["quote"] for c in catalog.references(variant.id))
  citation = catalog.get("citation.jingcheng.liunian-stem-method")
  assert isinstance(citation, Citation)
  assert citation.quote == (
    "均可依大限、流年、流月、流日、流时的天干为准来推查，查法和原命盘推查方法一样。"
  )


def test_pure_annual_query_and_knowledge_do_not_import_calendar() -> None:
  script = """
import sys
from ziwei.liunian import LiunianStars, liunian_stars
from ziwei.knowledge import load_catalog
if LiunianStars(2012) != liunian_stars(2012):
  raise ValueError('annual query differs')
load_catalog()
for prefix in ('ziwei.calendar', 'ziwei.birth', 'ziwei.timezone', 'celestial_calendar', 'tzdata'):
  if any(n == prefix or n.startswith(prefix + '.') for n in sys.modules):
    raise ValueError('unexpected dependency: ' + prefix)
"""
  result = subprocess.run((sys.executable, "-I", "-c", script), capture_output=True, text=True)
  assert result.returncode == 0, result.stdout + result.stderr
