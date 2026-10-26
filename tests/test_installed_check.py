"""安装后消费者的拒绝用例。"""

import re
import subprocess
import sys
from dataclasses import asdict, replace
from importlib.metadata import distribution, version
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

import ziwei
from tools import installed_check
from ziwei.birth import Gender, GregorianBirthRecord
from ziwei.bureau import WuxingJu
from ziwei.calendar import LunarAlgorithm
from ziwei.decades import decade_periods
from ziwei.ganzhi import Dizhi, Tiangan
from ziwei.knowledge import load_catalog
from ziwei.knowledge.catalog import Catalog
from ziwei.knowledge.model import Citation, Concept, PremiseStatus, RuleVariant
from ziwei.stars import Star, place_stars
from ziwei.timezone import TimezoneData

pytestmark = pytest.mark.usefixtures("unload_celestial")


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
  output = capsys.readouterr().out
  assert "Installed ziwei" in output
  assert (
    f"Installed calendar: ALGO3, celestial {version('celestial-calendar')}, lunar years 1600-2199"
    in output
  )


def test_calendar_consumer_rejects_faulty_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
  """check_calendar 拒绝已安装解析器产出错误农历月。"""
  import ziwei.resolver as resolver_module
  from ziwei.ganzhi import Dizhi, Ganzhi

  def faulty(record: object, choices: object, lunar_algorithm: object = None) -> Any:
    return SimpleNamespace(
      lunar_year=1988,
      month=5,
      day=19,
      is_leap_month=False,
      shichen=Dizhi.午,
      year_ganzhi=Ganzhi.from_str("戊辰"),
    )

  monkeypatch.setattr(resolver_module, "resolve", faulty)
  with pytest.raises(ValueError, match="wrong lunar date"):
    installed_check.check_calendar()


def test_calendar_consumer_rejects_wrong_calendar_pin(monkeypatch: pytest.MonkeyPatch) -> None:
  """check_calendar 拒绝与声明钉版不一致的 celestial 版本。"""
  import ziwei.calendar as calendar_module

  monkeypatch.setattr(calendar_module, "celestial_version", lambda: "9.9.9")
  with pytest.raises(ValueError, match="declared pin"):
    installed_check.check_calendar()


@pytest.mark.parametrize(
  "field, wrong",
  [
    ("lunar_algorithm", LunarAlgorithm.天文计算),
    ("lunar_algorithm_version", "0.0.0"),
    ("supported_lunar_year_range", (1, 9999)),
  ],
)
def test_calendar_consumer_rejects_wrong_result_provenance(
  monkeypatch: pytest.MonkeyPatch, field: str, wrong: object
) -> None:
  from ziwei import resolver
  from ziwei.birth import CalculationInput

  installed_check.check_calendar()
  resolve = resolver.resolve

  def faulty(*args: Any, **kwargs: Any) -> CalculationInput:
    value = resolve(*args, **kwargs)
    object.__setattr__(value, field, wrong)
    return value

  monkeypatch.setattr(resolver, "resolve", faulty)
  with pytest.raises(ValueError, match="calendar provenance"):
    installed_check.check_calendar()


@pytest.mark.parametrize("kind", ["sihua", "sihua-reference", "decade-reference"])
def test_sihua_decade_consumer_rejects_wrong_values_or_sources(
  monkeypatch: pytest.MonkeyPatch,
  kind: str,
) -> None:
  if kind == "sihua":
    monkeypatch.setattr(
      installed_check,
      "sihua_for_stem",
      lambda *args: SimpleNamespace(
        ke=Star.紫微,
        ji=Star.武曲,
        rule_id="variant.sihua.zhongyi999",
      ),
    )
  else:
    original = Catalog.references
    prefix = "variant.sihua." if kind == "sihua-reference" else "variant.decades."

    def references(self: Catalog, identifier: str) -> tuple[Citation, ...]:
      return () if identifier.startswith(prefix) else original(self, identifier)

    monkeypatch.setattr(Catalog, "references", references)
  with pytest.raises(ValueError, match=r"Installed sihua|Installed decade"):
    installed_check.check_sihua_decades()


@pytest.mark.parametrize("kind", ["count", "position", "age", "convention"])
def test_sihua_decade_consumer_rejects_wrong_periods(
  monkeypatch: pytest.MonkeyPatch,
  kind: str,
) -> None:
  periods: list[Any] = list(decade_periods(Dizhi.亥, WuxingJu.水二局, Tiangan.甲, Gender.男))
  if kind == "count":
    periods.pop()
  elif kind == "position":
    periods.reverse()
  elif kind == "age":
    periods[0] = replace(periods[0], start_age=3, end_age=12)
  else:
    values = asdict(periods[0])
    values["age_convention"] = "周岁"
    # 模拟有错误元数据的安装包，不通过领域构造器制造合法记录。
    periods[0] = SimpleNamespace(**values)
  monkeypatch.setattr(installed_check, "decade_periods", lambda *args: tuple(periods))
  with pytest.raises(ValueError, match="Installed decade"):
    installed_check.check_sihua_decades()


@pytest.mark.parametrize("kind", ["sihua", "decades"])
def test_calendar_consumer_rejects_wrong_resolved_sihua_or_decades(
  monkeypatch: pytest.MonkeyPatch,
  kind: str,
) -> None:
  if kind == "sihua":
    monkeypatch.setattr(
      installed_check, "shengnian_sihua", lambda *args: SimpleNamespace(ke=Star.紫微)
    )
  else:
    wrong = decade_periods(Dizhi.亥, WuxingJu.火六局, Tiangan.甲, Gender.男)
    monkeypatch.setattr(installed_check, "place_decades", lambda *args: wrong)
  with pytest.raises(ValueError, match=r"Installed sihua|Installed decade"):
    installed_check.check_calendar()


def test_command_line_entry_validates_under_optimization(tmp_path: Path) -> None:
  """命令行入口在 -O 下仍执行校验，而不是依赖 assert。"""
  result = subprocess.run(
    (sys.executable, "-O", "-I", str(Path(installed_check.__file__)), "unrelated-version"),
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode != 0
  assert "ValueError" in result.stderr
  assert re.search("outside the consumer environment|Installed version differs", result.stderr)


def test_dependency_pin_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
  def wrong_pin(name: str) -> Any:
    if name == "ziwei":
      return SimpleNamespace(requires=["tzdata==0.0.0"])
    return distribution(name)

  monkeypatch.setattr(installed_check, "distribution", wrong_pin)
  with pytest.raises(ValueError, match="declared pin"):
    installed_check.check_inputs()


@pytest.mark.parametrize("defect", ["palace", "day"])
def test_input_consumer_rejects_missing_value_guards(
  monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
  if defect == "palace":
    monkeypatch.setattr(installed_check, "Palace", lambda **kwargs: None)
    message = "Installed Palace accepted a non-enum branch"
  else:
    monkeypatch.setattr(installed_check, "effective_month", lambda *args: 1)
    message = "Installed effective_month accepted day 31"
  with pytest.raises(ValueError, match=message):
    installed_check.check_inputs()


def test_full_chart_consumer_rejects_faulty_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(installed_check, "render_text", lambda chart: "命宫")
  with pytest.raises(ValueError, match="Installed text chart"):
    installed_check.check_chart()


def test_installed_consumer_rejects_consistent_wrong_positions(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  from ziwei import chart as chart_module

  original = place_stars
  branches = tuple(Dizhi)

  def shifted(value: Any) -> Any:
    return tuple(
      replace(p, dizhi=branches[(branches.index(p.dizhi) + 1) % 12]) for p in original(value)
    )

  monkeypatch.setattr(chart_module, "place_stars", shifted)
  with pytest.raises(ValueError, match="independent star positions"):
    installed_check.check_chart()


@pytest.mark.parametrize(
  "kind", ["no_provenance", "wrong_package", "wrong_iana", "wrong_offset", "gap", "fold"]
)
def test_input_consumer_rejects_faulty_results(kind: str, monkeypatch: pytest.MonkeyPatch) -> None:
  resolve = GregorianBirthRecord.resolve_time

  def faulty(self: GregorianBirthRecord) -> Any:
    if kind in ("gap", "fold") and self.birth_date.month == (4 if kind == "gap" else 9):
      return None
    result = resolve(self)
    if kind == "no_provenance":
      return SimpleNamespace(data=None)
    if kind == "wrong_package":
      return replace(result, data=TimezoneData("0.0.0", "2026e"))
    if kind == "wrong_iana":
      return replace(result, data=TimezoneData(version("tzdata"), "0000a"))
    if kind == "wrong_offset":
      return SimpleNamespace(data=result.data, offset=None)
    return result

  monkeypatch.setattr(GregorianBirthRecord, "resolve_time", faulty)
  with pytest.raises(ValueError, match=r"Timezone|timezone"):
    installed_check.check_inputs()


@pytest.mark.parametrize("kind", ["aliases", "pending", "alternatives", "quote", "chart_match"])
def test_knowledge_consumer_rejects_missing_or_changed_corpus(
  kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
  catalog = load_catalog()
  if kind == "aliases":
    catalog = Catalog(
      version="empty", concepts=(), variants=(), sources=(), citations=(), entries=()
    )
  elif kind in ("pending", "alternatives"):
    catalog = replace(
      catalog,
      entries=tuple(
        replace(item, premise_status=PremiseStatus.已明确)
        if kind == "pending"
        else replace(item, alternatives=())
        for item in catalog.entries
      ),
    )
  elif kind == "chart_match":
    catalog = replace(catalog, entries=tuple(replace(item) for item in catalog.entries))
    pending = catalog.filter_entries(premise_status=PremiseStatus.待定)[0]
    object.__setattr__(pending, "chart_match", "已匹配")
  else:
    catalog = replace(
      catalog,
      citations=tuple(
        replace(item, quote="错误原文") if item.id == "citation.quanshu.tianma-anchor" else item
        for item in catalog.citations
      ),
    )
  monkeypatch.setattr(installed_check, "load_catalog", lambda: catalog)
  with pytest.raises(ValueError, match="knowledge"):
    installed_check.check_knowledge()


@pytest.mark.parametrize("defect", ["tianma-alias", "geng-count", "empty-reference"])
def test_knowledge_consumer_rejects_each_independent_missing_condition(
  defect: str, monkeypatch: pytest.MonkeyPatch
) -> None:
  if defect == "empty-reference":
    original_references = Catalog.references

    def references(self: Catalog, identifier: str) -> tuple[Citation, ...]:
      return (
        () if identifier == "entry.tianma.year-branch" else original_references(self, identifier)
      )

    monkeypatch.setattr(Catalog, "references", references)
  else:
    original_find = Catalog.find
    target = "天馬" if defect == "tianma-alias" else "庚干四化"

    def find(self: Catalog, name: str) -> tuple[Concept | RuleVariant, ...]:
      return () if name == target else original_find(self, name)

    monkeypatch.setattr(Catalog, "find", find)
  with pytest.raises(ValueError, match="knowledge"):
    installed_check.check_knowledge()


def test_consumers_succeed_in_an_optimized_process(tmp_path: Path) -> None:
  root = Path(__file__).resolve().parents[1]
  script = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "from tools.installed_check import check_knowledge, check_inputs; "
    "check_knowledge(); check_inputs(); print('optimized-consumers-passed')"
  )
  result = subprocess.run(
    (sys.executable, "-O", "-I", "-c", script, str(root)),
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr
  assert "optimized-consumers-passed" in result.stdout
