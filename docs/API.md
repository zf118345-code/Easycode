# Easycode API 接口文档

> 自动生成于 Phase 2 优化阶段。FastAPI 自带 Swagger UI 可访问 `/docs`。

## 统一响应格式

```json
{
  "code": 0,
  "data": {},
  "message": "success"
}
```

## 错误码

| 错误码 | 说明 |
|--------|------|
| 0 | 成功 |
| 100 | 内部服务器错误 |
| 101 | 请求参数错误 |
| 102 | 资源不存在 |
| 104 | 数据校验失败 |
| 200 | 未授权访问 |
| 201 | 禁止访问 |
| 400 | 服务不可用 |
| 500 | 蓝图加载失败 |
| 501 | 蓝图保存失败 |
| 502 | 任务不存在 |
| 503 | 执行失败 |
| 504 | 执行记录不存在 |
| 505 | 项目路径无效 |
| 600 | 文件不存在 |
| 603 | 检测到路径遍历攻击 |

## 接口清单

### 1. 系统 (system_router)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/params` | 获取全局节点参数定义 |

### 2. 项目工作区 (project_workspace_router)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/workspaces/active` | 当前唯一活动项目与切换阻塞项 |
| GET | `/api/workspaces/recent` | 全局最近项目（不存入子项目） |
| POST | `/api/workspaces/inspect` | 检查任意文件夹，不隐式写入 |
| POST | `/api/workspaces/open` | 打开或经确认初始化项目 |
| POST | `/api/workspaces/repair` | 备份后修复损坏项目 |
| POST | `/api/workspaces/close` | 冲刷保存后关闭项目 |
| GET | `/api/workspaces/changes` | 检测项目文件的外部修改 |
| POST | `/api/workspaces/acknowledge` | 确认已处理当前磁盘版本 |

### 3. 蓝图与任务 (blueprint_router)

除工作区打开/检查和 Player 接口外，所有项目请求都必须携带
`X-Workspace-Id` 与 `X-Workspace-Generation`；请求体中的旧式 `project_path`
只做一致性校验，不能决定实际读写目录。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/blueprint` | 获取完整蓝图 |
| POST | `/api/blueprint/save` | 保存蓝图 |
| GET | `/api/tasks` | 获取任务列表 |
| GET | `/api/tasks/{task_id}` | 获取单个任务 |
| PUT | `/api/tasks/{task_id}` | 更新任务 |
| POST | `/api/tasks` | 创建任务 |
| DELETE | `/api/tasks/{task_id}` | 删除任务 |
| GET | `/api/tasks/{task_id}/nodes` | 获取任务节点列表 |
| POST | `/api/tasks/order` | 保存任务排序 |

### 3. 执行引擎 (execution_router)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/run` | 运行任务（支持断点） |
| GET | `/api/execution/{execution_id}` | 获取执行状态 |
| POST | `/api/execution/{execution_id}/stop` | 停止执行 |
| GET | `/api/execution/{execution_id}/stream` | SSE 日志流 |
| POST | `/api/execution/{execution_id}/pause` | 暂停执行 |
| POST | `/api/execution/{execution_id}/resume` | 恢复执行 |
| POST | `/api/execution/{execution_id}/step` | 单步执行 |
| GET | `/api/execution/{execution_id}/debug` | 获取调试状态 |
| GET | `/api/execution/{execution_id}/variables` | 获取变量快照 |
| POST | `/api/execution/{execution_id}/breakpoints` | 批量设置断点 |
| POST | `/api/execution/{execution_id}/breakpoints/add` | 添加断点 |
| POST | `/api/execution/{execution_id}/breakpoints/remove` | 移除断点 |

### 4. 导出与播放器 (build_router)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/exporter/schema` | 获取表单 Schema |
| POST | `/api/exporter/schema` | 保存表单 Schema |
| POST | `/api/exporter/build` | 打包导出 |
| POST | `/api/exporter/compile-exe` | 编译 Player EXE |
| GET | `/api/player/init` | Player 初始化 |
| GET | `/api/player/providers` | 获取 Provider 选项 |
| POST | `/api/player/config` | 保存用户配置 |
| POST | `/api/player/run` | 运行 Player |
| POST | `/api/player/stop` | 停止 Player |

### 5. 模板与视觉 (vision_router)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/templates/tree` | 获取模板目录树 |
| GET | `/api/templates/preview` | 模板预览 |
| GET | `/api/image/thumb` | 获取图片缩略图 |
| POST | `/api/templates/mkdir` | 创建模板文件夹 |
| GET | `/api/templates/impact` | 删除/移动前检查引用影响 |
| POST | `/api/templates/delete` | 事务删除并清空节点资源与坐标 |
| POST | `/api/templates/move` | 移动或重命名，稳定资源 ID 不变 |
| GET | `/api/templates/trash` | 列出项目资源回收站 |
| POST | `/api/templates/trash/{id}/restore` | 恢复资源与元数据，不自动重绑节点 |
| GET | `/api/regions` | 获取区域列表 |
| POST | `/api/regions` | 保存区域 |
| POST | `/api/ocr/test` | OCR 测试 |
| POST | `/api/image/test` | 图像识别测试 |

### 6. 工作区 (workspace_router)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/screenshot/full` | 全屏截图 |
| POST | `/api/screenshot/crop` | 裁剪截图 |
| GET | `/api/windows` | 获取窗口列表 |
| POST | `/api/context` | 保存工作区上下文 |
| GET | `/api/context` | 获取工作区上下文 |

### 7. 能力函数 (capability_router)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/capabilities` | 发现内置、项目和用户级能力，返回契约或包错误 |

### 8. 平台运行时 (platform_router)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/PUT/DELETE | `/api/platform/state/{key}` | IDE/Player 持久状态 |
| GET/POST/DELETE | `/api/platform/schedules` | 每日、间隔和单次计划任务 |
| POST | `/api/platform/messages` | 发布本机协同消息 |
| POST | `/api/platform/messages/claim` | 带租期领取本机消息 |
| POST | `/api/platform/messages/{id}/ack` | 确认并删除已处理消息 |
| POST | `/api/platform/leases/acquire|renew|release` | 本机资源租约生命周期 |
| POST | `/api/platform/remote/messages` | 发送跨电脑消息，失败进离线队列 |
| GET | `/api/platform/outbox` | 离线发送队列状态 |
| POST | `/api/platform/coord/messages*` | 令牌保护的协调端消息 API |
| POST | `/api/platform/coord/leases/*` | 令牌保护的跨机资源租约 API |

## 前后端接口对齐状态

- 前端 API 适配器通过 `test_frontend_api_contract.py` 自动与 FastAPI OpenAPI 方法/路径对齐，不再手工维护易失效的端点数量。
- 前端重复调用已收敛：`getExecutionStatus`/`stopExecution` 从 `blueprintApi` 移除，统一使用 `executionApi`
- 后端仅 Player 相关端点（7 个）前端编辑器未调用（由 Player 视图使用）
- 所有原始 dict body 端点已补充 Pydantic Schema 校验
