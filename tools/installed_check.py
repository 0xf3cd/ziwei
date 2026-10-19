"""隔离验证已安装的包。"""

import sys
from datetime import UTC, date, datetime, time, timedelta
from importlib import import_module
from importlib.metadata import distribution
from pathlib import Path

import ziwei
from ziwei.birth import GongliBirthRecord, JisuanInput, ShijianJingdu, Xingbie
from ziwei.config import Huannian, PaipanConfig, RunyueGuishu, ZishiHuanri
from ziwei.ganzhi import Dizhi
from ziwei.shiqu import AmbiguousTimeError, IanaShiqu, NonexistentTimeError


def check_inputs() -> None:
  """消费已安装的出生输入与时区数据，不触发历法初始化。"""
  record = GongliBirthRecord(
    riqi=date(1988, 7, 1),
    shijian=time(12),
    shijian_jingdu=ShijianJingdu.分,
    shiqu=IanaShiqu("Asia/Shanghai"),
    xingbie=Xingbie.男,
  )
  result = record.resolve_time()
  dependency = distribution("tzdata")
  if f"tzdata=={dependency.version}" not in (distribution("ziwei").requires or ()):
    raise ValueError("Installed timezone data differs from the declared pin")
  if result.shuju is None or result.shuju.banben != dependency.version:
    raise ValueError("Timezone data provenance is missing or inconsistent")
  if result.shuju.iana_banben != import_module("tzdata").IANA_VERSION:
    raise ValueError("Timezone IANA release differs from the installed data")
  if result.offset != timedelta(hours=9) or result.utc != datetime(1988, 7, 1, 3, tzinfo=UTC):
    raise ValueError("Installed timezone data did not resolve Shanghai summer time")
  for riqi, clock, error in (
    (date(1988, 4, 17), time(2, 30), NonexistentTimeError),
    (date(1988, 9, 11), time(1, 30), AmbiguousTimeError),
  ):
    try:
      GongliBirthRecord(
        riqi=riqi,
        shijian=clock,
        shijian_jingdu=ShijianJingdu.分,
        shiqu=IanaShiqu("Asia/Shanghai"),
        xingbie=Xingbie.男,
      ).resolve_time()
    except error:
      pass
    else:
      raise ValueError("Installed timezone validation accepted an unresolved local time")
  choices = PaipanConfig(
    runyue_guishu=RunyueGuishu.全月归本月,
    zishi_huanri=ZishiHuanri.晚子时归次日,
    huannian=Huannian.农历正月初一,
  )
  # 合成计算输入只检验消费合同，不作为历法转换或参考盘例。
  value = JisuanInput(
    jilu=record,
    nongli_nian=2000,
    yue=1,
    ri=1,
    runyue=False,
    shichen=Dizhi.子,
    ganzhi_nian=2000,
    koujing=choices,
  )
  value.require_complete()


def main(expected_version: str) -> None:
  """检查身份、导入路径及原生历法库隔离。"""
  metadata = distribution("ziwei")
  origin = Path(str(ziwei.__file__)).resolve()
  if not origin.is_relative_to(Path(sys.prefix).resolve()):
    raise ValueError("Imported ziwei from outside the consumer environment")
  if metadata.version != expected_version:
    raise ValueError("Installed version differs from the built version")
  if not origin.with_name("py.typed").is_file():
    raise ValueError("Installed package is missing py.typed")
  check_inputs()
  if any(
    name == "celestial_calendar" or name.startswith("celestial_calendar.") for name in sys.modules
  ):
    raise ValueError("Import initialized the calendar adapter")
  print(f"Installed ziwei {metadata.version}; optimized={sys.flags.optimize}")


if __name__ == "__main__":
  main(sys.argv[1])
