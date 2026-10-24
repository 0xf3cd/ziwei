# ziwei

Python 紫微斗数排盘与知识库。历法与时间由
[celestial-calendar](https://github.com/0xf3cd/celestial-calendar) 提供；本仓记录紫微斗数的安星规则、
四化口径、流派变体与出处，并组织可复现的命盘结果。

目前提供出生记录、显式口径配置、民用时刻消歧、干支基础、celestial 历法适配、解析层
（公历/农历记录到计算输入）、命宫身宫与十二宫、五行局、28星安星、具名生年四化与大限，
以及完整命盘组合、文本十二宫格和独立知识目录。
用法见[出生输入](docs/birth.md)、[历法与时间](docs/calendar.md)、[解析层](docs/resolver.md)、
[命宫身宫与十二宫](docs/palaces.md)、[五行局](docs/bureau.md)、[安星](docs/stars.md)、
[四化与大限](docs/sihua-decades.md)、[完整命盘与文本盘面](docs/chart.md)和[知识查询](docs/knowledge.md)，
开发检查与协作约定见[参与开发](docs/contributing.md)。
首次发布的前置配置、审批与产物核验见[发布准备](docs/releasing.md)。

当前源码为开发版本；已发布版本以
[发布记录](https://github.com/0xf3cd/ziwei/releases)为准。
与v0.1.0相比，开发源码不再提供命盘JSON保存／恢复与旧盘重算接口，也不读取旧JSON命盘。
已发布的v0.1.0及其制品不变。

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
当前源代码开发安装与检查见[参与开发](docs/contributing.md)，版本与首次发布仍以发布记录为准。

## 首版目标

已知出生时刻与性别，排出可复现的本命盘：

- 保存出生原始记录，显式处理时区与可选的真太阳时，保留解析后的农历年月日时与所用历法算法。
- 闰月归属、子时换日、换年三个口径作为具名配置，不设静默默认。
- 安命宫、身宫与十二宫宫干，定五行局，安紫微、天府两系十四主星。
- 安六吉、六煞、禄存与天马；按所选具名四化表取生年四化。
- 起大限：顺逆由年干阴阳与性别定，首限起始虚岁由五行局数定。
- 输出不可变结构与文本盘面，保留输入、口径、历法版本与派生结果。

交付任务与验收见 [v0.1.0 milestone](https://github.com/0xf3cd/ziwei/milestone/1)。

## 设计边界

- [仓库结构与计算边界](docs/architecture.md)
- [知识组织与来源](docs/knowledge.md)
- [参与开发](docs/contributing.md)

首版同时支持独立查知识：不排盘、不加载原生历法库，也能查到星曜、宫位、四化等概念，
以及安星规则的流派变体与出处。来源核验状态、适用前提与展示资格分别记录。

通用概念用惯用英语，术数专有词用拼音，枚举另有中文别名；文档、issue 与 PR 使用中文。

## 后续方向

- [杂曜、运限与展示](https://github.com/0xf3cd/ziwei/milestone/2)：杂曜、庙旺利陷、小限与流年流月、
  飞星四化、格局识别、盘面展示。
- [解释知识与研究](https://github.com/0xf3cd/ziwei/milestone/3)：有出处的解释知识与前提判别、
  1972 年前的历史时刻、多源排盘比对、与八字的联合入口。

这些 milestone 记录方向，不设发布日期。每项技术在实现前须明确定义、出处与参考盘例。

## 许可证

[MIT](LICENSE)。
