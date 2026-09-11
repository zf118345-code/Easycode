# 函数系统

状态：`Approved`（官方 v1 完整最小目录、稳定 ID、原子/标准分层、结果类型和宿主/目标矩阵已冻结）

最近修订：2026-09-01

## 1. 用户可见分类

函数库只向脚本制作者展示以下三类来源；检索与分组优先使用“图像、文字、输入、等待、文件”等用途，不要求用户理解实现层级。

| 类别 | 用户能力 | 编辑边界 |
| --- | --- | --- |
| 官方函数 | EasyCode 随产品提供的通用能力 | 可查看契约与组合定义，不可修改或删除官方版本 |
| 项目函数 | 当前项目用 ProgramDocument 组合的业务流程 | 可创建、编辑、引用、重命名和删除 |
| 扩展函数 | 项目级或用户级 Python/原生实现 | 在 EasyCode 审核契约，在外部 IDE 维护实现 |

所有函数都通过同一方式插入 `call` 语句，并由右侧检查器编辑类型化参数和返回绑定；不再存在“调用能力节点”或另一套扩展调用入口。

## 2. 内部实现分层

| 内部层级 | 实现 | 约束 |
| --- | --- | --- |
| 原子函数 | Python、Kotlin、C++ 或平台驱动 | 不可再由现有原子函数表达的最小查询、动作或平台事务 |
| 标准函数 | ProgramDocument 组合，必要时带等价融合实现 | 官方高频组合，优先只依赖原子函数 |
| 项目函数 | ProgramDocument 组合 | 当前项目业务逻辑，可依赖所有已启用函数 |
| 扩展函数 | Python、Kotlin、C++ 或受控原生实现 | 项目或第三方复杂算法、协议与领域能力 |

- 候选能力若只是另一个原子函数的参数变体，应扩展原函数的类型化参数或模式，不新增同义函数。
- 能由原子函数和结构化控制语句组合出的高频能力属于标准函数。性能敏感的标准函数可以编译为融合实现，但参数、返回、取消、错误和日志语义必须通过等价性测试。
- 条件、循环、异常区域、`target_scope` 和监听声明属于 ProgramDocument 结构与运行机制，不进入函数库计数；不同事件源不得复制调度语义。
- 原子与标准只用于内部治理。普通函数库不以“原子/标准”分栏，避免实现方式压过用户用途。

“最小核心”和“易用函数库”是两个边界：运行核心只保留不可由现有原语表达的能力，官方函数目录则可以收录经过筛选的高频标准组合。标准函数候选至少满足：已能由现有结构表达、在多个真实项目中重复出现、显著减少易错样板、具有清晰单一语义，并能对组合定义和任何融合实现运行等价性 Harness。只服务单个项目、单个游戏或特殊算法的组合不得因此进入官方目录。

## 3. 函数契约

每个函数契约至少包含稳定 `function_id`、命名空间、显示名、版本、类型化参数、一个逻辑返回 Schema、副作用、权限、平台、所需能力、网络级别（无网络/本机或局域网/公网）、超时、取消、幂等、稳定异常 ID、异常的 `transient / permanent` 重试分类、摘要模板、测试和最低运行时版本。未知异常默认不可重试。多项相关输出组成带稳定 `field_id` 的命名记录；只有“有值 / 无值”的正常结果使用 `optional<T>`，不得以空记录或伪造坐标表示无结果。

摘要模板是版本化函数契约的一部分，并由服务端确定性投影为 `statement_summary.schema_version + parts`。固定文字与参数槽分别传输；参数槽使用稳定 `parameter_id`、语义角色和 `presentation = auto`，值仍只来自 ProgramDocument。官方、项目和扩展函数不得向中央编辑区注入 HTML、CSS 或私有组件。扩展可以省略摘要模板，此时只显示规范函数名；模板只能引用本函数已声明参数，未知参数使契约校验失败。摘要只决定中央流程需要的基础语义，不改变右侧完整参数、编译、运行或 Player 契约。

### 3.1 名称、默认值与平台矩阵

- 规范显示名统一为 `命名空间.动作`。中文同义词、历史名称和自然语言描述只进入搜索别名与帮助，ProgramDocument、Player Schema、ECIR、日志关联和迁移只使用稳定 ID。
- 只有跨项目、跨目标仍然安全且语义稳定的参数可以拥有默认值。图片、文件/目录路径、目标、窗口选择器、实例和其他不能可靠猜测的必填项使用 `unset`；插入时不得从当前选中资源、上次填写值或当前调试目标静默推断。
- 契约逐函数声明 Windows、ADB、Android 本机与无目标场景，并使用“支持 / 条件支持 / 不支持”表达权限或宿主前提。编辑检查、编译、发布和运行前必须消费同一矩阵；只写“支持 Android”不构成有效契约。
- 每个平台条目同时保存两个正交结论：`support = supported / conditional / unsupported` 描述产品契约，`implementation = verified / planned` 描述当前实现证据。`conditional` 必须列出稳定 `required_capabilities`；`verified` 只能由对应宿主/目标 Harness 证据产生。旧 `implementation_state` 只由“是否至少存在一个 verified 平台”派生，旧宿主与目标字段只作为矩阵生成兼容输入，不参与编译、目录或发布的第二次判断。
- 可插入目录只包含至少一个平台已验证的函数，并返回 `verified_platforms` 与完整 `platform_support`。未指定目标平台时，ProgramDocument 可以保存、编辑和检查全部契约；Compiler 生成 ECIR 时只声明依赖闭包共同拥有的 verified 平台。指定平台编译、发布或运行时，`unsupported` 与 `planned` 都在运行前阻止，分别报告“不支持”和“尚未验证”；条件能力继续进入 ECIR/发布闭包并由目标能力快照检查。
- 当前自动证据只覆盖 Windows 宿主、该宿主操作的 ADB 目标和 Windows 无目标实例。任何纯函数、目标函数或文件函数不得由共享 Python 实现推断为 Android 本机已验证；Android 本机条目在签名 APK 脱离 IDE/后端通过真机 Harness 前保持 `planned`。

### 3.2 契约版本与项目锁

- 每个函数声明稳定 `function_id`、语义化 `contract_version` 和由规范化行为字段计算的 `contract_fingerprint`。行为字段至少覆盖参数/默认值、返回、正常空结果、异常、副作用、权限、平台、超时、取消和幂等语义。
- 项目在 `easycode.lock` 中记录所引用函数的精确契约版本与指纹。发现本机注册表版本不同或指纹漂移时，IDE 保持原锁并停止编译，不用当前安装版本静默替换。
- 兼容增加与实现修复可以保留同一主版本，但更新项目锁仍需开发者确认。删除参数、改变输入/返回类型、改变正常结果与异常边界、改变副作用/权限/平台或改变既有默认行为属于破坏性变化，必须发布新主版本。
- 迁移前展示受影响的 ProgramDocument 调用、Player 绑定、目标平台和发布闭包；确认后以一个可撤销项目事务同时更新结构与锁。取消、失败或验证不通过时，旧项目继续使用原契约构建。
- 弃用只改变新项目推荐与目录提示，不删除已有项目所需的兼容构建产物。官方标准函数只有在多个相互独立的真实项目中证明高频、减少易错样板并通过等价性 Harness 后，才能从候选提升为正式官方函数。

网络级别描述真实实现路径，不由显示名猜测。Compiler 根据被引用函数与扩展实现生成发布报告；显式 LAN/公网函数的连接失败沿用函数错误契约，不能形成 Runtime 全局离线错误。首版把普通文本/JSON HTTP 请求、multipart 文件上传和文件下载冻结为三个独立原子能力：普通请求只返回文本响应；上传从可读 `FileReference` 流式发送明确字段；下载先流式写临时文件再原子提交到可写 `FileReference`。文件字节不进入 ProgramDocument、项目变量或普通日志，也不通过万能正文 Control 暴露。ProgramDocument 异常区域重试缺省关闭；作者显式开启且区域包含 HTTP/上传等副作用时必须确认远端可能已经收到上一请求，并优先使用业务幂等键。浏览器 DOM、网页会话接管、验证码、任意二进制流与断点续传协议不属于这些原子能力，完整边界见 [`NETWORK.md`](NETWORK.md)。

官方 v1 函数清单必须逐项声明 Windows、ADB 与 Android 本机支持情况和目标能力，不允许只写笼统的“Android”。跨平台函数在不同实现上保持同一参数、返回、超时、取消、错误和日志语义；Windows UIA 等平台专属函数可以不支持 Android，但 IDE 检查与 Android 发布必须在运行前阻止并定位全部调用。首个正式版本至少要求图像/OCR、输入、等待、日志、变量/集合、文件、消息、类型化 HTTP/API 与 HTTP 文件传输所需原子能力在 Android 本机形成闭环。

插入函数时，Program Service 根据契约创建合法 `call` 骨架：有默认值的字段写入类型化默认值；无默认值的必填字段写入可定位的 `unset` 值。缺失字段会产生语义诊断并阻止运行和发布，但不会形成不可解析草稿。重命名、移动和删除前必须按稳定 ID 查询 ProgramDocument、Player Schema 与其他扩展引用。

官方函数显示名与稳定 ID 以第 5 节为准；别名和帮助文案可以改进，但不能进入持久化身份或形成第二个同义函数。

## 4. 扩展函数开发与发布

项目扩展位于 `extensions/<package>/`，共享扩展位于用户级扩展目录。两者发现后以普通函数契约进入同一函数库；实现来源只在扩展维护界面展示。

EasyCode 负责创建骨架、导入、契约审核、测试、启停、引用分析和发布检查。Python/原生实现使用 PyCharm、VS Code 或其他外部 IDE 编写，EasyCode 不再内置另一套扩展代码编辑器。扩展在故障隔离 Worker 中执行；超时、异常或崩溃不得拖垮 IDE，也不得伪报成功。该 Worker 不构成恶意代码安全沙箱，可执行扩展仍按 [`EXTENSIONS.md`](EXTENSIONS.md) 作为可信本地代码审批。

依赖检查必须区分：

- 当前开发环境未安装的依赖；
- 已安装但未进入 Player 交付闭包的依赖；
- 实现中使用但 Manifest 未声明的依赖。

额外 Python 包随扩展放入其隔离依赖目录。平台已冻结的 OpenCV、NumPy、Pillow、PyAV、OCR 和 Windows 运行模块可以直接声明。任何缺失或未封闭依赖都会阻止发布，不能在开发机成功后到客户机静默失败。

Android 发布只能使用函数契约声明的 Android 驱动实现或已构建 Kotlin/JVM、C++/NDK 扩展变体。只有 Python/Windows 实现的函数仍可在 Windows/ADB Player 使用，但引用它的项目不能发布 Android APK，直到调用被移除或提供等价 Android 变体。

任何项目函数都可以由开发者显式加入 Player 按钮。首版在任务运行期间禁用函数按钮，只允许空闲时启动，避免把未实现的并发策略伪装成可选功能。

## 5. 官方 v1 完整最小目录

全部官方函数首个契约版本为 `1.0.0`。`A` 表示原子函数，`S` 表示由 ProgramDocument 组合的标准函数；该标记只用于实现和等价性治理，不在普通函数库中分栏。表中稳定 `function_id` 不随中文显示名、分类或别名改变。

宿主代码：`W` 为 Windows Runtime，`A` 为 Android 本机 Runtime，`W/A` 为两者。目标能力为 `none` 时不要求操作目标；其他能力必须由当前或显式引用目标声明，并在编辑、编译、发布和运行前使用同一能力注册表校验。

### 5.1 基础、目标、应用与窗口

| 显示名 | `function_id` | 层级 | 主要输入 → 返回 | 宿主 | 目标能力 |
| --- | --- | --- | --- | --- | --- |
| `日志.输出` | `official.log.output` | A | 内容、级别 → `void`；内部分类由宿主生成 | W/A | `none` |
| `等待.持续` | `official.wait.duration` | A | 持续时间 → `void` | W/A | `none` |
| `等待.直到` | `official.wait.until` | A | 时间点 → `void`；已过时等待下一次到达 | W/A | `none` |
| `时间.现在` | `official.time.now` | A | 时区 → `datetime` | W/A | `none` |
| `时间.今天` | `official.time.today` | A | 时区 → `date` | W/A | `none` |
| `随机.整数` | `official.random.integer` | A | 最小值、最大值 → `int64` | W/A | `none` |
| `项目.数据目录` | `official.project.data_directory` | A | 访问模式 → `DirectoryReference` | W/A | `none` |
| `剪贴板.读取文本` | `official.clipboard.read_text` | A | 无 → `optional<string>` | W/A | `host.clipboard` |
| `剪贴板.写入文本` | `official.clipboard.write_text` | A | 文本 → `void` | W/A | `host.clipboard` |
| `目标.等待在线` | `official.target.wait_online` | S | 目标引用、超时 → `optional<TargetInfo>` | W/A | `target.registry` |
| `目标.读取状态` | `official.target.read_status` | A | 目标引用 → `TargetInfo` | W/A | `target.registry` |
| `目标.获取画面` | `official.target.capture_frame` | A | 当前目标 → `FrameReference` | W/A | `frame.read` |
| `画面.保存` | `official.frame.save` | A | 文件、可选画面、可选裁剪区域、格式、质量 → `FileReference` | W/A | `frame.read`、`filesystem` |
| `颜色.读取` | `official.color.read` | A | 坐标、可选画面 → `Color` | W/A | `frame.read` |
| `颜色.查找` | `official.color.find` | A | 颜色、容差、可选区域、可选画面 → `optional<Point>` | W/A | `frame.read` |
| `应用.启动` | `official.application.start` | A | `ApplicationReference`、参数 → `ApplicationRunReference` | W/A | `application.launch` |
| `应用.等待退出` | `official.application.wait_exit` | A | `ApplicationRunReference`、超时 → `optional<ApplicationExitResult>` | W | `application.lifecycle` |
| `应用.是否运行` | `official.application.is_running` | A | `ApplicationRunReference` → 布尔 | W | `application.lifecycle` |
| `应用.停止` | `official.application.stop` | A | `ApplicationRunReference`、退出等待 → 布尔 | W | `application.lifecycle` |
| `窗口.查找` | `official.window.find` | A | `WindowSelector` → `optional<WindowReference>` | W | `window.uia` |
| `窗口.等待出现` | `official.window.wait_visible` | S | `WindowSelector`、超时 → `optional<WindowReference>` | W | `window.uia` |
| `窗口.获取当前目标窗口` | `official.window.current` | A | 当前 Windows 目标 → `WindowReference` | W | `window.uia` |
| `窗口.激活` | `official.window.activate` | A | `WindowReference` → `bool` | W | `window.uia` |
| `窗口.关闭` | `official.window.close` | A | `WindowReference` → `bool` | W | `window.uia` |
| `窗口.读取状态` | `official.window.read_status` | A | `WindowReference` → `WindowStatus` | W | `window.uia` |
| `窗口.移动` | `official.window.move` | A | `WindowReference`、坐标 → `bool` | W | `window.manage` |
| `窗口.调整大小` | `official.window.resize` | A | `WindowReference`、客户区尺寸 → `bool` | W | `window.manage` |
| `窗口.确保完整可见` | `official.window.ensure_visible` | A | `WindowReference` → `bool` | W | `window.manage` |
| `窗口.改变显示状态` | `official.window.set_display_state` | A | `WindowReference`、还原/最小化/最大化 → `bool` | W | `window.manage` |

`应用.启动` 不接受 Shell 文本、PowerShell、命令解释器或脚本宿主。Windows 变体只启动获得 `execute` 授权的明确 `.exe`，参数以 `shell = false` 的参数数组传入；Windows→ADB 变体只启动明确 Android 包/Activity，首版不接受自由启动参数。只填包名时由 Android 包管理器解析 Launcher Activity，再以固定参数启动，不依赖可能被云机裁剪的 `monkey`。未来需要 Intent extras 时必须增加强类型键、类型和值契约，不能把文本拼入 `adb shell`。Android 本机通过显式 Intent 启动已批准应用，并以 `MAIN + LAUNCHER` 查询支持 Android 11+ 的普通启动器应用可见性，不申请全包枚举权限。`应用.等待退出` 仅支持 Windows 精确进程；`应用.是否运行 / 停止` 支持 Windows 精确进程及 Windows 宿主当前 ADB 目标中的已校验包名。Android 本机没有权限可靠停止或观察任意第三方应用进程，因此在插入、编译和 APK 预检前阻止，不能把“已不在前台”伪报为进程退出。

### 5.2 视觉、文字、输入与控件

| 显示名 | `function_id` | 层级 | 主要输入 → 返回 | 宿主 | 目标能力 |
| --- | --- | --- | --- | --- | --- |
| `图像.查找` | `official.image.find` | A | 图片、区域、相似度、可选帧 → `optional<ImageMatch>` | W/A | `frame.read` |
| `图像.查找全部` | `official.image.find_all` | A | 图片、区域、相似度、上限、可选帧 → `list<ImageMatch>` | W/A | `frame.read` |
| `图像.等待出现` | `official.image.wait_visible` | S | 图片、区域、相似度、超时 → `optional<ImageMatch>` | W/A | `frame.read` |
| `图像.等待消失` | `official.image.wait_hidden` | S | 图片、区域、相似度、超时 → `bool` | W/A | `frame.read` |
| `图像.点击一次` | `official.image.click_once` | S | 图片、区域、相似度、点击设置 → `optional<ImageMatch>` | W/A | `frame.read + input.point` |
| `图像.点击直到消失` | `official.image.click_until_hidden` | S | 图片、区域、相似度、点击设置、超时 → `ImageClickResult` | W/A | `frame.read + input.point` |
| `图像.点击位置直到出现` | `official.image.click_position_until_visible` | S | 点击位置、等待图片、区域、相似度、点击设置、超时 → `ImageClickConditionResult` | W/A | `frame.read + input.point` |
| `图像.点击位置直到消失` | `official.image.click_position_until_hidden` | S | 点击位置、等待图片、区域、相似度、点击设置、超时 → `ImageClickConditionResult` | W/A | `frame.read + input.point` |
| `文字.识别` | `official.text.recognize` | A | 区域、语言、预处理、可选帧 → `OCRResult` | W/A | `frame.read` |
| `文字.匹配` | `official.text.match` | S | 目标文字、匹配模式、区域、语言 → `optional<OCRResult>` | W/A | `frame.read` |
| `文字.等待出现` | `official.text.wait_visible` | S | 目标文字、匹配模式、区域、语言、超时 → `optional<OCRResult>` | W/A | `frame.read` |
| `输入.点击` | `official.input.click` | A | 坐标、按钮、次数、保持时间、间隔 → `void` | W/A | `input.point` |
| `输入.输入文本` | `official.input.type_text` | A | 文本、输入模式 → `void` | W/A | `input.text` |
| `输入.滚动` | `official.input.scroll` | A | 方向、距离/滚轮量、次数、惯性模式 → `void` | W/A | `input.scroll` |
| `输入.拖拽` | `official.input.drag` | A | 路径、移动时长、缓动 → `void` | W/A | `input.drag` |
| `输入.按键` | `official.input.key` | A | 键、动作、保持时间 → `void` | W/A | `input.key` |
| `输入.移动指针` | `official.input.move_pointer` | A | 坐标、移动时长 → `void` | W | `pointer.move` |
| `控件.查找` | `official.control.find` | A | `ControlSelector` → `optional<ControlReference>` | W/A | `control.semantic` |
| `控件.等待出现` | `official.control.wait_visible` | S | `ControlSelector`、超时、间隔 → `optional<ControlReference>` | W/A | `control.semantic` |
| `控件.等待消失` | `official.control.wait_hidden` | S | `ControlSelector`、超时、间隔 → `bool` | W/A | `control.semantic` |
| `控件.点击` | `official.control.click` | A | `ControlReference`、调用模式 → `bool` | W/A | `control.semantic` |
| `控件.按选择器点击` | `official.control.click_selector` | A | `ControlSelector`、调用模式 → `bool` | W/A | `control.semantic` |
| `控件.读取文本` | `official.control.read_text` | A | `ControlReference` → `string` | W/A | `control.semantic` |
| `控件.输入文本` | `official.control.type_text` | A | `ControlReference`、文本、模式 → `void` | W/A | `control.semantic` |
| `控件.读取状态` | `official.control.read_status` | A | `ControlReference` → `ControlStatus` | W/A | `control.semantic` |
| `控件.聚焦` | `official.control.focus` | A | `ControlReference` → `bool` | W/A | `control.semantic` |
| `控件.设置值` | `official.control.set_value` | A | `ControlReference`、值 → `bool` | W/A | `control.semantic` |
| `控件.选择项目` | `official.control.select` | A | 项目 `ControlReference` → `bool` | W/A | `control.semantic` |
| `控件.切换开关` | `official.control.toggle` | A | `ControlReference` → `bool` | W/A | `control.semantic` |
| `控件.滚动到控件` | `official.control.scroll_into_view` | A | `ControlReference` → `bool` | W/A | `control.semantic` |

普通图像/OCR调用没有显式帧时取得调用开始后的当前目标新帧；同一 `FrameReference` 必须分析相同像素。`文字.匹配` 的匹配模式固定为 `exact / contains / regex`，界面显示“完全等于 / 包含 / 正则”；持久化不得混用 `equals / exact`。OCR 普通日志记录最终识别文字和区域，不把引擎置信度当成面向用户的识别结果。

图像、OCR 与颜色查找的“区域”是分析范围提示，而不是要求当前帧尺寸与捕获时完全一致。运行时取作者区域和当前帧的交集作为实际分析区域：部分越出左、上、右或下边界时自动裁剪并继续，结果坐标仍使用当前帧坐标；完全无交集时，图像/颜色返回正常无结果，OCR 返回空全文、空行与零尺寸实际区域，不抛出异常。区域格式错误或宽高不为正数仍返回 `vision.region_invalid`。运行日志、测试预览和离线回放必须遵循同一规则并能说明实际裁剪；`画面.保存` 的裁剪区域属于文件输出契约，继续严格要求完整位于画面内，防止静默生成与作者指定尺寸不同的文件。

可选 `frame_ref` 的明确空值表示“自动获取最新画面”。作者从已有画面引用清空字段时必须保存该空值，不得报成必填、恢复旧引用或生成 `unset`；显式引用和自动新帧的语义必须可逆切换。

开发端对上述图像/OCR函数提供无副作用的当前画面测试。测试必须先取得一张新的 `FrameReference`，再调用与正式 Runtime 相同的 `vision.find` 或 `text.recognize` 适配器；图像等待/点击组合在测试时只执行一次查找，绝不产生输入。图像与 OCR 返图只展示本次真正参与分析的实际区域，不能用完整目标画面冒充区域证据；命中框从帧坐标换算为返图内坐标，部分越界同时显示裁剪后的实际区域，完全无交集显示明确空状态而不返回整帧。OCR 返图展示正式预处理后的区域图与本次识别文字；图片资源使用稳定资源选择器，不要求作者手输资源 ID 或表达式。含变量、结果或计算值的参数只能通过真实流程运行验证，不用界面临时值冒充。

图像查找在同一次模板分析中保留阈值过滤前的最高有限相似度。即时测试、直接查找日志以及标准等待/点击的到期日志都必须同时显示实际分值和当前阈值；低于阈值仍返回正常空结果，诊断分值不得伪造成一次命中，也不得通过第二次模板扫描取得。

`输入.点击` 的保持时间默认为 `0`；它表示普通单击，Windows 后台驱动仍使用 50ms 的平台最小按压时间，避免按下与抬起被 Chromium/DirectX 目标折叠进同一渲染帧。大于 `0` 时同一原子表达按作者时长单点长按，多次时对每次点击分别保持，不另设重复的“输入.长按”函数。Windows 窗口点击解析目标点所属的最深可用子窗口，并通过有界同步消息直接交给该窗口过程；它不移动物理鼠标，仍必须把结果标记为“效果未验证”。`输入.拖拽` 的移动时长作用于整条路径；Windows/ADB 按各段几何长度确定性分配，Android Accessibility 使用同一总时长执行整条手势。`图像.点击一次`、`图像.点击直到消失` 与两个“点击位置直到…”函数都是可展开、可调试的标准函数，不是新的输入原语。“点击位置直到…”每轮先取得新画面并判断后置条件，条件已经满足时零点击返回；只有未满足时才点击指定固定位置。出现默认连续命中 1 帧，消失默认连续未命中 2 帧，防止动画瞬帧造成误判。Android/ADB 对 `输入.点击` 只接受主触控语义；非主鼠标按钮在平台检查中拒绝。`输入.移动指针` 仅支持具备独立指针的 Windows 目标。`控件.*` 使用统一契约和平台适配器；SurfaceView/自绘页面没有语义节点时明确提示改用图像、OCR 或坐标，不伪造控件。

所有枚举参数由同一函数契约声明中文标签、稳定值和可用平台，IDE 与 Player 不维护第二份选项表。Windows 文本输入支持“自动选择 / 仅后台输入 / 物理键盘”；ADB 与 Android 本机支持“自动选择 / 目标原生输入”。“自动选择”在 Windows 上优先后台投递，只有目标允许或工作区为桌面时才回退物理输入，并记录失败原因与真实路径；“仅后台输入”失败时不得偷偷回退。平台不兼容的固定选项在编译时阻止，运行时驱动仍做第二次防御校验。

### 当前基础平台切片自动化证据

格式 6 Runtime 已使用可控替身完成 `目标.等待在线 / 读取状态` 的稳定目标闭包、当前目标重新探测、正常到期空值与取消；完成 Windows `.exe` 类型化启动、同一进程引用等待、命令解释器/脚本宿主拒绝，以及 ADB 包/Activity 固定参数数组边界。Windows 窗口引用会校验句柄、进程、线程与窗口类，控件动作必须先由 `控件.查找` 取得当前运行会话内的 `ControlReference`；句柄复用、控件变化和跨目标引用均返回结构化异常。按键覆盖 Windows 后台消息与显式物理回退、ADB scrcpy 控制通道；物理回退日志包含后台失败原因、真实输入路径与鼠标恢复事实。坐标、区域、图片、控件和拖拽路径的 Capture action 已按真实宿主能力向 Windows、ADB 和 Android 本机开放；控件内部适配分别为 UIA、UIAutomator 与 Accessibility，SurfaceView/自绘页明确转用图像、OCR 或坐标。

视觉/OCR 原子切片已使用固定种子合成帧自动验证 Windows RGB 与 ADB BGR 适配：`图像.查找 / 查找全部` 真实裁剪区域、边缘部分越界自动取交集、完全无交集正常空结果、全量结果去重与上限、普通调用逐次取新帧、显式 `FrameReference` 同像素复用、资源哈希失败和结构化错误均已闭环；`文字.识别` 通过 RapidOCR/ddddocr 统一适配返回固定 `OCRResult/OCRLine`，同帧同实际区域同预处理缓存，空文字或无交集返回空全文/空行而不是异常，用户日志只显示文字与实际区域。Windows Player 规格已显式收集两类 OCR 模型与 ONNX Runtime 动态库，并有静态闭包测试；离线回放已有这三个原子函数的独立纯帧适配器。`exact / contains / regex` 已由标准文字匹配和等待函数使用；无效正则是结构化错误，未命中或到期是正常空结果。

官方 v1 目录的 83 个函数已全部进入 `complete/available`。其中 `窗口.等待出现`、`控件.等待出现/等待消失`、六个图像等待/点击组合、`文字.匹配`、`文字.等待出现` 以及既有 `目标.等待在线` 都具有可由 Compiler 验证和降低的规范 `ProgramDocument`。性能融合路径与规范组合逐项比较返回、原子调用轨迹、正常超时、取消和日志；每次控件、视觉或 OCR 检查都重新读取当前宿主状态，稳定帧计数不复用隐式缓存。图像点击标准函数只组合图像查找与 `输入.点击`，没有第二套隐藏输入语义。

`时间.今天` 是原子宿主时间能力：默认使用系统时区，也可显式使用 IANA 时区/UTC，日历日由宿主 `tzdb` 处理 DST，无效时区返回结构化错误。`项目.数据目录` 在 IDE 映射到当前项目 `.easycode/data`，在 Player 映射到当前产品的独立私有 `project-data`；两者都不因此自动取得递归删除权限。

除各专题另附真实宿主报告的项目外，上述结论仍不能由自动化适配器/替身直接推导为发布验收。跨平台控件已有真实 Windows UIA、显式 ADB 模拟器/手机和 Android 模拟器 Accessibility 证据，见 `output/harness/cross-platform-controls-20260902/report.md`；Android 本机物理手机仍必须在 APK 可安装设备上补齐，不得用 ADB UIAutomator 或模拟器冒充。OCR 模型闭包及其他领域继续按各自 Harness 放行。

### 5.3 文件与目录

| 显示名 | `function_id` | 层级 | 主要输入 → 返回 | 宿主 | 目标能力 |
| --- | --- | --- | --- | --- | --- |
| `文件.存在` | `official.file.exists` | A | `FileReference` → `bool` | W/A | `filesystem` |
| `文件.读取文本` | `official.file.read_text` | A | 文件、编码 → `string` | W/A | `filesystem.read` |
| `文件.写入文本` | `official.file.write_text` | A | 文件、内容、编码 → `void` | W/A | `filesystem.write` |
| `文件.追加文本` | `official.file.append_text` | A | 文件、内容、编码 → `void` | W/A | `filesystem.write` |
| `文件.替换文本` | `official.file.replace_text` | A | 文件、查找、替换、范围、编码 → `int64` | W/A | `filesystem.read_write` |
| `文件.读取JSON` | `official.file.read_json` | A | 文件 → `json` | W/A | `filesystem.read` |
| `文件.写入JSON` | `official.file.write_json` | A | 文件、JSON 值 → `void` | W/A | `filesystem.write` |
| `文件.删除` | `official.file.delete` | A | 文件 → `bool` | W/A | `filesystem.delete_file` |
| `文件.复制` | `official.file.copy` | A | 来源、目标、冲突策略 → `FileReference` | W/A | `filesystem.read_write` |
| `文件.移动` | `official.file.move` | A | 来源、目标、冲突策略 → `FileReference` | W/A | `filesystem.read_write` |
| `目录.存在` | `official.directory.exists` | A | `DirectoryReference` → `bool` | W/A | `filesystem` |
| `目录.创建` | `official.directory.create` | A | 父目录、相对位置、已存在策略 → `DirectoryReference` | W/A | `filesystem.write` |
| `目录.列出` | `official.directory.list` | A | 目录、筛选、递归设置 → `list<FileSystemEntry>` | W/A | `filesystem.read` |
| `目录.复制` | `official.directory.copy` | A | 来源、目标父目录、名称、冲突策略 → `DirectoryOperationReport` | W/A | `filesystem.read_write` |
| `目录.移动` | `official.directory.move` | A | 来源、目标父目录、名称、冲突策略 → `DirectoryOperationReport` | W/A | `filesystem.read_write` |
| `目录.删除` | `official.directory.delete_empty` | A | 空目录 → `bool` | W/A | `filesystem.delete_empty_directory` |
| `目录.递归删除` | `official.directory.delete_tree` | A | 已授权目录 → `DirectoryOperationReport` | W/A | `filesystem.delete_tree` |

以上集合与 [`FILES.md`](FILES.md) 完全一致。`DirectoryReference` 派生文件使用核心纯值操作 `core.file_ref_child.v1`，不是额外 I/O 函数；它只能在已有授权根内缩小能力。递归删除仍使用独立函数、危险权限、作者审核和终端实际授权根确认，不能改成普通删除参数。

### 5.4 网络与消息

| 显示名 | `function_id` | 层级 | 主要输入 → 返回 | 宿主 | 目标能力 |
| --- | --- | --- | --- | --- | --- |
| `网络.请求` | `official.network.request` | A | 方法、URL、查询、头、文本/JSON正文、超时 → `HTTPResponse` | W/A | `network` |
| `网络.上传文件` | `official.network.upload_file` | A | HTTP设置、有序 multipart 字段 → `HTTPResponse` | W/A | `network + filesystem.read` |
| `网络.下载文件` | `official.network.download_file` | A | HTTP设置、可写文件、大小上限 → `HTTPDownloadResult` | W/A | `network + filesystem.write` |
| `消息.发送` | `official.message.send` | A | 收件实例列表、名称、内容、有效期 → `MessageBatch` | W/A | `messaging` |
| `消息.等待接收` | `official.message.wait_receive` | A | 名称、来源过滤、超时 → `optional<ReceivedMessage>` | W/A | `messaging` |
| `消息.等待已读` | `official.message.wait_read` | A | 发送批次、全部/任一、超时 → `MessageReadResult` | W/A | `messaging` |
| `消息.取消` | `official.message.cancel` | A | 发送批次、可选收件实例 → `MessageCancelResult` | W/A | `messaging` |

网络函数使用 `网络.*` 作为唯一规范名称；历史 `HTTP.*` 只可作为搜索别名。普通请求、上传和下载保持三个独立原子函数。消息已读只表示接收脚本已取得并解码；不提供 `消息.完成 / 消息.重发 / 消息.回复`，业务再次通知继续调用 `消息.发送`。

### 5.5 宿主—目标能力矩阵

| 目标能力 | Windows 宿主 / Windows 目标 | Windows 宿主 / ADB 目标 | Android 本机宿主 / 当前手机 | 无操作目标 |
| --- | --- | --- | --- | --- |
| `target.registry` | 支持 | 支持 | 仅当前手机引用 | 支持配置/等待引用，不执行视觉输入 |
| `frame.read` | 支持 | 支持 | 支持 | 不支持 |
| `application.launch` | 支持 | 支持 | 支持；必须通过真机启动/返回闭环 | 不支持 |
| `application.lifecycle` | 支持 | 支持运行状态与停止；等待退出不支持 | 不支持 | 不支持 |
| `window.uia` | 支持 | 不支持 | 不支持 | 不支持 |
| `input.point / text / scroll / drag / key` | 支持或按驱动条件支持 | 支持 | 支持或按权限条件支持 | 不支持 |
| `pointer.move` | 支持 | 不支持 | 不支持 | 不支持 |
| `control.semantic` | UIA | UIAutomator，条件支持 | Accessibility，条件支持 | 不支持 |
| `filesystem / network / messaging` | 由 Windows 宿主提供，不依赖当前目标 | 由 Windows 宿主提供，不依赖当前目标 | 由 Android 本机宿主提供 | 支持 |

“条件支持”必须在目标能力快照中给出具体前提，例如后台输入、Accessibility、生命周期观察或文件 Provider 原子提交；缺少前提时原位禁用并在编译/发布前阻止，不能点击后才伪报支持。平台矩阵不使用单一“Android”布尔值。

### 5.6 首版结果类型与纯值补充

- `date` 是只有日历日期、没有时刻的类型；`datetime` 始终携带明确时区。
- `TargetInfo` 至少包含稳定目标 ID、目标种类、在线/就绪状态、视口尺寸、空间版本和能力快照。
- `FrameReference` 是当前运行内不可变引用，至少包含帧 ID、来源目标 ID、空间版本、采集序号/时间和尺寸；不能保存为项目变量或 Player 字段。
- `ImageMatch` 至少包含区域、中心、相似度、来源帧和来源目标；单项查找返回 `optional<ImageMatch>`，全部查找返回有界列表。
- `OCRLine` 至少包含识别文字和区域；`OCRResult` 至少包含最终全文、按阅读顺序排列的行、识别区域、来源帧和来源目标。面向用户的成功日志输出识别文字，不显示笼统置信度。
- `ImageClickResult` 至少包含点击次数、是否已经消失和最后一次匹配的可选结果。
- `ApplicationRunReference`、`WindowReference`、`ControlReference`、`FileReference` 与 `DirectoryReference` 都是有宿主/能力约束的强类型引用，不降级为普通路径、句柄或字符串。
- 核心纯值注册表增加 `core.file_ref_child.v1`：用 `DirectoryReference + 安全相对位置 + 访问模式` 派生能力不扩大的 `FileReference`，不访问文件系统；以及 `core.json_parse_text.v1`：把文本确定性解析为 `optional<json>`，非法 JSON 返回无结果而不是执行 I/O。两者使用稳定操作/输入槽 ID 并进入 lock 哈希。

多个视觉候选的规范组合是“`画面.保存` 一次 → 对同一 `FrameReference` 执行多个 `图像.查找`/OCR/控件查询 → 用条件组和有序 `如果/否则如果` 只进入一个分支”。“任一命中”使用或条件，“全部命中”使用且条件；需要按最高图片相似度选择时，先保存各 `ImageMatch.相似度` 再以普通数值比较决定分支。性能边界由一次取帧和多个必要匹配组成；不得用每个候选各自等待超时的串行方案。首版不增加与该组合同义的“匹配多张图片”函数或 `switch/race` 结构，除非后续多个真实项目证明配置仍不可接受并能冻结跨图像、OCR、控件一致的返回契约。

### 5.7 明确不属于函数目录

`if / loop / return / try / target_scope / listen` 是 ProgramDocument 结构；计划、录制与回放是宿主控制面。首版不注册 `页面.* / 存储.* / 租约.* / 计划.* / 录制.* / 回放.* / 重试.*`，也不提供任意 Shell、PowerShell、命令解释器或通用脚本执行函数。普通项目使用项目函数和现有结构组合业务，不从旧节点名称平移同义函数。

## 6. 正常无结果与异常边界

- 图像、文字、控件和窗口的立即查询未命中，返回对应 `optional<T>` 的明确空状态。
- 等待图片、文字、控件或窗口直到截止时间仍未命中，也以正常完成返回明确空状态；该结果可直接用于“有结果”条件，不产生失败 Toast、异常或伪造坐标。
- 资源不存在/损坏、权限不足、目标断开、平台不支持、参数越界以及驱动/扩展崩溃产生结构化异常，并沿 ProgramDocument 异常区域传播。
- 运行日志分别记录正常“无结果”和失败异常；任何函数不得用空字典、错误字符串或统一 `false` 混淆二者。

通用重试已冻结为现有异常区域的可选策略：默认关闭，开启时默认最多再试 2 次、固定间隔 500ms，只处理契约标记为瞬时的结构化异常。它不增加 `retry` 语句或函数，也不给所有函数复制重试次数和失败策略；正常无结果与 HTTP `4xx/5xx` 不重试，取消/停止永不重试，副作用不回滚且必须由作者审核。消息、更新和调度内部的幂等传输重试继续由各服务自己的契约治理。

## 7. 首批冻结需求

- `[REQ-FUNC-APP-001]` Windows 宿主提供受约束的应用启动与进程退出等待，并拒绝任意 Shell、PowerShell、命令解释器和系统命令文本。
- `[REQ-FUNC-WIN-001]` Windows 驱动提供窗口立即查找、等待、激活、关闭和位置/尺寸/可见性/前台状态读取。
- `[REQ-FUNC-TGT-001]` 启动模拟器后转入 ADB 使用应用启动、目标等待与 `target_scope` 的普通组合，不新增同义模拟器运行机制。
- `[REQ-FUNC-FRAME-001]` 普通视觉调用自动取得调用开始后的当前目标新帧，不能消费上一调用的隐式截图缓存。
- `[REQ-FUNC-FRAME-002]` 显式 `frame_ref` 可供多个图像/OCR调用复用完全相同的像素，并使所有结果继承来源目标与空间版本。
- `[REQ-FUNC-FRAME-003]` 可选画面字段可从显式引用清空为“自动获取最新画面”，保存后不得恢复旧引用或阻止运行。
- `[REQ-FUNC-VISION-DIAG-001]` 图像匹配一次分析同时产生命中结果与阈值前最高相似度；预览和运行日志在命中、未命中及到期时显示实际分值与阈值，不增加第二次扫描。
- `[REQ-FUNC-VISION-REGION-001]` 图像、OCR 与颜色分析使用作者区域和当前帧的交集；部分越界继续分析，完全无交集返回类型对应的正常空结果，格式错误或非正宽高才是 `vision.region_invalid`。正式运行、无副作用预览、离线回放、Windows/ADB 与 Android 本机保持一致；测试返图必须是实际分析区域而不是整帧，并显示实际区域坐标/尺寸与裁剪状态；`画面.保存` 保持严格裁剪。
- `[REQ-FUNC-VISION-ACTION-001]` “点击位置直到出现/消失”在首次和每次点击前读取当前目标新帧；后置条件已满足时必须零点击返回，未满足时只点击作者指定位置，不偷换成匹配中心。
- `[REQ-FUNC-VISION-ACTION-002]` 两个函数使用单调超时、可取消间隔和连续稳定帧；正常到期返回 `reached=false`、点击次数与最后匹配，不抛出伪异常。
- `[REQ-FUNC-RESULT-001]` 查询未命中和等待到期返回正常明确空结果；资源、权限、目标、平台和驱动/扩展故障返回结构化异常。
- `[REQ-FUNC-NAME-001]` 规范显示名使用 `命名空间.动作`，别名只参与搜索与帮助，持久化和绑定只使用稳定 ID。
- `[REQ-FUNC-DEFAULT-001]` 只有安全稳定参数使用类型化默认值，不能可靠推断的必填资源、路径、目标和选择器保持 `unset`。
- `[REQ-FUNC-PLATFORM-001]` 每个函数分别声明 Windows、ADB、Android 本机与无目标支持状态，并由编辑、编译、发布和运行前检查一致执行。
- `[REQ-FUNC-VERSION-001]` 项目锁定函数契约版本与指纹；任何发现、兼容更新或破坏性迁移都不能静默改写项目。
- `[REQ-FUNC-MIGRATION-001]` 迁移展示全部调用、Player 与平台影响并以原子项目事务提交；取消或失败后旧锁仍可构建。
- `[REQ-FUNC-ERROR-001]` 每个结构化异常拥有稳定异常 ID 和瞬时/永久分类；未知异常默认永久，取消与停止属于控制信号而非可重试异常。
- `[REQ-FUNC-RETRY-001]` 用户程序重试只能通过异常区域可选策略表达；函数目录不存在独立重试函数，普通函数契约不复制通用重试参数。
- `[REQ-FUNC-DIR-001]` 官方目录函数集合与 `FILES.md` 的七项首版契约一致；普通目录删除不能通过参数、别名或旧名称取得递归删除权限。
- `[REQ-FUNC-REPLAY-001]` 录制与回放不进入普通函数目录；首版可回放标记仅由官方无外部副作用、输入可完全固定且存在跨平台专用实现的图像/OCR 分析声明使用。
- `[REQ-FUNC-CATALOG-001]` 官方 v1 注册表必须与第 5 节 83 个稳定 `function_id` 一致；不得缺项、重复 ID、注册同义规范名或出现第 5.7 节禁止命名空间。
- `[REQ-FUNC-CATALOG-002]` 原子/标准实现层级属于锁定契约元数据；标准函数的 ProgramDocument 定义与任何融合实现必须通过返回、异常、超时、取消、日志和调试等价性测试。
- `[REQ-FUNC-MATRIX-001]` 每个函数分别声明宿主要求和目标能力；Windows/Windows、Windows/ADB、Android 本机和无目标结论由两者交集产生，不能使用单一 Android 布尔值。
- `[REQ-FUNC-TYPE-001]` `date`、`TargetInfo`、`FrameReference`、`ImageMatch`、`OCRLine` 和 `OCRResult` 按第 5.6 节建立稳定类型/字段契约，并由成员选择器而非字符串键访问。
- `[REQ-FUNC-PURE-001]` 纯值操作注册表包含稳定 `core.file_ref_child.v1` 与 `core.json_parse_text.v1`；前者不能扩大目录引用能力或访问文件系统，后者对非法 JSON 返回明确无结果。
- `[REQ-FUNC-APP-ANDROID-001]` Android 本机 `应用.启动` 必须在真机完成类型化应用引用、Intent 启动、权限/失败、目标帧与返回 Player 闭环；不能用 Windows/ADB 启动证据替代。

## 8. 后续第一方领域扩展函数

浏览器 DOM 函数不加入官方核心原子目录，也不混入 `网络.*`。它们由第一方签名扩展包贡献，并在函数库、ProgramDocument 调用、中央摘要、右侧 Control、返回绑定、异常和日志中表现为普通函数。

- `[REQ-FUNC-DOM-001]` 首期命名空间覆盖浏览器生命周期、导航、页面等待、DOM 元素查找/等待/点击/输入/选择、数据读取、标签页、iframe 与下载；稳定 ID 和精确契约版本进入 `easycode.lock`。
- `[REQ-FUNC-DOM-002]` `DomSelectorV1` 是强类型扩展值，不能与 `control_ref`、字符串 CSS 或动态字典隐式互换。
- `[REQ-FUNC-DOM-003]` 扩展未启用或未进入发布闭包时，目录不展示其函数，Runtime 不启动浏览器宿主。
- `[REQ-FUNC-DOM-004]` 完整契约以 [`AUTHORING_AUTOMATION.md`](AUTHORING_AUTOMATION.md) 为准。
