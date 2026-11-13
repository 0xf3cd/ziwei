# API 参考

[出生输入用法](birth.md) · [项目入口](../README.md)

在线文档随`main`更新，不固定于某次发行；查阅时请核对安装版本。
[在线API正文](https://0xf3cd.github.io/ziwei/docs/api.html)包含生成后的签名与模块说明。
直接浏览Markdown源码不会展开下方指令；离线全文请按[构建文档](contributing.md#构建文档)生成HTML。

以下签名和说明从实现生成；模块按职责导入，不从包根初始化历法或时区数据。
枚举中的中文成员名是对应拼音或英语成员的别名，指向同一成员。
模块中的公开数据以显式 `TypeAlias`，或带变量说明的 `Final` 声明；下划线名字为内部实现。
其他未加下划线的赋值和导入不因此成为公开数据合同。API 检查要求每项公开数据声明都有对应的 HTML 签名；
页面可以同时包含枚举成员、数据字段等其他签名。
声明与签名检查的维护方式见[参与开发](contributing.md#维护api文档)。

从0.4.1起，下列模块中的公开对象也可从对应`doushu.*`路径导入，例如
`from doushu.chart import create_chart`、`from doushu.knowledge.model import Source`。
两个模块本身不同，其中的公开对象相同：

```python
import doushu.chart as alias_module
import ziwei.chart as original_module
from doushu.birth import LunarBirthRecord

assert alias_module is not original_module
assert alias_module.create_chart is original_module.create_chart
assert LunarBirthRecord.__module__ == "ziwei.birth"
```

从别名路径取得的`LunarBirthRecord`，repr与pickle也保持原样。包入口不会自动加载所有子模块。
`ziwei.knowledge.data`不在本页的公开模块列表中，不提供别名路径。

(chinese-domain-api)=
## 中文领域入口

下表的中文类型名与原名指向同一对象；中文结果属性读取原字段或property。构造关键字、函数名、
规则标识及知识查询方法仍用原名。下表中的模块都可将`ziwei.`换成`doushu.`。

| 模块 | 中文类型名 → 原类型名 |
|---|---|
| `birth` | `性别 → Gender`、`公历出生记录 → GregorianBirthRecord`、`农历出生记录 → LunarBirthRecord`、`出生记录 → BirthRecord`、`计算输入 → CalculationInput` |
| `config` | `闰月归属 → LeapMonthPolicy`、`子时换日 → DayRollover`、`换年界线 → YearBoundary`、`天马规则 → TianmaRule`、`命盘配置 → ChartConfig`、`口径选项 → PolicyOption` |
| `ganzhi` | `阴阳 → Yinyang`、`天干 → Tiangan`、`地支 → Dizhi`、`干支 → Ganzhi`、`五行 → Wuxing` |
| `palaces` | `宫名 → PalaceName`、`宫位 → Palace` |
| `bureau` | `五行局 → WuxingJu` |
| `stars` | `星曜 → Star`、`安星规则 → StarRule`、`星位 → StarPlacement` |
| `brightness` | `亮度等级 → BrightnessLevel`、`亮度表 → BrightnessTable`、`亮度读数 → BrightnessReading` |
| `sihua` | `四化变体 → SihuaVariant`、`四化表 → SihuaTable`、`四化结果 → SihuaResult` |
| `decades` | `行运方向 → Direction`、`大限 → Decade` |
| `liunian` | `流年星曜 → LiunianStars`、`流年年界 → LiunianBoundary`、`流年区间 → LiunianYear`、`流年四化 → LiunianSihua` |
| `xiaoxian` | `小限 → Xiaoxian` |
| `tongxian` | `童限边界 → TongxianBoundary`、`童限 → Tongxian` |
| `yunxian` | `运限 → Yunxian` |
| `chart` | `紫微命盘 → ZiweiChart`、`宫位视图 → PalaceView`、`流年叠读 → LiunianView`、`流年宫位 → LiunianPalaceView` |

### 只读属性

箭头左侧是中文读取名，右侧是原读取名。返回类型见下方各类的生成签名；例如宫位视图的四化可能为`None`，
完整四化结果中的四颗星则均有值。`纪年`是整数年份，`年干支`是`Ganzhi`对象，`农历年`是整数农历年份；
采用立春换年时，`纪年`与`农历年`可能不同。
年度`禄存`返回地支，`化禄`返回星曜，二者不能混用。

| 所属类型 | 中文属性 → 原属性 |
|---|---|
| `CalculationInput` | `原始记录 → record`、`农历年 → lunar_year`、`农历月 → month`、`农历日 → day`、`闰月 → is_leap_month`、`时辰 → shichen`、`纪年 → ganzhi_year`、`命盘配置 → config`、`性别 → gender`、`年干支 → year_ganzhi`、`年干阴阳 → yinyang` |
| `Tiangan` | `阴阳 → yinyang` |
| `Ganzhi` | `天干 → tiangan`、`地支 → dizhi` |
| `Palace` | `地支 → dizhi`、`天干 → tiangan`、`宫名 → name`、`干支 → ganzhi` |
| `WuxingJu` | `局数 → number` |
| `StarPlacement` | `星曜 → star`、`地支 → dizhi` |
| `BrightnessReading` | `星曜 → star`、`地支 → dizhi`、`亮度表 → table`、`等级 → level` |
| `SihuaResult` | `年干 → year_tiangan`、`变体 → variant`、`化禄 → lu`、`化权 → quan`、`化科 → ke`、`化忌 → ji` |
| `Decade` | `地支 → dizhi`、`行运方向 → direction`、`起始虚岁 → start_age`、`终止虚岁 → end_age` |
| `LiunianStars` | `纪年 → ganzhi_year`、`禄存 → lucun`、`擎羊 → qingyang`、`陀罗 → tuoluo`、`年干支 → year_ganzhi` |
| `LiunianYear` | `纪年 → ganzhi_year`、`年界 → boundary`、`起始日期 → start`、`终止日期 → end`、`年干支 → year_ganzhi`、`命宫 → minggong` |
| `LiunianSihua` | `纪年 → ganzhi_year`、`年干支 → year_ganzhi`、`年干 → year_tiangan`、`变体 → variant`、`化禄 → lu`、`化权 → quan`、`化科 → ke`、`化忌 → ji` |
| `Xiaoxian` | `生年支 → year_dizhi`、`性别 → gender`、`虚岁 → age`、`地支 → dizhi` |
| `Tongxian` | `命宫 → minggong`、`五行局 → ju`、`虚岁 → age`、`边界 → boundary`、`宫名 → palace_name`、`地支 → dizhi` |
| `Yunxian` | `小限 → xiaoxian`、`童限 → tongxian`、`大限 → decade` |
| `ZiweiChart` | `计算输入 → calculation`、`十二宫 → palaces`、`身宫 → shengong`、`五行局 → bureau`、`星位 → stars`、`生年四化 → sihua`、`大限 → decades` |
| `PalaceView` | `宫位 → palace`、`星位 → stars`、`化禄 → lu`、`化权 → quan`、`化科 → ke`、`化忌 → ji`、`是否身宫 → is_shengong` |
| `LiunianView` | `流年 → liunian`、`本命宫 → natal` |
| `LiunianPalaceView` | `纪年 → ganzhi_year`、`宫名 → name`、`地支 → dizhi`、`本命宫 → natal`、`流年四化 → sihua`、`化禄 → lu`、`化权 → quan`、`化科 → ke`、`化忌 → ji` |

大限的起止虚岁首尾包含；流年区间的起始日期包含、终止日期不含。`命宫`和`身宫`仍是地支，
完整宫位从`宫位视图.宫位`读取。出生记录与配置增加了中文类型名，字段和构造关键字仍用原名；
通用时间、错误类型和知识记录结构的名称也保持原样。

### 从出生记录读取年度结果与出处

以下使用合成的2024年农历正月初一子时女命。先按明确的出生口径排盘，再把已确定纪年的年度星曜与本命宫并读。

```{doctest}
>>> from ziwei.birth import 农历出生记录, 性别
>>> from ziwei.chart import create_chart, liunian_view
>>> from ziwei.config import 命盘配置, 子时换日, 换年界线, 闰月归属
>>> from ziwei.ganzhi import 地支
>>> from ziwei.knowledge import load_catalog
>>> from ziwei.liunian import LiunianStars, 流年星曜
>>> from ziwei.sihua import 四化变体
>>> 记录 = 农历出生记录(
...   year=2024, month=1, day=1, is_leap_month=False, shichen=地支.子, gender=性别.女,
... )
>>> 口径 = 命盘配置(
...   leap_month_policy=闰月归属.全月归本月,
...   day_rollover=子时换日.早晚子时同日,
...   year_boundary=换年界线.农历正月初一,
... )
>>> 命盘 = create_chart(记录, 口径, sihua_variant=四化变体.排命盘口诀转录)
>>> 流年星曜 is LiunianStars
True
>>> 年曜 = 流年星曜(2024)
>>> 年曜.纪年, str(年曜.年干支), 年曜.禄存.value, 年曜.擎羊.value, 年曜.陀罗.value
(2024, '甲辰', '寅', '卯', '丑')
>>> 年曜.陀罗 is 年曜.tuoluo is 地支.丑
True
>>> 叠读 = liunian_view(命盘, 年曜.纪年)
>>> 叠读.本命宫.宫位.宫名.value, 叠读.本命宫.宫位.地支.value
('福德', '辰')
>>> load_catalog().get(叠读.流年.rule_id).id
'variant.liunian.lucun-yangtuo'
```

构造与调用参数仍用`year=`、`gender=`等原名；`rule_id`仍是查询出处的稳定标识。
若从日期确定流年纪年，先按[流年指南](liunian.md)显式选择日期年界。

### 中文类型签名

```{eval-rst}
.. autodata:: ziwei.birth.性别
   :no-value:
.. autodata:: ziwei.birth.公历出生记录
   :no-value:
.. autodata:: ziwei.birth.农历出生记录
   :no-value:
.. autodata:: ziwei.birth.出生记录
   :no-value:
.. autodata:: ziwei.birth.计算输入
   :no-value:
.. autodata:: ziwei.config.闰月归属
   :no-value:
.. autodata:: ziwei.config.子时换日
   :no-value:
.. autodata:: ziwei.config.换年界线
   :no-value:
.. autodata:: ziwei.config.天马规则
   :no-value:
.. autodata:: ziwei.config.命盘配置
   :no-value:
.. autodata:: ziwei.config.口径选项
   :no-value:
.. autodata:: ziwei.ganzhi.阴阳
   :no-value:
.. autodata:: ziwei.ganzhi.天干
   :no-value:
.. autodata:: ziwei.ganzhi.地支
   :no-value:
.. autodata:: ziwei.ganzhi.干支
   :no-value:
.. autodata:: ziwei.ganzhi.五行
   :no-value:
.. autodata:: ziwei.palaces.宫名
   :no-value:
.. autodata:: ziwei.palaces.宫位
   :no-value:
.. autodata:: ziwei.bureau.五行局
   :no-value:
.. autodata:: ziwei.stars.星曜
   :no-value:
.. autodata:: ziwei.stars.安星规则
   :no-value:
.. autodata:: ziwei.stars.星位
   :no-value:
.. autodata:: ziwei.brightness.亮度等级
   :no-value:
.. autodata:: ziwei.brightness.亮度表
   :no-value:
.. autodata:: ziwei.brightness.亮度读数
   :no-value:
.. autodata:: ziwei.sihua.四化变体
   :no-value:
.. autodata:: ziwei.sihua.四化表
   :no-value:
.. autodata:: ziwei.sihua.四化结果
   :no-value:
.. autodata:: ziwei.decades.行运方向
   :no-value:
.. autodata:: ziwei.decades.大限
   :no-value:
.. autodata:: ziwei.liunian.流年星曜
   :no-value:
.. autodata:: ziwei.liunian.流年年界
   :no-value:
.. autodata:: ziwei.liunian.流年区间
   :no-value:
.. autodata:: ziwei.liunian.流年四化
   :no-value:
.. autodata:: ziwei.xiaoxian.小限
   :no-value:
.. autodata:: ziwei.tongxian.童限边界
   :no-value:
.. autodata:: ziwei.tongxian.童限
   :no-value:
.. autodata:: ziwei.yunxian.运限
   :no-value:
.. autodata:: ziwei.chart.紫微命盘
   :no-value:
.. autodata:: ziwei.chart.宫位视图
   :no-value:
.. autodata:: ziwei.chart.流年叠读
   :no-value:
.. autodata:: ziwei.chart.流年宫位
   :no-value:
```

## 出生记录与计算输入

```{eval-rst}
.. automodule:: ziwei.birth
   :members: Gender, TimePrecision, GregorianBirthRecord, LunarBirthRecord, CalculationInput, shichen_from_time
   :undoc-members:
   :member-order: bysource
```

```{eval-rst}
.. autodata:: ziwei.birth.BirthRecord
   :no-value:
```

## 口径

```{eval-rst}
.. automodule:: ziwei.config
   :members: LeapMonthPolicy, DayRollover, YearBoundary, TianmaRule, ChartConfig
   :undoc-members:
   :member-order: bysource
```

```{eval-rst}
.. autodata:: ziwei.config.PolicyOption
   :no-value:

.. autodata:: ziwei.config.POLICY_ENUMS
   :annotation:
```

## 时区与消歧

```{eval-rst}
.. automodule:: ziwei.timezone
   :members: IanaTimezone, FixedOffset, TimezoneData, ResolvedTime, NonexistentTimeError, AmbiguousTimeError, resolve_civil_time, current_timezone_data
   :undoc-members:
   :member-order: bysource
```

## 干支

[干支来源与限度](birth.md#干支来源与限度)。

```{eval-rst}
.. automodule:: ziwei.ganzhi
   :members: Yinyang, Tiangan, Dizhi, Wuxing, Ganzhi, year_ganzhi, nayin, yin_stem, palace_stems
   :undoc-members:
   :member-order: bysource
```

```{eval-rst}
.. autodata:: ziwei.ganzhi.JIAZI
   :no-value:

.. autodata:: ziwei.ganzhi.YEAR_GANZHI
   :no-value:

.. autodata:: ziwei.ganzhi.NAYIN_ELEMENT
   :annotation:

.. autodata:: ziwei.ganzhi.WUHU_YIN
   :annotation:
```

## 历法适配

celestial-calendar 的具体适配；导入本模块不初始化 celestial 原生库（公开函数在
函数体内导入）。所选农历算法与支持范围见[历法与时间](calendar.md)，时标合同见
[解析层](resolver.md)。

```{eval-rst}
.. automodule:: ziwei.calendar
   :members: LunarAlgorithm, celestial_version, supported_lunar_year_range, gregorian_to_lunar, lunar_to_gregorian, lunar_year_info, validate_lunar_date, utc_to_ut1_jd, lichun_jd, lichun_date, utc_civil, apparent_solar
   :undoc-members:
   :member-order: bysource

.. autodata:: ziwei.calendar.LICHUN_DATE_YEAR_RANGE
   :no-value:
```

## 命宫身宫与十二宫

[安星边界](palaces.md)。

```{eval-rst}
.. automodule:: ziwei.palaces
   :members: PalaceName, Palace, opposite_dizhi, sanfang_sizheng, effective_month, month_palace_index, minggong_dizhi, shengong_dizhi, palace_dizhi, twelve_palaces, palace_ganzhi
   :undoc-members:
   :member-order: bysource

.. autodata:: ziwei.palaces.OPPOSITE_RULE_ID
   :no-value:

.. autodata:: ziwei.palaces.SANFANG_SIZHENG_RULE_ID
   :no-value:
```

## 五行局

[定局规则](bureau.md)。

```{eval-rst}
.. automodule:: ziwei.bureau
   :members: WuxingJu, bureau_of, bureau_number
   :undoc-members:
   :member-order: bysource
```

## 解析层

[解析顺序与失败边界](resolver.md)。

```{eval-rst}
.. automodule:: ziwei.resolver
   :members: resolve, DEFAULT_LUNAR_ALGORITHM
   :undoc-members:
   :member-order: bysource
```

## 安星

[36星用法、来源与失败边界](stars.md) · [定义生成的安星参考表](knowledge-reference.md#implemented-stars)

```{eval-rst}
.. automodule:: ziwei.stars
   :members: Star, StarRule, StarPlacement, ziwei_dizhi, tianfu_dizhi, place_major_stars, place_month_stars, place_hour_stars, lucun_yangtuo_dizhi, place_stem_stars, place_fire_bell, tianma_dizhi, place_hongluan_tianxi, place_tianku_tianxu, place_tianshang_tianshi, place_stars
   :undoc-members:
   :member-order: bysource

.. autodata:: ziwei.stars.STAR_RULES
   :no-value:
   :annotation:

.. autodata:: ziwei.stars.MAJOR_STARS
   :no-value:
```

## 亮度

[七级原名、查询与来源限度](brightness.md)。只读取已有星位，不初始化原生历法库。

```{eval-rst}
.. automodule:: ziwei.brightness
   :members: BrightnessLevel, BrightnessTable, BrightnessReading, star_brightness
   :undoc-members:
   :member-order: bysource
```

## 生年四化与大限

[用法与来源限度](sihua-decades.md)。两个模块均不在导入时初始化原生历法库。

```{eval-rst}
.. automodule:: ziwei.sihua
   :members: SihuaVariant, SihuaTable, SihuaResult, sihua_for_stem, shengnian_sihua
   :undoc-members:
   :member-order: bysource

.. autodata:: ziwei.sihua.SIHUA_TABLES
   :no-value:

.. automodule:: ziwei.decades
   :members: Direction, Decade, decade_direction, decade_periods, place_decades
   :undoc-members:
   :member-order: bysource

.. autodata:: ziwei.decades.DECADE_RULE_ID
   :no-value:

.. autodata:: ziwei.decades.DECADE_DEFINITION
   :no-value:
```

## 流年

[纪年定位、年度禄羊陀、日期年界与本命叠读](liunian.md)。纯纪年不初始化原生历法，日期查询显式选择独立年界。

```{eval-rst}
.. automodule:: ziwei.liunian
   :members: LiunianStars, liunian_stars, LiunianBoundary, LiunianYear, liunian_minggong, liunian_on_date, liunian_palace_dizhi, LiunianSihua, liunian_sihua
   :undoc-members:
   :member-order: bysource

.. autodata:: ziwei.liunian.LIUNIAN_MINGGONG_RULE_ID
   :no-value:

.. autodata:: ziwei.liunian.LIUNIAN_STARS_RULE_ID
   :no-value:

.. autodata:: ziwei.liunian.LIUNIAN_STARS_DEFINITION
   :no-value:

.. autodata:: ziwei.liunian.LIUNIAN_PALACES_RULE_ID
   :no-value:

.. autodata:: ziwei.liunian.LIUNIAN_PALACES_DEFINITION
   :no-value:

.. autodata:: ziwei.liunian.LIUNIAN_SIHUA_RULE_ID
   :no-value:

.. autodata:: ziwei.liunian.LIUNIAN_SIHUA_DEFINITION
   :no-value:
```

## 小限、童限与运限并读

小限、童限的独立查询与已有命盘的运限并读，见[运限用法](yunxian.md)。

```{eval-rst}
.. automodule:: ziwei.xiaoxian
   :members: Xiaoxian, xiaoxian_at_age
   :undoc-members:
   :member-order: bysource

.. autodata:: ziwei.xiaoxian.XIAOXIAN_RULE_ID
   :no-value:

.. autodata:: ziwei.xiaoxian.XIAOXIAN_DEFINITION
   :no-value:

.. autodata:: ziwei.xiaoxian.XIAOXIAN_STARTS
   :no-value:

.. automodule:: ziwei.tongxian
   :members: TongxianBoundary, Tongxian, tongxian_palace, tongxian_at_age
   :undoc-members:
   :member-order: bysource

.. autodata:: ziwei.tongxian.TONGXIAN_RULE_ID
   :no-value:

.. autodata:: ziwei.tongxian.TONGXIAN_PALACES
   :no-value:

.. automodule:: ziwei.yunxian
   :members: Yunxian, yunxian_at_age
   :undoc-members:
   :member-order: bysource
```

## 完整命盘与显示

[用法与参考盘例](chart.md)。从原始出生记录排盘，生成只读文本或静态SVG盘面，不提供命盘保存／恢复接口。
`render_svg()`自v0.2.0起提供。

```{eval-rst}
.. automodule:: ziwei.chart
   :members: ZiweiChart, PalaceView, palace_view, LiunianView, liunian_view, LiunianPalaceView, liunian_palaces, chart_brightness, create_chart
   :undoc-members:
   :member-order: bysource

.. automodule:: ziwei.render
   :members: render_text, render_svg
```

## 独立知识目录

[查询与状态说明](knowledge.md) · [从语料生成的参考页](knowledge-reference.md)

### 加载目录

```{eval-rst}
.. automodule:: ziwei.knowledge
   :members: load_catalog
```

### 记录类型与状态

```{eval-rst}
.. automodule:: ziwei.knowledge.model
   :members: ConceptKind, TextLayer, EvidenceAspect, SourceStatus, PremiseStatus, CurationStatus, Concept, RuleVariant, Source, Citation, KnowledgeEntry
   :undoc-members:
   :member-order: bysource
```

### 目录查询

```{eval-rst}
.. automodule:: ziwei.knowledge.catalog
   :members: Catalog
   :undoc-members:
   :member-order: bysource

.. autodata:: ziwei.knowledge.catalog.Record
   :no-value:

```
