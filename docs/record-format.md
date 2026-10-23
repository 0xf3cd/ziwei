# schema 1 字段参考

[完整命盘与记录](chart.md) · [API](api.md#完整命盘记录与显示)

本页列出 schema 1 的全部对象键。每个对象都须包含所列键，不接受额外键、重复键或错类型。
`null` 只在明确标记“可空”的字段使用；整数不接受 bool，数值只接受有限值。
枚举字符串使用对应领域枚举的线上中文值，Python 别名不另生线上值。

## 顶层

| 键 | JSON 类型 | 含义与约束 |
|---|---|---|
| `schema_version` | 整数 | 固定为 1；决定读取、字段与组件核验，不等于软件版本 |
| `software_version` | 字符串 | 非空的生成软件版本，恢复保留；不选算法或规则 |
| `record` | 对象 | 下述两种出生记录之一 |
| `calculation` | 对象 | 已解析输入及生成元数据 |
| `palaces` | 对象数组 | 十二宫，按宫名序 |
| `shengong` | 字符串 | 身宫地支 |
| `bureau` | 字符串 | 五行局 |
| `stars` | 对象数组 | 已发布 28 星及固定顺序，不由当前枚举长度推得 |
| `sihua` | 对象 | 具名生年四化 |
| `decades` | 对象数组 | 十二限，按起限先后 |

## 原始记录与时区

两种 `record` 都含以下键：

| 键 | 类型／可空性 | 单位与含义 |
|---|---|---|
| `calendar` | 字符串 | `公历` 或 `农历`，选择下列不同键集 |
| `gender` | 字符串 | `Gender` 值，完整盘须已知 |
| `longitude_deg` | 数值，可空 | 东经为正，单位度，-180 至 180；保留整数／浮点及 -0.0 |
| `place`、`source` | 字符串，可空 | 地点、来源原文；字符边界见[记录指南](chart.md#json-schema与版本) |

公历记录另含：

| 键 | 类型／可空性 | 单位与含义 |
|---|---|---|
| `birth_date` | 字符串 | 规范 ISO 日期 `YYYY-MM-DD` |
| `birth_time` | 字符串，可空 | 不带时区或 fold 的规范 ISO 钟点，最多微秒；完整盘须已知 |
| `time_precision` | 字符串 | `TimePrecision` 值，钟点不得含更低精度分量 |
| `timezone` | 对象 | IANA 请求或固定偏移 |

农历记录另含：

| 键 | 类型／可空性 | 单位与含义 |
|---|---|---|
| `year`、`month`、`day` | 整数 | 农历年 1–9999、月 1–12、日 1–30；存在性由重算认证 |
| `is_leap_month` | bool | 是否闰月 |
| `shichen` | 字符串，可空 | 时辰地支；完整盘须已知 |

IANA `timezone` 恰含 `kind`（固定 `IANA`）、`key`（相对时区标识字符串）、`fold`
（整数 0／1 或 `null`，表示请求的重叠选择）。固定偏移对象恰含 `kind`（固定 `固定偏移`）和
`offset_microseconds`（整数微秒，绝对值小于 24 小时），没有 `fold`。

## 计算输入

| `calculation` 键 | 类型／可空性 | 单位与含义 |
|---|---|---|
| `lunar_year`、`month`、`day` | 整数 | 解析后的农历年月日，值域同农历记录 |
| `is_leap_month` | bool | 解析后的闰月标志 |
| `shichen` | 字符串，可空 | 解析后的时辰；完整盘须已知 |
| `ganzhi_year` | 整数 | 所选换年口径下的纪年编号，不一定等于农历年 |
| `config` | 对象 | 恰含 `leap_month_policy`、`day_rollover`、`year_boundary`、`tianma_rule` 四个字符串；分别为对应具名枚举值 |
| `lunar_algorithm` | 字符串 | `LunarAlgorithm` 线上值 |
| `lunar_algorithm_version` | 字符串 | 非空 celestial 版本；重算要求确切匹配 |
| `supported_lunar_year_range` | 整数数组 | 两个闭区间端点，有序、1–9999 且包含 `lunar_year`；生成时快照，不认证来源真实性 |
| `apparent_solar` | bool | 是否采用真太阳时 |
| `day_rolled` | bool | 是否按晚子时归次日顺延 |
| `ut1_jd`、`lichun_jd` | 浮点，可空 | 出生瞬间与该年立春的 UT1 儒略日，单位日；立春比较路径两者都须存在，纯民用路径为 `null` |
| `resolved_time` | 对象，可空 | 需要瞬间的公历路径保存以下对象，其余为 `null` |

`resolved_time` 恰含：

| 键 | 类型／可空性 | 单位与含义 |
|---|---|---|
| `local_time` | 字符串 | 不带时区／fold 的规范 ISO 日期时间，最多微秒 |
| `utc` | 字符串 | 带 `+00:00` 的规范 ISO 日期时间，最多微秒，1972 年起 |
| `offset_microseconds` | 整数 | 钟面减 UTC，单位微秒，绝对值小于 24 小时 |
| `fold` | 整数 | 实际重叠分支 0／1，不替换原记录中的请求值 |
| `data` | 对象，可空 | IANA 时含 `package_version` 和 `iana_version` 两个非空字符串；固定偏移时为 `null` |

## 组件

| 对象 | 全部键、类型与单位 |
|---|---|
| `palaces` 每项 | `dizhi`、`tiangan`、`name` 三个字符串，分别为地支、天干、宫名枚举值 |
| `stars` 每项 | `star`、`dizhi`、`rule_id` 三个字符串，分别为星曜、地支和该星实际采用的稳定规则标识 |
| `sihua` | `year_tiangan`、`variant`、`rule_id`、`lu`、`quan`、`ke`、`ji` 七个字符串，分别为生年干、具名完整变体、规则标识与四颗星曜 |
| `decades` 每项 | `dizhi`、`direction`、`rule_id`、`age_convention` 为字符串；`start_age`、`end_age` 为整数虚岁，首尾包含。年龄约定固定为 `虚岁` |

## 演进与迁移

| 变化 | 处理办法 |
|---|---|
| 软件修复而 JSON 形状、规则含义不变 | 不为软件版本号升 schema；生成版本仍单独保存 |
| 新增字段、星曜或组件，改变记录形状 | 升 schema 并提供对应读取和核验；schema 1 仍按旧 28 星恢复，不补新值 |
| 改执行规则含义 | 新规则 ID，并保留旧记录需要的实现；不能用软件版本猜规则 |
| 新增 Python 别名或显示名 | 不改变原 JSON 字面量、concept_id 或 rule_id；存量标识不随拼音重命名 |
| 需要转换旧文件 | 提供显式迁移，保留原记录并说明每个字段的转换；不能以重排盘或补星冒充恢复 |
| 依赖版本或当前支持范围变化 | 恢复仍保留快照；重算另查版本与当前能力，不能静默替换算法 |

本版没有改变 JSON 形状，因此仍写 schema 1，没有空的 schema 2 读取器或迁移入口。
未知版本先给调用方可识别的版本异常，不尝试按当前字段猜读。
