"""把已有命盘的读数存为结果记录，并与JSON文本互转。

结果只含读数，不含出生资料、口径、所选表、规则标识或版本；这些随运行时命盘对象保留，
需要留存时另行保存。读取只核结果内部的引用与重复读数，不调用历法，也不按现行规则重算，
规则日后修正时旧结果仍可读回。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import MISSING, dataclass, fields, is_dataclass
from enum import Enum
from functools import cache
from itertools import pairwise
from types import UnionType
from typing import (
  TYPE_CHECKING,
  Literal,
  TypeAlias,
  TypeVar,
  cast,
  get_args,
  get_origin,
  get_type_hints,
)

from ziwei.brightness import BrightnessLevel
from ziwei.bureau import WuxingJu
from ziwei.decades import Direction
from ziwei.ganzhi import Dizhi, Ganzhi, Tiangan
from ziwei.palaces import PalaceName
from ziwei.stars import Star

if TYPE_CHECKING:
  from ziwei.brightness import BrightnessTable
  from ziwei.chart import ZiweiChart
  from ziwei.sihua import SihuaVariant
  from ziwei.tongxian import TongxianBoundary

_E = TypeVar("_E")


def _check(value: object, kind: type, field: str) -> None:
  if kind is int:
    if type(value) is not int:
      raise TypeError(f"{field}: 须为整数，不接受bool或小数")
  elif not isinstance(value, kind):
    raise TypeError(f"{field}: 须为{kind.__name__}")


def _items(value: Sequence[_E], kind: type, field: str) -> tuple[_E, ...]:
  items = tuple(value)
  for index, item in enumerate(items):
    _check(item, kind, f"{field}[{index}]")
  return items


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultPalace:
  """本命一宫的宫名与干支。"""

  name: PalaceName
  tiangan: Tiangan
  dizhi: Dizhi

  def __post_init__(self) -> None:
    _check(self.name, PalaceName, "name")
    _check(self.tiangan, Tiangan, "tiangan")
    _check(self.dizhi, Dizhi, "dizhi")
    try:
      Ganzhi(self.tiangan, self.dizhi)
    except ValueError as error:
      raise ValueError(f"dizhi: 宫干支阴阳不相配（{error}）") from None

  @property
  def 宫名(self) -> PalaceName:
    return self.name

  @property
  def 天干(self) -> Tiangan:
    return self.tiangan

  @property
  def 地支(self) -> Dizhi:
    return self.dizhi


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultStar:
  """一颗星所在的地支。"""

  star: Star
  dizhi: Dizhi

  def __post_init__(self) -> None:
    _check(self.star, Star, "star")
    _check(self.dizhi, Dizhi, "dizhi")

  @property
  def 星曜(self) -> Star:
    return self.star

  @property
  def 地支(self) -> Dizhi:
    return self.dizhi


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultSihua:
  """一层四化的四颗星；落宫从结果的星位读取。"""

  lu: Star
  quan: Star
  ke: Star
  ji: Star

  def __post_init__(self) -> None:
    seen: dict[Star, str] = {}
    for field in ("lu", "quan", "ke", "ji"):
      star = getattr(self, field)
      _check(star, Star, field)
      if star in seen:
        raise ValueError(f"{field}: 与{seen[star]}是同一颗星")
      seen[star] = field

  @property
  def 化禄(self) -> Star:
    return self.lu

  @property
  def 化权(self) -> Star:
    return self.quan

  @property
  def 化科(self) -> Star:
    return self.ke

  @property
  def 化忌(self) -> Star:
    return self.ji


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultBrightness:
  """一颗主星在所选表中的亮度等级。"""

  star: Star
  level: BrightnessLevel

  def __post_init__(self) -> None:
    _check(self.star, Star, "star")
    _check(self.level, BrightnessLevel, "level")

  @property
  def 星曜(self) -> Star:
    return self.star

  @property
  def 等级(self) -> BrightnessLevel:
    return self.level


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultDecade:
  """一个大限的地支与虚岁区间，首尾包含。"""

  dizhi: Dizhi
  start_age: int
  end_age: int

  def __post_init__(self) -> None:
    _check(self.dizhi, Dizhi, "dizhi")
    _check(self.start_age, int, "start_age")
    _check(self.end_age, int, "end_age")
    if self.start_age < 1:
      raise ValueError("start_age: 虚岁须为正整数")
    if self.end_age != self.start_age + 9:
      raise ValueError("end_age: 一限首尾包含共十年")

  @property
  def 地支(self) -> Dizhi:
    return self.dizhi

  @property
  def 起始虚岁(self) -> int:
    return self.start_age

  @property
  def 终止虚岁(self) -> int:
    return self.end_age


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultDecades:
  """十二大限：行运方向、年龄计法，以及按起限先后排列的各限。"""

  direction: Direction
  age_convention: Literal["虚岁"]
  periods: tuple[ResultDecade, ...]

  def __post_init__(self) -> None:
    _check(self.direction, Direction, "direction")
    if self.age_convention != "虚岁":
      raise ValueError("age_convention: 大限年龄只用虚岁")
    periods = _items(self.periods, ResultDecade, "periods")
    if len(periods) != len(Dizhi):
      raise ValueError(f"periods: 须有12限，实际{len(periods)}限")
    branches = tuple(Dizhi)
    step = 1 if self.direction is Direction.FORWARD else -1
    for index, (before, after) in enumerate(pairwise(periods), start=1):
      if after.start_age != before.end_age + 1:
        raise ValueError(f"periods[{index}].start_age: 须紧接上一限")
      if branches.index(after.dizhi) != (branches.index(before.dizhi) + step) % len(branches):
        raise ValueError(f"periods[{index}].dizhi: 须按行运方向走到下一地支")
    object.__setattr__(self, "periods", periods)

  @property
  def 行运方向(self) -> Direction:
    return self.direction

  @property
  def 各限(self) -> tuple[ResultDecade, ...]:
    return self.periods


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultYunxian:
  """一个虚岁的小限、童限与大限地支。

  tongxian为None表示该岁不在所选边界的童限内；decade为None表示首限之前。
  """

  age: int
  xiaoxian: Dizhi
  tongxian: Dizhi | None
  decade: Dizhi | None

  def __post_init__(self) -> None:
    _check(self.age, int, "age")
    if self.age < 1:
      raise ValueError("age: 虚岁须为正整数")
    _check(self.xiaoxian, Dizhi, "xiaoxian")
    if self.tongxian is not None:
      _check(self.tongxian, Dizhi, "tongxian")
    if self.decade is not None:
      _check(self.decade, Dizhi, "decade")

  @property
  def 虚岁(self) -> int:
    return self.age

  @property
  def 小限(self) -> Dizhi:
    return self.xiaoxian

  @property
  def 童限(self) -> Dizhi | None:
    return self.tongxian

  @property
  def 大限(self) -> Dizhi | None:
    return self.decade


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultLiunianPalace:
  """流年一宫的宫名与地支。"""

  name: PalaceName
  dizhi: Dizhi

  def __post_init__(self) -> None:
    _check(self.name, PalaceName, "name")
    _check(self.dizhi, Dizhi, "dizhi")

  @property
  def 宫名(self) -> PalaceName:
    return self.name

  @property
  def 地支(self) -> Dizhi:
    return self.dizhi


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultLiunian:
  """一个干支纪年的流年十二宫、禄羊陀与年度四化；sihua为None表示未请求年度四化。"""

  ganzhi_year: int
  palaces: tuple[ResultLiunianPalace, ...]
  lucun: Dizhi
  qingyang: Dizhi
  tuoluo: Dizhi
  sihua: ResultSihua | None

  def __post_init__(self) -> None:
    _check(self.ganzhi_year, int, "ganzhi_year")
    if self.ganzhi_year < 1:
      raise ValueError("ganzhi_year: 纪年须为正整数")
    palaces = _items(self.palaces, ResultLiunianPalace, "palaces")
    _check_palace_names(palaces)
    for field in ("lucun", "qingyang", "tuoluo"):
      _check(getattr(self, field), Dizhi, field)
    if self.sihua is not None:
      _check(self.sihua, ResultSihua, "sihua")
    object.__setattr__(self, "palaces", palaces)

  @property
  def 纪年(self) -> int:
    return self.ganzhi_year

  @property
  def 十二宫(self) -> tuple[ResultLiunianPalace, ...]:
    return self.palaces

  @property
  def 禄存(self) -> Dizhi:
    return self.lucun

  @property
  def 擎羊(self) -> Dizhi:
    return self.qingyang

  @property
  def 陀罗(self) -> Dizhi:
    return self.tuoluo

  @property
  def 流年四化(self) -> ResultSihua | None:
    return self.sihua


def _check_palace_names(palaces: Sequence[ResultPalace | ResultLiunianPalace]) -> None:
  if len(palaces) != len(PalaceName):
    raise ValueError(f"palaces: 须有12宫，实际{len(palaces)}宫")
  for index, (palace, name) in enumerate(zip(palaces, PalaceName, strict=True)):
    if palace.name is not name:
      raise ValueError(f"palaces[{index}].name: 须按宫名序排列，此处应为{name.value}")
  if len({palace.dizhi for palace in palaces}) != len(palaces):
    raise ValueError("palaces: 各宫地支不得重复")


@dataclass(frozen=True, slots=True, kw_only=True)
class ChartResult:
  """一张命盘的读数：本命十二宫、身宫、五行局、星位、生年四化与大限，以及可选的亮度、运限和流年。

  可选层为None表示导出时未选，空元组表示选了但没有条目。构造时核类型、重复读数与层内引用，
  例如四化星须在星位中、运限的大限须覆盖该岁；不核星位、亮度或四化是否符合现行规则与某张表。
  """

  palaces: tuple[ResultPalace, ...]
  shengong: Dizhi
  bureau: WuxingJu
  stars: tuple[ResultStar, ...]
  sihua: ResultSihua
  decades: ResultDecades
  brightness: tuple[ResultBrightness, ...] | None = None
  yunxian: tuple[ResultYunxian, ...] | None = None
  liunian: tuple[ResultLiunian, ...] | None = None

  def __post_init__(self) -> None:
    palaces = _items(self.palaces, ResultPalace, "palaces")
    _check_palace_names(palaces)
    _check(self.shengong, Dizhi, "shengong")
    _check(self.bureau, WuxingJu, "bureau")
    stars = _items(self.stars, ResultStar, "stars")
    placed = {position.star for position in stars}
    if len(placed) != len(stars):
      raise ValueError("stars: 星曜不得重复")
    _check(self.sihua, ResultSihua, "sihua")
    _check_sihua_stars(self.sihua, placed, "sihua")
    _check(self.decades, ResultDecades, "decades")
    object.__setattr__(self, "palaces", palaces)
    object.__setattr__(self, "stars", stars)
    if self.brightness is not None:
      readings = _items(self.brightness, ResultBrightness, "brightness")
      for index, reading in enumerate(readings):
        if reading.star not in placed:
          raise ValueError(f"brightness[{index}].star: 须是本结果星位中的星")
      if len({reading.star for reading in readings}) != len(readings):
        raise ValueError("brightness: 星曜不得重复")
      object.__setattr__(self, "brightness", readings)
    if self.yunxian is not None:
      ages = _items(self.yunxian, ResultYunxian, "yunxian")
      if len({item.age for item in ages}) != len(ages):
        raise ValueError("yunxian: 虚岁不得重复")
      periods = self.decades.periods
      for index, item in enumerate(ages):
        if item.decade is None:
          if item.age >= periods[0].start_age:
            raise ValueError(f"yunxian[{index}].decade: 首限开始后须给出大限")
        elif not any(
          period.dizhi is item.decade and period.start_age <= item.age <= period.end_age
          for period in periods
        ):
          raise ValueError(f"yunxian[{index}].decade: 须是覆盖该虚岁的大限地支")
      object.__setattr__(self, "yunxian", ages)
    if self.liunian is not None:
      years = _items(self.liunian, ResultLiunian, "liunian")
      if len({year.ganzhi_year for year in years}) != len(years):
        raise ValueError("liunian: 纪年不得重复")
      for index, year in enumerate(years):
        if year.sihua is not None:
          _check_sihua_stars(year.sihua, placed, f"liunian[{index}].sihua")
      object.__setattr__(self, "liunian", years)

  @property
  def 十二宫(self) -> tuple[ResultPalace, ...]:
    return self.palaces

  @property
  def 身宫(self) -> Dizhi:
    return self.shengong

  @property
  def 五行局(self) -> WuxingJu:
    return self.bureau

  @property
  def 星位(self) -> tuple[ResultStar, ...]:
    return self.stars

  @property
  def 生年四化(self) -> ResultSihua:
    return self.sihua

  @property
  def 大限(self) -> ResultDecades:
    return self.decades

  @property
  def 亮度(self) -> tuple[ResultBrightness, ...] | None:
    return self.brightness

  @property
  def 运限(self) -> tuple[ResultYunxian, ...] | None:
    return self.yunxian

  @property
  def 流年(self) -> tuple[ResultLiunian, ...] | None:
    return self.liunian


def _check_sihua_stars(sihua: ResultSihua, placed: set[Star], path: str) -> None:
  for field in ("lu", "quan", "ke", "ji"):
    if getattr(sihua, field) not in placed:
      raise ValueError(f"{path}.{field}: 须是本结果星位中的星")


def result_of(
  chart: ZiweiChart,
  *,
  brightness_table: BrightnessTable | None = None,
  ages: Sequence[int] | None = None,
  tongxian_boundary: TongxianBoundary | None = None,
  years: Sequence[int] | None = None,
  liunian_sihua_variant: SihuaVariant | None = None,
) -> ChartResult:
  """从已有命盘取读数。

  brightness_table、ages、years传None时不导出对应层；ages或years传空序列时导出空层。
  导出ages须同时选tongxian_boundary；只给tongxian_boundary或liunian_sihua_variant
  而不导出对应层时抛ValueError。所选表、边界与变体决定读数，但不写入结果。
  """
  from ziwei.chart import ZiweiChart, chart_brightness, liunian_palaces
  from ziwei.liunian import liunian_sihua, liunian_stars
  from ziwei.yunxian import yunxian_at_age

  if not isinstance(chart, ZiweiChart):
    raise TypeError("结果导出须使用 ZiweiChart")
  if (ages is None) is not (tongxian_boundary is None):
    raise ValueError("导出运限须同时给出ages与tongxian_boundary")
  if years is None and liunian_sihua_variant is not None:
    raise ValueError("年度四化须随years一起导出")
  brightness = None
  if brightness_table is not None:
    brightness = tuple(
      ResultBrightness(star=reading.star, level=reading.level)
      for reading in chart_brightness(chart, table=brightness_table)
      if reading.level is not None
    )
  yunxian = None
  if ages is not None and tongxian_boundary is not None:
    yunxian = tuple(
      ResultYunxian(
        age=reading.xiaoxian.age,
        xiaoxian=reading.xiaoxian.dizhi,
        tongxian=reading.tongxian.dizhi,
        decade=None if reading.decade is None else reading.decade.dizhi,
      )
      for reading in (
        yunxian_at_age(chart, age, tongxian_boundary=tongxian_boundary) for age in ages
      )
    )
  liunian = None
  if years is not None:
    readings = []
    for year in years:
      stars = liunian_stars(year)
      annual = (
        None
        if liunian_sihua_variant is None
        else liunian_sihua(year, variant=liunian_sihua_variant)
      )
      readings.append(
        ResultLiunian(
          ganzhi_year=year,
          palaces=tuple(
            ResultLiunianPalace(name=view.name, dizhi=view.dizhi)
            for view in liunian_palaces(chart, year)
          ),
          lucun=stars.lucun,
          qingyang=stars.qingyang,
          tuoluo=stars.tuoluo,
          sihua=None
          if annual is None
          else ResultSihua(lu=annual.lu, quan=annual.quan, ke=annual.ke, ji=annual.ji),
        )
      )
    liunian = tuple(readings)
  return ChartResult(
    palaces=tuple(
      ResultPalace(name=palace.name, tiangan=palace.tiangan, dizhi=palace.dizhi)
      for palace in chart.palaces
    ),
    shengong=chart.shengong,
    bureau=chart.bureau,
    stars=tuple(ResultStar(star=item.star, dizhi=item.dizhi) for item in chart.stars),
    sihua=ResultSihua(
      lu=chart.sihua.lu, quan=chart.sihua.quan, ke=chart.sihua.ke, ji=chart.sihua.ji
    ),
    decades=ResultDecades(
      direction=chart.decades[0].direction,
      age_convention=chart.decades[0].age_convention,
      periods=tuple(
        ResultDecade(dizhi=item.dizhi, start_age=item.start_age, end_age=item.end_age)
        for item in chart.decades
      ),
    ),
    brightness=brightness,
    yunxian=yunxian,
    liunian=liunian,
  )


@cache
def _record_fields(kind: type) -> tuple[tuple[str, object, bool], ...]:
  hints = get_type_hints(kind)
  return tuple((item.name, hints[item.name], item.default is MISSING) for item in fields(kind))


def _encode(value: object) -> object:
  if isinstance(value, Enum):
    return value.value
  if isinstance(value, tuple):
    return [_encode(item) for item in value]
  if is_dataclass(value) and not isinstance(value, type):
    return {
      name: _encode(getattr(value, name))
      for name, _, required in _record_fields(type(value))
      if required or getattr(value, name) is not None
    }
  return value


def dumps(result: ChartResult) -> str:
  """写成JSON文本：键名与读数类型的字段同名，枚举写中文值，未选的层省略，末尾换行。

  中文不转义，保存时用UTF-8。
  """
  if not isinstance(result, ChartResult):
    raise TypeError("结果JSON须由 ChartResult 写出")
  return json.dumps(_encode(result), ensure_ascii=False, indent=2) + "\n"


class _Pairs(tuple[tuple[str, object], ...]):
  """JSON对象的原始键值对；保留重复键，读取时按路径拒绝。"""

  __slots__ = ()


def _reject_constant(name: str) -> object:
  raise ValueError(f"结果JSON不接受{name}")


def _decode(kind: object, value: object, path: str) -> object:
  origin = get_origin(kind)
  if origin is UnionType:
    (inner,) = (arg for arg in get_args(kind) if arg is not type(None))
    return None if value is None else _decode(inner, value, path)
  if origin is tuple:
    if not isinstance(value, list):
      raise ValueError(f"{path}: 须为JSON数组")
    return tuple(
      _decode(get_args(kind)[0], item, f"{path}[{index}]") for index, item in enumerate(value)
    )
  if origin is Literal or kind is int:
    # 原样交给记录构造器核对，消息由下面补上路径。
    return value
  if isinstance(kind, type) and issubclass(kind, Enum):
    if not isinstance(value, str):
      raise ValueError(f"{path}: 须为字符串")
    member = kind._value2member_map_.get(value)
    if member is None:
      raise ValueError(f"{path}: 不认识的值{value!r}")
    return member
  if not (isinstance(kind, type) and is_dataclass(kind)):
    raise TypeError(f"{path}: 结果类型不支持的字段注解{kind!r}")
  if not isinstance(value, _Pairs):
    raise ValueError(f"{path}: 须为JSON对象")
  known = {name: (hint, required) for name, hint, required in _record_fields(kind)}
  data: dict[str, object] = {}
  for key, item in value:
    if key in data:
      raise ValueError(f"{path}.{key}: 键重复")
    if key not in known:
      raise ValueError(f"{path}.{key}: 不认识的键")
    data[key] = item
  for name, (_, required) in known.items():
    if required and name not in data:
      raise ValueError(f"{path}.{name}: 缺少此键")
  arguments = {key: _decode(known[key][0], item, f"{path}.{key}") for key, item in data.items()}
  try:
    return kind(**arguments)
  except (TypeError, ValueError) as error:
    raise ValueError(f"{path}.{error}") from None


def loads(text: str) -> ChartResult:
  """读回结果JSON文本，不调用历法，也不重新排盘。

  未知或缺少的键、错类型、不认识的枚举值、重复键与层内引用矛盾都抛ValueError，
  消息以JSON路径开头，例如``$.yunxian[1].decade``。NaN、Infinity与不合JSON语法的文本
  也抛ValueError，消息不带路径。
  """
  if not isinstance(text, str):
    raise TypeError("结果JSON须为 str")
  document = json.loads(text, object_pairs_hook=_Pairs, parse_constant=_reject_constant)
  return cast(ChartResult, _decode(ChartResult, document, "$"))


命盘结果: TypeAlias = ChartResult
结果宫位: TypeAlias = ResultPalace
结果星位: TypeAlias = ResultStar
结果四化: TypeAlias = ResultSihua
结果亮度: TypeAlias = ResultBrightness
结果大限: TypeAlias = ResultDecade
结果大限组: TypeAlias = ResultDecades
结果运限: TypeAlias = ResultYunxian
结果流年宫位: TypeAlias = ResultLiunianPalace
结果流年: TypeAlias = ResultLiunian
