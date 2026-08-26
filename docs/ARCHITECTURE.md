# Easycode 系统架构设计文档

> 版本：2.4 | 更新日期：2026-08-22

---

## 一、总体架构

Easycode 采用经典的 **前后端分离 + 独立客户端** 三层架构：

```
┌─────────────────────────────────────────────────────────────┐
│                        用户层                                │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Vue3 IDE    │  │ Player (Web) │  │ Player (PyInstaller│  │
│  │ (前端编辑器)  │  │ (浏览器运行) │  │   独立 EXE 客户端) │  │
│  └──────┬───────┘  └──────┬───────┘  └─────────┬─────────┘  │
│         │                 │                    │            │
│         └─────────────────┼────────────────────┘            │
│                           │                                 │
│                    HTTPS / WebSocket                        │
└───────────────────────────┼─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    FastAPI 后端 API 层                       │
│  ┌────────┐ ┌──────────┐ ┌───────────┐ ┌────────┐ ┌──────┐ │
│  │ System │ │Blueprint │ │Execution  │ │ Build  │ │Vision│ │
│  │ Router │ │ Router   │ │ Router    │ │ Router │ │Router│ │
│  └────────┘ └──────────┘ └───────────┘ └────────┘ └──────┘ │
│  ┌────────────┐                                            │
│  │ Workspace  │               核心服务层 (Core Services)    │
│  │   Router   │  ┌──────────────────────────────────────┐  │
│  └────────────┘  │  执行 / 调试 / 蓝图 / 导出 / 视觉... │  │
│                  └──────────────────────────────────────┘  │
│                         节点执行层 + 图引擎                  │
└─────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                      持久化 & 外部资源                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  SQLite DB   │  │  .ebp 密包   │  │  识图模板 / OCR   │   │
│  │ (执行记录)   │  │ (DRM 加密)   │  │  (Paddle / CV2)   │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 1.1 前端层（Vue3 + Vite）

- **IDE 编辑器**：`frontend/src/main.js` 入口，提供可视化蓝图编辑器、节点属性面板、执行日志面板、全局变量面板等完整 IDE 功能
- **Player 运行端**：`frontend/src/player-main.js` 独立入口，面向终端用户提供动态表单渲染 + 一键运行能力
- **捕获文件管理器**：`frontend/src/capture-main.js` 独立入口，供原生截图宿主悬浮调用
- **组件体系**：
  - 画布层：`WorkflowCanvas.vue` / `TopologyCanvas.vue`（工作流图 + 拓扑地图双画布）
  - 面板层：`NodeListPanel` / `NodeEditorPanel` / `ExecutionLogPanel` / `GlobalVariablesPanel` / `ProjectExplorerPanel` 等
  - 状态管理：Pinia Stores（`topologyStore` / `executionStore` / `projectStore` / `contextStore` / `uiStore`）

### 1.2 后端层（FastAPI + Python 3.10+）

- **API 入口**：`api/app.py` - `create_app()` 工厂模式构建 FastAPI 实例，注册中间件、路由、全局异常处理
- **启动模式**：
  - `dev` 模式：纯后端 uvicorn 运行（`127.0.0.1:8000`）
  - `prod` 模式：后端线程 + PyWebView 原生窗口（`start_webview()`）

### 1.3 Player 独立客户端

- **Web Player**：静态托管于 `release/web/`，通过 `StaticFiles` 挂载到 FastAPI 根路径
- **Native Player**：`scripts/build_player.py` + PyInstaller 打包为独立 EXE，内嵌 assets.ebp 密包

---

## 二、后端分层架构

### 2.1 API 层（`api/routers/`）

路由按工作区、蓝图、执行、构建、视觉、捕获、系统等领域拆分，并通过工厂函数装配：

| 路由模块 | 文件 | 主要职责 |
|---|---|---|
| **System** | `system_router.py` | 系统信息、参数 Schema 注册、健康检查、配置枚举查询 |
| **Blueprint** | `blueprint_router.py` | 蓝图 CRUD、签名校验、项目加载、流程/节点增删改 |
| **Execution** | `execution_router.py` | 任务启动/停止、SSE 日志流 `/execution/{id}/stream`、状态查询 |
| **Build** | `build_router.py` | EBP 密包导出、PyInstaller EXE 编译、Player 打包 |
| **Vision** | `vision_router.py` | 视觉识别接口、截图、模板匹配、OCR 识别调试 |
| **Workspace** | `workspace_router.py` | 工作空间管理、项目列表、文件系统操作、导入导出 |
| **Project Workspace** | `project_workspace_router.py` | 单活动项目打开/关闭、最近项目、修复、外部修改检测 |
| **Capture** | `capture_router.py` | 冻结帧、原生捕获宿主、资源保存事务与 IDE 操作桥接 |

路由注册见 `api/app.py:161-173`，统一通过 `include_router()` 装配。

---

### 2.2 核心服务层（`core/services/`）

核心服务按领域拆分，承载项目、执行、捕获、资源与交付逻辑：

| 服务 | 文件 | 核心职责 |
|---|---|---|
| **ProjectWorkspaceManager** | `project_workspace_service.py` | 单活动项目、初始化/修复、代次隔离、项目锁、最近项目与外部修改检测 |
| **BlueprintService** | `blueprint_service.py` | 元数据/工作流/拓扑三文档事务保存、崩溃恢复与结构校验 |
| **TemplateLibraryService** | `template_library_service.py` | 项目资源删除/移动/恢复、引用清理、回收站与崩溃恢复 |
| **ExecutionService** | `execution_service.py` | 执行生命周期管理、后台线程运行、状态/日志内存存储、SSE 流生成 |
| **DebugService** | `debug_service.py` | 断点调试会话：`DebugSession` 管理 pause/resume/step、断点集合、变量快照 |
| **ExportService** | `export_service.py` | 资产导出编排：调用 ProjectExporter 生成 EBP 密包、生成 user_config.json |
| **PlayerService** | `player_service.py` | Player 运行时：EBP 解密加载、表单 Schema 解析、运行上下文注入 |
| **VisionService** | `vision_service.py` | 视觉能力封装：图像匹配、OCR、内存模板缓存（MemoryMatcher） |
| **WorkspaceService** | `workspace_service.py` | 工作空间文件操作、路径安全校验、项目列表检索 |
| **SnapshotService** | `snapshot_service.py` | 项目版本历史快照、恢复与容量保留策略 |

服务调用关系：

```
API Router → Core Services → Node Executors → Graph Engine
                         ↘ Security Module / Conditions / Variables
```

---

### 2.3 节点执行层（`core/node_executors/base/`）

**12 种标准节点执行器** + 1 个基类 `base_class.py`：

| 节点类型 | 文件 | 功能描述 |
|---|---|---|
| **click** | `click.py` | 坐标点击 / 图像点击（PC 鼠标 + Android ADB 双模式） |
| **image_recognition** | `image_recognition.py` | 模板匹配 / 多目标检测 / 置信度阈值判断 |
| **ocr_recognition** | `ocr_recognition.py` | PaddleOCR 文字识别 / 区域 OCR / 文字包含判断 |
| **logic_check** | `logic_check.py` | 条件组合判断（AND/OR/NOT），集成条件引擎 evaluator |
| **branch** | `branch.py` | 多分支择优：基于图像得分或条件结果选择输出端口 |
| **set_window** | `set_window.py` | 窗口绑定 / 坐标偏移设置 / 模拟器 ADB 自动探测 |
| **wait** | `wait.py` | 固定时长等待 / 图像出现等待 / 条件满足等待 |
| **script_call** | `script_call.py` | Python 脚本片段注入执行 / 外部脚本调用 |
| **smart_jump** | `smart_jump.py` | 图驱动智能跳转：调用 PathFinder 寻路最短路径 |
| **variable_op** | `variable_op.py` | 变量赋值 / 模板字符串渲染 / 类型转换 |
| **log** | `log.py` | 自定义日志输出 / 图像日志截图 / 变量值打印 |
| **page_state** | `page_state.py` | 页面状态断言 / 拓扑地图页面 ID 切换 |

所有执行器通过 `NodeExecutorRegistry` 自动注册（`core/registry.py`），GraphExecutor 通过 `node_type` O(1) 查找执行器类。

---

### 2.4 参数定义层（`core/params/base/`）

与节点执行器 **一一对应** 的 Pydantic Schema 定义：

| 参数模块 | 对应节点 | 核心字段 |
|---|---|---|
| `click.py` | click | target_type(coord/image/ocr), region, offset, clicks, interval |
| `image_recognition.py` | image_recognition | template_path, threshold, match_mode, region, timeout |
| `ocr_recognition.py` | ocr_recognition | region, keywords, lang, mode(exact/contains) |
| `logic_check.py` | logic_check | conditions[], operator(AND/OR), timeout |
| `branch.py` | branch | outputs[] - 多个分支端口配置 |
| `set_window.py` | set_window | window_title, offset_top/bottom/left/right, is_emulator |
| `wait.py` | wait | duration, wait_for(image/text/condition) |
| `script_call.py` | script_call | script_code, script_path, timeout |
| `smart_jump.py` | smart_jump | target_page_id, target_node_id, path_strategy |
| `variable_op.py` | variable_op | operations[] - 赋值/追加/删除/计算 |
| `log.py` | log | message, level, capture_image, variable_names[] |
| `topology.py` | - | 拓扑地图节点 Schema（页面 + 跳转边） |

参数 Schema 同时被后端校验（Pydantic ValidationError 全局捕获）和前端表单渲染（FormSchemaEditor）使用，保持前后端一致。

---

### 2.5 安全模块（`core/security/`）

```
core/security/
├── __init__.py
├── crypto.py          # SecureAssetCrypto - AES-256 + PBKDF2
└── licensing.py       # 授权管理（机器码绑定 / 卡密校验）
```

| 组件 | 实现要点 |
|---|---|
| **SecureAssetCrypto** | `crypto.py:12` - AES-256-CBC 加解密 + PBKDF2(SHA256, 10万次迭代) 动态密钥派生 + 随机 IV 头部 |
| **Licensing** | `licensing.py` - 机器码采集 + 卡密格式校验 + 授权过期判断 |
| **assert_safe_path** | `security/__init__.py` - realpath + normcase 边界校验，阻止目录穿越与链接越界 |
| **atomic_write_json** | `security/__init__.py` - 同目录临时文件、fsync、`os.replace` 原子替换 |

---

### 2.6 条件引擎（`core/conditions/`）

```
core/conditions/
├── __init__.py
├── base.py            # ConditionRegistry + BaseConditionHandler
├── evaluator.py       # 统一评估入口 evaluate_condition()
└── handlers/
    ├── file_exists.py     # 文件/目录存在判断
    ├── image_exists.py    # 图像模板是否出现在屏幕
    ├── text_contains.py   # OCR 文字包含判断
    ├── variable_check.py  # 变量值比较 (=/!=/>/</contains/regex)
    └── window_state.py    # 窗口状态（存在/激活/最大化等）
```

**核心流程**（`evaluator.py:5`）：
1. 从 cond_data 中提取 condition_type 与 params
2. 通过 ConditionRegistry 查找对应 Handler 类
3. 调用 `handler.evaluate(params, context)` 返回 bool 结果
4. 未找到 Handler 时输出 warning 日志并返回 False

扩展机制：新增条件只需继承 `BaseConditionHandler` 并使用 `@ConditionRegistry.register('xxx')` 装饰器注册。

---

### 2.7 图与运行时变量

#### 图引擎（`core/graph/`）

```
core/graph/
├── __init__.py
├── builder.py     # GraphBuilder - 构建邻接表 AdjacencyGraph
└── pathfinder.py  # PathFinder - BFS 最短路径查找
```

| 类 | 核心方法 | 作用 |
|---|---|---|
| **GraphBuilder** | `build_from_project()` | 扫描运行时 `project.tasks`，为主流程和函数调用帧构建邻接表 |
| **GraphBuilder** | `build_topology_graph()` | 从 topology 配置构建页面跳转拓扑图 |
| **PathFinder** | `find_shortest_path(graph, src, dst)` | BFS 算法返回 PathResult（路径 + 节点序列 + 总权重） |

GraphExecutor 在 `__init__` 中调用 `_build_graphs()` 预构建所有邻接表（`executor.py:90`），供 smart_jump 节点运行时寻路。

运行时变量由项目元数据、执行上下文和表达式求值器共同管理；不再维护旧版
`core/variables/` 类型注册目录。任务调用通过显式输入/输出映射隔离局部值。

---

## 三、安全设计

### 3.1 SecurityConfig 统一密钥管理（`core/config.py:18`）

**原则：禁止硬编码密钥，所有敏感配置通过环境变量注入。**

| 环境变量 | 用途 | Dev 兜底 | Prod 要求 |
|---|---|---|---|
| `APP_ENV` | 运行环境标记 dev/prod | dev | 必须为 prod |
| `EASYCODE_MASTER_SALT` | PBKDF2 资产加密 Salt | `EasycodeDRMSalt2026SecureStorage` | **必填**，否则启动失败 |
| `EASYCODE_CORS_ORIGINS` | CORS 白名单（逗号分隔） | `['*']` | 未配置时仅允许 `127.0.0.1:8000` |
| `EASYCODE_RATE_LIMIT` | slowapi 速率限制 | `120/minute` | 按需调整 |

启动时 Prod 环境缺失资产加密 Salt 会抛出 `RuntimeError`。

---

### 3.2 项目结构校验（`core/project_schema.py`）

IDE 只接受同一版本的 `project.json`、`workflow.json`、`topology.json`、
`context.json`、`form_schema.json`，并要求 `templates/assets.json` 使用当前资源索引版本。
加载时严格校验任务、节点、实体边、稳定端口 ID 与 `asset://` 资源引用；不会补建缺失文档或猜测执行跨版本迁移。同一文档版本内仅对旧滚动/拖拽字段执行一次性、带三文档快照的手势参数迁移。

---

### 3.3 SecureAssetCrypto AES-256 + PBKDF2（`core/security/crypto.py:12`）

**EBP 密包加密链路**：

```
Master Key (32B)
    │
    ├──▶ PBKDF2-HMAC-SHA256(iter=100000, salt=SecurityConfig)
    │         │
    │         └─▶ MachineCode 绑定派生 Key（跨机器不可解密）
    │
    └─▶ AES-256-CBC 加密
              │
              ├─ IV: os.urandom(16) 随机生成（拼接头 16B）
              ├─ Padding: PKCS7 (128-bit)
              └─ 输出: [IV(16B)][CipherText]
```

关键 API：
- `derive_key_from_machine(master_key, machine_code)` - 机器绑定派生
- `encrypt_ebp_stream(raw_data, key)` - 加密
- `decrypt_ebp_stream(encrypted_bytes, key)` - 解密（长度不足抛 ValueError）

---

### 3.4 assert_safe_path 防目录遍历（`core/security/__init__.py`）

**攻击防护场景**：用户提交 `../../etc/passwd` 或 `project/../secret.txt` 路径尝试越界访问。

校验步骤（Windows 完全兼容）：
1. `os.path.abspath()` → 解析为绝对路径
2. `os.path.normcase()` → 统一小写（消除 Windows 盘符大小写不一致）
3. base 路径末尾补 `os.sep` → 防止 `/demo` 误匹配 `/demo_2` 前缀
4. 严格比较：`norm_target == norm_base || norm_target.startswith(base_prefix)`
5. 失败抛 `HTTPException(400, "非法路径越界操作")`

---

### 3.5 CORS 白名单 + 限流 + 安全响应头

配置于 `api/app.py:121-142`：

| 安全机制 | 实现 |
|---|---|
| **CORS** | `CORSMiddleware` + SecurityConfig 白名单；Methods 限定 `GET/POST/PUT/DELETE/PATCH/OPTIONS`；仅暴露必要 Headers |
| **速率限制** | `slowapi.Limiter`（可选依赖，缺失时降级无限制）；默认 `120/minute` 按客户端 IP；异常时返回 429 |
| **安全响应头**（全局中间件） | `X-Content-Type-Options: nosniff`<br>`X-Frame-Options: SAMEORIGIN`<br>`X-XSS-Protection: 1; mode=block`<br>`Referrer-Policy: strict-origin-when-cross-origin` |
| **全局异常处理** | `RequestValidationError` → 422 业务错误码；兜底 Exception → 500 屏蔽堆栈（生产日志记录，前端仅见通用提示） |

---

## 四、执行引擎

### 4.1 核心三角：Executor + ExecutionService + DebugService

```
┌────────────────────────────────────────────────────────┐
│                    执行引擎核心三角                      │
│                                                        │
│  GraphExecutor (core/executor.py)                      │
│    ├─ 图驱动迭代式任务执行（替代递归防栈溢出）           │
│    ├─ 邻接表预构建 + 环路检测（MAX_NODE_VISITS=50）      │
│    ├─ 线程安全 stop() 停止标志 + 日志锁                 │
│    └─ FlowTermination 自定义异常替代 StopIteration      │
│                                                        │
│  ExecutionService (core/services/execution_service.py) │
│    ├─ BackgroundTasks 后台线程启动任务                  │
│    ├─ OrderedDict 内存缓存（上限 100 条）               │
│    ├─ _active_executors 持有引用支持 stop()             │
│    └─ stream_execution_logs() 异步 SSE 生成器           │
│                                                        │
│  DebugService (core/services/debug_service.py)         │
│    ├─ DebugSession 会话级断点/单步管理                  │
│    ├─ threading.Event 实现 pause/resume 同步            │
│    ├─ 变量快照 + 调用栈 + 访问计数状态输出              │
│    └─ 多会话并发隔离（_sessions dict + 锁）             │
└────────────────────────────────────────────────────────┘
```

---

### 4.2 GraphExecutor 图执行引擎（`core/executor.py:32`）

**关键改进（P0/P1）**：

| 改进项 | 解决问题 | 实现方式 |
|---|---|---|
| **停止机制** | 无限循环可中断 | `_stop` 标志 + `_stop_lock`；所有循环检查 `is_stopped` |
| **环路保护** | 连线环路导致死循环 | `_visited_count` 计数器；单节点访问上限 `MAX_NODE_VISITS=50` |
| **迭代式跳转** | 递归跨任务导致 Python 栈溢出 | 显式 `_call_stack` 列表；`_execute_task_iterative()` while 循环 |
| **O(1) 节点查找** | 避免线性扫描 | `node_id_to_index` dict 预构建映射 |
| **沙箱异常捕获** | 单节点崩溃中断整个流程 | `_execute_node_safely()` try/except 包装 |

**执行主流程**（`run()` → `_execute_task_iterative()` → `_execute_single_task()`）：

```
1. 初始化调用栈 [{'task_id': entry, 'start_node_id': None}]
2. While 调用栈非空且未停止:
   ├─ Pop 栈帧，进入 _execute_single_task
   │   ├─ 查找任务，构建 node_id_to_index
   │   └─ While current_node_index < count:
   │       ├─ 禁用节点跳过
   │       ├─ 环路检测（visited_count >= 50 → FlowTermination）
   │       ├─ _execute_node_safely() 执行节点
   │       └─ _handle_jump() 路由决策（返回值决定是否 Ret 到上层）
   └─ 如 should_return 或栈空则 Continue
3. 捕获 FlowTermination → 自然结束或主动停止
4. 兜底 Exception → 标记 error 状态
```

---

### 4.3 SSE 日志流（`/execution/{id}/stream`）

**API 实现**：`execution_router.py` 中挂载 `GET /execution/{execution_id}/stream`，返回 `StreamingResponse`，Content-Type `text/event-stream`。

**推送策略**（`stream_execution_logs()`，`execution_service.py:132`）：
- 轮询间隔：`await asyncio.sleep(0.2)`（200ms）
- 增量推送：维护 `last_sent_index`，仅推送新日志
- 流终止条件：状态 ∈ `[success, error, stopped]` **且** 日志全部推送完毕
- 每条消息格式：`data: {"status": {...}, "logs": [...]}\n\n`
- 日志项契约：`{time, level, category, message, image?}`。`category` 固定为 `execution / node / vision / navigation / operation / data`，由执行器统一生成。

前端通过 `EventSource` API 订阅，实时追加到 ExecutionLogPanel。

---

### 4.4 断点调试（DebugService）

**DebugSession 状态机**（`debug_service.py:19`）：

```
         start_debug_session()
                 │
                 ▼
         ┌──────────────┐
         │   Running    │ ◄────────── resume() / step()
         └──────┬───────┘
                │ on_node_enter 触发:
                │ - breakpoints 命中
                │ - step_event 置位（单步）
                │ - pause() 手动
                ▼
         ┌──────────────┐
         │   Paused     │ ── get_state() 返回变量快照
         └──────────────┘
                │
         stop() └─▶ release + executor.stop()
```

**调试 API**（DebugService 静态方法）：

| 方法 | 作用 |
|---|---|
| `start_debug_session()` | 启动会话，支持初始断点集合 |
| `add_breakpoint(node_id)` / `remove_breakpoint(node_id)` | 断点管理 |
| `resume_session()` | 从暂停点继续全速运行 |
| `step_session()` | 单步越过（stepOver）执行下一个节点后暂停 |
| `pause_session()` | 手动暂停（等待当前节点执行完） |
| `stop_session()` | 终止调试 |
| `get_variables()` | 获取运行时变量实时值 |
| `list_sessions()` | 列出所有活跃会话 |

变量快照：暂停瞬间通过 `dict(self.executor.variables)` 捕获完整变量副本，避免继续执行污染调试视图。

---

### 4.5 execution_db.py 执行记录持久化

**SQLite 存储**（`core/services/execution_db.py`）替代内存 OrderedDict，支持：

| 表 | 字段 | 用途 |
|---|---|---|
| `executions` | execution_id(PK), project_path, task_id, start_node_id, status, message, created_at, updated_at | 执行主记录 |
| `execution_logs` | id, execution_id(FK), seq, timestamp, level, category, message | 日志明细（seq 自增有序、来源分类可过滤） |
| `execution_variables` | execution_id + variable_name (联合 PK), variable_value(JSON), variable_type, updated_at | 变量快照 |

关键方法：
- `create_execution()` / `update_status()` - 生命周期管理
- `add_logs()` - 批量写入日志（事务）
- `get_logs(after_seq=0)` - 增量拉取日志
- `list_executions(project_path, limit=50)` - 历史记录分页
- `cleanup_old_executions(max_records=100)` - 自动清理，避免 DB 膨胀

---

## 五、导出系统

### 5.1 双阶段流水线：Exporter（密包） + Compiler（EXE）

```
IDE Build 按钮
      │
      ▼
┌──────────────────────────────┐
│  ExportService.export()      │
│  ┌────────────────────────┐  │
│  │ ProjectExporter        │  │
│  │ build_export_bundle()  │──┼──▶ assets.ebp (AES-256 加密)
│  └────────────────────────┘  │     + user_config.json 模板
└──────────────┬───────────────┘
               │ 可选：编译独立 EXE
               ▼
┌──────────────────────────────┐
│  CompilerService             │
│  compile_player_exe()        │
│  ┌────────────────────────┐  │
│  │ subprocess.Popen       │  │
│  │ scripts/build_player.py│──┼──▶ PyInstaller 打包
│  │  (5 分钟超时保护)      │  │     EasycodePlayer.exe
│  └────────────────────────┘  │     + assets.ebp 内嵌
└──────────────────────────────┘
               │
               ▼
       dist/EasycodePlayer_Bundle/ （分发包目录）
```

---

### 5.2 ProjectExporter EBP 密包打包（`core/builder/exporter.py:13`）

**密包结构**：

```
assets.ebp
├── [IV 16 bytes] 随机头部
└── [AES-256-CBC 加密数据]
        └── ZIP 压缩（ZIP_DEFLATED）
             ├── blueprint.json       （固定 revision 的运行蓝图合并视图）
             ├── form_schema.json     （动态表单 Schema）
             ├── context.json         （如果存在）
             ├── templates/
                  ├── assets.json     （稳定资源 ID、路径和捕获元数据）
                  └── **/*.png|jpg|jpeg  （识图模板，保留子目录结构）
             ├── capabilities/        （仅实际引用的项目/公共能力及其包依赖）
             └── scripts/             （仅实际引用的兼容脚本）
```

**user_config.json 自动生成**（`exporter.py:116`）：
- 扫描 form_schema 中所有 fields
- 按 `target` 前缀分发：`$var.xxx` → `vars.xxx`；`$ctx.xxx` → `ctx.xxx`；`$env.xxx` → `env.xxx`
- 提取 `default` 值填充初始配置

项目只使用当前严格文档版本；手势字段迁移前会写入 `.easycode/migrations/gesture-path-*` 快照，并以可恢复事务提交：
- `project.json`：`schema_version` / `project_id` / `revision` / `project_name` / `variables` / `ui_state` / `settings`
- `workflow.json`：`{ schema_version, tasks, edges }`（流程画布）
- `topology.json`：`{ schema_version, tasks, edges }`（拓扑地图，页面数据存于节点 params）
- `context.json`：可移植工作面板参数；窗口句柄、标题和 ADB 绑定写入 `.easycode/local-settings.json`
- `form_schema.json`：Player 参数表单与固定入口
- `templates/assets.json`：稳定 `asset://<assetId>` 到 `image/ocr/page` 文件的映射

EasyCode 源码目录不是脚本项目。任意文件夹都可被显式打开为一个隔离项目；浏览器请求必须携带
`X-Workspace-Id` 和 `X-Workspace-Generation`。切换项目会先冲刷旧保存队列，并使所有旧代次请求失效。

---

### 5.3 CompilerService PyInstaller EXE 编译（`core/builder/compiler_service.py:9`）

**执行流程**：

1. 发布前检查并创建固定 `projectId + revision` 的不可变构建快照
2. 定位 `scripts/build_player.py` 脚本
3. `EASYCODE_EXPORT_PROJECT_PATH` 只指向快照，`EASYCODE_OUTPUT_PROJECT_PATH` 只接收最终产物
4. `subprocess.Popen([sys.executable, build_script])` 子进程启动
   - stdout/stderr 实时捕获
   - timeout=300s（5 分钟 PyInstaller 超时保护）
5. returncode ≠ 0 → 抛 500 详细日志
6. 成功返回 `dist/EasycodePlayer_Bundle` 绝对路径

关键设计：子进程隔离编译环境；构建期间继续编辑项目不会混入本次交付包。

---

## 六、测试架构

### 6.1 测试范围

后端测试由 `pytest` 自动发现，覆盖当前项目结构、实体边语义、执行循环、弹窗处理、稳定资源、Player、捕获宿主、后台输入和发布前检查。前端测试由 Vitest 覆盖画布、Store、资源管理、Player 与大型流程工具；ESLint 作为静态质量门禁。

用例数随功能持续增长，以 `pytest -q` 和 `npm test -- --run` 的当次统计为准。

---

### 6.2 测试基础设施

| 文件 | 作用 |
|---|---|
| `conftest.py` | Pytest fixtures：FastAPI TestClient、临时项目目录、测试用蓝图数据、SQLite 内存 DB |
| `pytest.ini` | 配置：测试路径、markers、输出格式、Pythonpath 设置 |
| `pyproject.toml` | Ruff lint 规则 + pytest 可选配置 |
| `.github/workflows/ci.yml` | CI 流水线：`pip install` → `ruff check` → `pytest --cov` |

---

### 6.3 测试层级

```
┌────────────────────────────────────────┐
│  E2E API 层 (TestClient)               │
│  test_system_api / test_blueprint_api  │
│  └─ HTTP 请求 → 路由 → 服务 → DB       │
├────────────────────────────────────────┤
│  服务单元测试                           │
│  test_asset_service / test_crypto      │
│  └─ 直接调用类方法，断言输出            │
├────────────────────────────────────────┤
│  基础设施 / 工具测试                    │
│  test_config / test_security_path      │
│  test_utils / test_response            │
│  └─ 纯函数 / 配置类测试                 │
├────────────────────────────────────────┤
│  异常 / 健壮性测试                      │
│  test_error_handling                   │
│  └─ 非法输入 / 边界 / 异常链路          │
└────────────────────────────────────────┘
```

---

## 附录：关键路径速查表

| 功能 | 入口文件 | 核心类/函数 |
|---|---|---|
| API 启动 | `api/app.py:108` | `create_app()` |
| 运行蓝图 | `core/executor.py:141` | `GraphExecutor.run()` |
| 调试会话 | `core/services/debug_service.py:161` | `DebugService.start_debug_session()` |
| SSE 流 | `core/services/execution_service.py:132` | `stream_execution_logs()` |
| 项目结构校验 | `core/project_schema.py` | `load_project_documents()` |
| 资产加密 | `core/security/crypto.py:38` | `SecureAssetCrypto.encrypt_ebp_stream()` |
| 导出 EBP | `core/builder/exporter.py:44` | `ProjectExporter.build_export_bundle()` |
| 编译 EXE | `core/builder/compiler_service.py:16` | `CompilerService.compile_player_exe()` |
| 条件评估 | `core/conditions/evaluator.py:5` | `evaluate_condition()` |
| 最短路径 | `core/graph/pathfinder.py` | `PathFinder.find_shortest_path()` |
| 路径安全 | `core/security/__init__.py` | `assert_safe_path()` |

---

## 七、复杂脚本能力架构

EasyCode 将可复用逻辑分为三层，避免为每个业务细节增加一种节点：

1. **基础节点**：语义稳定且几乎所有项目都会使用，如等待、滚动/滑动、拖拽/长按、文本输入、图像与 OCR。
2. **能力函数**：算法性、多步骤、领域相关的功能以包的形式交付，由“调用能力”节点做类型化输入/输出绑定。
3. **平台服务**：跨执行和跨电脑的持久状态、计划任务、消息、租约与离线补发，由 SQLite WAL 和协调 API 承载。

项目能力放在 `<project>/capabilities/<package>/`；可跨项目复用的能力放在 `EASYCODE_CAPABILITY_HOME` 或默认用户级目录。打包时只收集蓝图真实引用的能力包及声明依赖；能力代码在真正调用前不执行，不同项目使用隔离的 Python 命名空间。

详细能力包合约、调用示例和内置能力见 `docs/CAPABILITIES.md`。

---

## 八、v3 主流程、函数、区块与唯一页面地图

磁盘项目只接受严格 v3，五个项目文档分别承担单一职责：`project.json`、`workflow.json`、`topology.json`、`context.json` 与 `form_schema.json`。保存和加载不会迁移旧格式；版本或结构不符会明确阻止打开。

- `workflow.json.main_graph` 是项目唯一主流程，不存在用户可见的任务组或子流程。
- `workflow.json.functions[]` 保存显式创建的函数。每个函数拥有独立画布、唯一固定入口、形参、局部变量、输出、结果出口、测试用例和至少一个显式返回节点。
- `call_function` 通过稳定的参数、输出和结果出口 ID 调用函数；递归调用在 Schema、发布检查和运行时三层阻止。
- `workflow.json.function_folders[]` 只整理函数库，不改变执行或变量作用域。
- 主流程、函数画布与页面地图都可创建几何区块。区块只持久化 `x/y/width/height` 等几何信息，不保存节点 ID；节点完全落入区块内容范围时才随区块移动。
- `topology.json` 是项目唯一扁平页面地图，直接保存 `nodes/edges/blocks`。页面节点用 `page_id` 标识，随机弹窗由页面节点自身的 `is_random_popup` 声明，与区块无关。
- 函数跨项目传输统一使用数据型 `.ecf`；导出会收集被调用函数、稳定资源和能力闭包，导入会生成全新 ID 并重写内部引用。

执行器内部仍使用紧凑的 `Task` 对象承载主流程与函数调用帧，这是运行时适配层，不是持久化格式，也不会重新暴露为产品概念。
