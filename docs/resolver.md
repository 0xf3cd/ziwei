# 解析层：出生记录到计算输入

[API 参考](api.md#解析层) · [历法与时间](calendar.md) · [命宫身宫与十二宫](palaces.md)

`ziwei.resolver.resolve` 把原始出生记录（公历或农历）与显式口径解析为 `CalculationInput`，
随结果保存所用农历算法与版本、真太阳时路径、晚子时顺延，以及立春换年比较的出生瞬间与
立春时刻（UT1 日数）。

## 解析顺序

1. 时刻：只有立春口径或真太阳时（有经度）才解析 UTC 瞬间；正月初一口径加无经度纯民用
   路径不需要瞬间。
2. 时辰：民用路径取记录钟面；真太阳时路径取真太阳钟。时辰所附民用日＝民用路径取出生地
   当地民用日、真太阳时路径取真太阳钟的民用日。
3. 子时换日：时辰为子且落在所附民用日 23:00–24:00（晚子时）时，「晚子时归次日」取次日日标签，
   「早晚子时同日」不改；`day_rolled` 记录是否顺延。
4. 农历日：只换算最终取用的日标签，不要求未取用的前一日也在算法范围内。
5. 换年：立春 → 出生瞬间按 modelled-UT1 换算（见[时标合同](calendar.md#时标合同)）与立春
   时刻比较，左闭右开（出生瞬间等于立春时刻归新年）；正月初一 → 按（换日调整后的）农历日
   所属年。
6. 未知时辰／性别可随解析输入保存；[安星入口](stars.md)需要已知时辰，允许性别未知。
   完整命盘另要求性别已知。

## 失败边界

- 农历输入选立春口径：显式失败（农历记录没有瞬间与时区，无法与立春 UT1 时刻同标比较）。
- 农历记录时辰为子且选晚子时归次日：显式失败（记录无钟点粒度，无法判定早子时或晚子时）；
  选早晚子时同日则无此歧义。
- 1972 年前的公历记录需要瞬间（立春口径或真太阳时）时显式失败；正月初一口径加无经度
  路径不受影响。
- 请求的农历算法不支持该日期、闰月／日组合不存在、时辰未知但需要瞬间（立春口径或
  真太阳时——有经度但钟点未知）时：显式失败。

```{doctest}
>>> from datetime import date, time
>>> from ziwei.birth import Gender, GregorianBirthRecord, TimePrecision
>>> from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, YearBoundary
>>> from ziwei.resolver import resolve
>>> from ziwei.timezone import IanaTimezone
>>> record = GregorianBirthRecord(
...   birth_date=date(1988, 7, 1), birth_time=time(12), time_precision=TimePrecision.分,
...   timezone=IanaTimezone("Asia/Shanghai"), gender=Gender.男,
... )
>>> choices = ChartConfig(
...   leap_month_policy=LeapMonthPolicy.全月归本月,
...   day_rollover=DayRollover.晚子时归次日,
...   year_boundary=YearBoundary.农历正月初一,
... )
>>> value = resolve(record, choices)
>>> (value.lunar_year, value.month, value.day), value.shichen.value
((1988, 5, 18), '午')
>>> str(value.year_ganzhi), value.ut1_jd
('戊辰', None)
```
