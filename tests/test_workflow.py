"""CI 必须带锁运行与贡献指南相同的命令。"""

import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/checks.yml"
RELEASE = ROOT / ".github/workflows/release.yml"
DOCS = ROOT / ".github/workflows/docs.yml"
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
  check_ci_policy(load_workflow(WORKFLOW.read_text(encoding="utf-8")))


def check_execution_steps(job: dict[str, Any], expected: tuple[str, ...], label: str) -> None:
  """按解析后的完整命令与动作顺序核必要步骤，不把注释中的字串算作执行。"""
  steps = [(step.get("run", step.get("uses", "").split("@", 1)[0]), step) for step in job["steps"]]
  critical = [(key, step) for key, step in steps if key in expected]
  require(tuple(key for key, _ in critical) == expected, label)
  require(all("if" not in step for _, step in critical), label + " must be unconditional")
  require(all("continue-on-error" not in step for _, step in critical), label + " must fail closed")


def check_ci_policy(data: dict[str, Any]) -> None:
  commands = documented_commands()
  require(
    commands == ("uv sync --locked --python 3.14", "uv run --locked python tools/check.py"),
    "Documented locked commands",
  )
  job = data["jobs"]["quality"]
  require("if" not in job and "continue-on-error" not in job, "Quality job must run")
  check_execution_steps(
    job,
    (
      "actions/checkout",
      "actions/setup-python",
      "astral-sh/setup-uv",
      commands[0].replace("3.14", "${{ matrix.python }}"),
      commands[1],
    ),
    "Quality execution chain",
  )


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
  require("if" not in jobs["consume"], "Consumption must not be skipped")
  check_execution_steps(
    jobs["consume"],
    (
      "actions/checkout",
      "actions/setup-python",
      "astral-sh/setup-uv",
      "actions/download-artifact",
      'uv sync --locked --python "$PYTHON_VERSION"',
      "uv run --locked python tools/release.py consume",
    ),
    "Consumption execution chain",
  )
  sync = next(
    step
    for step in jobs["consume"]["steps"]
    if step.get("run") == 'uv sync --locked --python "$PYTHON_VERSION"'
  )
  require(sync.get("shell") == "bash", "Matrix sync uses Bash variables on every platform")
  require(
    set(jobs) == {"build", "consume", "publish-pypi"},
    "Release jobs",
  )
  dependencies = {
    "consume": {"build"},
    "publish-pypi": {"build", "consume"},
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
    require(job.get("environment") == "pypi", "Literal release environment")
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
    require(
      steps[2]["with"]
      == {
        "repository-url": "https://upload.pypi.org/legacy/",
        "packages-dir": "dist/packages",
        "attestations": "true",
        "skip-existing": "false",
      },
      "Fixed upload target and no skip-existing",
    )
  check_execution_steps(
    jobs["build"],
    (
      "actions/checkout",
      "actions/setup-python",
      "astral-sh/setup-uv",
      "uv sync --locked --python 3.14",
      SOURCE_CHECK,
      "uv run --locked python tools/release.py validate",
      "uv run --locked python tools/check.py --artifacts-dir dist",
      SOURCE_CHECK,
      "uv run --locked python tools/release.py prepare",
      "actions/upload-artifact",
    ),
    "Full build gate before retaining outputs",
  )
  require(
    jobs["consume"]["env"]
    == {
      "RELEASE_VERSION": "${{ needs.build.outputs.version }}",
      "RELEASE_SHA": "${{ needs.build.outputs.source_sha }}",
      "SDIST_SHA256": "${{ needs.build.outputs.sdist_sha256 }}",
      "WHEEL_SHA256": "${{ needs.build.outputs.wheel_sha256 }}",
      "PYTHON_VERSION": "${{ matrix.python }}",
    },
    "Consumption receives independent build outputs",
  )
  require(
    jobs["publish-pypi"]["steps"][1]["env"]
    == {
      "DIST_DIR": "dist",
      "RELEASE_VERSION": "${{ needs.build.outputs.version }}",
      "SDIST_NAME": "${{ needs.build.outputs.sdist_name }}",
      "WHEEL_NAME": "${{ needs.build.outputs.wheel_name }}",
      "SDIST_SHA256": "${{ needs.build.outputs.sdist_sha256 }}",
      "WHEEL_SHA256": "${{ needs.build.outputs.wheel_sha256 }}",
    },
    "Byte verification receives independent build outputs",
  )


def test_release_workflow_obeys_the_publication_contract() -> None:
  check_release_policy(load_workflow(RELEASE.read_text()))


@pytest.mark.parametrize("fail_fast", ["false", "true", None])
def test_release_policy_does_not_treat_fail_fast_as_an_upload_safety_condition(
  fail_fast: str | None,
) -> None:
  data = load_workflow(RELEASE.read_text())
  check_release_policy(data)
  strategy = data["jobs"]["consume"]["strategy"]
  if fail_fast is None:
    strategy.pop("fail-fast")
  else:
    strategy["fail-fast"] = fail_fast
  check_release_policy(data)


@pytest.mark.parametrize(
  "defect", ["replace", "delete", "skip", "duplicate", "reorder", "job-skip"]
)
def test_quality_policy_requires_executed_commands(defect: str) -> None:
  good = load_workflow(WORKFLOW.read_text())
  check_ci_policy(good)
  bad = deepcopy(good)
  job = bad["jobs"]["quality"]
  steps = job["steps"]
  index = next(i for i, step in enumerate(steps) if step.get("run") == documented_commands()[1])
  match defect:
    case "replace":
      steps[index]["run"] = "true"
    case "delete":
      steps.pop(index)
    case "skip":
      steps[index]["if"] = "false"
    case "duplicate":
      steps.append(deepcopy(steps[index]))
    case "reorder":
      steps[index - 1], steps[index] = steps[index], steps[index - 1]
    case "job-skip":
      job["if"] = "false"
  with pytest.raises(ValueError, match="Quality"):
    check_ci_policy(bad)


def test_quality_command_in_comment_does_not_execute() -> None:
  command = documented_commands()[1]
  original = WORKFLOW.read_text()
  check_ci_policy(load_workflow(original))
  assert original.count(command) == 1
  commented = original.replace(command, "true # " + command)
  with pytest.raises(ValueError, match="Quality execution chain"):
    check_ci_policy(load_workflow(commented))


@pytest.mark.parametrize(
  "defect",
  [
    "consume-replace",
    "consume-delete",
    "consume-if",
    "consume-job-if",
    "consume-duplicate",
    "consume-order",
    "consume-env",
    "build-check-if",
    "build-prepare-if",
    "build-action-duplicate",
    "build-action-order",
    "publish-env",
  ],
)
def test_release_execution_chain_rejects_skipped_or_rebound_steps(defect: str) -> None:
  good = load_workflow(RELEASE.read_text())
  check_release_policy(good)
  bad = deepcopy(good)
  consume = bad["jobs"]["consume"]
  steps = consume["steps"]
  index = next(
    i
    for i, step in enumerate(steps)
    if step.get("run") == "uv run --locked python tools/release.py consume"
  )
  build = bad["jobs"]["build"]["steps"]
  match defect:
    case "consume-replace":
      steps[index]["run"] = "true"
    case "consume-delete":
      steps.pop(index)
    case "consume-if":
      steps[index]["if"] = "false"
    case "consume-job-if":
      consume["if"] = "false"
    case "consume-duplicate":
      steps.append(deepcopy(steps[index]))
    case "consume-order":
      steps[index - 1], steps[index] = steps[index], steps[index - 1]
    case "consume-env":
      consume["env"]["RELEASE_SHA"] = "${{ github.sha }}"
    case "build-check-if":
      next(
        step
        for step in build
        if step.get("run") == "uv run --locked python tools/check.py --artifacts-dir dist"
      )["if"] = "false"
    case "build-prepare-if":
      next(
        step
        for step in build
        if step.get("run") == "uv run --locked python tools/release.py prepare"
      )["if"] = "false"
    case "build-action-duplicate":
      build.insert(1, deepcopy(build[0]))
    case "build-action-order":
      build[0], build[1] = build[1], build[0]
    case "publish-env":
      bad["jobs"]["publish-pypi"]["steps"][1]["env"]["WHEEL_SHA256"] = "0" * 64
  with pytest.raises(
    ValueError,
    match=r"execution chain|must not be skipped|Full build gate|independent build outputs",
  ):
    check_release_policy(bad)


def check_pages_policy(data: dict[str, Any]) -> None:
  require(set(data["on"]) == {"push", "workflow_dispatch"}, "Pages main push or dispatch only")
  require(data["on"]["push"] == {"branches": ["main"]}, "Pages main push only")
  require(data["on"]["workflow_dispatch"] in ("", {}), "Pages dispatch has no ref inputs")
  require(data["permissions"] == {}, "Pages has no workflow-level permissions")
  require(
    data["concurrency"] == {"group": "ziwei-pages", "cancel-in-progress": "false"},
    "Pages deployments serialize separately from package publishing",
  )
  jobs = data["jobs"]
  require(set(jobs) == {"build", "deploy"}, "Pages has one build and one deployment")
  for name, job in jobs.items():
    require(job.get("if") == "github.ref == 'refs/heads/main'", "Pages main ref guard")
    require(job["runs-on"] == "ubuntu-latest", "Pages uses Linux")
    require("continue-on-error" not in job, "Pages jobs fail closed")
    require("env" not in job, "No Pages job-level input rebinding")
    for step in job["steps"]:
      require("if" not in step and "continue-on-error" not in step, "Pages steps unconditional")
      if "uses" in step:
        require(
          re.fullmatch(r"[\w-]+/[\w-]+@[0-9a-f]{40}", step["uses"]),
          "Pages action uses a full commit SHA",
        )
    require(
      job["permissions"]
      == ({"contents": "read"} if name == "build" else {"pages": "write", "id-token": "write"}),
      "Pages least-privilege job permissions",
    )
  build = jobs["build"]
  require("needs" not in build and "environment" not in build, "Pages build has no deployment")
  expected = (
    "actions/checkout",
    "actions/setup-python",
    "astral-sh/setup-uv",
    "uv sync --locked --python 3.14",
    "uv run --locked python tools/check.py --docs-dir site",
    "actions/upload-pages-artifact",
  )
  check_execution_steps(build, expected, "Pages build execution chain")
  require(
    tuple(step.get("run", step.get("uses", "").split("@", 1)[0]) for step in build["steps"])
    == expected,
    "Pages build executes only the checked document pipeline",
  )
  steps = build["steps"]
  require(
    steps[0]["with"] == {"ref": "${{ github.sha }}", "persist-credentials": "false"},
    "Pages checks out the event source SHA without stored credentials",
  )
  require(steps[1]["with"] == {"python-version": "3.14"}, "Pages pinned Python")
  require(
    steps[2]["with"]
    == {
      "version": UV_VERSION,
      "checksum": uv_archive_checksums()["ubuntu-latest"],
      "enable-cache": "false",
    },
    "Pages locked uv version and checksum",
  )
  require(
    steps[4].get("env") == {"SCRATCH": "${{ runner.temp }}"}, "Pages document scratch boundary"
  )
  require(
    steps[5]["with"] == {"name": "github-pages", "path": "site/html", "retention-days": "1"},
    "Pages uploads only checked HTML under the fixed artifact name",
  )
  deploy = jobs["deploy"]
  require(deploy.get("needs") == "build", "Pages deployment needs the successful build")
  require(
    deploy["environment"]
    == {"name": "github-pages", "url": "${{ steps.deployment.outputs.page_url }}"},
    "Pages deployment environment and URL binding",
  )
  require(
    len(deploy["steps"]) == 1
    and deploy["steps"][0].get("uses", "").startswith("actions/deploy-pages@")
    and deploy["steps"][0].get("id") == "deployment"
    and deploy["steps"][0].get("with") == {"artifact_name": "github-pages"}
    and "run" not in deploy["steps"][0],
    "Pages deployment only consumes its current-run static artifact",
  )


def test_documentation_workflow_has_a_read_only_build_and_isolated_deployment() -> None:
  check_pages_policy(load_workflow(DOCS.read_text()))


@pytest.mark.parametrize(
  "defect",
  [
    "pull-request",
    "pull-request-target",
    "dispatch-ref",
    "push-branch",
    "build-ref",
    "deploy-ref",
    "dependency",
    "build-permission",
    "deploy-permission",
    "environment",
    "url",
    "upload-root",
    "artifact-name",
    "floating-action",
    "skip-build",
    "replace-build",
    "unchecked-mutation",
    "deploy-code",
    "checkout-ref",
  ],
)
def test_pages_policy_rejects_a_single_boundary_defect(defect: str) -> None:
  good = load_workflow(DOCS.read_text())
  check_pages_policy(good)
  bad = deepcopy(good)
  build = bad["jobs"]["build"]
  deploy = bad["jobs"]["deploy"]
  match defect:
    case "pull-request" | "pull-request-target":
      bad["on"][defect.replace("-", "_")] = {}
    case "dispatch-ref":
      bad["on"]["workflow_dispatch"] = {"inputs": {"ref": {"type": "string"}}}
    case "push-branch":
      bad["on"]["push"]["branches"] = ["*"]
    case "build-ref":
      build.pop("if")
    case "deploy-ref":
      deploy["if"] = "always()"
    case "dependency":
      deploy.pop("needs")
    case "build-permission":
      build["permissions"]["pages"] = "write"
    case "deploy-permission":
      deploy["permissions"]["contents"] = "write"
    case "environment":
      deploy["environment"]["name"] = "pypi"
    case "url":
      deploy["environment"]["url"] = "https://example.org"
    case "upload-root":
      build["steps"][-1]["with"]["path"] = "."
    case "artifact-name":
      deploy["steps"][0]["with"]["artifact_name"] = "unchecked"
    case "floating-action":
      deploy["steps"][0]["uses"] = "actions/deploy-pages@v5"
    case "skip-build":
      build["steps"][4]["if"] = "false"
    case "replace-build":
      build["steps"][4]["run"] = "true"
    case "unchecked-mutation":
      build["steps"].insert(-1, {"run": "touch site/html/unchecked.html"})
    case "deploy-code":
      deploy["steps"].append({"run": "uv run python tools/check.py"})
    case "checkout-ref":
      build["steps"][0]["with"]["ref"] = "${{ github.event.inputs.ref }}"
  with pytest.raises(ValueError, match="Pages"):
    check_pages_policy(bad)


@pytest.mark.parametrize(
  "defect",
  [
    "trigger",
    "permissions",
    "environment",
    "needs",
    "url",
    "index",
    "extra-publish",
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
      publish["environment"] = "unprotected"
    case "needs":
      publish["needs"].remove("consume")
    case "url":
      publish["steps"][2]["with"]["repository-url"] = "${{ inputs.url }}"
    case "index":
      publish["steps"][2]["with"]["repository-url"] = "https://test.pypi.org/legacy/"
    case "extra-publish":
      bad["jobs"]["publish-extra"] = deepcopy(publish)
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
    "index": "Fixed upload target",
    "extra-publish": "Release jobs",
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
