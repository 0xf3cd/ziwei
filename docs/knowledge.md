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
>>> from ziwei.knowledge.model import PremiseStatus, SourceStatus
>>> catalog = load_catalog()
>>> catalog.find("天馬")[0].id
'concept.star.tianma'
>>> [item.id for item in catalog.find("庚干四化")]
['variant.sihua.geng-wikisource', 'variant.sihua.geng-jiuqian-quanshu', 'variant.sihua.geng-jiuqian-zhongzhou']
>>> pending = catalog.filter_entries(premise_status=PremiseStatus.待定)
>>> leap = catalog.get("entry.leap-month.month-stars-scope")
>>> leap.alternatives
('闰月例只约束命宫与身宫', '闰月例同时约束其他月系星')
>>> leap.show_by_default
False
>>> reference = catalog.references("entry.tianma.year-branch")[0]
>>> reference.quote
'论本生年支'
>>> catalog.get(reference.source_id).status is SourceStatus.已核
True
>>> catalog.filter_entries(show_by_default=True)
()
```

`find()`查完整名称及显式别名，忽略首尾空白与大小写，歧义返回全部匹配，不静默取第一条。
`list_concepts()`可按种类过滤；`list_variants()`可按概念或流派过滤。一个变体可以关联多个概念，
例如童限边界变体同时关联“童限”和“童限与大限起运衔接”两个概念，按其中任一概念过滤都会列出它。
已有运行结果时，用结果里的`rule_id`调`get()`直接取得对应变体；`find("童限")`只匹配概念名，不返回边界变体。
`filter_entries()`的条件取交集，
`filter_sources()`可按核验状态、支持层次或谱系键过滤。标识参数不是字符串时抛`TypeError`，
格式非法（如`Nope`）抛`ValueError`，格式合法但不存在（如`entry.unknown`）抛`KeyError`。
带记录种类要求的查询参数若指向另一种记录，也会抛`ValueError`，例如概念参数传入来源标识。
`get()`本身不限制记录种类；查询不按名称替代标识，其他无效值也显式失败。
`concept_id`、`school_id`、`variant_id`、`source_id`等参数接收稳定标识字符串，如`concept.star.wenchang`，
不接收`Star.文昌`或概念对象；按状态或种类筛选的参数仍接收对应枚举成员。
`show_by_default=None`（默认）不按展示资格筛选，`True`只取可默认展示条目，`False`只取暂不默认展示条目。
该参数只接受`bool`或`None`，不把`0`、`1`或字符串转换成布尔值。
概念过滤和引用查询包含条目直接关联的概念，以及关联变体所属的概念和流派；
不递归展开概念之间的相关链接。
记录和目录会把输入序列复制成元组；修改调用方原列表不会改动已经构造的目录。

默认展示指`filter_entries(show_by_default=True)`筛出的条目，条件见[状态说明](#状态需要分开表达)。
当前内置条目均不进入默认展示：有的只核到电子录文或转录页，有的前提尚待裁定，有的只有一路独立出处。
规则可以执行不等于对应条目可以默认展示；`filter_entries()`默认检索全部条目，
所以仍能比较分歧与查看待决材料。
亮度表及校异通过[具名表条目](knowledge-reference.md#entry.brightness.quanshu-juan2)关联原引与来源，
其中固定录文已核、底本未核、讲义图原书待核分别记录；完整范围见[亮度指南](brightness.md)。

例如，[月支天马](knowledge-reference.md#entry.tianma.month-branch)按所见网页的农历生月口径登记；
[闰月例能否用于同书其他安星段落](knowledge-reference.md#entry.leap-month.month-stars-scope)仍保留两种读法。
调用者可分别选择命身与月系归月；月系未另指定时跟随命身，辅弼、月马与刑姚共用月系选择，
见[项目组合](knowledge-reference.md#entry.star.month-policy-composition)及[配置示例](stars.md#归月与失败边界)。
条目并列记录书本上下文和固定软件行为，推荐半月法不改变默认展示资格。
[晚子时归次日](knowledge-reference.md#entry.day-rollover.late-zi)登记项目已有选项，但不编造其外部出处。
[换年](knowledge-reference.md#concept.policy.year-boundary)区分正月初一与立春：前者记录《精成》网页的春节生年句，
后者只登记项目已有选项。历书能给立春时刻，不能证明术数应采用立春换年。
流年的[日期年界](knowledge-reference.md#concept.policy.liunian-year-boundary)另建概念，
不与本命瞬间选项混用：初一有现代作者定义，立春日期只作为固定软件行为支持的具名兼容政策。
[定位规则](knowledge-reference.md#entry.liunian.year-branch)、[历书日期](knowledge-reference.md#source.pmo-calendar-2022)
和软件链的支持层次分别记录；输入基准及范围见[流年指南](liunian.md)。
年度禄羊陀沿用三颗星的概念；[年度规则与出处](knowledge-reference.md#entry.liunian.lucun-yangtuo)说明怎样推算位置，并列出文献例子。
从禄存、擎羊或陀罗的概念查变体时，本命与年度规则分别返回。`find("流禄")`等短名匹配年度规则，
不把流禄登记为化禄。数值见[年度参考表](knowledge-reference.md#implemented-liunian-stars)。
年度十二宫使用[独立的太岁起宫规则](knowledge-reference.md#entry.liunian.twelve-palaces)，
不把旧的命宫落支条目扩成完整十二宫说明。[讲义表的年度四化](knowledge-reference.md#entry.liunian.sihua-wangtingzhi-lecture)
分别关联完整表、年度查法与直接例；查询用法及六列文本表示例见[流年指南](liunian.md#从出生记录读取年度十二宫)。
待决条目保存具体复核动作（`recheck`）与跟进讨论入口（`tracking_url`）；issue关闭不表示争议已经解决。
`RuleVariant.tracking_url`保留实现议题的历史链接；火铃异读、相关称名、归月范围与换年／子时出处等未决事项，由
[来源研究](https://github.com/0xf3cd/ziwei/issues/43)跟进，不把实现交付当作文献结论。

### 按星名查安星规则

按星名取得概念后，把概念的`id`传给`list_variants(concept_id=)`，就能查到该星的具名安星规则。
`find()`也会匹配规则变体，只有概念的标识才能传给`concept_id`。
下面分别查询文昌和文曲；这两个完整名称在当前目录中各只有一个匹配，因此可用单元素解包：

```{doctest}
>>> for name in ("文昌", "文曲"):
...   concept, = catalog.find(name)
...   rule, = catalog.list_variants(concept_id=concept.id)
...   print(name, rule.id)
文昌 variant.star.wenchang-wenqu-hour
文曲 variant.star.wenchang-wenqu-hour
>>> citations = catalog.references(rule.id)
>>> citations[0].locator, citations[0].quote
('安文昌文曲星诀/论本生时；子时、丑时例', '子时戌上起文昌')
>>> citations[0].source_id, catalog.get(citations[0].source_id).title
('source.quanshu-wikisource', '紫微斗數全書/卷二（维基文库电子录文）')
```

文昌与文曲在本目录中共用同一条规则。`references(rule.id)`返回支持该规则的引用元组，
每条引用的`locator`给出所见来源中的定位，`quote`保存短引；用`source_id`再读取来源记录、版本和核验状态。
一般查询仍需处理多个匹配或多个规则；电子录文已核与纸本底本已核的区别见下方[来源状态](#状态需要分开表达)。

### 阅读主题与检索正文

`topic(concept_id)`把一个概念的条目、变体和出处放进新的`Catalog`。例如读取闰月主题，
可同时看各条说法的前提、备选读法及原引：

```{doctest}
>>> topic = catalog.topic("concept.policy.leap-month")
>>> pending = topic.get("entry.leap-month.month-stars-scope")
>>> pending.alternatives
('闰月例只约束命宫与身宫', '闰月例同时约束其他月系星')
>>> topic.references(pending.id)[0].source_id
'source.quanshu-wikisource'
>>> matches = catalog.search_entries("六辛逢虎马")
>>> [entry.id for entry in matches]
['entry.star.kuiyue-quanshu-pending']
>>> selected = catalog.select_entries([entry.id for entry in matches])
>>> selected.entries == matches
True
```

“六辛逢虎马”只在原引中命中。`search_entries()`搜索条目的陈述、前提、例外、备选读法、
限度和复核动作，以及条目引用的引文原文、定位和限度；不搜索概念名或变体说明，名称仍用`find()`。
查询忽略首尾空白与大小写，不转换简繁；无命中返回空元组。
查询不是字符串时抛`TypeError`，去除首尾空白后为空时抛`ValueError`。
筛选参数与`filter_entries()`相同，条件对条目取交集。`source_id`只要求条目引用该来源，
命中文字仍可来自条目本身或它引用的其他来源。下例限定闰月主题和论坛来源，
命中的原引却来自同一条目引用的《精成》网页；用`references()`可以读到它：

```{doctest}
>>> entry, = catalog.search_entries(
...   "寅午戌月馬在申", concept_id="concept.policy.leap-month", source_id="source.zhongyi999-paimingpan",
... )
>>> entry.id
'entry.tianma.month-branch'
>>> reference, = (item for item in catalog.references(entry.id) if "寅午戌月馬在申" in item.quote)
>>> reference.source_id, reference.quote
('source.jingcheng-golla', '寅午戌月馬在申')
```

`topic()`的条目归属沿用`filter_entries()`，包含条目自身及其变体关联的概念与流派。
返回值还带该概念的所有变体，包括尚无条目引用的变体。`select_entries()`只带选中条目引用的变体；
重复条目标识去重，空序列返回空目录。两者均保留原目录顺序。
标识不是字符串时抛`TypeError`，格式非法时抛`ValueError`，格式合法但不存在时抛`KeyError`。
已存在但种类不符时抛`ValueError`：`topic()`要求概念标识，`select_entries()`要求条目标识。

要比较同名变体，可先用`find("庚干四化")`取得三个变体，再分别用`filter_entries(variant_id=...)`取条目，
最后用`select_entries()`读取各自的出处。

为使子目录中的标识都能在子目录内解析，两者还会带齐条目引用的引文与来源，并补齐概念记录：

- 带入所选条目的`concept_ids`，以及所选变体的`concept_ids`和`school_ids`所指的概念。
- 从这些概念及主题概念出发，沿`Concept.related_ids`逐层补入相关概念，直到没有新的概念。

补概念不改变上面已经选定的条目与变体，也不反查指向这些概念的入边。
例如紫微主题带有亮度变体，该变体还关联其他主星，因此子目录也会带入那些主星的概念，
但不会因此收进它们的所有条目。

### 给前端读取

`to_dict()`返回`concepts`、`variants`、`sources`、`citations`、`entries`五组完整记录，
以稳定ID相连。每条记录的键名与`Concept`、`KnowledgeEntry`等记录类型的字段名一致；
枚举写既有值，日期写ISO日期，元组写数组，
`None`、空字符串与空数组分别保留。返回容器可独立修改。

下面沿用上节的闰月目录`topic`和待决条目`pending`：

```{doctest}
>>> import json
>>> document = json.loads(json.dumps(topic.to_dict(), ensure_ascii=False))
>>> entry = next(item for item in document["entries"] if item["id"] == pending.id)
>>> entry["premise_status"], entry["show_by_default"]
('前提待定', False)
>>> entry["alternatives"] == list(pending.alternatives)
True
```

显示时沿条目→引文→来源读取，并同时展示条件、例外和限度。`lineage_id`相同表示同路材料，
不同也不能据此认定独立。具体来源关系与限度见条目及其来源记录，例如[月支天马](knowledge-reference.md#entry.tianma.month-branch)。
输出不计算独立来源数、不判规则冲突或命盘适用性。这是知识展示数据，与[命盘结果JSON](result.md)分别使用；
当前没有知识JSON导入接口。

### 中文入口

用`from ziwei.knowledge import 加载目录`加载目录，目录类型也可从`ziwei.knowledge.catalog`导入`知识目录`。
下列中文名与英文名指向同一对象，接受相同参数；`doushu.knowledge`及其对应子模块同样可用。

| 英文名 | 中文名 |
|---|---|
| `load_catalog` | `加载目录` |
| `Catalog` | `知识目录` |

目录方法使用英文名，如`topic()`、`search_entries()`和`to_dict()`。

### 只有知识的星曜

知识概念可以多于已实现星曜。`catalog.topic("concept.star.tiankong")`可读取“年支天空”的
子年丑宫例，当前没有对应`Star`成员或安星实现。完整名称查询用“年支天空”，
不将无上下文的“天空”当成全局别名；与时系地空的称名区别见
[`entry.star.tiankong-year`](knowledge-reference.md#entry.star.tiankong-year)的`limits`。

(knowledge-interpretations)=
### 按星曜和来源查解释

《紫微斗數全書》卷一的《诸星问答论》提供十四主星各一条星性描述（书中如何称述星曜）和一条带条件解释，共28条；
另有天空地劫、天伤天使、天刑、天姚、天哭天虚五节各两条，两组合计38条。
昌曲、流年昌曲、辅弼魁钺、禄存、天马、四化、羊陀火铃及两篇总论等十八节再提供33条，
目录现有71条选定解释。
用概念与来源一起筛选，可以将这本书的解释和已有安星条目分开读取。
当前目录的解释来源只有这一卷，因此示例将来源结果解包为`source`：

```{doctest}
>>> from ziwei.knowledge import load_catalog
>>> from ziwei.knowledge.model import EvidenceAspect, PremiseStatus
>>> catalog = load_catalog()
>>> source, = catalog.filter_sources(aspect=EvidenceAspect.解释)
>>> source.id
'source.quanshu-juan1-wikisource'
>>> ziwei, = catalog.find("紫微")
>>> entries = catalog.filter_entries(concept_id=ziwei.id, source_id=source.id)
>>> [entry.id for entry in entries]
['entry.interpretation.ziwei-nature', 'entry.interpretation.ziwei-fubi']
>>> conditional = entries[1]
>>> print(catalog.references(conditional.id)[0].quote)
無輔弼同行則為孤君，雖美玉不足。
>>> conditional.premises[-1]
'原文所说的无辅弼同行成立；同行的具体范围待核。'
>>> conditional.show_by_default
False
```

示例用`entries[1]`读取列表中的辅弼条件条目。将`catalog.find("紫微")`改为`catalog.find("武曲")`，
即可读取武曲的星性与同宫条件两条记录。
星性与条件解释共用`KnowledgeEntry`，没有单独的类别字段；筛选后通过陈述与前提区分内容。
也可按稳定标识直接读取条目，例如武曲与天府同宫的解释：

```{doctest}
>>> wuqu = catalog.get("entry.interpretation.wuqu-tianfu")
>>> print(catalog.references(wuqu.id)[0].quote)
與天府同宮有壽
>>> wuqu.premises[-1]
'武曲与天府同宫。'
>>> wuqu.premise_status is PremiseStatus.已明确
True
>>> wuqu.show_by_default
False
```

`statement`是仓内归纳，可以并列概括原文的几种说法；`exceptions`保存对这些说法的转折或限定。
读取时应结合`premises`与`exceptions`，用`references()`查看逐字原引，`limits`说明解释范围。
星性条目的`premises`通常说明收录了原文的哪一部分；带条件解释则记录条件、条件之间的区别和待核范围。
条目中的“答曰”引出对节题问句的回答，“歌曰”引出歌诀。
这些记录说明书中对星曜、四化含义与年度条件的说法，查询不会检查某张命盘是否满足条件。
上例的“已明确”只说明条目前提表达明确，武曲条目仍不默认展示。
全部71条均可检索，但不进入默认展示；
展示资格与出处、前提状态的区别见[状态说明](#状态需要分开表达)。

成对论述共用一条记录，关联两颗星。例如，天哭和天虚读到相同的两条解释：

```{doctest}
>>> tianku, = catalog.find("天哭")
>>> tianxu, = catalog.find("天虚")
>>> paired = catalog.filter_entries(concept_id=tianku.id, source_id=source.id)
>>> paired == catalog.filter_entries(concept_id=tianxu.id, source_id=source.id)
True
>>> [entry.id for entry in paired]
['entry.interpretation.kuxu-nature', 'entry.interpretation.kuxu-yulu']
>>> paired[1].premise_status is PremiseStatus.待定
True
```

书中“天空地劫”一节的解释关联本库时系地空、地劫；这个局部文献称名不成为全局星名别名。
用`catalog.get("entry.interpretation.kongjie-nature")`及`references()`可查同书卷二安诀和年支天空的区别。
查询仍不检查某张盘是否符合身命、二限、入庙或遇禄等条件，也不补全杂曜亮度。

### 读取四化、年度与共享总论

四化的含义分别用“化禄”“化权”“化科”“化忌”查阅。下面按“化禄”取得化禄概念，
再读取它的两条解释：

```{doctest}
>>> hualu, = catalog.find("化禄")
>>> hualu.id
'concept.sihua.hualu'
>>> meaning = catalog.topic(hualu.id)
>>> [entry.id for entry in meaning.entries]
['entry.interpretation.hualu-nature', 'entry.interpretation.hualu-kequan']
>>> meaning.variants
()
```

“化祿”和“化權”是显式繁体别名，同样可用。要换读另一个四化，将`find()`的名字换成“化权”等即可。
化禄含义没有规则变体，所以`meaning.variants`为空。
查四化表时，可用`catalog.topic("concept.sihua.shengnian")`读取生年四化主题，
或用`catalog.topic("concept.sihua.liunian")`读取流年四化主题。
按年干查询哪些星化禄的用法见[四化与大限](sihua-decades.md)和[流年](liunian.md)。

“流年昌曲”也有独立主题，可在主题内检索原引并读取对应例外：

```{doctest}
>>> annual = catalog.topic("concept.liunian.changqu")
>>> entry, = annual.search_entries("不能耐久")
>>> entry.id
'entry.interpretation.liunian-changqu'
>>> entry.exceptions
('末句说二星在巳酉得地不富即贵，但不能耐久。',)
>>> entry.premise_status is PremiseStatus.待定
True
```

魁钺合节的两条解释同时关联天魁与天钺；羊陀二星、羊陀火铃四星两篇总论各用一条记录，
关联标题中的星曜。从火星主题读取四星总论，仍会保留全部四个主体：

```{doctest}
>>> shared = catalog.topic("concept.star.huoxing").get("entry.interpretation.yangtuohuoling-general")
>>> [catalog.get(identifier).name for identifier in shared.concept_ids]
['擎羊', '陀罗', '火星', '铃星']
```

来源、文本层次与复核动作见[卷一来源记录](knowledge-reference.md#source.quanshu-juan1-wikisource)
及其关联条目；其他星曜的解释覆盖由[#77](https://github.com/0xf3cd/ziwei/issues/77)追踪。

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
已实现星曜的概念标识由`Star.concept_id`显式声明；知识专有概念在目录中声明。
[安星结果](stars.md)中的`StarPlacement.rule_id`保存所用规则的标识，与知识目录中相应规则变体的标识一致。
修改解释措辞不另建身份；新增含义不同的概念或规则时分配新的标识，不把旧标识改用于另一种含义。

### 记录分工

| 记录 | 保存什么 |
|---|---|
| 概念 | 身份、种类（星曜、宫位、四化、亮度、五行局、运限、口径、流派）、名称与别名、相关概念 |
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
查询时不动态导入或运行。36星的概念标识、规则标识、公开实现链接从`stars`定义引用，
完整四化表与大限也链接所属模块的执行入口；既有单行四化异文和魁钺古籍异文仍保留`implementation=None`，
不因某行与执行表相同就改变原记录的含义。完整表、盘例与转录限度见[四化与大限](sihua-decades.md)。
口径概念的`options`从配置定义取值；目录拒绝把变体链接到该概念之外的配置选项。
[口径选项及六十甲子参考](knowledge-reference.md#implemented-policies)直接读取现有定义。
流年日期换年、童限与大限起运衔接归为运限概念，可用`list_concepts(kind=ConceptKind.运限)`检索；
流年、童限查询的`boundary`参数分别使用`LiunianBoundary`、`TongxianBoundary`枚举，不属于出生解析配置。
已有概念标识保持不变。

原文引述、今人说明、仓内原作说明是不同文本层。同一祖本的多份转抄不构成独立来源；
措辞逐字相同的两处只算一路。保留原文措辞与定位，记录收录材料的转载权限。

## 来源与规则的三层问题

一条安星规则绑着三个可以分开回答的问题，一份来源常常只定其中一个：

1. **系统归属**：这条规则属于紫微斗数，还是同名星曜在其他术数中的规则。
   例如红鸾、天喜在其他术数中也有同名星，本库只收紫微斗数本命安星段的生年支查法。
2. **规则**：表、偏移、组合条件。
   例如庚干四化，两张具名四化表的化科与化忌不同。
3. **查法**：锚在年干、年支、生月还是生时；安在十二宫的哪一类位置。
   例如天马可按生年支安，也可用`TianmaRule.月支天马`改按农历生月对应的地支安。

记录每份来源说明了哪一层、没有说明哪一层。原文未写是否把起始宫位算作第一宫时，须通过例解判断；
找不到例解就并列保留两种读法。同名异物、转抄冒充独立来源、底本差异都可能改变结论。
`recheck`写明要取得什么新材料、复核哪一处，不只写“以后再研究”。

解释文本的支持层次另记为`EvidenceAspect.解释`，不套进安星规则或查法。
`filter_sources(aspect=)`按引文支持层次筛来源；它不将条目分成星性或条件两种类型。
条目的`premise_status`仍只说明前提是否表达明确，不能当作这两种内容的分类。

## 状态需要分开表达

| 问题 | 字段 | 类型与当前行为 |
|---|---|---|
| 所列出处核实了吗？ | `Source.status` | `SourceStatus`：所列版本已核或版本待核 |
| 条目前提已表达清楚了吗？ | `KnowledgeEntry.premise_status` | `PremiseStatus`：已明确或待定 |
| 条目可以默认展示吗？ | `KnowledgeEntry.show_by_default` | `bool`：须显式指定 |

整理进度另由`KnowledgeEntry.curation`记录。类型说明见[记录类型与状态API](api.md#记录类型与状态)。
`Source.lineage_id`是同路转录材料的归组标识；按它过滤不等于计算独立来源数。

出处核实不能单独证明适用；检索到相关陈述，也不能证明它适用于当前盘。
将来的判别器须区分满足、不满足、未知。只验证部分条件时，只能返回部分证据。

来源状态只回答所列版本是否已核：维基文库的固定修订可以标为已核，而它的底本仍可能未确认；
转录页的文字可已读，但原著版本未核时继续标待核。谱系键仅用于归并同路材料，不计算独立来源数。
默认展示须由整理者显式指定，且前提明确、整理完成、引文所指来源已核；这些检查仍不证明某张盘满足前提。

### 简称与限度的位置

指南中的《全书》指维基文库《紫微斗數全書/卷二》固定修订1963110的简体录文；中州派讲义指王亭之
《紫微斗数初级讲义》及同路网页转录；《精成》指《紫微斗數精成》网页或列明的下载件。
每个来源的版本、谱系与限度记在[参考页](knowledge-reference.md#records-sources)的来源记录里，
每条规则和解释的前提、限度与复核动作（`limits`、`recheck`）记在对应条目里，指南不另抄一份。

公开语料只收必要短引和仓内说明，不转载现代全文；没有原文的地方保留空引用及具体检索动作，
不写成“古籍没有”。查询条目本身不执行四化、天马或归月换日计算。
