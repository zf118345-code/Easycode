# EasyCode 当前系统架构

> 版本：3.0
> 更新日期：2026-08-27
> 本文只描述当前代码和 Schema v3；旧任务组、区块、跨画布连线和旧项目迁移语义不再属于系统架构。

## 1. 架构目标

EasyCode 是面向 Windows、模拟器和通过 ADB 连接的 Android 设备的低代码自动化 IDE。系统同时提供：

- 主流程：描述一次自动化任务的控制流。
- 函数：带参数、局部变量、返回值和稳定结果端口的可复用节点图。
- 页面地图：项目唯一的页面状态与导航图，供智能跳转按目标页面寻路。
- 能力库：用 Python 实现并通过显式契约调用的复杂能力包。
- Player：只暴露开发者允许修改的运行配置，并执行已发布项目。
- 原生捕获宿主：承担桌面级低延迟截图选择、控件捕获和悬浮交互。

总体原则是“Web 技术负责高密度编辑，原生宿主负责桌面能力，Python 运行时负责执行和设备适配”。不把浏览器页面伪装成原生输入或后台捕获能力。

## 2. 运行拓扑

```text
Vue 3 IDE / Player / Capture UI
        │ HTTP + SSE + workspace identity
        ▼
FastAPI Router（协议、校验、错误映射）
        │
        ▼
Application / Domain Services
        ├─ Workspace、Blueprint、Asset、Snapshot
        ├─ Execution、Debug、Preflight、Player
        ├─ Capture、Vision、Frame Recording
        └─ Capability、Platform、Build
        │
        ▼
Runtime Ports
        ├─ Capture: WGC / DXGI / PrintWindow / ADB stream
        ├─ Input: UIA / window message / ADB / authorized physical fallback
        ├─ Vision: OpenCV / RapidOCR / ddddocr
        └─ Desktop host: Native WebView2 / Capture Overlay
        │
        ▼
Project documents + assets + runtime state
```

开发时：

- 后端：`python api/app.py --mode dev`，默认监听 `127.0.0.1:8000`。
- 前端：在 `frontend/` 运行 Vite，默认监听 `127.0.0.1:5173`。
- `main.py` 是命令行执行器，需要项目与入口参数，不是 IDE 后端启动命令。

发布时：

- FastAPI 托管已构建的 `release/web`。
- `start_webview()` 优先使用项目原生 WebView2 宿主；只有宿主不可用时才显式回退 PyWebView。
- Poetry/打包 CLI 的稳定入口是 `api.app:main`。

## 3. 项目与工作区边界

EasyCode 源码仓库和用户脚本项目是两个边界。脚本项目可以位于任意用户选择的目录，不属于源码仓库的 Git 生命周期。

一个 Schema v3 项目包含：

```text
project.json       项目名、项目 ID、revision、全局变量、设置和 UI 状态
workflow.json      唯一主流程、函数定义与函数文件夹
topology.json      唯一页面地图
context.json       运行上下文
form_schema.json   Player 可配置表单
templates/
  assets.json      稳定 asset:// 引用注册表
  image/
  ocr/
  page/
scripts/
capabilities/
.easycode/         锁、恢复事务、历史等内部状态
```

项目约束：

- 节点引用图片必须使用稳定的 `asset://` ID，移动文件不改变节点引用。
- 主流程、每个函数和页面地图都是独立图，禁止跨图连线。
- `project_id` 是项目身份；`revision` 是持久化版本；前端展示名不参与身份判断。
- 每个项目请求必须携带 `X-Workspace-Id` 与 `X-Workspace-Generation`。
- 切换项目会递增 generation，旧项目的延迟响应不能写入新项目。
- 同一项目只有一个写入者；第二个实例以只读方式打开，不能静默争夺锁。

前端不是活动项目的权威来源。活动项目、锁、只读状态和 generation 均由 `ProjectWorkspaceManager` 管理。

## 4. 持久化与自动保存

`BlueprintService` 按文档域保存：

- 工作流和函数变更只保存 `project.json + workflow.json`。
- 页面地图变更只保存 `project.json + topology.json`。
- 项目设置和全局变量只保存 `project.json`。
- 显式完整保存才提交全部项目文档。

所有 JSON 通过同目录临时文件、flush/fsync 和 `os.replace` 原子替换。多文档事务带恢复记录，进程中断后可以补偿，不允许出现“前端提示成功但只写入一半”。

API 中间件只对真正改变项目文件的路由更新工作区基线。运行、暂停、捕获心跳、截图预热等运行时请求不会扫描项目目录。高频文档保存使用增量指纹；资源树变更才触发完整资源指纹更新。

`SnapshotService` 保存可恢复历史，并使用轻量 `index.json` 读取历史列表。索引缺失、损坏或发现外部新增快照时自动重建；常规自动保存不再反复解析全部历史 JSON。

## 5. 前端职责

```text
View / Panel
  └─ composable（交互协议与生命周期）
      └─ Pinia store（项目事实与可共享 UI 状态）
          └─ API client（身份头、取消、超时、错误归一化）
```

主要入口：

- `App.vue`：IDE / Player 入口选择。
- `IdeLayout.vue`：应用外壳、模式侧栏、工具窗口和宿主事件协调。
- `CanvasPage.vue`：主流程、函数、页面地图的数据源切换和保存协调。
- `CanvasView.vue`：节点与边渲染、选择、拖动、连接、键鼠手势。
- `InspectorPanel.vue`：单节点、批量、函数契约检查器。
- `projectStore`：项目文档、模式和函数事实状态。
- `uiStore`：选择集、临时 UI 状态和面向当前图的批量操作。
- `executionStore`：运行、调试、日志和执行高亮。

前端边界：

- 节点列表、画布和检查器共享同一选择集。
- 资源预览只在图片引用或已提交的预处理参数变化时刷新，也可手动刷新；拖动、选择和无关表单变化不触发视觉请求。
- 画布节点采用对象身份缓存。拖动一个节点时，未变化节点保持相同渲染对象，避免重绘全部图片预览。
- 外部文件变化每 30 秒兜底轮询一次，并在窗口重新获得焦点时立即检查；不是高频目录监听。
- 工具图标使用 Lucide；外壳标题与内容标题只保留一层。

## 6. API 与错误边界

Router 只负责请求 Schema、工作区身份、HTTP 状态和响应格式。CPU/IO 重任务通过线程池或后台 Worker 执行，不阻塞 FastAPI 事件循环。

路由领域包括：

- project workspace：打开、初始化、锁、最近项目和外部修改。
- blueprint：主流程、页面地图、函数和历史。
- execution：启动、停止、断点、暂停、恢复、单步和 SSE。
- vision/capture：资源事务、截图、OCR、图像测试和原生宿主通信。
- workspace/frame recording：窗口、ADB、帧录制与离线回放。
- capability/platform：能力包、多实例消息、租约和协调。
- build/player：发布前检查、表单 Schema、密包、EXE、Player 状态。

规则：

- 用户可修正的冲突使用明确 4xx 状态。
- 基础设施不可用使用 503，不伪装成参数错误。
- 未处理异常记录完整堆栈，响应不泄露本地路径和内部异常文本。
- 后台截图或输入失败必须返回真实失败；物理输入回退只在项目显式授权时执行。

## 7. 执行架构

`ExecutionService` 管理执行登记、生命周期、日志流和线程安全状态；`GraphExecutor` 只负责编排控制流、函数调用帧和运行策略。

执行前：

1. 发布前/运行前检查验证当前图、资源、函数契约和目标能力。
2. 绑定工作窗口或 ADB serial，生成本次运行不可变的 runtime target。
3. 创建运行时会话、帧缓存、输入派发和调试上下文。

执行中：

- 纯日志、变量、固定等待等节点不触发页面或弹窗扫描。
- 弹窗只在具有视觉识别或输入副作用的节点前检测，并与页面寻路隔离。
- 页面地图只在智能跳转及其恢复策略中参与识别和寻路。
- 同一轮页面/图像/OCR 判断优先共享新鲜帧与预处理结果。
- 调用函数建立独立局部变量帧，通过稳定 outcome ID 返回。
- 能力调用的每次重试使用独立上下文和队列，超时 Worker 不能串入下一次重试。

执行后：

- `ExecutionService` 原子更新最终状态，保留诊断信息。
- Runtime session 释放截图、ADB stream、输入和 Worker 资源。
- 单个实例失败不应污染其他实例。

## 8. 输入、捕获与设备能力

能力按目标分级，而不是假设所有窗口都支持同一种方案：

- Windows 标准控件：优先 UIA。
- 普通窗口：后台窗口消息；投递后可做视觉/状态验证。
- GPU/自绘窗口：优先 WGC/DXGI 获取画面；输入不支持时按策略阻止或回退。
- 模拟器/Android：自动从已选窗口解析 ADB serial，使用持续 Android 帧会话和 ADB 输入。
- 物理输入：最后手段，默认关闭；只有用户授权后才能占用鼠标键盘。

最小化、保护画面、独占全屏、反作弊或不接受后台输入时，系统应展示能力原因，不得记录“点击成功”后静默继续。

原生 Capture Overlay 常驻后端生命周期，使用轻量消息协议。编辑捕获与脚本执行互斥；进入捕获前验证目标窗口非最小化并确保得到完整工作区画面。

## 9. 资源与离线回放

`TemplateLibraryService` 对资源执行事务化移动、删除、回收站恢复和引用清理。默认 `image/ocr/page` 三个根目录始终存在且不可删除；所有资源选择/录入界面显示三类目录，入口只决定默认选中目录。

帧录制和离线回放用于不可重复或一闪即逝的业务画面：

- 录制真实时间线和关键帧，不要求当场创建节点。
- 回放画面可以作为截图捕获的数据源，复用同一套点选、框选和资源保存协议。
- 图像、OCR 和页面识别可对录制帧离线回归，输出命中原因和耗时。

## 10. 函数与能力库

函数是节点图，不是复制模板。每个函数有独立 ID 和独立画布、形参、局部变量、返回值、稳定结果端口、固定入口及至少一个返回节点，并可保存测试用例和导入导出契约。

能力库是代码实现的复杂函数包，适合算法、协议或第三方依赖逻辑。能力调用必须经过 manifest 契约、参数校验、超时、重试和隔离 Worker；不能让任意能力代码直接修改 IDE 全局状态。

## 11. 安全与发布

- 路径通过 realpath/normcase 边界验证，拒绝目录穿越和工作区外写入。
- 远程协调只允许 `http/https`，LAN 请求需要协调令牌。
- CORS、响应头和速率限制由 `SecurityConfig` 集中读取。
- EBP 使用项目密包；密钥和 Player 秘密不进入前端项目文档。
- 发布前检查阻止缺失资源、失效函数引用、无入口和不支持的运行能力。

## 12. 质量门禁

统一门禁由 `scripts/quality_gate.ps1` 执行：

1. 前端 ESLint。
2. 前端 Vitest 全量测试。
3. 前端生产构建。
4. Python Ruff 关键正确性规则。
5. Bandit 中高风险扫描。
6. Python Pytest 全量测试。

真实 UI 另由 `scripts/ui_smoke_test.mjs` 在隔离工作区验证流程、函数、页面地图切换、节点渲染、控制台错误、网络失败、横向溢出和无可访问名称的图标按钮。

任何架构调整必须同时更新本文、回归测试和 `docs/FULL_STACK_OPTIMIZATION_2026-08-27.md` 的迭代记录；“代码已写”不等于验收完成。
