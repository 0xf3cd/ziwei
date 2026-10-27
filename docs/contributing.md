# 参与开发

[项目入口](../README.md) · [文档入口](index.md)

本指南面向参与`main`开发的人；固定发行版本的文档请从相应源码标签查阅。
先读[相关 issue](https://github.com/0xf3cd/ziwei/issues)和[结构设计](architecture.md)，确认功能范围与验收盘例。
仓库的编码、知识整理与交付约定统一维护在[AGENTS.md](https://github.com/0xf3cd/ziwei/blob/main/AGENTS.md)，它也是唯一的agent指令源；
本页说明如何安装、检查和准备贡献，不另列一套规约。

## 运行检查

安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)，在仓库根目录运行：

```sh
uv sync --locked --python 3.14
uv run --locked python tools/check.py
```

支持 Python 3.11–3.14，原生依赖的平台要求见[安装要求](../README.md#安装要求)。
CI在Linux x86_64的3.11／3.14、Linux ARM64的3.14和macOS／Windows3.14上运行同一命令。
本地验证下限时使用 `uv sync --locked --python 3.11`。
优化模式也使用`tools/check.py`入口；它为pytest设置所需的警告过滤，裸跑`python -O -m pytest`不等价。

该命令依次检查：

- Ruff lint、两空格格式、严格mypy，以及普通／优化模式的pytest。
- 文档本地链接、严格HTML与doctest全量构建。API检查比对公开类、函数、方法、类型别名及带说明的常量
  与实际HTML签名，拒绝被渲染成正文的指令。知识参考页从内置记录与配置定义生成；检查会拒绝字段、
  口径表配对或稳定锚点不符，包括遗漏成员和指向未知记录。标准库类型链接使用离线inventory，不在构建时下载。
- sdist内容与由它重建的wheel。锁定开发组提供build和setuptools后端，构建使用`python -m build --no-isolation`。
  sdist须带全源码、测试、工具、workflow、文档、锁文件与协作约定，不得夹带`.review/`。
  检查会在构建前删除`src/*.egg-info`，避免旧文件清单掩盖`MANIFEST.in`的变化。
- 在仓外以隔离模式导入安装后的包，分别运行普通／优化消费。运行时依赖按锁文件hash安装，
  本项目wheel用`--no-deps`安装；消费前后比对产物hash，拒绝被改写的文件。

临时HTML、doctest报告、分发包和安装验证环境优先使用环境变量`SCRATCH`，否则使用系统临时目录，
退出时删除。构建元数据和工具缓存可能保留在仓内已忽略的目录中。
显式传入`--artifacts-dir`可将同一份已核产物保留到空目录，详见[发布指南](releasing.md)。

工具版本由 `uv.lock` 锁定：Python 3.11 使用 Sphinx 8.2.3，较新 Python 使用 Sphinx 9.1.0。
覆盖率报告用于定位遗漏。当前测试覆盖历法解析、安星、四化与大限、整盘组合、文本显示和知识查询，
并包含独立参考盘例及合成取证。各项证据的适用范围见[完整命盘](chart.md#参考盘例与验收限度)，不把组件联动当成独立整盘认证。

CI的uv版本与各平台下载归档摘要在工作流中固定；摘要取自uv发布资产并与实际归档字节核对。
第三方action均使用完整提交SHA，浮动tag由回归测试拒绝。

本地格式化运行 `uv run ruff format .`。任一命令失败即停止，修复原因后重跑。
依赖变更须更新锁文件并通过两个 Python 端点；忽略规则或警告时应限制范围并说明原因。

## 构建文档

只检查文档并保留HTML时，在仓库根目录运行：

```sh
uv run --locked python tools/check.py --docs-dir build/docs
```

输出目录须不存在或为空；路径已是文件或目录非空时，会在构建前拒绝，不删除已有内容。
若要保留上次产物，本次改用另一个新目录。

该入口执行严格HTML与doctest构建，并核验API签名、知识记录与参考表。
打开`build/docs/html/index.html`进入文档，实际正文位于`build/docs/html/docs/`。
根入口使用相对链接，离线打开和部署到项目子路径都使用同一份输出。
[开发文档站](https://0xf3cd.github.io/ziwei/)随`main`更新，不固定于某次发行。

按上面的`uv sync`从本仓安装源码，本地分发名／版本为`ziwei`／`0.2.0`。
可检查安装的版本字符串：

```{doctest}
>>> from importlib.metadata import version
>>> version("ziwei")
'0.2.0'
```

同一版本字符串不能证明安装来源或具体源码提交；核对安装对象时还须检查这两项。

## 依赖兼容策略

当前正式支持的组合为`celestial-calendar==0.8.0`和`tzdata==2026.5`，包元数据也限定这组版本。
实际pip安装中，将ziwei与celestial 0.9.0或tzdata 2026.4显式放在同一安装命令中，会因依赖冲突被拒绝；
环境中仅预装celestial 0.9.0时，再安装ziwei会将其降到0.8.0。
因此应使用独立虚拟环境，不要让应用在同一环境中要求另一精确版本。

celestial 0.7.0／0.9.0的探索以`--no-deps`强制安装，选定排盘例及HKO表、天文计算、混合三算法的范围端点检查通过，
但`pip check`均拒绝其元数据；这既不证明候选版本不可运行，也不构成正式兼容支持。
此次所见三算法支持范围均未变化，平台要求仍以[安装要求](../README.md#安装要求)为准。

候选依赖发布新版本、应用需要共装其他版本，或算法范围、时区来源与精度约定变化时，应重新评估。
复查须实际安装、共装与排盘，核对算法范围内端点及范围外日期的接受／拒绝，保留算法、范围、
历法与时区版本，不通过静默换算法取得兼容。允许范围若改变，依赖配置与锁文件同步修改，
并在Python 3.11／3.14通过完整检查。策略与更新节奏分别由
[#25](https://github.com/0xf3cd/ziwei/issues/25)和[#16](https://github.com/0xf3cd/ziwei/issues/16)追踪。

## 维护API文档

公开类型别名以`TypeAlias`声明；公开常量以`Final`声明，并用紧随赋值的字符串或紧邻赋值之前的`#:`注释说明。
修改声明时同步维护[API参考](api.md)的生成指令；检查要求这些公开数据在实际HTML中都有签名。

## 准备PR

按[AGENTS.md](https://github.com/0xf3cd/ziwei/blob/main/AGENTS.md#验证与交付)准备PR格式、验证记录与署名。
说明对应issue、变更的行为、实际运行的命令和未解决问题；使用AI编写的贡献仍由贡献者负责。
改规则时先核[知识与来源](knowledge.md)，参考盘例及其限度见[完整命盘](chart.md#参考盘例与验收限度)。
改文档时除运行示例外，还应打开生成页面，检查文字、完整盘面与目标锚点是否可读。
