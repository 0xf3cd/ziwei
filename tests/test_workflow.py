"""CI 必须带锁运行与贡献指南相同的命令。"""

import re
from pathlib import Path

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
