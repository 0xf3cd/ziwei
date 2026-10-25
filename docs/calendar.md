# 历法与时间

[API 参考](api.md#历法适配) · [解析层](resolver.md) · [项目入口](../README.md)

历法换算与节气时刻由 [celestial-calendar](https://github.com/0xf3cd/celestial-calendar) 0.8.0
提供；本页说明适配层对外承诺的农历算法、时标合同与真太阳时。导入本包与查询知识不会初始化
celestial 原生库，适配函数在首次调用时才加载它。

## 农历算法

三种算法为具名选项，随解析结果保存；选择按来源与兼容角色，不按假设的精度排名：

| 算法 | 农历年范围 | 角色 |
|---|---|---|
| `ALGO1` HKO 表 | 1901–2099 | 香港天文台日期标签兼容 |
| `ALGO2` 天文计算 | 410–2500 | 更宽的计算窗口 |
| `ALGO3` 混合 | 1600–2199 | 默认：1901–2099 与 HKO 表一致 |

`gregorian_to_lunar`消费最终取用的日期标签：解析层先选当地民用钟或真太阳钟的日期，再按该钟应用子时换日。
超出算法覆盖范围时显式失败。
`validate_lunar_date` 核对该闰月／日组合在所选算法中存在；`lunar_to_gregorian` 反向换算，组合不存在时显式失败。
可确认的范围／组合错误抛`ValueError`；年历查询及原生转换的内部故障原样传播，不伪装成输入错误。
公历可表示区间由首个农历年的首日及末个农历年的各月长确定；上表列的是农历年范围，不是同年份的公历1月1日至12月31日。
晚子时顺延时只检验最终取用的日标签；未取用的前一日不必在范围内。

## 时标合同

celestial 的节气时刻是 UT1，民用输入是 UTC 或固定偏移；两者不直接比较钟面数值。

- `utc_to_ut1_jd` 把 UTC 瞬间按 modelled-UT1 定义换算到 UT1 日数：
  TT=UTC+(ΔAT+32.184s)，UT1=TT-ΔT；ΔAT取内置历史表，ΔT取celestial的DEFAULT（ALGO5）模型并在TT处估一次。
- `lichun_jd` 返回所选公历年立春的 UT1 日数，直接与出生瞬间的 UT1 日数比较。
- 立春比较左闭右开：出生瞬间等于立春时刻归新年。换年判定见[解析层](resolver.md)。
- UTC转UT1与民用时刻解析都拒绝1972年前的UTC瞬间，不向前外推现代UTC规则；无需瞬间的纯民用排盘不受此下界限制。

内置偏移表参照[IERS生效日与TAI−UTC表](https://hpiers.obspm.fr/iers/bul/bulc/Leap_Second.dat)，
以[NIST闰秒插入日](https://www.nist.gov/pml/time-and-frequency-division/time-realization/leap-seconds)的次日交叉核对。
1972-01-01的10秒是基线，其后27次正闰秒把偏移增至2017-01-01的37秒。
更晚日期沿用最后已知偏移是本实现的计算假设，不表示未来不会增加闰秒。
Python `datetime`不能表达`23:59:60`，接口不接受闰秒本秒；测试用可表示的边界前一秒、生效时刻与后一秒核偏移。
1972基线行的前一秒由公开入口的下界检查拒绝。

模型对照只用了1972、1975、1988、2000、2017、2024、2050、2099年的八个选定时刻，
与celestial的`chart_snapshot`计算结果比较，最大差约40.23微秒，回归阈值取10毫秒。
两者共用celestial的ΔT模型，因此这一对照不是独立参考。
这不保证1972–2099年每个时刻的精度，也不是实测UT1；独立历史表的逐边界检查另核偏移与生效日期。

## 真太阳时

`apparent_solar` 以 UTC 民用时刻与东经经度换算当地真太阳钟（年月日与当日小数）。
解析层给经度时才走真太阳时路径，取时辰用真太阳钟；两种路径都记入结果。

```{doctest}
>>> from datetime import UTC, datetime
>>> from ziwei.calendar import apparent_solar
>>> apparent_solar(datetime(2024, 2, 4, 12, tzinfo=UTC), 120.0)
(2024, 2, 4, 0.8237...)
```
