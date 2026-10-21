# 生年四化与大限

[项目入口](../README.md) · [解析层](resolver.md) · [API](api.md#生年四化与大限)

四化只说明哪颗星化禄、化权、化科、化忌，不改变星曜身份或位置。大限给出十二个宫位上的
岁数区间，不解释吉凶。两者可以独立计算，不要求先构造完整命盘。

## 显式选择一套完整四化表

目前提供《排命盘口诀》网页转录与王亭之《紫微斗数初级讲义》转录两套表，无默认。
前者指2007年论坛帖的网页，后者取讲义网页提取稿。名称只表示实际所见转录，
不认证某个门派或所有同名刊本。两套在戊科、庚科／忌、壬科上有分歧；
[完整参考表](knowledge-reference.md#implemented-sihua)从执行定义生成，不另维护一份数值表。

```{doctest}
>>> from ziwei.ganzhi import Tiangan
>>> from ziwei.sihua import SihuaVariant, sihua_for_stem
>>> d = sihua_for_stem(Tiangan.庚, SihuaVariant.排命盘口诀转录)
>>> (d.lu.value, d.quan.value, d.ke.value, d.ji.value)
('太阳', '武曲', '天同', '太阴')
>>> c = sihua_for_stem(Tiangan.庚, SihuaVariant.王亭之讲义转录)
>>> (c.ke.value, c.ji.value)
('天府', '天同')
>>> c.rule_id
'variant.sihua.wangtingzhi-lecture'
>>> d.variant.value
'排命盘口诀网页转录'
>>> SihuaVariant(d.variant.value) is SihuaVariant.排命盘口诀转录
True
```

`排命盘口诀转录`是成员名，保存的中文值为`排命盘口诀网页转录`；按值构造枚举时使用完整的保存值，
如上例所示。结果是不可变的`SihuaResult`，保留年干、变体、四颗星和规则标识。
禄权科忌使用固定字段，构造时还会校验四星与该年干、变体的表行一致；不接收可能重复或缺项的标签列表。
参数须为对应枚举成员，不把普通字符串猜成配置；
所请求的变体没有唯一完整定义时抛错，不换用另一张表。

## 命宫起大限

阳男阴女按子、丑、寅……亥顺行，阴男阳女逆行。首限在命宫，以五行局数起，每限十年。
这里的岁数是**虚岁标签，首尾均包含**，例如水二局首限为2–11，下一限12–21；
不是周岁，也不计算当前年龄或公历起止日期。本库不规定虚岁在生日、正月初一还是立春那天加一岁；
所选换年口径用于确定出生年干和阴阳。

```{doctest}
>>> from ziwei.birth import Gender
>>> from ziwei.bureau import WuxingJu
>>> from ziwei.decades import decade_periods
>>> from ziwei.ganzhi import Dizhi, Tiangan
>>> periods = decade_periods(Dizhi.亥, WuxingJu.水二局, Tiangan.甲, Gender.男)
>>> [(p.dizhi.value, p.start_age, p.end_age) for p in periods[:2]]
[('亥', 2, 11), ('子', 12, 21)]
>>> (len(periods), periods[0].direction.value, periods[0].age_convention)
(12, '顺行', '虚岁')
>>> periods[0].rule_id
'variant.decades.xusui-inclusive'
```

返回十二个不可变的`Decade`，第一项是命宫所在的首限，随后按顺行或逆行的方向排。
每限的字段保存地支、方向、起止岁数、年龄计法与规则标识；后两项由所用规则固定，不接收调用方覆盖。
首限前的岁数不补小限或童限。
性别未知时显式失败，不代填男或女。[大限示例](knowledge-reference.md#implemented-decades)同样从执行定义生成。

## 使用解析后的出生记录

```{doctest}
>>> from ziwei.birth import Gender, LunarBirthRecord
>>> from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, YearBoundary
>>> from ziwei.ganzhi import Dizhi
>>> from ziwei.resolver import resolve
>>> from ziwei.sihua import SihuaVariant, shengnian_sihua
>>> from ziwei.decades import place_decades
>>> choices = ChartConfig(
...   leap_month_policy=LeapMonthPolicy.全月归本月,
...   day_rollover=DayRollover.早晚子时同日,
...   year_boundary=YearBoundary.农历正月初一,
... )
>>> record = LunarBirthRecord(
...   year=2024, month=1, day=1, is_leap_month=False,
...   shichen=Dizhi.子, gender=Gender.男,
... )
>>> value = resolve(record, choices)
>>> shengnian_sihua(value, SihuaVariant.排命盘口诀转录).lu.value
'廉贞'
>>> place_decades(value)[0].dizhi.value
'寅'
```

这两个入口沿用`CalculationInput`的所选年干，不暗中改回农历年的年干；换年口径可能同时改变
四化、大限方向、宫干与五行局。大限的命宫也沿用所选闰月规则，晚子时是否顺延已由解析层处理。
只算四化不要求时辰或性别；从出生输入起大限则二者都须已知。既有`resolve()`和`place_stars()`调用不变。
四化不附带星位；需要显示在盘上时，可按`Star`身份关联安星结果，不用宫位作为唯一键覆盖同宫多星。

## 来源与验证能说明什么

- 《排命盘口诀》完整十干表取[所见论坛转录](knowledge-reference.md#source.zhongyi999-paimingpan)。
  甲、乙、丙、丁、己、辛、癸七干与王亭之讲义、读书网转录的[《九千飞星》对照表](knowledge-reference.md#source.jiuqian-dushu)相同；
  戊壬科另据[玄门转载的令东来说明](knowledge-reference.md#source.lingdonglai-sihua)，
  庚科忌另据[藏玄易社的独立解释](knowledge-reference.md#source.cangxuan-geng)。
  没有把这些说明拼成执行表，也没有声称取得第二份完整同表。
- 王亭之完整表取讲义网页提取稿，并与《九千飞星》对照表的王亭之列逐干核对。戊太阳科有直接文字，
  但纸本、PDF图像和版次未校，不能说成已认证的原著刊本。
- 1954甲午盘例检验共有的甲干四化，不能区分庚壬异文。
  1970庚戌图检验庚干四化；它不是王亭之原图，也不证明图作者采用讲义中庚以外的九干。
  该图没有完整生日，不能据此重排全星位。逐干字面期望另检全部表值。
- 论坛原文明说岁数是虚岁；其中的木三局顺逆例与1954火六局例都给出首尾包含的岁数区间。
  王亭之讲义图四的金四局原图另作区间和方向对照。这些例子不为本库增加实际换岁日期的合同。
- 电子《全书》的[邻宫起限异文](knowledge-reference.md#entry.decades.quanshu-adjacent)另存待核、不执行。
  该句只定父母／兄弟宫起限与顺逆，不借现行局数起岁规则补齐；本版仍从命宫起限。

具体定位、短引、独立支持及未核事项见知识条目
[网页转录四化](knowledge-reference.md#entry.sihua.zhongyi999)、
[讲义四化](knowledge-reference.md#entry.sihua.wangtingzhi-lecture)与
[大限](knowledge-reference.md#entry.decades.xusui-inclusive)。
来源仍保留转录未校的状态。代码能按所选表计算，但知识条目暂不默认展示，也不据此解读某张命盘。
