# 历法与时间

[API 参考](api.md#历法适配) · [解析层](resolver.md) · [项目入口](../README.md)

历法换算与节气时刻由 [celestial-calendar](https://github.com/0xf3cd/celestial-calendar)
提供；本页说明适配层对外承诺的农历算法、时标合同与真太阳时。导入本包与查询知识不会初始化
celestial 原生库，适配函数在首次调用时才加载它。

## 农历算法

三种算法为具名选项，随解析结果保存；选择按来源与兼容角色，不按假设的精度排名：

| 算法 | 农历年范围 | 角色 |
|---|---|---|
| `ALGO1` HKO 表 | 1901–2099 | 香港天文台日期标签兼容 |
| `ALGO2` 天文计算 | 410–2500 | 更宽的计算窗口 |
| `ALGO3` 混合 | 1600–2199 | 默认：1901–2099 与 HKO 表一致 |

`resolve()`与`create_chart()`的`lunar_algorithm`参数不传时取`ALGO3`，这是解析入口参数中唯一有默认值的一项；
闰月归属、子时换日和换年仍须显式指定。`ChartConfig.tianma_rule`另有按年支安天马的默认值，见[安星](stars.md)。

`gregorian_to_lunar`消费最终取用的日期标签：解析层先选当地民用钟或真太阳钟的日期，再按该钟应用子时换日。
超出算法覆盖范围时显式失败。
`validate_lunar_date` 核对该闰月／日组合在所选算法中存在；`lunar_to_gregorian` 反向换算，组合不存在时显式失败。
范围／组合错误抛`ValueError`；年历查询及原生转换的计算、资源或内部故障以`celestial_calendar.CelestialError`原样传播。
公历可表示区间由首个农历年的首日及末个农历年的各月长确定；上表列的是农历年范围，不是同年份的公历1月1日至12月31日。
晚子时顺延时只检验最终取用的日标签；未取用的前一日不必在范围内。

## 时标合同

celestial 的节气时刻是 UT1，民用输入是 UTC 或固定偏移；两者不直接比较钟面数值。

- `utc_to_ut1_jd` 把 UTC 瞬间按 modelled-UT1 定义换算到 UT1 日数，
  使用上游的`utc_to_jde`、`jde_to_ut1`与`ut1_to_jd`，ΔT固定使用ALGO5。
- `lichun_jd` 返回所选公历年立春的 UT1 日数，直接与出生瞬间的 UT1 日数比较。
- 立春比较左闭右开：出生瞬间等于立春时刻归新年。换年判定见[解析层](resolver.md)。
- UTC转UT1与民用时刻解析都拒绝1972年前的UTC瞬间；下界按UTC而非转换后的UT1日期判断。
  无需瞬间的纯民用排盘不受此下界限制。上游对1972年前输入给出的是UT1替代值，并非历史UTC；本仓仍拒绝这类UTC输入。

闰秒表由上游维护；自2017-01-01起沿用TAI−UTC=37秒，不预测未来闰秒。
Python `datetime`不能表达`23:59:60`，接口不接受闰秒本秒。
此处返回的是模型化UT1，不是实测UT1。上游的闰秒、舍入与逆转换约定见
[UTC转换说明](https://github.com/0xf3cd/celestial-calendar/blob/v1.1.1/docs/UTC_CONVERSIONS.md)。

## 真太阳时

`apparent_solar` 以 UTC 民用时刻与东经经度换算当地真太阳钟（年月日与当日小数）。
解析层给经度时才走真太阳时路径，取时辰用真太阳钟；两种路径都记入结果。

```{doctest}
>>> from datetime import UTC, datetime
>>> from ziwei.calendar import apparent_solar
>>> apparent_solar(datetime(2024, 2, 4, 12, tzinfo=UTC), 120.0)
(2024, 2, 4, 0.8237...)
```
