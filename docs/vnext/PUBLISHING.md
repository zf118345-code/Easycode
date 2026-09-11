# 独立 Windows Player 发布边界

状态：v6 契约已冻结。本文定义 Windows Player 的最小进程、HTTP、前端与文件发布边界；一次构建是否通过以及真实 Windows 宿主证据记录在 Harness 产物中，不写回本规范。

## 1. 目标与范围

Windows Player 是执行已签名 `.ecplayer` 的独立产品，不是隐藏了菜单的 IDE。交付物必须在没有项目目录、ProgramDocument、作者服务、开发后端和系统 Python 的环境中加载固定发布者的包，提供终端表单、运行控制、诊断、已发布字段动作，以及该安装明确需要的更新、计划和 LAN 管理能力。

同一冻结 EXE 还可以用 `--player-console` 启动当前用户多实例控制台；该入口不绑定单一包，只能枚举 Player Hub 已验签登记的产品，并为所选实例启动独立的 Player-only 工作进程。完整交互和故障边界见 [`PLAYER_CONSOLE.md`](PLAYER_CONSOLE.md)。

本边界不包含工作区、ProgramDocument 编辑、Player 设计器、编译、作者发布/打包、扩展开发、旧节点执行器、旧条件/参数系统、IDE Capture 管理、Replay 编辑入口或任意 legacy API。Android APK 使用 [`ANDROID.md`](ANDROID.md) 的本机边界，不复用本文件的 Python/HTTP 宿主。

## 2. 进程启动与信任顺序

- `[REQ-PUB-WIN-001]` 正式入口是专用 `player.py`。在任何 FastAPI 应用、Bundle Manager 或运行时全局初始化前，只允许导入 Python 标准库，先分派 capability worker、扩展 worker 与 Player Hub agent，再解析命令行。
- `[REQ-PUB-WIN-002]` 普通 Player 分支必须同时取得存在的 `.ecplayer` 与外部 `trust-root.json`，规范化绝对路径并提交 `EASYCODE_PLAYER_BUNDLE`、`EASYCODE_PLAYER_TRUST_ROOT` 和强制信任标志后，才可导入 DPI、应用工厂、Bundle Loader 或 Runtime。缺失、错误扩展名或非本机 HTTP 监听地址直接启动失败，不创建半初始化应用。
- Worker 分支不解析普通 Player 参数，也不加载 Player Web/API。普通分支只监听 loopback；远端请求即使绕过监听配置也由应用边界返回 `403`。

## 3. Player-only HTTP 合约

- `[REQ-PUB-WIN-003]` 独立应用采用显式闭集：签名包 bootstrap/环境检查/方案/字段动作/运行启动，运行状态、事件、暂停、继续、停止、诊断和失败帧，终端 Capture SSE/动作确认/关闭，已录制会话的终端列表、查看、帧读取、导出与删除，以及终端更新、计划、Player Hub 和 Player LAN 管理路由。OpenAPI 操作集合必须由精确白名单测试锁定，新增路径视为发布边界变化。
- Capture 公网面只保留 `/api/ui-control/events`、`/api/capture/action`、`/api/capture/action/ack` 和 `/api/capture/close`。会话注册、目标冻结帧创建和宿主触发由已验证的 Player Runtime 内部调用，不能开放 legacy session/snapshot/asset/replay、全局 UI-control 模式、热键或 IDE 设置路由。
- 工作区、ProgramDocument、项目函数编辑、Player 设计器、编译、作者发布/打包、扩展管理和全部 legacy 路径必须为 `404`。本机更新路由可以稳定存在并返回当前产品域的禁用状态；作者关闭更新时仍不得携带远端 Feed 端点、产品身份、后台检查器或可见入口，也不得发生网络请求。
- 应用不导出模块级全局 `app`；测试、桌面入口和冻结运行时均显式调用应用工厂。异常统一产生结构化错误和请求 ID，不能把签名/状态冲突伪装成成功或空对象。

## 4. 导入图与冻结运行时

- `[REQ-PUB-WIN-004]` 创建应用并生成 OpenAPI 后的导入图不得包含 IDE 应用、完整 vNext Router、Workspace Manager、Compiler/Publisher、Program Service、旧 Execution/Capture/Replay 服务、旧 `node_executors`/`conditions`/`player`/`params` 包。`core.vnext` 根包必须惰性导出，不能因导入一个运行模块而隐式装载 Workspace。
- PyInstaller 清单以专用入口和显式运行闭包为准，不允许对 `core.vnext`、旧节点执行器、条件、Player 或参数包做整包 `collect_submodules`。允许闭包限于 ECIR Runtime、实际官方运行适配器、OCR 运行数据、受控扩展 worker、目标/capture/native 宿主，以及计划、LAN、消息、文件、网络和更新的终端实现。
- 已发布扩展调用只能进入密封扩展校验与 Worker 协议模块；开发态发现、信任写入、签名创建、骨架生成和 Workspace 扩展服务不得进入 Player 清单。源码 IDE 只有在不存在发布运行锁时才可走开发态扩展路径。
- 动态入口必须逐项列入清单并用导入/运行测试证明；`excludes` 只是第二道失败保护，不能替代显式 allowlist 和导入图证据。

## 5. Player-only Web 产物

- `[REQ-PUB-WIN-005]` Vite 使用独立 Player 配置，只构建 `player.html` 与 `capture.html`。`player.html` 只能依赖 Player API 客户端；`capture.html` 只承担原生终端 Capture 就绪桥，不装载 IDE 资源管理器。产物不得包含 `index.html`、`src/`、Vue/TypeScript/JSX 源、source map 或 `.easy`。
- Player Web 客户端不能导入作者/Workspace API 汇总模块。对运行、更新和 Capture ACK 的请求由窄客户端显式列出；后端不存在的入口不得以隐藏按钮保留。

## 6. 组装与源码隔离

- `[REQ-PUB-WIN-006]` 发布与 readiness 只接受冻结 Runtime 模板和 `release/player-web`。组装器要求 `EasycodePlayer.exe`、`player.html`、`capture.html` 三者齐全，并在写入交付目录前拒绝 IDE 首页、前端源码、EasyCode/作者 Python 源、source map 和项目 `src` 目录。冻结 Runtime 在 `_internal` 中为运行所需携带的第三方 Python 支持文件与依赖许可证不属于作者源码，但仍由依赖锁、清单与发布扫描约束。
- `[REQ-PUB-WIN-007]` `.ecplayer` 在组装前由同一 Loader 完整验签，并扫描 ZIP 文件清单；任何 `.easy`、`programs/`、`program.json`、`ProgramDocument` 或等价可编辑程序事实都阻止交付。交付目录只保存 Runtime、编译后的 Player Web、签名包、公开信任根、启动脚本和非秘密构建清单。
- 组装使用临时目录和原子替换。失败保留既有完整交付，清理只允许发生在已验证的输出父目录内；信任根和私钥边界继续遵守 [`PLAYER.md`](PLAYER.md) 与 ADR-059。

## 7. 真实加载与失败语义

- `[REQ-PUB-WIN-008]` 自动验收必须用真实签名 `.ecplayer` 和匹配外部信任根通过专用应用完成 bootstrap、无目标 ECIR 运行和停止，不得只 mock Bundle Manager。错误信任根、源文件污染、缺少静态页、越权路由和 CLI 顺序回归分别有独立失败证据。
- Bundle 加载失败时不创建运行；启动请求在方案/目标/危险确认校验前不得执行 ECIR。停止返回同一运行 ID 的终态，暂停/继续不创建新运行。更新、LAN 或计划故障不得冒充任务运行故障。

## 8. 放行与非目标

自动 OpenAPI、导入图、文件清单、Vite、签名包和专项 pytest 只能证明代码边界。首个正式 Windows 交付仍必须在没有系统 Python、没有 IDE/开发后端的干净 Windows 主机上，从组装目录启动真实 `EasycodePlayer.exe`，完成 WebView2、原生 Capture、OCR/目标驱动、扩展 worker、计划/LAN（若启用）和离线网络审计。未执行 PyInstaller 或真实宿主冒烟时必须明确标记“未验证”，不能用源码进程或浏览器测试替代。

窗口化 Player 在应用导入、签名包加载或 HTTP/WebView 启动前失败时，也必须在 `%LOCALAPPDATA%\\EasyCode\\Player\\logs` 写入启动诊断；不得只依赖不可见的 stdout/stderr 或表现为无声闪退。正常运行日志与 Python 原生崩溃日志使用同一目录，便于终端用户导出证据。

范围外：安装器签名/升级助手、商业授权、云端设备舰队、自动遥测、Android APK，以及尚未冻结的全局热键设置与 IDE Capture/Replay 管理界面。
