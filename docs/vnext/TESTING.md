# vNext 验收与测试

状态：`Approved`（首版垂直切片验收项与反向范围检查已冻结；环境证据状态仍由 Harness 报告，不因规格批准而视为已实现）

最近修订：2026-09-03

本文档只定义 vNext 垂直切片的重点验收。命令顺序、证据等级、故障注入、资源保护和发布门统一遵循 [`../TEST_HARNESS.md`](../TEST_HARNESS.md)。

## 1. 核心程序切片

- `[AC-VN-PGM-001]` ProgramDocument 是项目函数唯一可编辑事实；结构化语句投影、检查器、变量和调试器不保存平行模型，不存在 `.easy`、Monaco、解析草稿或文本反向导入路径。
- `[AC-VN-PGM-002]` 插入、移动、复制、嵌套、删除、提取函数、撤销和重做都经过版本化结构命令；移动保留 ID，复制产生新 ID，无关 ID 不变。
- `[AC-VN-PGM-003]` 缺少必填值使用类型化 `unset` 状态；对象可保存、选择和修复，但编译、运行和发布被明确阻止。
- `[AC-VN-PGM-004]` 相同 ProgramDocument、函数契约、扩展锁、资源和编译器版本生成字节级或规范化等价 ECIR；IDE 与 Player 执行同一语义。
- `[AC-VN-PGM-COL-001]` 记录、列表、字典、JSON 和结构化集合变换通过 Schema、ProgramDocument、ECIR、IDE 与 Player 契约测试；固定快照循环、缺失值、JSON 转换和大型集合渲染均有覆盖。
- `[AC-VN-PGM-EXPR-001]` 完整递归纯值树通过 ProgramDocument、结构命令、类型检查、ECIR、IDE/Player 等价执行和跨平台契约测试；普通函数、I/O、文本公式和扩展私有语法均不能进入表达式。
- `[AC-VN-PGM-EXPR-002]` 稳定 `value_id` 在移动、折叠、改名、包装、解包、复制、提取、撤销和重做中符合保留/新建规则；诊断、调试和 Player 嵌套绑定不依赖显示摘要或树路径。
- `[AC-VN-PGM-EXPR-003]` 条件选择只求值命中分支；赋值/函数提取只在作用域、次数、惰性、空值、错误和来源目标保持等价时生效，否则结构事务原子回滚。
- `[AC-VN-PGM-EXPR-004]` Player 只能覆盖已签名参数根或嵌套值槽；父子重叠、未知/过期节点、结构注入、越权引用和类型不兼容在运行前拒绝。
- `[AC-VN-PGM-EXPR-005]` 循环引用与节点、深度、编译时间、ECIR 体积和运行内存预算具有可取消压力测试和精确诊断；预算只作为安全门，不缩减正常组合能力。
- `[AC-VN-PGM-EXPR-006]` 纯值操作注册表的稳定操作/输入槽 ID、版本和内容哈希贯穿 `easycode.lock`、编译缓存、ECIR 与发布签名；未知或漂移操作被拒绝。
- `[AC-VN-PGM-EXPR-007]` `core.file_ref_child.v1` 只在授权根内派生能力不扩大的文件引用且不访问文件系统；`core.json_parse_text.v1` 对合法 JSON 产生确定值、对非法 JSON 产生正常无结果，两者在 Windows/Android 与 Player 覆盖中语义一致。
- `[AC-VN-PGM-EXPR-008]` 加载、修改、撤销和重做返回的 Program 快照只携带文档实际引用到的操作、输入槽、记录类型和字段展示元数据；中央摘要、检查器和聚焦编辑显示同一中文名称，未知展示契约显示明确不可用状态，不把稳定 ID 当作用户文案。
- `[AC-VN-PGM-SUMMARY-001]` 全部官方函数目录项投影版本化、仅引用已声明参数的 `statement_summary`；受控扩展可使用同一模板槽且未知参数在注册前拒绝，省略时回退规范函数名。前端结构化消费固定文字与参数值，不把摘要保存为 ProgramDocument 第二事实；图片、枚举、百分比、引用失效和旧纯文本摘要均有契约与组件回归。
- `[AC-VN-PGM-CLOSURE-001]` ProgramDocument 每一种已批准语句和值节点都具有 `validation → compiler → ECIR → runtime` 闭环证据，或在 Compiler Service 产生稳定阻断诊断。`target_scope` 已在 Windows Runtime 完成 Windows/ADB 串行切换，其目标闭包错误返回 `PGM-TARGET-001..003`；`listen` 已链接普通项目处理函数并由进程内 Runtime/隔离 Worker 在安全检查点串行调度，同步等待与监听的静态重叠和动态不确定范围分别返回 `PGM-MSG-001 / PGM-MSG-002`。未知、planned、输入槽错误和类型错误的纯值操作分别返回 `PGM-OP-001..004`，不得生成空操作、顺序误执行或延迟到 Runtime 才发现。自动化证据见 `tests/test_vnext_message_listen_runtime_v6.py`，并由消息、Program linker/service、目标作用域、平台原子性和 Worker 事件回归组共同覆盖。
- `[AC-VN-PGM-CLOSURE-002]` 已验证纯值操作覆盖递归数值/文本/可选/选择/几何、列表/字典不可变查询更新、结构化筛选/转换/稳定排序/分组/查找/统计/索引、JSON 解析/严格 Schema/路径不可变更新，以及授权目录内的能力不扩张文件引用派生；专项测试覆盖嵌套词法遮蔽、确定性降低、惰性短路、可选空结果、重复键、固定快照、结构复制 ID、Player 嵌套签名槽、取消、100,000 项预算、10,000 项性能基线、相对位置穿越拒绝与输出能力缩减。自动证据见 `tests/test_vnext_collection_selectors_v6.py`、`tests/test_vnext_file_reference_operation_v6.py`、`tests/test_vnext_player_bindings_v6.py` 与 Program Control 聚焦组件测试；Android 本机仍须以签名 APK 和真实 SAF Provider Harness 单独放行。
- `[AC-VN-PGM-RETRY-001]` 异常区域可选重试策略经过 ProgramDocument、结构命令、确定性 ECIR、调试映射和 IDE/Player 等价测试；策略缺省关闭，启用默认最多再试 2 次、固定间隔 500ms。
- `[AC-VN-PGM-RETRY-002]` 瞬时异常按次数重试，永久/未知异常直接捕获，正常无结果、HTTP `4xx/5xx`、取消与停止不重试；暂停/继续保持同一尝试和剩余间隔。
- `[AC-VN-PGM-RETRY-003]` 每次重试从区域主体开头开始且不回滚变量或外部副作用；耗尽后捕获分支只接收最后异常，最终分支只执行一次，日志记录区域 ID、尝试序号、异常 ID 和每次新的操作 ID。
- `[AC-VN-PGM-RETRY-004]` 直接或传递副作用触发作者审核门；未确认草稿可以继续编辑但不能编译、运行或发布。客户端只提交 `statement_id + expected_revision`，服务端根据当前主体与锁定契约计算并写入指纹，响应返回新 revision、完整快照和撤销/重做状态；请求携带指纹、无策略、无副作用或过期 revision 分别以 `422 / 409` 拒绝且不修改文档。确认后编译通过；修改区域主体、引用函数或锁定契约后旧指纹失效并产生 `PGM-TRY-003`，重新确认前继续阻断。撤销确认恢复未确认快照，重做恢复相同的服务端审核事实，所有 statement/value ID 保持不变。
- `[AC-VN-PGM-DANGER-001]` `目录.递归删除` 使用普通调用与独立作者审核事实；语句、目录参数值树、函数契约或权限版本变化使指纹失效，审核事实不进入函数参数且不能替代 IDE 调试或 Player 对实际授权根的执行确认。

检查器专项覆盖类型化参数、返回绑定、字段级错误、Control 未提交草稿、revision 冲突和切换不丢数据。诊断使用稳定 `function_id + statement_id + value_id` 并附带可读字段路径，不依赖文本行号或当前树路径。

### 1.0.1 统一输入器当前证据状态（2026-09-02）

- **自动验证通过**：前端全量 95 个测试文件、483 项断言通过；其中 Program 专项 21 个文件、129 项断言覆盖直接值、引用、操作补全、比较、选择器作用域、稳定 ID、中文展示投影、非法草稿和结构编辑。`vue-tsc --noEmit`、ESLint 与生产构建通过。后端纯值目录、语法参考、集合选择器、Program 语义、HTTP、Runtime、字段命令和流程控制共 87 项专项测试通过。
- **人工验证通过**：在 DDT 项目的真实 IDE 页面把整数赋值改为 `数值.相加(80, 6)`，重载后中央语句显示 `(80 + 6)`；把判断条件以 `@当前体力 >= @最低体力` 提交后仍绑定原局部/项目变量。显式无操作目标下检查通过并运行完成，日志输出“体力足够，可以继续副本”。输入无效整数“十八岁”时，输入器保留草稿并就地说明错误，Escape 恢复旧值；进入整数编辑只产生一次值目录请求，浏览器控制台无错误。截图见 [`../../output/playwright/expression-input-ddt-proof.png`](../../output/playwright/expression-input-ddt-proof.png) 与 [`../../output/playwright/expression-completion-ddt-proof.png`](../../output/playwright/expression-completion-ddt-proof.png)。
- **中文投影人工验证通过**：重启 Program Service 并重新打开 DDT 后，持久化为稳定 ID `core.number_max.v1` 的值在中央语句、检查器摘要和统一输入器中一致显示为 `数值.取较大值(18, 3)`；把右侧参数由 `3` 改为 `4`、保存、刷新再改回 `3` 后仍保持中文投影，页面不出现内部操作 ID。截图见 [`../../output/playwright/chinese-expression-projection-final.png`](../../output/playwright/chinese-expression-projection-final.png)。
- **未验证**：本条只证明 Windows IDE 中的统一输入交互和无目标运行，不替代 Android 本机 Player、真实 Windows/ADB 目标或发布包的整体验收。

### 1.1 官方函数契约与视觉结果

- `[AC-FUNC-APP-001]` Windows 宿主使用类型化应用引用启动真实应用并等待同一进程退出；Shell 文本、PowerShell、命令解释器和脚本宿主通用执行入口均被契约/发布检查拒绝。
- `[AC-FUNC-WIN-001]` Windows 真实宿主覆盖窗口立即查找、等待、激活、关闭，以及位置、尺寸、可见性和前台状态读取；句柄失效或被复用时不得操作错误窗口。
- `[AC-FUNC-TGT-001]` 真实模拟器完成“Windows 启动应用 → 等待对应 ADB 目标 → 进入目标作用域”，且没有专用模拟器运行语义、缓存串用或错误目标回退。
- `[AC-FUNC-FRAME-001]` 连续两个普通视觉调用分别取得调用开始后的新帧；运行时不得因同目标或相同参数自动让第二次消费第一帧。
- `[AC-FUNC-FRAME-002]` 多个图像/OCR调用传入同一 `frame_ref` 时分析相同像素并产生相同来源目标/空间版本；传入其他目标或已变化空间的输入动作在执行前被拒绝。
- `[AC-FUNC-RESULT-001]` 图像、文字、控件和窗口的立即未命中与等待到期产生正常空结果和正常完成日志；缺失资源、权限、目标、平台或驱动/扩展故障产生可区分结构化异常。
- `[AC-FUNC-NAME-001]` 改显示名、分类或搜索别名不改变 ProgramDocument、Player、ECIR 和日志关联使用的稳定 `function_id`；别名不能作为持久引用解析。
- `[AC-FUNC-DEFAULT-001]` 安全默认值生成类型化值；必填资源、路径、目标、窗口选择器和其他不可推断值生成 `unset`，且当前选择与历史输入不会静默填入。
- `[AC-FUNC-PLATFORM-001]` 每个官方函数的 Windows、ADB、Android 本机与无目标矩阵由 IDE、Compiler、Publisher 和 Runtime 使用同一契约；不支持调用在运行前定位阻止。
- `[AC-FUNC-PLATFORM-002]` 每个平台条目分别验证支持状态、实现证据和条件能力 ID；可插入目录只返回至少一个 verified 平台的函数并携带 `verified_platforms + platform_support`。固定测试函数在 Windows/ADB 编译和 Runtime adapter 绑定成功，在 Android 本机以“尚未验证”阻止；未指定平台的 ECIR 只声明依赖闭包共同 verified 的平台。把 planned 改成 verified 必须伴随对应真实宿主证据，不能由同一 Python 单元测试推导 Android 本机结论。
- `[AC-FUNC-VERSION-001]` 相同函数稳定 ID 的锁定版本/指纹在不同机器生成相同编译输入；注册表漂移、兼容新版或破坏性新版均不能在打开项目时改写锁。
- `[AC-FUNC-MIGRATION-001]` 显式迁移列出受影响调用、Player 字段、目标平台和发布闭包并原子提交；取消、故障注入或迁移后验证失败时 ProgramDocument 与 `easycode.lock` 同时回滚，原版本继续构建。
- `[AC-FUNC-CATALOG-001]` 官方注册表逐项匹配 `FUNCTIONS.md` 的 78 个稳定 ID、规范显示名、原子/标准标记和结果类型；缺项、重复、同义规范函数或禁止命名空间使契约测试失败。
- `[AC-FUNC-CATALOG-002]` 所有标准函数的 ProgramDocument 定义与任何融合实现逐项通过返回、异常、超时、取消、日志和调试等价性测试。
- `[AC-FUNC-MATRIX-001]` 每项调用分别按运行宿主和目标能力计算 Windows/Windows、Windows/ADB、Android 本机与无目标结论；编辑、编译、发布和运行诊断一致。
- `[AC-FUNC-TYPE-001]` `date`、`TargetInfo`、`FrameReference`、`ImageMatch`、`OCRLine` 和 `OCRResult` 使用稳定类型/字段 ID，成员选择与可选值收窄不依赖中文名或字符串键。
- `[AC-FUNC-APP-ANDROID-001]` 签名 Android 测试 APK 在真机使用 `应用.启动` 启动批准应用，覆盖 Intent、权限/找不到应用、前后台、取得新目标帧和返回 Player；ADB 启动结果不能替代该证据。

### 1.1.1 当前基础平台切片证据状态

- **自动验证通过**：官方 v1 注册表 78/78 均为 `complete/available`，每项可用函数都有 Runtime 绑定；PlatformRuntime 适配器声明的 opcode 现在必须与隔离会话分派集合精确相等，防止“Compiler 与适配器已实现、Worker 未接线”再次发生。官方标准函数定义均是可校验、可编译的 `ProgramDocument`，融合路径对规范组合逐项验证返回与原子轨迹；窗口/控件/图像/OCR 轮询覆盖新状态、正常空超时、取消、`exact / contains / regex` 和无效正则错误；`时间.今天` 覆盖系统/UTC/IANA 时区日期边界和无效时区；`项目.数据目录` 覆盖 IDE/Player 宿主根且不自动授予递归删除。其他已有证据包括目标引用闭包与在线/状态替身、Windows `.exe` 安全启动、ADB 包/Activity 固定 argv、应用状态/停止、Windows 窗口句柄复用保护、UIA 重新定位、Windows 物理回退证据、ADB scrcpy/Capture 契约以及单文档/bundle ECIR 确定性。
- **无操作目标自动证据**：IDE 检查与运行、HTTP 省略平台的项目检查、Player 预览与独立 Player 均把空目标解析为显式 `no_target`。图像/输入/目标帧调用在创建 Runtime session 前以 `PGM-PLATFORM-001` 或 Player 预检失败阻止；参数检查器在无目标时不展示取点、框选和视觉录入动作。证据见 `tests/test_vnext_program_http_full_v6.py`、`tests/test_vnext_distribution_v6.py`、`frontend/src/vnext/__tests__/VNextIdeV6Capture.test.ts` 与 Program API 适配器测试。
- **递归删除自动安全证据**：独立 `filesystem.delete_tree` 权限、服务端作者审核指纹及参数改动失效、编译产物契约指纹、Player 运行前服务端解析实际目标、客户端显式确认与伪造/过期确认拒绝已闭环。Runtime 仅在 `pytest tmp_path` 执行成功删除，并验证盘符根、用户目录、工作区/Player 数据根、未授权树、目标或后代符号链接越界均在第一次修改前拒绝；成功与文件系统失败返回显式删除计数和失败报告。
- **真实宿主证据**：Windows 应用/窗口、UIA、模拟器与连接手机 ADB 的包/Activity、输入、捕获和回填已经完成对应真实宿主切片；Android 本机也已在 API 33 真机完成 Capture、Accessibility、SAF、文件、视觉、输入与 Runtime 关键流程，并在 API 34 模拟器完成真实 loopback HTTP 请求、上传与原子下载。Windows 锁屏/UAC、Android 非小米设备、物理 Android 网络/外部 Provider、计划休眠和生产签名等仍按各领域完成门保持未验证。
- **环境限制**：Windows 开发机若未开启符号链接创建权限，链接逃逸用例标记为环境跳过；其他非链接保护仍自动执行。本切片不使用自动单元证据冒充 Windows/ADB/Android 真实宿主；已经取得的单机证据也不能替代未覆盖的平台、权限和设备矩阵。

### 1.2 项目格式 6

- `[AC-VN-FMT-001]` 新建项目只生成 `format_version: 6`、ProgramDocument、变量/资源/Player 注册表和 `easycode.lock`；打开格式 5、旧画布或 `.easy` 只返回不支持诊断，不迁移或兼容写回。
- `[AC-VN-FMT-002]` 相同项目模型、Manifest、函数契约、依赖解析和工具链产生确定性等价的 ProgramDocument JSON 与 lock；外部冲突不会造成无限 409 或静默覆盖。
- `[AC-VN-FMT-003]` Manifest/lock/密封产物缺失、哈希/签名漂移、宿主变体不兼容或信任缺失时定位 `package_id + variant_id` 并阻止编译/发布。
- `[AC-VN-FMT-004]` `.ecplayer`、Windows Bundle 和 Android APK 扫描证明不存在 `program/`、`.easycode/`、扩展源码、测试、构建/IDE 配置或未锁依赖。

## 2. 资源、捕获与回放

- `[AC-VN-RES-001]` 资源在 ProgramDocument 或扩展命名空间数据中以稳定 `asset_id` 结构引用；重命名和移动不破坏引用。
- `[AC-VN-RES-002]` 所有选择、录入和 Capture Session 保存入口始终显示可切换的 `image / ocr / page` 三个根目录；入口只能决定默认目录。
- `[AC-VN-RES-003]` 单击资源只选中；确认后才通过结构命令更新参数。提交失败保留选中项和绑定上下文。
- `[AC-VN-RES-004]` 真实 PNG/JPEG/BMP/WEBP 导入和替换经过完整解码与扩展名校验；损坏、伪装格式、空文件和超限文件在注册表或文件变化前拒绝。尺寸、字节数、SHA-256、来源和重复内容提示与真实文件一致。
- `[AC-VN-RES-005]` Capture Session 保存的分类取用户最终选择，元数据记录真实目标、平台、宿主、选择区域、来源工作区和参考尺寸；资源模型没有可被后续调用继承的运行区域字段。
- `[AC-VN-RES-006]` 工作区/目标/目的地/revision 过期、IDE 回填拒绝或原生宿主取消时不留下孤立资源；已创建事务完成撤销，窗口保留可恢复上下文。同名资源的引用检查异常按 `409` 失败关闭。
- `[AC-VN-RES-007]` 重命名、跨分类移动和目录移动保留稳定 ID；删除存在引用的资源/目录被阻止，未引用删除需要确认，确认期间新增引用仍阻止且不宣称静默清空源码。
- `[AC-VN-RES-008]` 加载失败时三类入口仍可见并提供重试；键盘可以完成搜索、目录切换、资源选择/确认、重命名和删除，删除后聚焦相邻项。`<1100px` 检查器使用抽屉，关闭后恢复资源焦点，`700px` 以下不遮挡主要操作。

### 2.1 IDE v6 资源与 Capture 当前证据状态（2026-09-01）

- **自动验证通过**：`tests/test_vnext_resources_capture_integration_v6.py` 使用临时 format 6 项目和真实图片字节覆盖固定三目录、目录/分类移动、稳定 ID、哈希与外部修改检测、损坏图片和扩展名伪装拒绝、重复内容提示、引用阻止删除、Capture 最终目录、真实溯源元数据、损坏 ProgramDocument 时覆盖失败关闭及资源事务撤销。
- **自动静态验证通过**：资源工作区、IDE 壳、Capture Session、Capture 文件管理器、FileBrowser、类型契约及其聚焦测试文件通过 ESLint，四个相关 SFC 通过 Vue 编译器解析；前端 `vue-tsc --noEmit` 通过。
- **人工验证通过**：无；本轮没有把静态检查或 jsdom 断言提升为真实 WebView/Windows 宿主证据。
- **自动验证通过**：vNext 前端 Vitest 共 66 个测试文件、164 项断言通过；其中资源工作区 12 项覆盖三目录加载失败重试、独立视觉录入的分类默认值/串行忙态/取消回焦、真实元数据、重复导入提示、两阶段选择、引用阻止删除、二次确认、删除后相邻资源选中与焦点恢复、跨分类移动和后台刷新不阻塞已有资源库。
- **未验证**：真实 IDE WebView 的文件选择取消/多文件导入、Capture Overlay 到资源管理器再回填的端到端路径、`409` 后人工重试、键盘遍历与焦点可见性、`1099px / 700px` 窄宽和 Windows DPI 100%–200% 视觉冒烟。

录制与回放的唯一验收定义见 [`TEST_HARNESS.md`](../TEST_HARNESS.md) 中 `AC-VN-REPLAY-001..010` 与 `AC-VN-REPLAY-SCOPE-001`。本文件只负责说明它们属于资源、捕获与回放垂直切片，不复制第二份可能漂移的正文。

| 需求 | 覆盖验收 |
| --- | --- |
| `REQ-REPLAY-001` | `AC-VN-REPLAY-002`、`AC-VN-REPLAY-004`、`AC-VN-REPLAY-010` |
| `REQ-REPLAY-002` | `AC-VN-REPLAY-002` |
| `REQ-REPLAY-003` | `AC-VN-REPLAY-003` |
| `REQ-REPLAY-004` | `AC-VN-REPLAY-004`、`AC-VN-REPLAY-009` |
| `REQ-REPLAY-005` | `AC-VN-REPLAY-005` |
| `REQ-REPLAY-006` | `AC-VN-REPLAY-006` |
| `REQ-REPLAY-007` | `AC-VN-REPLAY-001` |
| `REQ-REPLAY-008` | `AC-VN-REPLAY-007` |
| `REQ-REPLAY-009` | `AC-VN-REPLAY-008` |
| `REQ-REPLAY-010` | `AC-VN-REPLAY-009` |
| `REQ-REPLAY-011` | `AC-VN-REPLAY-009` |
| `REQ-REPLAY-012` | `AC-VN-REPLAY-SCOPE-001` |

捕获专项覆盖 IDE 与 Player 两种目的地、点、区域、截取/选择图片、控件、手势路径、读文件、保存位置和目录，并验证项目/产品、会话、目标、字段、方案 revision、并发、取消、拒绝、权限撤销、过期和原生宿主崩溃。

## 3. 扩展与首版范围

- `[AC-VN-EXT-001]` 有效/无效 `easycode-extension.json`、签名、依赖、权限、贡献点、宿主/目标变体和数据 Schema 均经过严格 Schema 与集成测试。
- `[AC-VN-EXT-002]` 相同解析输入生成规范化等价 `easycode.lock`；本机版本漂移、发布者指纹变化、信任缺失和依赖冲突不会静默改写项目。
- `[AC-VN-EXT-003]` 未启用扩展没有入口、Worker、轮询、编译输入、ECIR/Player 依赖或包体文件；启停事务失败回到原状态。
- `[AC-VN-EXT-004]` 未信任包的可执行贡献被阻止，声明式安全视图不能注入脚本或越权命令；可信代码批准、撤销和换机缺失具有真实状态。
- `[AC-VN-EXT-005]` Worker 超时、取消、崩溃、非法返回、序列化失败和缺失依赖产生定位到 `package_id + contribution_id/function_id` 的诊断，不拖垮宿主。
- `[AC-VN-EXT-006]` Windows/ADB 与 Android 真机分别加载锁定密封变体；Python-only、ABI/签名不兼容或缺少目标能力的扩展在发布前失败。
- `[AC-VN-EXT-007]` 发布包扫描证明不存在扩展源码、测试、构建/IDE 配置、未锁依赖或运行期下载入口；Bundle Loader 拒绝篡改、路径越界和哈希漂移。
- `[AC-VN-EXT-008]` 中立扩展覆盖函数、声明式工作区、命名空间数据、受信任编译/运行模块、禁用回收和发布闭包，但不进入产品清单或正式包。
- `[AC-EXT-GENERIC-001]` 中立测试扩展证明扩展地基不依赖页面导航，并满足 `[AC-VN-EXT-001..008]`。
- `[AC-SCOPE-PAGE-001]` IDE、Windows Bundle 与 Android APK 不包含页面导航包、Page Model、`页面.*`、页面工作区、页面 Worker 或拓扑组件。
- `[AC-SCOPE-PAGE-002]` 新建、打开、编译、运行、发布和空闲生命周期均无页面入口或后台活动。
- `[AC-SCOPE-PAGE-003]` `page` 资源目录可选择、录入和引用，但不会激活页面函数、服务或发布依赖。

## 4. Player 与发布

- `[AC-VN-PLY-001]` Player Schema 使用判别式稳定函数/语句/参数/嵌套值/变量/资源/目标 ID；运行时只把终端用户值应用到已签名覆盖槽，不改写表达式结构或签名 ECIR。
- `[AC-VN-PLY-002]` `.ecplayer` 和独立 Player 不包含 ProgramDocument、可编辑投影数据、扩展源码、测试或 IDE 组件；扩展只携带已构建、已签名的运行产物。
- `[AC-VN-PLY-003]` Bundle Loader 拒绝签名/哈希失配、路径穿越、符号链接、不兼容版本、未声明权限、缺失依赖闭包和源码泄漏。
- `[AC-VN-PLY-004]` 全部已批准 Control 经过设计器、Schema 持久化、发布、运行端渲染、校验和平台动作的同契约遍历。
- `[AC-PLY-CAP-001]` Player 字段默认无终端动作；只有作者逐字段/动作/平台开放且满足字段类型、发布闭包、宿主/目标和当前权限的动作才出现。
- `[AC-PLY-CAP-002]` IDE 与 Player 使用同一强类型捕获结果；Player 按 `control_id + action_id` 原子修改运行方案或私有资源覆盖，不改 ProgramDocument 或签名 ECIR。
- `[AC-PLY-CAP-003]` 取消、拒绝、永久拒绝、撤销、目标离线、目标/方向/revision 变化和宿主失败均保持字段旧值与草稿，恢复后回到原字段。
- `[AC-PLY-CAP-004]` 同一 Player 实例的 Capture Session 串行且不串字段；运行、暂停或排队期间捕获和方案修改被阻止并解释。
- `[AC-PLY-CAP-004A]` 遗留会话有界过期释放由 `tests/test_vnext_player_bindings_v6.py` 覆盖；Android Activity 的目的地/滚动恢复已通过 Kotlin 编译与 JVM 聚焦测试，仍待真实设备方向切换、系统回收和选择器返回验收。
- `[AC-PLY-CAP-005]` 图片选择/截取原子导入私有覆盖目录；磁盘满、复制/哈希失败不留下半资源，恢复开发者默认可用。
- `[AC-PLY-CAP-006]` 发布包只携带实际函数与开放字段动作需要的权限/宿主，未开放动作不增加权限或 UI。
- `[AC-PLY-CAP-007]` 字段动作只能由终端用户显式触发；未确认候选和外部内容不进入运行方案、发布包、日志或网络。
- `[AC-PLY-FILE-001]` 读取文件、创建保存文件和选择目录使用不同类型化动作与访问模式，Android 使用 SAF 引用而非伪路径。
- `[AC-PLY-FILE-002]` 文件/目录被移动、删除、撤销授权或 Provider 离线时保留引用并标记不可用，重选后恢复，不伪报成功。
- `[AC-PLY-FILE-003]` 无操作目标方案可使用当前 Player 宿主的文件/目录系统选择器；必填引用在选择前保持 `unset`，系统确认后经二次目的地校验原子回填。Windows 候选的无目标、候选不泄漏路径、确认/revision 单调及取消不写入由 `tests/test_vnext_player_bindings_v6.py`、`tests/test_vnext_player_runtime_api.py` 和 Player 组件测试自动覆盖。Android SDK 34 模拟器已通过真实 DocumentsUI/SAF Provider 验证读取文件、创建保存位置、选择目录、取消/拒绝旧值保持、revision 单调和可读摘要；该证据不替代真机与断线 APK。
- `[AC-PLY-UX-001]` `scripts/create_player_capture_harness.py` 生成签名全字段包。独立 Windows Player 串行验收已验证：方案恢复、目标草稿保存提示、Windows UIA 控件回填、Windows 系统读取文件选择器出现/取消/旧值保持、ADB 真机 `590×1280` 与模拟器 `720×1280` 预检、两者原生捕获层点选并按设备帧坐标回填。证据位于 `output/playwright/player-windows-control`、`output/playwright/player-adb-physical` 与 `output/playwright/player-adb-emulator`。2026-09-03 又在 Android 本机 API 33 真机完成共享 Player、MediaProjection、Accessibility、SAF、断网运行与字段原子回填；该证据与 ADB 宿主证据分开记录，仍不替代非小米设备和生产签名矩阵。
- `[AC-PLY-UX-002]` vNext IDE/Player、发布运行时与原生 Capture 的业务反馈静态禁止 Windows/Browser 默认提示框；系统文件/目录选择、Android 权限/设置和 APK 安装作为系统授权边界单独验收。`tests/test_vnext_feedback_surface_v6.py` 覆盖源码闭包及 Android 字段采集单一反馈源，真实 Windows Player 已验证文件选择器取消后回到原字段且动作恢复，Android 模拟器已验证路径确认后仅出现共享 Player 的 EasyCode 反馈条。
目录函数的唯一验收定义见 [`TEST_HARNESS.md`](../TEST_HARNESS.md) 中 `AC-DIR-001..008`。本文件只把该集合归入 Player、发布与跨平台垂直切片，不复制第二份正文。

| 需求 | 覆盖验收 |
| --- | --- |
| `REQ-DIR-001` | `AC-DIR-001`、`AC-DIR-003` |
| `REQ-DIR-002` | `AC-DIR-002` |
| `REQ-DIR-003` | `AC-DIR-006`、`AC-DIR-007` |
| `REQ-DIR-004` | `AC-DIR-003`、`AC-DIR-004` |
| `REQ-DIR-005` | `AC-DIR-005` |
| `REQ-DIR-006` | `AC-DIR-006` |
| `REQ-DIR-007` | `AC-DIR-001`、`AC-DIR-005` |
| `REQ-DIR-008` | `AC-DIR-008` |

## 5. 本地优先与网络隔离

- `[AC-OFF-PKG-001]` 未声明公网能力的 Windows Bundle 在清空预热缓存、阻断出站公网、关闭 IDE/后端且无 Python 的环境完成固定本地项目。
- `[AC-OFF-AND-001]` 未声明公网能力的 Android APK 在飞行模式、断开数据线并关闭 IDE/后端后完成表单、视觉/OCR、输入、文件、日志和运行状态闭环。
- `[AC-OFF-CLOSURE-001]` 发布包包含 Runtime、函数、Control、资源、OCR 数据、字体/图标、原生库与扩展；缺少任一必需项时发布或本地加载失败，不发生运行期下载。
- `[AC-OFF-CONN-001]` 完全本地项目启动与执行没有公网 DNS/TCP/HTTP；包内 loopback/IPC 单独记录并证明只连接随包组件。
- `[AC-OFF-NET-001]` 显式公网函数覆盖断网、DNS、连接、TLS、鉴权、限流、服务端与超时错误，诊断定位当前语句，普通错误处理后本地步骤可以继续。
- `[AC-OFF-HTTP-FILE-001]` 公网阻断、传输中断或远端错误只让对应上传/下载语句失败；上传内容不进入平台诊断，下载原目标哈希不变，Player 外壳和无关本地任务继续工作。
- `[AC-OFF-MSG-001]` 公网断开但同机/LAN 可达时消息继续工作；协调器、LAN 和收件实例分别产生准确状态，不伪报已读或全局失败。
- `[AC-OFF-UPD-001]` 更新或未来授权端点不可达时不阻止 Player 打开或中断运行/暂停现场；没有已生效强制策略时不阻止新任务，已有且超过宽限期的可信策略继续生效；界面不伪报成功状态。平台不存在自动遥测端点。
- `[AC-OFF-IDE-001]` 本地工具链齐全时 IDE 断网仍能编辑、校验、编译和调试；缺少工具链时报告具体缺失项。
- `[AC-OFF-EXT-001]` 未声明网络权限的扩展外连被阻止或发布失败；声明公网的扩展出现在发布报告且不获得完全离线结论。
- `[AC-OFF-UX-001]` 完全本地任务断网时不显示阻塞性离线错误；连接错误说明公网/LAN/协调器/实例/服务层级、受影响操作和恢复方式。

## 6. Android 本机垂直切片

- `[AC-AND-DEV-001]` Windows IDE 向 USB 连接的真实设备安装或更新测试 APK，并在证据中明确标注 ECIR 由 Android Runtime 执行；普通 ADB 目标测试不能通过此项。
- `[AC-AND-DEV-002]` IDE 能读取 Android 本机结构化日志、运行/实例/目标身份、最后稳定语句和权限诊断；断线只中断调试连接，不让 APK 依赖 IDE 才能继续运行。
- `[AC-AND-CAP-001]` Android Capture Session 在真实手机上完成点、区域、图片与路径采集，结果使用与 IDE 相同的类型契约；不可用动作禁用并解释原因。
- `[AC-AND-CAP-002]` Android 真机覆盖每次 MediaProjection 同意、拒绝、系统停止、锁屏、前后台、旋转和进程终止；旧空间结果不得回填。
- `[AC-AND-CTRL-001]` 只有宿主能生成真实 Accessibility 选择器时才显示控件捕获；无节点、旧节点或宿主不支持返回可诊断结果，不作为全机型硬门。
- `[AC-AND-VIS-001]` Android Runtime 从 MediaProjection 真实帧执行图片与 OCR，正确处理方向变化、尺寸变化、前后台切换和帧权限撤销，不消费旧空间缓存。
- `[AC-AND-INP-001]` Android Runtime 在真实设备完成点击、滑动、拖拽、长按和文本输入；无障碍不可用或动作失败时返回真实错误，不伪报成功。
- `[AC-AND-PERM-001]` MediaProjection、无障碍、通知/前台服务和文件权限的同意、拒绝、永久拒绝、撤销及重启后状态都具有可恢复交互和结构化诊断；同一任务同时缺少多项权限时按需逐项授权，每次返回后重新检查，全部满足前不创建运行，也不遗漏后续权限。
- `[AC-AND-PARITY-001]` 同一受支持 ProgramDocument 在 Windows IDE 调试、Windows/ADB Player 与 Android 本机 Player 中保持项目变量、控制流、纯值计算、超时、取消、日志和 Player 覆盖语义一致；平台不支持项在发布前阻止。
- `[AC-AND-PLY-001]` Android Player 使用同一 Player Schema 与 Control 契约，在小屏、字体放大、横竖屏和系统返回行为下完成配置、校验、运行、暂停、继续与停止。
- `[AC-AND-PKG-001]` 可安装签名 APK 在断开数据线且关闭 IDE、后端后独立启动并执行固定样例项目；AAB 不作为此验收前提。
- `[AC-AND-PKG-002]` APK 不包含 ProgramDocument、可编辑投影、扩展源码、Windows Python、IDE 组件或开发机绝对路径。
- `[AC-AND-BUILD-001]` Android 基础 Runtime 在 API 21 lint 下无不受保护的新 API 调用；项目 `minSdk` 由实际能力闭包自动取最大值，并在函数/扩展契约、签名 lock、密封扩展描述、ECIR 依据、IDE 发布摘要及来源明细、设备加载预检、Gradle 参数和成品 Manifest 间精确一致。API 21 基础与 API 21 扩展不生成重复提级依据；API 23 消息、API 24 触控和一个更高版本扩展样例分别验证可安装边界、发布提示、篡改阻断和更老设备稳定阻止。IDE 的 APK 动作只接受当前工作区，经后端重新发布、派生固定信任根并写入项目 `dist/android`，不得由 Renderer 拼接本地路径。`compileSdk/targetSdk` 固定为 37；正式发布的真实 native 闭包仅为 `arm64-v8a + armeabi-v7a`，`x86_64` 只进入独立开发/模拟器产物。纯 JVM 候选没有 `.so` 时必须报告“架构中立、ABI 未验收”，不得把 `abiFilters` 或假 JNI 当作通过。release 缺失项目外部 keystore/CI secret 时稳定失败且绝不回退到 debug 签名；debug 可重复构建，仓库、APK、构建报告和日志不含正式私钥或口令。
- `[AC-AND-EXT-001]` Android 发布只携带 Manifest 声明且已构建/签名的 Android 兼容扩展变体；Python-only、ABI 不兼容或缺少权限闭包的扩展在发布前被阻止并定位调用。
- `[AC-AND-FILE-001]` 应用私有文件与用户通过 Android 系统选择器授权的外部文件都按类型化引用读写；权限撤销、内容 URI 失效和存储不足返回真实错误。
- `[AC-AND-MSG-001]` Android Player 与同机或局域网实例使用相同消息内容、已读、过期和监听语义；网络切换与离线不损坏本地运行现场。
- `[AC-AND-LIFE-001]` 主动暂停只在同一进程继续；停止、取消或崩溃后重新运行使用新运行 ID 从入口开始，并保留可导出的中断诊断。
- `[AC-AND-REAL-001]` Android 本机发布门使用 Harness 冻结的真实设备/API/分辨率矩阵；替身、桌面模拟器和 ADB 目标测试分别标记，不能计为真机通过。
- `[AC-AND-PERF-001]` Android 真机记录冷启动、运行内存、帧获取、输入延迟、耗电和长时间增长趋势，包含构建、设备、系统、权限、方向、样本与 p50/p95；阈值由基线硬件专题冻结。

### 6.1 当前 Android 候选证据（2026-09-03）

- **自动验证通过**：`:app:testProductionDebugUnitTest` 覆盖 Runtime 控制状态、项目变量/局部值/调用/控制流、纯值 registry v6、逐项运行权限门、`DirectoryReference + relative_path` 能力缩小、私有目录与 SAF 逐段延迟解析，以及递归删除的独立授权和当次执行确认。Python 聚焦测试覆盖签名 Player 包、registry lock/ECIR 一致性、Android 预检、release readiness、ADB 命令边界和禁止厂商专属分支；Android 相关 Vitest 覆盖本机终端动作可见性及 Player/目标 API 接线。
- **自动验证通过**：早期 `productionDebug` 基线曾对同一输入执行两次完整强制重建并得到相同 APK；最新密封真机候选 `app-production-debug-g6-android-generic-v2.apk` 的 SHA-256 为 `c44e811f2cae1295c0ab83229acc5027d681da3af200c609c27c1e266f8ff6cb`，`apksigner` 验证 debug v2 签名，结构扫描证明没有 ProgramDocument、源码或开发密钥，并声明 `arm64-v8a + armeabi-v7a` 原生闭包。候选仍报告 `android_local_contract_status=planned` 和 `delivery_class=debug_candidate`；真实证据未通过受控发布事实进入前，不手改为 verified。
- **自动拒绝通过**：直接 `assembleProductionRelease` 在未提供项目外部 keystore/CI secret 时以 `AND-SIGN-001` 失败；delivery bridge 在当前发布报告没有 `android_local` verified 时以 `android.release_readiness_blocked` 拒绝且不生成 release APK。没有受信 Kotlin/JVM Android 变体的扩展以 `AND-EXT-001` 明确不可用。
- **模拟器交互验证通过**：SDK 34、720×1280 模拟器中的 `emulatorDebug` APK 已真实完成共享 Vue/Control Player、竖横屏、点/区域/图片及 61 点手势路径回填、MediaProjection 拒绝、SAF 读取/保存/目录成功、取消/拒绝保留旧值、滚动位置恢复和应用内单一反馈。共享 Player v7 进一步验证冻结选择页“取消”和 Android 系统返回都重新进入原 Control、保留原坐标并恢复焦点；原生壳与共享页面使用同一暖黑/橙色令牌，证据为 `output/android-local-capture-v4/shared-player-theme-v7.png`、`point-overlay-theme-v7.png`、`point-cancel-return-v7.png` 与 `point-system-back-return-v7.png`。v8/v9 验证旋转不重建共享 WebView，未保存值 `888` 横屏后保持；系统字体 150%/200% 动态变化时未保存值 `999` 保持、正文真实放大、字段和按钮无横向溢出，长表单底部没有被固定运行栏遮挡；MediaProjection 拒绝返回旧字段后，同一动作可以再次拉起系统授权。v10 验证冻结帧期间发生方向变化会拒绝旧坐标空间、回到原字段，并显示“设备方向或显示设置已变化，请重新采集；旧值保持不变”，不再暴露缓存路径。证据为 `rotation-draft-after-v8.png`、`font-scale-150-draft-v9.png`、`font-scale-200-draft-v9.png`、`font-scale-200-long-form-bottom-v9.png`、`projection-deny-return-v9.png`、`projection-retry-dialog-v9.png` 与 `overlay-rotation-feedback-v10.png`。Windows Player 对 Windows 测试窗口、ADB 模拟器和连接手机的当前构建预检分别真实取得 640×420、720×1280 和 590×1280 帧。
- **真机关键切片已验证，完整矩阵待补**：Android 13 / API 33 物理手机已安装 ARM `productionDebug` APK，完成本机 Player、MediaProjection、AccessibilityService 控件、SAF 文件/目录、运行与录制切片。采集返回在真机和 API 34 模拟器上都使用同一标准 API 实现通过，代码不含厂商行为分支。真机又完成 Accessibility 撤销失败与恢复成功、活动默认网络为 `none` 的飞行模式运行、横竖屏数据保持、强制停止后从新入口运行，以及同时缺少 MediaProjection/Accessibility 时逐项授权后才创建运行；4 小时 ARM 长稳正在原子记录。当前两台设备信息都报告 Xiaomi，计划休眠和非小米实体设备仍须单独放行，不能把双 API 证据写成多厂商通过，也不能直接标记整个 `android_local` verified。
- `[AC-AND-GENERIC-001]` Android 产品源码不得包含小米/MIUI 或其他 OEM 的行为分支、私有设置包名和页面坐标；公开设置 Intent 必须先解析并对缺失/启动失败返回应用内结构化原因，Accessibility 返回后等待真实连接。自动检查覆盖厂商标识回归和可选遥测缺失，真实矩阵至少补一台非小米实体设备后才允许宣称 Android 通用通过。

## 7. 网络、配对与计划

- `[AC-NET-HTTP-001]` 真实服务覆盖类型化方法、重复查询、请求头、文本/JSON请求、响应头、重定向和文本响应；Windows/Android 值往返不依赖手写请求脚本。
- `[AC-NET-HTTP-ERROR-001]` `4xx/5xx`、DNS、连接、TLS、代理、超时、取消、响应过大、编码和未授权目标产生可区分结果。
- `[AC-NET-HTTP-SEC-001]` 协议绕过、DNS rebinding、未授权跨范围重定向、敏感头跨源转发和关闭证书校验均被阻止。
- `[AC-NET-HTTP-RETRY-001]` 有副作用请求响应丢失时不自动发送第二次；只有作者在外层异常区域启用策略并确认副作用风险后才产生下一次请求，并可以使用同一业务幂等键。
- `[AC-NET-UPLOAD-001]` 真实服务按原顺序收到文本/文件 multipart 字段、同名字段和一致文件哈希；Windows 与 Android 从可读 `FileReference` 流式上传，峰值内存不随文件大小线性增长。
- `[AC-NET-UPLOAD-FAIL-001]` 引用失效、授权撤销、读取中断、网络断开、取消以及服务端已收到部分上传但响应丢失时，错误定位真实阶段且 Runtime 不自动发送第二请求。
- `[AC-NET-DOWNLOAD-001]` Windows 与 Android 把真实 `2xx` 大文件流式写入临时文件并原子提交到可写 `FileReference`，返回字节数与最终文件哈希一致。
- `[AC-NET-DOWNLOAD-ATOMIC-001]` 预置旧目标后注入非 `2xx`、截断、取消、超限、磁盘满、权限撤销、进程退出和提交失败，旧目标哈希不变且没有可见半文件；不支持原子提交的 Android Provider 在联网前拒绝。
- `[AC-NET-FILE-CLOSURE-001]` 发布报告分别定位网络范围、上传读取和下载写入权限；普通请求拒绝文件/二进制值，缺少函数实现、文件宿主或权限闭包时发布失败且不发生运行期补下载。
- `[AC-NET-LOCAL-TRUST-001]` 同机同用户同一签名产品信任域只自动信任普通消息；跨用户、跨项目、不同签名域、伪造本机身份和远程启动不继承权限。
- `[AC-NET-PAIR-001]` 短期码/二维码在无公网 LAN 完成双向配对；错误、过期、重复、中间人指纹不一致和拒绝均不留下半配对。
- `[AC-NET-REVOKE-001]` 消息、状态和远程启动权限可分别撤销；撤销设备后旧会话、重放与离线队列不能恢复权限。
- `[AC-NET-NOCLOUD-001]` 阻断公网后配对、消息和 LAN 派发按授权工作；抓包没有云端发现、心跳、遥测或公网中继。
- `[AC-SCH-TIME-001]` 虚拟时钟覆盖单次、每日、固定间隔、重启、时区/DST与时钟跳变，同一到期点最多一个 occurrence。
- `[AC-SCH-IDEMPOTENCY-001]` 超时、重复提交、ACK 丢失、协调器/目标重启时，同一 `dispatch_id` 始终返回同一 `run_id`。
- `[AC-SCH-SERIAL-001]` 同一实例在运行、启动、停止和主动暂停时不并发第二任务；不同实例可以独立并行或错峰。
- `[AC-SCH-WIN-001]` Windows 真实宿主完成两个已安装产品、多方案、并行/错峰、登录、锁屏、UAC 与目标占用测试。
- `[AC-SCH-AND-001]` Android 真机只列当前 APK 方案，并覆盖休眠、强制停止、前台服务、权限撤销及计划/实际时间差。

当前证据状态（2026-09-01）：

- `tests/test_vnext_schedule_core_v6.py` 与 `tests/test_vnext_schedule_http_v6.py` 覆盖类型化触发、IANA/DST、revision、不可变 occurrence、错过/重叠、同实例 FIFO、跨实例独立、错峰、SQLite 重启及严格 HTTP；
- `tests/test_vnext_schedule_hub_v6.py` 使用临时签名 `.ecplayer` 和隔离 Hub 数据根，覆盖签名/哈希复验、发布与方案引用、注册表漂移、批次部分失败、数据库故障、重复接纳、重复 ACK、Agent 重启复用 `run_id`，并把无目标固定样例交给普通 Player Runtime 执行到终态；
- `frontend/src/vnext/__tests__/VNextScheduleWorkspace.test.ts`、TypeScript 和 ESLint 覆盖 API 承接的计划中心空态、Agent 操作与区域导航；应用外壳接线后仍须执行真实浏览器流程；
- 当前 Windows 主机已使用临时、唯一任务名完成 Task Scheduler 安装、读取和卸载安全冒烟，清理成功；交互会话探测完成只读冒烟。这些只计为对应宿主步骤通过，不等同于完整 `AC-SCH-WIN-001`；
- `tests/test_vnext_lan_control_v6.py` 在 Windows loopback 使用真实 TCP/UDP 与 spawn 双进程覆盖稳定身份、发现/手工地址、短期码、二维码载荷、响应认证、指纹固定、加密双向认证、半连接、重放、三项独立权限、撤销、可靠多收件消息、重启补发、过期、未授权立即失败和远程 dispatch 幂等；测试结束会停止监听并回收子进程；
- 两个真实安装产品的窗口/ADB 批次、真实第二台电脑、防火墙放行/阻断、睡眠唤醒、锁屏、UAC、目标占用仍未验证。当前出站守卫证明自动用例只连接 loopback/private 地址，但不等同于操作系统级公网抓包；`AC-NET-NOCLOUD-001` 的真实抓包与 `AC-SCH-AND-001` 仍不能标记完整通过。

## 8. 在线更新

- `[AC-UPD-DISABLED-001]` 更新关闭时无端点、调度器、网络请求或入口，现有版本离线运行。
- `[AC-UPD-OFFLINE-001]` 更新服务、DNS、TLS、超时或服务端失败不影响现有版本，不伪报“已是最新”。
- `[AC-UPD-SIGN-001]` 签名/哈希错误、旧清单重放、回退、错误目标和混搭产物被拒绝。
- `[AC-UPD-ATOMIC-001]` 下载、磁盘、进程或切换中断不形成半版本，当前或上一完整版本可启动。
- `[AC-UPD-RUN-001]` 活动或暂停任务固定 `release_id`，只允许暂存，安全边界前不切换。
- `[AC-UPD-ROLLBACK-001]` 启动/加载失败恢复上一正常版本，业务执行失败不触发更新回滚。
- `[AC-UPD-PROFILE-001]` 运行方案按稳定 Control 保留或明确要求检查，不静默清空或替换。
- `[AC-UPD-MULTI-001]` 多实例共用下载和协调切换，不并发覆盖活动目录。
- `[AC-UPD-WIN-001]` Windows 内容与应用更新在真实 Bundle 和安装助手通过。
- `[AC-UPD-AND-CONTENT-001]` Android 内容包在应用私有槽验证并切换，不触发 APK 安装。
- `[AC-UPD-AND-APK-001]` Android APK 更新在真机覆盖系统确认、取消、失败与数据保留。
- `[AC-UPD-SCALE-001]` 错峰、缓存、续传、退避和请求数据审计通过规模测试。
- `[AC-UPD-HOSTED-001]` 官方托管从作者登录、上传、通道推广、配额/审计到真实客户端下载形成闭环，服务失败不影响现有运行。
- `[AC-UPD-SELFHOST-001]` 同一发布可部署到标准 HTTPS 静态 Feed/对象存储，并保持相同客户端语义。
- `[AC-UPD-PORTABLE-001]` 签名源迁移与镜像变更通过，未签名 URL 或信任根变化拒绝。
- `[AC-UPD-CREDENTIAL-001]` 私钥与上传凭据不泄漏到任何项目、发布、日志或诊断产物。
- `[AC-UPD-QUOTA-001]` 托管配额失败只影响新发布，不影响现有 Player，且不伪装成授权失败。
- `[AC-UPD-REQUIRED-001]` 可选更新可延后；强制策略只在宽限后阻止旧版本新开任务。
- `[AC-UPD-ACTIVE-001]` 运行或暂停现场不被到达/生效的强制策略中断，结束后的新任务受约束。
- `[AC-UPD-POLICY-001]` 策略签名、重放、防时钟回拨和缓存清理边界通过故障注入。
- `[AC-UPD-PLATFORM-001]` 缺少任一平台兼容产物时不能发布覆盖该平台的强制策略。
- `[AC-UPD-LOCKED-001]` 更新无法完成时只阻止新任务，Player 维护与诊断能力保持可用。
- `[AC-UPD-CONTROL-001]` 普通检查、下载和应用偏好分别控制对应行为、跨版本保留且不被作者发布重置；手动检查不重开其他自动化。
- `[AC-UPD-POLICY-CHECK-001]` 关闭普通检查后只保留已披露的签名强制策略请求，不取得或安装产物。
- `[AC-UPD-GRACE-001]` 强制策略宽限期允许用户择时更新，宽限结束只阻止新任务。
- `[AC-UPD-CONTROL-POLICY-001]` 已验证强制策略不可被普通设置或本地清理绕过；未取得策略的客户端不猜测。
- `[AC-UPD-AUTHOR-OFF-001]` 作者关闭更新的发布没有终端更新 UI、端点或请求。
- `[AC-UPD-ROLLOUT-ID-001]` 产品域随机分组码跨升级保留、跨产品隔离且不包含硬件或账号身份。
- `[AC-UPD-ROLLOUT-PRIVACY-001]` 请求不上传原始分组码或运行数据，Feed 白名单只含哈希。
- `[AC-UPD-ROLLOUT-BUCKET-001]` Windows/Android 对固定输入得到相同确定性分桶。
- `[AC-UPD-ROLLOUT-MONOTONIC-001]` 扩大比例时原命中集合完整保留且产物不变。
- `[AC-UPD-ROLLOUT-WHITELIST-001]` `0%` 只对白名单提供更新，非法与重复代码拒绝。
- `[AC-UPD-ROLLOUT-PAUSE-001]` 暂停、离线延迟收束、未应用暂存包和已安装版本的行为符合契约。
- `[AC-UPD-ROLLOUT-RESUME-001]` 继续、扩大和全量不重新分桶或重建产物。
- `[AC-UPD-ROLLOUT-FORCE-001]` 未全量的可选发布不能成为强制最低版本。
- `[AC-UPD-ROLLOUT-NOTELEMETRY-001]` 无运行遥测、伪安装指标或自动服务端回滚。
- `[AC-UPD-ROLLOUT-LOCAL-ROLLBACK-001]` 本地启动健康恢复不改变服务端灰度。
- `[AC-UPD-ROLLOUT-AUDIT-001]` 所有灰度策略变化有单调 revision 和完整作者审计。
- `[AC-UPD-ROLLOUT-STATIC-001]` 官方与静态自建 Feed 对同一输入产生相同结果。
- `[AC-UPD-ROLLOUT-UX-001]` 作者和终端状态只展示真实可知信息。
- `[AC-UPD-TEST-CHANNEL-001]` 普通稳定 Player 无通道选择器；只有作者把项目测试分组码加入白名单后才取得测试发布，移除后已安装版本不降级。
- `[AC-UPD-TEST-PROMOTE-001]` 同一不可变测试产物推广到稳定白名单、百分比和全量时哈希/签名不变，终端无需修改通道设置。
- `[AC-UPD-NODEVICE-CLOUD-001]` 托管抓包与存储审计证明无终端心跳、在线设备、运行/崩溃/截图数据；作者端无云端设备舰队或伪在线数。

### 8.1 当前发布签名证据（2026-09-01）

- **自动验证通过**：`.ecplayer` format 2 的 Ed25519 签名、规范化完整性清单、所有归档文件大小/SHA-256、重复路径、未签名夹带文件、无签名旧包、篡改 ECIR/表单/目标/资源、替换公钥和固定信任根不匹配均有直接测试。
- **自动验证通过**：作者私钥文件保存在项目外，并由当前 Windows 用户 DPAPI 保护；发布结果、清单、签名元数据、交付目录和公开信任根只携带公钥与指纹。
- **自动验证通过**：Publisher 在原子替换上次产物前使用 Loader 自验临时归档；Windows Distribution 组装公开信任根并在启动参数中强制使用，错误信任根无法加载。
- **自动验证通过**：IDE 发布窗口只消费真实发布检查与运行时就绪结果；存在错误时禁用交付，运行时模板缺失时仍允许生成有效签名 `.ecplayer`，但禁用并解释“独立 Player”。
- **未验证**：真实 PyInstaller 通用 Runtime 与独立 Windows Player 已在当前宿主通过，但生产 Authenticode、无开发工具的干净 Windows 客户机仍未验证；Android debug 候选 APK 已在 API 33 真机安装并完成无活动默认网络的离线运行，但正式 keystore、非小米实体设备和完全拔线客户环境仍按 6.1 节阻塞。本节不能替代对应真实宿主与更新 Harness。

### 8.2 v6 在线更新实现证据（2026-09-03）

- **自动验证通过**：`tests/test_vnext_updates_v6.py` 覆盖 Ed25519 角色阈值、根与在线密钥轮换、篡改/混搭/过期/重放/降级拒绝、不可变静态 Feed、ETag/HEAD/Range、5xx、部分下载、最终大小与哈希、磁盘失败、A/B 切换与健康回滚、进程租约安全点、关闭时零传输与零身份、产品域隔离分组码、百分比分桶、白名单、暂停/继续/单调扩大、强制策略和时钟回拨。
- **自动验证通过**：`tests/test_vnext_update_api_v6.py` 覆盖作者配置、静态源初始化和关闭域拒绝；`tests/test_vnext_distribution_v6.py` 覆盖关闭更新时 Bundle 不含端点或更新配置，以及启用后签名配置、固定信任根、项目内容 `release_id` 一致性和交付目录强制携带独立 Windows 更新助手。`tests/test_vnext_windows_update_helper_v6.py` 覆盖严格 ZIP 文件清单、未登记成员拒绝、安装根与启动入口约束、同盘暂存、健康探针、最终回执、失败目录隔离和旧目录恢复。TypeScript 与 Player 组件测试覆盖应用内安装确认和等待退出说明。
- **自动验证通过**：策略独立检查不会取得目标或产物；任务开始固定不可变 `release_id`，超过可信宽限只阻止新任务；参考 Feed 服务不写数据、不接收运行心跳、日志、截图、崩溃、任务结果、原始分组码或硬件身份。
- **真实 Windows 宿主通过（开发签名候选）**：冻结的 `EasycodeUpdateHelper.exe` 已对真实目录完成成功换版和故意损坏新版回滚；完整约 460 MB PyInstaller Player 已完成严格打包、同卷暂存、整目录替换、新 `EasycodePlayer.exe` 启动、本地 API 健康回执、签名 `.ecplayer` 加载以及上一目录保留。证据与可重复 Harness 位于 `output/g7-windows-application-update`、`output/g7-windows-application-rollback`、`output/g7-windows-real-player-update` 和 `.tmp/g7_windows_*`。生产 Authenticode 签名及干净无 Python 客户机仍未验证，因此不能把开发候选表述为正式安装包放行。
- **Android 模拟器真实通过**：SDK 34 x86_64 模拟器已完成签名 HTTPS 内容更新、应用私有内容槽切换、重启保持；APK 已完成 v1→v2 与 v2→v3 的系统 PackageInstaller 确认、5 MiB 中断后的 Range 续传、整包哈希验证、进程替换后的状态认领，以及用户取消时旧 versionCode 保持和可重试暂存。启用更新时持久 JobScheduler 完成一次真实后台检查；关闭更新的 APK 不注册任务且不声明安装权限。证据位于 `output/g7-android-content-update-v2`、`output/g7-android-apk-update`、`output/g7-android-apk-resume-update` 与 `output/g7-android-no-update`。模拟器不计 Android 真机通过。
- **未验证**：Windows 生产代码签名/安装器和干净客户机；Android 真实手机的内容槽、PackageInstaller、ARM ABI、空间不足和断线升级；外部生产 HTTPS 对象存储/CDN、规模错峰与长时故障注入。
- **环境阻塞**：官方托管尚无真实账号、对象存储/CDN、配额与审计基础设施，入口继续明确不可用；Android 候选 APK 的安装阻塞已消除，API 33 真机与 API 34 模拟器基础运行已通过，但生产签名、非小米实体设备及真机长稳矩阵仍缺少完整环境。

### 8.3 IDE 外壳与快捷键实施证据（2026-09-04）

- `[AC-IDE-SHELL-001]` 顶部 `项目 / 编辑 / 视图 / 运行 / 帮助` 菜单只分发已有真实命令；禁用项原位给出原因，菜单同步展示当前有效快捷键。
- `[AC-IDE-SHORTCUT-001]` 快捷键使用稳定命令 ID，当前用户设置由 `/api/vnext/ide-settings` 原子保存；前后端共同拒绝冲突组合，支持搜索、录入、清除与恢复默认，不进入项目或发布包。
- `[AC-IDE-PANELS-001]` 函数库、语句检查器和问题/日志面板使用同一可访问分隔条，支持指针、方向键、Home 重置及项目视图状态往返；窄屏不写坏桌面尺寸。
- **自动验证通过**：UI-18 冻结基线为前端 105 个测试文件、537 项通过；TypeScript 类型检查、ESLint、IDE 构建和 Player-only 构建通过。后端统一基线为 1,303 项通过、2 项按平台跳过；命令、快捷键设置、跨层级剪切/粘贴、提取项目函数、搜索跳转和布局状态均由对应垂直切片承接。
- **真实浏览器人工验证通过**：UI-1 至 UI-18 已覆盖 360、412、600、700、900、1024、1280 和 1440 像素代表性尺寸、八个工作区、Player 页面以及 1,001 函数/10,000 语句/10,000 资源大项目。顶部菜单、全局命令搜索、快捷键、可调面板、窄屏抽屉、帮助/菜单弹层、焦点恢复和任务化布局均已走通；最终 600px 命令面板证据为 `output/playwright/ui18-command-palette-opaque-600.png`，完整迭代记录见 `docs/vnext/UI_ROADMAP.md`。
- **冻结判定**：当前 IDE UI 已完成并冻结，不再保留“旧后端 404”或“待统一候选重启”的历史描述。G16 Windows Player 与 Android `productionDebug` 均重新嵌入冻结后的共享 Player Web；Android 当前 UI 已在 API 34 模拟器和 API 33 物理手机安装启动复核。平台功能仍严格引用各自真实宿主证据，浏览器布局检查不替代原生运行验证。

## 9. 性能与环境矩阵

- 普通结构命令一帧内反馈；局部 Schema 校验 `<50ms`，跨函数语义校验 `<200ms`。
- 10,000 条结构化语句打开后 `<1s` 可交互；1,000 个函数检索 `<100ms`；10,000 个资源验证虚拟化与懒加载。
- 空闲 CPU 接近 0；未启用扩展不启动 Worker 或扫描；运行热路径不跨 HTTP/WebView。
- 覆盖 Windows 10/11、100%/125%/150%/200% DPI、至少一个模拟器和 ADB 配置，以及 IDE、Windows Player、Android Player、桌面 Capture 和 Android Capture 的生产构建。
- Android 本机必须使用真实设备验证启动、内存、帧获取、输入延迟、方向变化、前后台切换、持续运行和电量影响。替身、桌面模拟器或 Windows Runtime 的 ADB 操作都不能替代真机结果；具体设备/系统版本矩阵由 Harness 基线冻结。
- 报告必须区分自动验证通过、人工验证通过、未验证、失败和环境阻塞；一次性通过数量不写入长期规格。
