# ziwei

Python 紫微斗数排盘与知识库。历法与时间由
[celestial-calendar](https://github.com/0xf3cd/celestial-calendar) 提供；本仓记录紫微斗数的安星规则、
四化口径、流派变体与出处，并组织可复现的命盘结果。

本页介绍所在源码版本的功能与用法。GitHub上`main`分支的本页与[在线文档](https://0xf3cd.github.io/ziwei/)随开发更新，
可能包含尚未发行的接口。版本变化见[发行说明](https://0xf3cd.github.io/ziwei/docs/releases.html)，公开发行记录以
[PyPI](https://pypi.org/project/ziwei/)和[GitHub Releases](https://github.com/0xf3cd/ziwei/releases)为准。

目前提供出生记录、显式口径配置、民用时刻消歧、干支基础、celestial 历法适配、解析层
（公历/农历记录到计算输入）、命宫身宫与十二宫、五行局、30星安星、具名生年四化与大限，
以及完整命盘组合、十四主星七级亮度、第一层流年、只读按宫查询与宫位关系、文本十二宫格、静态SVG盘面和独立知识目录。
用法见[出生输入](https://0xf3cd.github.io/ziwei/docs/birth.html)、[历法与时间](https://0xf3cd.github.io/ziwei/docs/calendar.html)、
[解析层](https://0xf3cd.github.io/ziwei/docs/resolver.html)、[命宫身宫与十二宫](https://0xf3cd.github.io/ziwei/docs/palaces.html)、
[五行局](https://0xf3cd.github.io/ziwei/docs/bureau.html)、[安星](https://0xf3cd.github.io/ziwei/docs/stars.html)、
[四化与大限](https://0xf3cd.github.io/ziwei/docs/sihua-decades.html)、[完整命盘与盘面](https://0xf3cd.github.io/ziwei/docs/chart.html)
和[知识查询](https://0xf3cd.github.io/ziwei/docs/knowledge.html)。亮度的具名表、调用与来源限度见
[亮度指南](https://0xf3cd.github.io/ziwei/docs/brightness.html)。独立纪年查询与两种日期年界见
[流年指南](https://0xf3cd.github.io/ziwei/docs/liunian.html)。开发检查与协作约定见
[参与开发](https://0xf3cd.github.io/ziwei/docs/contributing.html)，发布状态与失败处理见
[发布指南](https://0xf3cd.github.io/ziwei/docs/releasing.html)。

当前不提供命盘JSON保存／恢复与旧盘重算接口，也不读取旧JSON命盘；历史兼容变化见
[发行说明](https://0xf3cd.github.io/ziwei/docs/releases.html)。

## 安装

先确认下方[安装要求](#安装要求)中的平台限制，再在已激活的独立虚拟环境中从正式PyPI安装当前发行版。

```sh
python -m pip install ziwei
python -m pip check
```

发行版接口与`main`文档可能不同，请先核对[发行说明中的兼容变化](https://0xf3cd.github.io/ziwei/docs/releases.html)。
需要使用开发中的接口时，可[从源码安装](https://0xf3cd.github.io/ziwei/docs/contributing.html)。
`main`源码不等同于PyPI发行制品；上传前的候选状态见[发布指南](https://0xf3cd.github.io/ziwei/docs/releasing.html)。

## 安装要求

支持Python 3.11–3.14。运行时精确依赖`celestial-calendar==0.8.0`与`tzdata==2026.5`。
celestial-calendar 0.8.0在PyPI只提供下列原生wheel，没有源码分发包；ziwei自身的纯Python wheel不扩大这个范围：

| 平台 | 架构与最低系统要求 |
|---|---|
| macOS | arm64，macOS 14或更新 |
| Linux | x86_64，glibc 2.26或更新；aarch64，glibc 2.24或更新 |
| Windows | amd64 |

Intel macOS、Windows ARM64、较旧macOS和musl Linux不在上述制品覆盖范围内，不能依靠pip自动回退源码构建。
请使用独立虚拟环境；与不同精确版本的celestial-calendar或tzdata显式共装会冲突。
安装ziwei时，pip也可能将环境中已有的较新celestial-calendar或tzdata降到上述精确版本。
允许的依赖版本与复查条件见[依赖兼容策略](https://0xf3cd.github.io/ziwei/docs/contributing.html)。

## 最小排盘

下面用合成的2024年农历正月初一子时女命演示最小排盘。
“口径”指闰月归属、子时换日和换年界线这三项计算选择；本例逐项指定，并选择一张具名生年四化表。
本例不是闰月，闰月归属不影响结果。农历记录只给时辰、没有钟点和时区，因此按农历正月初一换年，子时采用同日口径。
若要用立春换年，或区分早晚子时以执行晚子时归次日，须改用带钟点与时区的公历记录；
其他出生资料的口径选择与输入要求见[解析层](https://0xf3cd.github.io/ziwei/docs/resolver.html)。

```{doctest}
>>> from ziwei.birth import Gender, LunarBirthRecord
>>> from ziwei.chart import create_chart
>>> from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, YearBoundary
>>> from ziwei.ganzhi import Dizhi
>>> from ziwei.render import render_text
>>> from ziwei.sihua import SihuaVariant
>>> record = LunarBirthRecord(
...   year=2024, month=1, day=1, is_leap_month=False, shichen=Dizhi.子, gender=Gender.女,
... )
>>> choices = ChartConfig(
...   leap_month_policy=LeapMonthPolicy.全月归本月,
...   day_rollover=DayRollover.早晚子时同日,
...   year_boundary=YearBoundary.农历正月初一,
... )
>>> chart = create_chart(record, choices, sihua_variant=SihuaVariant.排命盘口诀转录)
>>> text = render_text(chart)
>>> print(text.splitlines()[0])
火六局 · 大限逆行 · 虚岁首尾包含
```

这里仅显示盘面摘要。用`print(text, end="")`查看十二宫、30星、四化与大限；
[同一输入的完整盘面](https://0xf3cd.github.io/ziwei/docs/chart.html)及其计算与验证边界见指南。
未知时辰或性别可以保存在出生记录中，但完整命盘入口会拒绝，不代填。

## 功能范围

已知出生时刻与性别，排出可复现的本命盘：

- 保存出生原始记录，显式处理时区与可选的真太阳时，保留解析后的农历年月日时与所用历法算法。
- 闰月归属、子时换日、换年三个口径作为具名配置，不设静默默认。
- 安命宫、身宫与十二宫宫干，定五行局，安紫微、天府两系十四主星。
- 安六吉、六煞、禄存、天马与红鸾天喜；按所选具名四化表取生年四化。
- 起大限：顺逆由年干阴阳与性别定，首限起始虚岁由五行局数定。
- 命盘结果不可变，保留输入、口径、历法版本与派生结果；另提供文本与静态SVG盘面用于显示。

功能与改进进度见[项目议题](https://github.com/0xf3cd/ziwei/issues)。

## 设计边界

- [仓库结构与计算边界](https://0xf3cd.github.io/ziwei/docs/architecture.html)
- [知识组织与来源](https://0xf3cd.github.io/ziwei/docs/knowledge.html)
- [参与开发](https://0xf3cd.github.io/ziwei/docs/contributing.html)

也可独立查知识：无需出生资料或先排盘，就能查到星曜、宫位、四化等概念，
以及安星规则的流派变体与出处。来源核验状态、适用前提与展示资格分别记录。

通用概念用惯用英语，术数专有词用拼音，枚举另有中文别名；文档、issue 与 PR 使用中文。

## 后续方向

- [杂曜、运限与展示](https://github.com/0xf3cd/ziwei/milestone/2)：杂曜、庙旺利陷、小限与流年流月、
  飞星四化、格局识别、盘面展示。
- [解释知识与研究](https://github.com/0xf3cd/ziwei/milestone/3)：有出处的解释知识与前提判别、
  1972 年前的历史时刻、多源排盘比对、与八字的联合入口。

这些 milestone 记录方向，不设发布日期。每项技术在实现前须明确定义、出处与参考盘例。

## 许可证

[MIT](https://github.com/0xf3cd/ziwei/blob/main/LICENSE)。
