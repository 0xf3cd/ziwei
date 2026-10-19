# 输入 API 参考

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
   :members: Yinyang, Tiangan, Dizhi, Ganzhi, year_ganzhi
   :undoc-members:
   :member-order: bysource
```

```{eval-rst}
.. autodata:: ziwei.ganzhi.JIAZI
   :no-value:

.. autodata:: ziwei.ganzhi.YEAR_GANZHI
   :no-value:
```
