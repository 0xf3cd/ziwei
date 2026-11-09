"""外部年度事实、完整表对照与项目组合边界分别验证。"""

import json
import pickle
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from ziwei.birth import Gender, LunarBirthRecord
from ziwei.calendar import LunarAlgorithm
from ziwei.chart import LiunianPalaceView, ZiweiChart, create_chart, liunian_palaces, liunian_view
from ziwei.config import ChartConfig
from ziwei.ganzhi import Dizhi, Tiangan, year_ganzhi
from ziwei.knowledge import load_catalog
from ziwei.knowledge.model import Citation, KnowledgeEntry, RuleVariant, Source, SourceStatus
from ziwei.liunian import (
  LIUNIAN_PALACES_RULE_ID,
  LIUNIAN_SIHUA_RULE_ID,
  LiunianBoundary,
  LiunianSihua,
  liunian_on_date,
  liunian_palace_dizhi,
  liunian_sihua,
  liunian_stars,
)
from ziwei.palaces import PalaceName
from ziwei.sihua import SihuaVariant
from ziwei.stars import Star

pytestmark = pytest.mark.usefixtures("unload_celestial")
REFERENCE = json.loads(
  Path(__file__).with_name("fixtures").joinpath("annual-query-reference.json").read_text("utf-8")
)
VARIANT = SihuaVariant.王亭之讲义转录


@pytest.mark.parametrize("year,expected", REFERENCE["project_palace_matrix"])
def test_twelve_origins_and_twelve_names_have_explicit_project_expectations(
  year: int, expected: str, lunar_chart: ZiweiChart
) -> None:
  assert len(expected) == 12 and set(expected) == {branch.value for branch in Dizhi}
  assert tuple(liunian_palace_dizhi(year, name).value for name in PalaceName) == tuple(expected)
  rows = liunian_palaces(lunar_chart, year)
  assert tuple(row.name for row in rows) == tuple(PalaceName)
  assert tuple(row.dizhi.value for row in rows) == tuple(expected)
  assert all(row.ganzhi_year == year and row.rule_id == LIUNIAN_PALACES_RULE_ID for row in rows)


@pytest.mark.parametrize(
  "year,name,branch", [row for source in REFERENCE["palace_sources"] for row in source["observed"]]
)
def test_external_annual_palace_facts(year: int, name: str, branch: str) -> None:
  assert liunian_palace_dizhi(year, PalaceName[name]) is Dizhi(branch)


@pytest.mark.parametrize("year,observed_stem,stars", REFERENCE["table_source"]["rows"])
def test_complete_named_table_against_jiuqian_column(
  year: int, observed_stem: str, stars: list[str]
) -> None:
  result = liunian_sihua(year, variant=VARIANT)
  assert result.year_tiangan.value == ("己" if observed_stem == "已" else observed_stem)
  assert (result.lu.value, result.quan.value, result.ke.value, result.ji.value) == tuple(stars)
  assert result.year_ganzhi == year_ganzhi(year)
  assert result.variant is VARIANT
  assert result.table_id == VARIANT.rule_id
  assert result.rule_id == LIUNIAN_SIHUA_RULE_ID != result.table_id


@pytest.mark.parametrize(
  "year,mark,star",
  [row for source in REFERENCE["annual_sihua_sources"] for row in source["observed"]],
)
def test_external_annual_marks_are_not_full_table_evidence(year: int, mark: str, star: str) -> None:
  assert getattr(liunian_sihua(year, variant=VARIANT), mark) is Star(star)


@pytest.mark.parametrize("year", [1, 9999])
def test_pure_query_range_endpoints(year: int) -> None:
  assert liunian_palace_dizhi(year, PalaceName.命宫) is year_ganzhi(year).dizhi
  result = liunian_sihua(year, variant=VARIANT)
  assert result.ganzhi_year == year and result.year_tiangan is year_ganzhi(year).tiangan


@pytest.mark.parametrize("value", [True, False, 2025.0, "2025", None])
def test_annual_queries_reject_year_coercion(value: Any, lunar_chart: ZiweiChart) -> None:
  with pytest.raises(TypeError):
    liunian_palace_dizhi(value, PalaceName.命宫)
  with pytest.raises(TypeError):
    liunian_sihua(value, variant=VARIANT)
  with pytest.raises(TypeError):
    liunian_palaces(lunar_chart, value)


@pytest.mark.parametrize("value", [0, -1, 10000])
def test_annual_queries_reject_year_outside_range(value: int, lunar_chart: ZiweiChart) -> None:
  with pytest.raises(ValueError):
    liunian_palace_dizhi(value, PalaceName.命宫)
  with pytest.raises(ValueError):
    LiunianSihua(value, variant=VARIANT)
  with pytest.raises(ValueError):
    liunian_palaces(lunar_chart, value, sihua_variant=VARIANT)


@pytest.mark.parametrize("value", ["命宫", Dizhi.巳, True, None])
def test_palace_lookup_requires_the_palace_name_enum(value: Any) -> None:
  with pytest.raises(TypeError):
    liunian_palace_dizhi(2025, value)


@pytest.mark.parametrize("value", ["王亭之讲义转录", True, 0, Tiangan.乙, None])
def test_annual_table_choice_rejects_wrong_types(value: Any, lunar_chart: ZiweiChart) -> None:
  with pytest.raises(TypeError):
    liunian_sihua(2025, variant=value)
  if value is not None:
    with pytest.raises(TypeError):
      liunian_palaces(lunar_chart, 2025, sihua_variant=value)


def test_annual_table_is_required_and_unavailable_variant_never_falls_back(
  lunar_chart: ZiweiChart,
) -> None:
  with pytest.raises(TypeError):
    liunian_sihua(2025)  # type: ignore[call-arg]
  with pytest.raises(TypeError):
    LiunianSihua(2025)  # type: ignore[call-arg]
  for year in (2025, 2030):
    with pytest.raises(ValueError, match="年度"):
      liunian_sihua(year, variant=SihuaVariant.排命盘口诀转录)
    with pytest.raises(ValueError, match="年度"):
      liunian_palaces(lunar_chart, year, sihua_variant=SihuaVariant.排命盘口诀转录)


def test_derived_fields_cannot_be_forged_at_construction() -> None:
  with pytest.raises(TypeError):
    LiunianSihua(2025, variant=VARIANT, lu=Star.天府)  # type: ignore[call-arg]
  result = LiunianSihua(2025, variant=VARIANT)
  with pytest.raises((TypeError, ValueError), match="init=False"):
    replace(result, lu=Star.天府)
  following = replace(result, ganzhi_year=2026)
  assert following.year_tiangan is Tiangan.丙 and following.lu is Star.天同
  assert result.lu is Star.天机
  with pytest.raises(FrozenInstanceError):
    result.variant = SihuaVariant.排命盘口诀转录  # type: ignore[misc]
  assert pickle.loads(pickle.dumps(result)) == result


def test_palace_only_reading_does_not_choose_the_birth_table(lunar_chart: ZiweiChart) -> None:
  assert lunar_chart.sihua.variant is SihuaVariant.排命盘口诀转录
  omitted = liunian_palaces(lunar_chart, 2030)
  assert omitted == liunian_palaces(lunar_chart, 2030, sihua_variant=None)
  assert all(
    row.sihua is None and (row.lu, row.quan, row.ke, row.ji) == (None,) * 4 for row in omitted
  )
  selected = liunian_palaces(lunar_chart, 2030, sihua_variant=VARIANT)
  assert selected[0].sihua is not None
  assert selected[0].sihua.ke is Star.天府 and selected[0].sihua.ji is Star.天同


@pytest.mark.parametrize("year", [2025, 2028, 2030, 2032])
def test_all_natal_content_and_annual_marks_are_preserved_separately(
  lunar_chart: ZiweiChart, year: int
) -> None:
  before = pickle.dumps(lunar_chart)
  rows = liunian_palaces(lunar_chart, year, sihua_variant=VARIANT)
  assert len(rows) == len({row.name for row in rows}) == len({row.dizhi for row in rows}) == 12
  positions = tuple(position for row in rows for position in row.natal.stars)
  assert len(positions) == len(lunar_chart.stars) == 30
  assert {p.star: p for p in positions} == {p.star: p for p in lunar_chart.stars}
  assert all(any(p is original for original in lunar_chart.stars) for p in positions)
  assert sum(row.natal.is_shengong for row in rows) == 1
  annual = liunian_sihua(year, variant=VARIANT)
  for mark in ("lu", "quan", "ke", "ji"):
    observed_annual = [getattr(row, mark) for row in rows if getattr(row, mark) is not None]
    observed_natal = [
      getattr(row.natal, mark) for row in rows if getattr(row.natal, mark) is not None
    ]
    assert observed_annual == [getattr(annual, mark)]
    assert observed_natal == [getattr(lunar_chart.sihua, mark)]
  assert all(row.sihua is rows[0].sihua for row in rows)
  same_origin = rows[0].dizhi is lunar_chart.palaces[0].dizhi
  assert all((row.name is row.natal.palace.name) == same_origin for row in rows)
  assert pickle.dumps(lunar_chart) == before


def test_same_star_can_have_different_birth_and_annual_marks(lunar_chart: ZiweiChart) -> None:
  assert lunar_chart.sihua.ji is Star.太阳
  rows = liunian_palaces(lunar_chart, 2028, sihua_variant=VARIANT)
  sun = next(row for row in rows if row.ke is Star.太阳)
  assert sun.natal.ji is Star.太阳 and sun.ke is Star.太阳
  assert sun.ji is not Star.太阳
  assert sun.sihua is not None and sun.sihua.year_tiangan is Tiangan.戊


def test_different_births_share_the_year_not_the_natal_placements(
  lunar_chart: ZiweiChart, chart_choices: ChartConfig
) -> None:
  other = create_chart(
    LunarBirthRecord(
      year=1985, month=2, day=10, is_leap_month=False, shichen=Dizhi.卯, gender=Gender.女
    ),
    chart_choices,
    sihua_variant=VARIANT,
  )
  assert other.calculation.year_ganzhi.tiangan is not lunar_chart.calculation.year_ganzhi.tiangan
  left = liunian_palaces(lunar_chart, 2030, sihua_variant=VARIANT)
  right = liunian_palaces(other, 2030, sihua_variant=VARIANT)
  assert tuple((row.name, row.dizhi, row.sihua) for row in left) == tuple(
    (row.name, row.dizhi, row.sihua) for row in right
  )
  assert tuple(row.natal for row in left) != tuple(row.natal for row in right)
  for rows, chart in ((left, lunar_chart), (right, other)):
    assert rows[0].sihua is not None and rows[0].sihua.year_tiangan is Tiangan.庚
    assert rows[0].sihua.ke is Star.天府
    assert {row.dizhi: row.natal.palace for row in rows} == {p.dizhi: p for p in chart.palaces}


def test_dates_use_the_explicit_annual_boundary(lunar_chart: ZiweiChart) -> None:
  lunar = liunian_on_date(
    date(2024, 2, 4), boundary=LiunianBoundary.正月初一日期, lunar_algorithm=LunarAlgorithm.混合
  )
  solar = liunian_on_date(date(2024, 2, 4), boundary=LiunianBoundary.立春日期)
  first = liunian_palaces(lunar_chart, lunar.ganzhi_year, sihua_variant=VARIANT)
  second = liunian_palaces(lunar_chart, solar.ganzhi_year, sihua_variant=VARIANT)
  assert (first[0].dizhi, second[0].dizhi) == (Dizhi.卯, Dizhi.辰)
  assert first[0].sihua is not None and second[0].sihua is not None
  assert (first[0].sihua.year_tiangan, second[0].sihua.year_tiangan) == (Tiangan.癸, Tiangan.甲)


def test_direct_palace_view_rejects_contradictions(lunar_chart: ZiweiChart) -> None:
  row, *rest = liunian_palaces(lunar_chart, 2025, sihua_variant=VARIANT)
  assert pickle.loads(pickle.dumps(row)) == row
  with pytest.raises(ValueError, match="落支"):
    replace(row, natal=rest[0].natal)
  with pytest.raises(ValueError, match="同一纪年"):
    replace(row, sihua=liunian_sihua(2024, variant=VARIANT))
  with pytest.raises(TypeError):
    replace(row, name="命宫")  # type: ignore[arg-type]
  with pytest.raises(TypeError):
    replace(row, natal=None)  # type: ignore[arg-type]
  with pytest.raises(TypeError):
    replace(row, sihua=lunar_chart.sihua)  # type: ignore[arg-type]
  with pytest.raises(FrozenInstanceError):
    row.name = PalaceName.夫妻  # type: ignore[misc]
  with pytest.raises(TypeError):
    LiunianPalaceView(2025, row.name, row.natal)  # type: ignore[call-arg]


@pytest.mark.parametrize("chart", [None, {}, True])
def test_full_annual_reading_requires_a_chart(chart: Any) -> None:
  with pytest.raises(TypeError):
    liunian_palaces(chart, 2025)


def test_old_one_palace_view_and_annual_lucun_remain_separate(lunar_chart: ZiweiChart) -> None:
  old = liunian_view(lunar_chart, 2025)
  first = liunian_palaces(lunar_chart, 2025, sihua_variant=VARIANT)[0]
  assert old.natal == first.natal
  assert old.liunian == liunian_stars(2025)
  assert old.liunian.lucun is Dizhi.卯
  assert first.sihua is not None and first.sihua.lu is Star.天机


def test_pure_annual_queries_do_not_import_birth_or_calendar() -> None:
  script = """
import sys
from ziwei.liunian import liunian_sihua, liunian_palace_dizhi
from ziwei.palaces import PalaceName
from ziwei.sihua import SihuaVariant
from ziwei.knowledge import load_catalog
assert liunian_sihua(2030, variant=SihuaVariant.王亭之讲义转录).ke.value == '天府'
assert liunian_palace_dizhi(2025, PalaceName.夫妻).value == '卯'
assert load_catalog().get('entry.liunian.twelve-palaces').show_by_default is False
assert 'ziwei.birth' not in sys.modules and 'ziwei.calendar' not in sys.modules
assert not any(name.startswith('celestial_calendar') for name in sys.modules)
"""
  result = subprocess.run([sys.executable, "-I", "-c", script], capture_output=True, text=True)
  assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
  "rule_id,entry_id,implementation",
  [
    (LIUNIAN_PALACES_RULE_ID, "entry.liunian.twelve-palaces", "ziwei.liunian.liunian_palace_dizhi"),
    (
      LIUNIAN_SIHUA_RULE_ID,
      "entry.liunian.sihua-wangtingzhi-lecture",
      "ziwei.liunian.liunian_sihua",
    ),
  ],
)
def test_annual_rules_have_separate_knowledge_and_reproducible_sources(
  rule_id: str, entry_id: str, implementation: str
) -> None:
  catalog = load_catalog()
  rule, entry = catalog.get(rule_id), catalog.get(entry_id)
  assert isinstance(rule, RuleVariant) and rule.implementation == implementation
  assert isinstance(entry, KnowledgeEntry) and entry.variant_ids == (rule_id,)
  assert entry.show_by_default is False and entry.recheck
  references = catalog.references(rule_id)
  assert len(references) >= 7
  for citation in references:
    source = catalog.get(citation.source_id)
    assert isinstance(source, Source)
    assert source.status is SourceStatus.待核
  assert catalog.get(VARIANT.rule_id).id != rule.id


def test_new_annual_quotes_keep_original_characters_and_anchor_sentences() -> None:
  catalog = load_catalog()
  quotes = {
    "citation.zhongzhou.md-sihua-wu-ji": "戊贪阴阳机，己武贪梁贡，",
    "citation.zhongzhou.md-sihua-geng-ren": "庚阳武府同，辛巨阳曲昌，\n壬梁紫府武，癸破巨阴贪",
    "citation.zhongzhou.md-flow-sihua-method": "流四化的起法与起星盘的方法相同",
    "citation.zhongzhou.md-liunian-stem": "流曜则仍依年干起，不用宫干。",
    "citation.zhongzhou.md-liunian-palaces": (
      "以流年太岁宫作为本年的命宫，按兄弟，夫妻等十二宫逆行安排"
    ),
    "citation.zhongzhou.year-1978-palace": "流年夫妻宮(壬辰宮)",
    "citation.zhongzhou.year-1975-minggong": "流年命宮在卯垣",
    "citation.zhongzhou.year-1975-palace": "流年疾厄宮飛至戌垣",
    "citation.zhongzhou.year-1978-sihua": ("在一九七八年戊午，流年命宮及流年夫妻宮同會貪狼化祿"),
    "citation.zhongzhou.year-1980-sihua": ("一九八零庚申年，命宮為武曲(大限化科、流年化權)"),
    "citation.zhongzhou.year-1981-sihua": "會丑宮文曲(流年化科)及文昌(流年化忌)",
    "citation.108s.year-2025-minggong": "2025年都在命盤的巳位",
    "citation.108s.year-2025-palaces": "2025年的流年祿存在卯位，坐流年夫妻宮",
    "citation.108s.year-2025-sihua": "天機化祿",
    "citation.iluck.sihua-year-stem": "须以流年岁次的年干作为条件，查表得出。",
    "citation.jingcheng.liunian-palaces": ("也是把小限、流年落宫当作命宫再逆布人事十二宫"),
  }
  assert len(quotes) == 16
  annual_refs = {citation.id: citation for citation in catalog.references(LIUNIAN_PALACES_RULE_ID)}
  for identifier, quote in quotes.items():
    record = catalog.get(identifier)
    assert isinstance(record, Citation) and record.quote == quote
    if identifier.endswith("minggong"):
      assert identifier in annual_refs
  entry = catalog.get("entry.liunian.sihua-wangtingzhi-lecture")
  assert isinstance(entry, KnowledgeEntry) and "年度直接例" in entry.limits
