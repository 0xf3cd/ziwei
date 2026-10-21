"""独立字面期望来自完整转录及原例，不从待测表或生成参考页反取。"""

from dataclasses import FrozenInstanceError, asdict, replace
from typing import Any, cast

import pytest

from ziwei import sihua
from ziwei.birth import Gender
from ziwei.bureau import WuxingJu
from ziwei.decades import Decade, Direction, decade_direction, decade_periods
from ziwei.ganzhi import Dizhi, Tiangan
from ziwei.sihua import SIHUA_TABLES, SihuaResult, SihuaTable, SihuaVariant, sihua_for_stem
from ziwei.stars import Star

# 第1组据2007论坛安化禄化权化科化忌诀；第2组据讲义页标39，并与九千王亭之列核对。
# 期望展开为星名，不把简称的解码当作原文引述，也不从SIHUA_TABLES读取。
EXPECTED = (
  (
    "廉贞/破军/武曲/太阳",
    "天机/天梁/紫微/太阴",
    "天同/天机/文昌/廉贞",
    "太阴/天同/天机/巨门",
    "贪狼/太阴/右弼/天机",
    "武曲/贪狼/天梁/文曲",
    "太阳/武曲/天同/太阴",
    "巨门/太阳/文曲/文昌",
    "天梁/紫微/左辅/武曲",
    "破军/巨门/太阴/贪狼",
  ),
  (
    "廉贞/破军/武曲/太阳",
    "天机/天梁/紫微/太阴",
    "天同/天机/文昌/廉贞",
    "太阴/天同/天机/巨门",
    "贪狼/太阴/太阳/天机",
    "武曲/贪狼/天梁/文曲",
    "太阳/武曲/天府/天同",
    "巨门/太阳/文曲/文昌",
    "天梁/紫微/天府/武曲",
    "破军/巨门/太阴/贪狼",
  ),
)


@pytest.mark.parametrize("variant", tuple(SihuaVariant))
@pytest.mark.parametrize("stem", tuple(Tiangan))
def test_all_ten_stems_per_complete_variant(stem: Tiangan, variant: SihuaVariant) -> None:
  result = sihua_for_stem(stem, variant)
  expected = EXPECTED[tuple(SihuaVariant).index(variant)][tuple(Tiangan).index(stem)].split("/")
  assert [result.lu.value, result.quan.value, result.ke.value, result.ji.value] == expected
  assert result.year_tiangan is stem and result.variant is variant
  assert result.rule_id == (
    "variant.sihua.zhongyi999"
    if variant is SihuaVariant.排命盘口诀转录
    else "variant.sihua.wangtingzhi-lecture"
  )


def test_independent_1954_jiawu_original_example() -> None:
  """论坛原例第13步③：1954甲午、九月初七子时男命；本测试只用来源给定的甲干。

  http://www.zhongyi999.com.cn/thread-1744-1-1.html
  共有甲行不区分庚壬异文，公历换算不是本例的历法基准。
  """
  result = sihua_for_stem(Tiangan.甲, SihuaVariant.排命盘口诀转录)
  assert (result.lu, result.quan, result.ke, result.ji) == (
    Star.廉贞,
    Star.破军,
    Star.武曲,
    Star.太阳,
  )


def test_independent_1970_gengxu_original_chart() -> None:
  """https://doushuxuantan.com/庚干四化/ 原图明确1970庚戌，非由输出反推。

  图为太阳禄亥、武曲权戌、天府科寅、天同忌酉；没有完整生日，不在本测试重排星位。
  非王亭之原图，只对照所选表在庚行的结果，不证明其余九干。
  """
  result = sihua_for_stem(Tiangan.庚, SihuaVariant.王亭之讲义转录)
  assert (result.lu, result.quan, result.ke, result.ji) == (
    Star.太阳,
    Star.武曲,
    Star.天府,
    Star.天同,
  )


def test_variant_aliases_and_result_are_immutable() -> None:
  assert SihuaVariant["排命盘口诀转录"] is SihuaVariant.ZHONGYI999
  assert SihuaVariant["王亭之讲义转录"] is SihuaVariant.WANGTINGZHI_LECTURE
  result = sihua_for_stem(Tiangan.壬, SihuaVariant.排命盘口诀转录)
  with pytest.raises(FrozenInstanceError):
    cast(Any, result).ke = Star.天府
  other = sihua_for_stem(Tiangan.壬, SihuaVariant.王亭之讲义转录)
  assert result.ke is Star.左辅 and other.ke is Star.天府
  # 四项由字段名承载，不接收可重复或遗漏标签的列表。
  with pytest.raises(TypeError):
    SihuaResult(Tiangan.甲, SihuaVariant.排命盘口诀转录, Star.廉贞, Star.破军, Star.武曲)  # type: ignore[call-arg]


def test_table_copies_both_sequence_levels() -> None:
  rows: Any = [list(row) for row in SIHUA_TABLES[0].rows]
  table = SihuaTable(SihuaVariant.排命盘口诀转录, rows)
  rows[0][0] = Star.紫微
  rows.pop()
  assert table.rows[0][0] is Star.廉贞 and len(table.rows) == 10
  assert isinstance(table.rows, tuple) and isinstance(table.rows[0], tuple)
  with pytest.raises(FrozenInstanceError):
    cast(Any, table).rows = ()


def test_table_does_not_accept_a_string_as_rows() -> None:
  with pytest.raises(TypeError, match="序列"):
    SihuaTable(SihuaVariant.排命盘口诀转录, "not a table")  # type: ignore[arg-type]


@pytest.mark.parametrize(
  "field,value",
  [
    ("year_tiangan", Tiangan.壬),
    ("variant", SihuaVariant.王亭之讲义转录),
    ("lu", Star.紫微),
    ("quan", Star.天机),
    ("ke", Star.天府),
    ("ji", Star.文曲),
  ],
)
def test_result_cannot_claim_a_rule_with_a_different_row(field: str, value: Any) -> None:
  result = sihua_for_stem(Tiangan.庚, SihuaVariant.排命盘口诀转录)
  with pytest.raises(ValueError, match="所选完整表一致"):
    replace(result, **{field: value})


def test_decade_metadata_is_preserved_in_dataclass_fields() -> None:
  period = Decade(Dizhi.子, Direction.顺行, 2, 11)
  saved = asdict(period)
  assert saved["rule_id"] == "variant.decades.xusui-inclusive"
  assert saved["age_convention"] == "虚岁"
  for field in ("rule_id", "age_convention"):
    changes: dict[str, Any] = {field: "其他口径"}
    with pytest.raises((TypeError, ValueError), match="init=False"):
      replace(period, **changes)


def test_decade_accepts_only_five_bureau_twelve_period_age_sequences() -> None:
  expected = {start + index * 10 for start in (2, 3, 4, 5, 6) for index in range(12)}
  accepted = set()
  for age in (*range(-10, 140), -(10**100), 10**100):
    if age in expected:
      period = Decade(Dizhi.子, Direction.顺行, age, age + 9)
      assert (period.start_age, period.end_age) == (age, age + 9)
      accepted.add(age)
    else:
      with pytest.raises(ValueError):
        Decade(Dizhi.子, Direction.顺行, age, age + 9)
  assert accepted == expected


@pytest.mark.parametrize("defect", ["missing", "extra", "short", "duplicate", "type"])
def test_incomplete_or_invalid_table_is_rejected(defect: str) -> None:
  rows: Any = [list(row) for row in SIHUA_TABLES[0].rows]
  if defect == "missing":
    rows.pop()
  elif defect == "extra":
    rows.append(rows[0])
  elif defect == "short":
    rows[0].pop()
  elif defect == "duplicate":
    rows[0][1] = rows[0][0]
  else:
    rows[0][0] = "廉贞"
  with pytest.raises((ValueError, TypeError)):
    SihuaTable(SihuaVariant.排命盘口诀转录, rows)


@pytest.mark.parametrize("invalid", [None, "甲", 0, True])
def test_stem_must_be_a_member(invalid: Any) -> None:
  with pytest.raises(TypeError):
    sihua_for_stem(invalid, SihuaVariant.排命盘口诀转录)
  with pytest.raises(TypeError):
    decade_direction(invalid, Gender.男)


@pytest.mark.parametrize("invalid", [None, "未知流派", SihuaVariant.排命盘口诀转录.value, 0])
def test_variant_is_explicit_and_not_coerced(invalid: Any) -> None:
  with pytest.raises(TypeError):
    sihua_for_stem(Tiangan.甲, invalid)
  with pytest.raises(TypeError):
    SihuaTable(invalid, SIHUA_TABLES[0].rows)
  with pytest.raises(TypeError):
    replace(sihua_for_stem(Tiangan.甲, SihuaVariant.排命盘口诀转录), variant=invalid)


@pytest.mark.parametrize("duplicate", [False, True])
def test_undefined_or_duplicate_registered_table_fails(
  monkeypatch: pytest.MonkeyPatch,
  duplicate: bool,
) -> None:
  table = SIHUA_TABLES[0]
  monkeypatch.setattr(sihua, "SIHUA_TABLES", (table, table) if duplicate else ())
  with pytest.raises(ValueError, match="完整定义"):
    sihua_for_stem(Tiangan.甲, table.variant)


@pytest.mark.parametrize(
  "stem,gender,direction,branches",
  [
    (Tiangan.甲, Gender.男, Direction.顺行, "亥子丑寅卯辰巳午未申酉戌"),
    (Tiangan.甲, Gender.女, Direction.逆行, "亥戌酉申未午巳辰卯寅丑子"),
    (Tiangan.乙, Gender.男, Direction.逆行, "亥戌酉申未午巳辰卯寅丑子"),
    (Tiangan.乙, Gender.女, Direction.顺行, "亥子丑寅卯辰巳午未申酉戌"),
  ],
)
@pytest.mark.parametrize("ju,start_age", list(zip(tuple(WuxingJu), (2, 3, 4, 5, 6), strict=True)))
def test_four_directions_five_bureaus_and_wraparound(
  stem: Tiangan,
  gender: Gender,
  direction: Direction,
  branches: str,
  ju: WuxingJu,
  start_age: int,
) -> None:
  result = decade_periods(Dizhi.亥, ju, stem, gender)
  assert len(result) == 12 and len({period.dizhi for period in result}) == 12
  assert "".join(period.dizhi.value for period in result) == branches
  assert all(period.direction is direction and period.age_convention == "虚岁" for period in result)
  assert all(period.rule_id == "variant.decades.xusui-inclusive" for period in result)
  assert result[0].start_age == start_age and result[-1].end_age == start_age + 119
  # 对整岁标签穷举，既不重叠也不漏岁；最后一岁必须在本限中。
  ages = [age for period in result for age in range(period.start_age, period.end_age + 1)]
  assert ages == list(range(start_age, start_age + 120))


def test_two_original_decade_examples() -> None:
  """论坛木三局原例与讲义图四金四局原图，前者明示虚岁，后者检区间及方向。"""
  forward = decade_periods(Dizhi.寅, WuxingJu.木三局, Tiangan.甲, Gender.男)
  reverse = decade_periods(Dizhi.寅, WuxingJu.木三局, Tiangan.甲, Gender.女)
  assert [(p.dizhi, p.start_age, p.end_age) for p in forward[:3]] == [
    (Dizhi.寅, 3, 12),
    (Dizhi.卯, 13, 22),
    (Dizhi.辰, 23, 32),
  ]
  assert [(p.dizhi, p.start_age, p.end_age) for p in reverse[:3]] == [
    (Dizhi.寅, 3, 12),
    (Dizhi.丑, 13, 22),
    (Dizhi.子, 23, 32),
  ]
  figure4 = decade_periods(Dizhi.丑, WuxingJu.金四局, Tiangan.甲, Gender.男)
  assert [(p.dizhi, p.start_age, p.end_age) for p in figure4[:2]] == [
    (Dizhi.丑, 4, 13),
    (Dizhi.寅, 14, 23),
  ]
  # 图仅给阳男，本测试用合成甲干表示阳；不补图中未提供的完整生日。


@pytest.mark.parametrize("stem", tuple(Tiangan))
def test_all_stem_polarities(stem: Tiangan) -> None:
  expected = Direction.顺行 if stem.value in "甲丙戊庚壬" else Direction.逆行
  assert decade_direction(stem, Gender.男) is expected
  assert decade_direction(stem, Gender.女) is (
    Direction.逆行 if expected is Direction.顺行 else Direction.顺行
  )


@pytest.mark.parametrize("gender", [Gender.未知, "男", "女", None, True])
def test_unknown_or_untyped_gender_is_not_defaulted(gender: Any) -> None:
  with pytest.raises((TypeError, ValueError)):
    decade_periods(Dizhi.子, WuxingJu.水二局, Tiangan.甲, gender)


@pytest.mark.parametrize(
  "field,value",
  [
    ("dizhi", "子"),
    ("direction", "顺行"),
    ("start_age", True),
    ("end_age", 11.0),
    ("start_age", 1),
    ("end_age", 12),
  ],
)
def test_decade_rejects_invalid_values(field: str, value: Any) -> None:
  period = Decade(Dizhi.子, Direction.顺行, 2, 11)
  with pytest.raises((TypeError, ValueError)):
    replace(period, **{field: value})
  with pytest.raises(FrozenInstanceError):
    cast(Any, period).start_age = 3


@pytest.mark.parametrize("field,value", [("year_tiangan", "甲"), ("lu", "廉贞"), ("ke", Star.太阳)])
def test_sihua_result_rejects_invalid_values(field: str, value: Any) -> None:
  result = sihua_for_stem(Tiangan.甲, SihuaVariant.排命盘口诀转录)
  with pytest.raises((TypeError, ValueError)):
    replace(result, **{field: value})


@pytest.mark.parametrize("minggong,ju", [("子", WuxingJu.水二局), (Dizhi.子, "水二局")])
def test_decade_inputs_are_not_coerced(minggong: Any, ju: Any) -> None:
  with pytest.raises(TypeError):
    decade_periods(minggong, ju, Tiangan.甲, Gender.男)
