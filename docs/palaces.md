# 命宫身宫与十二宫

[API 参考](api.md#命宫身宫与十二宫) · [解析层](resolver.md) · [项目入口](../README.md)

命宫与身宫由农历生月与生时定：从寅宫起正月顺数至生月，再自该宫起子时，逆数至生时安命、
顺数至生时安身（《紫微斗數全書》卷二《安身命例》，维基文库修订1963110；同法见王亭之中州派
《紫微斗数初级讲义》安命身宫诀）。十二宫自命宫起逆排，完整宫名与顺序见
[从领域定义生成的说明](knowledge-reference.md#variant.palace.twelve)，来源原字另见该页引文。

身宫是叠在某宫上的标记，不是第十三个宫；身宫只落命宫、福德、官禄、迁移、财帛、妻妾六宫
（按时辰的子午、丑未、寅申、卯酉、辰戌、巳亥分组）。

```{doctest}
>>> from ziwei.ganzhi import Dizhi
>>> from ziwei.palaces import minggong_dizhi, shengong_dizhi
>>> str(minggong_dizhi(1, Dizhi.子)), str(shengong_dizhi(1, Dizhi.子))
('寅', '寅')
>>> str(minggong_dizhi(1, Dizhi.丑)), str(shengong_dizhi(1, Dizhi.丑))
('丑', '卯')
```

## 宫干与闰月

宫干由年干经[五虎遁](knowledge-reference.md#implemented-wuhu)查寅宫干，其余各宫顺十天干排布
（《起五行寅例》）。闰月出生按具名口径取有效生月（`effective_month`）：
《全书》安身命段的[闰正月例](knowledge-reference.md#entry.leap-month.next)按二月起命身，
其他月系星是否沿用仍待核；LifeDNA列本月、次月、前后半月三法，自述采用第三种。
闰十二月全月归下月时没有对应安星月；按前后半月归属时，十六日起同样失败，初一至十五仍归本月。
`effective_month`不合成「来年正月」的无出处规则。

`Palace`构造时要求地支、天干与宫名分别为所属枚举成员，并核对干支阴阳配对。
同值字符串或列表抛`TypeError`，如甲丑这样的不合法配对抛`ValueError`；接受的宫位值不可变。
相比已发布的v0.1.0，这些非法输入会在构造宫位时立即失败，不再等到读取干支或组合完整盘时才拒绝。

`effective_month`只核月份1至12、日期1至30等基本值域，不检查真实月长或该年是否存在此闰月。
真实日期由历法适配的`validate_lunar_date`核验，解析层会调用它；例如小月三十不能仅靠本函数判断。

```{doctest}
>>> from ziwei.config import LeapMonthPolicy
>>> from ziwei.ganzhi import Dizhi, Tiangan
>>> from ziwei.palaces import effective_month, palace_ganzhi, twelve_palaces
>>> effective_month(2, 4, True, LeapMonthPolicy.全月归下月)
3
>>> str(palace_ganzhi(Dizhi.寅, 1984))  # 甲子年命寅 → 丙寅
'丙寅'
>>> palaces = twelve_palaces(Dizhi.子, Tiangan.甲)
>>> palaces[0].name.value, str(palaces[0].ganzhi)
('命宫', '丙子')
```

## 对宫与三方四正

v0.2.0（开发中）提供两个不依赖出生资料的关系查询。`opposite_dizhi()`返回相隔六宫的对宫；
`sanfang_sizheng()`返回本宫、两个三合宫与对宫。元组顺序固定为本宫、地支序偏移+4、偏移+8、对宫；
地支序按子丑寅卯排列并循环。这是项目API约定，不是来源规定的排列顺序。

```{doctest}
>>> from ziwei.palaces import opposite_dizhi, sanfang_sizheng
>>> opposite_dizhi(Dizhi.子).value
'午'
>>> tuple(branch.value for branch in sanfang_sizheng(Dizhi.寅))
('寅', '午', '戌', '申')
```

两个入口只接受`Dizhi`成员，同值字符串、整数或`bool`抛`TypeError`；不重算历法、不借星、不作吉凶解释。
以宫名读取命盘中的星曜与四化，见[按宫读取](chart.md#按宫读取)。

成员关系据[《名詞解釋》](knowledge-reference.md#source.ntnu-palace-glossary)与
[安迪作者站](knowledge-reference.md#source.andy-sanfang-sizheng)的现代说明及具体例子登记。
两页对单独“三方”的表达不同，本接口只提供成员一致的“三方四正”组合，不据此定义单独的“三方”。
《名詞解釋》的子女例与其一般定义不一致，不用于验收；两份网页的原始谱系与纸本均未核，不声称古籍或流派共识。
执行规则与短引见[对宫](knowledge-reference.md#variant.palace.opposite)、
[三方四正](knowledge-reference.md#variant.palace.sanfang-sizheng)。
