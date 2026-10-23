"""schema 1的JSON记录；恢复保全已存值，不运行历法或读取时区数据。"""

import json
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from math import isfinite
from typing import Any, Final, TypeAlias, TypeVar, cast

from ziwei._text import _check_json_text
from ziwei.birth import (
  BirthRecord,
  CalculationInput,
  Gender,
  GregorianBirthRecord,
  LunarBirthRecord,
  TimePrecision,
)
from ziwei.bureau import WuxingJu
from ziwei.calendar import LunarAlgorithm
from ziwei.chart import ZiweiChart
from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, TianmaRule, YearBoundary
from ziwei.decades import DECADE_RULE_ID, Decade, Direction
from ziwei.ganzhi import Dizhi, Tiangan
from ziwei.palaces import Palace, PalaceName
from ziwei.sihua import SihuaResult, SihuaVariant
from ziwei.stars import _NATAL_STARS_V1, Star, StarPlacement
from ziwei.timezone import FixedOffset, IanaTimezone, ResolvedTime, TimezoneData

SCHEMA_VERSION: Final = 1
"""本模块支持的唯一JSON schema版本；不与软件或规则版本混用。"""

_Json: TypeAlias = dict[str, Any]
_E = TypeVar("_E", bound=StrEnum)


class UnsupportedSchemaVersionError(ValueError):
  """未知整数 schema；schema_version 保存请求版本，不按当前字段解释载荷。"""

  def __init__(self, schema_version: int) -> None:
    self.schema_version = schema_version
    super().__init__(f"不支持的命盘schema版本：{schema_version}")


def _check_schema1_stars(stars: tuple[StarPlacement, ...]) -> None:
  if tuple(p.star for p in stars) != _NATAL_STARS_V1:
    raise ValueError("schema 1须保存已发布的28星及其顺序")


def _check_strings(value: Any, path: str = "$") -> None:
  if isinstance(value, str):
    try:
      _check_json_text(value)
    except ValueError as error:
      raise ValueError(f"{path}：{error}") from error
  elif isinstance(value, dict):
    for key, item in value.items():
      _check_strings(key, path)
      _check_strings(item, f"{path}.{key}")
  elif isinstance(value, list):
    for index, item in enumerate(value):
      _check_strings(item, f"{path}[{index}]")


def _microseconds(value: timedelta) -> int:
  return (value.days * 86400 + value.seconds) * 1_000_000 + value.microseconds


def _zone_dump(zone: IanaTimezone | FixedOffset) -> _Json:
  if isinstance(zone, IanaTimezone):
    return {"kind": "IANA", "key": str(zone.key), "fold": zone.fold}
  return {"kind": "固定偏移", "offset_microseconds": _microseconds(zone.offset)}


def _record_dump(record: BirthRecord) -> _Json:
  common = {
    "gender": record.gender.value,
    "longitude_deg": record.longitude_deg,
    "place": record.place,
    "source": record.source,
  }
  if isinstance(record, GregorianBirthRecord):
    return {
      "calendar": "公历",
      "birth_date": record.birth_date.isoformat(),
      "birth_time": None if record.birth_time is None else record.birth_time.isoformat(),
      "time_precision": record.time_precision.value,
      "timezone": _zone_dump(record.timezone),
      **common,
    }
  return {
    "calendar": "农历",
    "year": record.year,
    "month": record.month,
    "day": record.day,
    "is_leap_month": record.is_leap_month,
    "shichen": None if record.shichen is None else record.shichen.value,
    **common,
  }


def _resolved_dump(value: ResolvedTime | None) -> _Json | None:
  if value is None:
    return None
  return {
    "local_time": value.local_time.isoformat(),
    "utc": value.utc.isoformat(),
    "offset_microseconds": _microseconds(value.offset),
    "fold": value.fold,
    "data": None
    if value.data is None
    else {
      "package_version": value.data.package_version,
      "iana_version": value.data.iana_version,
    },
  }


def _chart_dump(chart: ZiweiChart) -> _Json:
  _check_schema1_stars(chart.stars)
  value = chart.calculation
  config = value.config
  return {
    "schema_version": SCHEMA_VERSION,
    "software_version": chart.software_version,
    "record": _record_dump(value.record),
    "calculation": {
      "lunar_year": value.lunar_year,
      "month": value.month,
      "day": value.day,
      "is_leap_month": value.is_leap_month,
      "shichen": value.shichen.value if value.shichen else None,
      "ganzhi_year": value.ganzhi_year,
      "config": {
        "leap_month_policy": config.leap_month_policy.value,
        "day_rollover": config.day_rollover.value,
        "year_boundary": config.year_boundary.value,
        "tianma_rule": config.tianma_rule.value,
      },
      "lunar_algorithm": value.lunar_algorithm.value,
      "lunar_algorithm_version": value.lunar_algorithm_version,
      "supported_lunar_year_range": list(cast(tuple[int, int], value.supported_lunar_year_range)),
      "apparent_solar": value.apparent_solar,
      "day_rolled": value.day_rolled,
      "ut1_jd": value.ut1_jd,
      "lichun_jd": value.lichun_jd,
      "resolved_time": _resolved_dump(value.resolved_time),
    },
    "palaces": [
      {"dizhi": p.dizhi.value, "tiangan": p.tiangan.value, "name": p.name.value}
      for p in chart.palaces
    ],
    "shengong": chart.shengong.value,
    "bureau": chart.bureau.value,
    "stars": [
      {"star": p.star.value, "dizhi": p.dizhi.value, "rule_id": p.rule_id} for p in chart.stars
    ],
    "sihua": {
      "year_tiangan": chart.sihua.year_tiangan.value,
      "variant": chart.sihua.variant.value,
      "rule_id": chart.sihua.rule_id,
      "lu": chart.sihua.lu.value,
      "quan": chart.sihua.quan.value,
      "ke": chart.sihua.ke.value,
      "ji": chart.sihua.ji.value,
    },
    "decades": [
      {
        "dizhi": p.dizhi.value,
        "direction": p.direction.value,
        "start_age": p.start_age,
        "end_age": p.end_age,
        "rule_id": p.rule_id,
        "age_convention": p.age_convention,
      }
      for p in chart.decades
    ],
  }


def dumps_chart(chart: ZiweiChart) -> str:
  """保存完整盘；浮点无损往返、偏移为整数微秒，任意文本字符使用JSON转义。

  领域值为中文。生成软件版本来自盘本身，恢复再保存不会用当前版本替换它。
  不保留调用方自定义的Python字符串/数值子类身份。
  """
  if not isinstance(chart, ZiweiChart):
    raise TypeError("序列化须使用 ZiweiChart")
  obj = _chart_dump(chart)
  _check_strings(obj)
  return json.dumps(obj, ensure_ascii=True, allow_nan=False, indent=2)


def _object(value: Any, keys: str) -> _Json:
  if type(value) is not dict or set(value) != set(keys.split()):
    raise ValueError("JSON对象字段缺失、多余或类型错误")
  return value


def _array(value: Any) -> list[Any]:
  if type(value) is not list:
    raise ValueError("JSON数组类型错误")
  return value


def _str(value: Any) -> str:
  if type(value) is not str:
    raise ValueError("JSON字段须为字符串")
  return value


def _int(value: Any) -> int:
  if type(value) is not int:
    raise ValueError("JSON字段须为整数，不接受bool")
  return value


def _bool(value: Any) -> bool:
  if type(value) is not bool:
    raise ValueError("JSON字段须为bool")
  return value


def _enum(kind: type[_E], value: Any) -> _E:
  return kind(_str(value))


def _jd(value: Any) -> float | None:
  if value is None:
    return None
  if type(value) is not float or not isfinite(value):
    raise ValueError("UT1日数须为有限float或null")
  return value


def _zone_load(value: Any) -> IanaTimezone | FixedOffset:
  if type(value) is not dict:
    raise ValueError("时区须为JSON对象")
  if value.get("kind") == "IANA":
    obj = _object(value, "kind key fold")
    return IanaTimezone(_str(obj["key"]), None if obj["fold"] is None else _int(obj["fold"]))
  obj = _object(value, "kind offset_microseconds")
  if obj["kind"] != "固定偏移":
    raise ValueError("不支持的时区种类")
  return FixedOffset(timedelta(microseconds=_int(obj["offset_microseconds"])))


def _record_load(value: Any) -> BirthRecord:
  if type(value) is not dict:
    raise ValueError("出生记录须为JSON对象")
  common = "gender longitude_deg place source"
  if value.get("calendar") == "公历":
    obj = _object(value, "calendar birth_date birth_time time_precision timezone " + common)
  else:
    obj = _object(value, "calendar year month day is_leap_month shichen " + common)
    if obj["calendar"] != "农历":
      raise ValueError("不支持的出生历法")
  longitude = obj["longitude_deg"]
  if longitude is not None and type(longitude) not in (int, float):
    raise ValueError("经度须为JSON数值或null，不接受bool")
  metadata = {
    "gender": _enum(Gender, obj["gender"]),
    "longitude_deg": longitude,
    "place": None if obj["place"] is None else _str(obj["place"]),
    "source": None if obj["source"] is None else _str(obj["source"]),
  }
  if obj["calendar"] == "公历":
    day = date.fromisoformat(_str(obj["birth_date"]))
    clock = None if obj["birth_time"] is None else time.fromisoformat(_str(obj["birth_time"]))
    if day.isoformat() != obj["birth_date"] or (
      clock is not None and clock.isoformat() != obj["birth_time"]
    ):
      raise ValueError("公历日期和钟点须为规范ISO格式")
    return GregorianBirthRecord(
      birth_date=day,
      birth_time=clock,
      time_precision=_enum(TimePrecision, obj["time_precision"]),
      timezone=_zone_load(obj["timezone"]),
      **metadata,
    )
  return LunarBirthRecord(
    year=_int(obj["year"]),
    month=_int(obj["month"]),
    day=_int(obj["day"]),
    is_leap_month=_bool(obj["is_leap_month"]),
    shichen=None if obj["shichen"] is None else _enum(Dizhi, obj["shichen"]),
    **metadata,
  )


def _resolved_load(value: Any, record: BirthRecord) -> ResolvedTime | None:
  if value is None:
    return None
  if not isinstance(record, GregorianBirthRecord):
    raise ValueError("农历记录不能含已解析民用时刻")
  obj = _object(value, "local_time utc offset_microseconds fold data")
  data = None
  if obj["data"] is not None:
    info = _object(obj["data"], "package_version iana_version")
    data = TimezoneData(_str(info["package_version"]), _str(info["iana_version"]))
  wall = datetime.fromisoformat(_str(obj["local_time"]))
  utc = datetime.fromisoformat(_str(obj["utc"]))
  if wall.isoformat() != obj["local_time"] or utc.isoformat() != obj["utc"]:
    raise ValueError("已解析时刻须为规范ISO格式")
  return ResolvedTime(
    local_time=wall,
    utc=utc,
    offset=timedelta(microseconds=_int(obj["offset_microseconds"])),
    zone=record.timezone,
    fold=_int(obj["fold"]),
    data=data,
  )


def _calculation_load(value: Any, record: BirthRecord) -> CalculationInput:
  obj = _object(
    value,
    "lunar_year month day is_leap_month shichen ganzhi_year config lunar_algorithm "
    "lunar_algorithm_version supported_lunar_year_range apparent_solar day_rolled ut1_jd lichun_jd resolved_time",
  )
  config = _object(obj["config"], "leap_month_policy day_rollover year_boundary tianma_rule")
  choices = ChartConfig(
    leap_month_policy=_enum(LeapMonthPolicy, config["leap_month_policy"]),
    day_rollover=_enum(DayRollover, config["day_rollover"]),
    year_boundary=_enum(YearBoundary, config["year_boundary"]),
    tianma_rule=_enum(TianmaRule, config["tianma_rule"]),
  )
  algorithm = _enum(LunarAlgorithm, obj["lunar_algorithm"])
  bounds = tuple(_int(x) for x in _array(obj["supported_lunar_year_range"]))
  if len(bounds) != 2:
    raise ValueError("supported_lunar_year_range须有两个端点")
  return CalculationInput(
    record=record,
    lunar_year=_int(obj["lunar_year"]),
    month=_int(obj["month"]),
    day=_int(obj["day"]),
    is_leap_month=_bool(obj["is_leap_month"]),
    shichen=None if obj["shichen"] is None else _enum(Dizhi, obj["shichen"]),
    ganzhi_year=_int(obj["ganzhi_year"]),
    config=choices,
    lunar_algorithm=algorithm,
    lunar_algorithm_version=_str(obj["lunar_algorithm_version"]),
    apparent_solar=_bool(obj["apparent_solar"]),
    day_rolled=_bool(obj["day_rolled"]),
    ut1_jd=_jd(obj["ut1_jd"]),
    lichun_jd=_jd(obj["lichun_jd"]),
    resolved_time=_resolved_load(obj["resolved_time"], record),
    supported_lunar_year_range=(bounds[0], bounds[1]),
  )


def _sihua_load(value: Any) -> SihuaResult:
  obj = _object(value, "year_tiangan variant rule_id lu quan ke ji")
  variant = _enum(SihuaVariant, obj["variant"])
  if _str(obj["rule_id"]) != variant.rule_id:
    raise ValueError("四化变体与规则标识不一致")
  return SihuaResult(
    _enum(Tiangan, obj["year_tiangan"]),
    variant,
    *(_enum(Star, obj[name]) for name in ("lu", "quan", "ke", "ji")),
  )


def _decade_load(value: Any) -> Decade:
  obj = _object(value, "dizhi direction start_age end_age rule_id age_convention")
  if _str(obj["rule_id"]) != DECADE_RULE_ID or _str(obj["age_convention"]) != "虚岁":
    raise ValueError("不支持的大限规则或年龄约定")
  return Decade(
    _enum(Dizhi, obj["dizhi"]),
    _enum(Direction, obj["direction"]),
    _int(obj["start_age"]),
    _int(obj["end_age"]),
  )


def _chart_load(value: Any) -> ZiweiChart:
  if type(value) is not dict or "schema_version" not in value:
    raise ValueError("命盘根对象须含schema_version")
  schema = _int(value["schema_version"])
  if schema != SCHEMA_VERSION:
    raise UnsupportedSchemaVersionError(schema)
  _check_strings(value)
  obj = _object(
    value,
    "schema_version software_version record calculation palaces shengong bureau stars sihua decades",
  )
  record = _record_load(obj["record"])
  palaces = []
  for item in _array(obj["palaces"]):
    p = _object(item, "dizhi tiangan name")
    palaces.append(
      Palace(_enum(Dizhi, p["dizhi"]), _enum(Tiangan, p["tiangan"]), _enum(PalaceName, p["name"]))
    )
  stars = []
  for item in _array(obj["stars"]):
    p = _object(item, "star dizhi rule_id")
    stars.append(
      StarPlacement(_enum(Star, p["star"]), _enum(Dizhi, p["dizhi"]), _str(p["rule_id"]))
    )
  _check_schema1_stars(tuple(stars))
  return ZiweiChart(
    calculation=_calculation_load(obj["calculation"], record),
    palaces=tuple(palaces),
    shengong=_enum(Dizhi, obj["shengong"]),
    bureau=_enum(WuxingJu, obj["bureau"]),
    stars=tuple(stars),
    sihua=_sihua_load(obj["sihua"]),
    decades=tuple(_decade_load(x) for x in _array(obj["decades"])),
    software_version=_str(obj["software_version"]),
  )


def _pairs(items: list[tuple[str, Any]]) -> _Json:
  result: _Json = {}
  for key, value in items:
    if key in result:
      raise ValueError("JSON不得包含重复字段")
    result[key] = value
  return result


def _reject_constant(value: str) -> Any:
  raise ValueError("JSON不得包含NaN或Infinity")


def _finite_float(value: str) -> float:
  number = float(value)
  if not isfinite(number):
    raise ValueError("JSON浮点值须有限")
  return number


def loads_chart(payload: str) -> ZiweiChart:
  """恢复schema 1，不重算、不替换存值；不认证历法与IANA偏移真实性。

  未知整数版本抛 UnsupportedSchemaVersionError；已支持版本仍严格检查字段与组件。
  拒绝缺/多字段、重复键、非有限数值、未知规则与结构矛盾。格式或内容错误抛ValueError，
  非严格str实例（含子类）抛TypeError。不接受URL、文件名或可执行载荷，也不查找历史算法。
  不限制输入体积或数组长度；接收不可信输入的调用方须自行限制资源用量。
  """
  if type(payload) is not str:
    raise TypeError("命盘JSON须为str")
  try:
    obj = json.loads(
      payload, object_pairs_hook=_pairs, parse_constant=_reject_constant, parse_float=_finite_float
    )
    return _chart_load(obj)
  except UnsupportedSchemaVersionError:
    raise
  except (TypeError, ValueError, OverflowError, RecursionError) as error:
    diagnostic = repr(str(error)[:200])
    if len(diagnostic) > 240:
      diagnostic = diagnostic[:237] + "..."
    raise ValueError(f"命盘JSON无效或与所选规则不兼容：{diagnostic}") from error
