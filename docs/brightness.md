# 十四主星七级亮度

[完整命盘与显示](chart.md) · [API](api.md#亮度) · [定义生成的168格参考](knowledge-reference.md#implemented-brightness)

自0.3.0起提供《紫微斗數全書》卷二固定电子录文的一套具名表，
不称“标准表”。亮度查询读取已有星位，不改变安星位置、不评分，也不解释吉凶。

## 查询与结果

```{doctest}
>>> from ziwei.brightness import BrightnessLevel, BrightnessTable, star_brightness
>>> from ziwei.ganzhi import Dizhi
>>> from ziwei.stars import Star
>>> table = BrightnessTable.全书卷二录文
>>> reading = star_brightness(Star.紫微, Dizhi.辰, table=table)
>>> reading.star.value, reading.dizhi.value, reading.table.value, reading.level.value
('紫微', '辰', '全书卷二固定录文', '得地')
>>> reading.table_id
'variant.brightness.quanshu-juan2'
>>> star_brightness(Star.红鸾, Dizhi.辰, table=table).level is None
True
>>> tuple(level.value for level in BrightnessLevel)
('庙', '旺', '得地', '利益', '平和', '不得地', '落陷')
```

`BrightnessReading`不可变，保存星曜、地支、所选表和等级；直接构造也核对读数与表一致。
表必须显式选择，查询只接受`Star`、`Dizhi`和`BrightnessTable`枚举成员，错类型抛`TypeError`。
`table_id`指向知识目录中的亮度变体，不是`StarPlacement.rule_id`所指的安星规则。

| 状态 | 表达 |
|---|---|
| 未请求亮度 | 不调用查询；显示的`brightness_table`省略或为`None` |
| 非主星不适用 | 返回读数，但`level is None`；不填“平和” |
| 未支持的表 | 不接受其他字符串或表身份，不静默换表 |
| 主星格缺失 | 显式失败，不把缺格当不适用；当前表的168格由全量测试核对 |

原表还列部分辅星，本功能只提取十四主星×十二地支168格；查询文昌、文曲等辅星同样返回不适用。
七级保留原名，不将“庙旺利陷”这个功能统称当作四档。

已有命盘可用`ziwei.chart.chart_brightness(chart, table=...)`批量读取，签名见[命盘API](api.md#完整命盘与显示)。
具体调用、文本与SVG开关见[命盘亮度](chart.md#读取与显示亮度)。

## 所选表与校异

依据是维基文库[卷二固定修订1963110](https://zh.wikisource.org/w/index.php?title=%E7%B4%AB%E5%BE%AE%E6%96%97%E6%95%B8%E5%85%A8%E6%9B%B8/%E5%8D%B7%E4%BA%8C&oldid=1963110)
中“一 命宫”之前的七级成表。逐格定位使用地支行、等级列及星曜缩写。

以下差异用于检查是否混表，不能用来修改所选表：

| 星曜与地支 | 所选成表原名 | 校异材料的原字 |
|---|---|---|
| 紫微辰 | 得地 | 王亭之讲义图：陷 |
| 太阳午 | 旺 | 王亭之讲义图：庙 |
| 巨门丑 | 不得地 | 王亭之讲义图：旺 |
| 太阳丑、戌 | 不得地 | 同书太阳条目：陷 |
| 天府卯 | 得地 | 同书天府条目：入庙 |

讲义图取自[bazilives第29篇](https://bazilives.com/jingdian/ziwei-shenzao/29/)的fig-27，
对照范围与原字处理见[来源记录](knowledge-reference.md#source.wangtingzhi-bazilives-brightness)。

知识目录中的[表与出处](knowledge-reference.md#entry.brightness.quanshu-juan2)记录来源状态、限度与复核条件，
暂不默认展示；可执行的查询不代表底本已校。
