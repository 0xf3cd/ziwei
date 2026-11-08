"""别名须保持原对象，错误制品在安装与上传前失败。"""

import base64
import csv
import hashlib
import io
import json
import os
import pickle
import shutil
import subprocess
import sys
from importlib import import_module
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from zipfile import ZipFile

import pytest
import yaml

from tools import doushu, doushu_installed_check
from tools.artifacts import file_sha256
from ziwei.chart import ZiweiChart

ROOT = doushu.ROOT
VERSION = doushu.project(ROOT)["version"]


def write_wheel(path: Path, contents: dict[str, bytes]) -> None:
  """重算RECORD，使负例不会只因旧摘要失败。"""
  record = f"doushu-{VERSION}.dist-info/RECORD"
  stream = io.StringIO(newline="")
  writer = csv.writer(stream, lineterminator="\n")
  for name, content in contents.items():
    if name != record:
      digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
      writer.writerow((name, "sha256=" + digest, str(len(content))))
  writer.writerow((record, "", ""))
  contents = {**contents, record: stream.getvalue().encode()}
  with ZipFile(path, "w") as archive:
    for name, content in contents.items():
      archive.writestr(name, content)


@pytest.fixture
def alias_wheel(tmp_path: Path) -> Path:
  primary = doushu.project(ROOT)
  info = f"doushu-{VERSION}.dist-info"
  fields = {
    "Metadata-Version": "2.4",
    "Name": "doushu",
    "Version": VERSION,
    "Requires-Python": primary["requires-python"],
    "License-Expression": "MIT",
    "License-File": "LICENSE",
    "Requires-Dist": f"ziwei=={VERSION}",
    "Description-Content-Type": "text/markdown",
  }
  text = "".join(f"{k}: {v}\n" for k, v in fields.items())
  text += "".join(f"Classifier: {v}\n" for v in primary["classifiers"])
  text += "".join(f"Project-URL: {k}, {v}\n" for k, v in primary["urls"].items())
  contents = {
    **doushu.forwarding_sources(ROOT),
    f"{info}/licenses/LICENSE": (ROOT / "LICENSE").read_text(encoding="utf-8").encode(),
    f"{info}/top_level.txt": b"doushu\n",
    f"{info}/METADATA": (text + "\n" + doushu.README).encode(),
    f"{info}/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
  }
  wheel = tmp_path / doushu.wheel_name(VERSION)
  write_wheel(wheel, contents)
  doushu.check_alias_wheel(wheel, VERSION)
  return wheel


def test_public_inventory_matches_documented_contract() -> None:
  actual = {module: set(names) for module, names in doushu.public_exports(ROOT).items()}
  documented = {module: set(names) for module, names in doushu.documented_exports(ROOT).items()}
  assert actual == documented
  assert actual["ziwei.knowledge"] == {"load_catalog"}
  assert {"Gender", "LunarBirthRecord", "BirthRecord"} <= actual["ziwei.birth"]
  sources = doushu.forwarding_sources(ROOT)
  assert "doushu/knowledge/data.py" not in sources
  assert b"Gender as Gender" in sources["doushu/birth.py"]
  assert b"import *" not in b"".join(sources.values())


def test_new_source_module_requires_classification(tmp_path: Path) -> None:
  (tmp_path / "src/ziwei").mkdir(parents=True)
  (tmp_path / "docs").mkdir()
  (tmp_path / "docs/api.md").write_bytes((ROOT / "docs/api.md").read_bytes())
  (tmp_path / "src/ziwei/new.py").touch()
  with pytest.raises(ValueError, match="classified"):
    doushu.public_exports(tmp_path)


def test_license_is_independent_of_checkout_newlines(
  alias_wheel: Path,
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  sources = doushu.forwarding_sources(ROOT)
  project = doushu.project(ROOT)
  checkout = tmp_path / "checkout"
  checkout.mkdir()
  text = (ROOT / "LICENSE").read_text(encoding="utf-8")
  (checkout / "LICENSE").write_bytes(text.replace("\n", "\r\n").encode())
  monkeypatch.setattr(doushu, "forwarding_sources", lambda root: sources)
  monkeypatch.setattr(doushu, "project", lambda root: project)
  doushu.check_alias_wheel(alias_wheel, VERSION, root=checkout)


def test_metadata_text_accepts_crlf_without_ignoring_content(alias_wheel: Path) -> None:
  with ZipFile(alias_wheel) as archive:
    contents = {name: archive.read(name) for name in archive.namelist()}
  metadata = f"doushu-{VERSION}.dist-info/METADATA"
  contents[metadata] = contents[metadata].replace(b"\n", b"\r\n")
  write_wheel(alias_wheel, contents)
  doushu.check_alias_wheel(alias_wheel, VERSION)
  contents[metadata] += b"unexpected content\r\n"
  write_wheel(alias_wheel, contents)
  with pytest.raises(ValueError, match="README differs"):
    doushu.check_alias_wheel(alias_wheel, VERSION)


@pytest.mark.parametrize(
  "value", ["01.2.3", "1.0", "1.0.0rc1", "1.0.0/other", "\uff11.0.0", "1\uff12.0.0"]
)
def test_alias_version_is_canonical(value: str) -> None:
  with pytest.raises(ValueError, match="canonical"):
    doushu.wheel_name(value)


@pytest.mark.parametrize(
  "defect",
  [
    "marker",
    "extra",
    "internal",
    "star",
    "implementation",
    "wrong-import",
    "license",
    "pin",
    "version",
    "python",
    "extra-dependency",
    "extra-metadata",
    "readme",
    "classifier",
    "url",
    "pure",
    "tag",
    "record-hash",
    "record-size",
    "record-name",
    "record-self",
    "record-row",
    "record-count",
    "duplicate",
  ],
)
def test_wheel_rejects_self_consistent_wrong_content(alias_wheel: Path, defect: str) -> None:
  with ZipFile(alias_wheel) as archive:
    contents = {name: archive.read(name) for name in archive.namelist()}
  info = f"doushu-{VERSION}.dist-info"
  metadata = f"{info}/METADATA"
  match defect:
    case "marker":
      contents.pop("doushu/py.typed")
    case "extra":
      contents["doushu/unchecked.py"] = b"pass\n"
    case "internal":
      contents["doushu/knowledge/data.py"] = b"from ziwei.knowledge.data import *\n"
    case "star":
      contents["doushu/birth.py"] = b"from ziwei.birth import *\n"
    case "implementation":
      contents["doushu/birth.py"] += b"class Gender: pass\n"
    case "wrong-import":
      contents["doushu/birth.py"] = contents["doushu/birth.py"].replace(
        b"ziwei.birth", b"doushu.birth"
      )
    case "license":
      contents[f"{info}/licenses/LICENSE"] = b"wrong\n"
    case "pin":
      contents[metadata] = contents[metadata].replace(f"ziwei=={VERSION}".encode(), b"ziwei>=0.1.0")
    case "version":
      contents[metadata] = contents[metadata].replace(
        f"Version: {VERSION}".encode(), b"Version: 0.0.1"
      )
    case "python":
      contents[metadata] = contents[metadata].replace(b"Requires-Python:", b"X-Requires-Python:")
    case "extra-dependency":
      contents[metadata] = b"Requires-Dist: unrelated\n" + contents[metadata]
    case "extra-metadata":
      contents[metadata] = b"Provides-Extra: bad\n" + contents[metadata]
    case "readme":
      contents[metadata] += b"unchecked\n"
    case "classifier":
      contents[metadata] = b"Classifier: bad\n" + contents[metadata]
    case "url":
      contents[metadata] = b"Project-URL: bad, https://example.invalid\n" + contents[metadata]
    case "pure":
      contents[f"{info}/WHEEL"] = contents[f"{info}/WHEEL"].replace(b"true", b"false")
    case "tag":
      contents[f"{info}/WHEEL"] = contents[f"{info}/WHEEL"].replace(
        b"py3-none-any", b"cp314-none-any"
      )
  write_wheel(alias_wheel, contents)
  if defect.startswith("record-") or defect == "duplicate":
    with ZipFile(alias_wheel) as archive:
      contents = {name: archive.read(name) for name in archive.namelist()}
    record = f"{info}/RECORD"
    text = contents[record].decode()
    match defect:
      case "record-hash":
        text = text.replace("sha256=", "sha512=")
      case "record-size":
        lines = text.splitlines()
        lines[0] = lines[0].rsplit(",", 1)[0] + ",99999"
        text = "\n".join(lines) + "\n"
      case "record-name":
        text = text.replace("doushu/py.typed", "unknown")
      case "record-self":
        text = text.replace(f"{record},,", f"{record},sha256=bad,1")
      case "record-row":
        text = text.replace("\n", ",extra\n", 1)
      case "record-count":
        text += text.splitlines()[0] + "\n"
    contents[record] = text.encode()
    with ZipFile(alias_wheel, "w") as archive:
      for name, content in contents.items():
        archive.writestr(name, content)
      if defect == "duplicate":
        with pytest.warns(UserWarning, match="Duplicate"):
          archive.writestr("doushu/py.typed", b"")
  with pytest.raises(ValueError):
    doushu.check_alias_wheel(alias_wheel, VERSION)


def test_alias_bundle_preserves_bytes_and_trusts_external_digest(
  alias_wheel: Path, tmp_path: Path
) -> None:
  digest = file_sha256(alias_wheel)
  directory = tmp_path / "bundle"
  doushu.preserve_alias(alias_wheel, digest, directory)
  assert (
    doushu.verify_alias_bundle(directory, VERSION, digest).read_bytes() == alias_wheel.read_bytes()
  )
  with pytest.raises(ValueError, match="trusted build output"):
    doushu.verify_alias_bundle(directory, VERSION, "b" * 64)
  with pytest.raises(ValueError, match="empty regular directory"):
    doushu.preserve_alias(alias_wheel, digest, directory)
  alias_wheel.write_bytes(b"changed")
  with pytest.raises(ValueError, match="changed during"):
    doushu.preserve_alias(alias_wheel, digest, tmp_path / "later")
  assert not (tmp_path / "later").exists()


@pytest.mark.parametrize(
  "defect", ["crlf", "extra", "extra-package", "changed", "mixed-version", "multi-checksum"]
)
def test_alias_bundle_rejects_pollution(alias_wheel: Path, tmp_path: Path, defect: str) -> None:
  digest = file_sha256(alias_wheel)
  directory = tmp_path / "bundle"
  doushu.preserve_alias(alias_wheel, digest, directory)
  match defect:
    case "crlf":
      sums = directory / "SHA256SUMS"
      sums.write_bytes(sums.read_bytes().replace(b"\n", b"\r\n"))
    case "extra":
      (directory / "extra").touch()
    case "extra-package":
      (directory / "packages/extra.whl").touch()
    case "changed":
      (directory / "packages" / alias_wheel.name).write_bytes(b"changed")
    case "mixed-version":
      (directory / "packages" / alias_wheel.name).rename(
        directory / "packages/doushu-0.0.1-py3-none-any.whl"
      )
    case "multi-checksum":
      sums = directory / "SHA256SUMS"
      sums.write_bytes(sums.read_bytes() * 2)
  with pytest.raises(ValueError):
    doushu.verify_alias_bundle(directory, VERSION, digest)


@pytest.fixture
def runtime_aliases(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], Path]:
  modules: dict[str, Any] = {}
  for module, names in doushu.documented_exports(ROOT).items():
    original = import_module(module)
    alias = ModuleType(module.replace("ziwei", "doushu", 1))
    vars(alias).update({n: getattr(original, n) for n in names})
    modules[module] = original
    modules[alias.__name__] = alias
  for name in ("doushu", "ziwei"):
    modules[name] = SimpleNamespace(__file__=str(Path(sys.prefix) / name / "__init__.py"))

  birth, config = modules["ziwei.birth"], modules["ziwei.config"]
  chart: ZiweiChart = modules["ziwei.chart"].create_chart(
    birth.LunarBirthRecord(
      year=2024,
      month=1,
      day=1,
      is_leap_month=False,
      shichen=modules["ziwei.ganzhi"].Dizhi.子,
      gender=birth.Gender.女,
    ),
    config.ChartConfig(
      leap_month_policy=config.LeapMonthPolicy.全月归本月,
      day_rollover=config.DayRollover.早晚子时同日,
      year_boundary=config.YearBoundary.农历正月初一,
    ),
    sihua_variant=modules["ziwei.sihua"].SihuaVariant.排命盘口诀转录,
  )

  def create_chart(*args: object, **kwargs: object) -> ZiweiChart:
    return chart

  monkeypatch.setattr(modules["ziwei.chart"], "create_chart", create_chart)
  modules["doushu.chart"].create_chart = create_chart
  for name in tuple(sys.modules):
    if name == "celestial_calendar" or name.startswith("celestial_calendar."):
      monkeypatch.delitem(sys.modules, name)
  monkeypatch.setattr(doushu_installed_check, "import_module", lambda name: modules[name])
  monkeypatch.setattr(
    doushu_installed_check,
    "distribution",
    lambda name: SimpleNamespace(version=VERSION, requires=[f"ziwei=={VERSION}"]),
  )
  expectations = tmp_path / "names.json"
  expectations.write_text(json.dumps(doushu.documented_exports(ROOT)), encoding="utf-8")
  return modules, expectations


@pytest.mark.parametrize(
  "defect, message",
  [
    (None, None),
    ("identity", "original objects"),
    ("version", "same version"),
    ("order", "import order"),
    ("golden", "omit required"),
    ("public-names", "public names differ"),
    ("pin", "pin differs"),
    ("outside", "outside the consumer environment"),
    ("missing-file", "outside the consumer environment"),
    ("native-query", "initialized the native calendar"),
    ("enum-pickle", "enum identity"),
    ("record-pickle", "record did not retain"),
    ("knowledge-query", "knowledge query differs"),
    ("chart-type", "chart differs"),
    ("chart-output", "chart differs"),
    ("chinese-query", "Chinese query differs"),
    ("chinese-native", "Chinese query initialized"),
  ],
)
def test_runtime_consumer_rejects_invalid_contracts(
  runtime_aliases: tuple[dict[str, Any], Path],
  monkeypatch: pytest.MonkeyPatch,
  defect: str | None,
  message: str | None,
) -> None:
  modules, expectations = runtime_aliases
  version, first = VERSION, "doushu"
  match defect:
    case "identity":
      modules["doushu.birth"].Gender = object()
    case "version":
      version = "0.0.1"
    case "order":
      first = "other"
    case "golden":
      expectations.write_text("{}")
    case "public-names":
      modules["doushu.birth"].unchecked = object()
    case "pin":
      monkeypatch.setattr(
        doushu_installed_check,
        "distribution",
        lambda name: SimpleNamespace(version=VERSION, requires=["ziwei>=0.1"]),
      )
    case "outside":
      modules["doushu"].__file__ = str(ROOT / "src/doushu/__init__.py")
    case "missing-file":
      modules["doushu"].__file__ = None
    case "native-query" | "knowledge-query":
      original = modules["ziwei.knowledge"].load_catalog

      def load_catalog() -> Any:
        if defect == "native-query":
          monkeypatch.setitem(sys.modules, "celestial_calendar", ModuleType("celestial_calendar"))
          return original()
        return SimpleNamespace(get=lambda name: SimpleNamespace(id="wrong"))

      monkeypatch.setattr(modules["ziwei.knowledge"], "load_catalog", load_catalog)
      modules["doushu.knowledge"].load_catalog = load_catalog
    case "enum-pickle":
      monkeypatch.setattr(pickle, "loads", lambda data: None)
    case "record-pickle":
      original_loads = pickle.loads
      calls: list[bytes] = []

      def loads(data: bytes) -> Any:
        calls.append(data)
        return original_loads(data) if len(calls) == 1 else None

      monkeypatch.setattr(pickle, "loads", loads)
    case "chart-type":
      monkeypatch.setattr(modules["ziwei.chart"], "create_chart", lambda *args, **kwargs: object())
      modules["doushu.chart"].create_chart = modules["ziwei.chart"].create_chart
    case "chart-output":
      monkeypatch.setattr(modules["ziwei.render"], "render_text", lambda chart: "wrong")
      modules["doushu.render"].render_text = modules["ziwei.render"].render_text
    case "chinese-query":
      monkeypatch.setattr(
        modules["ziwei.liunian"].LiunianStars,
        "陀罗",
        property(lambda _: modules["ziwei.ganzhi"].Dizhi.子),
      )
    case "chinese-native":

      def year_ganzhi(value: Any) -> Any:
        monkeypatch.setitem(sys.modules, "celestial_calendar", ModuleType("celestial_calendar"))
        return value.year_ganzhi

      monkeypatch.setattr(modules["ziwei.liunian"].LiunianStars, "年干支", property(year_ganzhi))
  if message is None:
    doushu_installed_check.main(version, expectations, first)
  else:
    with pytest.raises(ValueError, match=message):
      doushu_installed_check.main(version, expectations, first)


TYPING_RESULTS = [
  (0, ""),
  (1, "error [arg-type]"),
  (1, "error [attr-defined]"),
  (1, "error [misc]"),
  (1, "error [attr-defined]"),
  (1, "error [call-arg]"),
  (1, "error [call-arg]"),
  (1, "error [misc]"),
]


@pytest.mark.parametrize(
  "results",
  [
    TYPING_RESULTS,
    [(1, "error [arg-type]")],
    [(0, ""), (0, "")],
    [(0, ""), (1, "unrelated error")],
    *[[*TYPING_RESULTS[:index], (0, "")] for index in range(2, len(TYPING_RESULTS))],
    *[[*TYPING_RESULTS[:index], (1, "unrelated error")] for index in range(2, len(TYPING_RESULTS))],
  ],
)
def test_typing_gate_checks_both_outcomes_and_uses_installed_environment(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
  results: list[tuple[int, str]],
) -> None:
  calls: list[tuple[tuple[str, ...], dict[str, str]]] = []
  pending = iter(results)

  def fake_run(command: tuple[str, ...], **kwargs: Any) -> SimpleNamespace:
    calls.append((command, kwargs["env"]))
    code, output = next(pending)
    return SimpleNamespace(returncode=code, stdout=output, stderr="")

  monkeypatch.setattr(subprocess, "run", fake_run)
  monkeypatch.setenv("MYPYPATH", "untrusted")
  monkeypatch.setenv("PYTHONPATH", "untrusted")
  monkeypatch.setenv("PYTHONUTF8", "0")
  monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
  valid = results == TYPING_RESULTS
  if valid:
    doushu.check_alias_typing(tmp_path)
    assert len(calls) == len(TYPING_RESULTS)
  else:
    with pytest.raises(ValueError, match="unexpected exit code or diagnostic"):
      doushu.check_alias_typing(tmp_path)
  assert calls
  for command, env in calls:
    assert "MYPYPATH" not in env and "PYTHONPATH" not in env
    assert env["PYTHONUTF8"] == "1" and env["PYTHONIOENCODING"] == "utf-8"
    assert "--no-incremental" in command and "--python-executable" in command
    assert command[command.index("--python-executable") + 1].startswith(str(tmp_path / "consumer"))


@pytest.mark.parametrize(
  "code,stdout,stderr",
  [(2, "", "INTERNAL ERROR"), (1, "[arg-type]", "INTERNAL ERROR"), (2, "", "")],
)
def test_typing_gate_identifies_checker_crashes(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int, stdout: str, stderr: str
) -> None:
  monkeypatch.setattr(
    subprocess,
    "run",
    lambda *args, **kwargs: SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr),
  )
  with pytest.raises(ValueError, match="mypy crashed"):
    doushu.check_alias_typing(tmp_path)


def test_typing_gate_logs_chinese_diagnostics_on_a_narrow_output_stream(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  pending = iter(TYPING_RESULTS)

  def fake_run(command: tuple[str, ...], **kwargs: Any) -> SimpleNamespace:
    assert kwargs["encoding"] == "utf-8"
    code, output = next(pending)
    return SimpleNamespace(returncode=code, stdout=output + (" 陀罗" if code else ""), stderr="")

  buffer = io.BytesIO()
  stream = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")
  with monkeypatch.context() as patch:
    patch.setattr(subprocess, "run", fake_run)
    patch.setattr(sys, "stdout", stream)
    doushu.check_alias_typing(tmp_path)
  stream.flush()
  output = buffer.getvalue().decode("cp1252")
  assert r"\u9640\u7f57" in output and "[attr-defined]" in output
  assert next(pending, None) is None


def test_alias_installs_by_file_without_resolving_another_primary(
  alias_wheel: Path,
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  calls: list[tuple[tuple[str, ...], Path]] = []
  monkeypatch.setattr(doushu, "run", lambda command, *, cwd: calls.append((tuple(command), cwd)))
  doushu.consume_alias(alias_wheel, VERSION, tmp_path)
  assert calls[0][0][-2:] == ("--no-deps", str(alias_wheel))
  assert calls[1][0][:3] == ("uv", "pip", "check")
  executions = [command for command, cwd in calls[2:]]
  assert [command[-1] for command in executions] == ["doushu", "ziwei", "doushu", "ziwei"]
  assert all("-I" in command for command in executions)
  assert ["-O" in command for command in executions] == [False, False, True, True]
  assert all(cwd == tmp_path for _, cwd in calls[2:])
  with pytest.raises(ValueError, match="outside the repository"):
    doushu.consume_alias(alias_wheel, VERSION, ROOT / "consumer")


def test_alias_prepare_exposes_original_digest_without_rebuilding(
  alias_wheel: Path,
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  directory = tmp_path / "kept"
  digest = file_sha256(alias_wheel)
  doushu.preserve_alias(alias_wheel, digest, directory)
  outputs = tmp_path / "outputs"
  monkeypatch.setenv("GITHUB_OUTPUT", str(outputs))
  monkeypatch.setattr(sys, "argv", ["doushu", "prepare", "--directory", str(directory)])
  doushu.main()
  assert outputs.read_text().splitlines() == [
    f"doushu_wheel_name={alias_wheel.name}",
    f"doushu_wheel_sha256={digest}",
  ]
  assert file_sha256(directory / "packages" / alias_wheel.name) == digest


def test_alias_sdist_builder_runs_the_extracted_tool(
  alias_wheel: Path,
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  import tarfile

  from tools import check

  sdist = tmp_path / "source.tar.gz"
  with tarfile.open(sdist, "w:gz") as archive:
    content = b"# self-contained builder\n"
    entry = tarfile.TarInfo(f"ziwei-{VERSION}/tools/doushu.py")
    entry.size = len(content)
    archive.addfile(entry, io.BytesIO(content))
  calls: list[tuple[tuple[str, ...], Path]] = []

  def fake_run(command: tuple[str, ...], *, cwd: Path) -> None:
    calls.append((command, cwd))
    bundle = Path(command[-1])
    doushu.preserve_alias(alias_wheel, file_sha256(alias_wheel), bundle)

  monkeypatch.setattr(check, "run", fake_run)
  monkeypatch.setattr(check, "source_members", lambda root: ("tools/doushu.py",))

  def old_extractall(
    self: object, path: str = ".", members: object = None, *, numeric_owner: bool = False
  ) -> None:
    raise AssertionError("Rebuilding must not extract arbitrary archive members")

  monkeypatch.setattr(tarfile.TarFile, "extractall", old_extractall)
  assert check.alias_from_sdist(sdist, VERSION, tmp_path).read_bytes() == alias_wheel.read_bytes()
  command, cwd = calls[0]
  assert Path(command[1]) == cwd / "tools/doushu.py"
  assert cwd == tmp_path / "unpacked" / f"ziwei-{VERSION}"
  assert command[2:4] == ("build", "--directory")


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "directory"])
def test_sdist_rebuild_inputs_must_be_regular_files(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
  kind: str,
) -> None:
  import tarfile

  from tools import check

  sdist = tmp_path / "source.tar.gz"
  with tarfile.open(sdist, "w:gz") as archive:
    entry = tarfile.TarInfo(f"ziwei-{VERSION}/tools/doushu.py")
    entry.type = {
      "symlink": tarfile.SYMTYPE,
      "hardlink": tarfile.LNKTYPE,
      "directory": tarfile.DIRTYPE,
    }[kind]
    entry.linkname = "../../outside"
    archive.addfile(entry)
  monkeypatch.setattr(check, "source_members", lambda root: ("tools/doushu.py",))
  with pytest.raises(ValueError, match="regular files"):
    check.alias_from_sdist(sdist, VERSION, tmp_path)
  assert not (tmp_path / "outside").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows创建符号链接可能需要特权")
@pytest.mark.parametrize("component", ["bundle", "packages", "SHA256SUMS", "wheel"])
def test_bundle_rejects_each_symlink_boundary(
  alias_wheel: Path, tmp_path: Path, component: str
) -> None:
  directory = tmp_path / "bundle"
  digest = file_sha256(alias_wheel)
  doushu.preserve_alias(alias_wheel, digest, directory)
  if component == "bundle":
    link = tmp_path / "linked-bundle"
    link.symlink_to(directory, target_is_directory=True)
    directory = link
  elif component == "packages":
    packages = directory / "packages"
    target = tmp_path / "original-packages"
    packages.rename(target)
    packages.symlink_to(target, target_is_directory=True)
  else:
    path = (
      directory / "SHA256SUMS"
      if component == "SHA256SUMS"
      else directory / "packages" / alias_wheel.name
    )
    target = tmp_path / (component + "-target")
    path.rename(target)
    path.symlink_to(target)
  with pytest.raises(ValueError):
    doushu.verify_alias_bundle(directory, VERSION, digest)


@pytest.mark.parametrize("kind", ["file", "symlink"])
def test_preserve_alias_refuses_nonregular_destination(
  alias_wheel: Path, tmp_path: Path, kind: str
) -> None:
  directory = tmp_path / "destination"
  if kind == "file":
    directory.write_bytes(b"keep")
  else:
    if sys.platform == "win32":
      pytest.skip("Windows创建符号链接可能需要特权")
    target = tmp_path / "target"
    target.mkdir()
    directory.symlink_to(target, target_is_directory=True)
  with pytest.raises(ValueError, match="empty regular directory"):
    doushu.preserve_alias(alias_wheel, file_sha256(alias_wheel), directory)


def test_alias_builder_rejects_extra_output(
  alias_wheel: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  def fake_run(command: tuple[str, ...], *, cwd: Path) -> None:
    output = Path(command[command.index("--outdir") + 1])
    output.mkdir()
    shutil.copyfile(alias_wheel, output / alias_wheel.name)
    (output / "extra.whl").touch()

  monkeypatch.setattr(doushu, "run", fake_run)
  with pytest.raises(ValueError, match="exactly one built alias wheel"):
    doushu.build_alias(tmp_path / "build")


@pytest.mark.parametrize("phase", ["install", "primary", "alias"])
def test_consumption_cannot_replace_retained_artifacts(
  alias_wheel: Path,
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
  phase: str,
) -> None:
  from tools import check

  sdist = tmp_path / "source.tar.gz"
  primary = tmp_path / "ziwei.whl"
  sdist.write_bytes(b"source")
  primary.write_bytes(b"primary")
  monkeypatch.setattr(check, "run", lambda *args, **kwargs: None)
  monkeypatch.setattr(check, "built_artifacts", lambda *args: (sdist, primary))
  monkeypatch.setattr(check, "check_sdist", lambda *args: None)
  monkeypatch.setattr(check, "check_wheel", lambda *args: None)
  monkeypatch.setattr(check, "alias_from_sdist", lambda *args: alias_wheel)
  changed = alias_wheel if phase == "alias" else primary

  def change(*args: object, **kwargs: object) -> None:
    changed.write_bytes(b"changed")

  def keep(*args: object, **kwargs: object) -> None:
    pass

  monkeypatch.setattr(check, "install_and_consume", change if phase == "install" else keep)
  monkeypatch.setattr(check, "consume_alias", keep if phase == "install" else change)
  monkeypatch.setattr(check, "check_alias_typing", lambda *args: None)
  with pytest.raises(ValueError, match="changed during"):
    check.check_distribution(
      tmp_path, artifacts_dir=tmp_path / "kept", doushu_artifacts_dir=tmp_path / "kept-alias"
    )
  assert not (tmp_path / "kept").exists() and not (tmp_path / "kept-alias").exists()


@pytest.mark.skipif(sys.platform != "linux", reason="GitHub发布job仅在Linux执行Bash")
@pytest.mark.parametrize(
  "defect", [None, "digest", "changed", "extra", "name", "missing", "symlink"]
)
def test_real_alias_publish_bash_blocks_upload(
  alias_wheel: Path, tmp_path: Path, defect: str | None
) -> None:
  workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
  step = workflow["jobs"]["publish-pypi-doushu"]["steps"][1]
  directory = tmp_path / "bundle"
  digest = file_sha256(alias_wheel)
  doushu.preserve_alias(alias_wheel, digest, directory)
  wheel = directory / "packages" / alias_wheel.name
  name = wheel.name
  match defect:
    case "digest":
      digest = "a" * 64
    case "changed":
      wheel.write_bytes(b"changed")
    case "extra":
      (wheel.parent / "extra.whl").touch()
    case "name":
      name = "../../" + name
    case "missing":
      wheel.unlink()
    case "symlink":
      wheel.unlink()
      wheel.symlink_to(alias_wheel)
  marker = tmp_path / "upload-called"
  result = subprocess.run(
    ("bash", "-c", step["run"] + '\ntouch "$MARKER"\n'),
    cwd=tmp_path,
    env={
      **os.environ,
      "DIST_DIR": str(directory),
      "RELEASE_VERSION": VERSION,
      "WHEEL_NAME": name,
      "WHEEL_SHA256": digest,
      "MARKER": str(marker),
    },
    capture_output=True,
    text=True,
    timeout=10,
  )
  assert result.returncode == (0 if defect is None else 1), result.stderr
  assert marker.exists() is (defect is None)
