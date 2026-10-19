"""三个独立口径均需显式给出。"""

import json
from dataclasses import FrozenInstanceError, asdict
from itertools import product
from typing import Any

import pytest

from ziwei.config import Huannian, PaipanConfig, RunyueGuishu, ZishiHuanri


def test_all_independent_combinations() -> None:
  configurations = tuple(
    PaipanConfig(runyue_guishu=runyue, zishi_huanri=zishi, huannian=huannian)
    for runyue, zishi, huannian in product(RunyueGuishu, ZishiHuanri, Huannian)
  )
  assert len(set(configurations)) == 12
  for config in configurations:
    assert asdict(config) == {
      "runyue_guishu": config.runyue_guishu,
      "zishi_huanri": config.zishi_huanri,
      "huannian": config.huannian,
    }
    assert json.loads(json.dumps(asdict(config), ensure_ascii=False)) == {
      "runyue_guishu": config.runyue_guishu.value,
      "zishi_huanri": config.zishi_huanri.value,
      "huannian": config.huannian.value,
    }
    field = "huannian"
    with pytest.raises(FrozenInstanceError):
      setattr(config, field, Huannian.立春)


@pytest.mark.parametrize("missing", ["runyue_guishu", "zishi_huanri", "huannian"])
def test_no_policy_defaults(missing: str) -> None:
  values: dict[str, Any] = {
    "runyue_guishu": RunyueGuishu.全月归本月,
    "zishi_huanri": ZishiHuanri.晚子时归次日,
    "huannian": Huannian.农历正月初一,
  }
  del values[missing]
  with pytest.raises(TypeError):
    PaipanConfig(**values)


@pytest.mark.parametrize("field", ["runyue_guishu", "zishi_huanri", "huannian"])
@pytest.mark.parametrize("invalid", [None, "立春", 0, [], Huannian.立春])
def test_policies_are_not_coerced(field: str, invalid: Any) -> None:
  values: dict[str, Any] = {
    "runyue_guishu": RunyueGuishu.全月归本月,
    "zishi_huanri": ZishiHuanri.晚子时归次日,
    "huannian": Huannian.农历正月初一,
    field: invalid,
  }
  if field == "huannian" and invalid is Huannian.立春:
    assert PaipanConfig(**values).huannian is Huannian.立春
  else:
    with pytest.raises(TypeError):
      PaipanConfig(**values)


def test_policy_aliases() -> None:
  for chinese, pinyin in (
    ("全月归下月", "XIAYUE"),
    ("全月归本月", "BENYUE"),
    ("上半月归本月下半月归下月", "BANYUE"),
  ):
    assert RunyueGuishu.__members__[chinese] is RunyueGuishu.__members__[pinyin]
  for chinese, pinyin in (("晚子时归次日", "WANZI_CIRI"), ("早晚子时同日", "ZAOWAN_TONGRI")):
    assert ZishiHuanri.__members__[chinese] is ZishiHuanri.__members__[pinyin]
  for chinese, pinyin in (("农历正月初一", "ZHENGYUE_CHUYI"), ("立春", "LICHUN")):
    assert Huannian.__members__[chinese] is Huannian.__members__[pinyin]
