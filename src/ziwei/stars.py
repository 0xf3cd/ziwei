"""十四主星、六吉六煞、禄存与天马的纯函数安星。

《紫微斗數全書》卷二固定修订1963110（Q）给出五局逐日紫微宫格、天府对应与各系规则。
王亭之《中州派紫微斗数初级讲义》转录（W，第6至13、18条）及《紫微斗數精成》网页
（J，第7至12项）提供对照。W与星侨安星诀多处同文，不按网址数计独立来源。
来源定位、谱系和限度由知识目录关联；本模块的定义同时用于计算与参考页，不复制数值表。

魁钺只执行现代表；Q的异文留在知识目录。火铃起点据Q/W/J，两星顺行的方向据W例与J明文，
不归给Q。地空是时系星，Q的旧称天空不作为全局别名。月马按J单源变体执行；月系星与
三个归月口径的组合是项目规则，不宣称复刻某一著作的整套历法口径。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from ziwei.bureau import WuxingJu, bureau_of
from ziwei.config import TianmaRule
from ziwei.ganzhi import Dizhi, Tiangan
from ziwei.palaces import effective_month, minggong_dizhi, month_palace_index, palace_ganzhi

if TYPE_CHECKING:
  from ziwei.birth import CalculationInput


class Star(StrEnum):
  """28星身份；拼音成员及中文别名不随规则选择改变。"""

  ZIWEI = "紫微"
  TIANJI = "天机"
  TAIYANG = "太阳"
  WUQU = "武曲"
  TIANTONG = "天同"
  LIANZHEN = "廉贞"
  TIANFU = "天府"
  TAIYIN = "太阴"
  TANLANG = "贪狼"
  JUMEN = "巨门"
  TIANXIANG = "天相"
  TIANLIANG = "天梁"
  QISHA = "七杀"
  POJUN = "破军"
  ZUOFU = "左辅"
  YOUBI = "右弼"
  WENCHANG = "文昌"
  WENQU = "文曲"
  TIANKUI = "天魁"
  TIANYUE = "天钺"
  QINGYANG = "擎羊"
  TUOLUO = "陀罗"
  HUOXING = "火星"
  LINGXING = "铃星"
  DIKONG = "地空"
  DIJIE = "地劫"
  LUCUN = "禄存"
  TIANMA = "天马"
  紫微 = ZIWEI
  天机 = TIANJI
  太阳 = TAIYANG
  武曲 = WUQU
  天同 = TIANTONG
  廉贞 = LIANZHEN
  天府 = TIANFU
  太阴 = TAIYIN
  贪狼 = TANLANG
  巨门 = JUMEN
  天相 = TIANXIANG
  天梁 = TIANLIANG
  七杀 = QISHA
  破军 = POJUN
  左辅 = ZUOFU
  右弼 = YOUBI
  文昌 = WENCHANG
  文曲 = WENQU
  天魁 = TIANKUI
  天钺 = TIANYUE
  擎羊 = QINGYANG
  陀罗 = TUOLUO
  火星 = HUOXING
  铃星 = LINGXING
  地空 = DIKONG
  地劫 = DIJIE
  禄存 = LUCUN
  天马 = TIANMA

  @property
  def concept_id(self) -> str:
    """稳定知识标识；拼音规范名是身份键，不从中文显示名推导。"""
    return "concept.star." + self.name.lower()


@dataclass(frozen=True, slots=True)
class _Rule:
  id: str
  name: str
  stars: tuple[Star, ...]
  definition: str
  implementation: str
  scope: str = "本命安星；只定位置，不解释吉凶"
  conditions: tuple[str, ...] = ()
  tianma_rule: TianmaRule | None = None


# 顺逆均按地支子丑寅……亥；偏移为宫数，不含起点。
ZIWEI_OFFSETS: Final[tuple[tuple[Star, int], ...]] = (
  (Star.紫微, 0),
  (Star.天机, -1),
  (Star.太阳, -3),
  (Star.武曲, -4),
  (Star.天同, -5),
  (Star.廉贞, -8),
)
TIANFU_OFFSETS: Final[tuple[tuple[Star, int], ...]] = (
  (Star.天府, 0),
  (Star.太阴, 1),
  (Star.贪狼, 2),
  (Star.巨门, 3),
  (Star.天相, 4),
  (Star.天梁, 5),
  (Star.七杀, 6),
  (Star.破军, 10),
)
MONTH_STARS: Final[tuple[tuple[Star, Dizhi, int], ...]] = (
  (Star.左辅, Dizhi.辰, 1),
  (Star.右弼, Dizhi.戌, -1),
)
HOUR_STARS: Final[tuple[tuple[Star, Dizhi, int], ...]] = (
  (Star.文昌, Dizhi.戌, -1),
  (Star.文曲, Dizhi.辰, 1),
  (Star.地空, Dizhi.亥, -1),
  (Star.地劫, Dizhi.亥, 1),
)
# 十干按甲至癸；前魁后钺。Q的丙丁亥戌、辛寅午异文不混入本表。
KUIYUE_BY_STEM: Final[tuple[tuple[Dizhi, Dizhi], ...]] = tuple(
  (Dizhi(pair[0]), Dizhi(pair[1]))
  for pair in ("丑未", "子申", "亥酉", "亥酉", "丑未", "子申", "丑未", "午寅", "卯巳", "卯巳")
)
LUCUN_BY_STEM: Final[tuple[Dizhi, ...]] = tuple(Dizhi(value) for value in "寅卯巳午巳午申酉亥子")
SANHE_GROUPS: Final[tuple[tuple[Dizhi, ...], ...]] = tuple(
  tuple(Dizhi(value) for value in group) for group in ("寅午戌", "申子辰", "巳酉丑", "亥卯未")
)
FIRE_BELL_STARTS: Final[tuple[tuple[Dizhi, Dizhi], ...]] = (
  (Dizhi.丑, Dizhi.卯),
  (Dizhi.寅, Dizhi.戌),
  (Dizhi.卯, Dizhi.戌),
  (Dizhi.酉, Dizhi.戌),
)
TIANMA_BY_GROUP: Final[tuple[Dizhi, ...]] = (Dizhi.申, Dizhi.寅, Dizhi.亥, Dizhi.巳)

_ZIWEI = _Rule(
  "variant.star.ziwei-bureau-day",
  "五局逐日紫微",
  (Star.紫微,),
  "生日补至局数整倍；自寅含起点顺数至商数，再按补数奇逆偶顺移动。",
  "ziwei.stars.ziwei_dizhi",
  conditions=("五行局已定；农历日1至30，闰月不累加日数",),
)
_ZIWEI_SERIES = _Rule(
  "variant.star.ziwei-series",
  "紫微系固定关系",
  tuple(star for star, _ in ZIWEI_OFFSETS[1:]),
  "自紫微按紫微系固定宫数偏移安入其余五星。",
  "ziwei.stars.place_major_stars",
)
_TIANFU = _Rule(
  "variant.star.tianfu-reflection",
  "天府与紫微对应",
  (Star.天府,),
  "紫微与天府关于寅申轴对称，寅申同宫。",
  "ziwei.stars.tianfu_dizhi",
)
_TIANFU_SERIES = _Rule(
  "variant.star.tianfu-series",
  "天府系固定关系",
  tuple(star for star, _ in TIANFU_OFFSETS[1:]),
  "自天府按天府系固定宫数偏移安入其余七星。",
  "ziwei.stars.place_major_stars",
)
_FUBI = _Rule(
  "variant.star.fubi-effective-month",
  "辅弼按有效生月",
  (Star.左辅, Star.右弼),
  "辰起正月顺安辅、戌起正月逆安弼；本项目统一消费所选归月口径。",
  "ziwei.stars.place_month_stars",
  conditions=("月参数为已按所选口径解析的有效生月",),
)
_WEN = _Rule(
  "variant.star.wenchang-wenqu-hour",
  "昌曲按生时",
  (Star.文昌, Star.文曲),
  "戌起子时逆安昌、辰起子时顺安曲。",
  "ziwei.stars.place_hour_stars",
)
_KUIYUE = _Rule(
  "variant.star.kuiyue-modern",
  "魁钺现代表",
  (Star.天魁, Star.天钺),
  "依年干查现代表，前魁后钺；不执行电子全书异文。",
  "ziwei.stars.place_stem_stars",
)
_LUCUN = _Rule(
  "variant.star.lucun-stem",
  "禄存按年干",
  (Star.禄存,),
  "依已经确定的年干查禄存。",
  "ziwei.stars.place_stem_stars",
)
_YANGTUO = _Rule(
  "variant.star.yangtuo-lucun",
  "羊陀随禄存",
  (Star.擎羊, Star.陀罗),
  "禄存顺一宫为擎羊、逆一宫为陀罗。",
  "ziwei.stars.place_stem_stars",
)
_HUOLING = _Rule(
  "variant.star.huoling-forward",
  "火铃年支起点顺生时",
  (Star.火星, Star.铃星),
  "年支三合组定子时起点，两星均顺行至生时；方向据现代说明。",
  "ziwei.stars.place_fire_bell",
  conditions=("年支已由换年口径确定；时辰已知",),
)
_KONGJIE = _Rule(
  "variant.star.kongjie-hour",
  "时系地空地劫",
  (Star.地空, Star.地劫),
  "亥起子时逆安地空、顺安地劫；古籍时系旧称天空不作全局别名。",
  "ziwei.stars.place_hour_stars",
)
_YEAR_MA = _Rule(
  "variant.tianma.year-branch",
  "年支天马",
  (Star.天马,),
  "按年支三合组查马；是本项目具名默认，不替代三个必填历法口径。",
  "ziwei.stars.tianma_dizhi",
  conditions=("锚为已经确定的年支",),
  tianma_rule=TianmaRule.YEAR_BRANCH,
)
_MONTH_MA = _Rule(
  "variant.tianma.month-branch",
  "月支天马",
  (Star.天马,),
  "按有效农历生月所对应地支的三合组查马，不看节气；月马为具名单源执行例外。",
  "ziwei.stars.tianma_dizhi",
  conditions=("有效生月按本项目三个归月口径组合，非整套原书口径",),
  tianma_rule=TianmaRule.MONTH_BRANCH,
)
STAR_RULES: Final[tuple[_Rule, ...]] = (
  _ZIWEI,
  _ZIWEI_SERIES,
  _TIANFU,
  _TIANFU_SERIES,
  _FUBI,
  _WEN,
  _KUIYUE,
  _LUCUN,
  _YANGTUO,
  _HUOLING,
  _KONGJIE,
  _YEAR_MA,
  _MONTH_MA,
)
"""计算、知识关联与参考页共用的规则身份和公开实现路径，不动态导入或执行路径。"""


@dataclass(frozen=True, slots=True)
class StarPlacement:
  """一颗星的位置与实际规则标识；多星同宫合法。"""

  star: Star
  dizhi: Dizhi
  rule_id: str

  def __post_init__(self) -> None:
    if not isinstance(self.star, Star) or not isinstance(self.dizhi, Dizhi):
      raise TypeError("星位须使用 Star 与 Dizhi 成员")
    if not isinstance(self.rule_id, str):
      raise TypeError("安星规则标识须为字符串")
    if not any(rule.id == self.rule_id and self.star in rule.stars for rule in STAR_RULES):
      raise ValueError("安星规则标识须属于该星的已实现规则")


def _move(start: Dizhi, offset: int) -> Dizhi:
  return tuple(Dizhi)[(tuple(Dizhi).index(start) + offset) % 12]


def ziwei_dizhi(ju: WuxingJu, day: int) -> Dizhi:
  """由五行局与农历日安紫微；日限1至30，拒绝bool。"""
  if not isinstance(ju, WuxingJu):
    raise TypeError("五行局须为 WuxingJu 成员")
  if type(day) is not int:
    raise TypeError("农历日须为整数，不接受 bool")
  if not 1 <= day <= 30:
    raise ValueError("农历日须在1至30之间")
  quotient = (day + ju.number - 1) // ju.number
  padding = quotient * ju.number - day
  correction = -padding if padding % 2 else padding
  return _move(Dizhi.寅, quotient - 1 + correction)


def tianfu_dizhi(ziwei: Dizhi) -> Dizhi:
  """由紫微位置安天府：寅申同宫，其他宫关于寅申轴对称。"""
  if not isinstance(ziwei, Dizhi):
    raise TypeError("紫微位置须为 Dizhi 成员")
  return _move(Dizhi.辰, -tuple(Dizhi).index(ziwei))


def place_major_stars(ju: WuxingJu, day: int) -> tuple[StarPlacement, ...]:
  """独立安十四主星；只需局与日，不读取出生资料或历法。"""
  ziwei = ziwei_dizhi(ju, day)
  tianfu = tianfu_dizhi(ziwei)
  return (
    *(
      StarPlacement(star, _move(ziwei, offset), (_ZIWEI if star is Star.紫微 else _ZIWEI_SERIES).id)
      for star, offset in ZIWEI_OFFSETS
    ),
    *(
      StarPlacement(
        star, _move(tianfu, offset), (_TIANFU if star is Star.天府 else _TIANFU_SERIES).id
      )
      for star, offset in TIANFU_OFFSETS
    ),
  )


def place_month_stars(month: int) -> tuple[StarPlacement, ...]:
  """安左辅右弼；month为有效生月1至12，闰月须先调用effective_month。"""
  month_palace_index(month)
  return tuple(
    StarPlacement(star, _move(start, direction * (month - 1)), _FUBI.id)
    for star, start, direction in MONTH_STARS
  )


def place_hour_stars(shichen: Dizhi) -> tuple[StarPlacement, ...]:
  """依已知时辰安昌曲与时系空劫，不含年系天空。"""
  if not isinstance(shichen, Dizhi):
    raise TypeError("时辰须为 Dizhi 成员")
  offset = tuple(Dizhi).index(shichen)
  return tuple(
    StarPlacement(star, _move(start, direction * offset), (_WEN if index < 2 else _KONGJIE).id)
    for index, (star, start, direction) in enumerate(HOUR_STARS)
  )


def place_stem_stars(year_tiangan: Tiangan) -> tuple[StarPlacement, ...]:
  """依已确定年干安现代表魁钺、禄存与羊陀。"""
  if not isinstance(year_tiangan, Tiangan):
    raise TypeError("年干须为 Tiangan 成员")
  index = tuple(Tiangan).index(year_tiangan)
  kui, yue = KUIYUE_BY_STEM[index]
  lucun = LUCUN_BY_STEM[index]
  return (
    StarPlacement(Star.天魁, kui, _KUIYUE.id),
    StarPlacement(Star.天钺, yue, _KUIYUE.id),
    StarPlacement(Star.禄存, lucun, _LUCUN.id),
    StarPlacement(Star.擎羊, _move(lucun, 1), _YANGTUO.id),
    StarPlacement(Star.陀罗, _move(lucun, -1), _YANGTUO.id),
  )


def _group_index(branch: Dizhi) -> int:
  if not isinstance(branch, Dizhi):
    raise TypeError("三合组查法锚须为 Dizhi 成员")
  return next(index for index, group in enumerate(SANHE_GROUPS) if branch in group)


def place_fire_bell(year_dizhi: Dizhi, shichen: Dizhi) -> tuple[StarPlacement, ...]:
  """依年支组定火铃子时起点，两星均顺行至生时。"""
  group = _group_index(year_dizhi)
  if not isinstance(shichen, Dizhi):
    raise TypeError("时辰须为 Dizhi 成员")
  offset = tuple(Dizhi).index(shichen)
  fire, bell = FIRE_BELL_STARTS[group]
  return (
    StarPlacement(Star.火星, _move(fire, offset), _HUOLING.id),
    StarPlacement(Star.铃星, _move(bell, offset), _HUOLING.id),
  )


def tianma_dizhi(branch: Dizhi) -> Dizhi:
  """以选定的年支或有效月支查天马；调用方负责选择查法锚。"""
  return TIANMA_BY_GROUP[_group_index(branch)]


def place_stars(value: CalculationInput) -> tuple[StarPlacement, ...]:
  """从解析结果安28星，按Star枚举顺序返回；要求时辰已知，允许性别未知。

  本入口不重做历法，也不调用完整命盘校验。辅弼、月马与命宫共享有效生月，半月分界按解析后
  农历日day>=16；不累加上月天数。闰十二归下月等不可用组合显式失败，不返回部分结果。
  每颗星恰一位置，天马的rule_id记录实际选择，不依赖以后配置的默认值。
  """
  from ziwei.birth import CalculationInput

  if not isinstance(value, CalculationInput):
    raise TypeError("安星需要解析后的 CalculationInput")
  if value.shichen is None:
    raise ValueError("安星需要已知时辰")
  month = effective_month(
    value.month, value.day, value.is_leap_month, value.config.leap_month_policy
  )
  minggong = minggong_dizhi(month, value.shichen)
  ju = bureau_of(palace_ganzhi(minggong, value.ganzhi_year))
  year = value.year_ganzhi
  if value.config.tianma_rule is TianmaRule.YEAR_BRANCH:
    ma_branch, ma_rule = year.dizhi, _YEAR_MA
  else:
    ma_branch, ma_rule = tuple(Dizhi)[month_palace_index(month)], _MONTH_MA
  positions = (
    *place_major_stars(ju, value.day),
    *place_month_stars(month),
    *place_hour_stars(value.shichen),
    *place_stem_stars(year.tiangan),
    *place_fire_bell(year.dizhi, value.shichen),
    StarPlacement(Star.天马, tianma_dizhi(ma_branch), ma_rule.id),
  )
  if len(positions) != len(Star) or {item.star for item in positions} != set(Star):
    raise ValueError("安星结果须恰有28颗不同星曜")
  return tuple(sorted(positions, key=lambda item: tuple(Star).index(item.star)))
