"""用独立历书事实核干支，不在测试中调用外部排盘库。"""

import json
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from ziwei import ganzhi
from ziwei.ganzhi import JIAZI, YEAR_GANZHI, Dizhi, Ganzhi, Tiangan, Yinyang, year_ganzhi

# 中央气象署《天文日曆2024》印刷第6页（PDF第11页）的“干支順序表”。
# https://www.cwa.gov.tw/Data/service/notice/download/Publish_20231127145652.pdf
GOLDEN = (
  "甲子",
  "乙丑",
  "丙寅",
  "丁卯",
  "戊辰",
  "己巳",
  "庚午",
  "辛未",
  "壬申",
  "癸酉",
  "甲戌",
  "乙亥",
  "丙子",
  "丁丑",
  "戊寅",
  "己卯",
  "庚辰",
  "辛巳",
  "壬午",
  "癸未",
  "甲申",
  "乙酉",
  "丙戌",
  "丁亥",
  "戊子",
  "己丑",
  "庚寅",
  "辛卯",
  "壬辰",
  "癸巳",
  "甲午",
  "乙未",
  "丙申",
  "丁酉",
  "戊戌",
  "己亥",
  "庚子",
  "辛丑",
  "壬寅",
  "癸卯",
  "甲辰",
  "乙巳",
  "丙午",
  "丁未",
  "戊申",
  "己酉",
  "庚戌",
  "辛亥",
  "壬子",
  "癸丑",
  "甲寅",
  "乙卯",
  "丙辰",
  "丁巳",
  "戊午",
  "己未",
  "庚申",
  "辛酉",
  "壬戌",
  "癸亥",
)


@pytest.mark.parametrize("stem, expected", tuple(zip(Tiangan, "丙戊庚壬甲丙戊庚壬甲", strict=True)))
def test_wuhu_yin_for_every_year_stem(stem: Tiangan, expected: str) -> None:
  # 《全书》固定修订1963110起五行寅例，按十干展开，不从执行表重建期望。
  assert ganzhi.yin_stem(stem).value == expected


def test_wuhu_pair_members_are_exhaustive_and_order_independent(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  members = [stem for pair, _ in ganzhi.WUHU_YIN for stem in pair]
  assert len(members) == len(Tiangan) and set(members) == set(Tiangan)
  assert all(members.count(stem) == 1 for stem in Tiangan)
  monkeypatch.setattr(ganzhi, "WUHU_YIN", tuple(reversed(ganzhi.WUHU_YIN)))
  assert "".join(ganzhi.yin_stem(stem).value for stem in Tiangan) == "丙戊庚壬甲丙戊庚壬甲"


def test_wuhu_missing_pair_fails_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(ganzhi, "WUHU_YIN", ganzhi.WUHU_YIN[1:])
  with pytest.raises(ValueError, match="五虎遁缺少年干：己"):
    ganzhi.yin_stem(Tiangan.己)


def test_independent_full_cycle() -> None:
  assert len(JIAZI) == len(set(JIAZI)) == 60
  assert tuple(map(str, JIAZI)) == GOLDEN
  assert tuple(year for year, _ in YEAR_GANZHI) == tuple(range(1984, 2044))
  assert tuple(ganzhi for _, ganzhi in YEAR_GANZHI) == JIAZI
  # CWA同书PDF第2页年历抬头为2024甲辰；以此独立锚检验实现的1984锚。
  assert str(year_ganzhi(2024)) == "甲辰"
  assert str(year_ganzhi(1984)) == "甲子"
  assert str(year_ganzhi(1983)) == "癸亥"
  assert str(year_ganzhi(2044)) == "甲子"


def test_year_cycle_and_supported_endpoints() -> None:
  for year in range(1, 9940):
    assert year_ganzhi(year) == year_ganzhi(year + 60)
  assert isinstance(year_ganzhi(1), Ganzhi)
  assert isinstance(year_ganzhi(9999), Ganzhi)


@pytest.mark.parametrize("value", [0, -1, 10000])
def test_year_range(value: int) -> None:
  with pytest.raises(ValueError):
    year_ganzhi(value)


@pytest.mark.parametrize("value", [True, 2024.0, "2024", None])
def test_year_type(value: Any) -> None:
  with pytest.raises(TypeError):
    year_ganzhi(value)


def test_aliases_and_chinese_json() -> None:
  for kind in (Tiangan, Dizhi, Yinyang):
    for member in kind:
      assert kind.__members__[member.value] is member
      assert json.loads(json.dumps(member, ensure_ascii=False)) == member.value
  assert Tiangan.__members__["甲"] is Tiangan.JIA
  assert Dizhi.__members__["子"] is Dizhi.ZI
  assert Tiangan.甲.yinyang is Yinyang.阳
  assert Tiangan.乙.yinyang is Yinyang.阴
  assert {stem.value for stem in Tiangan if stem.yinyang is Yinyang.阳} == set("甲丙戊庚壬")


def test_ganzhi_values() -> None:
  for text in GOLDEN:
    value = Ganzhi.from_str(text)
    assert str(value) == text
    assert value == Ganzhi(Tiangan(text[0]), Dizhi(text[1]))
  field = "dizhi"
  with pytest.raises(FrozenInstanceError):
    setattr(JIAZI[0], field, Dizhi.丑)


@pytest.mark.parametrize("value", ["", "甲", "甲子年", "甲丑", "丙丑", "未知"])
def test_invalid_ganzhi(value: str) -> None:
  with pytest.raises(ValueError):
    Ganzhi.from_str(value)


@pytest.mark.parametrize("value", [None, 1, ["甲", "子"]])
def test_invalid_ganzhi_type(value: Any) -> None:
  with pytest.raises(TypeError):
    Ganzhi.from_str(value)
  with pytest.raises(TypeError):
    Ganzhi(value, Dizhi.子)
  with pytest.raises(TypeError):
    Ganzhi(Tiangan.甲, value)
