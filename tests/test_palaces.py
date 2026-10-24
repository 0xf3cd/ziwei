"""命宫、身宫、十二宫与宫干的测试；以《全书》安身命例与中州派例为独立盘例。"""

from dataclasses import FrozenInstanceError
from enum import StrEnum
from itertools import product
from typing import Any, cast

import pytest

from ziwei import palaces as module
from ziwei.bureau import WuxingJu, bureau_of
from ziwei.config import LeapMonthPolicy
from ziwei.ganzhi import Dizhi, Ganzhi, Tiangan
from ziwei.palaces import (
  Palace,
  PalaceName,
  effective_month,
  minggong_dizhi,
  month_palace_index,
  palace_ganzhi,
  shengong_dizhi,
  twelve_palaces,
)


def test_month_palace_index_starts_at_yin() -> None:
  assert month_palace_index(1) == 2  # 寅
  assert month_palace_index(2) == 3  # 卯
  assert month_palace_index(12) == 1  # 丑


@pytest.mark.parametrize("month", [0, 13, True])
def test_month_palace_index_rejects(month: object) -> None:
  with pytest.raises((TypeError, ValueError)):
    month_palace_index(month)  # type: ignore[arg-type]


def test_quanshu_anshenming_examples() -> None:
  """《全书》安身命例三例：正月子时命身同寅、正月丑时命丑身卯、正月寅时命子身辰。"""
  assert minggong_dizhi(1, Dizhi.子) is Dizhi.寅
  assert shengong_dizhi(1, Dizhi.子) is Dizhi.寅
  assert minggong_dizhi(1, Dizhi.丑) is Dizhi.丑
  assert shengong_dizhi(1, Dizhi.丑) is Dizhi.卯
  assert minggong_dizhi(1, Dizhi.寅) is Dizhi.子
  assert shengong_dizhi(1, Dizhi.寅) is Dizhi.辰


def test_zhongzhou_example_three_month_si_hour() -> None:
  """中州派讲义例：三月巳时，命在亥、身在酉。"""
  assert minggong_dizhi(3, Dizhi.巳) is Dizhi.亥
  assert shengong_dizhi(3, Dizhi.巳) is Dizhi.酉


def test_shengong_spans_six_palace_names() -> None:
  """身宫只落六个宫名：子午同宫、丑未福德、寅申官禄、卯酉迁移、辰戌财帛、巳亥夫妻。"""
  cases = {
    Dizhi.子: PalaceName.MINGGONG,
    Dizhi.丑: PalaceName.FUDE,
    Dizhi.寅: PalaceName.GUANLU,
    Dizhi.卯: PalaceName.QIANYI,
    Dizhi.辰: PalaceName.CAIBO,
    Dizhi.巳: PalaceName.QIQIE,
    Dizhi.午: PalaceName.MINGGONG,
    Dizhi.未: PalaceName.FUDE,
    Dizhi.申: PalaceName.GUANLU,
    Dizhi.酉: PalaceName.QIANYI,
    Dizhi.戌: PalaceName.CAIBO,
    Dizhi.亥: PalaceName.QIQIE,
  }
  for month in range(1, 13):
    for shichen, name in cases.items():
      minggong = minggong_dizhi(month, shichen)
      offset = (12 - 2 * tuple(Dizhi).index(shichen)) % 12
      palaces = twelve_palaces(minggong, Tiangan.甲)
      assert palaces[offset].dizhi == shengong_dizhi(month, shichen)
      assert palaces[offset].name is name


def test_palace_names_have_modern_aliases() -> None:
  assert PalaceName.__members__["夫妻"] is PalaceName.__members__["妻妾"]
  assert PalaceName.__members__["仆役"] is PalaceName.__members__["奴仆"]
  assert PalaceName.__members__["交友"] is PalaceName.__members__["奴仆"]
  assert PalaceName.__members__["事业"] is PalaceName.__members__["官禄"]
  assert PalaceName.__members__["命宫"] is PalaceName.MINGGONG


def test_twelve_palaces_order_and_stems() -> None:
  """命在子、甲年：命宫子(丙)、兄弟亥(乙)、妻妾戌(甲)；逆排一周回到命宫。"""
  palaces = twelve_palaces(Dizhi.子, Tiangan.甲)
  assert len(palaces) == 12
  assert [p.name for p in palaces] == list(PalaceName)
  assert (palaces[0].dizhi, palaces[0].tiangan) == (Dizhi.子, Tiangan.丙)
  assert (palaces[1].dizhi, palaces[1].tiangan) == (Dizhi.亥, Tiangan.乙)
  assert (palaces[2].dizhi, palaces[2].tiangan) == (Dizhi.戌, Tiangan.甲)


def test_twelve_palaces_cover_each_branch_once() -> None:
  for month, shichen, tiangan in product(range(1, 13), Dizhi, Tiangan):
    palaces = twelve_palaces(minggong_dizhi(month, shichen), tiangan)
    assert {palace.dizhi for palace in palaces} == set(Dizhi)
    assert {palace.name for palace in palaces} == set(PalaceName)
    for palace in palaces:
      assert isinstance(palace, Palace)


@pytest.mark.parametrize(
  "ganzhi_year, minggong, expected",
  [
    (1984, Dizhi.寅, Ganzhi.from_str("丙寅")),  # 甲年命寅
    (1985, Dizhi.寅, Ganzhi.from_str("戊寅")),  # 乙年命寅
    (1984, Dizhi.丑, Ganzhi.from_str("丁丑")),  # 甲年命丑
    (1988, Dizhi.午, Ganzhi.from_str("戊午")),  # 戊辰年命午
  ],
)
def test_palace_ganzhi_by_wuhu(ganzhi_year: int, minggong: Dizhi, expected: Ganzhi) -> None:
  assert palace_ganzhi(minggong, ganzhi_year) == expected


def test_quanshu_houju_example() -> None:
  """《全书》「甲生人安命在寅……丙寅丁卯炉中火，却去火局」：丙寅 → 火六局。"""
  assert bureau_of(palace_ganzhi(Dizhi.寅, 1984)) is WuxingJu.HUO_LIU


@pytest.mark.parametrize("field,text", [("dizhi", "子"), ("tiangan", "甲"), ("name", "命宫")])
@pytest.mark.parametrize("kind", ["string", "list", "none", "other-enum"])
def test_palace_rejects_non_domain_fields(field: str, text: str, kind: str) -> None:
  bad: Any = {"string": text, "list": [text], "none": None, "other-enum": WuxingJu.水二局}[kind]
  fields: dict[str, Any] = dict(dizhi=Dizhi.子, tiangan=Tiangan.甲, name=PalaceName.命宫)
  fields[field] = bad
  with pytest.raises(TypeError, match=field):
    Palace(**fields)


@pytest.mark.parametrize("stem,branch", [(Tiangan.甲, Dizhi.丑), (Tiangan.乙, Dizhi.子)])
def test_palace_rejects_unpaired_ganzhi(stem: Tiangan, branch: Dizhi) -> None:
  with pytest.raises(ValueError, match="阴阳"):
    Palace(dizhi=branch, tiangan=stem, name=PalaceName.命宫)


def test_palace_is_frozen_and_accepts_aliases() -> None:
  value = Palace(dizhi=Dizhi.子, tiangan=Tiangan.甲, name=PalaceName.夫妻)
  assert value.name is PalaceName.QIQIE
  assert value.ganzhi == Ganzhi.from_str("甲子")
  with pytest.raises(FrozenInstanceError):
    value.dizhi = Dizhi.寅  # type: ignore[misc]


@pytest.mark.parametrize("policy", tuple(LeapMonthPolicy))
@pytest.mark.parametrize("is_leap", [False, True])
@pytest.mark.parametrize("day", [0, 31, 100])
def test_effective_month_rejects_outside_basic_day_range(
  policy: LeapMonthPolicy, is_leap: bool, day: int
) -> None:
  with pytest.raises(ValueError, match="农历日须在1至30之间"):
    effective_month(12, day, is_leap, policy)


@pytest.mark.parametrize("policy", tuple(LeapMonthPolicy))
@pytest.mark.parametrize("is_leap", [False, True])
@pytest.mark.parametrize("day", [1, 15, 16, 30])
def test_effective_month_boundaries(policy: LeapMonthPolicy, is_leap: bool, day: int) -> None:
  expected = 2
  if is_leap and (
    policy is LeapMonthPolicy.全月归下月
    or (policy is LeapMonthPolicy.上半月归本月下半月归下月 and day >= 16)
  ):
    expected = 3
  assert effective_month(2, day, is_leap, policy) == expected


@pytest.mark.parametrize("policy", tuple(LeapMonthPolicy))
@pytest.mark.parametrize("day", [15, 16, 30])
def test_effective_month_leap_twelfth(policy: LeapMonthPolicy, day: int) -> None:
  if policy is LeapMonthPolicy.全月归本月 or (
    policy is LeapMonthPolicy.上半月归本月下半月归下月 and day == 15
  ):
    assert effective_month(12, day, True, policy) == 12
  else:
    with pytest.raises(ValueError, match="闰十二月"):
      effective_month(12, day, True, policy)
  assert effective_month(12, day, False, policy) == 12


@pytest.mark.parametrize("is_leap", [False, True])
def test_effective_month_rejects_unimplemented_policy(
  monkeypatch: pytest.MonkeyPatch, is_leap: bool
) -> None:
  # 用含既有成员的扩展枚举替换所属模块的类型，确保测到合法成员而不是错类型。
  extended = StrEnum(  # type: ignore[misc]
    "ExtendedLeapMonthPolicy",
    {name: member.value for name, member in LeapMonthPolicy.__members__.items()}
    | {"UNIMPLEMENTED": "未实现测试口径"},
  )
  monkeypatch.setattr(module, "LeapMonthPolicy", extended)
  assert effective_month(2, 16, is_leap, cast(LeapMonthPolicy, extended["CURRENT_MONTH"])) == 2
  with pytest.raises(ValueError, match="尚未实现的闰月口径：未实现测试口径"):
    effective_month(2, 16, is_leap, cast(LeapMonthPolicy, extended["UNIMPLEMENTED"]))
