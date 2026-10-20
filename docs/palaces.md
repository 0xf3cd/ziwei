# 命宫身宫与十二宫

[API 参考](api.md#命宫身宫与十二宫) · [解析层](resolver.md) · [项目入口](../README.md)

命宫与身宫由农历生月与生时定：从寅宫起正月顺数至生月，再自该宫起子时，逆数至生时安命、
顺数至生时安身（《紫微斗數全書》卷二《安身命例》，维基文库修订1963110；同法见王亭之中州派
《紫微斗数初级讲义》安命身宫诀）。十二宫自命宫起逆排，顺序依《安十二宫例》：
命宫、兄弟、妻妾、子女、财帛、疾厄、迁移、奴仆、官禄、田宅、福德、父母。

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

宫干由年干经五虎遁定寅宫干（甲己起丙寅、乙庚起戊寅、丙辛起庚寅、丁壬起壬寅、戊癸起甲寅），
其余各宫顺十天干排布（《起五行寅例》）。闰月出生按具名口径取有效生月（`effective_month`）：
《全书》以闰月全月归下月；LifeDNA 列全月归本月与十六日起算次月两种。闰十二月按归下月口径
没有对应命宫月（不合成「来年正月」的无出处规则），`effective_month` 显式失败。

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
