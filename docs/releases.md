# 版本变化

[项目入口](../README.md) · [完整命盘与盘面](chart.md) · [发布操作与失败处理](releasing.md)

本页记录各版本源码的功能与兼容变化。是否已经公开发行，以
[PyPI](https://pypi.org/project/ziwei/)和[GitHub Releases](https://github.com/0xf3cd/ziwei/releases)为准。

## 0.4.0（开发中）

### 改进

- 精简工具链自测中的重复文档构建与发布脚本用例；真实文档导出、发布身份和制品字节检查保留。
- 重复的星数断言改从星曜枚举派生，只保留一处字面星数检查；README安装示例不再钉项目版本。
- 补充按星名查询规则与出处的示例、主星名单和批量亮度查询入口，以及命盘相等性所包含的原始记录。

### 兼容变化

- 删除`ziwei.knowledge.data.CATALOG_VERSION`和`Catalog.version`，构造目录不再接收`version=`。
  语料变化由源码提交与发行版本定位；来源版次、核验日期和快照摘要保留。
- 删除`KnowledgeEntry.chart_match`；目录仍只提供独立知识查询，不判定某张命盘是否满足条目前提。
- 删除`LiunianYear.precision`；区间端点仍为`date`，日期年界与输入要求不变。
- 删除`DisplayEligibility`枚举，将`KnowledgeEntry.display`改为必填的`show_by_default: bool`。
  原`可默认展示`对应`True`，`暂不默认展示`对应`False`；默认展示仍须前提明确、整理完成并引用已核来源。
- `filter_entries()`删除`display=`与`default_only=`参数，改用`show_by_default=`：
  `None`（默认）不按展示资格筛选，`True`只取可默认展示条目，`False`只取暂不默认展示条目。
  原`default_only=True`改写为`show_by_default=True`；原`default_only=False`改写为不传该参数或传`None`，
  不应改成`show_by_default=False`。字段与查询不接受整数或字符串代替布尔值。

本次不改变排盘规则、数值、依赖版本或公开结果的构造校验。

## 0.3.0

### 新增与改进

- **红鸾／天喜**：完整星集由28星增至30星，按年支安入，文本和SVG盘面随之显示两星。
  用法与规则来源见[30星安星](stars.md)。
- **十四主星七级亮度**：提供《紫微斗数全书》卷二固定电子录文的具名表，按已有星位查询；
  文本与SVG可显式选择显示亮度，不改变安星位置。表的范围、校异与底本限度见[亮度指南](brightness.md)。
- **第一层流年**：`liunian_minggong()`按已确定纪年定位命宫；`liunian_on_date()`按显式选择的
  正月初一日期或立春日期确定纪年及`[start, end)`区间。与本命盘叠读可组合已有`palace_view()`，
  不给本命结果增加字段。输入、范围及日期基准见[流年指南](liunian.md)。
- **组合与验证说明**：明确工厂与公开直接构造各自核验的关系，保留原有构造行为；
  两星、亮度和流年分别增加有出处的离线对照，外部观测与项目采用预期分开保存。

### 兼容与范围

- 依赖完整星集数量为28的调用方需适配30星；原星曜身份与规则标识保留。
- 流年年界不设默认，也不继承本命配置。日期查询只接收`date`，拒绝`datetime`；
  立春日期把所在整日归新年，不提供交接瞬间查询。本命立春换年仍按瞬间处理。
- 亮度表的纸本底本仍未核定，流年仍缺独立完整生辰盘与专业软件原始样本。
  来源单元测试、安装消费和合成组合不作为独立整盘认证，见[亮度指南](brightness.md)及
  [流年验证限度](liunian.md#来源与验证限度)。
- 依赖版本与支持平台不变，见[安装要求](../README.md#安装要求)。
  本版不增加小限、流月、流日、流曜或运限四化。

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
  既有稳定标识与中文别名保留，不把未核实出处标成定论，见[知识组织](knowledge.md)。

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
