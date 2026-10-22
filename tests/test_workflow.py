"""CI 必须带锁运行与贡献指南相同的命令。"""

import hashlib
import os
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/checks.yml"
RELEASE = ROOT / ".github/workflows/release.yml"
UV_VERSION = "0.12.5"
VERSION = "0.1.0"
SOURCE_CHECK = (
  "set -euo pipefail\n"
  'test -z "$(git status --porcelain --untracked-files=all)"\n'
  'git diff --exit-code "$GITHUB_SHA" --\n'
)


def load_workflow(text: str) -> dict[str, Any]:
  # BaseLoader保留GitHub的on键；这里只按字面量核规则，不执行YAML构造器。
  data: dict[str, Any] = yaml.load(text, Loader=yaml.BaseLoader)
  if not isinstance(data, dict):
    raise ValueError("Workflow must be a mapping")
  return data


def require(condition: object, message: str) -> None:
  if not condition:
    raise ValueError(message)


def documented_commands() -> tuple[str, ...]:
  guide = (ROOT / "docs/contributing.md").read_text(encoding="utf-8")
  block = re.search(r"```sh\n(uv sync --locked[^`]*)```", guide)
  assert block is not None
  return tuple(block.group(1).splitlines())


def test_ci_runs_the_documented_locked_commands() -> None:
  workflow = WORKFLOW.read_text(encoding="utf-8")
  commands = documented_commands()
  assert commands == ("uv sync --locked --python 3.14", "uv run --locked python tools/check.py")
  assert "uv sync --locked --python ${{ matrix.python }}" in workflow
  assert commands[1] in workflow
  assert "uv sync --python" not in workflow
  assert "uv run python" not in workflow


def check_action_pins(workflow: str) -> None:
  actions = [
    step["uses"]
    for job in load_workflow(workflow)["jobs"].values()
    for step in job.get("steps", [])
    if "uses" in step
  ]
  require(actions, "Workflow must execute pinned actions")
  require(
    all(re.fullmatch(r"[\w-]+/[\w-]+@[0-9a-f]{40}", action) for action in actions),
    "Action must use a full commit SHA",
  )


def test_all_actions_use_full_commit_sha() -> None:
  for path in ROOT.glob(".github/workflows/*.y*ml"):
    check_action_pins(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
  "action", ["actions/checkout", "actions/setup-python", "astral-sh/setup-uv"]
)
def test_action_pin_guard_rejects_floating_tag(action: str) -> None:
  workflow = WORKFLOW.read_text(encoding="utf-8")
  mutated, count = re.subn(re.escape(action) + r"@[0-9a-f]{40}", action + "@v7", workflow)
  assert count == 1
  with pytest.raises(ValueError, match="full commit SHA"):
    check_action_pins(mutated)


def test_named_floating_action_cannot_hide_from_the_pin_guard() -> None:
  original = WORKFLOW.read_text()
  check_action_pins(original)
  defective = original + "\n      - name: Upload\n        uses: owner/action@latest\n"
  with pytest.raises(ValueError, match="full commit SHA"):
    check_action_pins(defective)


def test_each_ci_job_binds_uv_archive_checksum() -> None:
  workflow = WORKFLOW.read_text(encoding="utf-8")
  jobs = re.findall(
    r'- os: (\S+)\n\s+python: "([\d.]+)"\n\s+uv-checksum: "([0-9a-f]{64})"', workflow
  )
  assert [(os, python) for os, python, _ in jobs] == [
    ("ubuntu-latest", "3.11"),
    ("ubuntu-latest", "3.14"),
    ("ubuntu-24.04-arm", "3.14"),
    ("macos-latest", "3.14"),
    ("windows-latest", "3.14"),
  ]
  assert jobs[0][2] == jobs[1][2] and len({checksum for _, _, checksum in jobs}) == 4
  uv_step = workflow.split("- uses: astral-sh/setup-uv@", 1)[1].split("- run:", 1)[0]
  assert "checksum: ${{ matrix.uv-checksum }}" in uv_step
  assert f'version: "{UV_VERSION}"' in uv_step


def uv_archive_checksums() -> dict[str, str]:
  rows = load_workflow(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["quality"]["strategy"][
    "matrix"
  ]["include"]
  return {row["os"]: row["uv-checksum"] for row in rows}


def check_release_policy(data: dict[str, Any]) -> None:
  require(set(data["on"]) == {"workflow_dispatch"}, "Release must be dispatch-only")
  require(set(data["on"]["workflow_dispatch"]["inputs"]) == {"version", "sha"}, "Fixed inputs")
  require(data["permissions"] == {}, "No workflow-level permissions")
  require(
    data["concurrency"] == {"group": "ziwei-publish", "cancel-in-progress": "false"}, "Concurrency"
  )
  jobs = data["jobs"]
  pairs = [
    ("ubuntu-latest", "3.11"),
    ("ubuntu-latest", "3.12"),
    ("ubuntu-latest", "3.13"),
    ("ubuntu-latest", "3.14"),
    ("ubuntu-24.04-arm", "3.14"),
    ("macos-latest", "3.14"),
    ("windows-latest", "3.14"),
  ]
  checksums = uv_archive_checksums()
  require(
    jobs["consume"]["strategy"]["matrix"]["include"]
    == [
      {"os": os_name, "python": python, "checksum": checksums[os_name]} for os_name, python in pairs
    ],
    "Release consumption matrix and uv checksums",
  )
  require(jobs["consume"]["runs-on"] == "${{ matrix.os }}", "Consume runner follows matrix")
  require(
    jobs["consume"]["env"]["PYTHON_VERSION"] == "${{ matrix.python }}",
    "Consume Python follows matrix",
  )
  require("if" not in jobs["build"], "Identity validation must run rather than silently skip")
  sync = next(
    step
    for step in jobs["consume"]["steps"]
    if step.get("run") == 'uv sync --locked --python "$PYTHON_VERSION"'
  )
  require(sync.get("shell") == "bash", "Matrix sync uses Bash variables on every platform")
  require(
    set(jobs) == {"build", "consume", "publish-testpypi", "verify-testpypi", "publish-pypi"},
    "Release jobs",
  )
  dependencies = {
    "consume": {"build"},
    "publish-testpypi": {"build", "consume"},
    "verify-testpypi": {"build", "publish-testpypi"},
    "publish-pypi": {"build", "consume", "verify-testpypi"},
  }
  for name, job in jobs.items():
    require(
      all("${{ runner" not in value for value in job.get("env", {}).values()),
      "Job-level env cannot use runner context",
    )
    needs = job.get("needs", [])
    require(
      set([needs] if isinstance(needs, str) else needs) == dependencies.get(name, set()),
      "Release needs",
    )
    require("continue-on-error" not in job, "Jobs must fail closed")
    privileged = name.startswith("publish-")
    permissions = {"id-token": "write"} if privileged else {"contents": "read"}
    require(job.get("permissions") == permissions, "Least-privilege job permissions")
    for step in job["steps"]:
      require("${{" not in step.get("run", ""), "Expressions enter scripts only through env")
      require("continue-on-error" not in step, "Steps must fail closed")
      if "uses" not in step:
        continue
      action = step["uses"].split("@", 1)[0]
      options = step.get("with", {})
      if action == "actions/checkout":
        require(
          options == {"ref": "${{ github.sha }}", "persist-credentials": "false"},
          "Checkout identity",
        )
      if action == "astral-sh/setup-uv":
        require(
          options.get("version") == UV_VERSION and options.get("enable-cache") == "false",
          "Pinned uncached uv",
        )
        require("checksum" in options, "uv download checksum")
        require(
          options["checksum"]
          == ("${{ matrix.checksum }}" if name == "consume" else checksums[job["runs-on"]]),
          "Release uv checksum matches quality CI",
        )
      if action == "actions/download-artifact":
        require(
          options
          == {
            "artifact-ids": "${{ needs.build.outputs.artifact_id }}",
            "path": "dist",
            "digest-mismatch": "error",
          },
          "Download exact artifact ID",
        )
      if action == "actions/upload-artifact":
        require(
          name == "build" and options.get("overwrite") == "false", "Only build uploads artifacts"
        )
      require(action != "actions/cache", "No release cache")
    if not privileged:
      require("environment" not in job, "Unprivileged jobs do not deploy")
      continue
    environment = name.removeprefix("publish-")
    require(job.get("environment") == environment, "Literal release environment")
    require(job.get("if") == "github.ref == 'refs/heads/main'", "Main ref early check")
    require(job["runs-on"] == "ubuntu-latest", "Publish runner")
    steps = job["steps"]
    require(
      len(steps) == 3 and all("if" not in step for step in steps),
      "Publish has only three unconditional steps",
    )
    require(
      steps[0].get("uses", "").startswith("actions/download-artifact@"),
      "Download before verification",
    )
    require(
      steps[1].get("id") == "verify-bytes" and steps[1].get("shell") == "bash",
      "Verify before publish",
    )
    require(
      steps[2].get("uses", "").startswith("pypa/gh-action-pypi-publish@"), "Single publish action"
    )
    url = (
      "https://test.pypi.org/legacy/"
      if environment == "testpypi"
      else "https://upload.pypi.org/legacy/"
    )
    require(
      steps[2]["with"]
      == {
        "repository-url": url,
        "packages-dir": "dist/packages",
        "attestations": "true",
        "skip-existing": "false",
      },
      "Fixed upload target and no skip-existing",
    )
  require(
    jobs["publish-testpypi"]["steps"][1]["run"] == jobs["publish-pypi"]["steps"][1]["run"],
    "One shared publish-byte check",
  )
  require(
    [step["run"] for step in jobs["build"]["steps"] if "run" in step]
    == [
      "uv sync --locked --python 3.14",
      SOURCE_CHECK,
      "uv run --locked python tools/release.py validate",
      "uv run --locked python tools/check.py --artifacts-dir dist",
      SOURCE_CHECK,
      "uv run --locked python tools/release.py prepare",
    ],
    "Full build gate before retaining outputs",
  )


def test_release_workflow_obeys_the_publication_contract() -> None:
  check_release_policy(load_workflow(RELEASE.read_text()))


@pytest.mark.parametrize(
  "defect",
  [
    "trigger",
    "permissions",
    "environment",
    "needs",
    "url",
    "skip",
    "interpolation",
    "always",
    "checkout",
    "build-gate",
    "build-if",
    "windows-shell",
    "runner-job-env",
    "matrix-missing",
    "matrix-python",
    "matrix-checksum",
    "matrix-runner",
    "matrix-env",
    "uv-checksum",
  ],
)
def test_release_policy_rejects_a_single_guard_defect(defect: str) -> None:
  good = load_workflow(RELEASE.read_text())
  check_release_policy(good)
  bad = deepcopy(good)
  publish = bad["jobs"]["publish-pypi"]
  match defect:
    case "trigger":
      bad["on"]["push"] = {}
    case "permissions":
      bad["jobs"]["build"]["permissions"]["id-token"] = "write"
    case "environment":
      publish["environment"] = "testpypi"
    case "needs":
      publish["needs"].remove("verify-testpypi")
    case "url":
      publish["steps"][2]["with"]["repository-url"] = "${{ inputs.url }}"
    case "skip":
      publish["steps"][2]["with"]["skip-existing"] = "true"
    case "interpolation":
      publish["steps"][1]["run"] += "\necho ${{ inputs.version }}\n"
    case "always":
      publish["steps"][2]["if"] = "always()"
    case "checkout":
      bad["jobs"]["build"]["steps"][0]["with"]["ref"] = "${{ inputs.sha }}"
    case "build-gate":
      next(
        step
        for step in bad["jobs"]["build"]["steps"]
        if step.get("run", "").startswith("uv run --locked python tools/check.py")
      )["run"] = "true"
    case "build-if":
      bad["jobs"]["build"]["if"] = "github.ref == 'refs/heads/main'"
    case "windows-shell":
      next(step for step in bad["jobs"]["consume"]["steps"] if step.get("shell") == "bash").pop(
        "shell"
      )
    case "runner-job-env":
      bad["jobs"]["build"]["env"]["SCRATCH"] = "${{ runner.temp }}"
    case "matrix-missing":
      bad["jobs"]["consume"]["strategy"]["matrix"]["include"].pop()
    case "matrix-python":
      bad["jobs"]["consume"]["strategy"]["matrix"]["include"][0]["python"] = "3.10"
    case "matrix-checksum":
      bad["jobs"]["consume"]["strategy"]["matrix"]["include"][0]["checksum"] = "0" * 64
    case "matrix-runner":
      bad["jobs"]["consume"]["runs-on"] = "ubuntu-latest"
    case "matrix-env":
      bad["jobs"]["consume"]["env"]["PYTHON_VERSION"] = "3.14"
    case "uv-checksum":
      next(
        step
        for step in bad["jobs"]["build"]["steps"]
        if step.get("uses", "").startswith("astral-sh/setup-uv@")
      )["with"]["checksum"] = "0" * 64
  expected = {
    "trigger": "dispatch-only",
    "permissions": "Least-privilege",
    "environment": "Literal release environment",
    "needs": "Release needs",
    "url": "Fixed upload target",
    "skip": "Fixed upload target",
    "interpolation": "Expressions enter scripts",
    "always": "three unconditional steps",
    "checkout": "Checkout identity",
    "build-gate": "Full build gate",
    "build-if": "Identity validation must run",
    "windows-shell": "Bash variables on every platform",
    "runner-job-env": "Job-level env cannot use runner context",
    "matrix-missing": "consumption matrix",
    "matrix-python": "consumption matrix",
    "matrix-checksum": "consumption matrix",
    "matrix-runner": "Consume runner follows matrix",
    "matrix-env": "Consume Python follows matrix",
    "uv-checksum": "uv checksum matches quality CI",
  }[defect]
  with pytest.raises(ValueError, match=expected):
    check_release_policy(bad)


@pytest.mark.skipif(sys.platform != "linux", reason="Publish jobs execute this Bash on Linux")
@pytest.mark.parametrize("job", ["publish-testpypi", "publish-pypi"])
@pytest.mark.parametrize("defect", [None, "hash", "missing", "extra", "symlink", "filename"])
def test_actual_publish_script_fails_before_upload(
  tmp_path: Path, job: str, defect: str | None
) -> None:
  packages = tmp_path / "packages"
  packages.mkdir()
  names = (f"ziwei-{VERSION}.tar.gz", f"ziwei-{VERSION}-py3-none-any.whl")
  for name in names:
    (packages / name).write_bytes(name.encode())
  env = dict(
    os.environ,
    DIST_DIR=str(tmp_path),
    RELEASE_VERSION=VERSION,
    SDIST_NAME=names[0],
    WHEEL_NAME=names[1],
    SDIST_SHA256=hashlib.sha256(names[0].encode()).hexdigest(),
    WHEEL_SHA256=hashlib.sha256(names[1].encode()).hexdigest(),
  )
  match defect:
    case "hash":
      (packages / names[1]).write_bytes(b"changed")
    case "missing":
      (packages / names[1]).unlink()
    case "extra":
      (packages / "unexpected").touch()
    case "symlink":
      target = tmp_path / "outside.whl"
      target.write_bytes(names[1].encode())
      (packages / names[1]).unlink()
      (packages / names[1]).symlink_to(target)
    case "filename":
      env["WHEEL_NAME"] = "../outside.whl"
  script = load_workflow(RELEASE.read_text())["jobs"][job]["steps"][1]["run"]
  marker = tmp_path / "upload-called"
  result = subprocess.run(
    ["bash", "-c", script + '\nprintf called > "$UPLOAD_MARKER"\n'],
    env=dict(env, UPLOAD_MARKER=str(marker)),
    capture_output=True,
    text=True,
  )
  assert (result.returncode == 0) is (defect is None), result.stderr
  assert marker.exists() is (defect is None)
