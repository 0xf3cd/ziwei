# 36星安星

[API参考](api.md#安星) · [出生输入](birth.md) · [知识查询](knowledge.md) · [项目入口](../README.md)

`place_stars()`从解析后的`CalculationInput`安36星：十四主星、六吉、六煞、禄存、天马、红鸾天喜、刑姚、哭虚与伤使。
红鸾／天喜自0.3.0起提供，0.2.0的星集仍为28星。
返回不可变元组，每项保存星曜`Star`、所在宫位的地支`dizhi`和实际使用的规则标识`rule_id`。
每颗星只有一个位置，不同星可以落在同一宫。
`place_stars()`不是完整命盘API，不含四化、大限或吉凶解释；
另有独立的[四化与大限](sihua-decades.md)入口。

## 从出生记录安星

以下为合成农历记录，不补地点、钟点或时区。构造配置时，须自行选择闰月归属、子时换日和换年界线；
安星需要已知时辰，性别可以未知。

```{doctest}
>>> from ziwei.birth import LunarBirthRecord, Gender
>>> from ziwei.config import ChartConfig, LeapMonthPolicy, DayRollover, YearBoundary, TianmaRule
>>> from ziwei.ganzhi import Dizhi
>>> from ziwei.resolver import resolve
>>> from ziwei.stars import Star, place_stars
>>> config = ChartConfig(
...   leap_month_policy=LeapMonthPolicy.全月归本月,
...   day_rollover=DayRollover.早晚子时同日,
...   year_boundary=YearBoundary.农历正月初一,
... )
>>> record = LunarBirthRecord(
...   year=2024, month=1, day=7, is_leap_month=False,
...   shichen=Dizhi.子, gender=Gender.未知,
... )
>>> value = resolve(record, config)
>>> positions = place_stars(value)
>>> horse = next(position for position in positions if position.star is Star.天马)
>>> len(positions), horse.dizhi.value, horse.rule_id
(36, '寅', 'variant.tianma.year-branch')
>>> Star.天马.concept_id
'concept.star.tianma'
```

结果按`Star`枚举顺序排列。同一颗星的枚举成员与知识标识，不因显示名称或天马查法改变。
`ziwei.stars.MAJOR_STARS`给出十四主星的成员元组，可用`position.star in MAJOR_STARS`筛选已有星位，
无需另写一份主星名单；导入路径与类型见[安星API](api.md#安星)。
《全书》把按出生时辰安的地空称为天空；中州派讲义还列出另一颗按年支安的天空，本版不安那颗星。
为避免混淆，本项目不设`Star.天空`别名。

## 默认按年支安天马，也可改用月支

年支天马（年马）按解析结果的年支查表；月支天马（月马）把安星用的农历月份对应到地支，
如正月为寅、二月为卯，再查天马位置，不按节气划分月份。
默认使用年马，改为月马时，只有天马的位置与规则标识改变：

```{doctest}
>>> from dataclasses import replace
>>> monthly_input = replace(value, config=replace(config, tianma_rule=TianmaRule.月支天马))
>>> monthly = place_stars(monthly_input)
>>> monthly_horse = next(position for position in monthly if position.star is Star.天马)
>>> monthly_horse.dizhi.value, monthly_horse.rule_id
('申', 'variant.tianma.month-branch')
>>> tuple(p for p in positions if p.star is not Star.天马) == tuple(p for p in monthly if p.star is not Star.天马)
True
```

月马的出处与转录限度见[月马条目](knowledge-reference.md#entry.tianma.month-branch)。
天马有默认查法，不代表闰月归属、子时换日和换年界线也有默认值；这三项仍须自行指定。

## 主星与分组纯函数

已知五行局与农历日时，可独立安十四主星，不加载原生历法：

```{doctest}
>>> from ziwei.bureau import WuxingJu
>>> from ziwei.stars import place_major_stars, ziwei_dizhi, tianfu_dizhi
>>> ziwei_dizhi(WuxingJu.木三局, 22).value
'亥'
>>> tianfu_dizhi(Dizhi.亥).value
'巳'
>>> len(place_major_stars(WuxingJu.火六局, 30))
14
```

各组也可单独计算，返回的星位均带规则标识：

- `place_month_stars()`接收按月系闰月规则处理后的月份（1至12），依次安左辅、右弼、天刑、天姚。
- `place_hour_stars()`按时辰安文昌、文曲、地空、地劫。
- `place_stem_stars()`按年干安天魁、天钺、禄存、擎羊、陀罗；天魁、天钺使用现代资料的表。
- `place_fire_bell()`按年支与时辰安火星、铃星。
- `place_hongluan_tianxi()`按已确定的生年支安红鸾、天喜，不需要生时或性别。
- `place_tianku_tianxu()`按已确定的生年支安天哭、天虚。
- `place_tianshang_tianshi()`按命宫安固定法天伤、天使。

`tianma_dizhi()`只按传入的地支查天马，返回地支位置，不返回星位记录。
`place_stars()`负责选择传入年支还是农历月份对应的地支。各函数签名见[API](api.md#安星)。

## 红鸾与天喜

两星使用本命配置已经确定的生年支，不从公历年份另推，也不另设换年选项。
红鸾在卯宫起子年，逆数至生年支，天喜在其对宫；可以只给已确定的年支单独查询：

```{doctest}
>>> from ziwei.stars import place_hongluan_tianxi
>>> [(p.star.value, p.dizhi.value) for p in place_hongluan_tianxi(Dizhi.丑)]
[('红鸾', '寅'), ('天喜', '申')]
```

该位置与《捷览》乙丑直接例一致，但例子没有完整出生年月日时或年界配置。
直接例、口诀展开与合成完整盘的证明范围分开，见[红鸾天喜条目](knowledge-reference.md#entry.star.hongluan-tianxi-year-branch)。

## 天刑与天姚

天刑从酉起正月、天姚从丑起正月，两星均顺行到生月。可以从分组函数读取：

```{doctest}
>>> from ziwei.stars import place_month_stars
>>> [(p.star.value, p.dizhi.value) for p in place_month_stars(9)[-2:]]
[('天刑', '巳'), ('天姚', '酉')]
>>> place_month_stars(9)[-1].rule_id
'variant.star.tianxing-tianyao-month'
```

这个位置与iLuck九月直接例相同。两星没有生年四化或本库亮度等级；从完整盘按宫读取时仍是普通星位，
文本与SVG盘面都会显示这两颗星。定位依据见[刑姚条目](knowledge-reference.md#entry.star.tianxing-tianyao-month)。

## 天哭天虚与固定法天伤天使

哭虚从午宫起子年，哭逆虚顺，使用解析后的年支。伤使只依赖命宫，天伤固定在奴仆宫、天使固定在疾厄宫，
不按性别或年干阴阳互换：

```{doctest}
>>> from ziwei.stars import place_tianku_tianxu, place_tianshang_tianshi
>>> [(p.star.value, p.dizhi.value) for p in place_tianku_tianxu(Dizhi.辰)]
[('天哭', '寅'), ('天虚', '戌')]
>>> [(p.star.value, p.dizhi.value) for p in place_tianshang_tianshi(Dizhi.巳)]
[('天伤', '戌'), ('天使', '子')]
>>> place_tianshang_tianshi(Dizhi.巳)[0].rule_id
'variant.star.tianshang-tianshi-fixed'
```

伤使的另一种[阴阳男女互换法](knowledge-reference.md#variant.star.tianshang-tianshi-yinyang)仅登记在知识目录，
没有执行选项。定位来源见[哭虚](knowledge-reference.md#entry.star.tianku-tianxu-year-branch)与
[固定伤使](knowledge-reference.md#entry.star.tianshang-tianshi-fixed)条目。

## 归月与失败边界

`leap_month_policy`选择命身取月；`month_star_leap_month_policy`可另选辅弼、月马与刑姚取月，
省略或传`None`时跟随命身。两组都支持整月本月、整月下月与半月法；半月法推荐作为起步示例，
构造配置时仍须显式选择闰月、子时和年界，不会自动套用一整套流派规则。

下面用合成的2023闰二月十六日，命身按本月、月系按半月法，刑姚便使用三月：

```{doctest}
>>> mixed_config = replace(config,
...   month_star_leap_month_policy=LeapMonthPolicy.上半月归本月下半月归下月,
... )
>>> mixed_record = LunarBirthRecord(year=2023, month=2, day=16, is_leap_month=True,
...   shichen=Dizhi.子, gender=Gender.未知)
>>> mixed_input = resolve(mixed_record, mixed_config)
>>> [(p.star.value, p.dizhi.value) for p in place_stars(mixed_input) if p.star in (Star.天刑, Star.天姚)]
[('天刑', '亥'), ('天姚', '卯')]
>>> mixed_input.config.leap_month_policy.value, mixed_input.config.month_star_policy.value
('全月归本月', '上半月归本月、下半月归下月')
>>> replace(mixed_config, month_star_leap_month_policy=None).month_star_policy.value
'全月归本月'
```

未指定月系时，`dataclasses.replace()`修改命身口径也会改变月系；已经显式指定的月系则保持自己的选择。
月系覆盖不影响命身宫、五行局、主星或大限，年支天马也不受影响。组合依据与不同说法见
[归月条目](knowledge-reference.md#entry.star.month-policy-composition)。

两组都用`effective_month()`确定月份；选择半月法时，按解析后的农历日判断，初一至十五按本月、十六日起按下月。
子时换日由解析层先处理，紫微仍用解析后的日数，不累加前月天数。

闰十二月若需要按下月计算，就没有可用的第13月；这也包括前后半月分别归属时的十六日起。
命身或月系需要第13月时整次安星抛错，不自行改作来年正月，也不返回部分星位。
大限入口只需命身月份，不需要月系月份；只按五行局与生日计算的主星函数仍可单独调用。

公开函数拒绝错误枚举、`bool`冒充整数、越界月份与日期。未知时辰不代填子时；
农历不存在的月日由解析层拒绝。普通运行与`python -O`校验一致。

## 来源与参考表

全部规则标识、主星偏移及辅星数值表归`ziwei.stars`，
[安星参考表](knowledge-reference.md#implemented-stars)从这些定义生成；知识目录不抄第二张表。
来源逐条定位与限度见参考页的[来源](knowledge-reference.md#records-sources)与[条目](knowledge-reference.md#records-entries)记录。
