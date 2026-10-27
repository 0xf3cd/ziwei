# 版本变化

[项目入口](../README.md) · [完整命盘与盘面](chart.md) · [发布操作与失败处理](releasing.md)

本页记录各版本源码的功能与兼容变化。是否已经公开发行，以
[PyPI](https://pypi.org/project/ziwei/)和[GitHub Releases](https://github.com/0xf3cd/ziwei/releases)为准。

## 0.2.0

### 新增与改进

- **按宫查询**：`ziwei.chart.palace_view()`返回已有命盘中一宫的星曜、生年四化及身宫标记；
  `ziwei.palaces.opposite_dizhi()`与`sanfang_sizheng()`查询对宫和三方四正。用法见[按宫查询](chart.md#按宫读取)。
- **静态SVG**：`ziwei.render.render_svg()`显示十二宫、28星、生年四化、身宫与大限，
  可突出选定宫位的三方四正。原文本盘面保留，见[SVG盘面](chart.md#静态svg)。
- **输入与时间边界**：公开值对象更早拒绝非法类型、值域及字段组合，完整盘进一步核对组件关系。
  民用钟面标签与需要瞬间的消歧路径分别说明，补齐立春、真太阳时跨日和算法范围端点的检查。
  具体行为见[出生输入](birth.md)、[时区与历法](calendar.md)和[解析层](resolver.md)。
- **知识与出处**：参考表消费实际执行定义，补充来源短引、异读与未决前提的说明；
  语料版本为`2026.10.25.1`。既有稳定标识与中文别名保留，不把未核实出处标成定论，见[知识组织](knowledge.md)。

### 兼容变化

- 移除`ziwei.serialization`模块及其`dumps_chart()`、`loads_chart()`，不再读取旧JSON命盘。
  同时移除`ziwei.chart.recalculate()`和`ZiweiChart.software_version`字段。
  不提供替代存储格式、兼容壳或迁移入口；需要新盘时，从原始出生记录与显式口径调用`create_chart()`。
  已发布的0.1.0及其制品不变，旧版JSON文字往返问题保留在[#32](https://github.com/0xf3cd/ziwei/issues/32)，关闭不表示修复该版本。
- 原先可能延后失败的非法值现在会在构造时拒绝；不要依赖无效对象能先构造成功。
  具体校验边界见[组合与失败](architecture.md#组合与失败)。
- 时区资源不可用统一抛`zoneinfo.ZoneInfoNotFoundError`并保留原因。
  直接调用`IanaTimezone.require_resolvable()`且捕获`ValueError`的代码需调整；权限与不相关读取故障仍原样传播。
  独立调用`current_timezone_data()`读取版本时仍保留原异常，见[时区资源错误](calendar.md)。
- `CalculationInput.supported_lunar_year_range`保存所选算法在构造时的支持范围，由构造器取得，
  不是调用者新增的必填参数。直接构造完整盘仍不重新验证公农历对应或时区偏移，应优先使用`create_chart()`。

依赖版本与支持平台不变，见[安装要求](../README.md#安装要求)。本版不扩充星数，不增加格局、运限或吉凶解释。

## 0.1.0

首个公开发行：[PyPI 0.1.0](https://pypi.org/project/ziwei/0.1.0/)与
[v0.1.0 Release](https://github.com/0xf3cd/ziwei/releases/tag/v0.1.0)，
对应源码`206723d794bbf9333062ab0f07beb0d9e4751b2e`。
交付出生输入、历法解析、28星安星、生年四化、大限、完整命盘与文本显示，以及独立知识目录。
