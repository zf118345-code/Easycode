# EasyCode vNext 细分规范

这里保存当前架构各领域的详细契约。产品范围、总体架构、交互和测试放行分别以根目录 `PRODUCT.md`、`docs/ARCHITECTURE.md`、`design.md` 和 `docs/TEST_HARNESS.md` 为准。

项目格式：`6`（已冻结；不兼容旧画布、格式 5 或 `.easy` 试验项目）

ProgramDocument Schema：`1`

ECIR 版本：`1`

扩展 Manifest：`easycode-extension.json / manifest_version 1`

扩展锁：`easycode.lock / lock_version 1`

扩展运行产物：`ecx-runtime-1`

## 文档地图

- [PROGRAM_MODEL.md](PROGRAM_MODEL.md)：ProgramDocument、稳定 ID、纵向投影和 ECIR 边界。
- [PROGRAM_SEMANTICS.md](PROGRAM_SEMANTICS.md)：结构化程序语义、类型、值表达式和控制结构，不定义用户可编辑文本。
- [ARCHITECTURE.md](ARCHITECTURE.md)：ProgramDocument、ECIR和运行分层细节。
- [PROJECT_FORMAT.md](PROJECT_FORMAT.md)：项目文件与自动保存。
- [FUNCTIONS.md](FUNCTIONS.md)：官方 v1 完整最小目录、稳定 ID、宿主/目标矩阵、函数分类、契约、组合与融合实现。
- [EXTENSIONS.md](EXTENSIONS.md)：`easycode-extension.json`、可信本地代码、声明式安全贡献、宿主变体、`easycode.lock` 与密封发布闭包。
- [VARIABLES.md](VARIABLES.md)：局部变量、项目变量、运行副本和 Player 初始值绑定。
- [PLAYER_CONSOLE.md](PLAYER_CONSOLE.md)：Windows 单窗口多实例控制台、独立工作进程与恢复边界。
- [FILES.md](FILES.md)：文件读写与替换、目录树操作、受控递归删除、强类型授权和并发/部分完成语义。
- [NETWORK.md](NETWORK.md)：类型化 HTTP、实例身份、跨设备配对和 LAN 信任边界。
- [MESSAGES.md](MESSAGES.md)：一个或多个明确实例的可靠消息、独立收件副本、同机/局域网路由与未来广播/工作队列。
- [SCHEDULES.md](SCHEDULES.md)：本地计划、Windows 批量运行、Android 当前 APK 计划与 LAN 幂等派发。
- [TARGETS.md](TARGETS.md)：Windows、ADB、Android本机和多目标。
- [ANDROID.md](ANDROID.md)：Android 本机 Runtime、签名 APK、权限、真机调试与首版完成门。
- [OFFLINE.md](OFFLINE.md)：Player 本地优先、网络能力分级、完整依赖闭包与离线验收。
- [UPDATES.md](UPDATES.md)：IDE、Player 应用与项目内容的可关闭服务器更新、作者控制测试通道、签名信任链和安全切换。
- [RESOURCES.md](RESOURCES.md)：资源标识、选择、引用与生命周期。
- [REPLAY.md](REPLAY.md)：首版三平台完整帧录制、不可变会话、离线视觉分析、历史 Capture、导出和崩溃诊断证据。
- [PLAYER.md](PLAYER.md)：表单绑定与发布产物。
- [PUBLISHING.md](PUBLISHING.md)：独立 Windows Player 的专用入口、HTTP/导入图、Player-only Web 与源码隔离发布边界。
- [IDE_UX.md](IDE_UX.md)：IDE信息架构与交互。
- [UI_SYSTEM.md](UI_SYSTEM.md)：跨工作区、跨扩展与跨平台 Player 的统一界面系统。
- [UI_COMPONENT_SYSTEM_PLAN.md](UI_COMPONENT_SYSTEM_PLAN.md)：全局 UI 组件化改造、功能保护、迁移阶段、防回退规则与验收矩阵。
- [TESTING.md](TESTING.md)：vNext 专项验收矩阵。
- [RELEASE_GATES.md](RELEASE_GATES.md)：首个正式版本从统一值模型到发布审计的顺序阶段门。
- [RELEASE_AUDIT.md](RELEASE_AUDIT.md)：各阶段当前证据、真实性分级和仍阻止正式放行的环境事项。
- [FINAL_GAP_LEDGER.md](FINAL_GAP_LEDGER.md)：历史待办与当前源码合并后的正式版收尾总账，区分已闭环、部分完成、未实现和外部验收。
- [ACCEPTANCE_PROJECTS.md](ACCEPTANCE_PROJECTS.md)：六个固定真实验收项目、候选哈希纪律和当前环境缺口。
- [WINDOWS_INSTALLATION.md](WINDOWS_INSTALLATION.md)：Windows Player 当前用户安装、离线修复、卸载、数据保留与升级边界。

## 维护规则

- 只记录长期契约，不新增日期化实施报告或阶段周报。
- 实现证据进入 Harness 产物，不把一次测试数字写成长期事实。
- 新功能使用 `docs/templates/FEATURE_SPEC.md`，通过规格审查后采用垂直切片实施。
- 旧画布 Schema、试验性文本流程和废弃节点模型不得反向约束当前设计。
- 格式 5 `.easy` Source、文本解析/语义编辑、旧函数文件服务和页面拓扑实现已经退役；旧 HTTP 名称只允许作为无状态结构化 `410` 边界，不能注册旧业务服务或读取格式 6 工作区。
- ProgramDocument 是项目函数唯一可编辑事实；结构化语句、只读摘要和扩展派生视图均为投影，ECIR 是确定性构建产物。
- 函数库对用户只区分官方、项目和扩展，并按用途组织；原子/标准是内部实现层级。
- 首个正式版本不注册 `页面.*`、页面工作区、Page Model 或拓扑投影。`image / ocr / page` 仍是始终可选的通用资源分类，`page` 不具备领域或运行语义。
