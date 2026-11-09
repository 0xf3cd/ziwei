# 流年查询与本命叠读

[项目入口](../README.md) · [本命盘与按宫查询](chart.md) · [API](api.md#流年)

流年命宫落在目标年支的同支宫，再逆布年度十二宫；流禄、流羊、流陀及具名流年四化按目标年干查询。
可直接查询已确定纪年，或先从日期按所选年界取得纪年，再与同支本命内容分层读取。

也可用`流年星曜(2024).陀罗`等中文类型名和只读属性；完整出生记录、年度叠读与出处查询示例见
[中文领域入口](api.md#中文领域入口)。以下英文／拼音调用仍读取相同结果。

## 已确定纪年：直接查命宫支

```{doctest}
>>> from ziwei.liunian import liunian_minggong
>>> liunian_minggong(2025).value
'巳'
```

参数是**已经确定的干支纪年编号**，支持1至9999；它不判断某个公历日期属于哪年。
此入口不需要出生资料、年界、农历算法或原生历法初始化。
定位规则标识为`LIUNIAN_MINGGONG_RULE_ID`，可交给知识目录查询出处。

年度其他宫位用`liunian_palace_dizhi()`，宫名须为`PalaceName`成员：

```{doctest}
>>> from ziwei.liunian import liunian_palace_dizhi
>>> from ziwei.palaces import PalaceName
>>> liunian_palace_dizhi(1978, PalaceName.夫妻).value
'辰'
```

`PalaceName.夫妻`是`PalaceName.妻妾`的别名；下文表格按枚举值显示“妻妾”。

十二宫次序见[年度十二起点表](knowledge-reference.md#implemented-liunian-palaces)，规则与直接例见
[太岁起十二宫](knowledge-reference.md#entry.liunian.twelve-palaces)。宫位查询只给地支，不推导年度宫干。

## 年度禄羊陀

`liunian_stars()`返回目标年的流禄（禄存）、流羊（擎羊）与流陀（陀罗）：

```{doctest}
>>> from ziwei.liunian import liunian_stars
>>> annual = liunian_stars(2012)
>>> print(annual.year_ganzhi)
壬辰
>>> tuple(p.value for p in (annual.lucun, annual.qingyang, annual.tuoluo))
('亥', '子', '戌')
>>> annual.rule_id
'variant.liunian.lucun-yangtuo'
```

参数同样是1至9999的已确定纪年，拒绝`bool`、字符串和浮点数。`LiunianStars`不可变，
保存`ganzhi_year`，三位置由纪年派生，不能在构造时另填。此查询不需要本命盘或出生资料。
流禄给出年度禄存的落宫地支，化禄给出星曜，二者不能混用。
完整十干位置见[年度参考表](knowledge-reference.md#implemented-liunian-stars)。

## 具名年度四化

`liunian_sihua()`独立查询年度禄权科忌，不需要出生资料。必须显式选择表，当前年度入口支持
`SihuaVariant.王亭之讲义转录`，请求其他年度变体抛`ValueError`：

```{doctest}
>>> from ziwei.liunian import liunian_sihua
>>> from ziwei.sihua import SihuaVariant
>>> sihua = liunian_sihua(2030, variant=SihuaVariant.王亭之讲义转录)
>>> str(sihua.year_ganzhi), tuple(star.value for star in (sihua.lu, sihua.quan, sihua.ke, sihua.ji))
('庚戌', ('太阳', '武曲', '天府', '天同'))
>>> sihua.rule_id, sihua.table_id
('variant.liunian.sihua-wangtingzhi-lecture', 'variant.sihua.wangtingzhi-lecture')
```

`LiunianSihua`保存目标纪年与显式变体，四星由年干派生，构造时不能另填四星；纪年范围同为1至9999。
`rule_id`追溯年度用途，`table_id`追溯完整表。十干数值见[年度四化表](knowledge-reference.md#implemented-liunian-sihua)，
依据与适用边界见[讲义表的年度用途](knowledge-reference.md#entry.liunian.sihua-wangtingzhi-lecture)。

## 日期：显式选择年界

同一日期在两种年界下可能属于不同的纪年。初一政策必须指定农历算法；立春日期政策不接受农历算法。
不确定选哪种算法时，可用与解析层默认相同的`LunarAlgorithm.混合`（ALGO3）。

```{doctest}
>>> from datetime import date
>>> from ziwei.calendar import LunarAlgorithm
>>> from ziwei.liunian import LiunianBoundary, liunian_on_date
>>> lunar = liunian_on_date(
...   date(2024, 2, 4), boundary=LiunianBoundary.正月初一日期,
...   lunar_algorithm=LunarAlgorithm.混合,
... )
>>> solar = liunian_on_date(date(2024, 2, 4), boundary=LiunianBoundary.立春日期)
>>> print(lunar.year_ganzhi, solar.year_ganzhi)
癸卯 甲辰
>>> tuple(str(day) for day in (solar.start, solar.end))
('2024-02-04', '2025-02-03')
>>> solar.minggong.value, solar.date_basis, solar.supported_year_range
('辰', 'UTC+08', (1972, 2199))
>>> liunian_stars(lunar.ganzhi_year).lucun.value, liunian_stars(solar.ganzhi_year).lucun.value
('子', '寅')
```

`LiunianYear`保存所归纪年、所选年界、`[start, end)`日期区间、实际使用的农历算法、
支持的纪年范围与celestial版本。起点属于本年，终点属于下一年；查询日不另存入结果。
`rule_id`追溯命宫定位，`boundary.rule_id`追溯日期年界。结果不可变；支持范围由定义派生，不能由调用方填写。
直接构造只核字段关系，不重算历法，手工构造通过不能证明日期正确。

两种年界均无默认，也不继承`ChartConfig`的本命配置。传入本命`YearBoundary`或同值字符串会失败。
日期入口只收`date`，拒绝`datetime`，不会丢掉钟点或时区后再计算。

### 日期基准与支持范围

初一路径把输入视为**所选农历算法基准中的前推公历日期标签**，不做瞬间或当地时区转换。
前推公历指把公历规则延伸到1582年以前，不能直接当成史书的儒略历日期。
立春路径输入是**UTC+08日期标签**；其他时区的瞬间需由调用方先取得该基准的日期。

| 年界／算法 | 有效输入日期，含起点不含终点 | 日期基准 |
|---|---|---|
| 初一／ALGO1 | `[1901-02-19, 2100-02-09)` | HKO表标签，农历年1901至2099 |
| 初一／ALGO2 | `[0410-01-22, 2501-02-19)` | 天文算法标签，农历年410至2500 |
| 初一／ALGO3 | `[1600-02-15, 2200-02-15)` | 混合标签，农历年1600至2199 |
| 立春日期 | `[1972-02-05, 2200-02-04)` | modelled-UTC加8小时，干支年1972至2199 |

ALGO2在1972年以前用UT1代替UTC，再加8小时；1972年起使用闰秒表，最后一项之后冻结`ΔAT=37 s`。
ALGO3在1901至2099年沿用HKO，其余使用天文算法。不能把所有历史标签统一称为实际UTC+08日期。
立春日期也沿用现有的modelled-UT1/UTC转换与未来闰秒假设，支持到2199不构成准确度保证。
历法版本与范围应与结果一起查看；范围外显式失败，原生计算故障不会静默换用另一算法或政策。

### 立春日期与本命立春瞬间

本命`YearBoundary.立春`比较交接瞬间；流年`LiunianBoundary.立春日期`把立春所在的**整日**归新年。
2024年立春的历书时刻为北京时间2月4日16:27：当天10:00的本命立春纪年仍为2023，
当天18:00为2024；流年日期查询对2月4日整日均给2024。接口不接受钟点，也不承诺流年瞬间换年。

## 与已有本命盘叠读

`liunian_view(chart, ganzhi_year)`同时返回年度禄羊陀和流年命宫所在宫的本命内容。
下面用合成的2024年农历正月初一子时女命，查询2025乙巳年：

```{doctest}
>>> from ziwei.birth import Gender, LunarBirthRecord
>>> from ziwei.chart import create_chart, liunian_view
>>> from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, YearBoundary
>>> from ziwei.ganzhi import Dizhi
>>> from ziwei.sihua import SihuaVariant
>>> chart = create_chart(
...   LunarBirthRecord(year=2024, month=1, day=1, is_leap_month=False,
...                    shichen=Dizhi.子, gender=Gender.女),
...   ChartConfig(leap_month_policy=LeapMonthPolicy.全月归本月,
...               day_rollover=DayRollover.早晚子时同日, year_boundary=YearBoundary.农历正月初一),
...   sihua_variant=SihuaVariant.排命盘口诀转录,
... )
>>> view = liunian_view(chart, 2025)
>>> view.liunian.lucun.value, view.natal.palace.dizhi.value, view.natal.palace.name.value
('卯', '巳', '田宅')
```

`view.liunian`给出整年的禄羊陀位置；`view.natal`只读取流年命宫所在的一宫，本例为巳宫，
本命宫名仍是田宅。`view.natal.stars`、生年四化和身宫标记均来自本命盘，不混入年度禄羊陀。
`chart`本身不被修改。

从日期叠读时，把`liunian_on_date()`结果的`ganzhi_year`传入即可；改选年界也在日期查询这一步完成。
例如沿用上面的立春日期结果`solar`：

```{doctest}
>>> dated_view = liunian_view(chart, solar.ganzhi_year)
>>> dated_view.liunian == liunian_stars(2024)
True
>>> dated_view.natal.palace.dizhi.value
'辰'
```

若只需该处本命内容，仍可用`palace_view(chart, liunian_minggong(ganzhi_year))`。
`LiunianView`直接构造时核类型与宫支对应关系；成员类型不对抛`TypeError`，宫支不对应抛`ValueError`。

## 从出生记录读取年度十二宫

`liunian_palaces()`按`PalaceName`顺序返回十二个`LiunianPalaceView`。本例使用合成出生资料，
本命表选《排命盘口诀》转录，年度表另选王亭之讲义转录；两次选择互不代替。

```{doctest}
>>> from datetime import date
>>> from ziwei.birth import 农历出生记录, 性别
>>> from ziwei.calendar import LunarAlgorithm
>>> from ziwei.chart import create_chart, liunian_palaces, 宫位视图, 流年宫位
>>> from ziwei.config import 命盘配置, 闰月归属, 子时换日, 换年界线
>>> from ziwei.ganzhi import 地支
>>> from ziwei.liunian import liunian_on_date, 流年年界
>>> from ziwei.sihua import 四化变体
>>> 出生 = 农历出生记录(
...   year=2024, month=1, day=1, is_leap_month=False, shichen=地支.子, gender=性别.女,
... )
>>> 口径 = 命盘配置(
...   leap_month_policy=闰月归属.全月归本月,
...   day_rollover=子时换日.早晚子时同日, year_boundary=换年界线.农历正月初一,
... )
>>> 命盘 = create_chart(出生, 口径, sihua_variant=四化变体.排命盘口诀转录)
>>> 年度 = liunian_on_date(
...   date(2025, 6, 1), boundary=流年年界.正月初一日期, lunar_algorithm=LunarAlgorithm.混合,
... )
>>> 各宫 = liunian_palaces(命盘, 年度.纪年, sihua_variant=四化变体.王亭之讲义转录)
>>> def 四化标记(value: 宫位视图 | 流年宫位) -> str:
...   marks = (("禄", value.化禄), ("权", value.化权), ("科", value.化科), ("忌", value.化忌))
...   return "、".join(f"{star.value}{label}" for label, star in marks if star is not None) or "—"
>>> print("流年宫名 | 地支 | 本命宫名 | 本命星曜 | 生年四化 | 流年四化")
流年宫名 | 地支 | 本命宫名 | 本命星曜 | 生年四化 | 流年四化
>>> for 宫 in 各宫:
...   本命 = 宫.本命宫
...   星曜 = "、".join(position.星曜.value for position in 本命.星位) or "—"
...   print(" | ".join((宫.宫名.value, 宫.地支.value, 本命.宫位.宫名.value,
...                     星曜, 四化标记(本命), 四化标记(宫))))
命宫 | 巳 | 田宅 | 武曲、破军、天喜 | 破军权、武曲科 | —
兄弟 | 辰 | 福德 | 天同、左辅、文曲 | — | —
妻妾 | 卯 | 父母 | 擎羊 | — | —
子女 | 寅 | 命宫 | 火星、禄存、天马 | — | —
财帛 | 丑 | 兄弟 | 廉贞、七杀、天魁、陀罗 | 廉贞禄 | —
疾厄 | 子 | 妻妾 | 天梁 | — | 天梁权
迁移 | 亥 | 子女 | 天相、地空、地劫、红鸾 | — | —
奴仆 | 戌 | 财帛 | 巨门、右弼、文昌、铃星 | — | —
官禄 | 酉 | 疾厄 | 紫微、贪狼 | — | 紫微科
田宅 | 申 | 迁移 | 天机、太阴 | — | 天机禄、太阴忌
福德 | 未 | 奴仆 | 天府、天钺 | — | —
父母 | 午 | 官禄 | 太阳 | 太阳忌 | —
```

首行巳宫在年度中是命宫，在本命中仍是田宅宫。`宫.本命宫`保留本命宫名、星位、生年四化与身宫标记；
年度化禄星在本宫时，`宫.化禄`返回这颗星，否则为`None`；`化权`、`化科`、`化忌`同理。
`宫.本命宫.化禄`等属性仍给生年标记，本命与年度可以在同一星曜上保留不同标记。
`宫.流年四化`是整年的`LiunianSihua`，十二行共享同一个不可变结果；省略`sihua_variant`或传`None`
只查宫位，`宫.流年四化`为`None`，不会从本命配置选择年度表。年度禄羊陀仍用`liunian_stars()`单独读取。

从结果继续查所用规则与出处：

```{doctest}
>>> from ziwei.knowledge import load_catalog
>>> 目录 = load_catalog()
>>> 各宫[0].rule_id
'variant.liunian.twelve-palaces'
>>> 年化 = 各宫[0].流年四化
>>> 年化 is not None
True
>>> 目录.get(年化.rule_id).implementation
'ziwei.liunian.liunian_sihua'
>>> 目录.references(年化.rule_id)[0].source_id
'source.zhongzhou-mdyixue-upper'
```

直接构造年度宫位视图会核年度宫名与地支、四化纪年是否一致；本命内容仍由`PalaceView`校验。
六列文本表由示例读取结构化结果生成，现有`render_text()`和`render_svg()`仍只渲染本命盘。

## 来源与验证限度

年度禄羊陀的出处、文献例子与限度见[知识条目](knowledge-reference.md#entry.liunian.lucun-yangtuo)。

- [《全书》卷三固定录文](knowledge-reference.md#source.quanshu-juan3-wikisource)十二支太岁到宫句与
  [现代作者的2025乙巳例](knowledge-reference.md#source.click108-liunian)支持窄定位。原句中的小限与吉凶保留为引文，不执行。
- 初一至除夕的流年定义来自现代作者网页；[两份PMO历书](knowledge-reference.md#source.pmo-calendar-2022)分别见证
  2022初一先于立春、2024立春先于初一。历书给出的立春时刻到分钟，测试只取日级预期。
- [固定软件调用链](knowledge-reference.md#source.iztro-liunian-date)支持立春**日期级**行为，作为具名兼容政策；
  调用链上的几个库只算一路来源。

两种日期政策的限度与复核条件见[初一](knowledge-reference.md#entry.liunian.lunar-new-year)与
[立春日期](knowledge-reference.md#entry.liunian.lichun-date)条目。
