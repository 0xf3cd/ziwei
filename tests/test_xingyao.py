"""刑姚外部月表、分设归月与旧星回归分别检查。"""

from dataclasses import replace
from datetime import date, time, timedelta
from xml.etree.ElementTree import fromstring

import pytest

from tools.knowledge_reference import _star_rows
from ziwei.birth import (
  CalculationInput,
  Gender,
  GregorianBirthRecord,
  LunarBirthRecord,
  TimePrecision,
)
from ziwei.brightness import BrightnessTable
from ziwei.calendar import LunarAlgorithm
from ziwei.chart import chart_brightness, create_chart, liunian_palaces, palace_view
from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, TianmaRule
from ziwei.decades import place_decades
from ziwei.ganzhi import Dizhi
from ziwei.knowledge import load_catalog
from ziwei.knowledge.model import KnowledgeEntry
from ziwei.render import render_svg, render_text
from ziwei.resolver import resolve
from ziwei.sihua import SihuaVariant, shengnian_sihua
from ziwei.stars import STAR_RULES, Star, StarPlacement, place_month_stars, place_stars
from ziwei.timezone import FixedOffset

RULE = "variant.star.tianxing-tianyao-month"
# iLuck《月星系》的十二个月对照表；正二月另有《捷览》直接例，九月另有iLuck直接例。
MONTH_TABLE = (
  ("酉", "丑"),
  ("戌", "寅"),
  ("亥", "卯"),
  ("子", "辰"),
  ("丑", "巳"),
  ("寅", "午"),
  ("卯", "未"),
  ("辰", "申"),
  ("巳", "酉"),
  ("午", "戌"),
  ("未", "亥"),
  ("申", "子"),
)
OLD_STARS = tuple(
  Star(name)
  for name in (
    "紫微",
    "天机",
    "太阳",
    "武曲",
    "天同",
    "廉贞",
    "天府",
    "太阴",
    "贪狼",
    "巨门",
    "天相",
    "天梁",
    "七杀",
    "破军",
    "左辅",
    "右弼",
    "文昌",
    "文曲",
    "天魁",
    "天钺",
    "擎羊",
    "陀罗",
    "火星",
    "铃星",
    "地空",
    "地劫",
    "禄存",
    "天马",
    "红鸾",
    "天喜",
  )
)


@pytest.mark.parametrize("month,pair", tuple(enumerate(MONTH_TABLE, 1)))
def test_external_month_table_and_generated_reference(month: int, pair: tuple[str, str]) -> None:
  positions = place_month_stars(month)
  assert tuple(p.star for p in positions) == (Star.左辅, Star.右弼, Star.天刑, Star.天姚)
  assert tuple(p.dizhi.value for p in positions[-2:]) == pair
  assert all(p.rule_id == RULE for p in positions[-2:])
  for star, branch in zip((Star.天刑, Star.天姚), pair, strict=True):
    assert (RULE, str(month), star.value, branch) in _star_rows()


@pytest.mark.parametrize("star", (Star.天刑, Star.天姚))
def test_xingyao_ownership_and_knowledge(star: Star) -> None:
  assert tuple(rule.id for rule in STAR_RULES if star in rule.stars) == (RULE,)
  with pytest.raises(ValueError, match="须属于该星"):
    StarPlacement(star, Dizhi.酉, "variant.star.fubi-effective-month")
  catalog = load_catalog()
  (concept,) = catalog.find(star.value)
  assert concept.id == star.concept_id
  (rule,) = catalog.list_variants(concept_id=concept.id)
  assert rule.id == RULE
  entry = catalog.get("entry.star.tianxing-tianyao-month")
  assert isinstance(entry, KnowledgeEntry) and not entry.show_by_default
  assert len(catalog.references(entry.id)) == 4
  composition = catalog.get("entry.star.month-policy-composition")
  assert isinstance(composition, KnowledgeEntry)
  assert star.concept_id in composition.concept_ids and RULE in composition.variant_ids
  assert "未另指定" in composition.statement and "覆盖时分别取月" in composition.statement
  assert "跨派共识" in composition.limits


@pytest.mark.parametrize("palace_policy", tuple(LeapMonthPolicy))
@pytest.mark.parametrize("month_policy", (None, *tuple(LeapMonthPolicy)))
@pytest.mark.parametrize("day", (15, 16))
@pytest.mark.parametrize("leap", (False, True))
@pytest.mark.parametrize("horse", tuple(TianmaRule))
def test_month_policy_matrix_does_not_change_palace_frame(
  chart_choices: ChartConfig,
  palace_policy: LeapMonthPolicy,
  month_policy: LeapMonthPolicy | None,
  day: int,
  leap: bool,
  horse: TianmaRule,
) -> None:
  record = LunarBirthRecord(
    year=2020, month=4, day=day, is_leap_month=leap, shichen=Dizhi.午, gender=Gender.女
  )
  choices = replace(
    chart_choices,
    leap_month_policy=palace_policy,
    tianma_rule=horse,
    month_star_leap_month_policy=month_policy,
  )
  chart = create_chart(record, choices, sihua_variant=SihuaVariant.排命盘口诀转录)
  baseline = create_chart(
    record,
    replace(choices, month_star_leap_month_policy=None),
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  assert (chart.palaces, chart.shengong, chart.bureau, chart.decades, chart.sihua) == (
    baseline.palaces,
    baseline.shengong,
    baseline.bureau,
    baseline.decades,
    baseline.sihua,
  )
  monthly = {Star.左辅, Star.右弼, Star.天刑, Star.天姚}
  if horse is TianmaRule.月支天马:
    monthly.add(Star.天马)
  assert tuple(p for p in chart.stars if p.star not in monthly) == tuple(
    p for p in baseline.stars if p.star not in monthly
  )
  policy = palace_policy if month_policy is None else month_policy
  assert chart.计算输入.命盘配置.month_star_policy is policy
  following = leap and (
    policy is LeapMonthPolicy.全月归下月
    or (policy is LeapMonthPolicy.上半月归本月下半月归下月 and day == 16)
  )
  positions = {p.star: p.dizhi.value for p in chart.stars}
  expected = "申午丑巳" if following else "未未子辰"
  assert "".join(positions[s] for s in (Star.左辅, Star.右弼, Star.天刑, Star.天姚)) == expected
  expected_horse = ("申" if following else "亥") if horse is TianmaRule.月支天马 else "寅"
  assert positions[Star.天马] == expected_horse
  assert tuple(p.star for p in chart.stars) == (*OLD_STARS, Star.天刑, Star.天姚)
  with pytest.raises(ValueError, match="星位"):
    replace(chart, stars=chart.stars[:-1])


def test_day_rollover_reaches_month_star_split(chart_choices: ChartConfig) -> None:
  record = GregorianBirthRecord(
    birth_date=date(2023, 4, 5),
    birth_time=time(23, 30),
    time_precision=TimePrecision.分,
    timezone=FixedOffset(timedelta(hours=8)),
    gender=Gender.女,
  )
  choices = replace(
    chart_choices, month_star_leap_month_policy=LeapMonthPolicy.上半月归本月下半月归下月
  )
  same = create_chart(record, choices, sihua_variant=SihuaVariant.排命盘口诀转录)
  late = create_chart(
    record,
    replace(choices, day_rollover=DayRollover.晚子时归次日),
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  assert (same.calculation.month, same.calculation.day, same.calculation.is_leap_month) == (
    2,
    15,
    True,
  )
  assert (late.calculation.month, late.calculation.day, late.calculation.is_leap_month) == (
    2,
    16,
    True,
  )
  assert tuple(p.dizhi.value for p in same.stars[-2:]) == ("戌", "寅")
  assert tuple(p.dizhi.value for p in late.stars[-2:]) == ("亥", "卯")


def test_synthetic_leap12_failure_is_scoped_to_consumed_policy(chart_choices: ChartConfig) -> None:
  """合成解析输入不作为真实历法日期；分别检查命身与月系的失败范围。"""
  record = LunarBirthRecord(
    year=2023, month=12, day=16, is_leap_month=True, shichen=Dizhi.午, gender=Gender.女
  )
  value = CalculationInput(
    record=record,
    lunar_year=2023,
    month=12,
    day=16,
    is_leap_month=True,
    shichen=Dizhi.午,
    ganzhi_year=2023,
    config=chart_choices,
    lunar_algorithm=LunarAlgorithm.ALGO3,
    lunar_algorithm_version="1.1.1",
    apparent_solar=False,
    day_rolled=False,
    ut1_jd=None,
    lichun_jd=None,
  )
  # 宫位等组件由正常十二月构造，随后仅替换为字段内部一致的合成闰月输入。
  plain = create_chart(
    replace(record, is_leap_month=False), chart_choices, sihua_variant=SihuaVariant.排命盘口诀转录
  )
  synthetic = replace(plain, calculation=value)
  assert place_stars(value) == synthetic.stars
  assert len(place_decades(value)) == 12
  monthly_bad = replace(
    value, config=replace(chart_choices, month_star_leap_month_policy=LeapMonthPolicy.全月归下月)
  )
  assert place_decades(monthly_bad) == place_decades(value)
  for bad in (
    monthly_bad,
    replace(value, config=replace(chart_choices, leap_month_policy=LeapMonthPolicy.全月归下月)),
  ):
    with pytest.raises(ValueError, match="闰十二月"):
      place_stars(bad)
    with pytest.raises(ValueError, match="闰十二月"):
      replace(synthetic, calculation=bad)
  with pytest.raises(ValueError, match="闰十二月"):
    place_decades(
      replace(value, config=replace(chart_choices, leap_month_policy=LeapMonthPolicy.全月归下月))
    )
  with pytest.raises(ValueError, match="不存在闰12月"):
    create_chart(record, chart_choices, sihua_variant=SihuaVariant.排命盘口诀转录)


def test_new_stars_render_and_chinese_palace_queries(chart_choices: ChartConfig) -> None:
  chart = create_chart(
    LunarBirthRecord(
      year=2023, month=2, day=16, is_leap_month=True, shichen=Dizhi.寅, gender=Gender.女
    ),
    replace(chart_choices, month_star_leap_month_policy=LeapMonthPolicy.上半月归本月下半月归下月),
    sihua_variant=SihuaVariant.王亭之讲义转录,
  )
  assert len(chart.stars) == len(OLD_STARS) + 2
  text = render_text(chart)
  svg = fromstring(render_svg(chart))
  readings = chart_brightness(chart, table=BrightnessTable.全书卷二录文)
  for star, branch in ((Star.天刑, Dizhi.亥), (Star.天姚, Dizhi.卯)):
    assert text.count(star.value) == 1
    view = palace_view(chart, branch)
    assert any(p.星曜 is star and p.地支 is branch for p in view.星位)
    (cell,) = [n for n in svg if n.get("data-dizhi") == branch.name.lower()]
    assert any(n.get("class") == "star" and n.text == star.value for n in cell)
    (reading,) = [r for r in readings if r.star is star]
    assert reading.level is None
  rows = liunian_palaces(chart, 2030, sihua_variant=SihuaVariant.王亭之讲义转录)
  assert {p for row in rows for p in row.本命宫.星位} == set(chart.stars)
  assert chart.sihua == shengnian_sihua(chart.calculation, chart.sihua.variant)


@pytest.mark.parametrize(
  "policy,horse,day,expected",
  (
    (
      LeapMonthPolicy.全月归下月,
      TianmaRule.年支天马,
      15,
      "午巳卯寅丑戌戌亥子丑寅卯辰申申午戌辰丑未酉未寅戌亥亥申寅卯酉",
    ),
    (
      LeapMonthPolicy.全月归下月,
      TianmaRule.年支天马,
      16,
      "酉申午巳辰丑未申酉戌亥子丑巳申午戌辰丑未酉未寅戌亥亥申寅卯酉",
    ),
    (
      LeapMonthPolicy.全月归下月,
      TianmaRule.月支天马,
      15,
      "午巳卯寅丑戌戌亥子丑寅卯辰申申午戌辰丑未酉未寅戌亥亥申申卯酉",
    ),
    (
      LeapMonthPolicy.全月归下月,
      TianmaRule.月支天马,
      16,
      "酉申午巳辰丑未申酉戌亥子丑巳申午戌辰丑未酉未寅戌亥亥申申卯酉",
    ),
    (
      LeapMonthPolicy.全月归本月,
      TianmaRule.年支天马,
      15,
      "辰卯丑子亥申子丑寅卯辰巳午戌未未戌辰丑未酉未寅戌亥亥申寅卯酉",
    ),
    (
      LeapMonthPolicy.全月归本月,
      TianmaRule.年支天马,
      16,
      "巳辰寅丑子酉亥子丑寅卯辰巳酉未未戌辰丑未酉未寅戌亥亥申寅卯酉",
    ),
    (
      LeapMonthPolicy.全月归本月,
      TianmaRule.月支天马,
      15,
      "辰卯丑子亥申子丑寅卯辰巳午戌未未戌辰丑未酉未寅戌亥亥申亥卯酉",
    ),
    (
      LeapMonthPolicy.全月归本月,
      TianmaRule.月支天马,
      16,
      "巳辰寅丑子酉亥子丑寅卯辰巳酉未未戌辰丑未酉未寅戌亥亥申亥卯酉",
    ),
    (
      LeapMonthPolicy.上半月归本月下半月归下月,
      TianmaRule.年支天马,
      15,
      "辰卯丑子亥申子丑寅卯辰巳午戌未未戌辰丑未酉未寅戌亥亥申寅卯酉",
    ),
    (
      LeapMonthPolicy.上半月归本月下半月归下月,
      TianmaRule.年支天马,
      16,
      "酉申午巳辰丑未申酉戌亥子丑巳申午戌辰丑未酉未寅戌亥亥申寅卯酉",
    ),
    (
      LeapMonthPolicy.上半月归本月下半月归下月,
      TianmaRule.月支天马,
      15,
      "辰卯丑子亥申子丑寅卯辰巳午戌未未戌辰丑未酉未寅戌亥亥申亥卯酉",
    ),
    (
      LeapMonthPolicy.上半月归本月下半月归下月,
      TianmaRule.月支天马,
      16,
      "酉申午巳辰丑未申酉戌亥子丑巳申午戌辰丑未酉未寅戌亥亥申申卯酉",
    ),
  ),
)
def test_old_thirty_positions_without_override(
  chart_choices: ChartConfig, policy: LeapMonthPolicy, horse: TianmaRule, day: int, expected: str
) -> None:
  """c0ad2e1改动前采集的合成回归，不当作独立规则证据。"""
  record = LunarBirthRecord(
    year=2020, month=4, day=day, is_leap_month=True, shichen=Dizhi.子, gender=Gender.女
  )
  positions = place_stars(
    resolve(record, replace(chart_choices, leap_month_policy=policy, tianma_rule=horse))
  )
  assert tuple(p.star for p in positions[:30]) == OLD_STARS
  assert "".join(p.dizhi.value for p in positions[:30]) == expected
