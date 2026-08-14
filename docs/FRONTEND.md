# Easycode 前端开发文档

## 1. 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | 3.4+ | 渐进式前端框架，使用 Composition API (`<script setup>`) |
| Vite | 5.0+ | 开发构建工具，HMR 热更新 |
| Element Plus | 2.8+ | UI 组件库（对话框、表单、按钮、表格等） |
| Pinia | 4.0+ | 状态管理，拆分 5 个独立 Store |
| lucide-vue-next | 0.577+ | 统一 SVG 图标库（**禁止使用 emoji 作为 UI 图标**） |
| Vue Flow 画布 | 自研实现 | 工作流画布 + 拓扑画布（SVG 连线 + 拖拽节点） |
| Axios | 1.7+ | HTTP 请求库 |
| splitpanes | 4.1+ | IDE 分栏面板拖拽 |
| vuedraggable | 4.1+ | 列表拖拽排序 |
| pathfinding | 0.4.18 | 网格 A* 寻路（画布连线避障） |

## 2. 目录结构说明

```
frontend/src/
├── api/                          # 后端 API 封装层
│   ├── client.js                 # Axios 实例、拦截器、统一错误处理
│   ├── blueprintApi.js           # 蓝图 CRUD、任务/节点/边、运行任务
│   ├── executionApi.js           # 执行控制：stop/pause/resume/step、调试状态、变量
│   ├── exporterApi.js            # 导出为独立脚本
│   ├── visionApi.js              # 视觉/OCR 模板匹配
│   └── workspaceApi.js           # 工作区上下文（窗口模式、截图坐标）
│
├── components/                   # 组件目录（按功能域分文件夹）
│   ├── canvas/                   # 画布辅助组件
│   │   ├── CanvasLogPanel.vue    # 画布内嵌日志浮层
│   │   └── CanvasMinimap.vue     # 画布缩略图小地图
│   ├── conditions/               # 条件判断系统
│   │   ├── ConditionDialog.vue   # 条件编辑对话框（5 大条件类型）
│   │   ├── conditionSchemas.js   # 条件参数字段 Schema 定义
│   │   └── index.js              # 条件工具函数导出
│   ├── controls/                 # 动态表单原子控件库
│   │   ├── index.js              # controlMap 类型 → 组件映射表
│   │   ├── ControlString.vue     # 字符串输入
│   │   ├── ControlNumber.vue     # 数字输入
│   │   ├── ControlSelect.vue     # 下拉选择
│   │   ├── ControlSwitch.vue     # 布尔开关
│   │   ├── ControlSlider.vue     # 滑块
│   │   ├── ControlRadioGroup.vue # 单选组
│   │   ├── ControlTextarea.vue   # 多行文本
│   │   ├── ControlFileHover.vue  # 文件选择/上传
│   │   ├── ControlWindowSelect.vue # 窗口句柄选择
│   │   ├── ControlCoordPicker.vue # 坐标/区域拾取器
│   │   ├── ControlDict.vue       # 字典键值对编辑
│   │   ├── ControlConditionList.vue # 条件列表编辑器
│   │   ├── VariableInputControl.vue # 变量选择器（含自动补全）
│   │   ├── Margin4Control.vue    # 4 向边距输入
│   │   └── Size2Control.vue      # 宽高尺寸输入
│   ├── inspector/                # 节点/分组检查器面板
│   │   ├── WorkflowInspector.vue # 检查器主容器
│   │   └── panels/
│   │       ├── NodeInspectorPanel.vue    # 单节点参数编辑
│   │       ├── GroupInspectorPanel.vue   # 任务组参数编辑
│   │       └── BatchInspectorPanel.vue   # 批量节点属性编辑
│   ├── panels/                   # IDE 侧边/底部面板
│   │   ├── ProjectExplorerPanel.vue  # 项目资源管理器
│   │   ├── TaskListPanel.vue         # 任务列表
│   │   ├── NodeListPanel.vue         # 节点模板库
│   │   ├── NodeEditorPanel.vue       # 节点参数编辑器
│   │   ├── GlobalVariablesPanel.vue  # 全局变量管理
│   │   ├── VariableInspectorPanel.vue # 变量查看器
│   │   ├── LogPanel.vue              # 应用日志面板
│   │   ├── ExecutionLogPanel.vue     # 执行日志/SSE 流
│   │   └── PluginMarketPanel.vue     # 插件市场面板
│   ├── player/                   # Player 运行端
│   │   └── PlayerFormRenderer.vue    # Schema 驱动的客户表单渲染器
│   ├── schema/                   # Schema 编辑器
│   │   └── FormSchemaEditor.vue      # 客户表单 Schema 可视化编辑器
│   ├── shell/                    # IDE 外壳组件
│   │   ├── TopMenuBar.vue            # 顶部菜单栏
│   │   ├── ActivityBar.vue           # 左侧活动栏（图标切换面板）
│   │   └── ToolWindow.vue            # 可停靠工具窗口容器
│   ├── DebugToolbar.vue          # 调试工具栏（运行/暂停/单步/断点）
│   ├── WorkflowCanvas.vue        # 工作流节点画布
│   ├── TopologyCanvas.vue        # 拓扑（页面状态机）画布
│   ├── ParamRenderer.vue         # Schema 驱动的通用参数渲染器
│   ├── ScreenshotTool.vue        # 截图取色/坐标/区域工具
│   ├── FileBrowser.vue           # 项目文件浏览器（选图片、选路径）
│   └── PanelSettingsDialog.vue   # 面板布局设置对话框
│
├── composables/                  # 组合式函数 Hooks
│   ├── useCanvasDrag.js          # 画布节点拖拽 + 碰撞推挤
│   ├── useCanvasEdges.js         # 连线渲染 + 端口连接
│   ├── useCanvasKeyboard.js      # 画布快捷键（删除、复制粘贴等）
│   ├── useCanvasViewport.js      # 视口平移/缩放/聚焦
│   ├── useEdgeLabels.js          # 连线标签定位
│   └── useUndoRedo.js            # 撤销/重做历史栈
│
├── config/                       # 静态配置
│   ├── nodeIconsConfig.js        # 节点类型 → 图标/颜色映射
│   └── panelsConfig.js           # IDE 面板注册与布局配置
│
├── layouts/                      # 布局组件
│   └── IdeLayout.vue             # IDE 主布局（顶栏 + 活动栏 + 三栏分屏）
│
├── stores/                       # Pinia 状态管理（5 个独立 Store）
│   ├── index.js                  # 统一导出 + useMainStore 向后兼容代理
│   ├── projectStore.js           # 项目/蓝图/任务/节点数据
│   ├── uiStore.js                # UI 交互状态（选中、断点、画布模式）
│   ├── executionStore.js         # 执行会话与调试控制
│   ├── topologyStore.js          # 拓扑画布数据
│   ├── contextStore.js           # 工作区上下文（窗口/坐标偏移）
│   └── plugins/
│       └── loggerPlugin.js       # Pinia action 日志追踪插件
│
├── utils/                        # 工具函数库
│   ├── logger.js                 # 统一日志输出（[DBG]/[INF]/[WRN]/[ERR]）
│   ├── errorHandler.js           # 全局错误处理器
│   ├── storage.js                # localStorage 封装
│   ├── canvasRouter.js           # 画布网格 A* 寻路（连线避障）
│   ├── canvasShared.js           # 画布共享：节点样式、端口、箭头标记
│   ├── gridRouter.js             # 网格路由算法
│   ├── workflowRouter.js         # 工作流连线路由
│   ├── pathSmooth.js             # 贝塞尔路径平滑
│   ├── zIndexManager.js          # 浮层 z-index 管理
│   └── __tests__/                # 单元测试
│       ├── errorHandler.test.js
│       └── storage.test.js
│
├── views/                        # 路由级页面
│   └── PlayerView.vue            # Player 独立运行视图
│
├── assets/
│   └── theme.css                 # 全局主题变量与样式
├── App.vue                       # 根组件
├── main.js                       # IDE 端入口
└── player-main.js                # Player 端入口
```

## 3. 核心 Store 说明

项目使用 Pinia 拆分 **5 个独立 Store**，职责单一、解耦清晰。`stores/index.js` 中保留了 `useMainStore` 作为向后兼容代理层。

### 3.1 projectStore — 项目/蓝图数据

**文件**: `frontend/src/stores/projectStore.js`

**职责**: 管理一切与「持久化蓝图数据」相关的状态。

| 关键字段 | 说明 |
|---------|------|
| `currentProjectPath` | 当前打开的项目路径（持久化到 localStorage） |
| `currentProjectName` | 项目名称 |
| `blueprint` | 内存合并视图：`project_name / tasks / variables / ui_state / edges / topology`（由 project.json + workflow.json + topology.json 三份文件 GET 合并） |
| `paramsDefinitions` | 节点参数 Schema 定义（从后端拉取） |
| `currentTaskId` | 当前选中的任务 ID |
| `recentProjects` | 最近 5 个打开的项目（localStorage） |
| `uiState` | UI 布局状态（面板展开/折叠、宽度等，持久化到蓝图） |

**关键方法**:
- `loadProjectByPath(path)` — 打开项目、验证、写入最近项目
- `loadProjectData()` — 并行拉取 project/workflow/topology 三份数据并合并，同步初始化 topologyStore
- `saveProjectMeta()` / `saveProjectMetaDebounced()` — 保存项目元数据（POST /api/blueprint/save）
- `saveWorkflowImmediately()` — 保存流程画布（POST /api/workflow/save）
- `saveTopologyData()` / `saveTopologyDebounced()` — 保存拓扑地图（POST /api/topology/save）
- `saveBlueprintDebounced()` — 防抖 400ms 三路保存（日常编辑用）
- `saveBlueprintImmediately()` — 立即三路保存（运行任务前、手动保存用）
- `loadParams()` — 加载节点参数定义 Schema
- `createNewTask(taskName)` — 新建任务
- `updateUiState(key, value)` — 更新 UI 布局状态并持久化

### 3.2 uiStore — UI 交互状态

**文件**: `frontend/src/stores/uiStore.js`

**职责**: 纯前端交互态，**不持久化**（刷新后重置）。

| 关键字段 | 说明 |
|---------|------|
| `selectedNodeId` / `selectedNodeIds` | 当前选中的节点（单选 / 多选批量） |
| `selectedGroupId` | 选中的任务组 ID |
| `canvasMode` | `'workflow'` \| `'topology'` — 画布模式切换 |
| `batchMode` | 批量操作模式开关（框选多选节点） |
| `breakpoints` | `Set<node_id>` — 调试断点集合（会话级） |
| `focusTarget` | 画布镜头聚焦目标（跨组件通信：ProjectExplorer → Canvas） |

**关键方法**:
- `selectNode / selectNodes / clearSelection` — 节点选择
- `toggleBatchMode / enterBatchMode / exitBatchMode` — 批量模式
- `selectAllNodes / batchDeleteNodes / batchSetDelay` — 批量操作
- `toggleBreakpoint / addBreakpoint / removeBreakpoint / clearBreakpoints` — 断点管理
- `setCanvasMode(mode)` — 切换工作流/拓扑画布
- `setFocusTarget(target)` — 触发画布镜头聚焦

### 3.3 executionStore — 执行与调试控制

**文件**: `frontend/src/stores/executionStore.js`

**职责**: 管理后端任务执行会话，SSE 日志流消费，调试单步控制。

| 关键字段 | 说明 |
|---------|------|
| `executionLogs` | SSE 推送到日志列表 |
| `currentExecutionId` | 当前执行会话 ID |
| `executionState` | `idle / running / paused / success / error / stopped` |
| `executionPaused` | 是否暂停中（调试命中断点） |
| `executionVariables` | 当前调试变量快照 `[{name, type, value, level}]` |
| `executionCallstack` | 调用栈 `[{function, node_id, task_id}]` |
| `currentActiveNodeId` | 当前命中的节点（画布高亮） |
| `_pollTimer` | 调试状态轮询定时器 |

**关键方法**:
- `runTask(taskId, startNodeId)` — 启动任务，建立 SSE 连接，同步下发断点
- `stopExecution()` — 发送停止信号
- `pauseExecution() / resumeExecution()` — 暂停/恢复
- `stepOverExecution() / stepIntoExecution() / stepOutExecution()` — 单步控制
- `pollDebugState()` — 拉取调试状态
- `getExecutionVariables(level)` — 拉取变量快照
- `startDebugPolling(intervalMs) / stopDebugPolling()` — 调试轮询控制

**数据流**:
```
前端 runTask → 后端返回 execution_id
→ 建立 EventSource(/api/execution/{id}/stream)
→ SSE 推送 logs / debug_state(paused)
→ 更新 executionLogs / executionVariables / currentActiveNodeId
```

### 3.4 topologyStore — 拓扑画布数据

**文件**: `frontend/src/stores/topologyStore.js`

**职责**: 拓扑（页面状态机）画布的节点与连线。独立于工作流画布；文件层持久化为任务组结构 `{tasks, edges}`（topology.json），store 内部保持扁平 `{nodes, edges}`，加载/保存时自动折叠/展开。

| 关键字段 | 说明 |
|---------|------|
| `topologyBlueprint` | `{ nodes: [], edges: [] }` — 拓扑图数据（内部扁平结构） |
| `selectedTopologyNodeId` | 当前选中的拓扑节点 |

**关键方法**:
- `loadTopologyFromBlueprint(bp)` — 从蓝图反序列化（任务组展开为扁平节点；防覆盖本地未保存数据）
- `syncTopologyToBlueprint()` — 序列化为 topology.json 文件结构 `{tasks, edges}` 快照
- `saveTopologyToBlueprint()` — 写入 projectStore 并触发防抖保存（POST /api/topology/save）
- `addTopologyNode / updateTopologyNode / removeTopologyNode` — 节点 CRUD
- `addTopologyEdge / removeTopologyEdge` — 连线 CRUD（去重同源同端口）

### 3.5 contextStore — 工作区上下文

**文件**: `frontend/src/stores/contextStore.js`

**职责**: 截图/视觉识别时的坐标基准（窗口模式 vs 桌面模式）。

| 关键字段 | 说明 |
|---------|------|
| `currentContext.workMode` | `'window'` \| `'desktop'` |
| `windowTitle` | 目标窗口标题 |
| `isEmulator` | 是否模拟器模式 |
| `offsetTop/Bottom/Left/Right` | 窗口内容区偏移（去除标题栏/边框） |
| `targetContentWidth/Height` | 目标内容区尺寸 |

**关键方法**:
- `loadContext()` — 从后端 workspaceApi 拉取上下文
- `setCurrentContext(ctx)` — 更新并持久化

## 4. 画布系统

Easycode 包含两套自研画布：**WorkflowCanvas 工作流画布** 和 **TopologyCanvas 拓扑画布**。两者共享底层路由算法和视觉样式。

### 4.1 WorkflowCanvas 工作流画布

**文件**: `frontend/src/components/WorkflowCanvas.vue`

**核心能力**:
- **节点卡片**：节点头部带类型图标和颜色，支持拖拽移动、选中高亮、断点红点标记
- **任务组包围框**：包裹一组节点，显示循环次数/间隔，支持组拖拽和双击检查器
- **SVG 连线层**：使用网格 A* 寻路（`canvasRouter.js`），自动避开节点碰撞
- **成功/失败双出口**：绿色箭头（成功流）+ 红色箭头（失败流），方向感知的箭头标记
- **流光动画**：`edge-flow-path` 配合 CSS stroke-dashoffset 动画表达执行流向
- **实时拉线预览**：从端口拖出时显示虚线预览路径
- **节点碰撞推挤**：拖放节点时检测重叠，自动推挤周围节点（`useCanvasDrag.js`）
- **20px 网格吸附**：所有节点坐标对齐 20px 网格，确保连线整齐
- **小地图**：`CanvasMinimap.vue` 显示全景缩略图，支持点击定位
- **视口控制**：滚轮缩放、拖拽平移、聚焦动画（`useCanvasViewport.js`）
- **键盘快捷键**：Delete 删除、Ctrl+A 全选、Ctrl+C/V 复制粘贴（`useCanvasKeyboard.js`）

### 4.2 TopologyCanvas 拓扑画布

**文件**: `frontend/src/components/TopologyCanvas.vue`

**与 WorkflowCanvas 的区别**:
| 维度 | WorkflowCanvas | TopologyCanvas |
|------|---------------|----------------|
| 数据来源 | projectStore.blueprint.tasks[].nodes / edges（workflow.json） | topologyStore.topologyBlueprint（topology.json，任务组结构在 store 内展开为扁平） |
| 节点语义 | 动作节点（点击/OCR/脚本...） | 页面状态（page_state）或跳转动作 |
| 连线语义 | 执行流向：成功/失败端口 | 页面跳转：带条件 + 跳转动作 |
| 节点特性 | delay_before / timeout 等参数 | features（页面特征列表）/ feature_mode（and/or） |
| 出边数量 | 每个节点最多 2 条（success/failure） | 多条 exit（每条对应一个条件分支） |

**共享底层**:
- `canvasShared.js` — 统一节点卡片 CSS、端口定位、SVG 箭头标记
- `canvasRouter.js` / `gridRouter.js` — A* 网格寻路 + 连线偏移
- `pathSmooth.js` — 贝塞尔路径平滑
- `composables/` 中的拖拽、视口、键盘 Hooks

## 5. 调试与断点功能

### 5.1 DebugToolbar 组件

**文件**: `frontend/src/components/DebugToolbar.vue`

工业级风格调试工具栏，位于 IDE 顶部画布上方。

**按钮与快捷键**:
| 按钮 | 图标 | 快捷键 | 功能 | 启用条件 |
|------|------|--------|------|---------|
| 运行 | Play | F5 | 运行选中任务 | 已停止 + 有任务 |
| 暂停 | Pause | — | 请求暂停 | 执行中 |
| 继续 | Play | F5（暂停时） | 恢复执行 | 已暂停 |
| 停止 | Square | Shift+F5 | 终止执行 | 运行中或暂停 |
| 单步跳过 | SkipForward | F10 | 执行下一行，不进入子调用 | 已暂停 |
| 单步进入 | ArrowDownToLine | F11 | 进入子任务/函数内部 | 已暂停 |
| 单步跳出 | ArrowUpFromLine | Shift+F11 | 跳出当前子调用栈 | 已暂停 |

**状态指示器**:
- 灰色 `CircleDashed` — 就绪
- 蓝色动画 `Clock` — 执行中
- 橙色 `CircleDot` — 已暂停（命中断点）
- 右侧显示：断点总数量 + 当前激活节点 ID

### 5.2 断点设置与执行流程

**断点存储**:
- `uiStore.breakpoints: Set<node_id>` — 会话级断点集合，刷新后清空
- `toggleBreakpoint(nodeId)` — 切换，F9 快捷键
- `hasBreakpoint(nodeId)` — 画布节点据此渲染右上角红色圆点

**启动时同步**:
```js
// executionStore.runTask 启动时
const breakpoints = useUiStore().getBreakpointList()
await blueprintApi.runTask(projectPath, taskId, startNodeId, {
  ...blueprint,
  __debug: { breakpoints }  // 断点列表一次性下发给后端 debug_service
})
```

**命中流程**:
1. 后端执行器在节点入口检查 node_id 是否在断点列表中
2. 命中后写入暂停状态，通过 SSE 推送 `{debug_state: 'paused', node_id, callstack}`
3. 前端 executionStore 切换到 `paused`，高亮 `currentActiveNodeId`
4. 拉取变量快照 `getExecutionVariables()`，显示在 VariableInspectorPanel
5. 用户按 F10/F11/Shift+F11 或点击继续 → 调用 executionApi.step/resume

## 6. 动态表单系统

Easycode 的所有节点参数编辑器、条件表单、Player 客户表单都基于 **Schema 驱动的动态表单** 架构。核心是三层：

```
Schema 定义 → ParamRenderer 分发 → controls/* 原子控件
```

### 6.1 ParamRenderer — 通用参数渲染器

**文件**: `frontend/src/components/ParamRenderer.vue`

**核心职责**: 根据 `config.type` 字段查找对应的原子控件并渲染，统一处理标签、显隐逻辑、对话框挂载。

**分发逻辑**:
```js
const activeControl = computed(() => {
    const type = props.config.type
    if (type === 'variable' || type === 'autocomplete') {
        return VariableInputControl  // 变量选择单独处理
    }
    return controlMap[type] || controlMap.str  // 查表，fallback 到字符串
})
```

**条件显隐 `visible_if`**:
```js
// config 示例: { visible_if: { field: 'gray_scale', operator: 'eq', value: true } }
switch (operator) {
    case 'eq': return targetValue === value
    case 'ne': return targetValue !== value
    case 'in': return Array.isArray(value) && value.includes(targetValue)
}
```

**挂载的对话框**:
- `FileBrowser` — 选图片/文件、保存截图
- `ScreenshotTool` — 调用后端截图，选择点/区域/模板
- `ConditionDialog` — 打开条件编辑器（分支节点、逻辑检查节点用）

### 6.2 controls/ — 原子控件库

**文件**: `frontend/src/components/controls/index.js` 中 `controlMap` 维护映射表：

| type 值 | 控件组件 | 用途 |
|---------|---------|------|
| `str` / `string` | ControlString | 单行文本 |
| `textarea` | ControlTextarea | 多行文本 |
| `int` / `float` / `number` | ControlNumber | 数字输入 |
| `slider` | ControlSlider | 滑块 |
| `bool` / `switch` | ControlSwitch | 布尔开关 |
| `select` | ControlSelect | 下拉选择 |
| `radio` | ControlRadioGroup | 单选按钮组 |
| `window_select` | ControlWindowSelect | 窗口句柄选择器 |
| `file` | ControlFileHover | 文件选择（模板图片） |
| `list_int / region / list_int2 / list_int4` | ControlCoordPicker | 坐标/区域拾取（2 点或 4 点） |
| `dict` | ControlDict | 字典键值对 |
| `condition_list_editor / branch_candidate_editor` | ControlConditionList | 条件列表（多条 AND） |
| `margin4` | Margin4Control | 4 向边距（上右下左） |
| `size2` | Size2Control | 宽高尺寸 |
| `variable` | VariableInputControl | 变量名选择 + 自动补全 |

**新增控件的步骤**:
1. 在 `controls/` 目录创建 `ControlXxx.vue`，Props 接收 `config / modelValue / label / context`
2. 实现 `emit('update:modelValue', newValue)` 双向绑定
3. 在 `controls/index.js` 的 `controlMap` 中注册 type → 组件映射

### 6.3 FormSchemaEditor — 客户表单 Schema 编辑器

**文件**: `frontend/src/components/schema/FormSchemaEditor.vue`

供开发者（自动化作者）可视化配置暴露给最终用户（Player 端）的表单面板。

**Schema 结构**:
```js
{
  form_title: "弹弹堂挂机助手配置",
  groups: [
    {
      group_title: "挂机功能选择",
      fields: [
        {
          label: "刷日常副本",
          target: "$var.daily_dungeon_enabled",  // 绑定到全局变量
          ui_type: "switch",                      // 控件类型
          default: true,
          help: "开启后自动进入日常副本"
        },
        {
          label: "刷图次数",
          target: "$var.dungeon_count",
          ui_type: "number",
          min: 1, max: 999, default: 10
        },
        {
          label: "难度选择",
          target: "$var.dungeon_difficulty",
          ui_type: "select",
          options: [
            { label: "简单", value: "easy" },
            { label: "困难", value: "hard" }
          ]
        }
      ]
    }
  ]
}
```

**支持的 ui_type**: `checkbox_group / select / str / number / slider / switch`

**一键生成**: `autoGenerateFromVars()` 可从蓝图已定义的全局变量自动生成表单。

### 6.4 PlayerFormRenderer — 运行端表单渲染

**文件**: `frontend/src/components/player/PlayerFormRenderer.vue`

在 Player 端（`views/PlayerView.vue`）根据 FormSchemaEditor 生成的 Schema 渲染最终用户填写的表单。

**特点**:
- 与后端 `/player` API 协作，启动时拉取表单 Schema 和当前配置值
- 动态计算 `visible_if` 条件显隐
- 修改即自动保存（防抖）
- 不包含 ParamRenderer 的复杂控件（截图/条件对话框等），只渲染最终用户能理解的 6 种基础 UI

## 7. 条件判断系统

条件系统用于逻辑检查节点（logic_check）和分支节点（branch），支持 **5 大条件类型**。

### 7.1 ConditionDialog — 条件编辑对话框

**文件**: `frontend/src/components/conditions/ConditionDialog.vue`

两种模式：
- 普通模式（logic_check 节点）：单条条件
- 分支模式（branch 节点）：条件 + 跳转目标配置（`show-jump-config` prop）

**UI 结构**:
1. 顶部条件类型下拉（5 选 1）
2. Schema 驱动的参数表单：遍历 `CONDITION_SCHEMAS[type].params`，委托给 `ParamRenderer`
3. 灰度阈值滑块做了定制 UI（实时显示数值 + 提示文案）
4. 底部取消/保存按钮

### 7.2 conditionSchemas — 5 大条件类型 Schema

**文件**: `frontend/src/components/conditions/conditionSchemas.js`

#### 类型 1：image_exists — 屏幕/区域存在指定图片（图像判定）

**核心参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `exist_mode` | select | `exists` / `not_exists` — 存在或不存在 |
| `image_source` | file | 模板图片路径 |
| `gray_scale` | bool | 是否灰度二值化处理（去背景干扰） |
| `gray_threshold` | int | 0-255，二值化阈值（仅 gray_scale=true 时显示） |
| `threshold` | int | 匹配相似度 1%-100%，默认 85% |
| `region_type` | select | `fullwindow` 整个面板 / `recorded` 录制区域 / `custom` 自定义 |
| `region_value` | list_int4_picker | 区域坐标（仅 recorded/custom 时显示） |

#### 类型 2：text_contains — 屏幕/区域包含指定文本（OCR 判定）

**核心参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `exist_mode` | select | `contains` / `not_contains` / `equals` |
| `target_text` | str | 期望对比的文本，支持 `{var_name}` 变量占位 |
| `image_source` | file | OCR 文本视角模板（可选，限定识别区域） |
| `gray_scale` / `gray_threshold` | bool/int | 同图像判定 |
| `region_type` / `region_value` | — | 识别区域 |

#### 类型 3：variable_check — 变量数值/逻辑比较

**核心参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `variable_name` | variable | 从已有变量列表中选择比较源 |
| `operator` | select | `eq / ne / gt / gte / lt / lte / contains` |
| `compare_value` | str | 对比值，支持数字/字符串/`{var_name}` |

#### 类型 4：window_state — 指定窗口状态

**核心参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `window_title` | window_select | 从当前打开的窗口列表选择 |
| `state_check` | select | `exists` 存在 / `not_exists` 不存在 / `active` 前台激活 |

#### 类型 5：file_exists — 本地文件/文件夹是否存在

**核心参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `file_path` | str | 绝对路径，如 `D:/data/config.json` |
| `check_type` | select | `exists` / `not_exists` |

**扩展新条件类型的步骤**:
1. 在 `conditionSchemas.js` 的 `CONDITION_SCHEMAS` 对象中新增一项，定义 `label` 和 `params`
2. 在后端 `core/conditions/handlers/` 中实现对应的 handler 类（继承 `BaseCondition`）
3. 在 `ConditionDialog.vue` 类型下拉中添加 `<el-option>`

## 8. 图标规范

**强制规范：统一使用 `lucide-vue-next`，禁止在 UI 中使用 emoji。**

### 原因
- emoji 在不同操作系统/终端渲染不一致，导致 UI 错乱
- 日志中 emoji 会导致 CI 终端和 grep 检索乱码
- lucide 是矢量 SVG，支持 `size` 和 `color` 属性动态调整，符合主题系统

### 使用方式

```vue
<script setup>
import { Play, Pause, Square, Settings, Plus } from 'lucide-vue-next'
</script>

<template>
    <button @click="run">
        <Play :size="16" /> 运行
    </button>
</template>
```

### 常用图标清单

| 语义 | 推荐图标 |
|------|---------|
| 运行/开始 | Play |
| 暂停 | Pause |
| 停止 | Square |
| 单步跳过 | SkipForward |
| 单步进入 | ArrowDownToLine |
| 单步跳出 | ArrowUpFromLine |
| 断点 | CircleDot（实心）/ CircleDashed（空心） |
| 设置 | Settings |
| 添加 | Plus |
| 删除 | Trash2 |
| 保存 | Save |
| 编辑 | Pencil |
| 刷新 | RefreshCw |
| 搜索 | Search |
| 展开/折叠 | ChevronDown / ChevronRight |

**例外**:
- 执行日志消息中的状态 emoji（✅ / ⏸ / ❌ / ⛔）仅用于执行 Store 推送的日志字符串，不涉及 UI 组件图标，属于文本内容，允许保留。

## 9. 日志规范

**文件**: `frontend/src/utils/logger.js`

使用 logger.js 统一输出，前缀为 ASCII 文本，不使用 emoji。

### 日志级别

| 级别 | 前缀 | 方法 | 典型用途 |
|------|------|------|---------|
| DEBUG | `[DBG]` | `logger.debug(tag, ...args)` | 详细调试信息：变量内容、函数入参出参 |
| INFO | `[INF]` | `logger.info(tag, ...args)` | 关键流程节点：启动任务、加载项目、保存成功 |
| WARN | `[WRN]` | `logger.warn(tag, ...args)` | 可恢复异常：SSE 断开、轮询失败、配置缺失 |
| ERROR | `[ERR]` | `logger.error(tag, ...args)` | 严重错误：API 调用失败、数据解析异常 |
| GROUP | `[RUN]` | `logger.group(tag, title, cb)` | 分组追踪复杂流程（如渲染一帧画布） |
| TRACE | `[TRC]` | `logger.trace(tag, msg)` | 附带调用栈的深度追踪 |

### 示例代码

```js
import { logger } from '@/utils/logger'

const TAG = 'WorkflowCanvas'

function onNodeDrop(node) {
    logger.debug(TAG, '节点拖放', { nodeId: node.node_id, x: node.x, y: node.y })
    if (!validatePosition(node)) {
        logger.warn(TAG, '节点位置超出画布边界，已自动修正')
    }
    try {
        saveToStore(node)
        logger.info(TAG, `节点 ${node.node_id} 位置已更新`)
    } catch (err) {
        logger.error(TAG, '保存节点失败', err)
    }
}
```

### 运行时控制

开发环境默认 DEBUG 级别，生产环境 WARN。可在浏览器控制台临时调整：

```js
window.__LOG_LEVEL__ = 'INFO'   // 只显示 INFO/WARN/ERROR
window.__LOG_LEVEL__ = 'DEBUG'  // 全部显示
```

## 10. 开发命令

在 `frontend/` 目录下执行。

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

Vite 默认端口 5173，支持 HMR 热更新。需同时启动后端 `api.py`（默认端口 8000），`vite.config.js` 中配置了 `/api` 代理到后端。

### 生产构建

```bash
npm run build
```

输出目录 `frontend/dist/`，产物可由后端 Flask 静态托管。

### 代码检查与自动修复

```bash
npx eslint "src/**/*.{vue,js}" --fix
```

或使用 npm script:

```bash
npm run lint          # 检查 + 自动修复
npm run lint:check    # 仅检查，不修复（CI 用）
npm run format        # Prettier 格式化
```

### 测试

```bash
npm test              # 运行全部测试（vitest run）
npm run test:watch    # 监听模式（开发用）
```

## 11. 测试

### 测试框架配置

**文件**: `frontend/vitest.config.js`

```js
{
  test: {
    environment: 'jsdom',     // 浏览器 DOM 环境
    globals: true,            // 全局 describe/it/expect
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html']
    }
  },
  resolve: {
    alias: { '@': './src' }   // 与 vite.config.js 保持一致的 @ 别名
  }
}
```

### 测试目录

```
frontend/src/utils/__tests__/
├── errorHandler.test.js    # 全局错误处理器测试
└── storage.test.js         # localStorage 封装测试
```

### 编写测试示例

以 `storage.test.js` 为模板：

```js
import { describe, it, expect, beforeEach } from 'vitest'
import { saveToStorage, loadFromStorage } from '@/utils/storage'

describe('storage util', () => {
    beforeEach(() => localStorage.clear())

    it('should save and load string value', () => {
        saveToStorage('key', 'value')
        expect(loadFromStorage('key')).toBe('value')
    })

    it('should return default when key missing', () => {
        expect(loadFromStorage('nonexistent', 'fallback')).toBe('fallback')
    })
})
```

**测试组件时**，使用 `@vue/test-utils` 的 `mount()` 或 `shallowMount()`，配合 jsdom 环境。
