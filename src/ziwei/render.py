"""只读文本盘面；不执行历法、改变星位或输出任意出生元数据。"""

from unicodedata import east_asian_width

from ziwei.chart import ZiweiChart
from ziwei.ganzhi import Dizhi


def _width(text: str) -> int:
  return sum(2 if east_asian_width(char) in ("W", "F") else 1 for char in text)


def render_text(chart: ZiweiChart) -> str:
  """返回十二宫边框格（巳午未申在上，寅丑子亥在下），末尾换行。

  每宫显示宫名、宫干支、身宫标记、星曜与禄权科忌、大限虚岁。不输出地点、来源等任意文本，
  因此记录中的控制字符不会成为终端指令。对齐假定等宽终端，东亚宽字符占两列。
  """
  if not isinstance(chart, ZiweiChart):
    raise TypeError("文本盘面须使用 ZiweiChart")
  changes = dict(
    zip(
      (chart.sihua.lu, chart.sihua.quan, chart.sihua.ke, chart.sihua.ji),
      ("禄", "权", "科", "忌"),
      strict=True,
    )
  )
  cells: dict[Dizhi | None, list[str]] = {None: []}
  for palace in chart.palaces:
    decade = next(p for p in chart.decades if p.dizhi is palace.dizhi)
    stars = [
      p.star.value + ("[" + changes[p.star] + "]" if p.star in changes else "")
      for p in chart.stars
      if p.dizhi is palace.dizhi
    ]
    cells[palace.dizhi] = [
      palace.name.value
      + " "
      + str(palace.ganzhi)
      + (" 身宫" if palace.dizhi is chart.shengong else ""),
      *stars,
      f"大限 {decade.start_age}-{decade.end_age}虚岁",
    ]
  layout = (
    (Dizhi.巳, Dizhi.午, Dizhi.未, Dizhi.申),
    (Dizhi.辰, None, None, Dizhi.酉),
    (Dizhi.卯, None, None, Dizhi.戌),
    (Dizhi.寅, Dizhi.丑, Dizhi.子, Dizhi.亥),
  )
  width = max(_width(line) for lines in cells.values() for line in lines)
  border = "+" + "+".join("-" * (width + 2) for _ in range(4)) + "+"
  output = [
    chart.bureau.value + " · 大限" + chart.decades[0].direction.value + " · 首尾包含",
    border,
  ]
  for row in layout:
    height = max(len(cells[branch]) for branch in row)
    for index in range(height):
      lines = [cells[branch][index] if index < len(cells[branch]) else "" for branch in row]
      output.append(
        "|" + "|".join(" " + line + " " * (width - _width(line) + 1) for line in lines) + "|"
      )
    output.append(border)
  return "\n".join(output) + "\n"
