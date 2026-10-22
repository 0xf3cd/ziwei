# 发布准备与首发步骤

[项目入口](../README.md) · [参与开发](contributing.md) · [参考盘例与限度](chart.md#参考盘例与验收限度)

项目名、PyPI发行名和Python导入名均为`ziwei`。本页说明候选版本的发布方法，
不表示项目已经上架，也不表示GitHub环境或PyPI发布身份已经配置。
发布流程只使用正式PyPI。代码准备、服务端配置、正式上传、tag与Release是分别需要确认的操作。

## 首发前配置

顺序很重要：先保护GitHub的`pypi`环境，再登记允许使用该环境的PyPI发布者。
如果workflow引用不存在的environment，GitHub可能自动创建一个没有保护规则的同名环境。
因此，不能先在PyPI信任一个仅有名字、尚无部署限制的environment。

维护者批准配置后：

1. 在GitHub建立`pypi`环境。设置维护者为required reviewer，
   Deployment branches选择Selected branches and tags，唯一规则为`name: main`、`type: branch`，禁止管理员绕过。
   不添加API token或其他secret。不要用同名tag规则替代main分支规则。
2. 单维护者需要保留批准自己运行的能力；启用Prevent self-review会阻止这种批准。
   这里是同一人的显式第二步，不是另一人的独立审阅。
3. 用GitHub只读API核对`protection_rules`、`deployment_branch_policy`和
   `deployment-branch-policies`；在网页保存后重新打开环境设置，确认禁止管理员绕过。
   再按授权演练非main拒绝、等待批准和不能绕过的行为。workflow里的ref判断不能代替这些服务端规则。
4. 然后在PyPI登记pending publisher：项目`ziwei`，owner`0xf3cd`，repo`ziwei`，
   workflow文件名`release.yml`，environment填写`pypi`。
   即使PyPI把environment标为可选，本流程也必须填写，让发布身份绑定受保护的环境。

pending publisher首次使用时才创建项目，**不会预留名称**。配置前须重新确认名称和账号归属。
以上配置、拒绝行为与OIDC换取凭据的结果，在实际核验前都不能记为已完成。

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
   两个产物在消费前后须保持相同hash，不能检查完再重建。
   同步依赖后和保留产物前，还须核checkout没有偏离本次源码SHA或混入未跟踪文件；
   这项一致性检查不等于隔离了runner上所有依赖代码。
2. **支持矩阵消费**：Linux的Python3.11–3.14、Linux ARM64和macOS／Windows3.14
   下载同一个artifact-id，按构建job单独输出的hash核对后，运行相同安装消费函数。
   安装平台范围仍以[安装要求](../README.md#安装要求)为准。
3. **PyPI批准与上传**：构建和全部矩阵消费成功后，等待`pypi`环境批准，
   再下载同一个artifact-id，核对文件名与构建job给出的两文件hash，调用固定到完整提交SHA的上传action。
   上传job不检出或执行项目源码，不安装项目开发工具。

只有`publish-pypi`拥有`id-token: write`。不使用长期PyPI token、缓存或`skip-existing`，
不在push／PR上自动上传。输入和job输出只经环境变量进入脚本。

action引用固定完整提交SHA，但这不等于所有传递依赖都由OCI digest固定。
当前上传action用该SHA作为容器镜像tag；仍须信任上游维护者及镜像发布链。
启用前要核对当时的action实现、记录该镜像tag的实际digest，并确认这项信任条件；
不把“已钉action”写成“所有容器字节都已锁定”。

## 失败、拒绝与发布记录

artifact保留14天。批准时间须留在原产物的有效期内；过期或取回不符时停止，
不能自动重新构建另一份文件后声称沿用了原产物。

只核验流程时，停在`pypi`待批准；未批准就不会执行上传。若拒绝批准或取消运行，
先保存运行SHA、artifact-id、两个文件hash与错误，再确认后续处理。
不要自动改版本、开启`skip-existing`，或重传已经成功上传的文件。
同一次运行重跑失败job时，原outputs与artifact能否保全、可重跑期限多长，须在授权演练中验证；
未核之前不承诺重跑一定能恢复。重跑build或整条流程会重新构建，不属于沿用原产物的恢复路径。

任一上传失败后，先核远端实际已有的文件及hash；不能只凭本地退出码认定“什么都没上传”。

正式上传完成后，核PyPI文件摘要与PEP740证明中的Source Repository Digest，
确认它们对应这次运行的源码SHA。再另行批准按该固定SHA创建`v<版本>` tag和GitHub Release。
tag创建、移动和删除规则同样需要明确配置与验证；本工作流不拿未保护的tag作为构建身份。

## 本地可验证的部分

正常开发入口不变。需要保留同一份已核产物时，先确保输出目录为空，再运行：

```sh
uv run --locked python tools/check.py --artifacts-dir dist
```

输出目录保存`packages/`中的sdist与wheel，以及消费前固定的`SHA256SUMS`。
发布工作流随后加入`release.json`，并把文件名、hash和artifact-id分别传给下游job。
本地保留入口拒绝非空目的地，不静默覆盖；发布工具另核保留目录的精确成员、身份、软链和摘要，
缺文件、多文件、错误身份或hash不符时拒绝继续。

本机测试覆盖身份早失败、workflow权限／依赖结构、产物篡改、真实发布Bash及上传前拒绝。
它们不能证明服务端environment已经生效、OIDC已可用或PyPI已实际接收这些文件；
这些只有授权后的运行与回读结果才能证明。
