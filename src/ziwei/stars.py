"""十四主星、六吉六煞、禄存与天马的纯函数安星。

《紫微斗數全書》卷二固定修订1963110给出五局逐日紫微宫格、天府对应及各系安星规则。
另以王亭之《中州派紫微斗数初级讲义》网页转录的第6至13、18条，以及《紫微斗數精成》
网页第7至12项作对照。讲义与星侨网站的安星诀多处同文，不因网址不同就算作独立来源。
具体出处、转录关系和未核事项见知识目录；计算与参考页共用本模块的规则和数值表。

天魁、天钺采用现代资料所列的表，《全书》中不同的口诀只存入知识目录，待核后再决定是否执行。
火星、铃星在子时的起始宫位按出生年支分组，四组宫位参照上述三份资料；两星顺数到出生时辰的
方向，由讲义例解和《精成》明文支持，《全书》该段未说明顺逆。
本模块的地空按出生时辰安星；《全书》虽称它为天空，本项目不设这个全局别名，以免与另一颗
按年支安置的天空混淆。月马见《精成》与论坛两页同文口诀，按一路文本计，传承与原书未核。
辅弼、月马采用所选闰月归属规则，是本项目的组合方式，不代表完整采用某部著作的历法规则。
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
  """28颗星的名称与中文别名；选择不同的安星规则，不会把同一颗星变成另一颗星。"""

  _concept_id: str

  def __new__(cls, value: str, concept_id: str | None = None) -> Star:
    if concept_id is None:
      raise ValueError("新增星曜须显式指定知识标识")
    member = str.__new__(cls, value)
    member._value_ = value
    member._concept_id = concept_id
    return member

  ZIWEI = "紫微", "concept.star.ziwei"
  TIANJI = "天机", "concept.star.tianji"
  TAIYANG = "太阳", "concept.star.taiyang"
  WUQU = "武曲", "concept.star.wuqu"
  TIANTONG = "天同", "concept.star.tiantong"
  LIANZHEN = "廉贞", "concept.star.lianzhen"
  TIANFU = "天府", "concept.star.tianfu"
  TAIYIN = "太阴", "concept.star.taiyin"
  TANLANG = "贪狼", "concept.star.tanlang"
  JUMEN = "巨门", "concept.star.jumen"
  TIANXIANG = "天相", "concept.star.tianxiang"
  TIANLIANG = "天梁", "concept.star.tianliang"
  QISHA = "七杀", "concept.star.qisha"
  POJUN = "破军", "concept.star.pojun"
  ZUOFU = "左辅", "concept.star.zuofu"
  YOUBI = "右弼", "concept.star.youbi"
  WENCHANG = "文昌", "concept.star.wenchang"
  WENQU = "文曲", "concept.star.wenqu"
  TIANKUI = "天魁", "concept.star.tiankui"
  TIANYUE = "天钺", "concept.star.tianyue"
  QINGYANG = "擎羊", "concept.star.qingyang"
  TUOLUO = "陀罗", "concept.star.tuoluo"
  HUOXING = "火星", "concept.star.huoxing"
  LINGXING = "铃星", "concept.star.lingxing"
  DIKONG = "地空", "concept.star.dikong"
  DIJIE = "地劫", "concept.star.dijie"
  LUCUN = "禄存", "concept.star.lucun"
  TIANMA = "天马", "concept.star.tianma"
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
    """知识目录中的固定标识，不随 Python 成员名或显示名称改变。"""
    return self._concept_id


_NATAL_STARS_V1: Final = (
  Star.紫微,
  Star.天机,
  Star.太阳,
  Star.武曲,
  Star.天同,
  Star.廉贞,
  Star.天府,
  Star.太阴,
  Star.贪狼,
  Star.巨门,
  Star.天相,
  Star.天梁,
  Star.七杀,
  Star.破军,
  Star.左辅,
  Star.右弼,
  Star.文昌,
  Star.文曲,
  Star.天魁,
  Star.天钺,
  Star.擎羊,
  Star.陀罗,
  Star.火星,
  Star.铃星,
  Star.地空,
  Star.地劫,
  Star.禄存,
  Star.天马,
)


@dataclass(frozen=True, slots=True)
class StarRule:
  """一条安星规则的标识、说明及所用星曜。

  星曜与条件序列会复制为元组，调用者之后修改原来的列表不会改变这条规则。
  """

  id: str
  name: str
  stars: tuple[Star, ...]
  definition: str
  implementation: str
  scope: str = "本命安星；只定位置，不解释吉凶"
  conditions: tuple[str, ...] = ()
  tianma_rule: TianmaRule | None = None

  def __post_init__(self) -> None:
    for field in ("id", "name", "definition", "implementation", "scope"):
      value = getattr(self, field)
      if not isinstance(value, str):
        raise TypeError("规则文本须为字符串")
      if not value.strip():
        raise ValueError("规则文本不得为空")
    if isinstance(self.stars, str) or isinstance(self.conditions, str):
      raise TypeError("星曜与条件须为序列，不接受字符串")
    stars = tuple(self.stars)
    conditions = tuple(self.conditions)
    if any(not isinstance(star, Star) for star in stars):
      raise TypeError("规则星曜须为 Star 成员")
    if not stars or len(set(stars)) != len(stars):
      raise ValueError("规则星曜须非空且不重复")
    if any(not isinstance(condition, str) for condition in conditions):
      raise TypeError("规则条件须为字符串")
    if any(not condition.strip() for condition in conditions):
      raise ValueError("规则条件不得为空")
    if self.tianma_rule is not None:
      if not isinstance(self.tianma_rule, TianmaRule):
        raise TypeError("天马选择须为 TianmaRule 成员")
      if stars != (Star.天马,):
        raise ValueError("天马选择只适用于天马规则")
    elif Star.天马 in stars:
      raise ValueError("天马规则须声明查法选择")
    object.__setattr__(self, "stars", stars)
    object.__setattr__(self, "conditions", conditions)


# 顺行按子、丑、寅……亥排列，逆行相反；偏移0表示原宫，1表示顺移一宫。
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
_MONTH_STARS: Final[tuple[tuple[Star, Dizhi, int], ...]] = (
  (Star.左辅, Dizhi.辰, 1),
  (Star.右弼, Dizhi.戌, -1),
)
_HOUR_STARS: Final[tuple[tuple[Star, Dizhi, int], ...]] = (
  (Star.文昌, Dizhi.戌, -1),
  (Star.文曲, Dizhi.辰, 1),
  (Star.地空, Dizhi.亥, -1),
  (Star.地劫, Dizhi.亥, 1),
)
# 按甲至癸排列，每行依次为天魁、天钺。《全书》的丙丁亥戌、辛寅午异文不混入本表。
_KUIYUE_BY_STEM: Final[tuple[tuple[Dizhi, Dizhi], ...]] = tuple(
  (Dizhi(pair[0]), Dizhi(pair[1]))
  for pair in ("丑未", "子申", "亥酉", "亥酉", "丑未", "子申", "丑未", "午寅", "卯巳", "卯巳")
)
_LUCUN_BY_STEM: Final[tuple[Dizhi, ...]] = tuple(Dizhi(value) for value in "寅卯巳午巳午申酉亥子")
SANHE_GROUPS: Final[tuple[tuple[Dizhi, ...], ...]] = tuple(
  tuple(Dizhi(value) for value in group) for group in ("寅午戌", "申子辰", "巳酉丑", "亥卯未")
)
_FIRE_BELL_STARTS: Final[tuple[tuple[Dizhi, Dizhi], ...]] = (
  (Dizhi.丑, Dizhi.卯),
  (Dizhi.寅, Dizhi.戌),
  (Dizhi.卯, Dizhi.戌),
  (Dizhi.酉, Dizhi.戌),
)
_TIANMA_BY_GROUP: Final[tuple[Dizhi, ...]] = (Dizhi.申, Dizhi.寅, Dizhi.亥, Dizhi.巳)

_ZIWEI = StarRule(
  "variant.star.ziwei-bureau-day",
  "五局逐日紫微",
  (Star.紫微,),
  "把农历日向上补到局数的整数倍，所加的最小非负整数称为补数，补后的日数除以局数得到商。"
  "从寅宫起顺数到商数，寅宫算第一宫；再移动补数那么多宫，补数为奇数时逆行，为偶数时顺行。",
  "ziwei.stars.ziwei_dizhi",
  conditions=("五行局已定，农历日为1至30；闰月也使用当月的日数，不加上前一个月的天数",),
)
_ZIWEI_SERIES = StarRule(
  "variant.star.ziwei-series",
  "紫微系固定关系",
  tuple(star for star, _ in ZIWEI_OFFSETS if star is not Star.紫微),
  "以紫微所在宫位为起点，按固定的宫数和方向安置紫微系其余五星。",
  "ziwei.stars.place_major_stars",
)
_TIANFU = StarRule(
  "variant.star.tianfu-reflection",
  "天府与紫微对应",
  (Star.天府,),
  "紫微与天府关于寅申轴对称，寅申同宫。",
  "ziwei.stars.tianfu_dizhi",
)
_TIANFU_SERIES = StarRule(
  "variant.star.tianfu-series",
  "天府系固定关系",
  tuple(star for star, _ in TIANFU_OFFSETS if star is not Star.天府),
  "以天府所在宫位为起点，按固定的宫数和方向安置天府系其余七星。",
  "ziwei.stars.place_major_stars",
)
_FUBI = StarRule(
  "variant.star.fubi-effective-month",
  "辅弼按有效生月",
  tuple(star for star, _, _ in _MONTH_STARS),
  "左辅从辰宫起正月，顺数到生月；右弼从戌宫起正月，逆数到生月。"
  "闰月按所选的闰月归属规则确定安星用的月份。",
  "ziwei.stars.place_month_stars",
  conditions=("月参数须已按所选闰月归属规则确定，不能直接传入尚未处理的闰月月份",),
)
_WEN = StarRule(
  "variant.star.wenchang-wenqu-hour",
  "昌曲按生时",
  (Star.文昌, Star.文曲),
  "文昌从戌宫起子时，逆数到出生时辰；文曲从辰宫起子时，顺数到出生时辰。",
  "ziwei.stars.place_hour_stars",
)
_KUIYUE = StarRule(
  "variant.star.kuiyue-modern",
  "魁钺现代表",
  (Star.天魁, Star.天钺),
  "按年干查现代资料的天魁、天钺表，每行先列天魁、后列天钺；不执行电子《全书》中不同的口诀。",
  "ziwei.stars.place_stem_stars",
)
_LUCUN = StarRule(
  "variant.star.lucun-stem",
  "禄存按年干",
  (Star.禄存,),
  "依已经确定的年干查禄存。",
  "ziwei.stars.place_stem_stars",
)
_YANGTUO = StarRule(
  "variant.star.yangtuo-lucun",
  "羊陀随禄存",
  (Star.擎羊, Star.陀罗),
  "禄存顺一宫为擎羊、逆一宫为陀罗。",
  "ziwei.stars.place_stem_stars",
)
_HUOLING = StarRule(
  "variant.star.huoling-forward",
  "火铃按年支与生时",
  (Star.火星, Star.铃星),
  "按出生年支所属的三合组，确定火星、铃星在子时的起始宫位，再分别顺数到出生时辰。"
  "两星均顺行的依据是现代资料中的说明。",
  "ziwei.stars.place_fire_bell",
  conditions=("年支已由换年口径确定；时辰已知",),
)
_KONGJIE = StarRule(
  "variant.star.kongjie-hour",
  "时系地空地劫",
  (Star.地空, Star.地劫),
  "地空、地劫都从亥宫起子时，分别逆数、顺数到出生时辰。"
  "《全书》把这里的地空称为天空，但本项目不设Star.天空别名，以免与按年支安的另一颗天空混淆。",
  "ziwei.stars.place_hour_stars",
)
_YEAR_MA = StarRule(
  "variant.tianma.year-branch",
  "年支天马",
  (Star.天马,),
  "按出生年支所属的三合组查天马，是本项目默认的天马查法。"
  "闰月归属、子时换日和换年界线仍须另外指定。",
  "ziwei.stars.tianma_dizhi",
  conditions=("查表使用已经按所选换年规则确定的年支",),
  tianma_rule=TianmaRule.YEAR_BRANCH,
)
_MONTH_MA = StarRule(
  "variant.tianma.month-branch",
  "月支天马",
  (Star.天马,),
  "把农历生月对应到地支，再按所属三合组查天马，不按节气划分月份。"
  "作为可选的月支天马规则执行，来源与同文限度见知识目录。",
  "ziwei.stars.tianma_dizhi",
  conditions=("安星用的月份按所选闰月归属规则确定；这是项目组合，不代表采用原书的整套历法规则",),
  tianma_rule=TianmaRule.MONTH_BRANCH,
)
STAR_RULES: Final[tuple[StarRule, ...]] = (
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
"""计算、知识目录与参考页共用的规则记录；实现路径只存为字符串，不据此导入或调用函数。"""


@dataclass(frozen=True, slots=True)
class StarPlacement:
  """保存一颗星所在的地支宫位及实际使用的规则标识；不同星可以落在同一宫。"""

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


def _placement(star: Star, dizhi: Dizhi, tianma_rule: TianmaRule | None = None) -> StarPlacement:
  rules = tuple(
    rule for rule in STAR_RULES if star in rule.stars and rule.tianma_rule is tianma_rule
  )
  if len(rules) != 1:
    raise ValueError(f"星曜与查法须恰有一条规则：{star} / {tianma_rule}")
  return StarPlacement(star, dizhi, rules[0].id)


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
  """按五行局与农历日安十四主星，不读取出生记录，也不调用历法换算。"""
  ziwei = ziwei_dizhi(ju, day)
  tianfu = tianfu_dizhi(ziwei)
  return (
    *(_placement(star, _move(ziwei, offset)) for star, offset in ZIWEI_OFFSETS),
    *(_placement(star, _move(tianfu, offset)) for star, offset in TIANFU_OFFSETS),
  )


def place_month_stars(month: int) -> tuple[StarPlacement, ...]:
  """按安星用的月份安左辅、右弼，month须在1至12之间。

  闰月须先用effective_month按所选规则确定月份，不能直接把原始闰月月份传入。
  """
  month_palace_index(month)
  return tuple(
    _placement(star, _move(start, direction * (month - 1)))
    for star, start, direction in _MONTH_STARS
  )


def place_hour_stars(shichen: Dizhi) -> tuple[StarPlacement, ...]:
  """按出生时辰安文昌、文曲、地空与地劫，不包含那颗按年支安置的天空。"""
  if not isinstance(shichen, Dizhi):
    raise TypeError("时辰须为 Dizhi 成员")
  offset = tuple(Dizhi).index(shichen)
  return tuple(
    _placement(star, _move(start, direction * offset)) for star, start, direction in _HOUR_STARS
  )


def place_stem_stars(year_tiangan: Tiangan) -> tuple[StarPlacement, ...]:
  """按已确定的年干安天魁、天钺、禄存、擎羊与陀罗；天魁、天钺使用现代表。"""
  if not isinstance(year_tiangan, Tiangan):
    raise TypeError("年干须为 Tiangan 成员")
  index = tuple(Tiangan).index(year_tiangan)
  kui, yue = _KUIYUE_BY_STEM[index]
  lucun = _LUCUN_BY_STEM[index]
  return (
    _placement(Star.天魁, kui),
    _placement(Star.天钺, yue),
    _placement(Star.禄存, lucun),
    _placement(Star.擎羊, _move(lucun, 1)),
    _placement(Star.陀罗, _move(lucun, -1)),
  )


def _group_index(branch: Dizhi) -> int:
  if not isinstance(branch, Dizhi):
    raise TypeError("三合组查法锚须为 Dizhi 成员")
  return next(index for index, group in enumerate(SANHE_GROUPS) if branch in group)


def place_fire_bell(year_dizhi: Dizhi, shichen: Dizhi) -> tuple[StarPlacement, ...]:
  """按出生年支所属的三合组，确定火星、铃星在子时的起始宫位，再分别顺数到出生时辰。"""
  group = _group_index(year_dizhi)
  if not isinstance(shichen, Dizhi):
    raise TypeError("时辰须为 Dizhi 成员")
  offset = tuple(Dizhi).index(shichen)
  fire, bell = _FIRE_BELL_STARTS[group]
  return (
    _placement(Star.火星, _move(fire, offset)),
    _placement(Star.铃星, _move(bell, offset)),
  )


def tianma_dizhi(branch: Dizhi) -> Dizhi:
  """按传入地支所属的三合组查天马。

  调用者负责传入年支或农历生月对应的地支；本函数不替调用者选择年马或月马。
  """
  return _TIANMA_BY_GROUP[_group_index(branch)]


def place_stars(value: CalculationInput) -> tuple[StarPlacement, ...]:
  """从解析结果安28星，按Star枚举顺序返回；要求时辰已知，允许性别未知。

  本入口不重做历法，也不调用完整命盘校验。命宫、左辅右弼和月马使用同一个安星月份，
  由effective_month按所选闰月归属规则确定。选择按前后半月分别归属时，用解析后的农历日
  判断：初一至十五按本月，十六日起按下月；不把前一个月的天数加到生日上。
  闰十二月需要按下月安星等无法处理的组合会抛错，不返回部分结果。
  每颗星只返回一个位置；天马的rule_id保存此次实际使用的规则，不靠日后的默认值还原。
  """
  return _place_natal_stars_v1(value)


def _place_natal_stars_v1(value: CalculationInput) -> tuple[StarPlacement, ...]:
  """计算已发布的 28 星规则组，不随默认全集扩张。"""
  # 在调用时才导入出生记录类型，避免仅查询安星知识时连带加载出生与历法模块。
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
    ma_branch = year.dizhi
  elif value.config.tianma_rule is TianmaRule.MONTH_BRANCH:
    ma_branch = tuple(Dizhi)[month_palace_index(month)]
  else:
    raise ValueError("不支持的天马查法选择")
  positions = (
    *place_major_stars(ju, value.day),
    *place_month_stars(month),
    *place_hour_stars(value.shichen),
    *place_stem_stars(year.tiangan),
    *place_fire_bell(year.dizhi, value.shichen),
    _placement(Star.天马, tianma_dizhi(ma_branch), value.config.tianma_rule),
  )
  if len(positions) != len(_NATAL_STARS_V1) or {item.star for item in positions} != set(
    _NATAL_STARS_V1
  ):
    raise ValueError("安星结果须恰有28颗不同星曜")
  return tuple(sorted(positions, key=lambda item: _NATAL_STARS_V1.index(item.star)))


def _place_stored_stars(
  value: CalculationInput, stars: tuple[Star, ...]
) -> tuple[StarPlacement, ...]:
  """按已有完整星集求值；任意子集不能冒充历史规则组。"""
  if stars != _NATAL_STARS_V1:
    raise ValueError("不支持的完整星集或星曜顺序")
  return _place_natal_stars_v1(value)
