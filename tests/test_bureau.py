"""五行局的测试。"""

import pytest

from ziwei.bureau import WuxingJu, bureau_number, bureau_of
from ziwei.ganzhi import Ganzhi, Wuxing, nayin


@pytest.mark.parametrize(
  "ganzhi_text, expected",
  [
    ("丙寅", WuxingJu.HUO_LIU),  # 炉中火 → 火六局（《全书》安身命例）
    ("甲子", WuxingJu.JIN_SI),  # 海中金 → 金四局
    ("戊辰", WuxingJu.MU_SAN),  # 大林木 → 木三局
    ("庚午", WuxingJu.TU_WU),  # 路旁土 → 土五局
  ],
)
def test_bureau_by_nayin(ganzhi_text: str, expected: WuxingJu) -> None:
  assert bureau_of(Ganzhi.from_str(ganzhi_text)) is expected


def test_wuxingju_mapping_is_complete() -> None:
  """五种纳音五行各对应一个局，局数即起限年龄。"""
  assert {
    bureau_of(Ganzhi.from_str(text)) for text in ("甲子", "丙寅", "戊辰", "庚午", "丙子")
  } == set(WuxingJu)
  assert {bureau_number(ju) for ju in WuxingJu} == {2, 3, 4, 5, 6}


def test_nayin_elements_are_uniform() -> None:
  """纳音五行表两两一组，六十甲子都有且只属于一个五行。"""
  from ziwei.ganzhi import JIAZI, NAYIN_ELEMENT

  assert len(NAYIN_ELEMENT) == 30
  elements = {nayin(item) for item in JIAZI}
  assert elements == set(Wuxing)
  for index, element in enumerate(NAYIN_ELEMENT):
    assert nayin(JIAZI[index * 2]) is element
    assert nayin(JIAZI[index * 2 + 1]) is element


def test_bureau_rejects_non_ganzhi() -> None:
  with pytest.raises(TypeError, match="干支"):
    bureau_of("甲子")  # type: ignore[arg-type]


def test_bureau_number_rejects_non_ju() -> None:
  with pytest.raises(TypeError, match="五行局"):
    bureau_number("水二局")  # type: ignore[arg-type]


def test_bureau_covers_all_ganzhi() -> None:
  from ziwei.ganzhi import JIAZI

  for item in JIAZI:
    assert isinstance(bureau_of(item), WuxingJu)
