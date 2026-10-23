"""从核过摘要及源码对应关系的 0.1.0 wheel 重建历史夹具，不导入当前 ziwei。"""

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from datetime import date, time, timedelta
from enum import StrEnum
from importlib.metadata import version
from pathlib import Path
from typing import Any
from zipfile import ZipFile

SOURCE_SHA = "206723d794bbf9333062ab0f07beb0d9e4751b2e"
WHEEL_SHA256 = "a720f4d40497119673b35acbc2be2dd87dc9aa6c3f813c6e4c0ba715d1e4c862"


def _generate(wheel: Path, output: Path) -> None:
  sys.path.insert(0, str(wheel))
  import ziwei
  from ziwei import birth, bureau, calendar, config, decades, ganzhi, palaces, sihua, stars
  from ziwei.birth import BirthRecord, Gender, GregorianBirthRecord, LunarBirthRecord, TimePrecision
  from ziwei.chart import create_chart
  from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, TianmaRule, YearBoundary
  from ziwei.ganzhi import Dizhi
  from ziwei.knowledge import load_catalog
  from ziwei.knowledge.catalog import Record
  from ziwei.serialization import dumps_chart
  from ziwei.sihua import SihuaVariant
  from ziwei.timezone import FixedOffset, IanaTimezone

  if ziwei.__file__ is None or not ziwei.__file__.startswith(str(wheel) + "/"):
    raise RuntimeError("生成器必须只从指定 wheel 导入 ziwei")
  if (
    version("ziwei") != "0.1.0"
    or version("tzdata") != "2026.5"
    or calendar.celestial_version() != "0.8.0"
  ):
    raise RuntimeError("生成历史样本须使用 ziwei 0.1.0、celestial 0.8.0 和 tzdata 2026.5")
  choices = ChartConfig(
    leap_month_policy=LeapMonthPolicy.全月归本月,
    day_rollover=DayRollover.早晚子时同日,
    year_boundary=YearBoundary.农历正月初一,
  )
  default = SihuaVariant.王亭之讲义转录
  cases: dict[str, tuple[BirthRecord, ChartConfig, SihuaVariant]] = {
    "lunar": (
      LunarBirthRecord(
        year=2000,
        month=1,
        day=1,
        is_leap_month=False,
        shichen=Dizhi.子,
        gender=Gender.女,
        source="合成农历例",
      ),
      choices,
      default,
    ),
    "civil-fixed": (
      GregorianBirthRecord(
        birth_date=date(2000, 6, 1),
        birth_time=time(12),
        time_precision=TimePrecision.时,
        timezone=FixedOffset(timedelta(hours=8)),
        gender=Gender.男,
        place="江苏省\ud800\n\udc00",
        source="合成民用例\x00\x1b\U00010000",
      ),
      choices,
      default,
    ),
    "instant-fixed": (
      GregorianBirthRecord(
        birth_date=date(2024, 7, 1),
        birth_time=time(12, 0, 0, 1),
        time_precision=TimePrecision.微秒,
        timezone=FixedOffset(timedelta(hours=8, microseconds=1)),
        gender=Gender.女,
        longitude_deg=-0.0,
        source="合成固定偏移瞬间例",
      ),
      replace(choices, year_boundary=YearBoundary.立春),
      default,
    ),
    "instant-iana": (
      GregorianBirthRecord(
        birth_date=date(1988, 9, 11),
        birth_time=time(1, 30, 0, 123456),
        time_precision=TimePrecision.微秒,
        timezone=IanaTimezone("Asia/Shanghai", fold=1),
        gender=Gender.女,
        source="合成IANA重叠瞬间例",
      ),
      replace(choices, year_boundary=YearBoundary.立春),
      default,
    ),
    "civil-dst-gap": (
      GregorianBirthRecord(
        birth_date=date(2024, 3, 10),
        birth_time=time(2, 30),
        time_precision=TimePrecision.分,
        timezone=IanaTimezone("America/New_York"),
        gender=Gender.男,
        source="合成民用DST间隙标签例",
      ),
      choices,
      default,
    ),
    "civil-unchecked-fold": (
      GregorianBirthRecord(
        birth_date=date(2000, 6, 1),
        birth_time=time(12),
        time_precision=TimePrecision.时,
        timezone=IanaTimezone("Asia/Shanghai", fold=1),
        gender=Gender.男,
        source="合成民用普通钟点fold=1例",
      ),
      choices,
      default,
    ),
    "instant-solar-int": (
      GregorianBirthRecord(
        birth_date=date(2024, 7, 1),
        birth_time=time(12, 0, 0, 1),
        time_precision=TimePrecision.微秒,
        timezone=FixedOffset(timedelta(hours=8)),
        gender=Gender.女,
        longitude_deg=116,
        source="合成整数经度真太阳例",
      ),
      replace(choices, year_boundary=YearBoundary.立春),
      default,
    ),
    "civil-late-zi": (
      GregorianBirthRecord(
        birth_date=date(2024, 2, 9),
        birth_time=time(23, 30),
        time_precision=TimePrecision.分,
        timezone=IanaTimezone("Asia/Shanghai"),
        gender=Gender.男,
        source="合成民用晚子时顺延与月马例",
      ),
      replace(
        choices,
        leap_month_policy=LeapMonthPolicy.全月归下月,
        day_rollover=DayRollover.晚子时归次日,
        tianma_rule=TianmaRule.月支天马,
      ),
      SihuaVariant.排命盘口诀转录,
    ),
  }
  output.mkdir(parents=True, exist_ok=False)
  hashes: dict[str, str] = {}
  for name, (record, choice, variant) in cases.items():
    data = dumps_chart(create_chart(record, choice, sihua_variant=variant)).encode("ascii")
    filename = name + ".json"
    (output / filename).write_bytes(data)
    hashes[filename] = hashlib.sha256(data).hexdigest()
  enums = {}
  for module in (birth, bureau, calendar, config, decades, ganzhi, palaces, sihua, stars):
    for name, kind in vars(module).items():
      if (
        isinstance(kind, type)
        and issubclass(kind, StrEnum)
        and kind.__module__ == module.__name__
        and not name.startswith("_")
      ):
        enums[module.__name__ + "." + name] = {member.name: member.value for member in kind}
  catalog = load_catalog()
  entries = catalog.filter_entries()
  references = [item for entry in entries for item in catalog.references(entry.id)]
  records: tuple[Record, ...] = (
    *catalog.list_concepts(),
    *catalog.list_variants(),
    *catalog.filter_sources(),
    *entries,
    *references,
  )
  identifiers = {
    "enum_values": enums,
    "star_concepts": {star.value: star.concept_id for star in stars.Star},
    "star_rules": {rule.id: [star.value for star in rule.stars] for rule in stars.STAR_RULES},
    "sihua_rules": {variant.value: variant.rule_id for variant in sihua.SihuaVariant},
    "decade_rule": decades.DECADE_RULE_ID,
    "knowledge_ids": sorted({item.id for item in records}),
  }
  data = (json.dumps(identifiers, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode()
  (output / "identifiers.json").write_bytes(data)
  # 保持原始六份采集、标识采集、两份补采的摘要顺序。
  hashes = {name: hashes[name] for name in list(hashes)[:6]} | {
    "identifiers.json": hashlib.sha256(data).hexdigest(),
    **{name: hashes[name] for name in list(hashes)[6:]},
  }
  provenance: dict[str, Any] = {
    "software_version": "0.1.0",
    "schema_version": 1,
    "source_sha": SOURCE_SHA,
    "wheel": wheel.name,
    "wheel_sha256": WHEEL_SHA256,
    "celestial_calendar_version": "0.8.0",
    "cases": list(cases),
    "sha256": hashes,
  }
  (output / "provenance.json").write_text(
    json.dumps(provenance, indent=2) + "\n", encoding="utf-8", newline="\n"
  )
  print(f"Generated {len(cases)} historical charts and {len(enums)} enum baselines")


def main() -> None:
  """显式取得 wheel、源码仓与输出路径，拒绝未知 wheel 或覆盖已有夹具。"""
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--wheel", type=Path, required=True)
  parser.add_argument("--repository", type=Path, required=True)
  parser.add_argument("--output", type=Path, required=True)
  args = parser.parse_args()
  wheel = args.wheel.resolve()
  if (
    wheel.name != "ziwei-0.1.0-py3-none-any.whl"
    or hashlib.sha256(wheel.read_bytes()).hexdigest() != WHEEL_SHA256
  ):
    raise ValueError("历史 wheel 名称或摘要不符")
  with ZipFile(wheel) as archive:
    sources = [
      name for name in archive.namelist() if name.startswith("ziwei/") and name.endswith(".py")
    ]
    if len(sources) != 19:
      raise ValueError("历史 wheel 的 Python 源码清单不符")
    for name in sources:
      expected = subprocess.run(
        ["git", "-C", str(args.repository), "show", f"{SOURCE_SHA}:src/{name}"],
        check=True,
        capture_output=True,
      ).stdout
      if archive.read(name) != expected:
        raise ValueError(f"历史 wheel 与源码提交不一致：{name}")
  print("Verified 19 wheel source files against", SOURCE_SHA)
  _generate(wheel, args.output.resolve())


if __name__ == "__main__":
  main()
