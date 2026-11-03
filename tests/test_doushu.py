"""别名须保持原对象，错误制品在安装与上传前失败。"""

import base64
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
from copy import deepcopy
from importlib import import_module
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from zipfile import ZipFile

import pytest
import yaml

from tools import doushu, doushu_installed_check
from tools.artifacts import file_sha256

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


@pytest.mark.parametrize("defect", ["crlf", "extra", "extra-package", "changed", "mixed-version"])
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
  with pytest.raises(ValueError):
    doushu.verify_alias_bundle(directory, VERSION, digest)


def test_runtime_consumer_rejects_wrong_api_before_chart(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  modules: dict[str, Any] = {}
  for module, names in doushu.documented_exports(ROOT).items():
    original = import_module(module)
    alias = ModuleType(module.replace("ziwei", "doushu", 1))
    vars(alias).update({n: getattr(original, n) for n in names})
    modules[module] = original
    modules[alias.__name__] = alias
  for name in ("doushu", "ziwei"):
    modules[name] = SimpleNamespace(__file__=str(Path(sys.prefix) / name / "__init__.py"))
  monkeypatch.setattr(doushu_installed_check, "import_module", lambda name: modules[name])
  monkeypatch.setattr(
    doushu_installed_check,
    "distribution",
    lambda name: SimpleNamespace(version=VERSION, requires=[f"ziwei=={VERSION}"]),
  )
  expectations = tmp_path / "names.json"
  expectations.write_text(json.dumps(doushu.documented_exports(ROOT)), encoding="utf-8")
  modules["doushu.birth"].Gender = object()
  with pytest.raises(ValueError, match="original objects"):
    doushu_installed_check.main(VERSION, expectations, "doushu")
  with pytest.raises(ValueError, match="same version"):
    doushu_installed_check.main("0.0.1", expectations, "ziwei")
  with pytest.raises(ValueError, match="import order"):
    doushu_installed_check.main(VERSION, expectations, "other")
  expectations.write_text("{}")
  with pytest.raises(ValueError, match="omit required"):
    doushu_installed_check.main(VERSION, expectations, "ziwei")


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
  assert check.alias_from_sdist(sdist, VERSION, tmp_path).read_bytes() == alias_wheel.read_bytes()
  command, cwd = calls[0]
  assert Path(command[1]) == cwd / "tools/doushu.py"
  assert cwd == tmp_path / "unpacked" / f"ziwei-{VERSION}"
  assert command[2:4] == ("build", "--directory")


@pytest.mark.parametrize("phase", ["primary", "alias"])
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
  monkeypatch.setattr(check, "install_and_consume", lambda *args, **kwargs: None)
  monkeypatch.setattr(
    check,
    "consume_alias",
    lambda *args, **kwargs: (primary if phase == "primary" else alias_wheel).write_bytes(
      b"changed"
    ),
  )
  monkeypatch.setattr(check, "check_alias_typing", lambda *args: None)
  with pytest.raises(ValueError, match="changed during"):
    check.check_distribution(
      tmp_path, artifacts_dir=tmp_path / "kept", doushu_artifacts_dir=tmp_path / "kept-alias"
    )
  assert not (tmp_path / "kept").exists() and not (tmp_path / "kept-alias").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="GitHub发布job仅在Linux执行Bash")
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
  )
  assert result.returncode == (0 if defect is None else 1), result.stderr
  assert marker.exists() is (defect is None)


@pytest.mark.parametrize(
  "defect",
  [
    "alias-needs",
    "alias-path",
    "alias-hash",
    "alias-upload",
    "consume-path",
    "consume-pin",
    "outputs",
    "upload-path",
  ],
)
def test_workflow_rejects_alias_boundary_drift(defect: str) -> None:
  from tests.test_workflow import check_release_policy, load_workflow

  good = load_workflow((ROOT / ".github/workflows/release.yml").read_text())
  check_release_policy(good)
  bad = deepcopy(good)
  alias = bad["jobs"]["publish-pypi-doushu"]
  match defect:
    case "alias-needs":
      alias["needs"].remove("publish-pypi")
    case "alias-path":
      alias["steps"][0]["with"]["path"] = "dist"
    case "alias-hash":
      alias["steps"][1]["env"]["WHEEL_SHA256"] = "${{ needs.build.outputs.wheel_sha256 }}"
    case "alias-upload":
      alias["steps"][2]["with"]["packages-dir"] = "dist/packages"
    case "consume-path":
      bad["jobs"]["consume"]["steps"][4]["with"]["path"] = "dist"
    case "consume-pin":
      bad["jobs"]["consume"]["env"].pop("DOUSHU_WHEEL_SHA256")
    case "outputs":
      bad["jobs"]["build"]["outputs"]["doushu_artifact_id"] = (
        "${{ steps.upload.outputs.artifact-id }}"
      )
    case "upload-path":
      bad["jobs"]["build"]["steps"][11]["with"]["path"] = "dist/"
  with pytest.raises(ValueError):
    check_release_policy(bad)
