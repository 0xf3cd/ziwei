"""核对短引原字、解释层次，以及知识说明是否取自领域定义。"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ziwei import stars
from ziwei.ganzhi import Ganzhi, Wuxing, nayin
from ziwei.knowledge import load_catalog
from ziwei.knowledge.model import (
  CurationStatus,
  DisplayEligibility,
  EvidenceAspect,
  PremiseStatus,
  SourceStatus,
  TextLayer,
)


@pytest.mark.parametrize(
  "identifier,quote,locator,source,aspect",
  [
    ("zhongzhou.decades-text", "悉依局数", "起大限", "zhongzhou-wangtingzhi", EvidenceAspect.规则),
    ("lifedna.leap-next", "統一算次月", "第2节", "lifedna-flying", EvidenceAspect.查法),
    ("lifedna.opposes-lichun", "很大的錯誤", "第1节", "lifedna-flying", EvidenceAspect.查法),
    ("lifedna.opposes-late-zi", "那也是有問題的", "第3节", "lifedna-flying", EvidenceAspect.查法),
    (
      "zhongyi999.huoling-year-only",
      "而不论生时",
      "反对",
      "zhongyi999-paimingpan",
      EvidenceAspect.查法,
    ),
    ("zhongyi999.kongjie-name", "又名“地空”", "按语", "zhongyi999-paimingpan", EvidenceAspect.查法),
  ],
)
def test_modern_excerpts_retain_original_words_and_attribution(
  identifier: str, quote: str, locator: str, source: str, aspect: EvidenceAspect
) -> None:
  citations = {item.id: item for item in load_catalog().citations}
  citation = citations["citation." + identifier]
  assert citation.quote == quote
  assert locator in citation.locator
  assert citation.source_id == "source." + source
  assert citation.layer is TextLayer.今人说明
  assert citation.aspects == (aspect,)


def test_unverified_figure_identity_is_not_replaced_by_a_body_excerpt() -> None:
  catalog = load_catalog()
  citations = {item.id: item for item in catalog.citations}
  entries = {item.id: item for item in catalog.entries}
  sources = {item.id: item for item in catalog.sources}
  figure = citations["citation.zhongzhou.decades-figure4"]
  assert figure.quote == "安大限"
  assert all(text in figure.limits for text in ("2017-11-06", "404", "图题与图内岁数未核"))
  assert "支持局数起限、命宫起及含首尾" not in figure.limits
  assert "岁数证据在图中" not in figure.limits
  period = entries["entry.decades.xusui-inclusive"]
  assert figure.id not in period.citation_ids
  assert "citation.zhongzhou.decades-text" in period.citation_ids
  body = citations["citation.zhongzhou.decades-text"]
  assert "2017-11-06" in body.locator and "存档" in body.locator
  assert "只支持局数起限" in body.limits
  assert sources[figure.source_id].status is SourceStatus.待核
  source = sources[figure.source_id]
  assert source.url == (
    "https://web.archive.org/web/20171106140353/"
    "http://blog.sina.com.cn/s/blog_4ff71e4e0100ciex.html"
  )
  assert "2017-11-06" in source.edition and "存档" in source.provenance
  assert "404" in source.limits


def test_source_readings_remain_separate_from_executable_choices() -> None:
  catalog = load_catalog()
  citations = {item.id: item for item in catalog.citations}
  entries = {item.id: item for item in catalog.entries}
  sources = {item.id: item for item in catalog.sources}
  assert citations["citation.quanshu.huoling-starts"].aspects == (EvidenceAspect.规则,)
  assert citations["citation.quanshu.huoling-starts"].layer is TextLayer.原文
  for identifier in ("zhongzhou", "jingcheng", "zhongyi999"):
    assert citations[f"citation.{identifier}.huoling-direction"].aspects == (
      EvidenceAspect.规则,
      EvidenceAspect.查法,
    )
  pending = entries["entry.star.huoling-year-only-pending"]
  forward = entries["entry.star.huoling-forward"]
  assert pending.premise_status is PremiseStatus.待定 and pending.variant_ids == ()
  assert "未具名" in pending.statement and "例解" in pending.recheck
  assert pending.display is DisplayEligibility.暂不默认展示
  assert forward.premise_status is PremiseStatus.已明确
  assert forward.curation is CurationStatus.已整理
  assert forward.chart_match == "未评估"
  kongjie = entries["entry.star.kongjie-hour"]
  assert set(kongjie.citation_ids) == {
    "citation.quanshu.kongjie",
    "citation.zhongzhou.fubi-wen-kongjie",
    "citation.zhongyi999.kongjie-name",
  }
  assert "《精成》" not in kongjie.limits and "星侨" not in kongjie.limits
  assert "天空" not in stars.Star.__members__
  palace = citations["citation.quanshu.twelve-palaces"]
  assert palace.quote == (
    "一 命宫、二兄弟、三妻妾、四子女、五财帛、六疾厄、七迁移、八奴仆、九官禄、十田宅、十一福德、十二父母"
  )
  assert all(text in palace.limits for text in ("节选", "男女俱从逆转", "切忌莫顺去"))
  assert sources["source.quanshu-wikisource"].status is SourceStatus.已核
  assert sources["source.lifedna-flying"].status is SourceStatus.已核
  assert sources["source.yuanhai-changxian"].status is SourceStatus.待核


def test_lifedna_lists_three_leap_methods_without_endorsing_project_options() -> None:
  catalog = load_catalog()
  entries = {item.id: item for item in catalog.entries}
  for method, citation in (("current", "current"), ("next", "next"), ("split", "split")):
    assert "citation.lifedna.leap-" + citation in entries["entry.leap-month." + method].citation_ids
  assert "LifeDNA" in entries["entry.leap-month.next"].statement
  assert "列举" in entries["entry.leap-month.next"].premises[0]
  for suffix, target in (("lichun", "year-boundary.lichun"), ("late-zi", "day-rollover.late-zi")):
    opinion = entries["entry.lifedna.opposes-" + suffix]
    identifier = "citation.lifedna.opposes-" + suffix
    assert opinion.variant_ids == () and opinion.citation_ids == (identifier,)
    assert opinion.premise_status is PremiseStatus.已明确
    assert opinion.display is DisplayEligibility.暂不默认展示
    for prefix in ("entry.", "variant."):
      assert identifier not in {item.id for item in catalog.references(prefix + target)}
  assert catalog.filter_entries(default_only=True) == ()


def test_project_reference_text_consumes_domain_values_in_an_isolated_process(
  tmp_path: Path,
) -> None:
  script = r"""
import importlib
import sys
from enum import StrEnum
sys.path.insert(0, sys.argv[1])
from ziwei import bureau, ganzhi, palaces
from ziwei.knowledge import data
quotes = {item.id: item.quote for item in data.CITATIONS}
palaces.PalaceName = StrEnum('PalaceName', {
    item.name: item.value for item in reversed(tuple(palaces.PalaceName))})
bureau.WuxingJu = StrEnum('WuxingJu', {'EXAMPLE': '测试水局'})
ganzhi.WUHU_YIN = ((ganzhi.WUHU_YIN[0][0], ganzhi.Tiangan.戊), *ganzhi.WUHU_YIN[1:])
importlib.reload(data)
variants = {item.id: item.definition for item in data.VARIANTS}
entries = {item.id: item.statement for item in data.ENTRIES}
expected = '自命宫起逆排：' + '、'.join(item.value for item in palaces.PalaceName) + '。'
if variants['variant.palace.twelve'] != expected:
  raise RuntimeError('palace reference did not consume domain order')
if not variants['variant.palace.wuhu-dun'].startswith('甲己起戊寅'):
  raise RuntimeError('wuhu reference did not consume pair values')
if not variants['variant.wuxingju.mapping'].startswith('测试水局；'):
  raise RuntimeError('bureau variant did not consume domain names')
if '定：测试水局；' not in entries['entry.wuxingju.mapping']:
  raise RuntimeError('bureau entry did not consume domain names')
if quotes != {item.id: item.quote for item in data.CITATIONS}:
  raise RuntimeError('project value changes rewrote source quotes')
print('domain references consumed; source quotes unchanged')
"""
  root = Path(__file__).resolve().parents[1]
  result = subprocess.run(
    (sys.executable, "-I", "-B", "-c", script, str(root / "src")),
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stdout + result.stderr
  assert "source quotes unchanged" in result.stdout
  assert [nayin(Ganzhi.from_str(text)) for text in ("甲子", "乙丑", "丙寅", "丁卯")] == [
    Wuxing.金,
    Wuxing.金,
    Wuxing.火,
    Wuxing.火,
  ]


def test_changing_configuration_default_does_not_redefine_tianma(tmp_path: Path) -> None:
  source = tmp_path / "src"
  shutil.copytree(
    Path(__file__).resolve().parents[1] / "src/ziwei",
    source / "ziwei",
    ignore=shutil.ignore_patterns("__pycache__"),
  )
  config = source / "ziwei/config.py"
  text = config.read_text(encoding="utf-8")
  marker = "tianma_rule: TianmaRule = TianmaRule.YEAR_BRANCH"
  assert text.count(marker) == 1
  config.write_text(
    text.replace(marker, marker.replace("YEAR_BRANCH", "MONTH_BRANCH")), encoding="utf-8"
  )
  expected = {rule.id: rule.definition for rule in stars.STAR_RULES if rule.tianma_rule is not None}
  script = r"""
import json
import sys
sys.path.insert(0, sys.argv[1])
from ziwei import config, stars
from ziwei.birth import Gender, LunarBirthRecord
from ziwei.ganzhi import Dizhi
from ziwei.resolver import resolve
if not config.__file__.startswith(sys.argv[1]):
  raise RuntimeError('wrong source origin')
choices = config.ChartConfig(leap_month_policy=config.LeapMonthPolicy.全月归本月,
    day_rollover=config.DayRollover.早晚子时同日, year_boundary=config.YearBoundary.农历正月初一)
if choices.tianma_rule is not config.TianmaRule.月支天马:
  raise RuntimeError('changed default not selected')
record = LunarBirthRecord(year=2024, month=1, day=7, is_leap_month=False,
    shichen=Dizhi.子, gender=Gender.未知)
position = next(p for p in stars.place_stars(resolve(record, choices)) if p.star is stars.Star.天马)
if position.rule_id != 'variant.tianma.month-branch' or position.dizhi is not Dizhi.申:
  raise RuntimeError('default choice not consumed by placement')
actual = {rule.id: rule.definition for rule in stars.STAR_RULES if rule.tianma_rule is not None}
if actual != json.loads(sys.argv[2]):
  raise RuntimeError('configuration default changed rule identity or meaning')
print('default changed; rule identities and meanings retained')
"""
  result = subprocess.run(
    (sys.executable, "-I", "-B", "-c", script, str(source), json.dumps(expected)),
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stdout + result.stderr
  assert "rule identities and meanings retained" in result.stdout
