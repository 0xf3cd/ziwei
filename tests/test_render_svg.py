"""核SVG显示内容、关系角色、安全构造与几何；不以显示输出校验安星。"""

import re
import subprocess
import sys
from copy import deepcopy
from dataclasses import asdict, replace
from typing import Never
from unicodedata import east_asian_width
from xml.etree.ElementTree import Element, SubElement, fromstring, tostring

import pytest

from ziwei import calendar, chart, resolver, timezone
from ziwei.birth import Gender, LunarBirthRecord
from ziwei.chart import ZiweiChart, create_chart
from ziwei.config import ChartConfig, TianmaRule
from ziwei.ganzhi import Dizhi
from ziwei.palaces import PalaceName
from ziwei.render import render_svg
from ziwei.sihua import SihuaVariant
from ziwei.stars import Star

pytestmark = pytest.mark.usefixtures("unload_celestial")
SVG = "{http://www.w3.org/2000/svg}"


def _safe_tree(svg: str) -> Element:
  assert "<!DOCTYPE" not in svg and "<!ENTITY" not in svg
  root = fromstring(svg)
  assert root.tag == SVG + "svg"
  tags = {SVG + name for name in ("svg", "title", "desc", "style", "rect", "g", "text", "line")}
  attributes = {
    "width",
    "height",
    "viewBox",
    "role",
    "aria-label",
    "fill",
    "class",
    "data-dizhi",
    "transform",
    "x",
    "y",
    "x1",
    "x2",
    "y1",
    "y2",
  }
  for node in root.iter():
    assert node.tag in tags
    assert set(node.attrib) <= attributes
    assert not any(name.lower().startswith("on") for name in node.attrib)
    if node.tag == SVG + "style":
      assert not re.search(r"url\s*\(|@import|@font-face", node.text or "", re.IGNORECASE)
    for value in node.attrib.values():
      assert not re.search(r"(?:https?:|data:|javascript:|url\s*\()", value, re.IGNORECASE)
  return root


def _palaces(root: Element) -> dict[str, Element]:
  return {
    node.attrib["data-dizhi"]: node
    for node in root.findall(SVG + "g")
    if "data-dizhi" in node.attrib
  }


def _texts(group: Element, class_name: str) -> list[str]:
  return [
    node.text or "" for node in group.findall(SVG + "text") if node.get("class") == class_name
  ]


@pytest.fixture(
  params=[
    (1954, 9, 7, Dizhi.子, Gender.男),
    (1954, 10, 1, Dizhi.酉, Gender.男),
    (2024, 1, 1, Dizhi.午, Gender.女),
    (1984, 2, 2, Dizhi.酉, Gender.女),
    (2024, 1, 1, Dizhi.子, Gender.女),
  ],
  ids=["reference", "eight-stars", "empty", "empty-shengong", "shared-sihua"],
)
def svg_chart(request: pytest.FixtureRequest, chart_choices: ChartConfig) -> ZiweiChart:
  year, month, day, shichen, gender = request.param
  return create_chart(
    LunarBirthRecord(
      year=year, month=month, day=day, is_leap_month=False, shichen=shichen, gender=gender
    ),
    replace(chart_choices, tianma_rule=TianmaRule.年支天马),
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )


def test_svg_preserves_each_palace_and_stored_content(svg_chart: ZiweiChart) -> None:
  before = asdict(svg_chart)
  svg = render_svg(svg_chart)
  root = _safe_tree(svg)
  cells = _palaces(root)
  assert len(cells) == 12
  assert len([text for cell in cells.values() for text in _texts(cell, "star")]) == 30
  changes = dict(
    zip(
      (svg_chart.sihua.lu, svg_chart.sihua.quan, svg_chart.sihua.ke, svg_chart.sihua.ji),
      ("禄", "权", "科", "忌"),
      strict=True,
    )
  )
  for palace in svg_chart.palaces:
    cell = cells[palace.dizhi.name.lower()]
    assert _texts(cell, "name") == [palace.name.value]
    assert _texts(cell, "ganzhi") == [str(palace.ganzhi)]
    assert _texts(cell, "body") == (["身宫"] if palace.dizhi is svg_chart.shengong else [])
    assert _texts(cell, "star") == [
      position.star.value + ("[" + changes[position.star] + "]" if position.star in changes else "")
      for position in svg_chart.stars
      if position.dizhi is palace.dizhi
    ]
    decade = next(item for item in svg_chart.decades if item.dizhi is palace.dizhi)
    assert _texts(cell, "decade") == [
      f"大限 {decade.start_age}-{decade.end_age}{decade.age_convention}"
    ]
    assert cell.attrib["class"] == "palace"
    assert _texts(cell, "relation") == []
  assert sum(len(_texts(cell, "body")) for cell in cells.values()) == 1
  assert svg == render_svg(svg_chart)
  assert asdict(svg_chart) == before
  assert svg.endswith("\n")
  assert root.get("role") == "img" and root.findtext(SVG + "title")
  assert root.findtext(SVG + "desc")


@pytest.mark.parametrize(
  "base,members",
  [
    (Dizhi[base], members)
    for base, members in (
      ("子", "子辰申午"),
      ("丑", "丑巳酉未"),
      ("寅", "寅午戌申"),
      ("卯", "卯未亥酉"),
      ("辰", "辰申子戌"),
      ("巳", "巳酉丑亥"),
      ("午", "午戌寅子"),
      ("未", "未亥卯丑"),
      ("申", "申子辰寅"),
      ("酉", "酉丑巳卯"),
      ("戌", "戌寅午辰"),
      ("亥", "亥卯未巳"),
    )
  ],
)
def test_svg_highlights_exact_relationship_roles(
  lunar_chart: ZiweiChart, base: Dizhi, members: str
) -> None:
  cells = _palaces(_safe_tree(render_svg(lunar_chart, selected_palace=base)))
  expected = dict(
    zip(
      (Dizhi[branch].name.lower() for branch in members),
      ("selected", "sanhe", "sanhe", "opposite"),
      strict=True,
    )
  )
  labels = {"selected": "本宫", "sanhe": "三合", "opposite": "对宫"}
  for branch, cell in cells.items():
    role = expected.get(branch)
    assert cell.attrib["class"] == "palace" + (" " + role if role is not None else "")
    assert _texts(cell, "relation") == ([labels[role]] if role is not None else [])


def test_svg_palace_names_and_branches_are_equivalent(lunar_chart: ZiweiChart) -> None:
  for palace in lunar_chart.palaces:
    assert render_svg(lunar_chart, selected_palace=palace.name) == render_svg(
      lunar_chart, selected_palace=palace.dizhi
    )
  assert render_svg(lunar_chart, selected_palace=PalaceName.夫妻) == render_svg(
    lunar_chart, selected_palace=PalaceName.妻妾
  )


@pytest.mark.parametrize("selected", [None, *Dizhi])
def test_svg_selection_changes_summary_but_not_stored_palace_content(
  svg_chart: ZiweiChart, selected: Dizhi | None
) -> None:
  root = _safe_tree(render_svg(svg_chart, selected_palace=selected))
  summary = root.find(SVG + "g[@class='summary']")
  assert summary is not None
  if selected is None:
    selection = "未选择高亮宫位"
  else:
    palace = next(palace for palace in svg_chart.palaces if palace.dizhi is selected)
    selection = f"选宫 · {palace.name.value} {palace.ganzhi}"
  expected = [
    ("title", "紫微斗数"),
    ("subtitle", "本命十二宫"),
    ("bureau", svg_chart.bureau.value),
    (
      "age",
      "大限"
      + svg_chart.decades[0].direction.value
      + " · "
      + svg_chart.decades[0].age_convention
      + "首尾包含",
    ),
    ("selection", selection),
  ]
  if selected is not None:
    expected.append(("legend", "本宫 · 三合两宫 · 对宫"))
  assert [(node.get("class"), node.text) for node in summary.findall(SVG + "text")] == expected
  assert root.findtext(SVG + "desc") == "只显示已有命盘，不重新排盘或解释吉凶。" + (
    "未选择高亮宫位。" if selected is None else "以文字和边框区分本宫、两个三合宫与对宫。"
  )
  plain_cells = _palaces(_safe_tree(render_svg(svg_chart)))
  for branch, cell in _palaces(root).items():
    for class_name in ("name", "ganzhi", "body", "star", "decade"):
      assert _texts(cell, class_name) == _texts(plain_cells[branch], class_name)


def test_svg_does_not_print_software_versions(svg_chart: ZiweiChart) -> None:
  root = _safe_tree(render_svg(svg_chart, selected_palace=PalaceName.命宫))
  content = " ".join(
    node.text or ""
    for node in root.iter()
    if node.tag in (SVG + "text", SVG + "title", SVG + "desc")
  )
  assert re.search(r"(?<!\d)v?\d+\.\d+(?:\.\d+)?(?:[-+][\w.]+)?", content, re.IGNORECASE) is None


def test_svg_styles_are_scoped_to_the_chart(lunar_chart: ZiweiChart) -> None:
  root = _safe_tree(render_svg(lunar_chart))
  assert root.get("class") == "ziwei-chart"
  style = root.findtext(SVG + "style") or ""
  rules = re.findall(r"([^{}]+)\{[^}]*\}", style)
  assert rules
  for rule in rules:
    assert all(selector.strip().startswith(".ziwei-chart ") for selector in rule.split(","))


@pytest.mark.parametrize("role", ["selected", "sanhe", "opposite"])
def test_svg_relationship_role_classes_have_color_styles(
  lunar_chart: ZiweiChart, role: str
) -> None:
  root = _safe_tree(render_svg(lunar_chart, selected_palace=PalaceName.命宫))
  style = root.findtext(SVG + "style") or ""
  rules = re.findall(rf"\.ziwei-chart\s+\.{role}\s+(?:rect|\.relation)\s*\{{([^}}]*)\}}", style)
  assert any(re.search(r"(?:^|;)\s*(?:fill|stroke)\s*:\s*[^;\s]+", rule) for rule in rules)


@pytest.mark.parametrize("bad", [None, True, 1, {}, "chart"])
def test_svg_rejects_non_chart(bad: object) -> None:
  with pytest.raises(TypeError):
    render_svg(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["命宫", "子", 0, True, Star.紫微, object()])
def test_svg_rejects_non_enum_selection(lunar_chart: ZiweiChart, bad: object) -> None:
  with pytest.raises(TypeError):
    render_svg(lunar_chart, selected_palace=bad)  # type: ignore[arg-type]


def test_svg_fixed_palace_positions_and_content_bounds(svg_chart: ZiweiChart) -> None:
  root = _safe_tree(render_svg(svg_chart, selected_palace=PalaceName.命宫))
  cells = _palaces(root)
  assert tuple(cells) == (
    "si",
    "wu",
    "wei",
    "shen",
    "chen",
    "you",
    "mao",
    "xu",
    "yin",
    "chou",
    "zi",
    "hai",
  )
  style = root.findtext(SVG + "style") or ""
  font = re.search(r"\.star\s*\{[^}]*font-size:\s*(\d+)px", style)
  assert font is not None
  font_size = int(font[1])
  image_width, image_height = float(root.attrib["width"]), float(root.attrib["height"])
  assert root.attrib["viewBox"] == f"0 0 {int(image_width)} {int(image_height)}"
  for cell in cells.values():
    frame = cell.find(SVG + "rect")
    divider = cell.find(SVG + "line")
    assert frame is not None and divider is not None
    width, height = float(frame.attrib["width"]), float(frame.attrib["height"])
    offset = re.fullmatch(r"translate\((\d+) (\d+)\)", cell.attrib["transform"])
    assert offset is not None
    assert 0 <= int(offset[1]) < int(offset[1]) + width <= image_width
    assert 0 <= int(offset[2]) < int(offset[2]) + height <= image_height
    assert float(divider.attrib["y1"]) == float(divider.attrib["y2"]) < height
    for text in cell.findall(SVG + "text"):
      if text.get("class") == "star":
        x, y = float(text.attrib["x"]), float(text.attrib["y"])
        units = sum(1 if east_asian_width(c) in ("W", "F") else 0.6 for c in text.text or "")
        assert x > 0 and x + units * font_size < width
        assert y - font_size > 58
        assert y + font_size * 0.3 < float(divider.attrib["y1"])
      elif text.get("class") == "decade":
        assert float(divider.attrib["y1"]) < float(text.attrib["y"]) < height


def test_svg_dense_and_empty_shengong_examples(chart_choices: ChartConfig) -> None:
  dense = create_chart(
    LunarBirthRecord(
      year=1954, month=10, day=1, is_leap_month=False, shichen=Dizhi.酉, gender=Gender.男
    ),
    replace(chart_choices, tianma_rule=TianmaRule.年支天马),
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  brothers = next(palace for palace in dense.palaces if palace.name is PalaceName.兄弟)
  dense_cell = _palaces(_safe_tree(render_svg(dense)))[brothers.dizhi.name.lower()]
  assert len(_texts(dense_cell, "star")) == 8
  assert "廉贞[禄]" in _texts(dense_cell, "star")
  empty = create_chart(
    LunarBirthRecord(
      year=1984, month=2, day=2, is_leap_month=False, shichen=Dizhi.酉, gender=Gender.女
    ),
    chart_choices,
    sihua_variant=SihuaVariant.排命盘口诀转录,
  )
  cells = _palaces(_safe_tree(render_svg(empty)))
  assert _texts(cells["zi"], "star") == []
  assert _texts(cells["zi"], "body") == ["身宫"]
  assert _texts(cells["zi"], "name") == ["迁移"]
  assert _texts(cells["wu"], "body") == []


@pytest.mark.parametrize("variant", tuple(SihuaVariant))
def test_svg_uses_the_chosen_sihua(chart_choices: ChartConfig, variant: SihuaVariant) -> None:
  result = create_chart(
    LunarBirthRecord(
      year=1970, month=1, day=1, is_leap_month=False, shichen=Dizhi.子, gender=Gender.男
    ),
    chart_choices,
    sihua_variant=variant,
  )
  content = " ".join(_safe_tree(render_svg(result)).itertext())
  for star, label in zip(
    (result.sihua.lu, result.sihua.quan, result.sihua.ke, result.sihua.ji),
    ("禄", "权", "科", "忌"),
    strict=True,
  ):
    assert star.value + "[" + label + "]" in content


@pytest.mark.parametrize(
  "payload", ["\x00\x1b\ud800", "\udc00", '</text><script>alert("x")</script>&']
)
def test_svg_excludes_arbitrary_birth_metadata(lunar_chart: ZiweiChart, payload: str) -> None:
  record = replace(lunar_chart.calculation.record, place=payload, source=payload)
  result = replace(lunar_chart, calculation=replace(lunar_chart.calculation, record=record))
  svg = render_svg(result)
  _safe_tree(svg)
  assert payload not in svg
  assert svg == render_svg(lunar_chart)
  assert isinstance(record, LunarBirthRecord)
  assert str(record.year) not in svg


def test_svg_escapes_stored_labels_without_changing_them(lunar_chart: ZiweiChart) -> None:
  result = deepcopy(lunar_chart)
  for decade in result.decades:
    object.__setattr__(decade, "age_convention", '龄<&"')
  before = asdict(result)
  svg = render_svg(result)
  content = " ".join(_safe_tree(svg).itertext())
  assert "&lt;" in svg and "&amp;" in svg
  assert content.count('龄<&"') == 13
  assert asdict(result) == before
  assert all(decade.age_convention == "虚岁" for decade in lunar_chart.decades)


@pytest.mark.parametrize(
  "defect", ["script", "foreign", "event", "reference", "css", "dtd", "entity"]
)
def test_svg_safety_checks_reject_forbidden_constructs(
  lunar_chart: ZiweiChart, defect: str
) -> None:
  svg = render_svg(lunar_chart)
  root = fromstring(svg)
  if defect == "script":
    SubElement(root, SVG + "script").text = "alert(1)"
  elif defect == "foreign":
    SubElement(root, SVG + "foreignObject")
  elif defect == "event":
    root.set("onload", "alert(1)")
  elif defect == "reference":
    root.set("href", "https://example.invalid/image.svg")
  elif defect == "css":
    style = root.find(SVG + "style")
    assert style is not None
    style.text = (style.text or "") + ".star{fill:url(https://example.invalid/style)}"
  if defect == "dtd":
    unsafe = "<!DOCTYPE svg>" + svg
  elif defect == "entity":
    unsafe = '<!DOCTYPE svg [<!ENTITY example "value">]>' + svg
  else:
    unsafe = tostring(root, encoding="unicode")
  with pytest.raises(AssertionError):
    _safe_tree(unsafe)


def test_svg_does_not_recompute_or_access_calendar(
  lunar_chart: ZiweiChart, monkeypatch: pytest.MonkeyPatch
) -> None:
  before = deepcopy(lunar_chart)

  def forbidden(*args: object, **kwargs: object) -> Never:
    raise AssertionError("SVG调用了计算或资源入口")

  for owner, names in (
    (
      chart,
      (
        "resolve",
        "create_chart",
        "place_stars",
        "shengnian_sihua",
        "place_decades",
        "_chart_frame",
      ),
    ),
    (resolver, ("resolve",)),
    (
      calendar,
      (
        "validate_lunar_date",
        "gregorian_to_lunar",
        "lunar_to_gregorian",
        "lichun_jd",
        "utc_to_ut1_jd",
        "apparent_solar",
        "celestial_version",
      ),
    ),
    (timezone, ("_load_zone", "current_timezone_data", "resolve_civil_time")),
  ):
    for name in names:
      monkeypatch.setattr(owner, name, forbidden)
  for name in tuple(sys.modules):
    if name.split(".")[0] in ("celestial_calendar", "tzdata"):
      monkeypatch.delitem(sys.modules, name)
  monkeypatch.setitem(sys.modules, "celestial_calendar", None)
  monkeypatch.setitem(sys.modules, "tzdata", None)
  _safe_tree(render_svg(lunar_chart))
  _safe_tree(render_svg(lunar_chart, selected_palace=PalaceName.命宫))
  assert lunar_chart == before


def test_svg_module_import_does_not_initialize_native_resources() -> None:
  script = """
import sys
sys.modules['celestial_calendar'] = None
sys.modules['tzdata'] = None
from ziwei.render import render_svg
if not callable(render_svg):
  raise RuntimeError('SVG entry is missing')
"""
  result = subprocess.run([sys.executable, "-I", "-c", script], capture_output=True, text=True)
  assert result.returncode == 0, result.stderr
