"""小限直接年龄例、口诀展开、童限项目边界和整盘并读分别验收。"""

import json
import subprocess
import sys
from dataclasses import FrozenInstanceError, asdict, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

import pytest

from ziwei.birth import Gender
from ziwei.bureau import WuxingJu
from ziwei.chart import ZiweiChart
from ziwei.decades import Decade, Direction
from ziwei.ganzhi import Dizhi
from ziwei.palaces import PalaceName, palace_dizhi, twelve_palaces
from ziwei.tongxian import (
  TONGXIAN_RULE_ID,
  Tongxian,
  TongxianBoundary,
  tongxian_at_age,
  tongxian_palace,
)
from ziwei.xiaoxian import XIAOXIAN_RULE_ID, Xiaoxian, xiaoxian_at_age
from ziwei.yunxian import Yunxian, yunxian_at_age

REFERENCE = json.loads(
  Path(__file__).with_name("fixtures").joinpath("xiaoxian-tongxian-reference.json").read_text()
)


@pytest.mark.parametrize("row", REFERENCE["direct_xiaoxian_ages"])
def test_pdf_direct_ages_without_adopting_the_four_year_typo(row: list[Any]) -> None:
  year, gender, age, expected = row
  value = xiaoxian_at_age(Dizhi(year), Gender(gender), age)
  assert value.dizhi is Dizhi(expected)
  assert (value.year_dizhi, value.gender, value.age) == (Dizhi(year), Gender(gender), age)
  assert value.rule_id == XIAOXIAN_RULE_ID
  assert REFERENCE["pdf_four_year_observation"] == {"printed": "亥", "adopted_as_golden": False}


@pytest.mark.parametrize(
  "group,start", [("寅午戌", "辰"), ("申子辰", "戌"), ("巳酉丑", "未"), ("亥卯未", "丑")]
)
@pytest.mark.parametrize("gender,step", [(Gender.男, 1), (Gender.女, -1)])
def test_formula_expansion_all_groups_and_cycles(
  group: str, start: str, gender: Gender, step: int
) -> None:
  branches = "子丑寅卯辰巳午未申酉戌亥"
  for year in group:
    for age in (1, 2, 4, 12, 13, 24, 25, 37, 1000):
      expected = branches[(branches.index(start) + step * (age - 1)) % 12]
      assert xiaoxian_at_age(Dizhi(year), gender, age).dizhi is Dizhi(expected)


@pytest.mark.parametrize(
  "age,name",
  list(
    enumerate(
      (
        PalaceName.命宫,
        PalaceName.财帛,
        PalaceName.疾厄,
        PalaceName.夫妻,
        PalaceName.福德,
        PalaceName.官禄,
      ),
      1,
    )
  ),
)
def test_six_palaces_are_names_not_fixed_branches(age: int, name: PalaceName) -> None:
  assert tongxian_palace(age) is name
  for ming in Dizhi:
    value = tongxian_at_age(ming, WuxingJu.火六局, age, boundary=TongxianBoundary.起限当岁包含)
    assert value.palace_name is name
    assert value.dizhi is palace_dizhi(ming, name)
    assert value.rule_id == TONGXIAN_RULE_ID


@pytest.mark.parametrize("ming", tuple(Dizhi))
def test_shared_palace_relation_matches_all_names_and_existing_frame(ming: Dizhi) -> None:
  from ziwei.ganzhi import Tiangan

  branches = "子丑寅卯辰巳午未申酉戌亥"
  for index, name in enumerate(PalaceName):
    expected = Dizhi(branches[(branches.index(ming.value) - index) % 12])
    assert palace_dizhi(ming, name) is expected
    for stem in Tiangan:
      assert twelve_palaces(ming, stem)[index].dizhi is expected


@pytest.mark.parametrize("ju", tuple(WuxingJu))
@pytest.mark.parametrize("boundary", tuple(TongxianBoundary))
def test_project_boundaries_all_bureaus_not_external_boundary_examples(
  ju: WuxingJu, boundary: TongxianBoundary
) -> None:
  last = ju.number if boundary is TongxianBoundary.起限当岁包含 else ju.number - 1
  for age in range(1, 9):
    reading = tongxian_at_age(Dizhi.辰, ju, age, boundary=boundary)
    assert (reading.minggong, reading.ju, reading.age, reading.boundary) == (
      Dizhi.辰,
      ju,
      age,
      boundary,
    )
    assert (reading.palace_name is not None) == (age <= last)
    assert (reading.dizhi is None) == (age > last)
  assert len({option.rule_id for option in TongxianBoundary}) == 2


def test_undefined_mapping_is_distinct_from_modern_inapplicability() -> None:
  with pytest.raises(NotImplementedError):
    tongxian_palace(7)
  for boundary in TongxianBoundary:
    reading = tongxian_at_age(Dizhi.辰, WuxingJu.木三局, 7, boundary=boundary)
    assert reading.palace_name is None and reading.dizhi is None
  assert (
    tongxian_at_age(
      Dizhi.辰, WuxingJu.火六局, 6, boundary=TongxianBoundary.起限当岁不含
    ).palace_name
    is None
  )


@pytest.mark.parametrize("invalid", [None, True, False, "3", 3.0])
def test_age_type_checks_apply_to_public_constructors_and_functions(invalid: Any) -> None:
  for operation in (
    lambda: xiaoxian_at_age(Dizhi.寅, Gender.男, invalid),
    lambda: Xiaoxian(year_dizhi=Dizhi.寅, gender=Gender.男, age=invalid),
    lambda: tongxian_palace(invalid),
    lambda: Tongxian(
      minggong=Dizhi.辰, ju=WuxingJu.木三局, age=invalid, boundary=TongxianBoundary.起限当岁包含
    ),
  ):
    with pytest.raises(TypeError):
      operation()


@pytest.mark.parametrize("age", [0, -1])
def test_nonpositive_ages_are_not_absent_results(age: int) -> None:
  with pytest.raises(ValueError):
    xiaoxian_at_age(Dizhi.寅, Gender.男, age)
  with pytest.raises(ValueError):
    tongxian_palace(age)
  with pytest.raises(ValueError):
    tongxian_at_age(Dizhi.辰, WuxingJu.木三局, age, boundary=TongxianBoundary.起限当岁不含)


@pytest.mark.parametrize("invalid", [None, "男", True, 0])
def test_gender_type_is_not_coerced(invalid: Any) -> None:
  with pytest.raises(TypeError):
    xiaoxian_at_age(Dizhi.寅, invalid, 1)


def test_unknown_gender_and_foreign_equal_value_enums_fail() -> None:
  with pytest.raises(ValueError, match="已知性别"):
    xiaoxian_at_age(Dizhi.寅, Gender.未知, 1)
  OtherBoundary = StrEnum("OtherBoundary", {"VALUE": "起限当岁包含"})
  other: Any = OtherBoundary.VALUE
  assert other == TongxianBoundary.起限当岁包含
  with pytest.raises(TypeError):
    tongxian_at_age(Dizhi.辰, WuxingJu.木三局, 3, boundary=other)


@pytest.mark.parametrize("invalid", [None, "辰", True, 0])
def test_branch_types_are_checked_even_when_child_policy_is_inapplicable(invalid: Any) -> None:
  with pytest.raises(TypeError):
    xiaoxian_at_age(invalid, Gender.男, 1)
  with pytest.raises(TypeError):
    tongxian_at_age(invalid, WuxingJu.木三局, 8, boundary=TongxianBoundary.起限当岁包含)
  with pytest.raises(TypeError):
    palace_dizhi(invalid, PalaceName.命宫)
  with pytest.raises(TypeError):
    palace_dizhi(Dizhi.辰, invalid)


@pytest.mark.parametrize("invalid", [None, "木三局", 3, True])
def test_bureau_and_boundary_types_fail_before_inapplicability(invalid: Any) -> None:
  with pytest.raises(TypeError):
    tongxian_at_age(Dizhi.辰, invalid, 8, boundary=TongxianBoundary.起限当岁包含)
  with pytest.raises(TypeError):
    tongxian_at_age(Dizhi.辰, WuxingJu.木三局, 8, boundary=invalid)


def test_explicit_boundary_and_immutable_derived_positions() -> None:
  operation: Any = tongxian_at_age
  with pytest.raises(TypeError):
    operation(Dizhi.辰, WuxingJu.木三局, 3)
  small = xiaoxian_at_age(Dizhi.寅, Gender.女, 3)
  child = tongxian_at_age(Dizhi.辰, WuxingJu.木三局, 3, boundary=TongxianBoundary.起限当岁包含)
  for value in (small, child):
    mutable: Any = value
    with pytest.raises(FrozenInstanceError):
      mutable.age = 9
    constructor: Any = type(value)
    with pytest.raises(TypeError):
      constructor(**asdict(value))
  assert replace(child, boundary=TongxianBoundary.起限当岁不含).dizhi is None


def test_chart_combination_does_not_change_decades_or_hide_xiaoxian(
  lunar_chart: ZiweiChart,
) -> None:
  original = lunar_chart.decades
  start = lunar_chart.bureau.number
  for age in (1, start - 1, start, start + 1, original[-1].end_age):
    readings = [yunxian_at_age(lunar_chart, age, tongxian_boundary=b) for b in TongxianBoundary]
    assert readings[0].xiaoxian == readings[1].xiaoxian
    assert readings[0].decade == readings[1].decade
    assert readings[0].xiaoxian.age == age
    assert (readings[0].decade is None) == (age < start)
    if age == start:
      assert readings[0].tongxian.dizhi is None
      assert readings[1].tongxian.dizhi is not None
      assert readings[1].decade is original[0]
  assert lunar_chart.decades is original
  with pytest.raises(ValueError, match="十二大限"):
    yunxian_at_age(
      lunar_chart, original[-1].end_age + 1, tongxian_boundary=TongxianBoundary.起限当岁包含
    )
  operation: Any = yunxian_at_age
  with pytest.raises(TypeError):
    operation(lunar_chart, 3)
  with pytest.raises(TypeError):
    operation(None, 3, tongxian_boundary=TongxianBoundary.起限当岁包含)


def test_combination_constructor_checks_only_its_stated_relations() -> None:
  small = xiaoxian_at_age(Dizhi.寅, Gender.男, 3)
  child = tongxian_at_age(Dizhi.辰, WuxingJu.木三局, 3, boundary=TongxianBoundary.起限当岁包含)
  decade = Decade(Dizhi.辰, Direction.顺行, 3, 12)
  value = Yunxian(xiaoxian=small, tongxian=child, decade=decade)
  for type_changes in ({"xiaoxian": None}, {"tongxian": None}, {"decade": "无"}):
    with pytest.raises(TypeError):
      replace(value, **type_changes)
  for changes in (
    {"xiaoxian": replace(small, age=2)},
    {"decade": None},
    {"decade": Decade(Dizhi.辰, Direction.顺行, 4, 13)},
    {"decade": Decade(Dizhi.辰, Direction.顺行, 13, 22)},
  ):
    with pytest.raises(ValueError):
      replace(value, **changes)
  before = replace(small, age=1)
  before_child = replace(child, age=1)
  assert Yunxian(xiaoxian=before, tongxian=before_child, decade=None).decade is None
  with pytest.raises(ValueError, match="首限"):
    Yunxian(xiaoxian=before, tongxian=before_child, decade=decade)
  with pytest.raises(FrozenInstanceError):
    mutable: Any = value
    mutable.decade = None


def test_catalog_and_new_module_imports_do_not_load_birth_or_calendar() -> None:
  subprocess.run(
    [
      sys.executable,
      "-c",
      "import sys; import ziwei.xiaoxian, ziwei.tongxian, ziwei.yunxian; from ziwei.knowledge import load_catalog; load_catalog(); assert not {'ziwei.birth', 'ziwei.calendar', 'ziwei.chart'} & sys.modules.keys(); assert not any(x.startswith('celestial_calendar') for x in sys.modules)",
    ],
    check=True,
  )


def test_optimized_python_keeps_public_validation() -> None:
  subprocess.run(
    [
      sys.executable,
      "-O",
      "-c",
      "from ziwei.tongxian import tongxian_palace\ntry: tongxian_palace(True)\nexcept TypeError: pass\nelse: raise RuntimeError('bool accepted')\ntry: tongxian_palace(7)\nexcept NotImplementedError: pass\nelse: raise RuntimeError('undefined accepted')",
    ],
    check=True,
  )
