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
| GET | `/api/projects/verify` | 校验项目路径 |

### 2. 蓝图与任务 (blueprint_router)

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
| GET | `/api/regions` | 获取区域列表 |
| POST | `/api/regions` | 保存区域 |
| POST | `/api/ocr/test` | OCR 测试 |
| POST | `/api/image/test` | 图像识别测试 |

### 6. 工作区 (workspace_router)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/screenshot/full` | 全屏截图 |
| POST | `/api/screenshot/crop` | 裁剪截图 |
| POST | `/api/screenshot` | 截图 |
| GET | `/api/windows` | 获取窗口列表 |
| POST | `/api/context` | 保存工作区上下文 |
| GET | `/api/context` | 获取工作区上下文 |

## 前后端接口对齐状态

- 后端 46 个端点，前端 40 个调用函数
- 前端重复调用已收敛：`getExecutionStatus`/`stopExecution` 从 `blueprintApi` 移除，统一使用 `executionApi`
- 后端仅 Player 相关端点（7 个）前端编辑器未调用（由 Player 视图使用）
- 所有原始 dict body 端点已补充 Pydantic Schema 校验
