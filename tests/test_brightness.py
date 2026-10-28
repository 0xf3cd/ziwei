"""固定录文的独立字面期望；不从执行表生成168格预期。"""

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

import pytest

from tools.artifacts import source_members
from ziwei.brightness import BrightnessLevel, BrightnessReading, BrightnessTable, star_brightness
from ziwei.ganzhi import Dizhi, Tiangan
from ziwei.stars import MAJOR_STARS, STAR_RULES, Star, StarPlacement

REFERENCE = json.loads(
  Path(__file__)
  .with_name("fixtures")
  .joinpath("quanshu-brightness.json")
  .read_text(encoding="utf-8")
)
CELLS = tuple(
  (REFERENCE["abbreviations"][abbreviation], row["dizhi"], level, column, abbreviation)
  for row in REFERENCE["rows"]
  for column, (level, group) in enumerate(zip(REFERENCE["levels"], row["groups"], strict=True), 1)
  for abbreviation in group
)
TABLE = BrightnessTable.全书卷二录文


def test_sdist_requires_the_literal_brightness_reference() -> None:
  root = Path(__file__).resolve().parents[1]
  assert "tests/fixtures/quanshu-brightness.json" in source_members(root)


def test_literal_reference_is_a_complete_located_fourteen_by_twelve_subset() -> None:
  assert len(CELLS) == len({(star, branch) for star, branch, *_ in CELLS}) == 168
  assert tuple(row["dizhi"] for row in REFERENCE["rows"]) == tuple("子丑寅卯辰巳午未申酉戌亥")
  assert set(REFERENCE["abbreviations"].values()) == {
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
  }
  for index, row in enumerate(REFERENCE["rows"]):
    assert row["html_lines"] == [1236 + index * 4, 1238 + index * 4]
    assert len(row["groups"]) == 7
    assert set("".join(row["groups"])) == set(REFERENCE["abbreviations"])
    assert len("".join(row["groups"])) == 14
  assert "oldid=1963110" in REFERENCE["source_url"]
  assert REFERENCE["snapshot_sha256"] == (
    "2c34e08d75dbcba5a2d6a624e29d7ab7ce785198bd409530b13cb417a87203bb"
  )


@pytest.mark.parametrize("star,branch,expected,column,abbreviation", CELLS)
def test_all_168_cells_match_independent_source_transcription(
  star: str, branch: str, expected: str, column: int, abbreviation: str
) -> None:
  reading = star_brightness(Star(star), Dizhi(branch), table=TABLE)
  assert reading.star is Star(star) and reading.dizhi is Dizhi(branch)
  assert reading.table is TABLE and reading.table_id == "variant.brightness.quanshu-juan2"
  assert reading.level is BrightnessLevel(expected)
  assert REFERENCE["levels"][column - 1] == expected
  assert REFERENCE["abbreviations"][abbreviation] == star


def test_seven_original_names_aliases_and_major_star_identity() -> None:
  assert tuple(level.value for level in BrightnessLevel) == tuple(REFERENCE["levels"])
  for level in BrightnessLevel:
    assert BrightnessLevel[level.value] is level
  assert BrightnessTable["全书卷二录文"] is BrightnessTable.QUANSHU_JUAN2
  assert tuple(star.value for star in MAJOR_STARS) == tuple(REFERENCE["abbreviations"].values())
  assert TABLE.table_id not in {rule.id for rule in STAR_RULES}
  with pytest.raises(ValueError, match="安星规则"):
    StarPlacement(Star.紫微, Dizhi.辰, TABLE.table_id)
  with pytest.raises(ValueError):
    BrightnessTable("不存在的亮度表")


@pytest.mark.parametrize("star", tuple(star for star in Star if star not in MAJOR_STARS))
@pytest.mark.parametrize("branch", tuple(Dizhi))
def test_nonmajor_stars_are_not_filled_from_the_larger_source_table(
  star: Star, branch: Dizhi
) -> None:
  reading = star_brightness(star, branch, table=TABLE)
  assert reading.level is None and reading.table is TABLE


@pytest.mark.parametrize("invalid", [None, True, 0, "紫微", "子", Tiangan.甲, []])
@pytest.mark.parametrize("argument", ["star", "dizhi", "table"])
def test_query_rejects_coercion(argument: str, invalid: Any) -> None:
  values: dict[str, Any] = {"star": Star.紫微, "dizhi": Dizhi.辰, "table": TABLE}
  values[argument] = invalid
  with pytest.raises(TypeError):
    star_brightness(**values)


def test_reading_constructor_checks_consistency_and_is_frozen() -> None:
  reading = star_brightness(Star.紫微, Dizhi.辰, table=TABLE)
  assert reading.level is BrightnessLevel.得地
  assert reading == BrightnessReading(Star.紫微, Dizhi.辰, TABLE, BrightnessLevel.得地)
  for values in (
    {"level": None},
    {"level": BrightnessLevel.庙},
    {"star": Star.红鸾},
    {"dizhi": Dizhi.子},
  ):
    with pytest.raises(ValueError):
      replace(reading, **values)
  invalid_cases: tuple[dict[str, Any], ...] = (
    {"level": "得地"},
    {"star": "紫微"},
    {"dizhi": "辰"},
    {"table": TABLE.value},
  )
  for invalid_values in invalid_cases:
    with pytest.raises(TypeError):
      replace(reading, **invalid_values)
  with pytest.raises(FrozenInstanceError):
    reading.level = BrightnessLevel.庙  # type: ignore[misc]
  with pytest.raises(ValueError):
    BrightnessReading(Star.红鸾, Dizhi.子, TABLE, BrightnessLevel.平和)


@pytest.mark.parametrize(
  "star,branch,adopted,other_original",
  [
    (Star.紫微, Dizhi.辰, "得地", "陷"),
    (Star.太阳, Dizhi.午, "旺", "庙"),
    (Star.巨门, Dizhi.丑, "不得地", "旺"),
    (Star.太阳, Dizhi.丑, "不得地", "陷"),
    (Star.太阳, Dizhi.戌, "不得地", "陷"),
    (Star.天府, Dizhi.卯, "得地", "入庙"),
  ],
)
def test_variant_and_same_book_item_values_cannot_replace_the_named_table(
  star: Star, branch: Dizhi, adopted: str, other_original: str
) -> None:
  reading = star_brightness(star, branch, table=TABLE)
  assert reading.level is not None and reading.level.value == adopted
  assert reading.level.value != other_original
