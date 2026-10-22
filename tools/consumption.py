"""在仓外环境安装分发包并运行消费检查。"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path


def run(command: Sequence[str], *, cwd: Path) -> None:
  """在指定目录执行命令并传播失败。"""
  print(f"+ {' '.join(command)}", flush=True)
  subprocess.run(command, cwd=cwd, check=True)


def install_and_consume(wheel: Path, version: str, directory: Path, *, root: Path) -> None:
  """按root中的锁文件安装依赖和指定wheel，仓外执行普通和优化模式检查。"""
  if directory.resolve().is_relative_to(root.resolve()):
    raise ValueError("Installed consumption must run outside the repository")
  requirements = directory / "runtime.txt"
  run(
    (
      "uv",
      "export",
      "--locked",
      "--no-dev",
      "--no-emit-project",
      "--no-editable",
      "--output-file",
      str(requirements),
    ),
    cwd=root,
  )
  environment = directory / "consumer"
  run(("uv", "venv", "--python", sys.executable, str(environment)), cwd=root)
  python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
  run(
    (
      "uv",
      "pip",
      "install",
      "--python",
      str(python),
      "--require-hashes",
      "--default-index",
      "https://pypi.org/simple",
      "--requirements",
      str(requirements),
    ),
    cwd=root,
  )
  run(("uv", "pip", "install", "--python", str(python), "--no-deps", str(wheel)), cwd=root)
  for mode in ((), ("-O",)):
    run(
      (str(python), *mode, "-I", str(root / "tools/installed_check.py"), version),
      cwd=directory,
    )
