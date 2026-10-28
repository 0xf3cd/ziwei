# 第一层流年命宫与换年

[项目入口](../README.md) · [本命盘与按宫查询](chart.md) · [API](api.md#流年)

本页描述开发中的0.3.0功能，尚未发行。流年命宫落在目标年支的同支宫，
例如2025乙巳年落巳宫。虚岁、大限和本命命宫不参与这个定位。

## 已确定纪年：直接查命宫支

```{doctest}
>>> from ziwei.liunian import liunian_minggong
>>> liunian_minggong(2025).value
'巳'
```

参数是**已经确定的干支纪年编号**，支持1至9999；它不判断某个公历日期属于哪年。
此入口不需要出生资料、年界、农历算法或原生历法初始化。
定位规则标识为`LIUNIAN_MINGGONG_RULE_ID`，可交给知识目录查询出处。

## 日期：显式选择年界

同一日期在两种年界下可能属于不同的纪年。初一政策必须指定农历算法；立春日期政策不接受农历算法。

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
```

`LiunianYear`保存所归纪年、所选年界、`[start, end)`日期区间、实际使用的农历算法、
支持的纪年范围与celestial版本，精度为`date`。起点属于本年，终点属于下一年；查询日不另存入结果。
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

已有`chart`时，将流年命宫支交给原有查询即可：

```python
from ziwei.chart import palace_view
from ziwei.liunian import liunian_minggong

target = liunian_minggong(2025)
natal = palace_view(chart, target)
print(target.value, natal.palace.name.value)
```

`target`表示流年命宫地支，`natal.palace.name`仍是该处的本命宫名；星曜、四化与大限保持本命结果。
本次没有增加小限、流月、流日、流曜或运限四化，也没有流年叠盘显示入口。

## 来源与验证限度

- [《全书》卷三固定录文](knowledge-reference.md#source.quanshu-juan3-wikisource)十二支太岁到宫句与
  [现代作者的2025乙巳例](knowledge-reference.md#source.click108-liunian)支持窄定位。原句中的小限与吉凶保留为引文，不执行。
- 初一至除夕的流年定义来自现代作者网页；[两份PMO历书](knowledge-reference.md#source.pmo-calendar-2022)分别见证
  2022初一先于立春、2024立春先于初一。历书给出的立春时刻到分钟，测试只取日级预期。
- [固定软件调用链](knowledge-reference.md#source.iztro-liunian-date)支持立春**日期级**行为，作为具名兼容政策；
  所收材料尚未提供独立的紫微流年定义，不把软件选项称为古籍共识。依赖链不是多个独立来源。

离线材料分别保存外部观测与项目采用预期，差异按口径、输入、实现和来源未决分类。
固定印本、独立完整生辰流年盘和专业软件原始样本仍未取得；安装消费、合成组合与来源单元测试分别验收。
