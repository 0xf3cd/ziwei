"""出生记录保真、形状校验与完整性边界。"""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, time, timedelta
from itertools import product
from typing import Any

import pytest

from ziwei.birth import (
  GongliBirthRecord,
  JisuanInput,
  NongliBirthRecord,
  ShijianJingdu,
  Xingbie,
  shichen_from_time,
)
from ziwei.config import Huannian, PaipanConfig, RunyueGuishu, ZishiHuanri
from ziwei.ganzhi import Dizhi, Yinyang
from ziwei.shiqu import GudingShiqu, IanaShiqu


def gongli(**changes: Any) -> GongliBirthRecord:
  values: dict[str, Any] = {
    "riqi": date(1988, 7, 1),
    "shijian": time(12),
    "shijian_jingdu": ShijianJingdu.分,
    "shiqu": IanaShiqu("Asia/Shanghai"),
    "xingbie": Xingbie.男,
  }
  values.update(changes)
  return GongliBirthRecord(**values)


def nongli(**changes: Any) -> NongliBirthRecord:
  values: dict[str, Any] = {
    "nian": 2000,
    "yue": 4,
    "ri": 15,
    "runyue": True,
    "shichen": Dizhi.子,
    "xingbie": Xingbie.女,
  }
  values.update(changes)
  return NongliBirthRecord(**values)


def config() -> PaipanConfig:
  return PaipanConfig(
    runyue_guishu=RunyueGuishu.全月归本月,
    zishi_huanri=ZishiHuanri.早晚子时同日,
    huannian=Huannian.立春,
  )


def jisuan(**changes: Any) -> JisuanInput:
  values: dict[str, Any] = {
    "jilu": nongli(),
    "nongli_nian": 2000,
    "yue": 4,
    "ri": 15,
    "runyue": True,
    "shichen": Dizhi.子,
    "ganzhi_nian": 1999,
    "koujing": config(),
  }
  values.update(changes)
  return JisuanInput(**values)


@pytest.mark.parametrize(
  "clock, expected",
  [
    (time(0), Dizhi.子),
    (time(0, 59, 59, 999999), Dizhi.子),
    (time(1), Dizhi.丑),
    (time(22, 59, 59, 999999), Dizhi.亥),
    (time(23), Dizhi.子),
    (time(23, 59, 59, 999999), Dizhi.子),
  ],
)
def test_both_sides_of_zishi(clock: time, expected: Dizhi) -> None:
  assert shichen_from_time(clock) is expected
  record = gongli(shijian=clock, shijian_jingdu=ShijianJingdu.微秒)
  assert record.shichen is expected
  assert record.riqi == date(1988, 7, 1)


def test_every_shichen_boundary() -> None:
  expected = (
    Dizhi.丑,
    Dizhi.寅,
    Dizhi.卯,
    Dizhi.辰,
    Dizhi.巳,
    Dizhi.午,
    Dizhi.未,
    Dizhi.申,
    Dizhi.酉,
    Dizhi.戌,
    Dizhi.亥,
    Dizhi.子,
  )
  previous = (Dizhi.子, *expected[:-1])
  for hour, before, after in zip(range(1, 24, 2), previous, expected, strict=True):
    assert shichen_from_time(time(hour - 1, 59, 59, 999999)) is before
    assert shichen_from_time(time(hour)) is after


@pytest.mark.parametrize("bad", [None, "子", 0, datetime(2000, 1, 1)])
def test_clock_type(bad: Any) -> None:
  with pytest.raises(TypeError):
    shichen_from_time(bad)


@pytest.mark.parametrize("bad", [time(0, tzinfo=UTC), time(0, fold=1)])
def test_clock_does_not_hide_timezone_choice(bad: time) -> None:
  with pytest.raises(ValueError):
    shichen_from_time(bad)


def test_gongli_original_and_explicit_offset() -> None:
  record = gongli(jingdu_deg=121.5, didian="合成省", laiyuan="合成记录")
  resolved = record.resolve_time()
  assert resolved.offset == timedelta(hours=9)
  assert resolved.utc == datetime(1988, 7, 1, 3, tzinfo=UTC)
  assert record.shijian == time(12)
  assert record.jingdu_deg == 121.5
  assert record.didian == "合成省"
  assert record.laiyuan == "合成记录"
  fixed = replace(record, shiqu=GudingShiqu(timedelta(hours=8))).resolve_time()
  assert fixed.utc == datetime(1988, 7, 1, 4, tzinfo=UTC)
  assert fixed.shuju is None


def test_unknown_and_historical_originals_are_preserved() -> None:
  record = gongli(shijian=None, shijian_jingdu=ShijianJingdu.日, xingbie=Xingbie.未知)
  assert record.shichen is None
  assert record.xingbie is Xingbie.未知
  with pytest.raises(ValueError, match="未知"):
    record.resolve_time()
  old = gongli(riqi=date(1900, 1, 1))
  assert old.riqi.year == 1900
  with pytest.raises(ValueError, match="1972"):
    old.resolve_time()


@pytest.mark.parametrize(
  "changes, error",
  [
    ({"riqi": datetime(2000, 1, 1)}, TypeError),
    ({"riqi": "2000-01-01"}, TypeError),
    ({"shiqu": "Asia/Shanghai"}, TypeError),
    ({"xingbie": "男"}, TypeError),
    ({"shijian_jingdu": "分"}, TypeError),
    ({"shijian": None}, ValueError),
    ({"shijian_jingdu": ShijianJingdu.日}, ValueError),
    ({"shijian": time(12, 1), "shijian_jingdu": ShijianJingdu.时}, ValueError),
    ({"shijian": time(12, 0, 1)}, ValueError),
    ({"shijian": time(12, 0, 0, 1), "shijian_jingdu": ShijianJingdu.秒}, ValueError),
    ({"jingdu_deg": float("nan")}, ValueError),
    ({"jingdu_deg": float("inf")}, ValueError),
    ({"jingdu_deg": 180.1}, ValueError),
    ({"jingdu_deg": -180.1}, ValueError),
    ({"jingdu_deg": True}, TypeError),
    ({"jingdu_deg": "120"}, TypeError),
    ({"didian": ["合成省"]}, TypeError),
    ({"laiyuan": {}}, TypeError),
  ],
)
def test_gongli_rejects_invalid_inputs(changes: dict[str, Any], error: type[Exception]) -> None:
  with pytest.raises(error):
    gongli(**changes)


@pytest.mark.parametrize("precision", list(ShijianJingdu)[1:])
def test_known_time_precision(precision: ShijianJingdu) -> None:
  assert gongli(shijian_jingdu=precision).shijian_jingdu is precision


def test_nongli_is_structural_not_a_calendar_converter() -> None:
  record = nongli(nian=2000, yue=12, ri=30, runyue=True, shichen=None, xingbie=Xingbie.未知)
  assert (record.nian, record.yue, record.ri, record.runyue) == (2000, 12, 30, True)
  assert record.shichen is None
  assert not hasattr(record, "resolve_time")
  for longitude in (-180, 180):
    assert nongli(jingdu_deg=longitude).jingdu_deg == longitude


@pytest.mark.parametrize("field, maximum", [("nian", 9999), ("yue", 12), ("ri", 30)])
def test_nongli_ranges_and_types(field: str, maximum: int) -> None:
  for value in (0, maximum + 1):
    with pytest.raises(ValueError):
      nongli(**{field: value})
  for invalid in (True, 1.0, "1", None):
    with pytest.raises(TypeError):
      nongli(**{field: invalid})


@pytest.mark.parametrize("changes", [{"runyue": 1}, {"shichen": "子"}, {"xingbie": "女"}])
def test_nongli_nominal_types(changes: dict[str, Any]) -> None:
  with pytest.raises(TypeError):
    nongli(**changes)


def test_parsed_contract_and_independent_year_choice() -> None:
  value = jisuan()
  assert value.nongli_nian == 2000
  assert str(value.nian_ganzhi) == "己卯"
  assert value.ganzhi_nian == 1999
  assert value.xingbie is Xingbie.女
  assert value.yinyang is Yinyang.阴
  value.require_complete()
  assert jisuan(ganzhi_nian=2000).yinyang is Yinyang.阳
  for runyue, zishi, year in product(RunyueGuishu, ZishiHuanri, Huannian):
    choices = PaipanConfig(runyue_guishu=runyue, zishi_huanri=zishi, huannian=year)
    assert jisuan(koujing=choices).koujing is choices


def test_partial_parsed_inputs_do_not_gain_defaults() -> None:
  for unknown_time, unknown_gender in ((True, False), (False, True), (True, True)):
    value = jisuan(
      shichen=None if unknown_time else Dizhi.子,
      jilu=nongli(xingbie=Xingbie.未知 if unknown_gender else Xingbie.女),
    )
    with pytest.raises(ValueError, match="完整命盘"):
      value.require_complete()


@pytest.mark.parametrize(
  "changes, error",
  [
    ({"jilu": {}}, TypeError),
    ({"koujing": None}, TypeError),
    ({"ganzhi_nian": None}, TypeError),
    ({"ganzhi_nian": 0}, ValueError),
    ({"nongli_nian": True}, TypeError),
    ({"yue": 13}, ValueError),
    ({"runyue": 0}, TypeError),
    ({"shichen": "子"}, TypeError),
  ],
)
def test_parsed_input_validation(changes: dict[str, Any], error: type[Exception]) -> None:
  with pytest.raises(error):
    jisuan(**changes)


def test_frozen_inputs_and_nested_values() -> None:
  value = jisuan()
  for instance, field, replacement in (
    (gongli(), "laiyuan", "更改"),
    (nongli(), "runyue", False),
    (value, "ganzhi_nian", 2001),
    (value.jilu, "xingbie", Xingbie.男),
    (value.koujing, "huannian", Huannian.农历正月初一),
  ):
    with pytest.raises(FrozenInstanceError):
      setattr(instance, field, replacement)
  for chinese, pinyin in (("男", "NAN"), ("女", "NV"), ("未知", "WEIZHI")):
    assert Xingbie.__members__[chinese] is Xingbie.__members__[pinyin]
  for precision in ShijianJingdu:
    assert ShijianJingdu.__members__[precision.value] is precision
