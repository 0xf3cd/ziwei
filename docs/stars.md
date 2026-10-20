# 28星安星

[API参考](api.md#安星) · [出生输入](birth.md) · [知识查询](knowledge.md) · [项目入口](../README.md)

`place_stars()`从解析后的`CalculationInput`安28星：十四主星、六吉、六煞、禄存与天马。
返回不可变元组，每颗星有`Star`身份、地支`dizhi`与实际`rule_id`；每星恰一位置，多星可同宫。
这不是完整命盘API，不含四化、大限、序列化或吉凶解释。

## 从出生记录安星

以下为合成农历记录，不补地点、钟点或时区。三个历法口径仍须显式选择；
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
>>> len(positions), positions[-1].star is Star.天马
(28, True)
>>> positions[-1].dizhi.value, positions[-1].rule_id
('寅', 'variant.tianma.year-branch')
>>> Star.天马.concept_id
'concept.star.tianma'
```

结果按`Star`枚举顺序排列。星身份与知识标识不随显示名称或天马查法改变。
时系地空没有全局`Star.天空`别名，避免混同另一个年系对象。

## 天马的具名默认与覆盖

年马按解析结果的年支，月马按有效农历生月所对应地支（正月寅、二月卯等），不按节气月。
默认年马，可显式切换月马；只有天马的星位与规则标识改变：

```{doctest}
>>> from dataclasses import replace
>>> monthly_input = replace(value, config=replace(config, tianma_rule=TianmaRule.月支天马))
>>> monthly = place_stars(monthly_input)
>>> monthly[-1].dizhi.value, monthly[-1].rule_id
('申', 'variant.tianma.month-branch')
>>> positions[:-1] == monthly[:-1]
True
```

月马目前只核到《紫微斗數精成》网页一路独立成文，按具名单源例外执行；来源仍待核，
知识条目暂不默认展示。默认选择只属于安星规则，不替代闰月、子时换日、换年三个必填口径。

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

`place_month_stars()`接收有效月1至12，安左辅右弼；`place_hour_stars()`安昌曲与时系空劫；
`place_stem_stars()`安现代表魁钺、禄存与羊陀；`place_fire_bell()`按年支与时辰安火铃。
`tianma_dizhi()`只查所选地支，锚是年支还是月支由组合入口决定。
这些分组函数的返回值同样带规则标识；参数签名由[API](api.md#安星)生成。

## 归月与失败边界

组合入口不重新解析历法。命宫、辅弼与月马共享`effective_month()`，消费三个归月口径及
解析后的农历日；半月分界为`day>=16`，日不累加上月天数。这是项目组合规则，
不称作同一古籍或整套中州法；子时换日仍由解析层独立处理。

例如闰四月：归本月时辅未、弼未、月马亥；归下月时辅申、弼午、月马申。
半月口径在解析后的十五日取前者、十六日起取后者。闰十二归下月无对应有效月时整次失败，
不造来年正月规则，也不返回看似完整的部分结果；独立主星函数仍可调用。

公开函数拒绝错误枚举、`bool`冒充整数、越界月份与日期。未知时辰不代填子时；
农历不存在的月日由解析层拒绝。普通运行与`python -O`校验一致。

## 来源与参考表

全部规则标识、主星偏移及辅星数值表归`ziwei.stars`，
[安星参考表](knowledge-reference.md#implemented-stars)从这些定义生成；知识目录不抄第二张表。
来源逐条定位与限度见[安星材料](knowledge.md#安星材料的限度)。
