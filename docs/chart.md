# 完整命盘与文本盘面

[项目入口](../README.md) · [解析层](resolver.md) · [API](api.md#完整命盘与显示)

`create_chart()`接收原始出生记录和显式口径，先解析，再用同一份计算输入组合十二宫、身宫标记、五行局、28星、生年四化和十二限。
时辰与性别必须已知；三个口径须显式选择，四化表另由具名参数选择。请求无法完成时整次失败，
不返回缺星或缺限的部分盘。各组件的规则和来源仍归[安星](stars.md)、[四化与大限](sihua-decades.md)。

## 排盘与显示

下面使用匿名例甲：论坛转录《排命盘口诀》的1954年农历九月初七子时男命。
原著与纸本底本未核，来源与覆盖限度见本页末节。

```{doctest}
>>> from ziwei.birth import Gender, LunarBirthRecord
>>> from ziwei.config import ChartConfig, LeapMonthPolicy, DayRollover, YearBoundary, TianmaRule
>>> from ziwei.ganzhi import Dizhi
>>> from ziwei.chart import create_chart
>>> from ziwei.sihua import SihuaVariant
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
>>> render_text(chart).splitlines()[0]
'火六局 · 大限顺行 · 虚岁首尾包含'
>>> '命宫 甲戌 身宫' in render_text(chart)
True
```

`ZiweiChart`冻结保存计算输入和各组件；传入的序列复制为元组。十二宫按宫名序保存，
星位按`Star`枚举顺序保存，大限按起限先后（自命宫起，随顺逆）保存；每颗星有一个位置，不同星可以同宫。
身宫是叠宫标记，不是第十三宫。公开构造器按当前规则核对组件关系，不重新执行历法或时区解析。
这里的“纯规则”指不读取历法和时区数据、只凭表和算术即可核对的部分，如宫位、星位、四化与大限。

文本盘面是四乘四边框的十二宫格，中间四格留空；上边依次巳午未申，下边依次寅丑子亥。
每宫列出宫名、宫干支、身宫标记、所有星曜、禄权科忌和大限虚岁。显示不改变计算结果；
首行给出五行局、大限顺逆与岁数约定；“虚岁首尾包含”指例如6至15岁包含两端，共十年。
没有吉凶解释或图形绘制。等宽终端按东亚宽字符两列对齐，比例字体或不同终端宽度规则可能影响对齐。
盘面不输出地点、来源等任意文本，所以它们携带的控制字符不会成为终端指令。

## 计算输入与来源信息

`chart.calculation`保留原始出生记录、口径、解析后的农历年月日时与干支纪年，以及此次使用的农历算法和celestial版本。
构造`CalculationInput`时，`supported_lunar_year_range`从所选算法取得，结果保存这次支持范围，不接受调用方传入范围。
星位、四化与大限保留各自的规则标识；规则的定义与来源见所属领域模块和知识目录。

公历且选择立春或提供经度时，`calculation.resolved_time`保存此次取得的本地钟面、UTC、
整数微秒偏移、实际fold，以及IANA数据包版本和发布版本。固定偏移没有IANA数据版本。
其他路径为`None`，包括1954例所用的纯民用路径。民用时刻解析只支持1972年起的UTC；
纯民用路径不取瞬间，因此不受这个时标边界限制。
请求的fold留在原记录中，实际fold另存，两者不互相替代。
纯民用路径不消歧，不检查钟点是否落在夏令时间隙或请求的fold是否适用于该钟点；原请求值原样保存。

直接构造`ZiweiChart`不会重新核验公历／农历对应、UT1来源或IANA偏移；从原始记录排盘应调用`create_chart()`。
当前源码不提供命盘保存、恢复或旧盘重算接口，也不读取v0.1.0的JSON命盘；不保留替代格式或迁移入口。

## 参考盘例与验收限度

| 证据 | 能检验什么 | 不能推出什么 |
|---|---|---|
| 1954外部例：`tests/conftest.py`、`tests/test_chart.py` | 同例公历/农历入口、命身宫、十二宫干支、火六局、28星与甲干四化 | 不是全部口径的独立原盘；年马/月马在此例相同 |
| 甲子年正月初一子时女命的手推合成例 | 命身宫、五行局、十四主星、大限逆行与年马 | 不是外部原盘或完整流派认证 |
| 合成闰月、子时、立春相邻秒、支持范围端点、真太阳时跨日 | 同一计算输入贯穿各组件，拒绝不支持组合 | 不代替独立原盘的数值验证 |
| HKO分钟立春与逐日农历表、独立均时差近似和手推合成例 | 两种换年／子时口径下的日期、时辰及受影响组件 | 不认证秒级立春、全域太阳时精度或完整流派 |

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

隔离安装验收使用由sdist重建的wheel，普通与优化模式均执行真实记录排盘、文本输出，
并核对独立星位和大限标签。它证明安装后的消费路径已执行，不代替跨平台CI或独立来源验证。
