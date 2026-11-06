# 发布与失败处理

[项目入口](../README.md) · [参与开发](contributing.md) · [参考盘例与限度](chart.md#参考盘例与验收限度)

主项目名、PyPI发行名和Python导入名均为`ziwei`；从0.4.1起，另发同版本`doushu`别名wheel，精确依赖主包。
本页说明随`main`维护的发布流程，
区分已有发布记录与下一候选版本的操作。
发布流程只使用正式PyPI。代码准备、服务端配置、正式上传、tag与Release是分别需要确认的操作。

## 已有发布记录

[PyPI 0.1.0](https://pypi.org/project/ziwei/0.1.0/)与
[v0.1.0 Release](https://github.com/0xf3cd/ziwei/releases/tag/v0.1.0)已公开。
轻量标签`v0.1.0`指向源码`206723d794bbf9333062ab0f07beb0d9e4751b2e`，不附独立标签签名。
非管理员创建拒绝、真实重复上传拒收和跨attempt失败恢复未做演练。维护者已取消这三项后续计划，
[#67](https://github.com/0xf3cd/ziwei/issues/67)以`not_planned`关闭；关闭不表示这些行为已验证。
[#26](https://github.com/0xf3cd/ziwei/issues/26)保留首发验证记录；不为补证重传0.1.0，也不改用TestPyPI。

[正式发布运行39854980639](https://github.com/0xf3cd/ziwei/actions/runs/39854980639)的attempt 1完成构建、
七项跨平台消费及`pypi`环境批准，上传的是同一artifact-id中的原产物。
从PyPI与Release取回的sdist／wheel与原件逐字节相同；已核对PyPI两份PEP740证明中记录的源码SHA、工作流、环境与attempt。

`pypi`环境已限制为`main`分支，要求维护者批准，允许本人批准自己的运行，禁止管理员绕过。
非main分支和同名`main`标签的无上传探针均被拒绝。
`v*`首次创建仅允许管理员角色；更新和删除规则无绕过，临时标签范围内的更新／删除负例均被拒绝。

开发Pages文档与PyPI发布分开。Pages使用`github-pages`环境，不属于`pypi`发布身份；
部署文档不改变PyPI信任的仓库、工作流或环境。

[PyPI 0.2.0](https://pypi.org/project/ziwei/0.2.0/)与
[v0.2.0 Release](https://github.com/0xf3cd/ziwei/releases/tag/v0.2.0)也已公开，
版本标签固定指向源码`5cdcc93fa3fd725177cc8532a667b0764f901a96`。

[PyPI 0.3.0](https://pypi.org/project/ziwei/0.3.0/)与
[v0.3.0 Release](https://github.com/0xf3cd/ziwei/releases/tag/v0.3.0)已公开，
版本标签固定指向源码`71cf78471a7d69146552ea902e4757dbc8173837`。

[PyPI 0.4.0](https://pypi.org/project/ziwei/0.4.0/)与
[v0.4.0 Release](https://github.com/0xf3cd/ziwei/releases/tag/v0.4.0)已公开，
版本标签固定指向源码`78bf22b5e1fcbef7b0ccb771d359c70a9a4133ae`。

[ziwei PyPI 0.4.1](https://pypi.org/project/ziwei/0.4.1/)、
[doushu PyPI 0.4.1](https://pypi.org/project/doushu/0.4.1/)与
[v0.4.1 Release](https://github.com/0xf3cd/ziwei/releases/tag/v0.4.1)已公开，
版本标签固定指向源码`419f14edc6e8a9fca3093142b9c355eabd548028`。
[正式运行41770565687](https://github.com/0xf3cd/ziwei/actions/runs/41770565687)的attempt 1完成构建、七项跨平台消费与两包上传。
三份公开制品与同次原件逐字节相同，PEP740发布身份、制品摘要与源码／workflow／environment／run／attempt字段已核对；
Python3.11／3.14各三种全新索引安装消费通过，含别名的组合也通过类型正反例。本次两个上传job分别等待并取得了`pypi`环境批准。

## 发布前准备

候选版本合入main前，更新`pyproject.toml`版本号，核对README的安装与文档入口，以及构建后的包元数据与长描述。
同时核对其他文档中的当前版本说明、安装示例与贡献指南的版本doctest；旧版本的发布记录和链接保留原版本。
README会成为PyPI长描述，不保留会在上传后过时的“开发中”说明。
README和文档入口仍须说明面向开发main还是已发布版本，不能只靠包版本号区分。

## 发布前配置核对

本项目已有`pypi`配置。每次发布前回读下列现有设置；若需新建或修改，须先取得维护者批准。
新建时先保护GitHub的`pypi`环境，再登记允许使用该环境的PyPI发布者。
如果workflow引用不存在的environment，GitHub可能自动创建一个没有保护规则的同名环境。
因此，不能先在PyPI信任一个仅有名字、尚无部署限制的environment。

核对内容如下：

1. GitHub的`pypi`环境设置维护者为required reviewer，
   Deployment branches选择Selected branches and tags，唯一规则为`name: main`、`type: branch`，禁止管理员绕过。
   不添加API token或其他secret。不要用同名tag规则替代main分支规则。
2. 单维护者需要保留批准自己运行的能力；启用Prevent self-review会阻止这种批准。
   这里是同一人的显式第二步，不是另一人的独立审阅。
3. 用GitHub只读API核对`protection_rules`、`deployment_branch_policy`和
   `deployment-branch-policies`；在网页保存后重新打开环境设置，确认禁止管理员绕过。
   再按授权演练非main拒绝、等待批准和不能绕过的行为。workflow里的ref判断不能代替这些服务端规则。
4. 分别核对两个PyPI项目的trusted publisher：`ziwei`与`doushu`，owner`0xf3cd`，repo`ziwei`，
   workflow文件名`release.yml`，environment填写`pypi`。
   即使PyPI把environment标为可选，本流程也必须填写，让发布身份绑定受保护的环境。

只有新项目才登记pending publisher；它首次使用时才创建项目，**不会预留名称**。
公开项目查询404也不能证明名称已保留。
ziwei与doushu均已完成首发，不应重新登记为pending publisher。维护者在账户Publishing页确认
doushu已归入自己的项目并转为普通publisher；后续发布核对上述仓库、workflow与environment，不重复登记。
新配置、拒绝行为与OIDC换取凭据的结果，
在实际核验前不能记为已完成；既有0.1.0证据也不能证明修改后的配置仍然有效。

官方说明：[新项目发布者](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)、
[安全模型](https://docs.pypi.org/trusted-publishers/security-model/)、
[GitHub环境](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)。

## 同一次运行中的发布链

候选版本验收完成并合入main后，维护者另行批准启动发布。进入Actions的Release工作流，
选择main，填写候选版本，并复制main最新提交的完整小写40位SHA。
如果提交表单前main又有新提交，须按新提交的SHA重填。
版本须与`pyproject.toml`一致，SHA须与GitHub为本次运行记录的`github.sha`一致；
不接受任意旧提交、tag或临时改写的版本。之后main的新提交不会改变已经锁定的运行SHA。

工作流依次执行：

1. **构建与门禁**：使用锁文件中的开发工具与后端，经sdist构建wheel，检查文档、元数据和内容，
   在仓外以锁定hash安装依赖、以`--no-deps`安装目标wheel，运行普通／优化两种模式的完整盘面消费。
   从同一sdist内的工具构建一次doushu wheel，在同一仓外环境中继续安装消费，并核静态类型正反例。
   主包两文件与别名wheel在消费前后须保持相同hash，不能检查完再重建。
   同步依赖后和保留产物前，还须核checkout没有偏离本次源码SHA或混入未跟踪文件；
   这项一致性检查不等于隔离了runner上所有依赖代码。
2. **支持矩阵消费**：Linux的Python3.11–3.14、Linux ARM64和macOS／Windows3.14
   分别按两个artifact-id下载到`dist`与`dist-doushu`，按构建job独立输出的hash核对后，
   安装同次主wheel和别名wheel，运行普通／优化模式消费；此阶段不安装mypy。
   安装平台范围仍以[安装要求](../README.md#安装要求)为准。
3. **PyPI批准与上传**：构建和全部矩阵消费成功后，等待`pypi`环境批准，
   再下载同一个artifact-id，核对文件名与构建job给出的两文件hash，调用固定到完整提交SHA的上传action。
   上传job不检出或执行项目源码，不安装项目开发工具。
4. **别名上传**：`publish-pypi-doushu`显式依赖构建、全部矩阵消费与主包上传成功，
   使用同一个受保护`pypi`环境，只下载和核验别名原wheel后上传。
   是否再次等待批准以当前运行的待部署状态为准；若等待，由维护者批准，不代批。

在PyPI发布工作流中，只有两个上传job拥有`id-token: write`。不使用长期PyPI token、缓存或`skip-existing`，
不在push／PR上自动上传。输入和job输出只经环境变量进入脚本。

消费矩阵保留`fail-fast: false`，便于一个组合失败后继续收集其他组合的结果。
它不是上传安全条件：即使改为提前取消其余组合，已有消费失败仍会阻止上传。

action引用固定完整提交SHA，但这不等于所有传递依赖都由OCI digest固定。
当前上传action用该SHA作为容器镜像tag；仍须信任上游维护者及镜像发布链。
每次正式上传前核对当时的action实现，记录镜像tag解析到的digest，并确认这项信任条件。
运行后从上传job日志取得实际拉取的digest，与运行前记录的值比较；两者与比较结果均记入本次发布验证记录。
不把“已钉action”写成“所有容器字节都已锁定”。

## 失败后先保存证据

artifact保留14天。批准时间须留在原产物的有效期内；过期或取回不符时停止，
不能自动重新构建另一份文件后声称沿用了原产物。

只核验流程时，停在`pypi`待批准；未批准就不会执行上传。失败、拒绝批准或取消运行后，
在任何重跑之前保存：

- 运行URL、`run-id`、`run-attempt`、本次`source SHA`与请求的版本。
- 失败job／step、完整日志、批准或取消状态，以及远端是否已经收到文件。
- 本次build的outputs：`version`、`source_sha`、`sdist_name`、`wheel_name`、
  `sdist_sha256`、`wheel_sha256`、`artifact_id`，以及别名的`doushu_wheel_name`、`doushu_wheel_sha256`、`doushu_artifact_id`。
- 对应artifact的ID、名称、所属运行及attempt、到期时间；取回原bundle，保存`release.json`、
  `SHA256SUMS`与两份分发文件，并重新核对文件摘要。
  同时保存别名独立bundle中的单行`SHA256SUMS`与wheel，不能用它覆盖主包目录中的同名文件。

artifact名称不包含attempt，不能据同名把不同attempt的outputs与制品拼在一起。
恢复时须能证明artifact-id、源码SHA、两个文件名和摘要均属于已经验收的那一组产物。
缺失outputs、原artifact过期或无法证明对应关系时停止，不猜测ID，也不按名字寻找替代品。

不要自动改版本、开启`skip-existing`，或重传已经成功上传的文件。
同一次运行重跑失败job时，原outputs与artifact能否保全、可重跑期限多长，仍须在授权演练中验证；
尚未验证可用的跨attempt恢复步骤，因此本页不承诺重跑一定能恢复。
重跑build或整条流程会重新构建，不属于沿用原产物的恢复路径。

主包已成功、别名失败时，保留两份artifact和各自outputs，停止后再评估能否只补传别名wheel，
且使用的仍是已验证的同一份原件；
不重传主包，不承诺重跑失败job能跨attempt复用outputs或再次等待批准。
任一上传失败后，分别到[ziwei文件页](https://pypi.org/project/ziwei/#files)和
[doushu文件页](https://pypi.org/project/doushu/#files)核对远端实际已有的文件及hash；
不能只凭本地退出码认定“什么都没上传”。

正式上传完成后，核PyPI文件摘要与PEP740证明中的Source Repository Digest，
确认它们对应这次运行的源码SHA。再另行批准按该固定SHA创建`v<版本>` tag和GitHub Release。
tag创建、移动和删除规则同样需要明确配置与验证；本工作流不拿未保护的tag作为构建身份。
发行后移除[发行说明](releases.md)中的候选标记，并在本页补记固定源码与发行链接；已发行制品和标签保持原样。

## 本地可验证的部分

正常开发入口不变。需要保留同一份已核产物时，先确保输出目录为空，再运行：

```sh
uv run --locked python tools/check.py --artifacts-dir dist --doushu-artifacts-dir dist-doushu
```

输出目录保存`packages/`中的sdist与wheel，以及消费前固定的`SHA256SUMS`。
独立的`dist-doushu`只保存`packages/`中的别名wheel与单行`SHA256SUMS`，不混入主包bundle。
发布工作流随后加入`release.json`，并把文件名、hash和artifact-id分别传给下游job。
本地保留入口拒绝非空目的地，不静默覆盖；发布工具另核保留目录的精确成员、身份、软链和摘要，
缺文件、多文件、错误身份或hash不符时拒绝继续。

Python发布工具核验bundle元数据、精确成员、制品内部身份和实际字节；上传job中的Bash只核对待上传的两份文件及其摘要。
元数据损坏等额外缺陷由Python拒绝，Bash不检查这些内容；两层都须成功，才能继续发布。

本机测试覆盖身份早失败、workflow权限／依赖结构、产物篡改、真实发布Bash及上传前拒绝。
它们不能证明某次服务端environment已生效、OIDC可用或PyPI实际接收了文件；
这些要以对应运行与回读结果为准，0.1.0的已核结果见上方已有发布记录。
