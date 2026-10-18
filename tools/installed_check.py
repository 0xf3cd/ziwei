"""隔离验证已安装的包。"""

import sys
from importlib.metadata import distribution
from pathlib import Path

import ziwei


def main(expected_version: str) -> None:
  """检查身份、导入路径及原生历法库隔离。"""
  metadata = distribution("ziwei")
  origin = Path(str(ziwei.__file__)).resolve()
  if not origin.is_relative_to(Path(sys.prefix).resolve()):
    raise ValueError("Imported ziwei from outside the consumer environment")
  if metadata.version != expected_version:
    raise ValueError("Installed version differs from the built version")
  if not origin.with_name("py.typed").is_file():
    raise ValueError("Installed package is missing py.typed")
  if any(
    name == "celestial_calendar" or name.startswith("celestial_calendar.") for name in sys.modules
  ):
    raise ValueError("Import initialized the calendar adapter")
  print(f"Installed ziwei {metadata.version}; optimized={sys.flags.optimize}")


if __name__ == "__main__":
  main(sys.argv[1])
