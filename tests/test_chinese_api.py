"""中文名称保持原类型、字段及只读结果。"""

import ast
import inspect
import pickle
import textwrap
from dataclasses import fields, is_dataclass, replace
from datetime import date
from enum import Enum
from importlib import import_module
from typing import Any, get_args

import pytest

from ziwei.birth import 农历出生记录, 性别
from ziwei.brightness import BrightnessTable, star_brightness
from ziwei.bureau import WuxingJu
from ziwei.calendar import LunarAlgorithm
from ziwei.chart import ZiweiChart, liunian_palaces, liunian_view, palace_view
from ziwei.config import POLICY_ENUMS, 口径选项
from ziwei.ganzhi import Dizhi, Ganzhi, Tiangan, 地支
from ziwei.liunian import LiunianBoundary, liunian_on_date, liunian_sihua, 流年星曜
from ziwei.palaces import PalaceName
from ziwei.sihua import SihuaVariant
from ziwei.stars import Star
from ziwei.tongxian import TongxianBoundary, tongxian_at_age
from ziwei.xiaoxian import xiaoxian_at_age
from ziwei.yunxian import yunxian_at_age

pytestmark = pytest.mark.usefixtures("unload_celestial")

ALIASES = {
  "birth": "性别:Gender 公历出生记录:GregorianBirthRecord 农历出生记录:LunarBirthRecord "
  "出生记录:BirthRecord 计算输入:CalculationInput",
  "config": "闰月归属:LeapMonthPolicy 子时换日:DayRollover 换年界线:YearBoundary "
  "天马规则:TianmaRule 命盘配置:ChartConfig 口径选项:PolicyOption",
  "ganzhi": "阴阳:Yinyang 天干:Tiangan 地支:Dizhi 干支:Ganzhi 五行:Wuxing",
  "palaces": "宫名:PalaceName 宫位:Palace",
  "bureau": "五行局:WuxingJu",
  "stars": "星曜:Star 安星规则:StarRule 星位:StarPlacement",
  "brightness": "亮度等级:BrightnessLevel 亮度表:BrightnessTable 亮度读数:BrightnessReading",
  "sihua": "四化变体:SihuaVariant 四化表:SihuaTable 四化结果:SihuaResult",
  "decades": "行运方向:Direction 大限:Decade",
  "liunian": "流年星曜:LiunianStars 流年年界:LiunianBoundary 流年区间:LiunianYear 流年四化:LiunianSihua",
  "xiaoxian": "小限:Xiaoxian",
  "tongxian": "童限边界:TongxianBoundary 童限:Tongxian",
  "yunxian": "运限:Yunxian",
  "chart": "紫微命盘:ZiweiChart 宫位视图:PalaceView 流年叠读:LiunianView 流年宫位:LiunianPalaceView",
}
PROPERTIES = {
  "birth.CalculationInput": "原始记录:record 农历年:lunar_year 农历月:month 农历日:day "
  "闰月:is_leap_month 时辰:shichen 纪年:ganzhi_year 命盘配置:config 性别:gender "
  "年干支:year_ganzhi 年干阴阳:yinyang",
  "ganzhi.Tiangan": "阴阳:yinyang",
  "ganzhi.Ganzhi": "天干:tiangan 地支:dizhi",
  "palaces.Palace": "地支:dizhi 天干:tiangan 宫名:name 干支:ganzhi",
  "bureau.WuxingJu": "局数:number",
  "stars.StarPlacement": "星曜:star 地支:dizhi",
  "brightness.BrightnessReading": "星曜:star 地支:dizhi 亮度表:table 等级:level",
  "sihua.SihuaResult": "年干:year_tiangan 变体:variant 化禄:lu 化权:quan 化科:ke 化忌:ji",
  "decades.Decade": "地支:dizhi 行运方向:direction 起始虚岁:start_age 终止虚岁:end_age",
  "liunian.LiunianStars": "纪年:ganzhi_year 禄存:lucun 擎羊:qingyang 陀罗:tuoluo 年干支:year_ganzhi",
  "liunian.LiunianYear": "纪年:ganzhi_year 年界:boundary 起始日期:start 终止日期:end "
  "年干支:year_ganzhi 命宫:minggong",
  "liunian.LiunianSihua": "纪年:ganzhi_year 年干支:year_ganzhi 年干:year_tiangan 变体:variant "
  "化禄:lu 化权:quan 化科:ke 化忌:ji",
  "xiaoxian.Xiaoxian": "生年支:year_dizhi 性别:gender 虚岁:age 地支:dizhi",
  "tongxian.Tongxian": "命宫:minggong 五行局:ju 虚岁:age 边界:boundary 宫名:palace_name 地支:dizhi",
  "yunxian.Yunxian": "小限:xiaoxian 童限:tongxian 大限:decade",
  "chart.ZiweiChart": "计算输入:calculation 十二宫:palaces 身宫:shengong 五行局:bureau "
  "星位:stars 生年四化:sihua 大限:decades",
  "chart.PalaceView": "宫位:palace 星位:stars 化禄:lu 化权:quan 化科:ke 化忌:ji 是否身宫:is_shengong",
  "chart.LiunianView": "流年:liunian 本命宫:natal",
  "chart.LiunianPalaceView": "纪年:ganzhi_year 宫名:name 地支:dizhi 本命宫:natal 流年四化:sihua "
  "化禄:lu 化权:quan 化科:ke 化忌:ji",
}


def pairs(names: str) -> tuple[tuple[str, str], ...]:
  return tuple((value.split(":")[0], value.split(":")[1]) for value in names.split())


@pytest.mark.parametrize(
  "module,chinese,original",
  [
    (module, chinese, original)
    for module, names in ALIASES.items()
    for chinese, original in pairs(names)
  ],
)
def test_alias_is_original_type(module: str, chinese: str, original: str) -> None:
  api = import_module(f"ziwei.{module}")
  alias, source = getattr(api, chinese), getattr(api, original)
  assert alias is source
  if isinstance(source, type):
    if issubclass(source, Enum):
      assert all(alias[name] is member for name, member in source.__members__.items())
  else:
    assert pickle.loads(pickle.dumps(alias)) == source


def test_chinese_policy_union_contains_the_validated_policy_types() -> None:
  assert get_args(口径选项) == POLICY_ENUMS


@pytest.fixture
def result_samples(lunar_chart: ZiweiChart) -> dict[str, tuple[Any, ...]]:
  chart = lunar_chart
  values = chart.calculation
  record = values.record
  assert isinstance(record, 农历出生记录)
  unknown = replace(values, record=replace(record, shichen=None, gender=性别.未知), shichen=None)
  table = BrightnessTable.全书卷二录文
  boundary = TongxianBoundary.起限当岁不含
  return {
    "birth.CalculationInput": (values, unknown),
    "ganzhi.Tiangan": tuple(Tiangan),
    "ganzhi.Ganzhi": (Ganzhi(Tiangan.甲, Dizhi.子), Ganzhi(Tiangan.乙, Dizhi.丑)),
    "palaces.Palace": chart.palaces,
    "bureau.WuxingJu": tuple(WuxingJu),
    "stars.StarPlacement": chart.stars,
    "brightness.BrightnessReading": (
      star_brightness(Star.紫微, Dizhi.子, table=table),
      star_brightness(Star.文昌, Dizhi.子, table=table),
    ),
    "sihua.SihuaResult": (chart.sihua,),
    "decades.Decade": chart.decades,
    "liunian.LiunianStars": (流年星曜(2024), 流年星曜(2012)),
    "liunian.LiunianSihua": tuple(
      liunian_sihua(year, variant=SihuaVariant.王亭之讲义转录) for year in (2024, 2030)
    ),
    "liunian.LiunianYear": (
      liunian_on_date(date(2024, 2, 4), boundary=LiunianBoundary.立春日期),
      liunian_on_date(
        date(2024, 2, 4), boundary=LiunianBoundary.正月初一日期, lunar_algorithm=LunarAlgorithm.混合
      ),
    ),
    "xiaoxian.Xiaoxian": (xiaoxian_at_age(Dizhi.寅, 性别.女, 3),),
    "tongxian.Tongxian": tuple(
      tongxian_at_age(Dizhi.辰, WuxingJu.木三局, age, boundary=policy)
      for policy in TongxianBoundary
      for age in (1, 3, 4)
    ),
    "yunxian.Yunxian": tuple(
      yunxian_at_age(chart, age, tongxian_boundary=boundary) for age in (1, 6)
    ),
    "chart.ZiweiChart": (chart,),
    "chart.PalaceView": tuple(palace_view(chart, name) for name in PalaceName),
    "chart.LiunianView": (liunian_view(chart, 2024),),
    "chart.LiunianPalaceView": (
      *liunian_palaces(chart, 2030),
      *liunian_palaces(chart, 2028, sihua_variant=SihuaVariant.王亭之讲义转录),
    ),
  }


@pytest.mark.parametrize(
  "owner,chinese,original",
  [
    (owner, chinese, original)
    for owner, names in PROPERTIES.items()
    for chinese, original in pairs(names)
  ],
)
def test_readonly_properties_read_original_member_without_storage(
  result_samples: dict[str, tuple[Any, ...]], owner: str, chinese: str, original: str
) -> None:
  for value in result_samples[owner]:
    descriptor = vars(type(value))[chinese]
    assert isinstance(descriptor, property)
    assert descriptor.fset is None and descriptor.fdel is None and descriptor.fget is not None
    function = ast.parse(textwrap.dedent(inspect.getsource(descriptor.fget))).body[0]
    assert isinstance(function, ast.FunctionDef) and function.returns is not None
    assert ast.dump(function.body[0]) == ast.dump(
      ast.Return(
        value=ast.Attribute(
          value=ast.Name(id="self", ctx=ast.Load()), attr=original, ctx=ast.Load()
        )
      )
    )
    assert len(function.body) == 1
    if is_dataclass(value):
      assert chinese not in {field.name for field in fields(value)}
    expected = getattr(value, original)
    actual = getattr(value, chinese)
    assert actual == expected
    if not isinstance(inspect.getattr_static(type(value), original), property):
      assert actual is expected
    before = repr(value)
    with pytest.raises((AttributeError, TypeError)):
      setattr(value, chinese, None)
    with pytest.raises((AttributeError, TypeError)):
      delattr(value, chinese)
    assert repr(value) == before and pickle.loads(pickle.dumps(value)) == value


def test_type_and_property_mapping_has_no_unplanned_chinese_exports() -> None:
  from tools.doushu import public_exports

  actual = public_exports(import_module("tools.doushu").ROOT)
  for module, exports in actual.items():
    chinese = {name for name in exports if not name.isascii()}
    assert chinese == {name for name, _ in pairs(ALIASES.get(module.removeprefix("ziwei."), ""))}
  assert sum(len(pairs(names)) for names in ALIASES.values()) == 42
  assert sum(len(pairs(names)) for names in PROPERTIES.values()) == 92


def test_existing_constructor_and_error_contracts_keep_their_names() -> None:
  assert repr(流年星曜(2024)).startswith("LiunianStars(ganzhi_year=2024,")
  with pytest.raises(TypeError):
    流年星曜(纪年=2024)  # type: ignore[call-arg]
  with pytest.raises(TypeError):
    流年星曜(True)
  with pytest.raises(ValueError):
    流年星曜(0)
  invalid_member = "不存在"
  with pytest.raises(AttributeError):
    getattr(地支, invalid_member)
  record = 农历出生记录(
    year=2024, month=1, day=1, is_leap_month=False, shichen=地支.子, gender=性别.女
  )
  assert type(record).__name__ == "LunarBirthRecord"
