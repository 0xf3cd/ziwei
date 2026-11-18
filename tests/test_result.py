"""结果JSON按值往返、能被纯JSON读者读出，矛盾与无法无损表示的输入按路径拒绝。"""

import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import fields, replace
from pathlib import Path
from typing import Any, TypeVar

import pytest

from ziwei.birth import LunarBirthRecord
from ziwei.brightness import BrightnessTable
from ziwei.chart import ZiweiChart, chart_brightness, liunian_palaces
from ziwei.ganzhi import Dizhi
from ziwei.liunian import liunian_sihua, liunian_stars
from ziwei.result import (
  ChartResult,
  ResultBrightness,
  ResultDecade,
  ResultDecades,
  ResultLiunian,
  ResultLiunianPalace,
  ResultPalace,
  ResultSihua,
  ResultStar,
  ResultYunxian,
  dumps,
  loads,
  result_of,
)
from ziwei.sihua import SihuaVariant
from ziwei.stars import Star
from ziwei.tongxian import TongxianBoundary
from ziwei.yunxian import yunxian_at_age

FIXTURES = Path(__file__).parent / "fixtures"
TABLE = BrightnessTable.全书卷二录文
BOUNDARY = TongxianBoundary.起限当岁不含
VARIANT = SihuaVariant.王亭之讲义转录
# lunar_chart是火六局：1、4岁在首限之前且仍在童限内，30、60岁有大限。
AGES = (1, 4, 30, 60)
YEARS = (2024, 2025)
Document = dict[str, Any]
_T = TypeVar("_T")


@pytest.fixture
def full(lunar_chart: ZiweiChart) -> ChartResult:
  return result_of(
    lunar_chart,
    brightness_table=TABLE,
    ages=AGES,
    tongxian_boundary=BOUNDARY,
    years=YEARS,
    liunian_sihua_variant=VARIANT,
  )


def document(result: ChartResult) -> Document:
  value: Document = json.loads(dumps(result))
  return value


def test_plain_json_reader_finds_the_chart_readings(
  lunar_chart: ZiweiChart, full: ChartResult
) -> None:
  # 这个读者只用标准库json，按字段约定逐层取值，与运行时命盘的查询结果对照。
  data = document(full)
  chart = lunar_chart
  assert [(p["name"], p["tiangan"], p["dizhi"]) for p in data["palaces"]] == [
    (p.name.value, p.tiangan.value, p.dizhi.value) for p in chart.palaces
  ]
  assert (data["shengong"], data["bureau"]) == (chart.shengong.value, chart.bureau.value)
  assert [(s["star"], s["dizhi"]) for s in data["stars"]] == [
    (p.star.value, p.dizhi.value) for p in chart.stars
  ]
  assert data["sihua"] == {
    "lu": chart.sihua.lu.value,
    "quan": chart.sihua.quan.value,
    "ke": chart.sihua.ke.value,
    "ji": chart.sihua.ji.value,
  }
  assert data["decades"]["direction"] == chart.decades[0].direction.value
  assert data["decades"]["age_convention"] == "虚岁"
  assert [(d["dizhi"], d["start_age"], d["end_age"]) for d in data["decades"]["periods"]] == [
    (d.dizhi.value, d.start_age, d.end_age) for d in chart.decades
  ]
  assert {b["star"]: b["level"] for b in data["brightness"]} == {
    r.star.value: r.level.value for r in chart_brightness(chart, table=TABLE) if r.level is not None
  }
  for item, age in zip(data["yunxian"], AGES, strict=True):
    expected = yunxian_at_age(chart, age, tongxian_boundary=BOUNDARY)
    decade = None if expected.decade is None else expected.decade.dizhi.value
    tongxian = None if expected.tongxian.dizhi is None else expected.tongxian.dizhi.value
    assert item == {
      "age": age,
      "xiaoxian": expected.xiaoxian.dizhi.value,
      "tongxian": tongxian,
      "decade": decade,
    }
  for item, year in zip(data["liunian"], YEARS, strict=True):
    stars = liunian_stars(year)
    annual = liunian_sihua(year, variant=VARIANT)
    assert item["ganzhi_year"] == year
    assert [(p["name"], p["dizhi"]) for p in item["palaces"]] == [
      (view.name.value, view.dizhi.value) for view in liunian_palaces(chart, year)
    ]
    assert (item["lucun"], item["qingyang"], item["tuoluo"]) == (
      stars.lucun.value,
      stars.qingyang.value,
      stars.tuoluo.value,
    )
    assert item["sihua"] == {
      "lu": annual.lu.value,
      "quan": annual.quan.value,
      "ke": annual.ke.value,
      "ji": annual.ji.value,
    }
  # 两层四化分开存放：2025年的化禄与生年化禄不是同一颗星。
  assert data["liunian"][1]["sihua"]["lu"] != data["sihua"]["lu"]


def test_round_trip_compares_values_and_text(full: ChartResult) -> None:
  text = dumps(full)
  assert loads(text) == full
  assert dumps(loads(text)) == text
  assert text.endswith("\n") and "紫微" in text and "\\u" not in text


def test_omitted_and_empty_layers_stay_distinct(lunar_chart: ZiweiChart) -> None:
  bare = result_of(lunar_chart)
  assert set(document(bare)) == {"palaces", "shengong", "bureau", "stars", "sihua", "decades"}
  assert (loads(dumps(bare)).yunxian, loads(dumps(bare)).liunian) == (None, None)
  empty = result_of(lunar_chart, ages=(), tongxian_boundary=BOUNDARY, years=())
  assert (document(empty)["yunxian"], document(empty)["liunian"]) == ([], [])
  assert (loads(dumps(empty)).yunxian, loads(dumps(empty)).liunian) == ((), ())
  without_annual = result_of(lunar_chart, years=(2024,))
  assert document(without_annual)["liunian"][0]["sihua"] is None


def test_output_carries_only_readings(lunar_chart: ZiweiChart, full: ChartResult) -> None:
  data = document(full)
  assert list(data) == [
    "palaces",
    "shengong",
    "bureau",
    "stars",
    "sihua",
    "decades",
    "brightness",
    "yunxian",
    "liunian",
  ]
  assert {key for p in data["palaces"] for key in p} == {"name", "tiangan", "dizhi"}
  assert {key for s in data["stars"] for key in s} == {"star", "dizhi"}
  assert set(data["decades"]) == {"direction", "age_convention", "periods"}
  assert {key for b in data["brightness"] for key in b} == {"star", "level"}
  assert {key for y in data["yunxian"] for key in y} == {"age", "xiaoxian", "tongxian", "decade"}
  assert {key for y in data["liunian"] for key in y} == {
    "ganzhi_year",
    "palaces",
    "lucun",
    "qingyang",
    "tuoluo",
    "sihua",
  }
  text = dumps(full)
  record = lunar_chart.calculation.record
  assert isinstance(record, LunarBirthRecord) and record.source is not None
  assert str(record.year) not in text and record.source not in text


@pytest.mark.parametrize(
  "choices",
  [
    {"tongxian_boundary": BOUNDARY},
    {"ages": (1,)},
    {"liunian_sihua_variant": VARIANT},
  ],
)
def test_export_rejects_a_selection_without_its_layer(
  lunar_chart: ZiweiChart, choices: dict[str, Any]
) -> None:
  with pytest.raises(ValueError):
    result_of(lunar_chart, **choices)


@pytest.mark.parametrize("bad", [None, b"{}", object()])
def test_export_and_write_reject_other_objects(bad: Any) -> None:
  with pytest.raises(TypeError):
    result_of(bad)
  with pytest.raises(TypeError):
    dumps(bad)
  with pytest.raises(TypeError):
    loads(bad)


def _remove_star(data: Document, star: Star) -> None:
  data["stars"] = [item for item in data["stars"] if item["star"] != star.value]


def _swap_names(palaces: list[Document]) -> None:
  palaces[0]["name"], palaces[1]["name"] = palaces[1]["name"], palaces[0]["name"]


def _repeat_dizhi(data: Document) -> None:
  # 隔一宫的地支阴阳相同，只制造重复，不触发干支阴阳检查。
  data["palaces"][2]["dizhi"] = data["palaces"][0]["dizhi"]
  data["palaces"][2]["tiangan"] = data["palaces"][0]["tiangan"]


def _wrong_parity(data: Document) -> None:
  data["palaces"][0]["tiangan"] = "乙" if data["palaces"][0]["tiangan"] == "甲" else "甲"


def _shift_decade(data: Document) -> None:
  period = data["decades"]["periods"][1]
  period["start_age"] += 1
  period["end_age"] += 1


def _flip_direction(data: Document) -> None:
  data["decades"]["direction"] = "逆行" if data["decades"]["direction"] == "顺行" else "顺行"


def _wrong_decade(data: Document) -> None:
  data["yunxian"][2]["decade"] = data["decades"]["periods"][0]["dizhi"]


def _unplace_annual_lu(data: Document) -> None:
  # 2025年化禄是天机；天机是主星，亮度层也引用它。先去掉亮度层，矛盾只留在年度四化。
  data.pop("brightness")
  _remove_star(data, Star.天机)


MUTATIONS: list[tuple[str, Callable[[Document], None], str]] = [
  ("unknown-key", lambda d: d.update(version="0.6.0"), "$.version: 不认识的键"),
  ("missing-key", lambda d: d.pop("bureau"), "$.bureau: 缺少此键"),
  ("nested-unknown-key", lambda d: d["stars"][0].update(rule_id="x"), "$.stars[0].rule_id: "),
  ("string-age", lambda d: d["yunxian"][0].update(age="1"), "$.yunxian[0].age: 须为整数"),
  ("bool-age", lambda d: d["yunxian"][0].update(age=True), "$.yunxian[0].age: 须为整数"),
  ("float-age", lambda d: d["yunxian"][0].update(age=1.0), "$.yunxian[0].age: 须为整数"),
  ("zero-age", lambda d: d["yunxian"][0].update(age=0), "$.yunxian[0].age: 虚岁须为正整数"),
  (
    "zero-start-age",
    lambda d: d["decades"]["periods"][0].update(start_age=0),
    "$.decades.periods[0].start_age: 虚岁须为正整数",
  ),
  (
    "zero-year",
    lambda d: d["liunian"][0].update(ganzhi_year=0),
    "$.liunian[0].ganzhi_year: 纪年须为正整数",
  ),
  ("unknown-star", lambda d: d["stars"][0].update(star="紫薇"), "$.stars[0].star: 不认识的值"),
  ("member-name", lambda d: d["stars"][0].update(star="ZIWEI"), "$.stars[0].star: 不认识的值"),
  ("astral-star", lambda d: d["stars"][0].update(star="\U00020000"), "$.stars[0].star: 不认识"),
  ("not-array", lambda d: d.update(stars={}), "$.stars: 须为JSON数组"),
  ("not-object", lambda d: d.update(sihua=[]), "$.sihua: 须为JSON对象"),
  ("null-required", lambda d: d.update(shengong=None), "$.shengong: 须为字符串"),
  ("parity", _wrong_parity, "$.palaces[0].dizhi: 宫干支阴阳不相配"),
  ("palace-order", lambda d: _swap_names(d["palaces"]), "$.palaces[0].name: 须按宫名序"),
  ("palace-repeat", _repeat_dizhi, "$.palaces: 各宫地支不得重复"),
  ("palace-count", lambda d: d["palaces"].pop(), "$.palaces: 须有12宫，实际11宫"),
  ("star-repeat", lambda d: d["stars"].append(d["stars"][0]), "$.stars: 星曜不得重复"),
  ("sihua-unplaced", lambda d: _remove_star(d, Star.廉贞), "$.sihua.lu: 须是本结果星位中的星"),
  ("sihua-repeat", lambda d: d["sihua"].update(ji=d["sihua"]["lu"]), "$.sihua.ji: 与lu是同一颗星"),
  ("brightness-unplaced", lambda d: _remove_star(d, Star.天府), "$.brightness[6].star: 须是本结果"),
  (
    "brightness-repeat",
    lambda d: d["brightness"].append(d["brightness"][0]),
    "$.brightness: 星曜不得重复",
  ),
  ("decade-gap", _shift_decade, "$.decades.periods[1].start_age: 须紧接上一限"),
  (
    "decade-length",
    lambda d: d["decades"]["periods"][0].update(end_age=16),
    "$.decades.periods[0].end_age: 一限首尾包含共十年",
  ),
  ("decade-direction", _flip_direction, "$.decades.periods[1].dizhi: 须按行运方向"),
  ("decade-count", lambda d: d["decades"]["periods"].pop(), "$.decades.periods: 须有12限"),
  (
    "age-convention",
    lambda d: d["decades"].update(age_convention="周岁"),
    "$.decades.age_convention: 大限年龄只用虚岁",
  ),
  ("yunxian-decade", _wrong_decade, "$.yunxian[2].decade: 须是覆盖该虚岁的大限地支"),
  (
    "yunxian-missing-decade",
    lambda d: d["yunxian"][2].update(decade=None),
    "$.yunxian[2].decade: 首限开始后须给出大限",
  ),
  ("age-repeat", lambda d: d["yunxian"].append(d["yunxian"][0]), "$.yunxian: 虚岁不得重复"),
  ("year-repeat", lambda d: d["liunian"].append(d["liunian"][0]), "$.liunian: 纪年不得重复"),
  (
    "liunian-palace-order",
    lambda d: _swap_names(d["liunian"][0]["palaces"]),
    "$.liunian[0].palaces[0].name: 须按宫名序",
  ),
  (
    "liunian-sihua-unplaced",
    _unplace_annual_lu,
    "$.liunian[1].sihua.lu: 须是本结果星位中的星",
  ),
]


@pytest.mark.parametrize(
  ("mutate", "message"), [m[1:] for m in MUTATIONS], ids=[m[0] for m in MUTATIONS]
)
def test_reading_rejects_defects_at_their_json_path(
  full: ChartResult, mutate: Callable[[Document], None], message: str
) -> None:
  data = document(full)
  mutate(data)
  with pytest.raises(ValueError) as error:
    loads(json.dumps(data, ensure_ascii=False))
  assert str(error.value).startswith(message)


@pytest.mark.parametrize(
  ("old", "new", "message"),
  [
    ('"bureau": ', '"bureau": "水二局", "bureau": ', "$.bureau: 键重复"),
    ('"age": 30', '"age": NaN', "结果JSON不接受NaN"),
    ('"age": 30', '"age": Infinity', "结果JSON不接受Infinity"),
    ('"紫微"', '"\\ud800"', "$.stars[0].star: 不认识的值"),
  ],
)
def test_reading_rejects_text_that_cannot_round_trip(
  full: ChartResult, old: str, new: str, message: str
) -> None:
  text = dumps(full)
  assert old in text
  with pytest.raises(ValueError) as error:
    loads(text.replace(old, new, 1))
  assert str(error.value).startswith(message)


def test_reading_rejects_a_non_object_document() -> None:
  with pytest.raises(ValueError, match=r"^\$: 须为JSON对象"):
    loads("[]")


def test_reading_keeps_results_that_current_rules_would_not_produce(full: ChartResult) -> None:
  # 读取不按现行规则重算：改过星位或少了未被引用的星，仍按原值读回。
  data = document(full)
  data["stars"][0]["dizhi"], data["stars"][1]["dizhi"] = (
    data["stars"][1]["dizhi"],
    data["stars"][0]["dizhi"],
  )
  _remove_star(data, Star.天使)
  result = loads(json.dumps(data, ensure_ascii=False))
  assert ResultStar(star=Star.天使, dizhi=Dizhi.戌) not in result.stars
  assert result.stars[0].dizhi is full.stars[1].dizhi


@pytest.mark.parametrize("mode", [(), ("-O",)])
def test_reading_in_a_process_without_birth_or_calendar_modules(
  full: ChartResult, tmp_path: Path, mode: tuple[str, ...]
) -> None:
  saved = tmp_path / "result.json"
  saved.write_text(dumps(full), encoding="utf-8")
  completed = subprocess.run(
    (sys.executable, *mode, "-I", str(FIXTURES / "result_isolation.py"), str(saved)),
    capture_output=True,
    text=True,
  )
  assert completed.returncode == 0, completed.stderr


def first(items: Sequence[_T] | None) -> _T:
  assert items
  return items[0]


# 每类读数记录从完整结果中取一个实例。
SAMPLES: dict[type, Callable[[ChartResult], Any]] = {
  ResultPalace: lambda r: r.palaces[0],
  ResultStar: lambda r: r.stars[0],
  ResultSihua: lambda r: r.sihua,
  ResultBrightness: lambda r: first(r.brightness),
  ResultDecade: lambda r: r.decades.periods[0],
  ResultDecades: lambda r: r.decades,
  ResultYunxian: lambda r: first(r.yunxian),
  ResultLiunianPalace: lambda r: first(r.liunian).palaces[0],
  ResultLiunian: lambda r: first(r.liunian),
  ChartResult: lambda r: r,
}
# age_convention是字面量，错值抛ValueError，见MUTATIONS的age-convention。
TYPED_FIELDS = [
  (kind, item.name) for kind in SAMPLES for item in fields(kind) if item.name != "age_convention"
]


@pytest.mark.parametrize(
  ("kind", "name"), TYPED_FIELDS, ids=[f"{kind.__name__}.{name}" for kind, name in TYPED_FIELDS]
)
def test_direct_construction_rejects_wrong_types_without_a_json_path(
  full: ChartResult, kind: type, name: str
) -> None:
  with pytest.raises(TypeError, match=rf"^{name}(\[0\])?: 须为"):
    replace(SAMPLES[kind](full), **{name: "紫微"})
