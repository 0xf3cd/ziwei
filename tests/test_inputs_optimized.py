"""不经 pytest 重写的子进程校验与导入隔离。"""

import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("mode", [(), ("-O",)])
def test_public_validation_without_rewritten_assertions(
  tmp_path: Path, mode: tuple[str, ...]
) -> None:
  result = subprocess.run(
    (sys.executable, *mode, "-I", str(FIXTURES / "public_validation.py")),
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr
  assert "checked=28" in result.stdout


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
import ziwei.timezone
import ziwei.calendar
import ziwei.palaces
import ziwei.bureau
import ziwei.resolver
from ziwei.knowledge import load_catalog
catalog = load_catalog()
if not catalog.find('天馬') or not catalog.references('entry.tianma.year-branch'):
  raise RuntimeError('independent knowledge lookup failed')
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


@pytest.mark.parametrize("mode", [(), ("-O",)])
def test_knowledge_is_independent_and_validates_without_asserts(
  tmp_path: Path, mode: tuple[str, ...]
) -> None:
  result = subprocess.run(
    (sys.executable, *mode, "-I", str(FIXTURES / "knowledge_isolation.py")),
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr
  assert "checked=15" in result.stdout
