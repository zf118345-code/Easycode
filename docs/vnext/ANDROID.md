# Android 本机 Player

状态：`Approved`（属于首个正式版本完成门；Player 逐字段捕获/文件动作、MediaProjection/SAF/Accessibility 权限边界与失败恢复已冻结；真机矩阵的数值预算由 Harness 冻结）

最近修订：2026-09-03

当前实现证据（2026-09-03）按证据等级区分：

- 自动与真实模拟器验证：项目能力闭包分别生成 `minSdk=21` 与 `minSdk=24` 的签名、无源码 productionDebug APK；Build Tools 37 的 `minSdkVersion` 输出已纳入成品检查器。API 24 候选在 `emulator-5556`（API 34）完成安装、冷启动、签名包加载与主程序执行，界面状态由“就绪”进入“已完成”，未出现 AndroidRuntime 崩溃。该证据不替代 API 21/24 对应低版本镜像，也不替代断线实体手机正式放行。
- 发布与设备双预检现在同时校验 bundle 版本/身份、签名 key、`easycode.lock` 哈希与扩展数量、扩展 `minimum_android_api`、ECIR/报告依据和 Player 字段动作闭包；API 21 扩展保持基线且不生成冗余提级来源。
- **Android Kotlin/JVM 扩展补充证据（2026-09-03）**：真实 JDK JAR 已经产品导入/校验/密封/签名/锁定后静态进入 `minSdk=21` APK。API 34 x86_64 模拟器和 API 33 arm64-v8a 真机均完成“成功 → 扩展抛错 → 100ms 超时并杀死独立 Worker → 重建 Worker 后恢复成功”的完整流程；主 Player 在扩展失败与超时后仍存活。最新候选还逐层复核扩展声明权限、实际入口函数权限、Android API 下限、APK 注册表和成品 Manifest 权限，篡改在执行前失败。证据位于 `output/g6-android-extension-harness/run-20260903-3/*-device-evidence.json`。这证明当前纯 JVM/API 21 闭包在高版本设备可正常运行，不替代 API 21 真实系统镜像的低版本兼容验收。
- **Android 最小 Manifest 权限补充证据（2026-09-03）**：纯计算扩展候选在构建前发现离线 ML Kit 的 AAR 仍追加网络权限，发布器现使用生成 Manifest 显式移除闭包外权限，并在成品 APK 反查阶段要求精确集合。`extension-*-debug-minimal.apk` 已同时生成 x86_64 与 armv7/arm64 候选，均只保留基础离线 Runtime 权限；API 34 模拟器和 API 33 真机仍分别通过成功、扩展失败、超时杀 Worker 与恢复运行。另一个真实 Player 捕获候选只恢复 MediaProjection 与悬浮窗权限，仍不携带网络权限。证据位于 `output/g6-android-extension-harness/run-20260903-3/*minimal*` 和 `output/g6-android-permission-closure-harness/capture-emulator-debug.apk.evidence.json`。

- **Android 控件、输入与视觉补充证据（2026-09-03）**：同一签名模拟器 APK 已用 Accessibility 实际完成控件输入与回读、焦点文本输入、控件点击、从 `control_ref.区域` 经 `区域.中心` 计算得到的坐标点击、横向拖拽、纵向滚动，以及 Android 返回键；同一运行还从 MediaProjection 新帧查找包内确定性图片标记并等待出现，实际相似度为 `1.0`。持久化结构日志完整记录上述结果，最终状态为 `completed`、`sequence=11`。
- **Android 文件与离线补充证据（2026-09-03）**：独立签名模拟器 APK 已在项目私有数据目录实际完成文本原子写入、追加、替换、读取，JSON 写入/读取以及目录列出；真实运行同时发现并修复了 Android `目录.列出` 将文件错误投影为目录引用、继承过宽能力的问题。修复后文件条目与 Windows 契约一致返回 `entry_type=file`、`file_ref`，且能力收窄为 `read/write`。在测试实例没有默认网络路由时，关闭并重新启动 APK 后同一文件闭环仍以 `completed`、`sequence=5` 结束，证明本地核心运行不依赖 IDE、开发后端或公网。
- **Android 物理真机无网补充证据（2026-09-03）**：物理手机进入系统飞行模式后，`dumpsys connectivity` 明确报告 `Active default network: none`；密封 APK 仍在 profile revision 15 上完成真实本机 Runtime，终态为 `completed`、`sequence=17`、无错误。验证后飞行模式、移动数据和 Wi-Fi 均已恢复。该证据证明当前本地核心闭包没有运行期公网前置；物理拔除数据线和更长时间离线仍需单独放行。
- **Android 本机录制补充证据（2026-09-03）**：共享 Player 已在 `android_local` 目标显示与 Windows/ADB 相同的运行方案录制设置，并将终端用户确认绑定到精确 profile revision。模拟器签名 APK 通过 MediaProjection 实际完成 5 秒 `all_frames` 录制，产生 13 张 720×1280 无损 PNG、目标片段、逐帧 SHA-256、终态和会话级完整性摘要；把产物拉回 Windows 后由同一 `RecordingStorageV6.verify_session` 校验为 `verified_frame_count=13`、零问题。后续 API 33 真机也已生成成功及任务失败两类录制，失败只收束 Recorder、不替代任务终态；真机 ARM 长稳仍在进行。
- **Android 真机失败录制补充证据（2026-09-03）**：将录制重新确认到 profile revision 15 后，在物理真机临时撤销 Accessibility 权限并运行真实 Harness。Runtime 稳定失败为 `control.permission_required`，结构化日志定位 `statement_find_semantic_input`；同次录制 `rec_20260903_152724_249125_03138ffc69` 保存 6 帧，`terminal.json` 为 `status=completed, terminal_reason=task_failed`，Player 明确显示“录制已完成；任务执行失败，录制记录已经完整保存”，没有把业务失败误报为录制异常。验证后 Accessibility 已恢复到原服务。
- **Android 运行记录与本地计划补充证据（2026-09-03）**：共享 Player 已真实浏览 Android 私有目录中的会话与 13 张原始帧，用 EasyCode 内部确认删除，并由用户显式调用系统文档选择器导出“画面与报告”ZIP；解包检查确认不含项目源码、ECIR、资源和运行方案值。当前 APK 的单次、每日、固定间隔计划已接入 `AlarmManager`、私有计划历史和普通 Runtime；应用退到桌面后，系统先在缺少 MediaProjection 时准确记录阻塞，授权后又连续两次创建独立 occurrence/dispatch/run 并正常完成。真机的权限撤销/恢复和强制停止后新运行已另行补证；计划在实体真机休眠期间的触发与实际延迟仍未验证。
- **IDE Android 交付入口（2026-09-03）**：发布检查界面现在只在项目声明 Android 本机交付时展示自动推导的最低 Android 版本及抬高版本的语句来源，并提供“生成 Android 测试 APK”。后端重新发布当前工作区、从作者签名派生项目固定信任根、调用受控 Gradle 变体、验证成品签名/源码隔离/minSdk 后写入项目 `dist/android`；Renderer 不接触作者密钥，也不能传入任意 Bundle、信任根或输出路径。正式 release 仍受本文件真机完成门阻止，测试入口不能冒充正式交付。
- **Android 消息与 LAN 远程调度补充证据（2026-09-03）**：签名模拟器 APK 已与 Windows 实例真实配对，并完成 Windows→Android、Android→Windows 消息传输以及脚本 `control.listen` 在主流程等待期间串行插入处理函数、随后恢复主流程。Windows 又通过独立 `dispatch.start` 特权协议启动普通 Android Runtime；两个不同网络请求重试同一逻辑派发时始终取得同一个 `run_id`，设备内只保存一条终态记录。改变同一派发身份的内容会稳定拒绝；在共享 Player 实际撤销远程启动权限后，Windows 立即停止派发，恢复授权后同步生效。上述仍是模拟器与同机端口转发证据，不替代物理局域网、公网阻断和真机生命周期矩阵。
- **已实现的候选**：仓库已有真实 Gradle/Android 工程和 Kotlin Runtime。Android APK 现在嵌入与 Windows Player 同一份编译后 Vue/Control 渲染层，Kotlin 只承接 Host Adapter、Runtime、MediaProjection、AccessibilityService、SAF、前台服务、原生采集和随 APK 密封的中英文 OCR。第二套 Kotlin 表单渲染器已删除；WebView 只加载 APK 内离线资源，Host 桥使用版本化信封和 API 白名单。签名 `.ecplayer`、registry v6 lock、项目变量/局部值、控制流、项目函数、结构化日志、暂停/继续/停止和 `profile_id + profile_revision + control_id` 原子字段回填均保留同一契约。
- **自动验证通过**：Android JVM/Gradle 聚焦测试、Python delivery/registry/签名聚焦测试和 Android Player Vitest 已执行；`productionDebug` 与 `emulatorDebug` 都嵌入无源码/无 source map 的离线 Player 资源。Host 桥白名单、结构化错误、单一共享表单边界和 SAF 可读名称投影均有回归测试。这些产物仍是 `debug_candidate`，不是正式发布 APK。
- **模拟器交互验证通过**：SDK 34、720×1280 模拟器中，APK 已真实完成竖屏/横屏共享 Player、点、区域、图片、61 点手势路径、MediaProjection 拒绝、SAF 读取文件、创建保存位置、目录授权、取消/拒绝保留旧值、revision 单调更新和应用内单一反馈。最新悬浮采集候选又验证了：Player 发起后在目标应用显示可拖动开始/取消组；开始时悬浮层不进入新帧；竖屏授权后可切到横屏目标并按新尺寸冻结；点、区域和图片在原画面内选择并原子回填；取消返回原 Control 且保持旧值。路径确认返回后保持原字段滚动位置，终态结果只由共享 Player 的 EasyCode 反馈条承接，不再叠加 Android Toast。独立 APK 又从 MediaProjection 新帧真实执行 bundled 中英文 OCR、`文字.匹配` 与 `文字.等待出现`，把识别全文写入结构化日志并完成任务；修复后终态快照的 sequence 与最终“任务运行完成”事件一致。另一个源码隔离的签名 APK 还已真实运行 `应用.启动 → 控件.查找 → 控件.输入文本 → 控件.读取文本 → 控件.点击 → 控件.读取文本`；Accessibility 日志精确记录“EasyCode Android 控件已验证”和“已确认：EasyCode Android 控件已验证”，最终状态为 completed、sequence 4。Windows Player 对当前 Windows 窗口、同一模拟器和连接手机也分别真实取得 640×420、720×1280 和 590×1280 帧。这是模拟器/ADB 证据，不等于真机 Android 本机放行。
- **Android 物理真机关键切片已通过**：ARM `productionDebug` APK 已安装并在 Android 13 物理手机启动；已真实完成 MediaProjection 原分辨率帧、点/区域/图片/路径、Accessibility 控件及父级链、SAF 读取/保存/目录授权、本机 Runtime 与录制。采集确认后通过标准 Android `PendingIntent` 返回 Player，revision 只增加一次，软键盘不重新弹出，原字段居中并短暂高亮。相同候选包又在第二个 Android 模拟器环境完成同一返回链路；实现只按 API 级别、权限和能力分支，不按小米或其他厂商分支。
- **Android 真机权限、离线与生命周期补充证据（2026-09-03）**：物理真机已验证 Accessibility 撤销产生 `control.permission_required` 且失败录制完整保存，重新授权后从新运行入口成功完成；飞行模式下活动默认网络为 `none` 时本地 Runtime 仍完成；横屏切换保持共享 Player、方案 revision 和字段数据。强制停止后 Player 不恢复旧执行栈；同时缺少 MediaProjection 与 Accessibility 时曾暴露只处理首项权限的缺口，现已改为逐项授权、每次返回重新检查、全部满足后才创建运行。相同流程在 Android 13 真机进入厂商系统设置页、在 Android 模拟器进入 AOSP 设置页，应用均只发出标准 `Settings.ACTION_ACCESSIBILITY_SETTINGS`，不识别设置页面结构。最新重新密封候选包 `app-production-debug-g6-android-generic-v2.apk`（SHA-256 `c44e811f2cae1295c0ab83229acc5027d681da3af200c609c27c1e266f8ff6cb`）已在真机完成 `run_0f88f792bab1461fa846977efc6dd76d`，终态为 `completed`。
- **真机完整放行仍在进行**：相同最新候选包已分别在 API 33 真机和 API 34 模拟器完成 Runtime，因此多 API 基础交叉验证已开始；不过当前两台设备信息都报告 Xiaomi，不能冒充多厂商证据。上述证据消除了安装、关键权限恢复、严格离线和基本方向/强制停止阻塞，但还需覆盖计划休眠唤醒、更长时间 ARM 性能及非小米实体设备；单台真机与单台模拟器不代表 Android 通用矩阵全部放行。
- **正式放行仍阻塞**：依照 ADR-053，Compiler/Publisher 的 `verified_platforms` 与正式发布报告仍不含 `android_local`。当前 OCR 候选已有真实 native 闭包：production debug 精确包含 `arm64-v8a + armeabi-v7a`，emulator debug 只含 `x86_64`；这仍不能替代 release 产物、断线真机和低端机性能验证。release 还要求项目外部 keystore/CI secret、完整离线闭包和真机 Harness，任何 debug APK 都不是用户发布绕过入口。

本文只冻结 Android 本机 Player 的跨模块交付边界。ProgramDocument、ECIR、函数、目标、Player、文件、扩展与 Harness 的详细契约仍以对应细分规范为准。

## 1. 产品结果

首个正式版本必须同时交付 Windows IDE、Windows/ADB Player 和 Android 本机 Player。Android 发布物是可安装的签名 APK；安装完成后，用户断开数据线并关闭 Windows IDE 与后端，仍能在手机上选择运行方案、填写表单、执行、暂停、继续、停止和查看诊断。

允许研发阶段先完成 Windows/ADB 垂直切片，但 Android 真机闭环未通过前，首个正式版本不得放行。未完成的 Android 入口保持不可见或明确禁用，不能用静态页面、模拟数据、桌面模拟器或普通 ADB 目标测试宣称已经支持。

## 2. 两种 Android 路径必须区分

- **ADB 操作目标**：ECIR 由 Windows Runtime 执行，Windows 通过 ADB 获取设备画面并发送输入；可以操作模拟器或连接设备。
- **Android 本机宿主**：ECIR 由手机内的 Android Runtime 执行，使用 Android 权限、捕获、输入、文件和生命周期；断开电脑后继续运行。

Windows IDE 可以借助 USB/ADB 安装、更新和连接本机测试 APK，但这只是开发通道，不改变实际执行宿主。日志、状态和测试证据必须显示实际宿主，避免把两种路径混为一谈。

## 3. 稳定需求

- `[REQ-AND-001]` 首个正式版本必须包含可脱离电脑独立运行的签名 Android APK；Android 垂直切片未通过时整个正式版本不得放行。
- `[REQ-AND-002]` Android Runtime 执行与 Windows/ADB 相同版本的 ECIR、函数契约、纯值语义、项目变量、Player Schema、超时、取消和结构化日志；平台差异只进入驱动、宿主和明确的平台能力。
- `[REQ-AND-003]` Windows IDE 必须能向用户授权的 USB 设备部署或更新测试 APK、连接调试会话并读取结构化日志，同时明确区别普通 ADB 目标测试。
- `[REQ-AND-004]` Android Runtime 必须从 MediaProjection 真实帧执行图片和 OCR，并在方向、尺寸、前后台或权限变化时停止消费旧空间缓存。
- `[REQ-AND-005]` Android Runtime 必须通过批准的本机输入通道完成点击、滑动、拖拽、长按和文本输入；权限不足、目标拒绝或动作失败时返回真实错误，不伪报成功。
- `[REQ-AND-006]` MediaProjection、无障碍、通知/前台服务和文件授权必须按需请求，并覆盖首次同意、拒绝、永久拒绝、被系统撤销、重启失效和恢复；一次运行同时缺少多项权限时，Player 必须逐项完成授权并在每次系统返回后重新检查，全部满足前不得创建 Runtime 运行。缺少权限时只阻止受影响能力并说明恢复路径，不能清空字段旧值或草稿。
- `[REQ-AND-007]` Android Capture Session 必须使用与 IDE 相同的点、区域、图片、控件和手势路径结果契约；Player 使用专属 `PlayerControlDestination` 验证产品、发布、运行方案、`control_id`、`action_id`、目标、请求和 revision，过期结果不能回填 ProgramDocument、ECIR 或其他字段。
- `[REQ-AND-008]` Android Player 必须从同一 Player Schema 和 Control Registry 渲染获批字段，并在小屏、横竖屏、字体放大、系统安全区和系统返回行为下保留草稿与真实运行状态。
- `[REQ-AND-009]` Android 文件函数必须支持应用私有目录和用户通过 Storage Access Framework 授权的强类型外部文件/目录引用；读取文件、保存文件和选择目录具有不同访问模式，授权撤销、内容引用失效、空间不足和读写失败必须保留结构化原因与重选入口。
- `[REQ-AND-010]` Android 发布器必须只携带项目实际引用的资源和 `easycode.lock` 选择的 Android 本机 `ecx-runtime-1` 密封扩展变体；Python-only、源码-only、Windows-only、ABI/签名不兼容、未声明权限或缺失依赖闭包时在生成 APK 前阻止。
- `[REQ-AND-011]` APK 不得包含 ProgramDocument、结构化编辑元数据、扩展源码/测试、Windows Python、IDE 组件、开发机绝对路径、签名密钥或授权令牌。
- `[REQ-AND-012]` Android Player 必须作为普通项目消息实例与 Windows 或其他 Android 实例收发结构化消息，并保持明确收件人、独立已读、过期、监听串行和离线语义。
- `[REQ-AND-013]` 主动暂停只在同一 Android 进程内继续；停止、取消、进程退出或崩溃后新运行使用新运行 ID 从入口开始，诊断保留中断位置但不自动续接旧界面流程。
- `[REQ-AND-014]` Android 本机实例只操作当前手机，不切换到 Windows 或外部 ADB 目标；真正并行继续使用多个隔离 Player 实例和消息协作。
- `[REQ-AND-015]` Android 正式放行必须使用真实设备矩阵验证部署、权限、Capture、视觉、输入、文件、消息、Player、扩展、打包、生命周期、性能与长稳；替身、模拟器和 ADB 目标证据单独标记，不能替代真机。
- `[REQ-AND-016]` 未声明公网能力的 Android APK 在飞行模式、断开数据线并关闭 IDE/后端后仍完成本地核心闭环；视觉、OCR、输入、文件和 Player UI 不依赖 Google Play 服务、EasyCode 云或运行期下载。
- `[REQ-AND-017]` Android 项目内容更新只写入应用私有的签名 A/B 内容槽；Runtime、Manifest、权限、ABI 或原生扩展变化必须生成保持应用标识和兼容签名身份的新 APK，并交给系统安装流程。
- `[REQ-AND-018]` APK 检查或下载可以自动进行，但普通设备需要用户确认安装时必须使用真实系统流程；取消、拒绝、签名/版本/ABI 不兼容、空间不足或安装失败都保留旧 APK、运行方案和用户数据。
- `[REQ-AND-019]` Android 本机首版必须完成全部帧、变化帧和诊断录制、本机时间线浏览、官方图像/OCR 离线分析、历史帧 Capture、两种显式导出与清理；应用进入后台、MediaProjection 失效、空间不足或进程终止时保留已提交帧和真实终态。
- `[REQ-AND-020]` Android `目录.*` 必须在应用私有目录与支持相应语义的 SAF 文档树完成存在、创建、列出、复制、移动、删除空目录和受控递归删除；Provider 不能证明后代范围或删除语义时在执行前拒绝。
- `[REQ-AND-021]` Android 基础 Runtime 以 API 21 为最低基线，具体项目/APK 的 `minSdk` 由编译器与发布器取全部已用函数、语言机制、Player 终端动作和扩展能力下限的最大值，并在 ECIR、发布报告、Gradle 参数和成品 Manifest 中保持一致且可追溯到稳定语句/字段/扩展；作者不能手工降低。每个 Player 终端动作也必须在同一权威契约中声明最低 API，不能因它不属于 ProgramDocument 而漏算。`compileSdk/targetSdk` 固定为 37。正式 APK 的真实原生依赖闭包只包含 `arm64-v8a + armeabi-v7a`；`x86_64` 只用于独立开发/模拟器测试产物，不扩大正式通用包。纯 JVM 候选没有 native 条目时属于架构中立产物，flavor 的 `abiFilters` 只能作为配置证据，不能冒充 ABI 已验收，也不得为制造标签加入假 JNI。release 必须从项目外部 keystore 或 CI secret 读取签名身份；缺失时构建明确失败，不回退到 debug 签名，也不在仓库保存正式私钥或默认口令。
- `[REQ-AND-024]` Android 本机的完整自动化能力以 API 24（Android 7.0）起验收；API 21–23 不伪装为完整版，而是根据项目实际能力闭包生成的受限兼容版。例如媒体投屏获得画面、图像匹配或 OCR 只有在该设备与项目的捕获闭环实测通过时才对外声明可用；通用 Accessibility 手势注入及依赖它的点击/滑动/拖拽自然抬高到 API 24。构建界面必须同时告知“这个 APK 可安装的最低版本”与“使用了哪些会抬高版本的能力”。API 21 以下不进入首个正式版本范围。
- `[REQ-AND-025]` APK Manifest 权限必须由签名发布闭包确定性生成：基础离线 Runtime 只保留其自身必需声明；网络、局域网、MediaProjection、悬浮窗、在线更新和扩展系统权限按实际能力加入。依赖 AAR 追加的闭包外权限必须在合并阶段显式移除；构建后从 APK 反查的权限集合除包内自动保护权限外必须与闭包精确一致。Manifest 声明仍不替代危险权限的按需系统授权。
- `[REQ-AND-022]` Android 本机行为只能按 API 级别、公开系统能力、当前权限和运行时探测分层；厂商、品牌与型号只能用于设备展示和诊断，不能选择业务路径。标准系统 Intent 在启动前必须验证可处理，授权返回后以真实服务连接状态为准；不提供可选诊断字段的设备仍可运行核心能力。不得把小米测试机行为、MIUI 私有入口或任何 OEM 页面坐标写入产品实现。
- `[REQ-AND-023]` Android Kotlin/JVM 扩展只允许在 APK 构建期把通过发布者签名、lock、密封描述、JAR 哈希和契约验证的模块静态链接，并生成与内容包精确对应的只读注册表；运行时不得下载或动态加载 DEX/JAR。扩展函数在独立 Worker 进程通过版本化 JSON ABI 执行，异常、超时、取消、进程退出、非法响应和返回类型错误必须收束为可定位诊断，不能终止 Player 主进程。

## 4. 发布闭环

```text
ProgramDocument + 项目配置 + 资源 + 扩展锁
                    ↓ Compiler Service
           签名 ECIR + 权限/依赖报告
                    ↓ Android Publisher
 Android Runtime + Player UI + 资源/扩展闭包
                    ↓ 签名并安装 APK
      断开电脑后的真实设备独立运行与证据
```

发布检查在生成 APK 前列出不支持函数、目标、Control、资源、权限、扩展和 ABI，并定位到稳定函数/语句/字段/资源 ID。Android 不支持的 Windows UIA 等调用不能被静默跳过，也不能等安装后才失败。

## 5. 交互与失败底线

- Android 运行端加载与 Windows Player 相同的编译后 Vue/Control 渲染层，以单列触控布局投影，不把桌面布局按比例压缩到手机；Kotlin 只承接 Host Adapter、Runtime、权限和原生捕获/选择器。
- 权限属于运行前检查与系统授权流程，不混成普通脚本参数；返回应用后恢复原操作上下文。
- 系统终止捕获、撤销无障碍、切换方向或进入后台时，Runtime 停止受影响动作并记录原因；不能继续使用旧帧、旧坐标或假成功状态。
- 终端捕获动作只在开发者明确发布且 Android APK 结构上支持时出现；永久不支持的动作不显示，因权限或宿主状态暂时不可用的动作禁用并解释原因，不把复杂值降级为文本。
- 日志与诊断不得包含签名秘密、授权令牌或未经批准的完整用户文件。

### 5.1 Player 字段动作与 Capture Session

作者按字段、动作和平台开放终端配置能力，默认全部关闭。Android Player 实际动作必须同时满足作者发布、字段类型、APK 能力/权限闭包、当前本机宿主/目标能力和当前权限状态。未开放或 APK 结构上不支持的动作不显示；权限被撤销、服务未开启等可以恢复的动作保留位置并说明恢复方法。

Android Player 字段动作固定为：坐标字段拾取坐标、区域字段框选区域、图片字段从当前画面截取或从设备选择图片、手势路径字段录制手势路径、文件字段选择读取文件或保存位置、目录字段选择文件夹。开发者逐字段开放“捕获控件”后，Android 本机通过 Accessibility 从当前活动窗口生成与 Windows/ADB 共用的稳定 `control_selector`；权限尚未授予时原位引导授权，节点缺失、过期、SurfaceView/自绘界面不暴露语义时返回可诊断的不可用结果并保留旧值。不得用坐标、文字或屏幕根节点假装控件选择器。

Android 点、区域、截图和路径 Capture Session 使用悬浮冻结流程：说明当前字段及所需访问 → 发起必要系统授权 → Player 退到后台并显示可拖动贴边的 EasyCode 悬浮按钮 → 用户准备目标画面 → 开始采集时移除全部 EasyCode 悬浮层 → 等待并取得移除之后的原始分辨率新帧 → 原地全屏冻结编辑 → 确认、取消或微调。冻结层不启动带页面切换动画的第二套表单，也不占用固定标题栏/底栏；进入冻结态的短暂淡绿色光效、选区外遮罩、选框、准星、路径和按钮只属于显示层，不进入截图像素。点、区域和路径按原始帧空间回填；图片只从该原始帧按确认选区裁剪。

用户在悬浮准备阶段切换目标应用或横竖屏时，宿主在点击开始后按当前真实显示尺寸刷新 MediaProjection 帧缓冲，再通过后隐藏帧门取得新帧，不要求返回 Player 或重新授权。冻结编辑出现后坐标空间才锁定；此时方向或显示尺寸变化必须取消候选、保留旧值并回到原字段，不允许缩放旧帧后继续提交。

文件/目录仍由 SAF 系统选择器完成目视预览与确认，返回 Player 后不再重复确认。在任一候选获得后，宿主均必须二次校验 `PlayerControlDestination`；成功后只对当前运行方案/私有图片覆盖做一次原子提交。系统返回、用户取消、拒绝、初始化/提交失败、目标/方向/尺寸变化或 release/profile/control/revision 改变时，宿主必须返回共享 Player 的原 Control、保留旧值并通过同一反馈组件说明结果；不得使用 Android Toast、通知横幅或通知动作形成第二个业务反馈面。应用被系统终止时不回填空值、旧坐标或其他字段，重新启动只恢复已原子提交的权威方案。

一个 Android Player 实例一次只能存在一个字段 Capture Session。运行、暂停和任务排队期间不能修改运行方案或进入字段捕获；第二个请求聚焦当前会话或明确拒绝。权限恢复、系统选择器返回和重新进入应用后，应回到原字段并恢复焦点、滚动及未提交草稿；无法恢复活动会话时明确结束该次采集，但仍保留字段原值。

### 5.2 MediaProjection、无障碍与文件授权

MediaProjection 只在用户主动发起屏幕采集或运行期真实需要画面时请求。对要求每个投影会话重新取得同意的平台版本，每次新建 Capture Session 都使用新的系统授权结果，不能缓存并复用旧 token。宿主监听系统停止回调；用户从系统状态入口停止、设备锁屏、其他投影接管或进程终止后立即释放帧和 Surface，废弃旧坐标空间并更新字段动作状态。

悬浮控制使用发布权限闭包中声明的 Android 应用悬浮能力，并只在终端用户主动发起字段 Capture Session 后显示；未发布 Android 捕获动作的 APK 不携带该入口。系统悬浮授权缺失时先在共享 Player 就近解释，再由用户进入系统授权页，拒绝后保持旧值且不降级为通知栏倒计时。MediaProjection 前台服务通知使用系统允许的最低非打扰重要级，只承接操作系统生命周期要求，不提供开始、取消、进入选择等业务动作。捕获按钮隐藏后必须等待至少一个带有后隐藏时间戳的新帧，防止 EasyCode 图标、通知横幅或合成残影进入截图。

权限解释只说明当前动作的用途和范围，不用一个总开关一次索取全部权限。单次拒绝保留原值并允许用户重试；永久拒绝或系统撤销不循环弹框，提供前往设置并在返回后重新检查。权限恢复只恢复受影响能力，不重建运行任务或更换运行方案。

Android 外部文件使用 Storage Access Framework：读取文件、创建/选择保存文件和选择目录分别走相应系统选择器，并只保存宿主返回的文档 URI、显示元数据和实际读写授权。目录引用只能访问用户选定的目录树；持久授权在文档移动、删除、提供者失效或用户撤销后仍可能失效，Player 必须保留旧引用、标记不可用并提供重选。图片字段从设备选择的图片经校验后复制到 Player 私有覆盖目录，不长期依赖相册 URI；复制或空间不足失败保持原图。

Android 表单中的坐标、区域、图片、路径、文件和目录必须显示可读的类型化摘要，不显示禁用 JSON 文本框或伪路径。文件选择应把作者的扩展名约束投影为 MIME 过滤；Provider 不支持时可放宽为所有文件，但不能放宽最终引用的类型、权限和字段绑定校验。

递归删除要求 Provider 能逐项枚举并证明每个子项仍在用户确认的 `authorization_root_id` 文档树内，同时支持所需删除语义。普通 SAF 目录授权不自动包含 EasyCode 的递归删除危险能力；派生引用只能缩小范围，终端确认、方案 revision、函数契约或授权根任一变化后都必须重新确认。Provider 不透明跳转、根位置、边界不明或部分能力缺失时，Android 宿主在删除首项之前拒绝。

Android Recorder 从当前 MediaProjection 会话旁路订阅帧并按方向、尺寸与投影会话变化切分片段。录制默认关闭，权限只在用户明确启用后请求；前台服务、空间、背压、方向变化和应用生命周期必须产生可诊断状态。录制与历史分析位于应用私有数据目录，导出使用 Android 系统分享/文档流程；默认导出不含分析快照，高级可重现导出显示项目逻辑、资源、模型与参数范围，平台不能自动上传。

Accessibility 只在当前 APK 能力闭包和用户授权允许时启用。服务关闭或被系统撤销时停止输入与控件读取，清理节点缓存；重新开启后必须重新取得当前窗口树，不能继续消费权限撤销前保存的节点。字段动作和运行期函数分别按自己的声明进入权限报告，开放一个手动捕获按钮不能隐式授予脚本任意后台读取。

## 6. 验收映射

Android 需求由 [`TESTING.md`](TESTING.md) 的 `AC-AND-*` 和根 Harness 的真机证据共同放行，至少覆盖：

- 开发部署与日志：`AC-AND-DEV-*`；
- Capture、视觉、输入和权限：`AC-AND-CAP-001`、`AC-AND-CAP-002`、`AC-AND-CTRL-001`、`AC-AND-VIS-001`、`AC-AND-INP-001`、`AC-AND-PERM-001`；
- 跨平台语义、Player、文件和消息：`AC-AND-PARITY-001`、`AC-AND-PLY-001`、`AC-AND-FILE-001`、`AC-AND-MSG-001`；
- 打包、源码隔离和扩展：`AC-AND-PKG-*`、`AC-AND-EXT-001`；
- 工具链、ABI 与签名边界：`AC-AND-BUILD-001`；
- 生命周期、真机矩阵和性能：`AC-AND-LIFE-001`、`AC-AND-REAL-001`、`AC-AND-PERF-001`。
- 本地优先与零隐式外连：`AC-OFF-AND-001`、`AC-OFF-CONN-001`、`AC-OFF-CLOSURE-001`。
- 在线更新：`AC-UPD-AND-CONTENT-001`、`AC-UPD-AND-APK-001`、`AC-UPD-DISABLED-001`。

## 7. 非目标与待冻结细节

- 首版硬门是可安装签名 APK；AAB 只有在明确需要应用商店分发时另立需求。
- iOS、macOS 和“一个 Android 本机实例切换到 Windows/外部 ADB”不在范围内。
- 不因 Android 首版要求开放第三方目标驱动、远程代码安装或在手机上编辑 ProgramDocument。
- Android 工具链、ABI 和 release 签名密钥边界由 ADR-061 冻结，项目能力推导最低 API 的规则由 ADR-083 取代原固定下限。各系统版本权限引导文案和真实设备/API/分辨率矩阵仍由 Harness 专题冻结，但不得推翻本文件的首版完成门。终端 Capture/文件动作白名单、系统选择器的高层授权粒度和控件捕获条件已由本文件冻结；实现不能重新引入全局开放或全设备控件捕获承诺。
