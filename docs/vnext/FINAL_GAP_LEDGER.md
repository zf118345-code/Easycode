# EasyCode 正式版功能查漏总账

状态：`Active`  
事实基线：2026-09-04，格式 6 / ProgramDocument 1 / ECIR 1

本文件把历史待办与当前源码合并为唯一的收尾总账。状态只允许：

- `Closed`：此前已形成垂直切片和相应证据，本轮不重复实现；
- `Partial`：已有一部分，但至少缺少契约、宿主、发布或真实证据中的一环；
- `Open`：正式范围内尚未实现；
- `External`：需要生产凭据、额外物理设备或托管基础设施，不能用替身冒充完成。
- `Deferred`：产品负责人明确推迟到设备、客户现场或服务上线阶段；不阻塞当前 UI 工作，但仍不能表述为通过。

每个代码目标均按同一完成门验收：函数/结构契约 → IDE 可创建 → 检查器 → Compiler/ECIR → Windows 与 Android Runtime → Player → 发布依赖闭包 → 失败恢复/诊断 → 对应真实宿主。

## A. 官方基础能力

| ID | 能力 | 当前事实 | 状态 | 完成验收 |
|---|---|---|---|---|
| REQ-GAP-001 | 画面保存与裁剪 | 单一 `画面.保存` 原子已覆盖当前/冻结画面、可选裁剪区域、PNG/JPEG 与授权文件；Windows/ADB 原子写盘和 Android 私有目录/SAF 写入均已接通；G12 已在 API 33 物理手机把 1080×2340 MediaProjection 帧保存为真实 PNG 并由项目内断言确认文件存在 | Partial | 自动证据与 G12 真机私有目录证据已通过；最终统一验收补 Windows/ADB 文件选择、Android SAF Provider、裁剪/JPEG 真机、磁盘故障与发布闭包证据 |
| REQ-GAP-002 | 手势路径执行 | `official.input.drag` 已接受 Player 可采集的 `gesture_path`，Windows/ADB/Android Runtime 均有路径执行入口 | Closed | 保留既有证据，最终统一回归 |
| REQ-GAP-003 | 控件状态读取 | `ControlStatus`、官方契约、ECIR、Windows UIA、ADB UIAutomator 与 Android Accessibility 已接通；平台不能读取的可选字段保持无结果 | Partial | 72 项控件聚焦测试与 Android 定向编译/单测通过；最终统一验收时补真实 Windows、模拟器与 Android 本机状态读取证据 |
| REQ-GAP-004 | 控件通用操作 | 聚焦、设置值、选择项目、切换开关和滚动到控件已形成三端适配；Windows/Android 使用原生语义 Pattern/Action，ADB 只承诺 UIAutomator 能可靠表达的行为 | Partial | 自动证据同 REQ-GAP-003；最终统一验收补不同控件类型的真实宿主成功与不支持失败证据，不允许坐标静默冒充 |
| REQ-GAP-005 | 剪贴板读写 | 官方契约、ECIR、Windows Host 与 Android 本机 ClipboardManager 已接通；ADB 目标运行时明确使用 Windows 宿主剪贴板而非伪造设备剪贴板；G12 已在物理 Android Runtime 完成写入后读取并由项目内条件断言原文一致 | Partial | 自动证据与 G12 真机往返证据已通过；最终统一验收补 Windows、空剪贴板、后台限制和独立发布闭包 |
| REQ-GAP-006 | 日期时间运算 | 纯值注册表 v7 已完成日期/时间/日期时间的加减、差值、格式化与解析，并统一 Python/Android ISO 标量和时区失败语义 | Closed | 自动证据：Python Runtime/类型目录 70 项聚焦测试通过；Android `PureOperationsCoreTest` 通过。最终统一回归仍会验证实机发布闭包 |
| REQ-GAP-007 | 文本信息提取 | 纯值注册表 v7 已完成正则指定分组、全部捕获分组和首个 int64 提取 | Closed | 自动证据同 REQ-GAP-006；覆盖无匹配、非法正则、组越界与溢出契约，最终候选再统一回归 |
| REQ-GAP-008 | Windows 窗口调整 | 已增加移动、调整大小和统一的“改变显示状态（还原/最小化/最大化）”，窗口状态同时返回最大化标记；真实 WinForms 已完成移动、缩放、三种状态与关闭。激活函数补充线程输入队列、交互 Shell 与有界 Alt 转换回退，但当前 Codex 终端仍被系统前台策略拒绝并正确报错 | Partial | 24 项聚焦测试通过；真实证据为 `output/functional-gap-evidence/windows-control-window-evidence.json`。最终候选需从 Player 交互进程复核激活，并补多显示器负坐标、系统最小尺寸约束、UWP/管理员窗口 |
| REQ-GAP-009 | 像素与颜色 | 已增加 `颜色.读取`、`颜色.查找` 与表达式 `颜色.接近`；三者共用 RGBA、0..255 通道/容差、冻结帧和逐行确定性首个结果语义；G12 已在物理手机从同一真实 MediaProjection 帧读取 `(0,0)` 颜色，再以零容差在全帧找到该颜色 | Partial | Python 合成像素、纯值跨端与 G12 Android 真机证据通过；最终统一验收补 Windows、ADB、大画面取消与容差边界证据 |
| REQ-GAP-029 | 官方函数结构值可组合性 | 78 个官方函数的参数与返回类型已完成全量契约审计；补齐目录筛选/条目、目录操作报告、消息结果与窗口选择器记录，修正 Android 目录筛选和树报告字段，使界面可创建、结果可选字段、两端可执行 | Closed | 自动防回归要求所有公开参数和返回值只能是已登记原子、权限引用、容器或命名记录；函数目录、类型目录、视觉、文件与运行适配器聚焦测试通过，最终统一回归不重复开发 |
| REQ-GAP-030 | Android 官方指令发布闭包一致性 | 修复 Kotlin APK 预检遗漏 `等待应用退出` 与剪贴板读写的问题；Python Publisher 与 APK 内预检现在精确接受同一 opcode 集合，并覆盖全部声明支持 Android 本机的官方函数 | Closed | Python Android 发布检查 32 项通过；Kotlin `AndroidPackagePreflightTest` 编译与定向测试通过；自动测试要求两层白名单精确相等并覆盖官方 Android 支持矩阵 |
| REQ-GAP-031 | Windows 当前用户安装介质 | 已形成无 Python 依赖的 EasyCode 自有安装界面、安装器/应用双层哈希验证、同卷原子升级、安全卸载、开始菜单/可选桌面入口、HKCU 卸载登记及 Player Hub 登记。真实旧版→G10 升级暴露 Hub 把版本误当安装身份以及登记超时误报整次安装失败；G11 已改为按稳定安装位置复用身份，并把 Hub 登记/停用收窄为 30 秒有界、可修复的附属步骤 | Partial | `output/g11-windows-player-functional-final/windows-install-upgrade-repair-uninstall-evidence.json` 证明 D 盘隔离当前用户环境完成旧版安装、G11 升级、同版本修复和卸载；安装/实例 ID 与数据目录保持，程序/注册表/快捷方式移除且用户数据保留。剩余干净客户机与生产 Authenticode 归 REQ-GAP-026 |
| REQ-GAP-032 | Android 本机录制共享方案契约 | 删除 Python Player 中“Android 本机录制尚未实现”的过期保存阻断；共享前端、Python 方案与 Kotlin Android 录制器现在接受同一 revision 绑定录制设置 | Closed | 录制回放 9 项聚焦测试通过；已有 Android 真机录制证据继续冻结，最终候选只做统一回归 |
| REQ-GAP-033 | Android 应用启动与生命周期边界 | Android 11+ 通过 Launcher 查询支持普通可启动应用的包可见性且不申请全包枚举；`等待应用退出` 从 Android 本机发布闭包移除，在开发/发布阶段阻止而非运行时必然失败 | Closed | 官方函数/Android 交付 54 项聚焦测试验证平台矩阵、Python/Kotlin 预检精确相等和 Manifest 可见性；最终候选补不同 Android 版本真实启动证据 |
| REQ-GAP-034 | 控件等待出现与消失 | 新增两个可检查、可编译的标准函数；每轮重新查询 UIA/UIAutomator/Accessibility，不复用旧控件引用，超时是正常空结果 | Closed | Python/Android 聚焦测试通过；`output/functional-gap-evidence/ddt-v6-control-wait-real.json` 证明冻结 Windows Player 依次命中 ChatGPT、微信、模拟器 Android Button 和恢复后的微信，缺失结果会主动失败 |
| REQ-GAP-035 | 应用运行状态与停止 | 新增 `应用.是否运行` 与 `应用.停止`；Windows 绑定本次启动的精确进程，ADB 绑定已校验包名并使用固定 argv，绝不开放自由 Shell；无 Activity 时改用包管理器解析 Launcher，兼容移除 `monkey` 的云机/模拟器。真实冻结 Player 验收曾发现隔离 Worker 漏接两个新 opcode，现已修复并用适配器/分派集合一致性测试防回归 | Partial | `output/g10-windows-lifecycle/windows-application-lifecycle-evidence.json` 证明无系统 Python 的 G10 冻结 Runtime 完成真实 WinForms 启动→运行确认→停止→停止确认→退出结果；`emulator-5556` 已完成包名启动与生命周期。剩余 API 21/24 和不同厂商设备矩阵并入统一验收 |

## B. 结构化 IDE、调试与恢复

| ID | 能力组 | 当前源码事实 | 状态 |
|---|---|---|---|
| REQ-GAP-010 | 提取函数、复制/剪切/粘贴、多选、跨层级移动 | 提取与多选、标准复制、延迟剪切、锚点粘贴、一次撤销的原子批量命令、连续选择批量层级调整及同函数公共参数批改已经闭环；服务端重新校验结构剪贴板并保证批处理失败零写入 | Closed |
| REQ-GAP-011 | 函数/变量/资源引用、项目搜索、跳转、安全重命名/删除 | 稳定 ID 引用索引、引用端点、问题跳转及生命周期阻止已经存在；最终回归仍需覆盖跨类别搜索结果 | Closed |
| REQ-GAP-012 | 断点、暂停/继续/单步、当前语句、变量/调用栈、日志跳转、失败帧与诊断 | Runtime、HTTP 和 IDE 运行控制台已经接通 | Closed |
| REQ-GAP-013 | 自动保存、历史、损坏恢复、外部冲突 | 原子仓库、历史/恢复 API 与 IDE 历史入口已经存在 | Closed |
| REQ-GAP-014 | 冲突处理和跨重启历史恢复 | 原子命令成功即保存，因此没有独立“内存 ProgramDocument”需要三方合并；界面已展示命令基线与磁盘 revision，可保留 Control 草稿稍后处理或明确重载；每次修改前快照支持跨重启查看与恢复 | Closed |

## C. 宿主、发布与运行闭环

| ID | 能力组 | 当前事实 | 状态 |
|---|---|---|---|
| REQ-GAP-015 | Windows、ADB、跨目标与跨平台控件 | 真实 Windows UIA、模拟器/手机 ADB 和 Windows→ADB→Windows 已取得阶段证据 | Closed |
| REQ-GAP-016 | 六个固定验收项目 | 六项固定范围、真实性分级和候选纪律已写入 `ACCEPTANCE_PROJECTS.md`；ACC-002 已由冻结 Windows 候选通过，Android v4 双角色及 LAN 证据已锁定。其余项目先补未覆盖环节，功能冻结后再统一重跑 | Partial |
| REQ-GAP-017 | Windows 独立 Player | 无系统 Python的冻结包已运行；安装/卸载、生产 Authenticode 与干净客户机矩阵未完成 | Partial |
| REQ-GAP-018 | Android 本机完整闭环 | OCR、HTTP、消息/监听、计划、录制、扩展、内容/APK 更新、Accessibility、MediaProjection 和 SAF 已进入源码；2026-09-04 候选又在 API 33 真机与模拟器完成取帧/OCR、语义控件、输入、图像、文件、录制和运行终态。G12 真机进一步用项目内断言完成画面保存、取色/找色与剪贴板往返，证据为 `output/g12-android-basics/android-basics-real-device-evidence.json`；非小米实体设备按 ADR-097 延期，正式签名和当前小米真机断线独立矩阵仍未闭环 | Partial |
| REQ-GAP-019 | Android 动态最低版本 | 项目能力闭包已计算动态 `minSdk`；最低 WebView 已冻结为 Chromium 64，APK 证据写入该值，Android 在创建共享 Player 前检查 User-Agent，不兼容或无法识别时显示原生说明而不加载页面 | Partial |
| REQ-GAP-020 | 录制与离线回放 | Windows/ADB/Android 录制和历史帧图像/OCR 分析已实现；最终候选需统一验证慢盘、空间上限、中断恢复和脱敏导出 | Partial |
| REQ-GAP-021 | 计划、多实例、LAN 与幂等派发 | Windows 与 Android 调度、消息、同机加密 LAN 已实现；2026-09-04 以显式配对和消息权限完成模拟器→物理 Android 的真实同步接收、监听接手、处理后恢复及双端已读回执。Harness 现在会在超时空结果或监听器未接手时主动失败，不再用无条件日志制造通过；反向 NAT、第二台物理主机、防火墙/睡眠/网络分区仍未验证 | Partial |
| REQ-GAP-022 | 更新与离线 | 签名协议、自建 Feed、关闭零外连、Windows helper、Android 内容/APK 路径已实现；G11 冻结 Windows Player 已完成文件与 HTTP 签名项目，Android 同一网络 Runtime 已在 API 33 真机与 API 34 模拟器完成请求/上传/下载。证据：`output/g11-file-http-acceptance-final/file-http-evidence.json`、`output/g11-android-network-runtime/android-network-real-device-evidence.json`；生产通道、正式签名与完整内容/APK 更新最终候选矩阵仍未闭环 | Partial |

## D. 性能、发布与外部条件

| ID | 能力组 | 当前事实 | 状态 |
|---|---|---|---|
| REQ-GAP-023 | 1 万语句、1000 函数、1 万资源、1/2/4/8 实例 | 已有可复现基线，最终候选只需统一复核哈希 | Closed |
| REQ-GAP-024 | 24 小时长稳 | 首轮约 4 小时 15 分因专用目标窗口被外部最小化按契约终止；UI 冻结后 G13–G15 高频预检又发现历史 Session 每轮残留 1 个 Windows 同步句柄，G16 已释放终态运行期对象并通过同哈希 30 分钟预检。旧失败与中间证据均保留；G16 已于 2026-09-04 20:00:35 从零启动完整 24 小时计时，当前只能标记运行中 | Partial |
| REQ-GAP-025 | Android 能耗/发热/帧延迟/内存与存储清理 | G16 安装包已从 API 33 真机回读并与输入 APK 哈希精确匹配；授权后的 36 秒短测完成 1 次真实运行和 4 个资源样本，当前正执行同一 APK 的 1 小时 PSS/RSS、电量、温度、热状态与私有数据采样。完成前仅作为前置测试；非小米多设备矩阵按 ADR-097 延期 | Partial |
| REQ-GAP-026 | 生产签名和干净客户机 | 需要 Authenticode、正式 Android keystore 和无开发环境客户机 | External |
| REQ-GAP-027 | 第二台物理 LAN 设备矩阵 | 当前已有同机双进程和模拟器→物理 Android 的协议与业务证据；两台独立物理宿主的防火墙、地址变化、睡眠/唤醒、网络分区和重连按 ADR-097 延期 | Deferred |
| REQ-GAP-028 | 官方托管发布服务 | 客户端开放协议、自托管 Feed 与“未连接时失败关闭”已完成。作者身份/OIDC、正式域名/TLS、不可变对象存储/CDN、配额计量、监控/备份/灾备属于真实服务建设，按 ADR-097 延期；上线前入口保持不可用，不用本机服务伪装 | Deferred |

## 明确范围外

页面拓扑/自动导航、浏览器 DOM 专用自动化、iOS、macOS、商业授权/VIP 激活、云端设备舰队与运行遥测、旧画布/`.easy`/格式 1–5 迁移继续保持范围外，不得在收尾阶段偷偷重新引入。

## 实施顺序

1. REQ-GAP-001–009、REQ-GAP-029–030 与 REQ-GAP-032–033 的源码能力已闭合；已有证据暂时冻结，三端真实结果统一在最终候选验收。
2. REQ-GAP-014 已按原子命令事实关闭；REQ-GAP-019 的实现已冻结，低版本设备证据并入最终候选矩阵。
3. 2026-09-04 已完成能力闭包复核：正式范围没有 `Open` 项；78 个官方函数及已批准 ProgramDocument 值/语句的契约、检查、Compiler/ECIR、Python Runtime 和 Android 发布指令集合一致性聚焦回归为 `74 passed`。从此停止重复开发已闭合能力，进入同一最终候选的统一验收；若验收失败，再按真实失败回到对应垂直切片修复。
4. REQ-GAP-026–028 保持显式外部验收，不使用模拟证据改写状态。

当前执行策略：正式范围源码、UI 与当前设备可完成的功能缺口已经收口并冻结为 G16；已通过真实宿主或形成稳定自动证据的能力不重复消耗时间。G16 正在执行唯一一次最终 24 小时长稳，期间不改动候选；只有长稳或后续外部矩阵暴露真实失败时，才回到对应垂直切片修复并重新冻结候选。

## 2026-09-04 源码冻结判定

- “没有 `Open`”只表示正式范围内没有已知的源码功能空洞，不表示所有发布门已经通过。
- `android_local` 契约仍显示 `planned` 是刻意的发布保护：只有签名 APK 在物理设备脱离 IDE、开发后端和数据线完成对应能力后，才能把该平台证据提升为 `verified`；不得仅凭共享 Python 实现或模拟器测试开放。
- Windows 窗口激活复核时，当前 Codex 终端所在会话的 `GetForegroundWindow` 返回句柄 `0`；移动、缩放、显示状态、关闭及 UIA 操作真实成功，激活按稳定错误 `window.operation_failed` 失败。该项必须由可访问交互桌面的 Player 启动路径复核，不能用“置顶但未成为前台”冒充成功。
