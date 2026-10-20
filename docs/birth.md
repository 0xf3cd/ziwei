# 出生输入与口径

[项目入口](../README.md) · [API 参考](api.md) · [计算边界](architecture.md)

本页的出生资料与计算输入均为合成数据。当前 API 保存输入、检查形状并消歧民用时刻，
不把公历换成农历、不应用闰月或子时换日，也不排出命盘。

## 保存原始公历记录

日期、钟点、精度与时区分别保存；不要先给钟点附上一个可能悄悄选错的时区对象。
经度以度计，东经为正，只保存于记录，不在此执行真太阳时换算。

```{doctest}
>>> from datetime import date, time
>>> from ziwei.birth import GregorianBirthRecord, TimePrecision, Gender
>>> from ziwei.timezone import IanaTimezone
>>> record = GregorianBirthRecord(
...   birth_date=date(1988, 7, 1), birth_time=time(12), time_precision=TimePrecision.分,
...   timezone=IanaTimezone("Asia/Shanghai"), gender=Gender.男,
...   place="合成省", source="合成记录",
... )
>>> moment = record.resolve_time()
>>> str(moment.offset), moment.utc.isoformat()
('9:00:00', '1988-07-01T03:00:00+00:00')
>>> record.birth_time.isoformat()
'12:00:00'
>>> record.shichen.value
'午'
```

上海在这个日期采用夏令时。显式固定偏移是另一种输入，不能自动替换成地区规则：

```{doctest}
>>> from dataclasses import replace
>>> from datetime import timedelta
>>> from ziwei.timezone import FixedOffset
>>> fixed = replace(record, timezone=FixedOffset(timedelta(hours=8)))
>>> fixed.resolve_time().utc.isoformat()
'1988-07-01T04:00:00+00:00'
```

精度为时、分或秒时，低于该精度的钟面分量须为零；微秒精度可保留全部分量。
钟点未知用 `birth_time=None`、精度为日；性别未知用 `Gender.未知`，都不代填。
来源与地点是可选字符串；原始记录、配置和结果均冻结，成员也不包含调用方可修改的容器。

## 间隙拒绝，重叠显式选

```{doctest}
>>> from ziwei.timezone import AmbiguousTimeError, NonexistentTimeError
>>> gap = replace(record, birth_date=date(1988, 4, 17), birth_time=time(2, 30))
>>> try:
...   gap.resolve_time()
... except NonexistentTimeError:
...   print("不存在，不自动平移")
不存在，不自动平移
>>> overlap = replace(record, birth_date=date(1988, 9, 11), birth_time=time(1, 30))
>>> try:
...   overlap.resolve_time()
... except AmbiguousTimeError:
...   print("需要选择 fold")
需要选择 fold
>>> early = replace(overlap, timezone=IanaTimezone("Asia/Shanghai", fold=0)).resolve_time()
>>> late = replace(overlap, timezone=IanaTimezone("Asia/Shanghai", fold=1)).resolve_time()
>>> early.utc.isoformat(), late.utc.isoformat()
('1988-09-10T16:30:00+00:00', '1988-09-10T17:30:00+00:00')
```

`fold=0` 取较早瞬间，`fold=1` 取较晚瞬间。普通时刻不接受多余的 `fold=1`。
请求保留在结果的 `zone`，实际选择保留在 `fold`；间隙没有可供选择的瞬间。

IANA 解析显式读取钉版 `tzdata` 包的资源，不查系统数据库，也不修改全局搜索路径。
`moment.data` 记录实际包版本 `package_version` 与 IANA 发布版本 `iana_version`，两者不是同一个版本号；
固定偏移结果的 `data` 为 `None`。未知标识抛 `ZoneInfoNotFoundError`，缺包抛 `ModuleNotFoundError`，不回落系统库。
文件读取发生在 `resolve_time()` 或 `resolve_civil_time()` 调用时，导入包和构造原始记录不读时区文件。

原始历史日期可以保存；民用时刻解析只支持 UTC 不早于 1972-01-01。
时标转换、历法算法与版本记录随后续历法适配提供，不用现代 UTC 合同替代更早的历史时标。

## 显式配置与解析后的输入形状

三个口径互相独立，构造配置时全部必填；它们不改变原始日期。
术数专有词用拼音，通用概念用惯用英语。枚举的中文别名与对应成员相同，JSON 值是中文。

```{doctest}
>>> from dataclasses import asdict
>>> import json
>>> from ziwei.config import YearBoundary, ChartConfig, LeapMonthPolicy, DayRollover
>>> choices = ChartConfig(
...   leap_month_policy=LeapMonthPolicy.全月归本月,
...   day_rollover=DayRollover.晚子时归次日,
...   year_boundary=YearBoundary.立春,
... )
>>> json.loads(json.dumps(asdict(choices), ensure_ascii=False))["year_boundary"]
'立春'
```

农历原始记录显式给闰月标志，时辰未知为 `None`。这里只核年1至9999、月1至12、日1至30等形状与值域，
不证明该年有这个闰月、这个月有这一天；这些须由历法适配验证。

`CalculationInput` 是解析层完成处理后的输出形状，由解析层从原始记录生成。
`ganzhi_year` 须是解析层按换年口径确定的纪年编号，可能不同于农历年；不能把公历出生年直接代入。
`lunar_algorithm` 与 `lunar_algorithm_version` 记录所用农历算法及版本，`apparent_solar`
与 `day_rolled` 记录真太阳时路径与晚子时顺延，`ut1_jd` 与 `lichun_jd` 记录立春换年
比较的出生瞬间与立春时刻。换年口径为立春时 `ut1_jd` 与 `lichun_jd` 不可缺省；
以下合成例用正月初一口径，只示范保存字段与拒绝缺项，不是历法转换或参考盘例。

```{doctest}
>>> from ziwei.birth import CalculationInput, LunarBirthRecord
>>> from ziwei.calendar import LunarAlgorithm
>>> from ziwei.config import YearBoundary
>>> from ziwei.ganzhi import Dizhi
>>> lunar = LunarBirthRecord(
...   year=2000, month=1, day=1, is_leap_month=False, shichen=Dizhi.子, gender=Gender.女,
... )
>>> lichun = ChartConfig(
...   leap_month_policy=LeapMonthPolicy.全月归本月,
...   day_rollover=DayRollover.晚子时归次日,
...   year_boundary=YearBoundary.立春,
... )
>>> value = CalculationInput(
...   record=lunar, lunar_year=2000, month=1, day=1, is_leap_month=False,
...   shichen=Dizhi.子, ganzhi_year=1999, config=lichun,
...   lunar_algorithm=LunarAlgorithm.ALGO3, lunar_algorithm_version="0.8.0",
...   apparent_solar=False, day_rolled=False, ut1_jd=0.0, lichun_jd=0.0,
... )
>>> str(value.year_ganzhi), value.yinyang.value, value.gender.value
('己卯', '阴', '女')
>>> value.config is lichun
True
>>> value.require_complete()
>>> partial = replace(value, shichen=None, record=replace(lunar, gender=Gender.未知))
>>> try:
...   partial.require_complete()
... except ValueError:
...   print("完整命盘需要时辰与性别")
完整命盘需要时辰与性别
```

普通记录可以保留未知，`require_complete()` 才检查完整命盘的必要项；它不排盘。
调用完整命盘入口时须先完成历法解析，再执行该检查。公开校验在 `python -O` 下同样有效。

## 干支来源与限度

六十甲子定义采用香港天文台[《天干和地支》表二](https://www.hko.gov.hk/tc/gts/time/stemsandbranches.htm)，
时辰钟面区间据同页表三；纪年锚为该台[1984年对照表首行](https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T1984c.txt)。
年干支参考表由同一六十甲子定义生成，不手抄第二套序列。`year_ganzhi()` 只查已经确定的纪年编号，
不采用该台的换年时刻去替调用方选择正月初一或立春。

纳音五行与五虎遁同为带出处的声明式表：纳音元素取自《紫微斗數全書》卷二纳音歌（维基文库
修订1963110）与《渊海子平》卷一纳音注解（物名异文不进入计算）；五虎遁取《起五行寅例》与
王亭之中州派讲义五虎遁诀，同口诀亦见《渊海子平》年上起月例。两表只供命宫定局与宫干推排，
不证明任何吉凶解释。

独立 golden 据交通部中央气象署编印[《天文日曆 2024》](https://www.cwa.gov.tw/Data/service/notice/download/Publish_20231127145652.pdf)，
2023年11月出版，印刷第6页（PDF第11页）的“干支順序表”；同书PDF第2页年历抬头提供2024甲辰锚。
这里取表列事实作测试，不转载该书正文或页面图像。

天干阴阳分类见《五行大義》卷二“第五論配支幹”，另见《選擇要略》上“十干所屬陰陽”：
已读的维基文库电子录文分别为[修订7915687](https://zh.wikisource.org/w/index.php?title=%E4%BA%94%E8%A1%8C%E5%A4%A7%E7%BE%A9/2&oldid=7915687)
与[修订2413684](https://zh.wikisource.org/w/index.php?title=%E9%81%B8%E6%93%87%E8%A6%81%E7%95%A5/%E4%B8%8A&oldid=2413684)。
只取基础分类，不引入其中其他术数的查法或吉凶解释；所据影印刊本与页码未核，不作纸本版本声称。

时区行为依据 [Python 3.11 zoneinfo 文档](https://docs.python.org/3.11/library/zoneinfo.html)及实际钉版时区资源。
这些来源不证明任何安星、四化或大限规则，也不构成完整命盘的独立盘例。
