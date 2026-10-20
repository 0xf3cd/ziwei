"""安星测试的独立期望取自《全书》五局宫格、星曜相对位置、中州派讲义例解及现代辅星表。"""

import json
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

import pytest

from ziwei import stars
from ziwei.bureau import WuxingJu
from ziwei.config import TianmaRule
from ziwei.ganzhi import Dizhi, Tiangan
from ziwei.stars import (
  STAR_RULES,
  Star,
  StarRule,
  place_fire_bell,
  place_hour_stars,
  place_major_stars,
  place_month_stars,
  place_stars,
  place_stem_stars,
  tianfu_dizhi,
  tianma_dizhi,
  ziwei_dizhi,
)

# 《全书》宫格缺失或有歧义的三处，按中州派讲义掌诀独立手算：木三局初五在寅、初九在辰，金四局三十在亥。
# 详见citation.quanshu.ziwei-daily的限度说明；不补录文原字、不从待测实现生成，也不称为讲义逐日表。
DAILY = (
  "丑寅寅卯卯辰辰巳巳午午未未申申酉酉戌戌亥亥子子丑丑寅寅卯卯辰",
  "辰丑寅巳寅卯午卯辰未辰巳申巳午酉午未戌未申亥申酉子酉戌丑戌亥",
  "亥辰丑寅子巳寅卯丑午卯辰寅未辰巳卯申巳午辰酉午未巳戌未申午亥",
  "午亥辰丑寅未子巳寅卯申丑午卯辰酉寅未辰巳戌卯申巳午亥辰酉午未",
  "酉午亥辰丑寅戌未子巳寅卯亥申丑午卯辰子酉寅未辰巳丑戌卯申巳午",
)
MAJOR_STARS = tuple(
  Star(value)
  for value in (
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
  )
)
# 按《全书》安南北斗诸星诀及安天府图，分别列出紫微在十二宫时的14星位置，不读取待测实现的偏移表。
MAJOR_BY_ZIWEI = (
  "子亥酉申未辰辰巳午未申酉戌寅",
  "丑子戌酉申巳卯辰巳午未申酉丑",
  "寅丑亥戌酉午寅卯辰巳午未申子",
  "卯寅子亥戌未丑寅卯辰巳午未亥",
  "辰卯丑子亥申子丑寅卯辰巳午戌",
  "巳辰寅丑子酉亥子丑寅卯辰巳酉",
  "午巳卯寅丑戌戌亥子丑寅卯辰申",
  "未午辰卯寅亥酉戌亥子丑寅卯未",
  "申未巳辰卯子申酉戌亥子丑寅午",
  "酉申午巳辰丑未申酉戌亥子丑巳",
  "戌酉未午巳寅午未申酉戌亥子辰",
  "亥戌申未午卯巳午未申酉戌亥卯",
)


@pytest.mark.parametrize("ju", tuple(WuxingJu))
@pytest.mark.parametrize("day", range(1, 31))
def test_all_150_daily_positions_and_all_fourteen_stars(ju: WuxingJu, day: int) -> None:
  expected_ziwei = DAILY[tuple(WuxingJu).index(ju)][day - 1]
  assert ziwei_dizhi(ju, day) is Dizhi(expected_ziwei)
  row = MAJOR_BY_ZIWEI["子丑寅卯辰巳午未申酉戌亥".index(expected_ziwei)]
  expected = {star: Dizhi(branch) for star, branch in zip(MAJOR_STARS, row, strict=True)}
  actual = place_major_stars(ju, day)
  assert len(actual) == 14
  assert {item.star: item.dizhi for item in actual} == expected
  assert len({item.star for item in actual}) == 14


@pytest.mark.parametrize(
  "ju,day,expected",
  [
    (WuxingJu.木三局, 22, Dizhi.亥),
    (WuxingJu.土五局, 20, Dizhi.巳),
    (WuxingJu.火六局, 3, Dizhi.亥),
  ],
)
def test_wangtingzhi_three_printed_examples(ju: WuxingJu, day: int, expected: Dizhi) -> None:
  """中州派讲义第6条、印刷页36的三个原例；期望值直接取自例子，不由本仓计算生成。"""
  assert ziwei_dizhi(ju, day) is expected


@pytest.mark.parametrize(
  "ziwei,expected", list(zip(tuple(Dizhi), "辰卯寅丑子亥戌酉申未午巳", strict=True))
)
def test_tianfu_reflection(ziwei: Dizhi, expected: str) -> None:
  assert tianfu_dizhi(ziwei) is Dizhi(expected)
  assert tianfu_dizhi(tianfu_dizhi(ziwei)) is ziwei


@pytest.mark.parametrize("month", range(1, 13))
def test_twelve_months(month: int) -> None:
  expected = {
    Star.左辅: Dizhi("辰巳午未申酉戌亥子丑寅卯"[month - 1]),
    Star.右弼: Dizhi("戌酉申未午巳辰卯寅丑子亥"[month - 1]),
  }
  assert {item.star: item.dizhi for item in place_month_stars(month)} == expected
  month_branch = Dizhi("寅卯辰巳午未申酉戌亥子丑"[month - 1])
  assert tianma_dizhi(month_branch) is Dizhi("申巳寅亥申巳寅亥申巳寅亥"[month - 1])


@pytest.mark.parametrize("shichen", tuple(Dizhi))
def test_twelve_hours(shichen: Dizhi) -> None:
  index = tuple(Dizhi).index(shichen)
  expected = {
    Star.文昌: Dizhi("戌酉申未午巳辰卯寅丑子亥"[index]),
    Star.文曲: Dizhi("辰巳午未申酉戌亥子丑寅卯"[index]),
    Star.地空: Dizhi("亥戌酉申未午巳辰卯寅丑子"[index]),
    Star.地劫: Dizhi("亥子丑寅卯辰巳午未申酉戌"[index]),
  }
  assert {item.star: item.dizhi for item in place_hour_stars(shichen)} == expected


@pytest.mark.parametrize(
  "stem,row",
  list(
    zip(
      tuple(Tiangan),
      (
        "丑未寅卯丑",
        "子申卯辰寅",
        "亥酉巳午辰",
        "亥酉午未巳",
        "丑未巳午辰",
        "子申午未巳",
        "丑未申酉未",
        "午寅酉戌申",
        "卯巳亥子戌",
        "卯巳子丑亥",
      ),
      strict=True,
    )
  ),
)
def test_ten_stems_modern_kuiyue_and_lucun_yangtuo(stem: Tiangan, row: str) -> None:
  stars = (Star.天魁, Star.天钺, Star.禄存, Star.擎羊, Star.陀罗)
  assert {item.star: item.dizhi for item in place_stem_stars(stem)} == {
    star: Dizhi(branch) for star, branch in zip(stars, row, strict=True)
  }


@pytest.mark.parametrize(
  "group,fire,bell,ma",
  [
    ("寅午戌", "丑寅卯辰巳午未申酉戌亥子", "卯辰巳午未申酉戌亥子丑寅", "申"),
    ("申子辰", "寅卯辰巳午未申酉戌亥子丑", "戌亥子丑寅卯辰巳午未申酉", "寅"),
    ("巳酉丑", "卯辰巳午未申酉戌亥子丑寅", "戌亥子丑寅卯辰巳午未申酉", "亥"),
    ("亥卯未", "酉戌亥子丑寅卯辰巳午未申", "戌亥子丑寅卯辰巳午未申酉", "巳"),
  ],
)
@pytest.mark.parametrize("shichen", tuple(Dizhi))
def test_fire_bell_four_by_twelve_and_all_year_group_members(
  group: str,
  fire: str,
  bell: str,
  ma: str,
  shichen: Dizhi,
) -> None:
  index = tuple(Dizhi).index(shichen)
  for year in group:
    result = place_fire_bell(Dizhi(year), shichen)
    assert tuple(item.dizhi for item in result) == (Dizhi(fire[index]), Dizhi(bell[index]))
    assert tianma_dizhi(Dizhi(year)) is Dizhi(ma)
  # 表中包含中州派讲义第13条壬辰年卯时例：火星在巳、铃星在丑；使用非子时才能检出顺逆方向错误。


def test_star_aliases_identity_json_and_no_global_tiankong() -> None:
  chinese = (
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
  )
  pinyin = (
    "ZIWEI",
    "TIANJI",
    "TAIYANG",
    "WUQU",
    "TIANTONG",
    "LIANZHEN",
    "TIANFU",
    "TAIYIN",
    "TANLANG",
    "JUMEN",
    "TIANXIANG",
    "TIANLIANG",
    "QISHA",
    "POJUN",
    "ZUOFU",
    "YOUBI",
    "WENCHANG",
    "WENQU",
    "TIANKUI",
    "TIANYUE",
    "QINGYANG",
    "TUOLUO",
    "HUOXING",
    "LINGXING",
    "DIKONG",
    "DIJIE",
    "LUCUN",
    "TIANMA",
  )
  for name, member in zip(chinese, pinyin, strict=True):
    assert Star.__members__[name] is Star.__members__[member]
    assert Star.__members__[name].value == name
    assert Star.__members__[name].concept_id == "concept.star." + member.lower()
  assert len(Star) == 28
  assert "天空" not in Star.__members__
  assert json.loads(json.dumps(list(Star), ensure_ascii=False)) == list(chinese)


def test_frozen_positions_and_rule_association() -> None:
  positions = place_major_stars(WuxingJu.火六局, 7)
  assert isinstance(positions, tuple)
  attribute = "dizhi"
  with pytest.raises(FrozenInstanceError):
    setattr(positions[0], attribute, Dizhi.子)
  assert positions[0].dizhi is Dizhi.戌
  assert len({rule.id for rule in STAR_RULES}) == len(STAR_RULES)
  for position in positions:
    assert any(rule.id == position.rule_id and position.star in rule.stars for rule in STAR_RULES)


def test_public_rule_copies_mutable_sequences() -> None:
  original = STAR_RULES[0]
  members: Any = list(original.stars)
  conditions: Any = ["时辰已知"]
  rule = replace(original, stars=members, conditions=conditions)
  members.clear()
  conditions.clear()
  assert isinstance(rule, StarRule)
  assert rule.stars == original.stars
  assert rule.conditions == ("时辰已知",)
  attribute = "name"
  with pytest.raises(FrozenInstanceError):
    setattr(rule, attribute, "改名")


@pytest.mark.parametrize(
  "changes,error",
  [
    ({"id": None}, TypeError),
    ({"name": " "}, ValueError),
    ({"definition": 1}, TypeError),
    ({"implementation": ""}, ValueError),
    ({"scope": False}, TypeError),
    ({"stars": "紫微"}, TypeError),
    ({"stars": ("紫微",)}, TypeError),
    ({"stars": ()}, ValueError),
    ({"stars": (Star.紫微, Star.紫微)}, ValueError),
    ({"conditions": "时辰已知"}, TypeError),
    ({"conditions": (None,)}, TypeError),
    ({"conditions": (" ",)}, ValueError),
    ({"tianma_rule": "年支天马"}, TypeError),
    ({"tianma_rule": TianmaRule.年支天马}, ValueError),
    ({"stars": (Star.天马, Star.紫微), "tianma_rule": TianmaRule.年支天马}, ValueError),
    ({"stars": (Star.天马,)}, ValueError),
  ],
)
def test_public_rule_rejects_invalid_values(
  changes: dict[str, Any], error: type[Exception]
) -> None:
  with pytest.raises(error):
    replace(STAR_RULES[0], **changes)


def test_hour_table_order_does_not_determine_rule(monkeypatch: pytest.MonkeyPatch) -> None:
  expected = {item.star: item for item in place_hour_stars(Dizhi.卯)}
  monkeypatch.setattr(stars, "_HOUR_STARS", tuple(reversed(stars._HOUR_STARS)))
  assert {item.star: item for item in place_hour_stars(Dizhi.卯)} == expected


@pytest.mark.parametrize("defect", ["missing", "duplicate"])
def test_rule_lookup_rejects_missing_or_ambiguous_owner(
  monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
  rule = next(rule for rule in STAR_RULES if Star.文昌 in rule.stars)
  changed = (
    tuple(item for item in STAR_RULES if item is not rule)
    if defect == "missing"
    else (*STAR_RULES, replace(rule, id="variant.star.duplicate"))
  )
  monkeypatch.setattr(stars, "STAR_RULES", changed)
  with pytest.raises(ValueError, match="恰有一条规则"):
    place_hour_stars(Dizhi.卯)


@pytest.mark.parametrize("day", [True, 1.0, "1", None])
def test_ziwei_rejects_wrong_day_type(day: Any) -> None:
  with pytest.raises(TypeError):
    ziwei_dizhi(WuxingJu.水二局, day)


@pytest.mark.parametrize("day", [0, -1, 31])
def test_ziwei_rejects_day_outside_lunar_range(day: int) -> None:
  with pytest.raises(ValueError):
    place_major_stars(WuxingJu.火六局, day)


@pytest.mark.parametrize("month", [True, 1.0, "1", None, 0, 13])
def test_month_inputs_are_not_coerced(month: Any) -> None:
  with pytest.raises((TypeError, ValueError)):
    place_month_stars(month)


@pytest.mark.parametrize("invalid", [None, True, 0, "子", Tiangan.甲])
def test_enum_inputs_are_not_coerced(invalid: Any) -> None:
  for action in (
    lambda: ziwei_dizhi(invalid, 1),
    lambda: tianfu_dizhi(invalid),
    lambda: place_hour_stars(invalid),
    lambda: place_fire_bell(invalid, Dizhi.卯),
    lambda: place_fire_bell(Dizhi.辰, invalid),
    lambda: tianma_dizhi(invalid),
    lambda: place_stars(invalid),
  ):
    with pytest.raises(TypeError):
      action()
  if not isinstance(invalid, Tiangan):
    with pytest.raises(TypeError):
      place_stem_stars(invalid)


@pytest.mark.parametrize(
  "changes,error",
  [
    ({"star": "紫微"}, TypeError),
    ({"dizhi": "子"}, TypeError),
    ({"rule_id": None}, TypeError),
    ({"rule_id": "variant.unknown"}, ValueError),
    ({"star": Star.天马}, ValueError),
  ],
)
def test_position_validates_members(changes: dict[str, Any], error: type[Exception]) -> None:
  position = place_major_stars(WuxingJu.水二局, 1)[0]
  with pytest.raises(error):
    replace(position, **changes)


@pytest.mark.parametrize("mode", [(), ("-O",)])
def test_stars_and_knowledge_without_native_and_unrewritten_validation(
  tmp_path: Path,
  mode: tuple[str, ...],
) -> None:
  script = r"""
import sys
from importlib.abc import MetaPathFinder
class Block(MetaPathFinder):
  def find_spec(self, fullname, path=None, target=None):
    if fullname.split('.')[0] in ('celestial_calendar', 'tzdata'):
      raise RuntimeError('unexpected native or timezone import: ' + fullname)
sys.meta_path.insert(0, Block())
from dataclasses import replace
from ziwei.birth import CalculationInput, LunarBirthRecord, Gender
from ziwei.calendar import LunarAlgorithm
from ziwei.config import ChartConfig, LeapMonthPolicy, DayRollover, YearBoundary
from ziwei.bureau import WuxingJu
from ziwei.ganzhi import Dizhi
from ziwei.stars import *
from ziwei.knowledge import load_catalog
config = ChartConfig(leap_month_policy=LeapMonthPolicy.全月归本月,
                     day_rollover=DayRollover.早晚子时同日, year_boundary=YearBoundary.农历正月初一)
record = LunarBirthRecord(year=2000, month=1, day=1, is_leap_month=False,
                         shichen=Dizhi.子, gender=Gender.未知)
value = CalculationInput(record=record, lunar_year=2000, month=1, day=1, is_leap_month=False,
  shichen=Dizhi.子, ganzhi_year=2000, config=config, lunar_algorithm=LunarAlgorithm.ALGO3,
  lunar_algorithm_version='0.8.0', apparent_solar=False, day_rolled=False,
  ut1_jd=None, lichun_jd=None)
if len(place_stars(value)) != 28 or not load_catalog().find('紫微'):
  raise RuntimeError('pure placement or independent lookup did not run')
cases = [lambda: ziwei_dizhi(WuxingJu.水二局, True),
   lambda: StarRule('id', 'name', ['紫微'], 'definition', 'implementation'),
   lambda: StarRule('id', 'name', [Star.紫微, Star.紫微], 'definition', 'implementation'),
   lambda: StarRule('id', 'name', [Star.紫微], 'definition', 'implementation', conditions=[None]),
  lambda: ziwei_dizhi(WuxingJu.水二局, 31), lambda: ziwei_dizhi('水二局', 1),
  lambda: place_month_stars(13), lambda: place_month_stars(True),
  lambda: place_hour_stars('子'), lambda: place_stem_stars('甲'),
  lambda: place_fire_bell('辰', Dizhi.卯), lambda: place_fire_bell(Dizhi.辰, None),
  lambda: tianma_dizhi('子'), lambda: tianfu_dizhi('子'),
  lambda: place_stars(replace(value, shichen=None)), lambda: place_stars(None),
  lambda: replace(config, tianma_rule='年支天马'),
  lambda: StarPlacement(Star.天马, Dizhi.寅, place_major_stars(WuxingJu.水二局, 1)[0].rule_id),
  lambda: StarPlacement('紫微', Dizhi.寅, 'variant.unknown')]
for action in cases:
  try:
    action()
  except (TypeError, ValueError):
    pass
  else:
    raise RuntimeError('validation accepted invalid input')
print('checked=' + str(len(cases)))
"""
  result = subprocess.run(
    (sys.executable, *mode, "-I", "-c", script),
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stdout + result.stderr
  assert "checked=19" in result.stdout
