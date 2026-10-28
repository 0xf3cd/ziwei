"""隔离验证已安装的包。"""

import sys
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from importlib import import_module
from importlib.metadata import distribution
from pathlib import Path
from xml.etree.ElementTree import fromstring

import ziwei
from ziwei.birth import (
  CalculationInput,
  Gender,
  GregorianBirthRecord,
  LunarBirthRecord,
  TimePrecision,
)
from ziwei.bureau import WuxingJu
from ziwei.calendar import LunarAlgorithm
from ziwei.chart import create_chart, palace_view
from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, YearBoundary
from ziwei.decades import Direction, decade_periods, place_decades
from ziwei.ganzhi import Dizhi, Tiangan
from ziwei.knowledge import load_catalog
from ziwei.knowledge.model import KnowledgeEntry, PremiseStatus
from ziwei.palaces import Palace, PalaceName, effective_month
from ziwei.render import render_svg, render_text
from ziwei.sihua import SihuaVariant, shengnian_sihua, sihua_for_stem
from ziwei.stars import Star
from ziwei.timezone import AmbiguousTimeError, IanaTimezone, NonexistentTimeError


def check_inputs() -> None:
  """消费已安装的出生输入与时区数据，不触发历法初始化。"""
  record = GregorianBirthRecord(
    birth_date=date(1988, 7, 1),
    birth_time=time(12),
    time_precision=TimePrecision.分,
    timezone=IanaTimezone("Asia/Shanghai"),
    gender=Gender.男,
  )
  result = record.resolve_time()
  dependency = distribution("tzdata")
  if f"tzdata=={dependency.version}" not in (distribution("ziwei").requires or ()):
    raise ValueError("Installed timezone data differs from the declared pin")
  if result.data is None or result.data.package_version != dependency.version:
    raise ValueError("Timezone data provenance is missing or inconsistent")
  if result.data.iana_version != import_module("tzdata").IANA_VERSION:
    raise ValueError("Timezone IANA release differs from the installed data")
  if result.offset != timedelta(hours=9) or result.utc != datetime(1988, 7, 1, 3, tzinfo=UTC):
    raise ValueError("Installed timezone data did not resolve Shanghai summer time")
  for birth_date, clock, error in (
    (date(1988, 4, 17), time(2, 30), NonexistentTimeError),
    (date(1988, 9, 11), time(1, 30), AmbiguousTimeError),
  ):
    try:
      GregorianBirthRecord(
        birth_date=birth_date,
        birth_time=clock,
        time_precision=TimePrecision.分,
        timezone=IanaTimezone("Asia/Shanghai"),
        gender=Gender.男,
      ).resolve_time()
    except error:
      pass
    else:
      raise ValueError("Installed timezone validation accepted an unresolved local time")
  choices = ChartConfig(
    leap_month_policy=LeapMonthPolicy.全月归本月,
    day_rollover=DayRollover.晚子时归次日,
    year_boundary=YearBoundary.农历正月初一,
  )
  # 合成计算输入只检验消费合同，不作为历法转换或参考盘例。
  value = CalculationInput(
    record=record,
    lunar_year=2000,
    month=1,
    day=1,
    is_leap_month=False,
    shichen=Dizhi.子,
    ganzhi_year=2000,
    config=choices,
    lunar_algorithm=LunarAlgorithm.ALGO3,
    lunar_algorithm_version="0.8.0",
    apparent_solar=False,
    day_rolled=False,
    ut1_jd=None,
    lichun_jd=None,
  )
  value.require_complete()
  try:
    Palace(dizhi="子", tiangan=Tiangan.甲, name=PalaceName.命宫)  # type: ignore[arg-type]
  except TypeError:
    pass
  else:
    raise ValueError("Installed Palace accepted a non-enum branch")
  try:
    effective_month(1, 31, False, LeapMonthPolicy.全月归本月)
  except ValueError:
    pass
  else:
    raise ValueError("Installed effective_month accepted day 31")
  check_sihua_decades()


def check_sihua_decades() -> None:
  """在原生历法初始化前消费四化、大限与其知识关联。"""
  catalog = load_catalog()
  for variant, expected in (
    (SihuaVariant.排命盘口诀转录, (Star.天同, Star.太阴)),
    (SihuaVariant.王亭之讲义转录, (Star.天府, Star.天同)),
  ):
    result = sihua_for_stem(Tiangan.庚, variant)
    if (result.ke, result.ji) != expected or not catalog.references(result.rule_id):
      raise ValueError("Installed sihua variant or source association differs")
  periods = decade_periods(Dizhi.亥, WuxingJu.水二局, Tiangan.甲, Gender.男)
  if len(periods) != 12 or (periods[1].dizhi, periods[0].end_age) != (Dizhi.子, 11):
    raise ValueError("Installed decade direction or age labels differ")
  if periods[0].age_convention != "虚岁" or not catalog.references(periods[0].rule_id):
    raise ValueError("Installed decade convention or source association differs")


def check_calendar() -> None:
  """消费已安装包的历法适配与安星基础；会加载 celestial 原生库，须在隔离检查之后。"""
  from ziwei.bureau import WuxingJu, bureau_of
  from ziwei.calendar import celestial_version, supported_lunar_year_range
  from ziwei.palaces import effective_month, minggong_dizhi, palace_ganzhi
  from ziwei.resolver import resolve

  installed_version = celestial_version()
  if f"celestial-calendar=={installed_version}" not in (distribution("ziwei").requires or ()):
    raise ValueError("Installed celestial-calendar version differs from the declared pin")
  record = GregorianBirthRecord(
    birth_date=date(1988, 7, 1),
    birth_time=time(12),
    time_precision=TimePrecision.分,
    timezone=IanaTimezone("Asia/Shanghai"),
    gender=Gender.男,
  )
  choices = ChartConfig(
    leap_month_policy=LeapMonthPolicy.全月归本月,
    day_rollover=DayRollover.晚子时归次日,
    year_boundary=YearBoundary.农历正月初一,
  )
  algorithm = LunarAlgorithm.混合
  value = resolve(record, choices, algorithm)
  if (value.lunar_year, value.month, value.day) != (1988, 5, 18):
    raise ValueError("Installed resolver produced a wrong lunar date")
  if str(value.year_ganzhi) != "戊辰":
    raise ValueError("Installed resolver produced a wrong ganzhi year")
  supported_range = supported_lunar_year_range(algorithm)
  if (
    value.lunar_algorithm is not algorithm
    or value.lunar_algorithm_version != installed_version
    or value.supported_lunar_year_range != supported_range
  ):
    raise ValueError("Installed calendar provenance differs from algorithm, version or range")
  effective = effective_month(
    value.month, value.day, value.is_leap_month, choices.leap_month_policy
  )
  if value.shichen is None or minggong_dizhi(effective, value.shichen) != Dizhi.子:
    raise ValueError("Installed palace rule produced a wrong minggong")
  if bureau_of(palace_ganzhi(Dizhi.子, value.ganzhi_year)) is not WuxingJu.JIN_SI:
    raise ValueError("Installed bureau rule produced a wrong wuxingju")
  if shengnian_sihua(value, SihuaVariant.排命盘口诀转录).ke is not Star.右弼:
    raise ValueError("Installed sihua did not use the resolved birth year")
  periods = place_decades(value)
  if (periods[0].dizhi, periods[0].start_age, periods[1].dizhi, periods[0].direction) != (
    Dizhi.子,
    4,
    Dizhi.丑,
    Direction.顺行,
  ):
    raise ValueError("Installed decade composition differs")
  print(
    f"Installed calendar: {algorithm.name}, celestial {installed_version}, "
    f"lunar years {supported_range[0]}-{supported_range[1]}"
  )


def main(expected_version: str) -> None:
  """检查已安装ziwei的版本、导入路径及原生历法库隔离。"""
  metadata = distribution("ziwei")
  origin = Path(str(ziwei.__file__)).resolve()
  if not origin.is_relative_to(Path(sys.prefix).resolve()):
    raise ValueError("Imported ziwei from outside the consumer environment")
  if metadata.version != expected_version:
    raise ValueError("Installed version differs from the built version")
  if not origin.with_name("py.typed").is_file():
    raise ValueError("Installed package is missing py.typed")
  check_knowledge()
  check_inputs()
  if any(
    name == "celestial_calendar" or name.startswith("celestial_calendar.") for name in sys.modules
  ):
    raise ValueError("Import initialized the calendar adapter")
  check_calendar()
  check_chart()
  print(f"Installed ziwei {metadata.version}; optimized={sys.flags.optimize}")


def check_chart() -> None:
  """用安装包排整盘和显示；普通与-O由同一个入口执行。"""
  record = GregorianBirthRecord(
    birth_date=date(1988, 7, 1),
    birth_time=time(12),
    time_precision=TimePrecision.分,
    timezone=IanaTimezone("Asia/Shanghai"),
    gender=Gender.男,
    place="江苏省",
    source="合成安装例",
  )
  choices = ChartConfig(
    leap_month_policy=LeapMonthPolicy.全月归本月,
    day_rollover=DayRollover.早晚子时同日,
    year_boundary=YearBoundary.立春,
  )
  chart = create_chart(record, choices, sihua_variant=SihuaVariant.排命盘口诀转录)
  if chart.palaces[0].dizhi is not Dizhi.子 or chart.bureau is not WuxingJu.金四局:
    raise ValueError("Installed full chart has wrong palace or bureau")
  if len(chart.stars) != 30 or len(chart.palaces) != 12 or len(chart.decades) != 12:
    raise ValueError("Installed full chart is incomplete")
  expected_pair = ((Star.红鸾, Dizhi.亥), (Star.天喜, Dizhi.巳))
  placements = {position.star: position for position in chart.stars}
  for star, branch in expected_pair:
    position = placements.get(star)
    if (
      position is None
      or position.dizhi is not branch
      or position.rule_id != "variant.star.hongluan-tianxi-year-branch"
    ):
      raise ValueError("Installed hongluan/tianxi placement or rule differs")
  resolved = chart.calculation.resolved_time
  if resolved is None or resolved.data is None or resolved.offset != timedelta(hours=9):
    raise ValueError("Installed full chart lost resolved timezone provenance")
  text = render_text(chart)
  if not all(
    part in text for part in ("命宫", "甲子", "大限 4-13虚岁", "紫微", "右弼[科]", "红鸾", "天喜")
  ):
    raise ValueError("Installed text chart is incomplete")
  image = fromstring(render_svg(chart, selected_palace=PalaceName.命宫))
  namespace = "{http://www.w3.org/2000/svg}"
  if image.tag != namespace + "svg":
    raise ValueError("Installed SVG chart has the wrong root")
  cells = [node for node in image.findall(namespace + "g") if "data-dizhi" in node.attrib]
  stars = [node for cell in cells for node in cell if node.get("class") == "star"]
  if len(cells) != 12 or len(stars) != 30:
    raise ValueError("Installed SVG chart is incomplete")
  for star, branch in expected_pair:
    if not any(
      cell.attrib["data-dizhi"] == branch.name.lower()
      and any(node.get("class") == "star" and node.text == star.value for node in cell)
      for cell in cells
    ):
      raise ValueError("Installed SVG chart lost hongluan/tianxi placement")
  roles = {
    cell.attrib["data-dizhi"]: cell.attrib["class"].split()[1]
    for cell in cells
    if len(cell.attrib["class"].split()) == 2
  }
  if roles != {"zi": "selected", "chen": "sanhe", "shen": "sanhe", "wu": "opposite"}:
    raise ValueError("Installed SVG chart has incorrect selected-palace relationships")
  selected_cell = next(cell for cell in cells if cell.attrib["data-dizhi"] == "zi")
  labels = {
    node.attrib["class"]: node.text
    for node in selected_cell
    if node.get("class") in ("ganzhi", "decade")
  }
  if labels != {"ganzhi": "甲子", "decade": "大限 4-13虚岁"} or not any(
    node.text == "右弼[科]" for node in stars
  ):
    raise ValueError("Installed SVG chart lost palace content")
  # 论坛《排命盘口诀》1954例第6至9步的独立星位；大限按同页规则推得，不由待测实现生成。
  reference = create_chart(
    LunarBirthRecord(
      year=1954, month=9, day=7, is_leap_month=False, shichen=Dizhi.子, gender=Gender.男
    ),
    replace(choices, year_boundary=YearBoundary.农历正月初一),
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  positions = {p.star: p.dizhi for p in reference.stars}
  if (positions[Star.紫微], positions[Star.天机], positions[Star.天府]) != (
    Dizhi.戌,
    Dizhi.酉,
    Dizhi.午,
  ):
    raise ValueError("Installed full chart differs from independent star positions")
  if [(p.dizhi.value, p.start_age, p.end_age) for p in reference.decades] != [
    (branch, 6 + 10 * index, 15 + 10 * index)
    for index, branch in enumerate("戌亥子丑寅卯辰巳午未申酉")
  ]:
    raise ValueError("Installed full chart differs from independent decade labels")
  view = palace_view(chart, PalaceName.命宫)
  if view.palace != chart.palaces[0] or view.stars != tuple(
    position for position in chart.stars if position.dizhi is Dizhi.子
  ):
    raise ValueError("Installed palace query lost palace or stars")
  ke_palace = next(position.dizhi for position in chart.stars if position.star is Star.右弼)
  if palace_view(chart, ke_palace).ke is not Star.右弼:
    raise ValueError("Installed palace query lost sihua")
  print("Installed full chart: calculated, rendered; independent positions and decades checked")


def check_knowledge() -> None:
  """消费安装包中的语料、别名、前提与原文引用，不只检查导入成功。"""
  catalog = load_catalog()
  if not catalog.version or not catalog.find("天馬") or len(catalog.find("庚干四化")) != 3:
    raise ValueError("Installed knowledge corpus or aliases are incomplete")
  pending = catalog.filter_entries(premise_status=PremiseStatus.待定)
  if not pending or any(item.chart_match != "未评估" for item in pending):
    raise ValueError("Installed knowledge lost unresolved premises")
  leap = catalog.get("entry.leap-month.month-stars-scope")
  if not isinstance(leap, KnowledgeEntry) or len(leap.alternatives) != 2:
    raise ValueError("Installed knowledge lost unresolved premises")
  references = catalog.references("entry.tianma.year-branch")
  if not references or references[0].quote != "论本生年支":
    raise ValueError("Installed knowledge citation differs from its source")


if __name__ == "__main__":
  main(sys.argv[1])
