# 结果JSON

[项目入口](../README.md) · [完整命盘与盘面](chart.md) · [API](api.md#结果json)

把已排好的命盘存成JSON，交给别的程序读取和绘制。结果只存读数：宫位、星位、四化、大限，
以及导出时选择的亮度、运限和流年。读回时不调用历法，也不重新排盘。

## 导出与读回

下面沿用[完整命盘](chart.md#排盘与显示)的合成输入。`result_of()`从已有命盘取读数，
`dumps()`写成JSON文本，`loads()`读回同样的值。

```{doctest}
>>> import json
>>> from ziwei.birth import Gender, LunarBirthRecord
>>> from ziwei.brightness import BrightnessTable
>>> from ziwei.chart import create_chart
>>> from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, YearBoundary
>>> from ziwei.ganzhi import Dizhi
>>> from ziwei.result import dumps, loads, result_of
>>> from ziwei.sihua import SihuaVariant
>>> from ziwei.tongxian import TongxianBoundary
>>> chart = create_chart(
...   LunarBirthRecord(
...     year=2024, month=1, day=1, is_leap_month=False, shichen=Dizhi.子, gender=Gender.女,
...   ),
...   ChartConfig(
...     leap_month_policy=LeapMonthPolicy.上半月归本月下半月归下月,
...     day_rollover=DayRollover.早晚子时同日,
...     year_boundary=YearBoundary.农历正月初一,
...   ),
...   sihua_variant=SihuaVariant.排命盘口诀转录,
... )
>>> result = result_of(
...   chart,
...   brightness_table=BrightnessTable.全书卷二录文,
...   ages=(3, 30),
...   tongxian_boundary=TongxianBoundary.起限当岁不含,
...   years=(2026,),
...   liunian_sihua_variant=SihuaVariant.王亭之讲义转录,
... )
>>> text = dumps(result)
>>> loads(text) == result
True
>>> data = json.loads(text)
>>> list(data)
['palaces', 'shengong', 'bureau', 'stars', 'sihua', 'decades', 'brightness', 'yunxian', 'liunian']
>>> print(json.dumps(data["yunxian"], ensure_ascii=False))
[{"age": 3, "xiaoxian": "申", "tongxian": "酉", "decade": null}, {"age": 30, "xiaoxian": "巳", "tongxian": null, "decade": "子"}]
```

`dumps()`的文本不转义中文，保存时用UTF-8。

## 存了什么

键名与Python读数类型的字段同名，值是领域枚举的中文值，年龄与纪年是整数。

| 键 | 内容 |
|---|---|
| `palaces` | 本命十二宫，按宫名序，每宫有`name`、`tiangan`、`dizhi` |
| `shengong`、`bureau` | 身宫地支、五行局 |
| `stars` | 每颗星的`star`与所在`dizhi` |
| `sihua` | 生年四化的`lu`、`quan`、`ke`、`ji`四颗星；落宫从`stars`查 |
| `decades` | 行运方向、年龄计法（虚岁）和十二限，每限有地支与首尾包含的起止虚岁 |
| `brightness` | 所选亮度表中十四主星的`level` |
| `yunxian` | 所选虚岁的小限、童限、大限地支 |
| `liunian` | 所选纪年的流年十二宫、禄存、擎羊、陀罗与年度四化 |

后三层只在导出时选择后出现。`result_of()`的`ages`或`years`传`None`时省略该层，
传空序列时写出空数组。`yunxian`中`tongxian`为`null`表示该岁不在所选边界的童限内，
`decade`为`null`表示首限之前；`liunian`中`sihua`为`null`表示未请求年度四化。

## 没存什么

结果不含出生资料、三个口径、所选四化表或亮度表、童限边界、规则标识和软件版本，
也没有格式版本号。同一份结果读回后，看不出亮度来自哪张表、四化按哪张表查得。
需要留档时，由保存出生资料与配置的档案一并记录。

## 读取时检查什么

`loads()`拒绝未知或缺少的键、错类型（布尔值和小数不当整数）、不认识的枚举值、重复键、
`NaN`与`Infinity`，也拒绝层内互相矛盾的读数：星曜重复、四化星不在`stars`中、
大限不相接或方向与地支走向不符、运限的大限不覆盖该岁等。错误消息以JSON路径开头：

```{doctest}
>>> loads(text.replace('"age": 30', '"age": 3'))
Traceback (most recent call last):
...
ValueError: $.yunxian: 虚岁不得重复
```

读取不按现行规则重算星位、亮度或四化。以后修正规则或增加星曜，已保存的结果仍按原值读回；
要按新规则得到新读数，从出生资料重新排盘再导出。
