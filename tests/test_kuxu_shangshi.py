"""哭虚外表、固定伤使与完整盘消费分别验收。"""

from dataclasses import replace
from datetime import date, time, timedelta
from typing import Any
from xml.etree.ElementTree import fromstring

import pytest

from tools.knowledge_reference import _star_rows
from ziwei.birth import Gender, GregorianBirthRecord, LunarBirthRecord, TimePrecision
from ziwei.brightness import BrightnessTable
from ziwei.chart import chart_brightness, create_chart, liunian_palaces, palace_view
from ziwei.config import ChartConfig, YearBoundary
from ziwei.ganzhi import Dizhi
from ziwei.knowledge import load_catalog
from ziwei.knowledge.model import KnowledgeEntry, RuleVariant
from ziwei.render import render_svg, render_text
from ziwei.resolver import resolve
from ziwei.sihua import SihuaVariant
from ziwei.stars import (
  STAR_RULES,
  Star,
  StarPlacement,
  place_stars,
  place_tianku_tianxu,
  place_tianshang_tianshi,
)
from ziwei.timezone import FixedOffset

KU_XU = "variant.star.tianku-tianxu-year-branch"
SHANG_SHI = "variant.star.tianshang-tianshi-fixed"
# iLuck《年支星系》表的子至亥十二行，次序为哭、虚；不由本库公式生成。
YEAR_PAIRS = (
  "午午",
  "巳未",
  "辰申",
  "卯酉",
  "寅戌",
  "丑亥",
  "子子",
  "亥丑",
  "戌寅",
  "酉卯",
  "申辰",
  "未巳",
)
# 十二宫逆排的字面期望，次序为奴仆天伤、疾厄天使；巳命另有iLuck阳女直接例。
PALACE_PAIRS = (
  "巳未",
  "午申",
  "未酉",
  "申戌",
  "酉亥",
  "戌子",
  "亥丑",
  "子寅",
  "丑卯",
  "寅辰",
  "卯巳",
  "辰午",
)


@pytest.mark.parametrize("branch,pair", tuple(zip(Dizhi, YEAR_PAIRS, strict=True)))
def test_kuxu_external_year_table(branch: Dizhi, pair: str) -> None:
  positions = place_tianku_tianxu(branch)
  assert tuple(p.star for p in positions) == (Star.天哭, Star.天虚)
  assert "".join(p.dizhi.value for p in positions) == pair
  assert all(p.rule_id == KU_XU for p in positions)
  for p in positions:
    assert (KU_XU, branch.value, p.star.value, p.dizhi.value) in _star_rows()


@pytest.mark.parametrize("minggong,pair", tuple(zip(Dizhi, PALACE_PAIRS, strict=True)))
def test_fixed_shangshi_all_palaces(minggong: Dizhi, pair: str) -> None:
  positions = place_tianshang_tianshi(minggong)
  assert tuple(p.star for p in positions) == (Star.天伤, Star.天使)
  assert "".join(p.dizhi.value for p in positions) == pair
  assert all(p.rule_id == SHANG_SHI for p in positions)
  for p in positions:
    assert (SHANG_SHI, minggong.value, p.star.value, p.dizhi.value) in _star_rows()


@pytest.mark.parametrize("invalid", [None, "子", 0, True])
def test_new_low_level_inputs_are_validated(invalid: Any) -> None:
  for function in (place_tianku_tianxu, place_tianshang_tianshi):
    with pytest.raises(TypeError):
      function(invalid)


def test_iluck_yang_female_fixed_example(chart_choices: ChartConfig) -> None:
  """只核iLuck例的宫位事实，不将其完整盘或其他口径当golden。"""
  chart = create_chart(
    LunarBirthRecord(
      year=1970, month=9, day=2, is_leap_month=False, shichen=Dizhi.巳, gender=Gender.女
    ),
    chart_choices,
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  assert chart.palaces[0].dizhi is Dizhi.巳
  positions = {p.star: p.dizhi for p in chart.stars}
  assert (positions[Star.天伤], positions[Star.天使]) == (Dizhi.戌, Dizhi.子)
  assert (positions[Star.天哭], positions[Star.天虚]) == (Dizhi.申, Dizhi.辰)


@pytest.mark.parametrize("year", [2024, 2025])
@pytest.mark.parametrize("gender", tuple(Gender))
def test_fixed_rule_ignores_yinyang_and_gender(
  chart_choices: ChartConfig,
  year: int,
  gender: Gender,
) -> None:
  value = resolve(
    LunarBirthRecord(
      year=year, month=9, day=2, is_leap_month=False, shichen=Dizhi.巳, gender=gender
    ),
    chart_choices,
  )
  positions = {p.star: p.dizhi for p in place_stars(value)}
  assert (positions[Star.天伤], positions[Star.天使]) == (Dizhi.戌, Dizhi.子)


def test_new_rules_ownership_and_unimplemented_alternative() -> None:
  catalog = load_catalog()
  for star, identifier in (
    (Star.天哭, KU_XU),
    (Star.天虚, KU_XU),
    (Star.天伤, SHANG_SHI),
    (Star.天使, SHANG_SHI),
  ):
    assert tuple(r.id for r in STAR_RULES if star in r.stars) == (identifier,)
    assert catalog.references(star.concept_id)
    with pytest.raises(ValueError, match="须属于该星"):
      StarPlacement(star, Dizhi.子, "variant.star.kongjie-hour")
  variant = catalog.get("variant.star.tianshang-tianshi-yinyang")
  assert isinstance(variant, RuleVariant) and variant.implementation is None
  entry = catalog.get("entry.star.tianshang-tianshi-yinyang")
  assert isinstance(entry, KnowledgeEntry) and not entry.show_by_default
  assert "天殇" not in Star.__members__ and catalog.find("天空") == ()
  assert catalog.find("天傷") == catalog.find("天伤")
  assert catalog.find("天虛") == catalog.find("天虚")


def test_kuxu_consumes_resolved_year_boundary(chart_choices: ChartConfig) -> None:
  record = GregorianBirthRecord(
    birth_date=date(2024, 2, 6),
    birth_time=time(12),
    time_precision=TimePrecision.秒,
    timezone=FixedOffset(timedelta(hours=8)),
    gender=Gender.未知,
  )
  results = [
    {p.star: p.dizhi for p in place_stars(resolve(record, replace(chart_choices, year_boundary=b)))}
    for b in (YearBoundary.农历正月初一, YearBoundary.立春)
  ]
  assert tuple((r[Star.天哭], r[Star.天虚]) for r in results) == (
    (Dizhi.卯, Dizhi.酉),
    (Dizhi.寅, Dizhi.戌),
  )


def test_new_stars_render_and_annual_natal_consumption(chart_choices: ChartConfig) -> None:
  chart = create_chart(
    LunarBirthRecord(
      year=2024, month=1, day=1, is_leap_month=False, shichen=Dizhi.子, gender=Gender.女
    ),
    chart_choices,
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  assert len(chart.stars) == len(set(p.star for p in chart.stars)) == 36
  assert tuple(p.star for p in chart.stars[-4:]) == (Star.天哭, Star.天虚, Star.天伤, Star.天使)
  text, svg = render_text(chart), fromstring(render_svg(chart))
  brightness = chart_brightness(chart, table=BrightnessTable.全书卷二录文)
  for p in chart.stars[-4:]:
    assert text.count(p.star.value) == 1
    assert p in palace_view(chart, p.dizhi).星位
    (cell,) = [n for n in svg if n.get("data-dizhi") == p.dizhi.name.lower()]
    assert any(n.get("class") == "star" and n.text == p.star.value for n in cell)
    (reading,) = [r for r in brightness if r.star is p.star]
    assert reading.level is None
  rows = liunian_palaces(chart, 2030, sihua_variant=SihuaVariant.王亭之讲义转录)
  assert {p for row in rows for p in row.本命宫.星位} == set(chart.stars)
