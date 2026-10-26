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
>>> leap = catalog.get("entry.leap-month.month-stars-scope")
>>> leap.alternatives
('闰月例只约束命宫与身宫', '闰月例同时约束其他月系星')
>>> leap.chart_match
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
`filter_sources()`可按核验状态、支持层次或谱系键过滤。标识参数不是字符串时抛`TypeError`，
格式非法（如`Nope`）抛`ValueError`，格式合法但不存在（如`entry.unknown`）抛`KeyError`。
带记录种类要求的查询参数若指向另一种记录，也会抛`ValueError`，例如概念参数传入来源标识。
`get()`本身不限制记录种类；查询不按名称替代标识，其他无效值也显式失败。
概念过滤和引用查询包含条目直接关联的概念，以及关联变体所属的概念和流派；
不递归展开概念之间的相关链接。
记录和目录会把输入序列复制成元组；修改调用方原列表不会改动已经构造的目录。

默认展示指`filter_entries(default_only=True)`筛出的条目，条件见[状态说明](#状态需要分开表达)。
当前内置条目均不进入默认展示：有的只核到电子录文或转录页，有的前提尚待裁定，有的只有一路独立出处。
规则可以执行不等于对应条目可以默认展示；`filter_entries()`默认检索全部条目，
所以仍能比较分歧与查看待决材料。
即使调用方构造了符合默认展示条件的条目，`chart_match`仍恒为未评估；目录不接收或判定命盘。

例如，[月支天马](knowledge-reference.md#entry.tianma.month-branch)按所见网页的农历生月口径登记；
[闰月例能否用于同书其他安星段落](knowledge-reference.md#entry.leap-month.month-stars-scope)仍保留两种读法。
本项目让左辅右弼、月马和命宫使用同一种闰月处理方式，调用者可在三种闰月归属选项中选择，
另记为[项目组合](knowledge-reference.md#entry.star.month-policy-composition)。这项实现选择不用于判定古籍原意。
[晚子时归次日](knowledge-reference.md#entry.day-rollover.late-zi)登记项目已有选项，但不编造其外部出处。
[换年](knowledge-reference.md#concept.policy.year-boundary)区分正月初一与立春：前者记录《精成》网页的春节生年句，
后者只登记项目已有选项。历书能给立春时刻，不能证明术数应采用立春换年。
待决条目保存具体复核动作（`recheck`）与跟进讨论入口（`tracking_url`）；issue关闭不表示争议已经解决。
`RuleVariant.tracking_url`保留实现议题的历史链接；火铃异读、相关称名、归月范围与换年／子时出处等未决事项，由
[来源研究](https://github.com/0xf3cd/ziwei/issues/43)跟进，不把实现交付当作文献结论。

## 记录与归属

概念、规则变体、来源、引文与知识条目使用稳定、与语言无关的标识。

### 标识与命名

记录标识使用小写ASCII字母、数字、点与连字符，以字母开头。
点和连字符都用于分段，各段不能为空。
新增记录先按种类选择`concept.`、`variant.`、`source.`、`citation.`或`entry.`前缀，
再按领域、对象或规则差异分段。例如，`concept.star.ziwei`指紫微这一星曜概念，
`variant.star.ziwei-bureau-day`指按五行局与农历日安紫微的规则；它们不是显示名称或Python成员名。
来源谱系的归组标识另用`lineage.`前缀。

已有标识不因显示名称、简繁字形、Python成员名或别名变化而改变，也不按列表序号生成。
星曜概念的标识由`Star.concept_id`显式声明。
[安星结果](stars.md)中的`StarPlacement.rule_id`保存所用规则的标识，与知识目录中相应规则变体的标识一致。
修改解释措辞不另建身份；新增含义不同的概念或规则时分配新的标识，不把旧标识改用于另一种含义。

### 记录分工

| 记录 | 保存什么 |
|---|---|
| 概念 | 身份、种类（星曜、宫位、四化、五行局、口径、流派）、名称与别名、相关概念 |
| 规则变体 | 定义、所属流派、适用范围与条件；可执行时链接实现中的表或函数 |
| 来源 | 书名或作者、版本或刊本、文本层（见 `TextLayer`）、来源谱系、支持的论断与限度 |
| 引文 | 来源中的具体定位、逐字原文、该处文本层、支持层次与限度 |
| 知识条目 | 陈述、关联概念／规则／来源、前提、例外、限度及整理状态 |

可执行常量与规则表归领域实现。知识条目链接规则标识，生成的参考表读取可执行定义。
解释文字说明原因与范围，不维护第二份安星表。
十二宫顺序、五虎遁与五局名称的完整复述直接消费所属领域值；纳音短例仍是解释性示例，另核示例元素。
来源原引不随项目定义变化改写。安星数值参考的覆盖检查按规则及星曜核至少一行，不把规则声明行当数值行；
它能发现整组缺失，不独立证明组内每个日期或月份都齐全。

当前schema中，`Source`保存版本、谱系、权利与总体支持范围；`Citation`保存具体定位、原引文、
支持层次、该处文本层与限度；同一来源的原文与注文可分别标记。同一本资料的多处引文共享来源，不复制一份版本信息。
`KnowledgeEntry.statement`保存整理者的陈述；逐字原文单独保存在`Citation.quote`。
`RuleVariant.option`只关联闰月归属、子时换日和换年界线的枚举选项；`implementation`可保存已实现规则的公开对象路径，
查询时不动态导入或运行。28星的概念标识、规则标识、公开实现链接从`stars`定义引用，
完整四化表与大限也链接所属模块的执行入口；既有单行四化异文和魁钺古籍异文仍保留`implementation=None`，
不因某行与执行表相同就改变原记录的含义。完整表、盘例与转录限度见[四化与大限](sihua-decades.md)。
口径概念的`options`从配置定义取值；目录拒绝把变体链接到该概念之外的配置选项。
[口径选项及六十甲子参考](knowledge-reference.md#implemented-policies)直接读取现有定义。

原文引述、今人说明、仓内原作说明是不同文本层。同一祖本的多份转抄不构成独立来源；
措辞逐字相同的两处只算一路。保留原文措辞与定位，记录收录材料的转载权限。

## 来源与规则的三层问题

一条安星规则绑着三个可以分开回答的问题，一份来源常常只定其中一个：

1. **系统归属**：这条规则属于紫微斗数，还是同名星曜在其他术数中的规则。
2. **规则**：表、偏移、组合条件。
3. **查法**：锚在年干、年支、生月还是生时；安在十二宫的哪一类位置。

记录每份来源说明了哪一层、没有说明哪一层。原文未写是否把起始宫位算作第一宫时，须通过例解判断；
找不到例解就并列保留两种读法。同名异物、转抄冒充独立来源、底本差异都可能改变结论。
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

来源状态只回答所列版本是否已核：维基文库的固定修订可以标为已核，而它的底本仍可能未确认；
转录页的文字可已读，但原著版本未核时继续标待核。谱系键仅用于归并同路材料，不计算独立来源数。
默认展示须由整理者显式指定，且前提明确、整理完成、引文所指来源已核；这些检查仍不证明某张盘满足前提。

### 首批材料的限度

- 维基文库《紫微斗數全書/卷二》固定修订`1963110`，实际正文为简体录文；没有确认其纸本底本。
  原字如天马句中的“戍”保留不改，不能用相同书名抹平不同四化口诀。
- golla《紫微斗數精成》与读书网《九千飞星》只作转录线索，原著版次、部分作者归属与转载许可未核。
  九千所列流派标签只记录为作者说法，不认证整个流派。
- LifeDNA作者站只证明其页面主张。页面转引古籍的历史论证未回原典，也未实测该站排盘算法。
  第2节列出本月、次月、前后半月三种闰法，自述采用第三种；第1节反对立春换年、第3节反对23点加日，
  两项意见单独登记，不作为本项目同名选项的支持出处，也不推广成流派共识。
- 新浪讲义正文核自2017-11-06网页存档，现页未取得正文。该存档的正文可核局数起限，
  2026-10-25指定图片存档请求返回404，图四图题与图内岁数尚未取得图像核对；不能以正文可读代替图像核验。

公开语料只收必要短引和仓内说明，不转载现代全文；没有原文的地方保留空引用及具体检索动作，
不写成“古籍没有”。查询条目本身不执行四化、天马或归月换日计算。

### 安星材料的限度

本节所说的《全书》是维基文库《紫微斗數全書/卷二》固定修订1963110；中州派讲义指王亭之
《紫微斗数初级讲义》及同路网页转录；《精成》指《紫微斗數精成》网页。星侨网站的安星诀与讲义多处同文，
不另算独立传承。

- 主星逐日宫格与偏移、辅弼昌曲、禄存羊陀、空劫，以电子《全书》和中州派讲义的不同口诀、例解对照；
  讲义与星侨多处同文，视作同一路文本，不把网址数量当独立传承数。
- [五术书社转录](knowledge-reference.md#source.zhongzhou-5shubook)定位到讲义第6至13、18条，
  与[新浪博客转录](knowledge-reference.md#source.zhongzhou-wangtingzhi)使用同一个来源谱系标识。原书版次、OCR转录是否忠实、
  转载授权均未核实，来源仍标为待核。条号和印刷页码取自网页页眉；未见纸本，不能确认完整章节。
  博客没有收录的章节也不归给博客。《全书》逐日宫格的缺失与歧义见[引文限度](knowledge-reference.md#citation.quanshu.ziwei-daily)。
- 魁钺只执行现代表；电子《全书》的虎马、猪狗等原字另存[待核异文](knowledge-reference.md#entry.star.kuiyue-quanshu-pending)，
  给出取得底本影像和另一有明确版次的古籍同段的复核动作。现代表多见同族歌诀，不声称每种异文各有两路独立出处。
- 《全书》火铃段只列年支四组与宫位，未明说子时起数、随生时移动或方向；本项目的子时起数、
  两星顺数到生时，依据讲义例解、《精成》与论坛明文。论坛还转述并反对未具名资料中不论生时的查法，
  [该异读](knowledge-reference.md#entry.star.huoling-year-only-pending)仍待取得底本或例解，不用作者评价裁定古籍原意。
- 时系地空的称名分别记来源：《全书》称天空，讲义称地空，论坛今人按语称天空又名地空。
  这些称名不建立全局别名，也不把按年支安的另一颗天空并入；同文转抄不增加独立出处。
- 月马见于《精成》与论坛两页明文；三合月口诀同文，按一路文本计，传承关系与原书版本未核。
  仍作为可选的安星规则提供，但条目暂不默认展示。
  默认使用年马、允许选月马，都不会把未核实的来源改标为已核。
