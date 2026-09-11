# vNext 技术架构

状态：`Approved`（程序模型、分层、函数目录、扩展信任与发布边界已冻结）

最近修订：2026-09-01

本文件细化 [目标架构](../ARCHITECTURE.md)。项目函数模型以 [结构化程序模型](PROGRAM_MODEL.md) 为准，文件/目录与录制/回放分别以 [FILES.md](FILES.md) 和 [REPLAY.md](REPLAY.md) 为准，扩展边界以 [扩展平台](EXTENSIONS.md) 为准，网络/配对与计划控制面分别见 [NETWORK.md](NETWORK.md) 和 [SCHEDULES.md](SCHEDULES.md)。

## 1. 分层

```text
Vue 3 + TypeScript IDE / Player
        │ typed command API + event protocol
纵向结构化语句投影 / Inspector / Control Registry
        │ versioned structural commands
Workspace / Program / Function / Resource / File / Recorder / Replay / Extension services
        │ immutable domain results
ProgramDocument + type system + function registry
        │ deterministic compile
versioned ECIR + debug map + dependency closure
        │ execute
Runtime Coordinator
   ├─ Windows driver
   ├─ Android ADB driver
   ├─ controlled extension workers / feature runtimes
   └─ Android native Kotlin/C++ runtime
```

前端只提交有类型的结构命令。应用服务校验命令的目标 ID、revision、类型和引用后，修改内存中的 ProgramDocument，并向所有投影发布不可变结果。界面组件不得直接修改 JSON、拼接可执行文本或维护平行参数对象。

## 2. 唯一事实与派生物

- `ProgramDocument` 是项目函数唯一可编辑事实，按 `program/functions/<function_id>.json` 持久化。
- 纵向语句、检查器、变量引用、调用图、调试状态和只读伪代码是 ProgramDocument 的派生投影。
- ECIR 是编译器根据 ProgramDocument、函数契约、扩展锁、资源和目标配置生成的确定性构建产物。
- IDE 调试和 Player 执行同一 ECIR 语义。运行时不读取 ProgramDocument，Player 发布包也不包含 ProgramDocument。
- 滚动位置、折叠、选择和面板宽度进入独立 view-state；它们不参与编译、内容哈希或业务事务。

系统不提供项目函数的用户源码、Monaco、Language Service、Parser、Formatter 或非法文本草稿。可以生成带明确“只读”标记的伪代码与诊断文本，但不能反向解析或保存为第二份业务事实。

## 3. Program Service 与结构命令

Program Service 负责 Schema、结构命令、稳定 ID、引用索引、类型检查、撤销重做、冲突检测和事务保存。

首版结构命令至少覆盖：

- 插入、删除、复制和移动语句；
- 移入、移出和重排作用域；
- 修改函数调用参数、返回绑定和可选步骤备注；
- 新建、重命名和删除局部符号；
- 提取项目函数并更新调用引用；
- 创建和修改条件、循环、带可选重试策略的异常区域、目标作用域与监听声明；异常区域主体或函数契约变化时使旧副作用确认失效。

命令以稳定 `document_id`、`statement_id`、`symbol_id`、`value_id` 和字段路径定位对象。移动保留对象 ID，复制生成新 ID；命令失败不修改模型或撤销栈。跨文档重构先计算完整变更集，再由 Workspace Service 原子提交。

没有默认值的必填参数使用显式 `unset` 值节点。`unset` 让结构保持可保存、可选择和可修复，同时阻止编译、运行和发布；它不是非法语法，也不是用户可以声明的运行时类型。

## 4. 类型、Control 与 ECIR

函数契约声明稳定参数 ID、类型、默认值、返回、稳定异常 ID、异常重试分类、副作用、平台、权限和 Control 覆盖。ProgramDocument 保存 `unset`、常量、稳定引用、容器、记录和递归纯值表达式。Control 只提交类型化值，不提交引号、逗号文本或代码片段。

Value Service 维护核心版本化纯操作注册表、稳定操作输入槽、稳定值节点、增量类型检查、引用索引、摘要投影和提取重构。经批准的兼容纯操作可以完整递归组合；普通函数、I/O 和扩展私有表达式不能进入。Player 可以按稳定值节点建立精确签名覆盖槽。操作注册表版本与内容哈希属于编译、缓存和发布签名输入。

Compiler Service 接收规范化 ProgramDocument、函数契约、纯值操作注册表、项目变量定义、启用扩展及其锁定版本、资源注册表和目标配置，并执行：

1. 校验 Schema、稳定引用、类型、平台和权限；
2. 拒绝 `unset`、破损引用和目标不兼容；
3. 展开或降低项目函数与官方标准函数；
4. 计算资源、扩展和原生依赖闭包；
5. 生成 ECIR、调试映射、权限清单和发布报告。

异常区域的可选重试策略确定性降低到同一 ECIR 控制流。策略缺省表示关闭；次数与间隔在进入区域时求值一次。Runtime 只重试标记为瞬时的结构化异常，从主体首条语句重新开始且不回滚副作用；耗尽后再进入捕获分支，最终分支只执行一次。取消/停止不属于可重试异常。

相同规范化输入、扩展锁和编译器版本必须产生字节级或规范化等价的 ECIR。调试映射使用稳定函数、语句、字段和 `value_id`，不依赖行号、显示摘要或当前树路径。

ECIR 首版使用显式版本 JSON；若 Android 性能证据要求更紧凑编码，可增加语义相同的 Protobuf，不能形成第二套执行含义。

## 5. 函数实现与扩展

- 官方原子函数与扩展函数可以由 Python、C++、Kotlin 或目标驱动实现。
- 官方标准函数和项目函数使用 ProgramDocument 组合。
- 标准函数可以具有经等价性测试验证的融合实现，但其返回、超时、取消、错误、日志和调试语义必须与结构化定义一致。
- 普通第三方扩展只能注册受控函数契约与批准的贡献点，不能修改 ProgramDocument Schema 或核心 Store。
- Python/原生扩展在 PyCharm、VS Code 等外部 IDE 中开发。EasyCode 只创建骨架、导入包、审核契约、运行测试、管理权限与依赖并计算发布闭包。
- Python 扩展在受控 Worker 中执行；Worker 崩溃、超时或序列化失败返回结构化诊断，不能拖垮 IDE 或伪报成功。Worker 是可靠性隔离而非恶意代码沙箱；Python/原生执行必须取得本机可信代码批准，未信任包只能使用声明式安全贡献。

Extension Service 只接受 `easycode-extension.json` v1 并把解析结果写入 `easycode.lock` v1。Manifest 分别声明 Windows/Android 本机宿主变体和 Windows/ADB/Android 本机/无目标范围；发布器只携带 lock 选择的 `ecx-runtime-1` 密封产物，不复制扩展源码、测试或开发配置。完整线格式和失败语义见 [`EXTENSIONS.md`](EXTENSIONS.md)。

功能扩展可以通过版本化贡献点提供完整领域模型、工作区、编译步骤、运行模块和 Player 模块。首个正式版本保留这套通用扩展地基，但不交付页面导航包，不注册页面工作区、`页面.*` 函数、Page Model、扫描服务、拓扑投影或 Player 依赖。通用贡献点由不进入产品清单和发布闭包的中性 Harness 扩展验证；未来领域扩展必须通过新的功能规格、架构决策和垂直切片立项。

## 6. 保存、并发与恢复

每个结构命令携带当前 revision 或基线内容哈希。Program Service 只接受基于当前模型的命令；遇到外部修改时，Workspace Service 返回内存模型、磁盘模型和基线信息供用户比较，不静默覆盖任何一方，也不通过反复重试制造无限 409。

保存流程为：Schema/引用校验 → 规范化序列化 → 同目录临时文件 → 原子替换。写入失败时保留内存模型、Control 草稿和撤销历史。损坏 JSON 或未知 Schema 版本只进入只读恢复与诊断，不由编辑器自动修复并覆盖磁盘。

## 7. 运行时与平台

FastAPI/WebSocket 只承载 IDE 工作区命令、运行控制和增量事件流。Runtime Coordinator 持有调用栈、项目变量会话副本、当前目标、驱动、资源缓存、监听状态和结构化日志。普通本地语句的 Runtime 热路径不得为驱动执行回到 WebView 或开发后端；项目显式调用的类型化 HTTP 函数按自身网络契约直接由 Runtime 执行，不构成 IDE 往返。

消息监听采用协作式串行调度：当存在候选消息且监听条件成立时，运行时在安全检查点挂起主调用栈，串行调用监听器绑定的项目函数；处理函数正常返回后，从主流程下一条语句继续。监听器不能创建第二条并发界面操作流。

主动暂停在同一进程内保存现场并允许继续。停止、取消、进程退出或崩溃不恢复旧调用栈；下一次运行从入口开始，诊断保留最后稳定语句与上下文。

Windows Player 可以在串行流程内切换 Windows 和 ADB 目标，任意时刻只有一个当前目标。Android Runtime 使用 Kotlin/C++、MediaProjection、AccessibilityService 与本机文件授权实现驱动，继续执行同一 ECIR，不依赖 ProgramDocument、Windows、IDE 后端或 Python 环境。Windows IDE 通过 USB/ADB 部署测试 APK、发起原生调试并读取日志；该路径必须与“Windows Runtime 把设备作为 ADB 操作目标”分开标记和验收。

Player 字段捕获使用与 IDE 相同的强类型结果，但通过独立 `PlayerControlDestination` 写入运行方案或私有图片覆盖，不得伪造编辑会话或修改 ProgramDocument/ECIR。权限只在终端用户主动触发动作时按需请求，实际能力是作者许可、字段类型、发布闭包、宿主能力和当前权限的交集。

File Integration Service 对 `FileReference` 与 `DirectoryReference` 执行平台载荷解析和能力校验。递归删除只有独立危险能力、作者审核和 IDE 调试或 Player 对 `authorization_root_id + 执行配置 revision` 的实际执行确认同时有效时才进入宿主；派生引用只能缩小范围，每个后代在删除前重新验证仍位于授权树内。目录复制/移动不合并或覆盖已存在目标；树操作不假装可回滚，中途失败返回类型化部分完成报告。

Recorder Service 旁路订阅当前目标帧和运行标记，以有界队列写入版本化本机录制会话。目标空间变化建立新片段；未启用录制时不创建订阅或 Worker。Replay Service 首版只对不可变历史帧执行官方无副作用图像/OCR 回放实现；控件树和第三方扩展回放不在像素帧首版范围。每次分析把精确帧范围、ProgramDocument/ECIR、实际资源字节、官方契约、OCR 模型/字典、`easycode.lock`、参数与回放实现固化为不可变、按内容寻址的 `AnalysisInputBundle` 后生成新报告，不能只保存 revision/hash；清理快照后报告明确降级。Recorder/Replay 不修改或注册为 ProgramDocument/ECIR 运行语义，也不能恢复或重放副作用。默认导出不含快照，高级可重现导出才在逐类披露后包含它。

运行计划属于 Player 宿主控制面而非 ProgramDocument。Windows 每用户 Player Hub 可以启动多个已安装项目/方案并向已配对 LAN 实例派发；Android 只调度当前 APK 方案。远程派发使用独立授权和 `dispatch_id` 幂等接纳，不通过普通消息隐式启动任务。

首个正式版本的 Android 发布物是可安装的签名 APK。它包含 Android Runtime、小屏 Player UI、ECIR、资源和目标平台兼容的已构建扩展闭包；数据线断开且 IDE/后端关闭后仍须完成启动、配置、运行、暂停、继续、停止与诊断。Android 真机闭环未通过前可以继续开发 Windows/ADB 切片，但不得放行首个正式版本。

## 8. 非目标与后续细化

首版不建设可编辑源码、通用投影式语言平台、公开扩展市场、第三方目标驱动、页面导航、浏览器 DOM 自动化、自动遥测、云端设备舰队、iOS 或 macOS 宿主。旧 `.easy` 与旧画布项目不迁移。首版冻结完成后的作者效率序列允许按 [`AUTHORING_AUTOMATION.md`](AUTHORING_AUTOMATION.md) 实现结构化操作录制、可靠控件选择器、项目触发器和第一方浏览器 DOM 扩展；这不回写首版完成声明，也不改变上述首版历史边界。

条件、结果成员、调用边界、结构化集合、完整递归纯值表达式、官方 v1 函数目录和扩展线格式已经冻结。Control 像素布局和 Harness 数值安全预算可以在不改变领域模型、宿主/目标矩阵或表达能力的前提下由实现与证据收束。
