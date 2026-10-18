"""安装后消费者的拒绝用例。"""

import sys
from importlib.metadata import version
from pathlib import Path
from types import ModuleType

import pytest

import ziwei
from tools import installed_check


@pytest.fixture
def consumer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
  package = tmp_path / "ziwei"
  package.mkdir()
  (package / "__init__.py").touch()
  (package / "py.typed").touch()
  monkeypatch.setattr(ziwei, "__file__", str(package / "__init__.py"))
  monkeypatch.setattr(sys, "prefix", str(tmp_path))
  return package


def test_import_outside_consumer_rejected(consumer: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(sys, "prefix", str(consumer.parent / "other-environment"))
  with pytest.raises(ValueError, match="outside the consumer environment"):
    installed_check.main(version("ziwei"))


def test_wrong_installed_version_rejected(consumer: Path) -> None:
  with pytest.raises(ValueError, match="Installed version"):
    installed_check.main("unrelated-version")


def test_missing_installed_typing_marker_rejected(consumer: Path) -> None:
  (consumer / "py.typed").unlink()
  with pytest.raises(ValueError, match=r"missing py\.typed"):
    installed_check.main(version("ziwei"))


@pytest.mark.parametrize("module", ["celestial_calendar", "celestial_calendar._binding"])
def test_loaded_calendar_rejected(
  consumer: Path, monkeypatch: pytest.MonkeyPatch, module: str
) -> None:
  monkeypatch.setitem(sys.modules, module, ModuleType(module))
  with pytest.raises(ValueError, match="calendar adapter"):
    installed_check.main(version("ziwei"))


def test_similar_module_name_allowed(consumer: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setitem(
    sys.modules, "celestial_calendar_extra", ModuleType("celestial_calendar_extra")
  )
  installed_check.main(version("ziwei"))


def test_installed_check_passes_for_consumer(
  consumer: Path, capsys: pytest.CaptureFixture[str]
) -> None:
  installed_check.main(version("ziwei"))
  assert "Installed ziwei" in capsys.readouterr().out
