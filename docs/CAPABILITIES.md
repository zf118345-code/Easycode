# EasyCode 能力函数开发指南

## 定位

能力函数用于承载“节点不适合表达，但又必须被节点流调用”的复杂逻辑。每个能力都有稳定 ID、版本、类型化输入/输出、权限、超时与幂等声明。画布仍只看到一个语义清晰的“调用能力”节点。

## 目录与清单

```text
<project>/capabilities/demo/
├─ capability.json
├─ main.py
└─ helper.py
```

```json
{
  "package_id": "demo",
  "version": "1.0.0",
  "functions": [
    {
      "id": "demo.calculate",
      "name": "计算示例",
      "entry": "main.py:run",
      "description": "返回两个整数之和",
      "inputs": [
        {"name": "left", "type": "int", "required": true},
        {"name": "right", "type": "int", "default": 0}
      ],
      "outputs": [{"name": "total", "type": "int"}],
      "permissions": [],
      "timeout_ms": 30000,
      "idempotent": true
    }
  ]
}
```

```python
from .helper import add


def run(context, **inputs):
    if context.cancelled:
        return {"success": False, "code": "CANCELLED", "message": "已停止"}
    total = add(inputs["left"], inputs["right"])
    context.log(f"计算完成: {total}")
    return {
        "success": True,
        "code": "OK",
        "message": "",
        "data": {"total": total}
    }
```

项目包可使用相对导入。打开左侧“能力库”只读取清单并校验入口语法，项目 Python 代码只在真正运行节点时加载。项目能力与公共能力在独立子进程中执行；超时或停止任务会终止该子进程，避免失控代码继续占用 IDE/Player。平台内置能力为了低延迟仍在引擎进程内执行。

能力库右上角“创建能力”可生成当前项目能力或公共能力的标准目录、清单和入口文件。当前项目能力位于 `<project>/capabilities`；公共能力默认位于 `%LOCALAPPDATA%/EasyCode/capabilities`，也可用 `EASYCODE_CAPABILITY_HOME` 指定。

## 输入与输出绑定

“调用能力”节点的输入可以是常量、`$var.name` / `$ctx.name` 变量，或以 `=` 开头的安全表达式。输出使用 `data` 中的字段路径绑定到 `$var.name` / `$ctx.name`。必填参数、未声明参数、无效输出目标和版本不匹配都会在发布前检查中拦截。

只有声明 `idempotent: true` 的能力才允许节点自动重试。自定义能力超时后工作进程会被强制终止；仍建议长循环检查 `context.cancelled`，以便在正常取消路径上主动释放业务资源。平台内置能力使用协作式取消，必须遵守取消信号。

## 权限与上下文

当前标准权限包括：

- `screen.read`：区域 OCR。
- `input.gesture`：定向滑动。
- `variables.write`：写入当前流程变量。
- `platform.state.read` / `platform.state.write`：跨次执行持久状态。
- `platform.message`：本机 IDE/Player 消息。
- `platform.lease`：本机资源租约。
- `network.coordinator`：访问受令牌保护的局域网协调端。

能力通过 `CapabilityContext` 使用已声明的标准适配器。工作进程提供故障与生命周期隔离，但项目能力本质上仍是本机 Python 代码，并不是防恶意代码的操作系统安全沙盒；发布前检查会明确提示开发者审查。

## 内置示例：`vision.collect_list`

该能力展示一个复杂功能如何不破坏节点流：它在指定区域做 OCR，按列规则拆分行，滑动到下一页，去重，并在页面重复或达到上限时停止。它是平台示例，不包含任何具体游戏知识。

主要输入：`region`、`reference_size`、`columns`、`key_fields`、`swipe_start`、`swipe_end`、`max_pages`、`hold_after_ms`。输出：`items`、`pages_scanned`、`stop_reason`。

## 平台内置能力

- 状态：`platform.state.get` / `platform.state.set`
- 本机消息：`platform.message.publish` / `claim` / `ack`
- 本机租约：`platform.lease.acquire` / `renew` / `release`
- 跨电脑消息：`platform.remote.publish` / `claim` / `ack`
- 跨电脑租约：`platform.remote.lease.acquire` / `renew` / `release`

消息采用“领取 + 租期 + 确认”语义，消费者崩溃后未确认消息会重新可见。租约用于防止两个 Player 同时操作同一账号、模拟器或任务分片。

IDE 左侧“运行服务”与 Player 顶部“运行服务”复用同一面板，按运行范围分别管理计划、持久状态、本机消息、本机租约、跨电脑消息和远程租约。远程消息发送失败进入当前范围的 outbox 自动补发；领取、确认和租约具有时效性，网络失败时会明确报错而不会伪报成功。
