"""CI 必须带锁运行与贡献指南相同的命令。"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/checks.yml"


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
  actions = re.findall(r"^\s+- uses: (\S+)", workflow, re.MULTILINE)
  assert len(actions) == 3
  assert all(re.fullmatch(r"[\w-]+/[\w-]+@[0-9a-f]{40}", action) for action in actions)


def test_all_actions_use_full_commit_sha() -> None:
  check_action_pins(WORKFLOW.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
  "action", ["actions/checkout", "actions/setup-python", "astral-sh/setup-uv"]
)
def test_action_pin_guard_rejects_floating_tag(action: str) -> None:
  workflow = WORKFLOW.read_text(encoding="utf-8")
  mutated, count = re.subn(re.escape(action) + r"@[0-9a-f]{40}", action + "@v7", workflow)
  assert count == 1
  with pytest.raises(AssertionError):
    check_action_pins(mutated)


def test_each_ci_job_binds_uv_archive_checksum() -> None:
  workflow = WORKFLOW.read_text(encoding="utf-8")
  jobs = re.findall(
    r'- os: (\S+)\n\s+python: "([\d.]+)"\n\s+uv-checksum: "([0-9a-f]{64})"', workflow
  )
  assert [(os, python) for os, python, _ in jobs] == [
    ("ubuntu-latest", "3.11"),
    ("ubuntu-latest", "3.14"),
    ("macos-latest", "3.14"),
    ("windows-latest", "3.14"),
  ]
  assert jobs[0][2] == jobs[1][2] and len({checksum for _, _, checksum in jobs}) == 3
  uv_step = workflow.split("- uses: astral-sh/setup-uv@", 1)[1].split("- run:", 1)[0]
  assert "checksum: ${{ matrix.uv-checksum }}" in uv_step
  assert 'version: "0.12.5"' in uv_step
