"""宫位关系与已有盘的只读视图；原例、手推合成例和资源阻断分别验证。"""

import importlib.abc
import subprocess
import sys
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from importlib.machinery import ModuleSpec
from types import ModuleType
from typing import Any, Never

import pytest

from ziwei import calendar, chart, resolver, timezone
from ziwei.birth import Gender, LunarBirthRecord
from ziwei.chart import PalaceView, ZiweiChart, create_chart, palace_view
from ziwei.config import ChartConfig
from ziwei.ganzhi import Dizhi
from ziwei.knowledge import load_catalog
from ziwei.knowledge.model import DisplayEligibility, KnowledgeEntry, RuleVariant, Source, TextLayer
from ziwei.palaces import (
  OPPOSITE_RULE_ID,
  SANFANG_SIZHENG_RULE_ID,
  PalaceName,
  opposite_dizhi,
  sanfang_sizheng,
)
from ziwei.sihua import SihuaVariant
from ziwei.stars import Star

pytestmark = pytest.mark.usefixtures("unload_celestial")


# 按十二宫环手列，四成员顺序是项目约定；来源例子在下方另核，不反取待测函数。
@pytest.mark.parametrize(
  "base,opposite,members",
  [
    ("子", "午", "子辰申午"),
    ("丑", "未", "丑巳酉未"),
    ("寅", "申", "寅午戌申"),
    ("卯", "酉", "卯未亥酉"),
    ("辰", "戌", "辰申子戌"),
    ("巳", "亥", "巳酉丑亥"),
    ("午", "子", "午戌寅子"),
    ("未", "丑", "未亥卯丑"),
    ("申", "寅", "申子辰寅"),
    ("酉", "卯", "酉丑巳卯"),
    ("戌", "辰", "戌寅午辰"),
    ("亥", "巳", "亥卯未巳"),
  ],
)
def test_all_branch_relations(base: str, opposite: str, members: str) -> None:
  branch = Dizhi(base)
  result = sanfang_sizheng(branch)
  assert opposite_dizhi(branch) is Dizhi(opposite)
  assert result == tuple(Dizhi(value) for value in members)
  assert len(set(result)) == 4
  assert opposite_dizhi(opposite_dizhi(branch)) is branch


def test_source_palace_examples(lunar_chart: ZiweiChart) -> None:
  """两网页的命宫、夫妻宫例；只核成员，不把来源所列次序当API顺序。"""
  for name, names in (
    (PalaceName.命宫, (PalaceName.命宫, PalaceName.财帛, PalaceName.官禄, PalaceName.迁移)),
    (PalaceName.夫妻, (PalaceName.夫妻, PalaceName.迁移, PalaceName.福德, PalaceName.官禄)),
  ):
    base = palace_view(lunar_chart, name).palace.dizhi
    assert {
      palace_view(lunar_chart, branch).palace.name for branch in sanfang_sizheng(base)
    } == set(names)


@pytest.mark.parametrize("invalid", [None, True, 0, "子", PalaceName.命宫])
def test_relation_inputs_are_domain_members(invalid: Any) -> None:
  for function in (opposite_dizhi, sanfang_sizheng):
    with pytest.raises(TypeError):
      function(invalid)


def test_external_1954_views(lunar_chart: ZiweiChart, expected_1954: dict[Star, Dizhi]) -> None:
  """复用2007论坛1954例的独立28星期望；甲干四化另列字面期望。"""
  marks = {"lu": Star.廉贞, "quan": Star.破军, "ke": Star.武曲, "ji": Star.太阳}
  for palace in lunar_chart.palaces:
    view = palace_view(lunar_chart, palace.name)
    assert isinstance(view, PalaceView)
    assert view == palace_view(lunar_chart, palace.dizhi)
    assert view.palace is palace
    assert tuple(
      position.star for position in view.stars if position.star in expected_1954
    ) == tuple(
      star for star in Star if star in expected_1954 and expected_1954[star] is palace.dizhi
    )
    assert view.stars == tuple(p for p in lunar_chart.stars if p.dizhi is palace.dizhi)
    for field, star in marks.items():
      assert getattr(view, field) is (star if expected_1954[star] is palace.dizhi else None)
    assert view.is_shengong is (palace.dizhi is Dizhi.戌)
  assert palace_view(lunar_chart, PalaceName.夫妻) == palace_view(lunar_chart, PalaceName.妻妾)
  assert palace_view(lunar_chart, PalaceName.事业) == palace_view(lunar_chart, PalaceName.官禄)
  assert palace_view(lunar_chart, PalaceName.交友) == palace_view(lunar_chart, PalaceName.奴仆)


def test_hand_derived_empty_and_multiple_stars(chart_choices: ChartConfig) -> None:
  """合成甲子正月初一午时：命身申、壬申金四局，紫微亥、天府巳。

  依已登记口诀手推两星系及辅星，官禄子无星，命宫申为太阳、巨门、火星、月马；
  对宫午有天同、太阴，不借入空宫。此例不是外部原盘。
  """
  result = create_chart(
    LunarBirthRecord(
      year=1984, month=1, day=1, is_leap_month=False, shichen=Dizhi.午, gender=Gender.女
    ),
    chart_choices,
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  empty = palace_view(result, PalaceName.官禄)
  assert empty.palace.dizhi is Dizhi.子
  assert empty.stars == ()
  assert (empty.lu, empty.quan, empty.ke, empty.ji) == (None, None, None, None)
  assert empty.is_shengong is False
  assert tuple(p.star for p in palace_view(result, Dizhi.午).stars) == (Star.天同, Star.太阴)
  ming = palace_view(result, PalaceName.命宫)
  assert ming.palace.dizhi is Dizhi.申 and ming.is_shengong is True
  assert tuple(p.star for p in ming.stars) == (Star.太阳, Star.巨门, Star.火星, Star.天马)
  assert (ming.lu, ming.quan, ming.ke, ming.ji) == (None, None, None, Star.太阳)


def test_hongluan_shengong_is_not_minggong(chart_choices: ChartConfig) -> None:
  """合成甲午正月初一未时：命未、身酉叠福德；原28星不落酉，新增红鸾在酉。"""
  result = create_chart(
    LunarBirthRecord(
      year=1954, month=1, day=1, is_leap_month=False, shichen=Dizhi.未, gender=Gender.女
    ),
    chart_choices,
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  ming = palace_view(result, PalaceName.命宫)
  assert ming.palace.dizhi is Dizhi.未 and ming.is_shengong is False
  shen = palace_view(result, PalaceName.福德)
  assert shen.palace.dizhi is Dizhi.酉 and shen.is_shengong is True
  assert tuple(p.star for p in shen.stars) == (Star.红鸾,)
  assert (shen.lu, shen.quan, shen.ke, shen.ji) == (None, None, None, None)
  for palace in result.palaces:
    view = palace_view(result, palace.name)
    assert view == palace_view(result, palace.dizhi)
    assert view.is_shengong is (palace.dizhi is Dizhi.酉)


def test_empty_shengong_is_not_minggong(chart_choices: ChartConfig) -> None:
  """合成甲子二月初二酉时：命午、身子叠迁移，用于查询空身宫，不作外部安星盘例。"""
  result = create_chart(
    LunarBirthRecord(
      year=1984, month=2, day=2, is_leap_month=False, shichen=Dizhi.酉, gender=Gender.女
    ),
    chart_choices,
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  ming = palace_view(result, PalaceName.命宫)
  shen = palace_view(result, PalaceName.迁移)
  assert ming.palace.dizhi is Dizhi.午 and not ming.is_shengong
  assert shen.palace.dizhi is Dizhi.子 and shen.is_shengong
  assert shen.stars == ()
  assert (shen.lu, shen.quan, shen.ke, shen.ji) == (None, None, None, None)


@pytest.mark.parametrize(
  "variant,expected",
  [
    (SihuaVariant.排命盘口诀转录, (Star.太阳, Star.武曲, Star.天同, Star.太阴)),
    (SihuaVariant.王亭之讲义转录, (Star.太阳, Star.武曲, Star.天府, Star.天同)),
  ],
)
def test_view_uses_the_selected_geng_sihua(
  chart_choices: ChartConfig, variant: SihuaVariant, expected: tuple[Star, Star, Star, Star]
) -> None:
  result = create_chart(
    LunarBirthRecord(
      year=1980, month=1, day=1, is_leap_month=False, shichen=Dizhi.子, gender=Gender.女
    ),
    chart_choices,
    sihua_variant=variant,
  )
  for field, star in zip(("lu", "quan", "ke", "ji"), expected, strict=True):
    marked = [getattr(palace_view(result, p.name), field) for p in result.palaces]
    assert [mark for mark in marked if mark is not None] == [star]


@pytest.mark.parametrize("invalid", [None, True, 0, "命宫", "戌", Star.紫微])
def test_view_rejects_non_palace_inputs(lunar_chart: ZiweiChart, invalid: Any) -> None:
  with pytest.raises(TypeError):
    palace_view(lunar_chart, invalid)
  with pytest.raises(TypeError):
    palace_view(invalid, Dizhi.子)


def test_view_is_immutable_and_isolates_star_sequences(lunar_chart: ZiweiChart) -> None:
  view = palace_view(lunar_chart, PalaceName.命宫)
  caller_stars = list(view.stars)
  copied = replace(view, stars=caller_stars)  # type: ignore[arg-type]
  caller_stars.clear()
  assert copied == view and isinstance(copied.stars, tuple)
  with pytest.raises(FrozenInstanceError):
    view.is_shengong = False  # type: ignore[misc]
  with pytest.raises(FrozenInstanceError):
    view.stars[0].dizhi = Dizhi.子  # type: ignore[misc]


@pytest.mark.parametrize(
  "changes,error",
  [
    ({"palace": "命宫"}, TypeError),
    ({"stars": ["紫微"]}, TypeError),
    ({"is_shengong": 1}, TypeError),
    ({"lu": "巨门"}, TypeError),
    ({"lu": Star.太阳}, ValueError),
  ],
)
def test_view_constructor_rejects_invalid_fields(
  lunar_chart: ZiweiChart, changes: dict[str, Any], error: type[Exception]
) -> None:
  with pytest.raises(error):
    replace(palace_view(lunar_chart, PalaceName.命宫), **changes)


def test_view_constructor_rejects_inconsistent_contents(lunar_chart: ZiweiChart) -> None:
  view = palace_view(lunar_chart, PalaceName.命宫)
  with pytest.raises(ValueError, match="不可重复"):
    replace(view, stars=(*view.stars, view.stars[0]))
  with pytest.raises(ValueError, match="属于视图"):
    replace(view, stars=palace_view(lunar_chart, PalaceName.夫妻).stars)
  with pytest.raises(ValueError, match="多个生年四化"):
    replace(view, lu=view.stars[0].star, quan=view.stars[0].star)


def test_queries_do_not_recompute_or_load_resources(
  lunar_chart: ZiweiChart, monkeypatch: pytest.MonkeyPatch
) -> None:
  before = deepcopy(lunar_chart)

  def forbidden(*args: object, **kwargs: object) -> Never:
    raise AssertionError("只读查询调用了重算或资源入口")

  class RejectResources(importlib.abc.MetaPathFinder):
    def find_spec(
      self, fullname: str, path: Sequence[str] | None = None, target: ModuleType | None = None
    ) -> ModuleSpec | None:
      if fullname.split(".")[0] in ("celestial_calendar", "tzdata"):
        raise AssertionError("只读查询导入了历法或时区资源")
      return None

  for owner, names in (
    (
      chart,
      (
        "resolve",
        "create_chart",
        "place_stars",
        "shengnian_sihua",
        "place_decades",
        "twelve_palaces",
        "shengong_dizhi",
        "_chart_frame",
      ),
    ),
    (resolver, ("resolve",)),
    (
      calendar,
      (
        "validate_lunar_date",
        "gregorian_to_lunar",
        "lunar_to_gregorian",
        "lichun_jd",
        "utc_to_ut1_jd",
        "apparent_solar",
        "celestial_version",
      ),
    ),
    (timezone, ("_load_zone", "current_timezone_data", "resolve_civil_time")),
  ):
    for name in names:
      monkeypatch.setattr(owner, name, forbidden)
  for name in tuple(sys.modules):
    if name.split(".")[0] in ("celestial_calendar", "tzdata"):
      monkeypatch.delitem(sys.modules, name)
  monkeypatch.setattr(sys, "meta_path", [RejectResources(), *sys.meta_path])
  for palace in lunar_chart.palaces:
    view = palace_view(lunar_chart, palace.name)
    assert view.palace is palace
    assert view == palace_view(lunar_chart, palace.dizhi)
    assert len(sanfang_sizheng(palace.dizhi)) == 4
    assert opposite_dizhi(opposite_dizhi(palace.dizhi)) is palace.dizhi
  assert lunar_chart == before


def test_relation_knowledge_has_stable_identity_and_explicit_limits() -> None:
  catalog = load_catalog()
  assert OPPOSITE_RULE_ID == "variant.palace.opposite"
  assert SANFANG_SIZHENG_RULE_ID == "variant.palace.sanfang-sizheng"
  citations = {
    "opposite": ("citation.ntnu.palace-opposite", "citation.andy.sanfang-sizheng-minggong"),
    "sanfang-sizheng": (
      "citation.ntnu.sanfang-sizheng",
      "citation.andy.sanfang-sizheng-minggong",
      "citation.andy.sanfang-sizheng-qiqie",
    ),
  }
  for suffix, function in (("opposite", "opposite_dizhi"), ("sanfang-sizheng", "sanfang_sizheng")):
    variant = catalog.get(f"variant.palace.{suffix}")
    assert isinstance(variant, RuleVariant)
    assert variant.concept_ids == (f"concept.palace.{suffix}",)
    assert variant.implementation == f"ziwei.palaces.{function}"
    entry = catalog.get(f"entry.palace.{suffix}")
    assert isinstance(entry, KnowledgeEntry)
    assert entry.variant_ids == (f"variant.palace.{suffix}",)
    assert entry.citation_ids == citations[suffix]
    assert entry.display is DisplayEligibility.暂不默认展示
    assert entry.recheck and entry.tracking_url.endswith("/issues/39")
  for identifier in ("source.ntnu-palace-glossary", "source.andy-sanfang-sizheng"):
    source = catalog.get(identifier)
    assert isinstance(source, Source) and source.layer is TextLayer.今人说明
    assert "未核" in source.provenance and "SHA256" in source.edition


def test_relations_and_knowledge_load_without_chart_or_native_resources() -> None:
  script = """
import importlib.abc
import sys
class Block(importlib.abc.MetaPathFinder):
  def find_spec(self, fullname, path=None, target=None):
    if fullname == 'ziwei.chart' or fullname.split('.')[0] in ('celestial_calendar', 'tzdata'):
      raise AssertionError('unexpected dependency: ' + fullname)
sys.meta_path.insert(0, Block())
from ziwei.ganzhi import Dizhi
from ziwei.palaces import opposite_dizhi, sanfang_sizheng
from ziwei.knowledge import load_catalog
assert opposite_dizhi(Dizhi.子) is Dizhi.午
assert sanfang_sizheng(Dizhi.寅) == (Dizhi.寅, Dizhi.午, Dizhi.戌, Dizhi.申)
assert load_catalog().get('variant.palace.sanfang-sizheng').implementation == 'ziwei.palaces.sanfang_sizheng'
assert 'ziwei.chart' not in sys.modules
print('RELATIONS_ONLY')
"""
  result = subprocess.run(
    [sys.executable, "-c", script], capture_output=True, text=True, check=False
  )
  assert result.returncode == 0, result.stdout + result.stderr
  assert result.stdout.strip() == "RELATIONS_ONLY"
