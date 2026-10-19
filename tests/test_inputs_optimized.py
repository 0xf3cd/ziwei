"""不经 pytest 重写的子进程校验与导入隔离。"""

import subprocess
import sys
from pathlib import Path

import pytest

PUBLIC_CHECKS = r"""
from datetime import date, datetime, time, timedelta
from ziwei.birth import GongliBirthRecord, NongliBirthRecord, JisuanInput, ShijianJingdu, Xingbie
from ziwei.config import PaipanConfig, RunyueGuishu, ZishiHuanri, Huannian
from ziwei.ganzhi import Ganzhi, nian_ganzhi
from ziwei.shiqu import IanaShiqu, GudingShiqu, resolve_minyong_shike
config = PaipanConfig(runyue_guishu=RunyueGuishu.全月归本月,
                      zishi_huanri=ZishiHuanri.晚子时归次日, huannian=Huannian.立春)
record = NongliBirthRecord(nian=2000, yue=4, ri=1, runyue=False,
                          shichen=None, xingbie=Xingbie.未知)
cases = [
  lambda: nian_ganzhi(True), lambda: nian_ganzhi(0),
  lambda: Ganzhi.from_str('甲丑'),
  lambda: PaipanConfig(runyue_guishu=None, zishi_huanri=config.zishi_huanri,
                       huannian=config.huannian),
  lambda: IanaShiqu('../UTC'), lambda: IanaShiqu('UTC', True),
  lambda: GudingShiqu(timedelta(days=1)),
  lambda: resolve_minyong_shike(datetime(1988, 4, 17, 2, 30), IanaShiqu('Asia/Shanghai')),
  lambda: resolve_minyong_shike(datetime(1988, 9, 11, 1, 30), IanaShiqu('Asia/Shanghai')),
  lambda: GongliBirthRecord(riqi=date(2000, 1, 1), shijian=time(12),
                           shijian_jingdu=ShijianJingdu.分,
                           shiqu=GudingShiqu(timedelta(0)), xingbie='男'),
  lambda: NongliBirthRecord(nian=True, yue=4, ri=1, runyue=False,
                           shichen=None, xingbie=Xingbie.未知),
  lambda: JisuanInput(jilu=record, nongli_nian=2000, yue=4, ri=1, runyue=False,
                      shichen=None, ganzhi_nian=2000, koujing=config).require_complete(),
]
for index, action in enumerate(cases):
  try:
    action()
  except (TypeError, ValueError):
    pass
  else:
    raise RuntimeError(f'public check {index} accepted invalid input')
print(f'checked={len(cases)}')
"""


@pytest.mark.parametrize("mode", [(), ("-O",)])
def test_public_validation_without_rewritten_assertions(
  tmp_path: Path, mode: tuple[str, ...]
) -> None:
  result = subprocess.run(
    (sys.executable, *mode, "-I", "-c", PUBLIC_CHECKS),
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr
  assert "checked=12" in result.stdout


def test_import_has_no_calendar_or_timezone_data_side_effects(tmp_path: Path) -> None:
  script = """
import sys
from importlib.abc import MetaPathFinder
class Block(MetaPathFinder):
  def find_spec(self, fullname, path=None, target=None):
    if fullname.split('.')[0] in ('celestial_calendar', 'tzdata', 'bazi'):
      raise RuntimeError('unexpected data or calendar import: ' + fullname)
sys.meta_path.insert(0, Block())
import ziwei
import ziwei.birth
import ziwei.config
import ziwei.ganzhi
import ziwei.shiqu
print('isolated imports passed')
"""
  result = subprocess.run(
    (sys.executable, "-I", "-c", script),
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr
  assert "isolated imports passed" in result.stdout
