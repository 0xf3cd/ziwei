# API 参考

[出生输入用法](birth.md) · [项目入口](../README.md)

以下签名和说明从实现生成；模块按职责导入，不从包根初始化历法或时区数据。
枚举中的中文成员名是对应拼音或英语成员的别名，指向同一成员。

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
   :members: LeapMonthPolicy, DayRollover, YearBoundary, ChartConfig
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
   :members: IanaTimezone, FixedOffset, TimezoneData, ResolvedTime, NonexistentTimeError, AmbiguousTimeError, resolve_civil_time
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
