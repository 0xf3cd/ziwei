# 小限、童限与具名衔接

[API](api.md#小限童限与运限并读) · [知识查询](knowledge.md) · [四化与大限](sihua-decades.md)

三套定位分别计算：小限按生年支和性别每岁走一宫，童限六宫按年龄取本命宫名，大限按五行局起岁、每宫十年。
它们不必互相替代。本页的现代衔接框架始终给出小限，并要求显式选择童限是否包含大限起限当岁。
所有年龄都是调用者提供的正整数虚岁标签；不接受bool，不计算当前年龄、换岁日期或吉凶。

## 独立定位

小限不要求完整出生资料、时辰、年干阴阳或目标流年：

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

童限低层只返回宫名，不要求性别、命宫或五行局：

```{doctest}
>>> from ziwei.tongxian import tongxian_palace
>>> tongxian_palace(3).value
'疾厄'
```

一至六岁的完整表和小限四组起宫见[生成参考表](knowledge-reference.md#implemented-tongxian)。
`tongxian_palace(7)`抛`NotImplementedError`，不把六宫循环成无限童限，也不猜七岁后古法。

## 显式选择现代衔接读法

`tongxian_at_age()`还需本命命宫与五行局；`boundary`必填，没有默认值。
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
这是两种项目读法的行为差别，不是两条已经分别核定的古籍结论。各局的实际适用年龄见
[衔接参考表](knowledge-reference.md#implemented-tongxian-boundaries)：不含时任何局都到不了六岁官禄，
包含时火六局可以查询六岁官禄。这个后果不用于判断哪种读法是文献原意。

超过所选现代政策的适用年龄，`tongxian_at_age()`返回宫名、地支均为`None`的读数；
它先判断适用性，因此七岁不会调用低层未定义的映射。缺少必填参数、错误枚举或非法年龄仍然失败，
不把缺输入、规则未定义和政策不适用混在一起，也不自动改用小限。

## 从已有命盘并读

`yunxian_at_age()`读取已有盘，不改变本命盘或大限区间，也不重算历法：

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

改变童限边界不改变同岁的`xiaoxian`或`decade`。首大限开始前`decade`为`None`，
超过盘内十二大限的最后一年则抛`ValueError`；这不限制独立小限查询的正整数年龄。
结果均不可变。直接构造`Yunxian`只核成员类型、年龄与区间关系，不认证与一张未提供的原盘一致。

## 出处、解释与未决知识

`small.rule_id`与`through.rule_id`分别定位小限规则和六宫映射；`through.boundary.rule_id`定位实际衔接解释。
知识查询不需要命盘或原生历法：

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
两处口诀同族，传承独立性未核；男女同法的明文只核到《捷览》转录，其原书正文与注文层次未校。

停止关联大限、童限期间参看小限见[《精成》下载件](knowledge-reference.md#source.jingcheng-pdf)第507页，
目前只核到一路现代文本，纸本版次未核。两个边界是对未明当岁的仓内解释，不是新造流派；
[不含当岁](knowledge-reference.md#entry.tongxian.before-decade)与
[包含当岁](knowledge-reference.md#entry.tongxian.through-decade-start)分别记录定义、前提和限度。

古籍录文另提七八九岁或十五命宫，其年龄范围与本模块最晚六岁停止的现代框架不同。
[待定条目](knowledge-reference.md#entry.tongxian.classical-unresolved)保留未核定的完整宫位和出限条件，
不把现代框架当成古法的已知部分，不将五星后续宫序移植进来。

测试将《精成》第24页的一至三岁直接例、口诀展开与项目边界合成用例分开。
该页女命四岁亥宫与同页规则不符，不作正确期望。当前没有完整外部交接边界盘例；
测试通过不认证古籍底本、历史源流或某种当岁读法。相关知识均不默认展示，来源问题见
[#71](https://github.com/0xf3cd/ziwei/issues/71)及[#43](https://github.com/0xf3cd/ziwei/issues/43)。
