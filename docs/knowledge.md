# 知识组织与来源

[项目入口](../README.md) · [结构设计](architecture.md) · [参与开发](contributing.md)

本仓同时服务排盘与知识学习。查询知识不应要求先有命盘、出生资料或已加载的 celestial 原生库。

## 查询目录与出处

当前提供独立知识查询及与安星实现的关联，不做命盘匹配。目录加载只构造不可变记录，不读取出生资料、
时区数据或原生历法库。完整记录与稳定链接见[知识参考](knowledge-reference.md)，签名见[API](api.md#独立知识目录)。
加载入口为`ziwei.knowledge.load_catalog`，每次调用新建目录；记录与枚举从`ziwei.knowledge.model`导入，
目录类型从`ziwei.knowledge.catalog`导入。这些模块路径均为公开API。

```{doctest}
>>> from ziwei.knowledge import load_catalog
>>> from ziwei.knowledge.model import PremiseStatus, DisplayEligibility, SourceStatus
>>> catalog = load_catalog()
>>> catalog.find("天馬")[0].id
'concept.star.tianma'
>>> [item.id for item in catalog.find("庚干四化")]
['variant.sihua.geng-wikisource', 'variant.sihua.geng-jiuqian-quanshu', 'variant.sihua.geng-jiuqian-zhongzhou']
>>> pending = catalog.filter_entries(premise_status=PremiseStatus.待定)
>>> pending[0].alternatives
('闰月例只约束命宫与身宫', '闰月例同时约束其他月系星')
>>> pending[0].chart_match
'未评估'
>>> reference = catalog.references("entry.tianma.year-branch")[0]
>>> reference.quote
'论本生年支'
>>> catalog.get(reference.source_id).status is SourceStatus.已核
True
>>> catalog.filter_entries(default_only=True)
()
```

`find()`查完整名称及显式别名，忽略首尾空白与大小写，歧义返回全部匹配，不静默取第一条。
`list_concepts()`可按种类过滤；`list_variants()`可按概念或流派过滤。`filter_entries()`的条件取交集，
`filter_sources()`可按核验状态、支持层次或谱系键过滤。未知标识抛`KeyError`，错类引用或无效值显式失败。
概念过滤和引用查询同时包含条目直接关联的概念、其具名变体的概念与流派；不递归展开概念之间的相关链接。
记录和目录会把输入序列复制成元组；修改调用方原列表不会改动已经构造的目录。

当前内置条目均暂不进入默认展示：有的只核到电子录文或转录页，有的前提尚待裁定，
有的采用单源执行例外。可执行资格不自动授予默认知识展示；`filter_entries()`默认检索全部条目，
所以仍能比较分歧与查看待决材料。
即使调用方构造了符合默认展示条件的条目，`chart_match`仍恒为未评估；目录不接收或判定命盘。

例如，[月支天马](knowledge-reference.md#entry.tianma.month-branch)按所见网页的农历生月口径登记；
[闰月例的跨段适用范围](knowledge-reference.md#entry.leap-month.month-stars-scope)仍保留两读。
本项目已明确选择辅弼、月马统一组合三归月口径，另记为[项目组合](knowledge-reference.md#entry.star.month-policy-composition)，
不借这项选择裁定古籍争议。
[晚子时归次日](knowledge-reference.md#entry.day-rollover.late-zi)登记项目已有选项，但不编造其外部出处。
待决条目保存具体复核动作（`recheck`）与跟进讨论入口（`tracking_url`）；issue关闭不表示争议已经解决。

## 记录与归属

概念、规则变体、来源与知识条目使用稳定、与语言无关的标识。

| 记录 | 保存什么 |
|---|---|
| 概念 | 身份、种类（星曜、宫位、四化、五行局、口径、流派）、名称与别名、相关概念 |
| 规则变体 | 定义、所属流派、适用范围与条件；可执行时链接实现中的表或函数 |
| 来源 | 书名或作者、版本或刊本、定位、文本层（见 `TextLayer`）、来源谱系、支持的论断与限度 |
| 知识条目 | 陈述、关联概念／规则／来源、前提、例外、限度及整理状态 |

可执行常量与规则表归领域实现。知识条目链接规则标识，生成的参考表读取可执行定义。
解释文字说明原因与范围，不再维护第二份安星表。

当前schema中，`Source`保存版本、谱系、权利与总体支持范围；`Citation`保存具体定位、原引文、
支持层次、该处文本层与限度；同一来源的原文与注文可分别标记。同一本资料的多处引文共享来源，不复制一份版本信息。
`KnowledgeEntry.statement`保存整理者的陈述；逐字原文单独保存在`Citation.quote`。
`RuleVariant.option`只链接三个历法口径枚举；`implementation`可保存已实现规则的公开对象路径，
查询时不动态导入或运行。28星的概念标识、规则标识、公开实现链接从`stars`定义引用，
没有实现的魁钺古籍异文与四化材料仍保留`implementation=None`。
口径概念的`options`从配置定义取值；目录拒绝把变体链接到该概念之外的配置选项。
[口径选项及六十甲子参考](knowledge-reference.md#implemented-policies)直接读取现有定义。

原文引述、今人说明、仓内原作说明是不同文本层。同一祖本的多份转抄不构成独立来源；
措辞逐字相同的两处只算一路。保留原文措辞与定位，记录收录材料的转载权限。

## 来源与规则的三层问题

一条安星规则绑着三个可以分开回答的问题，一份来源常常只定其中一个：

1. **系统归属**：这条规则属于紫微斗数，还是同名星曜在其他术数中的规则。
2. **规则**：表、偏移、组合条件。
3. **查法**：锚在年干、年支、生月还是生时；安在十二宫的哪一类位置。

记录每份来源定了哪一层、没定哪一层。起算约定（含不含起点）原文未载时，只有例解能裁；
找不到例解就并列保留两读。同名异物、转抄冒充独立来源、底本差异都可能改变结论。
`recheck`写明要取得什么新材料、复核哪一处，不只写“以后再研究”。

## 状态需要分开表达

| 问题 | 字段 | 类型与当前行为 |
|---|---|---|
| 所列出处核实了吗？ | `Source.status` | `SourceStatus`：所列版本已核或版本待核 |
| 条目前提已表达清楚了吗？ | `KnowledgeEntry.premise_status` | `PremiseStatus`：已明确或待定 |
| 条目可以默认展示吗？ | `KnowledgeEntry.display` | `DisplayEligibility`：须显式指定 |
| 某张命盘满足前提吗？ | `KnowledgeEntry.chart_match` | `Literal["未评估"]`：目录不判命盘 |

整理进度另由`KnowledgeEntry.curation`记录。类型说明见[记录类型与状态API](api.md#记录类型与状态)。
`Source.lineage_id`是同路转录材料的归组标识；按它过滤不等于计算独立来源数。

出处核实不能单独证明适用；检索到相关陈述，也不能证明它适用于当前盘。
将来的判别器须区分满足、不满足、未知。只验证部分条件时，只能返回部分证据。

来源状态只回答所列版本是否已核：维基文库的固定修订可已核，而它的底本仍可能未确认；
转录页的文字可已读，但原著版本未核时继续标待核。谱系键仅用于归并同路材料，不计算独立来源数。
默认展示须由整理者显式指定，且前提明确、整理完成、引文所指来源已核；这些检查仍不证明某张盘满足前提。

### 首批材料的限度

- 维基文库《紫微斗數全書/卷二》固定修订`1963110`，实际正文为简体录文；没有确认其纸本底本。
  原字如天马句中的“戍”保留不改，不能用相同书名抹平不同四化口诀。
- golla《紫微斗數精成》与读书网《九千飞星》只作转录线索，原著版次、部分作者归属与转载许可未核。
  九千所列流派标签只记录为作者说法，不认证整个流派。
- LifeDNA作者站只证明其页面主张。页面转引古籍的历史论证未回原典，也未实测该站排盘算法。

公开语料只收必要短引和仓内说明，不转载现代全文；没有原文的地方保留空引用及具体检索动作，
不写成“古籍没有”。查询条目本身不执行四化、天马或归月换日计算。

### 安星材料的限度

本节简称：Q为电子《紫微斗數全書/卷二》固定修订1963110；W为王亭之中州派《紫微斗数初级讲义》
及同路网页转录；J为《紫微斗數精成》网页。星侨安星诀与W多处同文，不另算独立传承。

- 主星逐日宫格与偏移、辅弼昌曲、禄羊陀、空劫以电子《全书》与W讲义不同诀文/例解对照；
  W与星侨多处同文，归同一文本族，不把网址数量当独立传承数。
- W补充转录精确定位讲义第6至13、18条；与既有博客使用同一谱系键。原书版次、OCR忠实度、
  转录授权未核，来源继续待核。条号和印刷页码据网页页眉，未见纸本、不认证完整章节；
  不把博客未覆盖的章节归给博客。Q逐日宫格的缺失与歧义见[引文限度](knowledge-reference.md#citation.quanshu.ziwei-daily)。
- 魁钺只执行现代表；电子《全书》的虎马、猪狗等原字另存[待核异文](knowledge-reference.md#entry.star.kuiyue-quanshu-pending)，
  给出取得底本影像和另一具版次古籍同段的复核动作。现代表多见同族歌诀，不声称异文各有双源。
- 火铃四组起点据Q/W/J；两星同顺的方向证据来自W壬辰卯时例与J明文，Q该段未载方向。
- 月马只核到J一路独立成文，作为具名单源例外可执行；默认年马和默认知识展示资格是两件事。
  选择月马不会把其来源升级为已核。
