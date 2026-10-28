# 完整命盘与盘面

[项目入口](../README.md) · [解析层](resolver.md) · [API](api.md#完整命盘与显示)

在线文档随`main`更新，不固定于某次发行；查阅时请核对安装版本。

`create_chart()`接收原始出生记录和显式口径，先解析，再用同一份计算输入组合十二宫、身宫标记、五行局、30星、生年四化和十二个大限。
时辰与性别必须已知；三个口径须显式选择，四化表另由具名参数选择。请求无法完成时整次失败，
不返回缺星或缺限的部分盘。各组件的规则和来源仍归[安星](stars.md)、[四化与大限](sihua-decades.md)。

## 排盘与显示

下面与README使用同一个合成输入：2024年农历正月初一子时女命。
三个口径分别指定闰月归属、子时换日与换年界线；天马采用默认的年支天马。
以下示例由当前文档的doctest执行，输出由本实现生成，不是外部参考盘。

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
>>> print(render_text(chart), end="")
火六局 · 大限逆行 · 虚岁首尾包含
+------------------+------------------+------------------+------------------+
| 田宅 己巳        | 官禄 庚午        | 奴仆 辛未        | 迁移 壬申        |
| 武曲[科]         | 太阳[忌]         | 天府             | 天机             |
| 破军[权]         | 大限 86-95虚岁   | 天钺             | 太阴             |
| 天喜             |                  | 大限 76-85虚岁   | 大限 66-75虚岁   |
| 大限 96-105虚岁  |                  |                  |                  |
+------------------+------------------+------------------+------------------+
| 福德 戊辰        |                  |                  | 疾厄 癸酉        |
| 天同             |                  |                  | 紫微             |
| 左辅             |                  |                  | 贪狼             |
| 文曲             |                  |                  | 大限 56-65虚岁   |
| 大限 106-115虚岁 |                  |                  |                  |
+------------------+------------------+------------------+------------------+
| 父母 丁卯        |                  |                  | 财帛 甲戌        |
| 擎羊             |                  |                  | 巨门             |
| 大限 116-125虚岁 |                  |                  | 右弼             |
|                  |                  |                  | 文昌             |
|                  |                  |                  | 铃星             |
|                  |                  |                  | 大限 46-55虚岁   |
+------------------+------------------+------------------+------------------+
| 命宫 丙寅 身宫   | 兄弟 丁丑        | 妻妾 丙子        | 子女 乙亥        |
| 火星             | 廉贞[禄]         | 天梁             | 天相             |
| 禄存             | 七杀             | 大限 26-35虚岁   | 地空             |
| 天马             | 天魁             |                  | 地劫             |
| 大限 6-15虚岁    | 陀罗             |                  | 红鸾             |
|                  | 大限 16-25虚岁   |                  | 大限 36-45虚岁   |
+------------------+------------------+------------------+------------------+
```

`ZiweiChart`冻结保存计算输入和各组件；传入的序列复制为元组。十二宫按宫名序保存，
星位按`Star`枚举顺序保存，大限按起限先后（自命宫起，随顺逆）保存；每颗星有一个位置，不同星可以同宫。
身宫是叠宫标记，不是第十三宫。公开构造器凭当前规则表和算术核对宫位、星位、四化与大限等组件关系，
不读取历法和时区数据，也不重新执行历法或时区解析。

直接构造`ZiweiChart`和调用`create_chart()`都拒绝未知时辰或性别。`Palace`自身的类型与干支配对由它的构造器检查；
完整盘仍检查每个序列的成员类型，以及全部组件是否对应同一份计算输入。
组件内容不符抛`ValueError`：十二宫、星位和大限报告数量差异或首个错项的零起始下标及期望／实际值；
身宫、五行局和四化也报告对应组件及期望／实际值。错类型抛`TypeError`，不会统一包装成通用错误。

文本盘面是四乘四边框的十二宫格，中间四格留空；上边依次巳午未申，下边依次寅丑子亥。
每宫列出宫名、宫干支、身宫标记、所有星曜、禄权科忌和大限虚岁。显示不改变计算结果；
首行给出五行局、大限顺逆与岁数约定；“虚岁首尾包含”指例如6至15岁包含两端，共十年。
文本盘面不作吉凶解释。等宽终端按东亚宽字符两列对齐，比例字体或不同终端宽度规则可能影响对齐。
盘面不输出地点、来源等任意文本，所以它们携带的控制字符不会成为终端指令。

## 读取与显示亮度

开发中的0.3.0提供一套[十四主星七级亮度表](brightness.md)。从已有盘读取，不给命盘增加字段，
也不改变安星结果；表须显式选择：

```{doctest}
>>> from ziwei.brightness import BrightnessTable
>>> from ziwei.chart import chart_brightness
>>> table = BrightnessTable.全书卷二录文
>>> readings = chart_brightness(chart, table=table)
>>> len(readings), sum(item.level is not None for item in readings)
(30, 14)
>>> text = render_text(chart, brightness_table=table)
>>> print(text.splitlines()[0])
火六局 · 大限逆行 · 虚岁首尾包含 · 全书卷二固定录文
>>> "廉贞[禄] (利益)" in text
True
>>> from ziwei.render import render_svg
>>> bright_svg = render_svg(chart, brightness_table=table)
>>> "全书卷二固定录文" in bright_svg
True
```

读数顺序与`chart.stars`相同：14颗主星有等级，其余16颗星的`level`为`None`，表示不适用。
按宫查询仍返回原来的星位，可逐条调用`star_brightness()`，不借入对宫星。
文本首行与SVG中央标明表名；SVG把等级放在星名下一行，并增加行距，避免与四化标记叠字。
两种显示省略`brightness_table`或传`None`时都不查询亮度，保留原有输出。
错类型抛`TypeError`，不接受表名字符串或静默换表。

## 按宫读取

v0.2.0新增`palace_view()`，从已有`ZiweiChart`读取一宫的结构化内容。
宫名是相对命宫的“田宅”等名称，地支是“巳”等固定位置；二者查询同一宫时返回相同结果。
下面继续读取上例，不重新排盘：

```{doctest}
>>> from ziwei.chart import palace_view
>>> from ziwei.palaces import PalaceName
>>> view = palace_view(chart, PalaceName.田宅)
>>> view.palace.name.value, str(view.palace.ganzhi)
('田宅', '己巳')
>>> tuple(position.star.value for position in view.stars)
('武曲', '破军', '天喜')
>>> view.quan.value, view.ke.value
('破军', '武曲')
>>> view == palace_view(chart, Dizhi.巳)
True
>>> palace_view(chart, PalaceName.命宫).is_shengong
True
```

返回的`PalaceView`不可变：`palace`保留宫名、地支与宫干，`stars`保留原盘顺序的星位及规则标识；
`lu`、`quan`、`ke`、`ji`分别是本宫中带生年禄、权、科、忌的星曜，不在本宫时为`None`。
`is_shengong`表示身宫叠在本宫。这里只读取原盘的生年四化，不按宫干另算飞化。
空宫的`stars`为空元组、四化全为`None`，不借入对宫星曜；星集只涉及当前已实现星曜。

查询只接受`ZiweiChart`与`PalaceName`或`Dizhi`成员，合法中文别名等同原成员，其他类型抛`TypeError`。
它不修改原盘，不重新解析出生记录或访问历法、时区资源。
直接构造的检查范围见[API中的PalaceView](api.md#完整命盘与显示)，不认证它来自某张完整命盘。
宫位间的对宫／三方四正查询见[宫位关系](palaces.md#对宫与三方四正)。

## 静态SVG

v0.2.0新增`render_svg()`，把已有命盘画成静态SVG。
它从已有命盘生成SVG字符串，不重新排盘。下面继续用上例，突出命宫的三方四正：

```{doctest}
>>> from ziwei.render import render_svg
>>> from ziwei.palaces import PalaceName
>>> svg = render_svg(chart, selected_palace=PalaceName.命宫)
```

用UTF-8保存后，可在浏览器中打开：

```python
from pathlib import Path

Path("chart.svg").write_text(svg, encoding="utf-8")
```

SVG沿用外围十二宫布局，显示宫名、干支、现有30星、生年四化、身宫标记与大限虚岁。
星曜按原盘顺序从左到右、从上到下排列。所有宫格等高，高度由星数最多的一宫决定。
空宫保留宫位信息，不借入对宫星曜。
中央给出五行局、大限方向与岁数约定。选宫时以文字和边框配合颜色区分本宫、两个三合宫和对宫，
不加入飞化或吉凶解释。

`selected_palace`接受`PalaceName`或`Dizhi`成员；指向同一宫时输出相同。
省略或传`None`时不高亮；字符串（如`"命宫"`、`"子"`）、整数等其他类型抛`TypeError`。
这是静态图，不支持点击换宫；要看另一宫，重新调用时更换参数。

返回内容自带样式，不含脚本、外部资源或字体文件；查看SVG的设备须装有中文字体，否则文字可能无法正确显示。
需要放大或缩小时，使用查看器的缩放功能。
它不输出原始生日、地点、来源等任意出生元数据，但盘面内容本身仍可能具有识别性，分享前请检查。
图上不印软件版本，独立SVG不承诺版本溯源，也不是可恢复命盘的存档。

## 计算输入与来源信息

`chart.calculation`保留原始出生记录、口径、解析后的农历年月日时与干支纪年，以及此次使用的农历算法和celestial版本。
构造`CalculationInput`时，`supported_lunar_year_range`从所选算法取得，结果保存这次支持范围，不接受调用方传入范围。
星位、四化与大限保留各自的规则标识；规则的定义与来源见所属领域模块和知识目录。

公历且选择立春或提供经度时，`calculation.resolved_time`保存此次取得的本地钟面、UTC、
整数微秒偏移、实际fold，以及IANA数据包版本和发布版本。fold的选择与适用条件见[出生输入](birth.md)。
固定偏移没有IANA数据版本。
其他路径为`None`，包括本页农历合成例和1954参考例所用的纯民用路径。民用时刻解析只支持1972年起的UTC；
纯民用路径只按记录的日期与钟面标签排盘，不取瞬间，因此不受这个时标边界限制；具体顺序见[解析层](resolver.md)。
请求的fold留在原记录中，实际fold另存，两者不互相替代。
纯民用路径不消歧，不检查钟点是否落在夏令时间隙或请求的fold是否适用于该钟点；原请求值原样保存。
例如不存在的当地钟点也可按记录标签排盘，这不表示已确认钟点真实存在；此时没有实际fold或UTC可供读取。

直接构造`ZiweiChart`不重做公农历、UT1或IANA偏移换算；它会核对已存解析值与原始记录的内部一致性，
但不证明这些原值正确。从原始记录排盘应调用`create_chart()`。
当前源码不提供命盘保存、恢复或旧盘重算接口，也不读取v0.1.0的JSON命盘；不保留替代格式或迁移入口。

## 参考盘例与验收限度

| 证据 | 能检验什么 | 不能推出什么 |
|---|---|---|
| 1954外部例：`tests/conftest.py`、`tests/test_chart.py` | 同例公历/农历入口、命身宫、十二宫干支、火六局、28星与甲干四化 | 不是全部口径的独立原盘；年马/月马在此例相同 |
| 甲子年正月初一子时女命的手推合成例 | 命身宫、五行局、十四主星、大限逆行与年马 | 不是外部原盘或完整流派认证 |
| 癸卯年闰二月十五／十六子时女命的手推合成例 | 三种闰月口径的命身宫、局数、紫微辅弼及首限 | 不是外部原盘；不以共享实现之间互比代替手推期望 |
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

隔离安装验收使用由sdist重建的wheel，普通与优化模式均执行真实记录排盘、文本与SVG输出，
并核对独立星位和大限标签。它证明安装后的消费路径已执行，不代替跨平台CI或独立来源验证。
