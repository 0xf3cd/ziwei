"""组合不可变本命盘；恢复可核纯规则，历法与时区真实性由重算核对。"""

from dataclasses import dataclass, fields, replace
from datetime import datetime, time
from importlib.metadata import version
from math import isfinite
from typing import cast

from ziwei.birth import BirthRecord, CalculationInput, LunarBirthRecord
from ziwei.bureau import WuxingJu, bureau_of
from ziwei.calendar import LunarAlgorithm, celestial_version, supported_lunar_year_range
from ziwei.config import ChartConfig, DayRollover, YearBoundary
from ziwei.decades import Decade, place_decades
from ziwei.ganzhi import Dizhi, Tiangan
from ziwei.palaces import (
  Palace,
  PalaceName,
  effective_month,
  minggong_dizhi,
  palace_ganzhi,
  shengong_dizhi,
  twelve_palaces,
)
from ziwei.resolver import DEFAULT_LUNAR_ALGORITHM, resolve
from ziwei.sihua import SihuaResult, SihuaVariant, shengnian_sihua
from ziwei.stars import StarPlacement, place_stars


def _check_calculation(value: CalculationInput) -> None:
  """核完整盘的结构政策；不读取历法或时区数据，不认证其已存原值。"""
  value.require_complete()
  minimum, maximum = supported_lunar_year_range(value.lunar_algorithm)
  if not minimum <= value.lunar_year <= maximum:
    raise ValueError("解析农历年超出所选算法的支持范围")
  for jd in (value.ut1_jd, value.lichun_jd):
    if jd is not None and not isfinite(jd):
      raise ValueError("UT1 日数须为有限值")
  record = value.record
  if isinstance(record, LunarBirthRecord):
    if record.longitude_deg is not None or value.config.year_boundary is YearBoundary.立春:
      raise ValueError("农历记录不能提供真太阳时或立春比较所需瞬间")
    if record.shichen is Dizhi.子 and value.config.day_rollover is DayRollover.晚子时归次日:
      raise ValueError("农历子时记录无法区分早晚子时")
    if (
      (value.lunar_year, value.month, value.day, value.is_leap_month, value.shichen)
      != (record.year, record.month, record.day, record.is_leap_month, record.shichen)
      or value.apparent_solar
      or value.day_rolled
    ):
      raise ValueError("农历解析值须保全原始农历记录")
  else:
    need_instant = (
      value.config.year_boundary is YearBoundary.立春 or record.longitude_deg is not None
    )
    if need_instant != (value.resolved_time is not None):
      raise ValueError("已解析时刻的存在性须与公历记录和口径一致")
    if value.apparent_solar != (record.longitude_deg is not None):
      raise ValueError("真太阳时路径须与公历记录的经度选择一致")
    if value.resolved_time is not None and (
      value.resolved_time.local_time
      != datetime.combine(record.birth_date, cast(time, record.birth_time))
      or value.resolved_time.zone != record.timezone
    ):
      raise ValueError("已解析时刻须对应原始钟面和时区选择")
    if not value.apparent_solar:
      if value.shichen is not record.shichen:
        raise ValueError("民用路径的解析时辰须与原始钟点一致")
      rolled = (
        record.birth_time is not None
        and record.birth_time.hour == 23
        and value.config.day_rollover is DayRollover.晚子时归次日
      )
      if value.day_rolled != rolled:
        raise ValueError("晚子时顺延须与民用钟点和换日口径一致")
    if value.config.year_boundary is YearBoundary.立春:
      before = cast(float, value.ut1_jd) < cast(float, value.lichun_jd)
      if value.ganzhi_year != record.birth_date.year - int(before):
        raise ValueError("干支纪年须与已存立春比较关系一致")
  if isinstance(record, LunarBirthRecord) and value.resolved_time is not None:
    raise ValueError("农历记录不得携带已解析民用时刻")


@dataclass(frozen=True, slots=True, kw_only=True)
class ZiweiChart:
  """完整本命盘，按当前纯规则核对组合，不重做历法或时区解析。

  宫位按宫名序，星曜按Star序，大限按行限序；序列复制为元组。software_version只作生成说明。
  calculation中的农历、UT1和IANA偏移仍是已存原值，构造成功不表示这些原值已经重新认证。
  """

  calculation: CalculationInput
  palaces: tuple[Palace, ...]
  shengong: Dizhi
  bureau: WuxingJu
  stars: tuple[StarPlacement, ...]
  sihua: SihuaResult
  decades: tuple[Decade, ...]
  software_version: str

  def __post_init__(self) -> None:
    if not isinstance(self.calculation, CalculationInput):
      raise TypeError("命盘须使用 CalculationInput")
    if not isinstance(self.shengong, Dizhi) or not isinstance(self.bureau, WuxingJu):
      raise TypeError("身宫与五行局须使用领域枚举")
    if not isinstance(self.sihua, SihuaResult):
      raise TypeError("四化须使用 SihuaResult")
    if not isinstance(self.software_version, str) or not self.software_version.strip():
      raise ValueError("生成软件版本不得为空")
    for name, kind in (("palaces", Palace), ("stars", StarPlacement), ("decades", Decade)):
      items = tuple(getattr(self, name))
      if any(not isinstance(item, kind) for item in items):
        raise TypeError(f"{name}须使用对应的领域记录")
      object.__setattr__(self, name, items)
    value = self.calculation
    _check_calculation(value)
    if any(
      not isinstance(p.dizhi, Dizhi)
      or not isinstance(p.tiangan, Tiangan)
      or not isinstance(p.name, PalaceName)
      for p in self.palaces
    ):
      raise TypeError("宫位记录须使用领域枚举，不接受同值字符串")
    month = effective_month(
      value.month, value.day, value.is_leap_month, value.config.leap_month_policy
    )
    shichen = cast(Dizhi, value.shichen)
    ming = minggong_dizhi(month, shichen)
    if self.palaces != twelve_palaces(ming, value.year_ganzhi.tiangan):
      raise ValueError("十二宫须与计算输入一致且按宫名序保存")
    if self.shengong is not shengong_dizhi(month, shichen):
      raise ValueError("身宫须与计算输入一致")
    if self.bureau is not bureau_of(palace_ganzhi(ming, value.ganzhi_year)):
      raise ValueError("五行局须与命宫干支一致")
    if self.stars != place_stars(value):
      raise ValueError("星位及规则须与计算输入一致且按星曜序保存")
    if self.sihua != shengnian_sihua(value, self.sihua.variant):
      raise ValueError("四化须使用解析后的生年干")
    if self.decades != place_decades(value):
      raise ValueError("大限须与计算输入一致且按行限序保存")


def create_chart(
  record: BirthRecord,
  config: ChartConfig,
  *,
  sihua_variant: SihuaVariant,
  lunar_algorithm: LunarAlgorithm = DEFAULT_LUNAR_ALGORITHM,
) -> ZiweiChart:
  """解析原始记录并组合完整盘；时辰、性别或所请求口径不可用时整次失败。"""
  value = resolve(record, config, lunar_algorithm)
  value.require_complete()
  month = effective_month(value.month, value.day, value.is_leap_month, config.leap_month_policy)
  shichen = cast(Dizhi, value.shichen)
  ming = minggong_dizhi(month, shichen)
  return ZiweiChart(
    calculation=value,
    palaces=twelve_palaces(ming, value.year_ganzhi.tiangan),
    shengong=shengong_dizhi(month, shichen),
    bureau=bureau_of(palace_ganzhi(ming, value.ganzhi_year)),
    stars=place_stars(value),
    sihua=shengnian_sihua(value, sihua_variant),
    decades=place_decades(value),
    software_version=version("ziwei"),
  )


def recalculate(chart: ZiweiChart) -> ZiweiChart:
  """按原始输入重新计算并比对；所需版本不可用或结果不同则失败，不覆盖记录。

  只匹配存有resolved_time的IANA数据版本；固定偏移和纯民用盘不要求tzdata版本相等。
  生成软件版本不参与计算比对；不下载旧算法、不允许静默版本漂移。
  """
  if not isinstance(chart, ZiweiChart):
    raise TypeError("重算须使用 ZiweiChart")
  value = chart.calculation
  if value.lunar_algorithm_version != celestial_version():
    raise ValueError("重算所需的 celestial 版本不可用")
  if value.resolved_time is not None and value.resolved_time.data is not None:
    import tzdata  # type: ignore[import-untyped]

    data = value.resolved_time.data
    if (data.package_version, data.iana_version) != (tzdata.__version__, tzdata.IANA_VERSION):
      raise ValueError("重算所需的 tzdata 版本不可用")
  # 先核当前纯规则仍能表示原结果，再执行历法与时区求值。
  replace(chart)
  result = create_chart(
    value.record,
    value.config,
    sihua_variant=chart.sihua.variant,
    lunar_algorithm=value.lunar_algorithm,
  )
  for field in fields(chart):
    if field.name != "software_version" and getattr(result, field.name) != getattr(
      chart, field.name
    ):
      raise ValueError(f"重算结果与已存记录不一致：{field.name}")
  return result
