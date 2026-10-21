# 五行局

[API 参考](api.md#五行局) · [命宫身宫与十二宫](palaces.md) · [项目入口](../README.md)

五行局由命宫干支的纳音五行定：水二局、木三局、金四局、土五局、火六局；
局数即首限起始虚岁，区间与顺逆见[四化与大限](sihua-decades.md)。

- 纳音五行表（六十甲子两两一组）见[知识参考](knowledge-reference.md#implemented-nayin)，
  元素取自《紫微斗數全書》卷二纳音歌（维基文库修订1963110）与《渊海子平》卷一纳音注解；
  纳音歌物名异文（如剑峰金）不进入计算。
- 《全书》安身命例以「丙寅丁卯炉中火，却去火局」示范命宫干支断局；王亭之中州派讲义
  定五行局节同列五局。

```{doctest}
>>> from ziwei.bureau import WuxingJu, bureau_of
>>> from ziwei.ganzhi import Ganzhi
>>> bureau_of(Ganzhi.from_str("丙寅"))
<WuxingJu.HUO_LIU: '火六局'>
>>> bureau_of(Ganzhi.from_str("甲子"))
<WuxingJu.JIN_SI: '金四局'>
>>> WuxingJu.MU_SAN.number
3
```
