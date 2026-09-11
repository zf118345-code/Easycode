# EasyCode 正式版固定验收项目

状态：`Active`  
基线：格式 6 / ProgramDocument 1 / ECIR 1

本文件只管理六个真实验收项目，不把单元测试、模拟返回或旧版本分散证据写成最终放行。每次候选必须记录精确 Runtime/Player/APK/项目包哈希、真实运行 ID、运行终态和仍未覆盖的环境。

| ID | 验收项目 | 必须证明 | 当前候选证据 | 状态 |
|---|---|---|---|---|
| ACC-001 | Windows 软件自动化 | 应用/窗口生命周期、UIA 查找与操作、输入模式、失败定位 | `output/g11-windows-lifecycle/windows-application-lifecycle-evidence.json` 已用同一 G11 冻结核心 Runtime 完成真实 WinForms 启动、同进程状态确认、停止、停止后状态与退出结果；`output/g11-windows-player-functional-final/windows-install-upgrade-repair-uninstall-evidence.json` 完成旧版安装、升级、修复和卸载。既有 WinForms/UIA 证据继续冻结。窗口激活仍需从 Player 交互进程以及 UWP/管理员窗口矩阵复核 | Partial |
| ACC-002 | Windows 启动模拟器后切换 ADB | Windows→ADB→Windows 顺序切换、应用启动、坐标空间与逻辑目标恢复 | `output/g11-windows-player-functional-final/windows-adb-windows-ddt-evidence.json`：G11 冻结 Player 的 `execution_5d8a31d4f3a84e20a5d20d1c847233ac` 已用真实控件结果完成 Windows→微信→`emulator-5556` ADB→微信，并恢复原 Windows 目标；既有同一幂等键不重复执行证据继续冻结 | Passed candidate |
| ACC-003 | 跨平台控件 | Windows UIA、ADB UIAutomator、Android Accessibility 的查找、操作、状态与父级选择 | Windows/ADB 见 DDT v3；Android Accessibility 见 Android v4 接收候选。最终还需把不同控件操作/状态失败语义集中为同一报告 | Partial |
| ACC-004 | 多实例消息与组队 | 明确收件人、同步接收、监听、串行恢复、已读、幂等与离线 | `output/g9-android-evidence/android-emulator-to-phone-lan.json` 以当前 Android 源码候选再次证明模拟器→真机加密 LAN、先发送后就绪、同步消息、监听接手、处理后恢复和双端已读；物理双机、反向 NAT、网络分区仍未覆盖 | Partial |
| ACC-005 | 文件、HTTP、更新与离线 | 类型化文件/SAF、请求/上传/下载、内容与应用更新、关闭更新零外连、失败恢复 | `output/g11-file-http-acceptance-final/file-http-evidence.json` 已由 G11 冻结 Player 执行签名无源码项目，项目内断言文件写入/替换/读取、请求、上传、失败下载不覆盖和成功原子下载；`output/g11-android-network-runtime/android-network-real-device-evidence.json` 又在 API 33 物理手机与 API 34 x86_64 模拟器的真实 Android 进程验证请求/上传/下载。G7 内容/应用更新、回滚、断点续传和关闭更新证据继续冻结；最终仍需把更新证据归并到候选家族并补正式签名矩阵 | Partial |
| ACC-006 | Android 本机独立运行 | 断开 IDE/后端后的 Player、MediaProjection、Accessibility、OCR、输入、控件、文件、录制、消息、更新与日志 | Android v4 在 API 33 真机完成组合运行并到达 sequence 24 `completed`；G11 网络候选补齐真机 HTTP/上传/下载；G12 `output/g12-android-basics/android-basics-real-device-evidence.json` 又以项目内断言确认 1080×2340 画面保存、同帧取色/找色和剪贴板往返，运行终态为 `completed`。正式签名、非小米实体设备、断开数据线/IDE/后端及真机更新矩阵未完成 | Partial |

## 候选纪律

- 六个项目的业务能力证据继续引用 G9–G12 的真实运行报告，不伪装为 G16 全量重跑。G16 相对已验收 Runtime 的增量只涉及 UI 冻结产物和终态 Session/Worker 资源释放；统一自动回归为 Python `1303 passed, 2 skipped`、前端 537/537，并通过同哈希 30 分钟资源预检。因此旧业务证据按“能力未变、增量回归覆盖”冻结继承；若最终长稳或外部矩阵暴露业务失败，必须回到对应项目重跑。
- 当前 Windows 冻结候选为 `output/g16-session-gate-windows-player/Player_Bundle`，清单 `candidate-manifest.json` 锁定核心 Runtime SHA-256 `f12ac55a364f6269c1babc7e89035e6933723756aecf8aa6b64f5443457e0151` 与 Player SHA-256 `c2c2a44d1e5fa93c274c5569bfb657b237ee9592bae3cf805f187e219d9c6507`。长稳专用包复用相同 Player 字节，只替换为当前格式的签名 Harness 项目包；最终 24 小时报告单独记录并校验两者哈希。
- 当前 UI 冻结 Android 安装候选为 `output/g16-session-gate-android/EasyCodePlayer-productionDebug.apk`，SHA-256 `49ec3e7414f2d3bd6d5636fc783ae70f5911505c804c73e03cbd5057099b5fa0`；它已在 API 34 模拟器和 API 33 物理手机完成安装/前台启动复核。本轮没有重新执行六项目业务流程，因此不能替代 G9–G12 的功能报告，也不能关闭正式签名、断线独立与非小米设备门。
- 历史跨平台家族身份仍保留于 `output/g12-release-candidate-family/candidate-family.json`（家族 SHA-256 `e0f7af1db4dba12c69f5223a71b8f66a3409efbce899f37bd32b108ca87c695f`），用于追踪 G9 消息双角色 APK、G12 Android 基础能力 APK、G11 Windows 清单及对应真实证据，不被 G16 覆盖。
- Android 每个角色 APK 会因嵌入的签名项目包而拥有不同整包哈希；必须同时记录变体、application id、项目 release id 和 APK SHA-256。仅目录名相同不表示候选相同。
- `Passed candidate` 只表示当前候选和当前环境通过，不等于正式发布；生产签名、第二台物理主机和干净客户机继续独立列为外部完成门。
- Harness 的成功日志必须由已验证结果分支产生。可选结果为空、等待超时或监听未接手时必须主动失败，禁止在后续无条件输出“已验证”。
