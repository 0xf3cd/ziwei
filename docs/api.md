# API 参考

[出生输入用法](birth.md) · [项目入口](../README.md)

以下签名和说明从实现生成；模块按职责导入，不从包根初始化历法或时区数据。
枚举中的中文成员名是对应拼音或英语成员的别名，指向同一成员。
模块中的公开数据以显式 `TypeAlias`，或带变量说明的 `Final` 声明；下划线名字为内部实现。
其他未加下划线的赋值和导入不因此成为公开数据合同。API 检查要求这些声明有真实 HTML 签名，
不要求枚举成员、数据字段等额外签名与源码声明集合完全相等。

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

celestial-calendar 0.8.0 的具体适配；导入本模块不初始化 celestial 原生库（公开函数在
函数体内导入）。所选农历算法与支持范围见[历法与时间](calendar.md)，时标合同见
[解析层](resolver.md)。

```{eval-rst}
.. automodule:: ziwei.calendar
   :members: LunarAlgorithm, celestial_version, supported_lunar_year_range, gregorian_to_lunar, lunar_to_gregorian, lunar_year_info, validate_lunar_date, utc_to_ut1_jd, lichun_jd, utc_civil, apparent_solar
   :undoc-members:
   :member-order: bysource
```

## 命宫身宫与十二宫

[安星边界](palaces.md)。

```{eval-rst}
.. automodule:: ziwei.palaces
   :members: PalaceName, Palace, effective_month, month_palace_index, minggong_dizhi, shengong_dizhi, twelve_palaces, palace_ganzhi
   :undoc-members:
   :member-order: bysource
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

[28星用法、来源与失败边界](stars.md) · [定义生成的安星参考表](knowledge-reference.md#implemented-stars)

```{eval-rst}
.. automodule:: ziwei.stars
   :members: Star, StarRule, StarPlacement, ziwei_dizhi, tianfu_dizhi, place_major_stars, place_month_stars, place_hour_stars, place_stem_stars, place_fire_bell, tianma_dizhi, place_stars
   :undoc-members:
   :member-order: bysource

.. autodata:: ziwei.stars.STAR_RULES
   :no-value:
   :annotation:
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

## 完整命盘、记录与显示

[用法、schema合同与参考盘例](chart.md)。恢复按已存版本核结构及纯规则，历法与时区真实性另由重算检验。

```{eval-rst}
.. automodule:: ziwei.chart
   :members: ZiweiChart, create_chart, recalculate
   :undoc-members:
   :member-order: bysource

.. automodule:: ziwei.serialization
   :members: dumps_chart, loads_chart, UnsupportedSchemaVersionError
   :undoc-members:
   :member-order: bysource

.. autodata:: ziwei.serialization.SCHEMA_VERSION
   :annotation:

.. automodule:: ziwei.render
   :members: render_text
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
   :members: ConceptKind, TextLayer, EvidenceAspect, SourceStatus, PremiseStatus, DisplayEligibility, CurationStatus, Concept, RuleVariant, Source, Citation, KnowledgeEntry
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

.. autodata:: ziwei.knowledge.data.CATALOG_VERSION
   :no-value:
```
