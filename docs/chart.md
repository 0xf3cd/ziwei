# 完整命盘与记录

[项目入口](../README.md) · [解析层](resolver.md) · [API](api.md#完整命盘记录与显示)

`create_chart()`把同一份解析结果组合为十二宫、身宫标记、五行局、28星、生年四化和十二限。
时辰与性别必须已知；三个口径须显式选择，四化表另由具名参数选择。请求无法完成时整次失败，
不返回缺星或缺限的部分盘。各组件的规则和来源仍归[安星](stars.md)、[四化与大限](sihua-decades.md)。

## 排盘、保存与显示

下面使用匿名例甲：论坛转录《排命盘口诀》的1954年农历九月初七子时男命。
原著与纸本底本未核，来源与覆盖限度见本页末节。

```{doctest}
>>> from ziwei.birth import Gender, LunarBirthRecord
>>> from ziwei.config import ChartConfig, LeapMonthPolicy, DayRollover, YearBoundary, TianmaRule
>>> from ziwei.ganzhi import Dizhi
>>> from ziwei.chart import create_chart, recalculate
>>> from ziwei.sihua import SihuaVariant
>>> from ziwei.serialization import dumps_chart, loads_chart
>>> from ziwei.render import render_text
>>> record = LunarBirthRecord(
...   year=1954, month=9, day=7, is_leap_month=False, shichen=Dizhi.子, gender=Gender.男,
...   source="匿名例甲：论坛转录《排命盘口诀》",
... )
>>> choices = ChartConfig(
...   leap_month_policy=LeapMonthPolicy.全月归本月,
...   day_rollover=DayRollover.早晚子时同日,
...   year_boundary=YearBoundary.农历正月初一,
...   tianma_rule=TianmaRule.月支天马,
... )
>>> chart = create_chart(record, choices, sihua_variant=SihuaVariant.排命盘口诀转录)
>>> chart.bureau.value, str(chart.palaces[0].ganzhi), chart.shengong.value
('火六局', '甲戌', '戌')
>>> len(chart.palaces), len(chart.stars), len(chart.decades)
(12, 28, 12)
>>> saved = dumps_chart(chart)
>>> restored = loads_chart(saved)
>>> restored == chart and dumps_chart(restored) == saved
True
>>> recalculate(restored) == chart
True
>>> render_text(restored).splitlines()[0]
'火六局 · 大限顺行 · 首尾包含'
>>> '命宫 甲戌 身宫' in render_text(restored)
True
```

`ZiweiChart`冻结保存计算输入和各组件；传入的序列复制为元组。十二宫按宫名序保存，
星位按`Star`枚举序保存，大限按行限序保存；每颗星有一个位置，不同星可以同宫。
身宫是叠宫标记，不是第十三宫。公开构造器会核对组件与计算输入是否符合当前纯规则。

文本盘面是四乘四边框的十二宫格，中间四格留空；上边依次巳午未申，下边依次寅丑子亥。
每宫列出宫名、宫干支、身宫标记、所有星曜、禄权科忌和大限虚岁。显示不改变计算结果；
没有吉凶解释或图形绘制。等宽终端按东亚宽字符两列对齐，比例字体或不同终端宽度规则可能影响对齐。
盘面不输出地点、来源等任意文本，所以它们携带的控制字符不会成为终端指令。

## JSON schema与版本

`dumps_chart()`返回字符串，调用方自行决定存入文件或数据库；`loads_chart()`只收JSON字符串，
不把字符串当URL、路径或代码执行。目前仅支持`SCHEMA_VERSION`指定的schema，不迁移未知版本。

| 顶层字段 | 内容 |
|---|---|
| `schema_version` | JSON格式版本，整数；不是软件版本 |
| `software_version` | 生成时已安装的ziwei分发版本，只作说明 |
| `record` | 公历或农历原始记录；时区请求、记录精度、性别、经度、地点与来源 |
| `calculation` | 已解析农历年月日时、闰月标志、干支纪年、口径与天马查法、农历算法及celestial版本、支持范围、路径标志、UT1原值和已解析时刻 |
| `palaces`、`shengong`、`bureau` | 十二宫、身宫与五行局 |
| `stars`、`sihua`、`decades` | 星位与规则标识、具名四化表及结果、大限及规则标识和年龄约定 |

领域枚举值用中文，规则标识沿用所属模块的稳定标识。支持范围从历法适配定义生成，
不另存一份可执行算法。生成软件版本不代表安星表的历史版本，也不参与恢复或重算的数值比对。

公历且选择立春或提供经度时，`calculation.resolved_time`保存此次取得的本地钟面、UTC、
整数微秒偏移、实际fold，以及IANA数据包版本和发布版本。固定偏移没有IANA数据版本。
其他路径为`null`，包括1954例所用的纯民用路径；不会为补齐元数据而额外解析1972年前的UTC。
请求的fold留在原记录中，实际fold另存，两者不互相替代。

有限浮点按Python JSON往返保留；经度的整数/浮点类型与浮点负零不强制归一。
偏移不用浮点秒。字符使用ASCII转义，包括控制字符和孤立代理字符；记录中的说明文字不被改写。
恢复不会重建调用方自定义的Python字符串或数值子类身份。

## 恢复与重算各保证什么

**恢复保全已存结果，但不认证历法真实性。** `loads_chart()`不调用出生解析器，不加载celestial，
也不读取tzdata。它拒绝重复键、缺/多字段、错类型、非有限数值、未知schema、未知规则，
以及宫位、星位、四化、大限与已存计算输入的纯规则矛盾。序列顺序不符也拒绝，不静默重排。

恢复可检查钟面减UTC等于偏移、fold与数据字段的结构、立春比较与干支纪年的代数关系，
却不能证明这些原值正确。以下留给重算核对：

- 公历日与已存农历年月日是否对应，月和闰月组合是否真实存在。
- `ut1_jd`是否由已存UTC正确换算，`lichun_jd`是否确为该年的立春原值。
- IANA时区的偏移与fold是否符合所标版本的数据。

恢复允许celestial或tzdata的已存版本与当前不同，因为没有重新求值；
当前代码内的纯安星规则仍须能表示该记录，否则明确失败。schema首版不承诺装载任意历史四化表或安星规则。

`recalculate()`先匹配所需celestial版本；有已解析IANA时刻时还须匹配两种tzdata版本。
然后用原始记录、口径、算法和四化变体重新计算，逐组件比较。版本不可用或结果不同抛`ValueError`，
不覆盖原盘、不下载旧算法，也不静默用新版本冒充复现。纯民用盘和固定偏移盘不强加tzdata版本匹配。
成功时返回此次计算的盘，生成软件版本可与旧盘不同。

`loads_chart()`对内容/格式错误统一抛`ValueError`，非字符串参数抛`TypeError`。
所有公开校验在`python -O`下仍执行。JSON数据仍需调用方按自己的存储与隐私要求妥善保管。

## 参考盘例与验收限度

| 证据 | 能检验什么 | 不能推出什么 |
|---|---|---|
| 1954外部例：`tests/conftest.py`、`tests/test_chart.py` | 同例公历/农历入口、命身宫、十二宫干支、火六局、28星与甲干四化 | 不是全部口径的独立原盘；年马/月马在此例相同 |
| 甲子年正月初一子时女命的手推合成例 | 命身宫、五行局、十四主星、大限逆行与年马 | 不是外部原盘或完整流派认证 |
| 合成闰月、子时、立春相邻秒、支持范围端点、真太阳时跨日 | 同一计算输入贯穿各组件，拒绝不支持组合 | 不代替独立原盘的数值验证 |
| JSON逐字段往返、阻断原生导入、版本/内容破坏用例 | 保存保真、恢复不求值、重算差异和失败边界 | 不证明排盘计算本身正确 |

1954例取自[2007论坛转录《排命盘口诀》](http://www.zhongyi999.com.cn/thread-1744-1-1.html)
末段“排命盘举例”第1至13步；页面明确写公历1954-10-03 00:00及农历九月初七子时，原著与底本未核。
原文没有时区，公历测试显式用固定+08:00，且走不依赖UTC的纯民用路径；两入口仍只算同一个独立命例。
大限逐限期望按同页规则推得，不能称原图逐限转录。当前没有立春或真太阳时的独立完整原盘。
1970庚戌图缺生日，只用于[四化参考](sihua-decades.md)，不算完整命例。

隔离安装验收使用由sdist重建的wheel，普通与优化模式均执行真实记录排盘、保存、恢复、重算、
文本输出和错误schema拒绝。它证明安装后的消费路径已执行，不代替跨平台CI或独立来源验证。
