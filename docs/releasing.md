# 发布准备与首发步骤

[项目入口](../README.md) · [参与开发](contributing.md) · [参考盘例与限度](chart.md#参考盘例与验收限度)

项目名、PyPI发行名和Python导入名均为`ziwei`。本页说明候选版本的发布方法，
不表示项目已经上架，也不表示GitHub环境或PyPI发布身份已经配置。
代码准备、服务端配置、测试站演练、正式上传、tag与Release是分别需要确认的操作。

## 首发前配置

顺序很重要：先保护GitHub环境，再登记允许使用这些环境的PyPI发布者。
如果workflow引用不存在的environment，GitHub可能自动创建一个没有保护规则的同名环境。
因此，不能先在PyPI信任一个仅有名字、尚无部署限制的environment。

维护者批准配置后：

1. 在GitHub建立`testpypi`与`pypi`两个environment。设置维护者为required reviewer，
   部署策略选selected，唯一规则为`name: main`、`type: branch`，禁止管理员绕过。
   不添加API token或其他secret。不要用同名tag规则替代main分支规则。
2. 单维护者需要保留批准自己运行的能力；启用Prevent self-review会阻止这种批准。
   这里是同一人的显式第二步，不是另一人的独立审阅。
3. 用GitHub只读API核对两环境的`protection_rules`、`can_admins_bypass`、
   `deployment_branch_policy`和`deployment-branch-policies`，再按授权演练非main拒绝、
   等待批准和不能绕过的行为。workflow里的ref判断不能代替这些服务端规则。
4. 然后分别在TestPyPI与PyPI登记pending publisher：项目`ziwei`，owner`0xf3cd`，repo`ziwei`，
   workflow文件名`release.yml`，environment分别填写`testpypi`与`pypi`。
   即使PyPI把environment标为可选，本流程也必须填写，防止两个发布权限互通。

pending publisher首次使用时才创建项目，**不会预留名称**。配置前须重新确认名称和账号归属。
以上配置、拒绝行为与OIDC换取凭据的结果，在实际核验前都不能记为已完成。

官方说明：[新项目发布者](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)、
[安全模型](https://docs.pypi.org/trusted-publishers/security-model/)、
[GitHub环境](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)。

## 同一次运行中的发布链

候选版本验收完成并合入main后，维护者另行批准启动发布。进入Actions的Release工作流，
选择main，填写候选版本和本次main运行的完整小写40位SHA。
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
3. **TestPyPI批准与上传**：等待`testpypi`环境批准，只下载、核hash，再调用固定SHA的上传action。
4. **测试站回读**：核精确项目／版本的两个文件摘要。目标wheel只从TestPyPI取回并核对实际hash，
   然后`--no-deps`安装；运行时依赖只按本仓锁定hash从PyPI安装，不使用`--extra-index-url`。
   TestPyPI没有本项目要求的完整依赖组合，不能把它当作PyPI镜像。
5. **PyPI批准与上传**：测试站回读与消费成功后，等待独立的`pypi`环境批准，
   再上传同一个artifact-id中的同一对文件。上传job不检出或执行项目源码，不安装项目开发工具。

只有两个上传job拥有`id-token: write`。不使用长期PyPI token、缓存或`skip-existing`，
不在push／PR上自动上传。输入和job输出只经环境变量进入脚本。

action引用固定完整提交SHA，但这不等于所有传递依赖都由OCI digest固定。
当前上传action用该SHA作为容器镜像tag；仍须信任上游维护者及镜像发布链。
启用前要核对当时的action实现与这项信任条件，不把“已钉action”写成“所有容器字节都已锁定”。

## 失败、拒绝与发布记录

artifact保留14天。批准时间须留在原产物的有效期内；过期或取回不符时停止，
不能自动重新构建另一份文件后声称沿用了原产物。

只演练时可以拒绝正式PyPI批准，但拒绝会使运行失败，**TestPyPI已上传的文件名仍被占用**。
不要因此重新启动整条流程并重传同版本，也不要自动改版本或开启`skip-existing`。
先保存运行SHA、artifact-id、两个文件hash、已上传文件与错误，再另行确认后续处理。
同一次运行重跑失败job时，原outputs与artifact能否保全、可重跑期限多长，须在授权演练中验证；
未核之前不承诺重跑一定能恢复。

元数据回读只对新版本的暂时404做有界等待。摘要不符立即失败，不等待另一个结果来覆盖它。
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
非空目录、缺文件、多文件、软链、错误身份或hash不符都须失败，不静默覆盖。

本机测试覆盖身份早失败、workflow权限／依赖结构、产物篡改、真实发布Bash及上传前拒绝。
它们不能证明服务端environment已经生效、OIDC已可用或TestPyPI已实际安装成功；
这些只有授权后的运行与回读结果才能证明。
