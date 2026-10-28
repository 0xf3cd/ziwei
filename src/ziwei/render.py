"""只读文本与SVG盘面；不执行历法、改变星位或输出任意出生元数据。"""

from typing import Final
from unicodedata import east_asian_width
from xml.etree.ElementTree import Element, SubElement, tostring

from ziwei.brightness import BrightnessTable
from ziwei.chart import ZiweiChart, chart_brightness, palace_view
from ziwei.ganzhi import Dizhi
from ziwei.palaces import PalaceName, sanfang_sizheng

_PALACE_LAYOUT: Final = (
  (Dizhi.巳, Dizhi.午, Dizhi.未, Dizhi.申),
  (Dizhi.辰, None, None, Dizhi.酉),
  (Dizhi.卯, None, None, Dizhi.戌),
  (Dizhi.寅, Dizhi.丑, Dizhi.子, Dizhi.亥),
)

_SVG_STYLE: Final = """
.ziwei-chart text{font-family:"Noto Sans CJK SC","Microsoft YaHei","PingFang SC",sans-serif;fill:#263e3b}
.ziwei-chart .palace rect{fill:#fffefa;stroke:#c5ceca;stroke-width:1}
.ziwei-chart .palace .name{font-size:22px;font-weight:600}
.ziwei-chart .ganzhi{font-size:16px;text-anchor:end}
.ziwei-chart .body,.ziwei-chart .relation{font-size:14px}
.ziwei-chart .relation{text-anchor:end;font-weight:600}
.ziwei-chart .star{font-size:19px}
.ziwei-chart .decade{font-size:13px;fill:#52645f}
.ziwei-chart .divider{stroke:#d9dfdb;stroke-width:1}
.ziwei-chart .selected rect{fill:#f8e8dd;stroke:#a74c30;stroke-width:3}
.ziwei-chart .sanhe rect{fill:#e8f1eb;stroke:#377461;stroke-width:2}
.ziwei-chart .opposite rect{fill:#eaf0f3;stroke:#4b6d83;stroke-width:2;stroke-dasharray:6 4}
.ziwei-chart .selected .relation{fill:#913e26}
.ziwei-chart .sanhe .relation{fill:#28624f}
.ziwei-chart .opposite .relation{fill:#3b5d73}
.ziwei-chart .summary text{text-anchor:middle}
.ziwei-chart .title{font-size:32px;font-weight:600}
.ziwei-chart .subtitle,.ziwei-chart .age,.ziwei-chart .legend{font-size:14px;fill:#52645f}
.ziwei-chart .bureau{font-size:26px;font-weight:600}
.ziwei-chart .selection{font-size:18px}
""".strip()


def _width(text: str) -> int:
  return sum(2 if east_asian_width(char) in ("W", "F") else 1 for char in text)


def render_text(chart: ZiweiChart, *, brightness_table: BrightnessTable | None = None) -> str:
  """返回十二宫边框格（巳午未申在上，寅丑子亥在下），末尾换行。

  每宫显示宫名、宫干支、身宫标记、星曜与禄权科忌、大限虚岁。不输出地点、来源等任意文本，
  因此记录中的控制字符不会成为终端指令。对齐假定等宽终端，东亚宽字符占两列。
  brightness_table为None时不查询亮度；显式选择表后，首行标明表名，主星后附原名等级。
  """
  if not isinstance(chart, ZiweiChart):
    raise TypeError("文本盘面须使用 ZiweiChart")
  levels = (
    {}
    if brightness_table is None
    else {
      reading.star: reading.level for reading in chart_brightness(chart, table=brightness_table)
    }
  )
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
      p.star.value
      + ("[" + changes[p.star] + "]" if p.star in changes else "")
      + (" (" + level.value + ")" if (level := levels.get(p.star)) is not None else "")
      for p in chart.stars
      if p.dizhi is palace.dizhi
    ]
    cells[palace.dizhi] = [
      palace.name.value
      + " "
      + str(palace.ganzhi)
      + (" 身宫" if palace.dizhi is chart.shengong else ""),
      *stars,
      f"大限 {decade.start_age}-{decade.end_age}{decade.age_convention}",
    ]
  width = max(_width(line) for lines in cells.values() for line in lines)
  border = "+" + "+".join("-" * (width + 2) for _ in range(4)) + "+"
  output = [
    chart.bureau.value
    + " · 大限"
    + chart.decades[0].direction.value
    + " · "
    + chart.decades[0].age_convention
    + "首尾包含"
    + (" · " + brightness_table.value if brightness_table is not None else ""),
    border,
  ]
  for row in _PALACE_LAYOUT:
    height = max(len(cells[branch]) for branch in row)
    for index in range(height):
      lines = [cells[branch][index] if index < len(cells[branch]) else "" for branch in row]
      output.append(
        "|" + "|".join(" " + line + " " * (width - _width(line) + 1) for line in lines) + "|"
      )
    output.append(border)
  return "\n".join(output) + "\n"


def _svg_text(parent: Element, value: str, *, x: int, y: int, class_name: str) -> None:
  SubElement(parent, "text", {"x": str(x), "y": str(y), "class": class_name}).text = value


def render_svg(
  chart: ZiweiChart,
  *,
  selected_palace: PalaceName | Dizhi | None = None,
  brightness_table: BrightnessTable | None = None,
) -> str:
  """返回自包含的静态SVG，显示已有十二宫、星曜、生年四化、身宫与大限。

  selected_palace接受宫名或地支枚举，突出本宫、两个三合宫和对宫；None不高亮。
  类型错误时抛TypeError，不接受字符串（如"命宫"或"子"）。显示不重算或修改命盘，也不输出出生记录中的
  生日、地点、来源等任意元数据。SVG不含脚本或外部资源；写入文件时须使用UTF-8。
  所有宫格等高，高度由星数最多的一宫决定；星曜按原盘顺序从左到右、从上到下排列。
  brightness_table为None时不查询亮度；选择表后，等级另行显示，中央标明表名。
  """
  if not isinstance(chart, ZiweiChart):
    raise TypeError("SVG盘面须使用 ZiweiChart")
  levels = (
    {}
    if brightness_table is None
    else {
      reading.star: reading.level for reading in chart_brightness(chart, table=brightness_table)
    }
  )
  selected = None if selected_palace is None else palace_view(chart, selected_palace)
  relations = (
    {}
    if selected is None
    else dict(
      zip(
        sanfang_sizheng(selected.palace.dizhi),
        ("selected", "sanhe", "sanhe", "opposite"),
        strict=True,
      )
    )
  )
  labels = {"selected": "本宫", "sanhe": "三合", "opposite": "对宫"}
  views = {palace.dizhi: palace_view(chart, palace.dizhi) for palace in chart.palaces}
  decades = {decade.dizhi: decade for decade in chart.decades}
  star_rows = max((len(view.stars) + 1) // 2 for view in views.values())
  cell_width = 256
  row_height = 28 if brightness_table is None else 48
  cell_height = max(208, 120 + star_rows * row_height)
  margin = 16
  width = 4 * cell_width + 2 * margin
  height = 4 * cell_height + 2 * margin

  root = Element(
    "svg",
    {
      "xmlns": "http://www.w3.org/2000/svg",
      "width": str(width),
      "height": str(height),
      "viewBox": f"0 0 {width} {height}",
      "role": "img",
      "class": "ziwei-chart",
      "aria-label": "紫微斗数十二宫命盘",
    },
  )
  SubElement(root, "title").text = "紫微斗数十二宫命盘"
  SubElement(root, "desc").text = "只显示已有命盘，不重新排盘或解释吉凶。" + (
    "未选择高亮宫位。" if selected is None else "以文字和边框区分本宫、两个三合宫与对宫。"
  )
  SubElement(root, "style").text = _SVG_STYLE + (
    "\n.ziwei-chart .brightness,.ziwei-chart .brightness-table{font-size:13px;fill:#52645f}"
    if brightness_table is not None
    else ""
  )
  SubElement(root, "rect", {"width": str(width), "height": str(height), "fill": "#f8f6f1"})

  for row_index, row in enumerate(_PALACE_LAYOUT):
    for column, branch in enumerate(row):
      if branch is None:
        continue
      view = views[branch]
      role = relations.get(branch)
      group = SubElement(
        root,
        "g",
        {
          "class": "palace" + (" " + role if role is not None else ""),
          "data-dizhi": branch.name.lower(),
          "transform": f"translate({margin + column * cell_width} {margin + row_index * cell_height})",
        },
      )
      SubElement(group, "rect", {"width": str(cell_width), "height": str(cell_height)})
      _svg_text(group, view.palace.name.value, x=16, y=30, class_name="name")
      _svg_text(group, str(view.palace.ganzhi), x=cell_width - 16, y=30, class_name="ganzhi")
      if view.is_shengong:
        _svg_text(group, "身宫", x=16, y=58, class_name="body")
      if role is not None:
        _svg_text(group, labels[role], x=cell_width - 16, y=58, class_name="relation")
      changes = {
        star: label
        for star, label in zip(
          (view.lu, view.quan, view.ke, view.ji), ("禄", "权", "科", "忌"), strict=True
        )
        if star is not None
      }
      for index, position in enumerate(view.stars):
        star = position.star
        _svg_text(
          group,
          star.value + ("[" + changes[star] + "]" if star in changes else ""),
          x=16 + index % 2 * 112,
          y=88 + index // 2 * row_height,
          class_name="star",
        )
        if (level := levels.get(star)) is not None:
          _svg_text(
            group,
            level.value,
            x=16 + index % 2 * 112,
            y=108 + index // 2 * row_height,
            class_name="brightness",
          )
      SubElement(
        group,
        "line",
        {
          "x1": "16",
          "x2": str(cell_width - 16),
          "y1": str(cell_height - 35),
          "y2": str(cell_height - 35),
          "class": "divider",
        },
      )
      decade = decades[branch]
      _svg_text(
        group,
        f"大限 {decade.start_age}-{decade.end_age}{decade.age_convention}",
        x=16,
        y=cell_height - 15,
        class_name="decade",
      )

  summary = SubElement(
    root,
    "g",
    {
      "class": "summary",
      "transform": f"translate({width // 2} {margin + cell_height})",
    },
  )
  _svg_text(summary, "紫微斗数", x=0, y=72, class_name="title")
  _svg_text(summary, "本命十二宫", x=0, y=101, class_name="subtitle")
  _svg_text(summary, chart.bureau.value, x=0, y=160, class_name="bureau")
  _svg_text(
    summary,
    "大限"
    + chart.decades[0].direction.value
    + " · "
    + chart.decades[0].age_convention
    + "首尾包含",
    x=0,
    y=191,
    class_name="age",
  )
  _svg_text(
    summary,
    "未选择高亮宫位"
    if selected is None
    else f"选宫 · {selected.palace.name.value} {selected.palace.ganzhi}",
    x=0,
    y=249,
    class_name="selection",
  )
  if selected is not None:
    _svg_text(summary, "本宫 · 三合两宫 · 对宫", x=0, y=286, class_name="legend")
  if brightness_table is not None:
    _svg_text(summary, brightness_table.value, x=0, y=326, class_name="brightness-table")
  return tostring(root, encoding="unicode") + "\n"
