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

`gregorian_to_lunar` 用出生地当地民用日标签（真太阳时路径取真太阳钟民用日）换算；超出算法覆盖范围时显式失败。
`validate_lunar_date` 核对该闰月／日组合在所选算法中存在；`lunar_to_gregorian` 反向换算，组合不存在时显式失败。
可确认的范围／组合错误抛`ValueError`；年历查询及原生转换的内部故障原样传播，不伪装成输入错误。
公历可表示区间由首个农历年的首日及末个农历年的各月长确定，不等于表中的公历元旦至除夕。
晚子时顺延时只检验最终取用的日标签；未取用的前一日不必在范围内。

## 时标合同

celestial 的节气时刻是 UT1，民用输入是 UTC 或固定偏移；两者不直接比较钟面数值。

- `utc_to_ut1_jd` 把 UTC 瞬间按 modelled-UT1 定义换算到 UT1 日数：
  TT=UTC+(ΔAT+32.184s)，UT1=TT-ΔT；ΔAT 取 1972 年起闰秒表（2017-01-01 后恒 37 秒），
  ΔT 取 celestial 的 DEFAULT（ALGO5）模型并在 TT 处估一次。该定义与
  `chart_snapshot` 返回的 `jd_ut1` 在 1972–2099 网格上一致（亚毫秒级）。
- `lichun_jd` 返回所选公历年立春的 UT1 日数，直接与出生瞬间的 UT1 日数比较。
- 立春比较左闭右开：出生瞬间等于立春时刻归新年。换年判定见[解析层](resolver.md)。
- 1972 年前的 UTC 时刻由解析层拒绝；不做现代 UTC 规则的向前外推。

## 真太阳时

`apparent_solar` 以 UTC 民用时刻与东经经度换算当地真太阳钟（年月日与当日小数）。
解析层给经度时才走真太阳时路径，取时辰用真太阳钟；两种路径都记入结果。

```{doctest}
>>> from datetime import UTC, datetime
>>> from ziwei.calendar import apparent_solar
>>> apparent_solar(datetime(2024, 2, 4, 12, tzinfo=UTC), 120.0)
(2024, 2, 4, 0.8237...)
```
