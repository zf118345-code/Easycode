# EasyCode 首个正式版本发布审计

状态：`In progress`  
审计基线：2026-09-03，格式 6 / ProgramDocument 1 / ECIR 1

本文件只汇总阶段门与可复现证据，不替代各领域规格。状态含义：

- **通过**：自动验收与要求的真实宿主验收都已取得证据；
- **部分通过**：实现和部分宿主已验证，但完成门要求的环境矩阵尚未全部覆盖；
- **环境阻塞**：代码侧无可继续绕过的安全路径，需要设备设置、第二台主机或生产基础设施；
- **进行中**：可重复 Harness 已启动，尚未达到规定测量时长。

## 阶段门总览

| 阶段 | 实现状态 | 自动验证 | 真实操作/宿主证据 | 放行结论 |
|---|---|---|---|---|
| G1 统一值模型与参数交互 | 完成 | 表达式、类型、捕获回填、枚举和所有 Control 投影已覆盖 | DDT 浏览器与 Windows/ADB 字段采集已走通 | 通过 |
| G2 官方基础能力闭包 | 源码冻结 | 官方 v1 目录 78/78 有 Runtime 绑定；已批准纯值操作没有 `planned` 项；2026-09-04 闭包与全量自动回归通过 | G11 冻结 Runtime 已完成 Windows 应用生命周期、文件与 HTTP 签名项目；Android 网络 Runtime 已在 API 33 真机和 API 34 模拟器实跑；G12 API 33 真机项目内断言完成画面保存、颜色读取/查找和剪贴板往返。窗口前台、物理断线与发布签名继续按真实门验收 | 待真实候选收口 |
| G3 结构化编写与调试 | 完成 | 结构命令、撤销、搜索、断点、暂停/继续/停止和错误定位通过 | 10,000 语句项目完成浏览器编辑、滚动与检查器操作 | 通过 |
| G4 项目持久化与恢复 | 完成 | 原子保存、冲突、损坏恢复、历史和诊断故障注入通过 | 浏览器恢复/冲突路径已走查 | 通过 |
| G5 Windows 与 ADB | 完成 | 跨目标、能力守卫、坐标来源和断连语义通过 | Windows UIA、雷电/模拟器 UIAutomator、连接手机 ADB 与 Windows→ADB→Windows 已验证 | 通过 |
| G6 独立 Player 与 Android 本机 | 完成候选 | 发布闭包、源码隔离、共享 Control、Android Runtime/API 通过 | 独立 Windows Player、API 34 模拟器与 API 33 物理真机关键切片通过；2026-09-04 同轮候选在模拟器和真机完成取帧/OCR、语义控件、输入、图像、文件、录制及终态断言；权限撤销/恢复、逐项授权、严格离线、旋转与强制停止已有证据，计划休眠/ARM 长稳/非小米实体设备待补 | 部分通过 / 矩阵进行中 |
| G7 录制、计划、协作与更新 | 完成候选 | 录制/回放、计划、消息、LAN、幂等派发、更新签名与回滚通过 | Windows/ADB/Android 模拟器录制，真实 Windows 调度/更新及同机加密 LAN通过；新增模拟器→物理 Android 的显式配对、真实同步消息、监听接手、主流程恢复和双端已读证据 | 部分通过；反向 NAT、物理双机、真机更新和官方托管未验证 |
| G8 性能、长稳与发布审计 | 实施中 | 大项目、资源/语句虚拟化、Worker/Session 句柄回归、UI-1 至 UI-22 通过 | Windows Capture、ADB 模拟器/手机、1/2/4/8 冻结 Player 已测；G16 Runtime 候选 30 分钟预检通过，未完成的 G16 24 小时运行已按 UI 冻结顺序停止并清理；UI-22 尚未并入冻结发布候选 | 进行中 |

## G8 可复现证据

### 大项目与编辑器

- 固定数据集：1,001 个项目函数、重型函数 10,000 条语句、10,000 个资源，数据集哈希记录在 `output/g8-performance/benchmark.md`。
- 当前格式重建数据集后的冷打开 `518.782 ms`；函数目录 p50 `86.137 ms`；资源目录 p50 `21.885 ms`；全项目文本搜索 p50 `150.892 ms`；重型文档局部校验 p50 `5.171 ms`；完整链接加载 p50 `112.586 ms`；编译 p50 `392.068 ms`。
- 语句列表在 10,000 条下保持约 39 个 DOM 行；资源末尾滚动在 3,334 个同类资源下保持 49 个卡片并正确到达最后一项。
- 1280、900、700 像素宽真实浏览器审查无页面级横向溢出；程序检查器和计划检查器在窄窗口改为显式抽屉，不再永久挤占主工作区。

### 冻结 Player 与捕获

- 最终候选 `output/g8-windows-player-final/Player_Bundle` 已重新组装并通过 1/2/4/8 实例启动：8 实例 RSS 峰值约 `776 MiB`，空闲 CPU 样本为 `0%`，最慢就绪 `1.565 s`。
- 2026-09-04 UI-18 冻结后重新构建通用 Runtime，并分别组装 DDT 验收包与当前格式的专用长稳 Harness。高频预检发现历史 `RuntimeSession` 在终态后仍保留仅供暂停/继续使用的 `threading.Event`，在 Windows 中造成每次运行稳定增加 1 个内核句柄；G13–G15 的原始报告保留为定位与失败对照，不作为候选。
- G16 已在终态释放 Worker 代理和运行期同步对象，同时把 Harness 加强为：业务终态后必须在 5 秒内确认隔离 Worker 真正退出，否则失败关闭。DDT 候选清单为 `output/g16-session-gate-windows-player/candidate-manifest.json`，核心 Runtime SHA-256 为 `f12ac55a364f6269c1babc7e89035e6933723756aecf8aa6b64f5443457e0151`；长稳可执行文件 SHA-256 为 `c2c2a44d1e5fa93c274c5569bfb657b237ee9592bae3cf805f187e219d9c6507`，项目包 SHA-256 为 `7fe70119e0d0500ed5618293c27e75e6a3e37c2685246721b9a782fc946c5264`。两种分发复用同一 Runtime 字节，只允许签名项目包不同。
- G16 的 5 分钟高频回归完成 10/10 次任务，修复前同阶段稳定句柄由 399 增至 404，修复后由 404 回落并稳定在 393。随后 `output/g16-session-gate-soak-preflight-30m` 以正式 30 秒采样、5 分钟任务间隔完成 60 个样本与 6/6 次任务，0 失败、全程单进程、数据目录增长 `0`；RSS 趋势 `-2481922.119 bytes/hour`，句柄趋势 `-0.343/hour`、首尾四分位差 `0`，候选哈希精确匹配，分析器结论为 `passed`。它是最终 24 小时前置门，不替代完整 24 小时结论。
- G16 最终 24 小时长稳曾于 2026-09-04 20:00:35（Asia/Shanghai）启动，但在 UI 尚未冻结、候选仍会变化时继续计时已无发布意义。按用户明确要求，2026-09-04 已精确停止该次 Harness、子进程与冻结 Player，并删除唯一未完成目录 `output/g16-session-gate-soak-24h-final`；30 分钟预检与其他已完成证据保留。UI 冻结后必须用同一最终候选哈希从零重新计满 24 小时，旧运行不得拼接或冒充通过。
- Windows Graphics Capture 对真实 Harness 窗口连续取得 1,000/1,000 帧，p50 `0.41 ms`、p95 `0.66 ms`、句柄增长 `0`；证据为 `output/g8-performance/windows-capture.json`。
- ADB 模拟器首帧等待 `187 ms`，连接手机首帧等待 `312 ms`；证据分别为 `android-adb-emulator.json` 和 `android-adb-phone.json`。这两项是 Windows/ADB 宿主证据，不替代 Android 本机真机。

### Worker 资源生命周期

- 旧冻结候选在每次一-shot 隔离 Worker 完成后保留 Windows 进程/队列句柄；20 分钟样本从约 405 阶梯增长到 457。
- Runtime 现在在 Worker 终态后显式关闭 Queue feeder、管道端点和 `multiprocessing.Process` 原生句柄，并允许 shutdown 对已关闭代理幂等执行。
- 新候选 13 次密集真实任务后句柄从首样本 422 回落到 415；Windows 自动回归在一次预热后连续 8 个 Worker 的句柄增长不超过 4。

### 自动验证基线

- 2026-09-04 UI-20 源码基线：前端 105 个测试文件、540 项通过；TypeScript、ESLint、IDE 生产构建与 Impeccable 静态扫描通过。DDT 在 1440×900 完成程序、资源、目标、Player、扩展工作区真实浏览器复核，在 800×900、640×900 完成程序工作区复核，控制台 0 警告、0 错误。UI-20 统一全局排版和语义色令牌，重组活动栏，精简状态栏，并强化结构语句而降低普通调用的视觉噪声。既有 Python `1303 passed, 2 skipped`、Player-only 构建与 Android `productionDebug` 证据未因本轮纯前端改动重跑。UI-20 晚于 G16 冻结产物，下一发布候选必须重新构建并锁定精确哈希。
- 2026-09-04 UI-21 源码增量：把信息克制设为硬约束，运行目标宽屏从重复三栏改为列表—设置两栏；资源技术元数据、继承目标和扩展包技术标识按需展示；函数库逐行插入操作仅在悬浮、聚焦或选中时出现。应用外壳全局屏蔽浏览器原生右键菜单，文本输入器使用 EasyCode 复制/剪切/粘贴/全选菜单，语句右键复用已有移动、复制、提取与删除动作，空白区域不展示无意义菜单。全量前端 106 个测试文件、544 项测试、TypeScript、ESLint、生产构建与 Impeccable 静态扫描通过；真实浏览器确认输入器菜单与空白区域行为。UI-21 晚于 G16，下一发布候选必须重新构建并锁定精确哈希。
- 2026-09-04 UI-22 源码增量：按“首要信息、辅助信息、追溯信息”重新审查程序、变量、资源、Player、运行记录和扩展工作区。删除重复入口与重复绑定摘要；变量限制、帧技术字段和扩展开发者字段改为可识别状态的按需披露；对用户可见的扩展参数类型和画面方向完成中文投影。回放分析目录在合法但没有图像/OCR语句时返回 200 空状态，浏览器不再产生伪失败，未知或非法分析标识仍按原契约拒绝。前端 106 个测试文件、544 项测试、TypeScript、ESLint、生产构建、后端回放目录聚焦测试及 Impeccable 扫描通过；DDT 在 1440×900、760×820 完成真实浏览器走查，最终控制台 0 警告、0 错误。证据为 `output/playwright/ui22-extension-final-1440.png`、`ui22-replay-final-1440.png` 及同目录程序、资源、变量、Player 截图。UI-22 晚于 G16，下一发布候选必须重新构建并锁定精确哈希。
- Android 直接执行 APK 组装而未提供共享 Player Web 产物时会按 `AND-WEB-001` 失败关闭；统一构建先执行 `npm run build:player`，再把 `release/player-web` 作为 `easycode.player.webAssets` 输入，证明 APK 没有退回空壳 WebView。
- 独立 Player OpenAPI 继续由精确闭集锁定；终端录制会话的列表、查看、帧读取、导出与删除已经显式纳入发布边界，没有引入 IDE 作者接口。

## 尚未通过或已明确延期的事项

1. **24 小时冻结 Player 长稳**：`scripts/soak_vnext_player.py` 已具备每 30 秒采样完整进程树与隔离数据目录、每 5 分钟执行真实任务的最终规则。首轮在约 4 小时 15 分时因专用 Capture Harness 窗口被外部最小化而按产品契约失败，现场保留于 `output/g8-performance/soak-24h-final/player-soak-24h.json`，不能冒充产品泄漏或合格长稳。Harness 现只对显式命名的测试夹具在每次任务前恢复可捕获状态，不改变产品 Runtime 的窗口语义；修正后的约 2.5 分钟样本保留于 `output/g8-performance/soak-24h-final-v2/player-soak-24h.json`。G16 未完成的 24 小时目录已按用户要求清理，完成的预检仍保留；UI-21 已形成更新的前端源码基线，UI 冻结后必须重新组装并锁定最终候选，不能把 G16 直接命名为包含当前 UI 的正式发布包。
   - `scripts/analyze_vnext_soak.py` 以完整时长、失败、任务覆盖、进程数、数据目录增长以及预热后的 RSS/句柄双趋势自动判定；未满 24 小时明确为 `incomplete`。
   - 可执行文件和发布包 SHA-256 被写入报告并与最终候选再次比对，避免仅靠目录名推断版本。
   - 修复 Worker 句柄后先完成约 31 分钟预检，7 次任务全部完成，末尾稳定样本 RSS 约 `101 MiB`、句柄 `399`；报告保留在 `output/g8-performance/soak-preflight-handle-fixed`。由于该版尚未持续采样数据目录，它只作为缺陷修复预检，不计作正式 24 小时结果。
2. **Android 真机完整矩阵**：Android 13 / API 33 物理手机已安装 ARM 候选 APK，并完成 Player、MediaProjection、Accessibility、SAF、控件、Runtime、录制、权限撤销/恢复、同时缺失多项权限的逐项授权、严格离线、旋转和强制停止后新运行。同一候选包又在 API 34 模拟器完成 Runtime；返回 Player 使用标准 Android `PendingIntent`，逐项授权流程进入标准 AOSP 设置入口，代码无厂商专属分支。两台设备信息当前都报告 Xiaomi；非小米实体设备按 ADR-097 延期到客户现场/新增设备验证，不能把双 API 证据写成多厂商通过。当前小米真机可完成的断线独立与短时性能测试仍单独收口。
3. **物理 LAN 双机矩阵（延期）**：加密协议、权限、离线补发和幂等派发已在真实 socket/双进程及模拟器→物理 Android 中通过；第二台独立物理宿主、防火墙、睡眠/唤醒与网络分区按 ADR-097 延期，不阻塞 UI 阶段，也不标记通过。
4. **官方托管生产服务（延期）**：自托管静态 Feed 契约与真实本地 HTTPS Harness 已有证据；官方托管账号、对象存储/CDN、配额和审计服务尚不存在，按 ADR-097 延期到真实上线建设。入口保持明确不可用，不能以“理论可用”替代联调。
5. **生产签名与干净客户机矩阵**：当前 Windows/Android 产物是开发签名候选；生产 Authenticode、正式 Android keystore，以及无开发工具的独立客户机/真机矩阵仍需发布环境。

## 2026-09-04 Android 候选增量证据

- UI 冻结后的 G16 `productionDebug` APK 位于 `output/g16-session-gate-android/EasyCodePlayer-productionDebug.apk`，SHA-256 为 `49ec3e7414f2d3bd6d5636fc783ae70f5911505c804c73e03cbd5057099b5fa0`；成品检查确认调试签名有效、无源码并包含 `arm64-v8a + armeabi-v7a` 原生闭包。相同 APK 已在 `emulator-5556`（API 34）和 `e7dfd7d1`（API 33 物理手机）安装并以前台 `PlayerActivity` 启动，未发现新增 AndroidRuntime 崩溃；实际屏幕证据为 `output/g16-session-gate-android/screens/emulator.png` 与 `phone.png`。本轮只复核共享 UI、安装和启动，既有能力强断言继续冻结；仍不替代断线运行、非小米设备或生产签名门。
- 从 API 33 物理手机的 PackageManager 安装路径回读 `base.apk` 后，SHA-256 仍为 `49ec3e7414f2d3bd6d5636fc783ae70f5911505c804c73e03cbd5057099b5fa0`，与输入候选逐字节一致；回读副本保存在 `output/g16-session-gate-android/installed-base-g16.apk`。重新安装后首次业务运行按 Android 契约停在 MediaProjection 系统授权，确认后运行 `run_a20a2a02372749c2a0076b6ff3491d22` 到达 sequence 8 `completed`。36 秒 Harness 短测完成 1 次新运行和 4 个设备样本、无失败；随后以相同 APK 启动 `output/g16-session-gate-android/android-local-preflight-1h.json` 的 1 小时真机前置采样，当前仅标记 `running`，不能提前写成性能通过。
- 首轮组合 Harness 把调试控件页写成 `com.easycode.player.candidate`，而实际 `productionDebug` application id 是 `com.easycode.player.debug`。模拟器与真机都以 `application.launch_failed` 明确失败；没有把失败包计入证据。生成器改为使用实际构建变体 application id 后重新生成并安装。
- 随后的审计发现旧 Harness 在 `消息.等待接收`超时返回空时仍无条件输出成功日志，监听窗口也会在未接手消息时自然结束。Harness 已加入运行时断言：同步消息必须非空；监听处理函数必须设置项目内断言标记，否则使用稳定错误 ID 主动失败。聚焦测试为 `10 passed`。
- 最终增量证据位于 `output/release-candidate-android-v4-evidence/android-emulator-to-phone-lan.json`。发送 APK SHA-256 为 `a5802be055c36f83965c9c58c6c3938713dd60229f1964ce9734f1351aa64ac6`，接收 APK SHA-256 为 `a0d8730554a17ee1ced8329ba48f700462ca8bfcadcc458eae8fbf626923b8b8`。两条消息在发送端与接收端均为 `read`，接收运行日志包含监听接手、处理函数执行、处理完成、主流程恢复和最终完成。
- 该证据是雷电模拟器向一台物理 Android 手机的真实局域网投递，不等于两台物理设备矩阵；手机无法直接访问模拟器 NAT 内部监听地址，因此反向方向继续明确未验证。
- G12 增加了独立的 Android 基础能力强断言项目。`output/g12-android-basics/android-basics-real-device-evidence.json` 锁定 APK、项目包、运行 ID、Runtime 状态与保存帧哈希；API 33 物理手机运行到 sequence 8 `completed`，项目只会在画面文件确实存在、同一 MediaProjection 帧的颜色可读取且可重新找到、剪贴板写入后读取完全一致时输出“Android 画面保存、颜色与剪贴板已验证”。保存帧为 1080×2340 PNG。该轮仍连接数据线且使用调试签名，因此只关闭这些能力的真机功能证据，不替代断线独立或生产签名门。

## 2026-09-04 候选家族与 Windows 窗口增量

- `scripts/freeze_release_candidate_family.py` 会复验 Windows 候选清单、安装介质、每个 Android 角色 APK 的哈希/长度/签名/源码隔离报告，并锁定真实运行报告。当前确定性锁已推进到 `output/g12-release-candidate-family/candidate-family.json`，家族 SHA-256 为 `e0f7af1db4dba12c69f5223a71b8f66a3409efbce899f37bd32b108ca87c695f`；它在不覆盖历史 G11 锁的前提下加入 G12 真机画面/颜色/剪贴板候选和证据，并继续锁定 G9 消息双角色、G11 Windows 清单、文件/HTTP、网络、混合目标、安装与应用生命周期证据。该锁只证明产物身份，不提升尚未满足的发布门。
- 真实 WinForms Harness 已通过窗口状态读取、移动到 `80,80`、调整为 `520×260`、最大化/最小化/还原及关闭；同一窗口的 UIA 状态读取、聚焦、设置值、输入和按钮点击也验证了可见效果。当前 Codex 终端进程在 Windows 前台锁下无法把 Harness 强制切到前台，Runtime 在三种回退后返回 `window.operation_failed`，因此 `output/functional-gap-evidence/windows-control-window-evidence.json` 明确记录为 `partial`，不会用其余操作成功掩盖该项。

上述项目不得被模拟器、替身或“测试全绿”改写为通过。除这些外部环境事项外，代码发现的缺陷继续在当前阶段修复并重跑相应完整基线。
