# EasyCode Automation Studio

EasyCode 是面向 Windows 软件、安卓模拟器和 Android 本机的结构化自动化开发环境。开发者从函数库插入能力，在纵向语句工作区组织执行顺序，并通过右侧类型化表单完成配置，再发布为不要求最终用户安装 Python 的独立 Player。项目函数以 ProgramDocument 为唯一可编辑事实；项目特有能力通过受控扩展进入同一编译与发布闭包。Player 本地优先：未显式使用公网能力的项目不依赖公网、IDE、EasyCode 云或单独安装的开发后端。首个正式版本的完成门同时包含 Windows/ADB Player 与可脱离电脑独立运行的签名 Android APK；在真实宿主和真机 Harness 通过前，Android 入口保持不可用且不得宣称已经交付。

## 开发运行

Python 依赖的唯一权威来源是 `pyproject.toml` 与 `poetry.lock`，支持 Python 3.10–3.12。首次准备或锁文件变化后执行：

```powershell
poetry sync
npm --prefix frontend ci
```

后端：

```powershell
.\.venv312\Scripts\python.exe api\app.py --mode dev
```

前端：

```powershell
npm --prefix frontend run dev
```

默认前端地址为 `http://localhost:5173/`。如果端口被占用，不要重复保留多个 Vite 服务；先核验占用进程。

## 文档

- [产品规格](PRODUCT.md)
- [文档索引](docs/README.md)
- [目标架构](docs/ARCHITECTURE.md)
- [UI 与交互规范](design.md)
- [测试 Harness](docs/TEST_HARNESS.md)
- [架构决策](docs/DECISIONS.md)
- [结构化程序模型](docs/vnext/PROGRAM_MODEL.md)
- [扩展平台](docs/vnext/EXTENSIONS.md)
- [vNext 细分规范](docs/vnext/README.md)

旧画布测试项目不兼容当前格式。功能实现和发布前必须遵守 `AGENTS.md` 的开工门与完成门。
