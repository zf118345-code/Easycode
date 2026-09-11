# EasyCode 后端可靠性基线

状态：`Implemented baseline`

适用范围：`api/`、`core/`、Windows IDE/Player 本地服务

最近修订：2026-08-29

## 1. 分层与依赖方向

```text
FastAPI router + Pydantic request contract
                 ↓
application service / workspace manager / runtime coordinator
                 ↓
domain model, compiler, resource and project invariants
                 ↓
filesystem, SQLite, subprocess, Windows/ADB/native infrastructure
```

- Router 只做 HTTP 参数绑定、工作区身份校验、错误翻译和调用编排，不直接实现业务事务。
- `api/contracts/` 是 HTTP 输入事实；禁止在路由中用松散 `dict` 接收有明确结构的写操作。
- 应用服务定义一次完整用例及其锁/事务边界，不把半完成状态暴露给路由。
- 领域层不依赖 FastAPI；可预期的领域错误由边界翻译成稳定错误码。
- 文件、进程、网络和平台调用属于基础设施；必须有超时、取消和 `finally` 清理。

## 2. HTTP 错误与请求追踪

每个请求都接受或生成 `X-Request-ID`，响应原样返回合法请求 ID。日志字段至少包含：

- `event`
- `request_id`
- `method`
- `path`
- `status_code`
- `duration_ms`

失败响应保留历史 `detail` 兼容性，并提供稳定的 `code`、用户可读 `message` 与 `recovery`。校验错误使用 422；身份/版本/幂等冲突使用 409；超时使用 504；未处理异常使用 500，且不会向客户端泄露内部堆栈。

## 3. 严格请求契约

下列高风险写入口使用 `extra='forbid'` 的 Pydantic 模型：

- 项目打开、检查、修复、最近项目和桌面文件对话框。
- 工作流执行、调试单步与断点。
- 导出 Schema、预检、资源包构建、EXE 编译和 Player 运行配置。
- 捕获会话、快照、资源保存、IDE 回填动作。
- 视觉资源目录、登记和区域元数据。
- 扩展骨架、导入、契约刷新和启停。
- 计划任务、消息与远程消息；旧版分布式租约接口仅作为待清理实现事实，不进入 vNext 产品契约。
- vNext 工作区、ProgramDocument 结构命令/保存、Player 发布和运行入口。

拼错或不支持的顶层字段必须在进入服务前返回 422，不能被静默忽略。

## 4. 幂等策略

可能因双击或网络重试而重复产生副作用的入口支持 `Idempotency-Key`：

- 旧版任务运行、导出 Schema 保存、资源包构建、EXE 编译、Player 启动。
- 捕获资源保存与捕获动作回填。
- vNext ProgramDocument 结构命令/保存、运行、Player 表单保存、发布和打包。

同一操作、同一键、同一请求体只执行一次，并重放深拷贝结果；并发重复请求等待首个生产者。相同键配不同请求体返回 `idempotency_conflict`。生产者失败不会永久毒化该键，后续可重新尝试。账本有容量和时间上限，不作为长期业务数据库。

## 5. 项目事务与版本冲突

- 单个 ProgramDocument 命令与保存使用 `expected_revision` / 内容哈希进行乐观并发；冲突返回基线、内存与磁盘比较所需信息，不允许无限 409 或静默覆盖。
- vNext 工作区的资源、目标、Player 表单、扩展、函数元数据和发布共享项目级可重入事务锁。
- 发布报告、Player 构建和打包在同一个项目快照边界内完成，期间不能穿插目标或资源变更。
- 捕获保存资源时加入同一项目事务；获取锁顺序固定，避免项目锁与捕获会话锁互相等待。
- 资源和发布写入先完成校验，再提交事实文件；失败路径必须保留可重试状态。

## 6. 执行、取消与资源释放

- vNext Runtime 使用独立 Worker，支持软取消、取消宽限期和硬超时。
- Windows Worker、扩展隔离进程与 PyInstaller 均按已知 PID 终止整棵子进程树，不扫描或误杀未知进程。
- 扩展 Worker 的 stdin/stdout/stderr 在所有返回路径关闭。
- PyInstaller 最长运行 300 秒；超时返回 504，并在 `finally` 删除构建快照。
- 运行会话结束后释放目标所有权、队列、Worker、日志缓冲和项目资源。

## 7. 契约与并发验证

质量门至少包含：

1. Ruff：`api/`、`core/`、`tests/`。
2. OpenAPI/TypeScript 契约漂移检查。
3. 严格模型未知字段与错误响应契约测试。
4. 并发幂等生产者单次执行测试。
5. 发布/捕获共享事务锁测试。
6. 运行取消、硬超时、扩展超时和 PyInstaller 超时清理测试。
7. 后端全量 pytest，使用 `-p no:cacheprovider` 避免受 Windows `.pytest_cache` 权限污染。

测试必须串行执行重型步骤。当前 Starlette `TestClient` 会发出迁移到 `httpx2` 的上游弃用警告；这是已知依赖迁移项，不影响现有断言，但升级依赖前必须单独建立兼容分支验证。
