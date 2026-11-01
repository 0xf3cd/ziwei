# 小限、童限与运限查询

[API](api.md#小限童限与运限并读) · [知识查询](knowledge.md) · [四化与大限](sihua-decades.md)

小限按生年支和性别每岁走一宫，童限按年龄取本命宫名，大限按五行局起岁、每宫十年。
查询时传入正整数虚岁。并读三套运限时，小限始终给出，童限是否包含大限起限当岁由调用者选择。

## 独立定位

用生年支、性别和虚岁查询小限：

```{doctest}
>>> from ziwei.birth import Gender
>>> from ziwei.ganzhi import Dizhi
>>> from ziwei.xiaoxian import xiaoxian_at_age
>>> small = xiaoxian_at_age(Dizhi.寅, Gender.女, 3)
>>> small.dizhi.value
'寅'
>>> (small.year_dizhi.value, small.gender.value, small.age)
('寅', '女', 3)
```

`tongxian_palace(age)`按虚岁返回本命宫名：

```{doctest}
>>> from ziwei.tongxian import tongxian_palace
>>> tongxian_palace(3).value
'疾厄'
```

一至六岁的完整表见[童限参考表](knowledge-reference.md#implemented-tongxian)，小限四组起宫见
[小限参考表](knowledge-reference.md#implemented-xiaoxian)。
`tongxian_palace()`支持一至六岁；七岁起抛`NotImplementedError`。

## 选择童限的起限当岁边界

`tongxian_at_age()`按本命命宫、五行局和虚岁定位童限，用必填参数`boundary`选择是否包含起限当岁。
以命宫辰、木三局、虚岁三岁为合成例：

```{doctest}
>>> from ziwei.bureau import WuxingJu
>>> from ziwei.tongxian import TongxianBoundary, tongxian_at_age
>>> through = tongxian_at_age(
...   Dizhi.辰, WuxingJu.木三局, 3, boundary=TongxianBoundary.起限当岁包含,
... )
>>> (through.palace_name.value, through.dizhi.value)
('疾厄', '亥')
>>> before = tongxian_at_age(
...   Dizhi.辰, WuxingJu.木三局, 3, boundary=TongxianBoundary.起限当岁不含,
... )
>>> (before.palace_name, before.dizhi)
(None, None)
```

包含时，木三局三岁还有童限疾厄，首大限也已开始；不包含时，三岁起停止童限。
各局的童限适用年龄见[衔接参考表](knowledge-reference.md#implemented-tongxian-boundaries)。

超过所选边界的适用年龄时，结果的`palace_name`与`dizhi`均为`None`。
在这个入口查询七岁，也会得到这样的读数。

## 从已有命盘并读

用`yunxian_at_age()`查询已有命盘在指定虚岁的三套运限：

```{doctest}
>>> from ziwei.birth import LunarBirthRecord
>>> from ziwei.chart import create_chart
>>> from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, YearBoundary
>>> from ziwei.sihua import SihuaVariant
>>> from ziwei.yunxian import yunxian_at_age
>>> chart = create_chart(
...   LunarBirthRecord(year=2024, month=1, day=1, is_leap_month=False, shichen=Dizhi.子, gender=Gender.女),
...   ChartConfig(leap_month_policy=LeapMonthPolicy.全月归本月, day_rollover=DayRollover.早晚子时同日, year_boundary=YearBoundary.农历正月初一),
...   sihua_variant=SihuaVariant.排命盘口诀转录,
... )
>>> age = chart.bureau.number
>>> a = yunxian_at_age(chart, age, tongxian_boundary=TongxianBoundary.起限当岁包含)
>>> b = yunxian_at_age(chart, age, tongxian_boundary=TongxianBoundary.起限当岁不含)
>>> (a.xiaoxian == b.xiaoxian, a.decade is b.decade, a.decade is chart.decades[0])
(True, True, True)
>>> (a.tongxian.dizhi is None, b.tongxian.dizhi is None)
(False, True)
```

上例切换童限边界后，`xiaoxian`和`decade`保持相同。首大限开始前`decade`为`None`，
超过盘内十二大限的最后一年则抛`ValueError`。独立小限查询支持任意正整数虚岁。

## 出处、解释与未决知识

`small.rule_id`与`through.rule_id`分别指向小限规则和六宫映射；`through.boundary.rule_id`指向所选童限边界。
用知识目录读取规则定义和出处：

```{doctest}
>>> from ziwei.knowledge import load_catalog
>>> catalog = load_catalog()
>>> catalog.get(through.boundary.rule_id).definition == through.boundary.definition
True
>>> catalog.get('entry.tongxian.classical-unresolved').show_by_default
False
```

[小限条目](knowledge-reference.md#entry.xiaoxian.year-branch-gender)记录四组起宫和男顺女逆；
[六宫条目](knowledge-reference.md#entry.tongxian.six-palaces)保留《全书》与《捷览》的录文。
两份录文中的口诀相近；是否出自同一路转抄，尚待核对。男女用法一致的说明见《捷览》的电子录文，
原书中这段是正文还是注文，仍待影印本核对。

[《精成》下载件](knowledge-reference.md#source.jingcheng-pdf)第507页主张进入大限后停止看童限，并在童限期间参看小限。
目前只核到这一路现代文本，纸本版次未核；原文没有明确起限当岁如何处理，本项目提供包含与不含两个选项：
[不含当岁](knowledge-reference.md#entry.tongxian.before-decade)与
[包含当岁](knowledge-reference.md#entry.tongxian.through-decade-start)分别记录定义、前提和限度。

古籍录文另提七八九岁或十五命宫；完整的后续宫位与童限结束条件仍待核定，
详见[待定条目](knowledge-reference.md#entry.tongxian.classical-unresolved)。当前两种边界采用上述现代文本的停止说法。

目前还缺能验证起限当岁边界的完整外部盘例，相关知识条目暂不进入默认展示。核验进展见
[#71](https://github.com/0xf3cd/ziwei/issues/71)及[#43](https://github.com/0xf3cd/ziwei/issues/43)。
