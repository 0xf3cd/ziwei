# 完整命盘与记录

[项目入口](../README.md) · [解析层](resolver.md) · [API](api.md#完整命盘记录与显示)

`create_chart()`接收原始出生记录和显式口径，先解析，再用同一份计算输入组合十二宫、身宫标记、五行局、28星、生年四化和十二限。
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
'火六局 · 大限顺行 · 虚岁首尾包含'
>>> '命宫 甲戌 身宫' in render_text(restored)
True
```

`ZiweiChart`冻结保存计算输入和各组件；传入的序列复制为元组。十二宫按宫名序保存，
星位按已发布规则组的顺序保存，大限按起限先后（自命宫起，随顺逆）保存；每颗星有一个位置，不同星可以同宫。
身宫是叠宫标记，不是第十三宫。公开构造器按盘已有的完整星集核对纯规则，不随以后默认全集扩大。
这里的“纯规则”指不读取历法和时区数据、只凭表和算术即可核对的部分，如宫位、星位、四化与大限。

文本盘面是四乘四边框的十二宫格，中间四格留空；上边依次巳午未申，下边依次寅丑子亥。
每宫列出宫名、宫干支、身宫标记、所有星曜、禄权科忌和大限虚岁。显示不改变计算结果；
首行给出五行局、大限顺逆与岁数约定；“虚岁首尾包含”指例如6至15岁包含两端，共十年。
没有吉凶解释或图形绘制。等宽终端按东亚宽字符两列对齐，比例字体或不同终端宽度规则可能影响对齐。
盘面不输出地点、来源等任意文本，所以它们携带的控制字符不会成为终端指令。

## JSON schema与版本

`dumps_chart()`返回字符串，调用方自行决定存入文件或数据库；`loads_chart()`只收严格的`str`实例（不接受子类），
不把字符串当URL、路径或代码执行。v0.2 继续读取 v0.1 的 schema 1，不补新星、不重新排盘。
目前写入仍为`SCHEMA_VERSION=1`，没有格式变化，不提供空迁移函数。

| 顶层字段 | 内容 |
|---|---|
| `schema_version` | JSON格式版本，整数；不是软件版本 |
| `software_version` | 生成时已安装的ziwei分发版本，参与完整记录相等，不作为重算兼容条件 |
| `record` | 公历或农历原始记录；时区请求、记录精度、性别、经度、地点与来源 |
| `calculation` | 已解析农历年月日时、闰月标志、干支纪年、口径与天马查法、农历算法及celestial版本、支持范围、真太阳时路径与晚子时顺延标志、UT1原值和已解析时刻 |
| `palaces`、`shengong`、`bureau` | 十二宫、身宫与五行局 |
| `stars`、`sihua`、`decades` | 星位与规则标识、具名四化表及结果、大限及规则标识和年龄约定 |

嵌套字段的键名、类型、单位、可空性及演进办法见 [schema 1 字段参考](record-format.md)。
领域枚举值用中文，规则标识沿用所属模块的稳定标识。支持范围在生成时从历法适配取一次，
由计算输入保存快照；恢复和再次保存不读当前范围替换它。这份范围声明不认证历史来源真实性。
生成软件版本不代表安星表的历史版本；它随恢复保全并参与`==`，但不是重算兼容条件。

公历且选择立春或提供经度时，`calculation.resolved_time`保存此次取得的本地钟面、UTC、
整数微秒偏移、实际fold，以及IANA数据包版本和发布版本。固定偏移没有IANA数据版本。
其他路径为`null`，包括1954例所用的纯民用路径。民用时刻解析只支持1972年起的UTC；
纯民用路径不取瞬间，因此不受这个时标边界限制。
请求的fold留在原记录中，实际fold另存，两者不互相替代。
纯民用路径不消歧，不检查钟点是否落在夏令时间隙或请求的fold是否适用于该钟点；原请求值原样保存。

有限浮点按Python JSON往返保留；经度的116与116.0、0.0与-0.0保持原样，不合并。
偏移不用浮点秒。字符使用ASCII转义，包括控制字符和孤立代理字符；保存文本里的中文也是`\uXXXX`形式，解析后读取中文值。
出生记录的地点与来源拒绝相邻的高→低代理码点对（如 Python 字符串 `"\ud800\udc00"`），
因为 JSON 解码会把它合成一个补充平面字符。孤立高代理、孤立低代理、低→高代理、实际补充平面字符、
中文和控制字符仍可保全；字段原有的格式限制不变。保存和恢复对所有字符串检查同一字符边界，
不能只靠再次保存文本相等来证明原对象值没变。
v0.1 已把两个码点编码成同一 JSON 转义的文件，只能按其中已存字符恢复，不能猜回编码前的原字符串。
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
schema 1 固定已发布的 28 星顺序和组件；即使以后默认安星扩大，旧盘仍只恢复这 28 星。
缺星、多星、重复、乱序或规则矛盾仍拒绝。旧规则标识的含义不能被原地改写；
这不等于承诺装载任意外部历史四化表或安星规则。
范围快照只检查两个严格整数、1–9999、有序且包含记录农历年；例如 `[1,9999]` 可以是合法元数据，
但不表示当前算法真的支持这个范围。当前能力留给重算检查。

`recalculate()`先匹配所需celestial版本；有已解析IANA时刻时还须匹配两种tzdata版本。
同时检查当前算法范围仍包含原日期，再用原始记录、口径、算法、四化变体和原星集重新计算，逐组件比较。
版本、当前范围或所需IANA时区不可用、结果不同均抛`ValueError`，
不覆盖原盘、不下载旧算法，也不静默用新版本冒充复现。纯民用盘和固定偏移盘不强加tzdata版本匹配。
成功时返回此次计算的盘，生成软件版本及范围快照可与旧盘不同；不把范围元数据变化本身当成计算差异，
也不覆盖原盘的快照。旧日期落到当前范围之外时，仍可恢复，但不能重算。

`loads_chart()`先识别整数 schema，再查该版字段。未知整数版本抛
`UnsupportedSchemaVersionError`（`ValueError` 子类），`schema_version` 属性保存请求版本；
即使载荷同时新增字段也按版本问题报告。已支持版本的内容／格式错误仍抛其他 `ValueError`，
保留原因链，非严格`str`实例抛`TypeError`。
库不限制JSON输入体积或数组长度；接收不可信请求的服务须在调用前自行限制载荷大小与资源用量。
所有公开校验在`python -O`下仍执行。JSON数据仍需调用方按自己的存储与隐私要求妥善保管。

## 参考盘例与验收限度

| 证据 | 能检验什么 | 不能推出什么 |
|---|---|---|
| 1954外部例：`tests/conftest.py`、`tests/test_chart.py` | 同例公历/农历入口、命身宫、十二宫干支、火六局、28星与甲干四化 | 不是全部口径的独立原盘；年马/月马在此例相同 |
| 甲子年正月初一子时女命的手推合成例 | 命身宫、五行局、十四主星、大限逆行与年马 | 不是外部原盘或完整流派认证 |
| 合成闰月、子时、立春相邻秒、支持范围端点、真太阳时跨日 | 同一计算输入贯穿各组件，拒绝不支持组合 | 不代替独立原盘的数值验证 |
| HKO分钟立春与逐日农历表、独立均时差近似和手推合成例 | 两种换年／子时口径下的日期、时辰及受影响组件 | 不认证秒级立春、全域太阳时精度或完整流派 |
| JSON逐字段往返、阻断原生导入、版本/内容破坏用例 | 保存保真、恢复不求值、重算差异和失败边界 | 不证明排盘计算本身正确 |

1954例取自[2007论坛转录《排命盘口诀》](http://www.zhongyi999.com.cn/thread-1744-1-1.html)
末段“排命盘举例”第1至13步；页面明确写公历1954-10-03 00:00及农历九月初七子时，原著与底本未核。
原文没有时区，公历测试显式用固定+08:00，且走不依赖UTC的纯民用路径；两入口仍只算同一个独立命例。
第22步正文列前九限，从戌宫6至15岁起，到午宫86至95岁止；
末三限未宫96至105岁、申宫106至115岁、酉宫116至125岁按同页规则推得。
表23图像未核，不能称十二限均为原图转录。当前没有立春或真太阳时的独立完整原盘。
1970庚戌图只用于[庚干四化参考](sihua-decades.md)，不算完整命例。
若用左辅反推生月、文昌反推时辰、紫微反推生日，农历生日仍有初六、十一、二十一三个候选；
反推所用的左辅、文昌、紫微星位不能再算作独立验证。

`tests/test_external_time_cases.py`的合成取证分开使用外部时间资料与手推规则：

- [HKO 2024节气分钟表](https://www.hko.gov.hk/en/gts/astronomy/data/files/24SolarTerms_2024.xml)
  给立春02/04 16:27香港时间，时区依据见[节气说明](https://www.hko.gov.hk/en/gts/astronomy/Solar_Term.htm)。
  立春时刻对照测试以60秒为容差，比较库内立春时刻与HKO分钟值，不认证秒级精度。
- 换年合成例取02/04 16:20和16:35，均为申时，分别在上述分钟值前7分钟、后8分钟，间隔均大于60秒容差。
  HKO[逐日表](https://www.hko.gov.hk/en/gts/time/calendar/text/files/T2024e.txt)给当日腊月廿五、02/10正月初一。
  两时刻都早于02/10，故正月初一口径均为癸卯，立春口径后者为甲辰。
- 2024-11-03 00:20+08、100°E对应11/02 16:20 UTC，平太阳钟为11/02 23:00。
  [pvlib校正Spencer71式](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.solarposition.equation_of_time_spencer71.html)
  独立估得均时差约+980.765秒，太阳钟约11/02 23:16:20.765；只对此例用60秒对照窗口。
  日序约定为`doy_in = yday + (hour + minute/60 + second/3600 - 12)/24`（UTC），
  日角`2π(doy_in−1)/365`，常数项`0.0000075`，闰年也用365。该式是经验近似，不承诺全域精度。
  HKO逐日表给11/02十月初二、11/03初三，配合两种子时口径分别手推紫微午／亥。

这些是有独立时间锚的合成例，非人工原盘；原始口诀和取用范围仍见各领域知识条目。

隔离安装验收使用由sdist重建的wheel，普通与优化模式均执行真实记录排盘、保存、恢复、重算、
文本输出和错误schema拒绝。它证明安装后的消费路径已执行，不代替跨平台CI或独立来源验证。
