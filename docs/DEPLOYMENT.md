# Easycode 部署与运维文档

## 环境要求

| 组件 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.10+ | 后端运行时，建议 3.11 |
| Node.js | 18+ | 前端构建与开发，建议 20 LTS |
| 操作系统 | Windows | **仅支持 Windows**，因自动化能力依赖 `pywin32` / `pyautogui` |

---

## 后端部署

### 依赖安装

项目提供两种依赖管理方式，二选一即可：

**方式一：pip（推荐快速上手）**

```bash
pip install -r requirements.txt
```

**方式二：Poetry（推荐开发环境）**

```bash
pip install poetry
poetry install
```

### 环境变量配置

复制项目根目录下的 `.env.example` 为 `.env`，并根据实际环境修改：

```bash
copy .env.example .env
```

#### 关键配置项

| 环境变量 | 必填 | 说明 |
|---------|------|------|
| `APP_ENV` | 是 | 运行环境，取值 `dev` 或 `prod` |
| `EASYCODE_SIGN_SECRET` | 生产必填 | 蓝图 HMAC-SHA256 签名密钥，建议 32 字节以上随机字符串 |
| `EASYCODE_MASTER_SALT` | 生产必填 | 资产加密 PBKDF2 Salt，建议 16 字节以上随机字符串 |
| `EASYCODE_CORS_ORIGINS` | 按需 | 允许的前端来源，逗号分隔，如 `http://a.com,http://b.com` |
| `EASYCODE_RATE_LIMIT` | 按需 | 全局速率限制（slowapi 格式），默认 `120/minute` |

> **密钥生成示例**
> ```bash
> # 生成 SIGN_SECRET
> python -c "import secrets; print(secrets.token_urlsafe(48))"
>
> # 生成 MASTER_SALT
> python -c "import secrets; print(secrets.token_urlsafe(32))"
> ```

#### 开发环境 vs 生产环境行为差异

| 配置项 | `APP_ENV=dev` | `APP_ENV=prod` |
|-------|--------------|---------------|
| SIGN_SECRET 未设置 | 使用内置兜底密钥（仅调试） | **启动失败**，禁止使用兜底 |
| MASTER_SALT 未设置 | 使用内置兜底 Salt（仅调试） | **启动失败**，禁止使用兜底 |
| CORS_ORIGINS 未设置 | 允许所有来源 `['*']` | 仅允许本机回环地址 |

### 启动服务

**方式一：直接运行入口脚本**

```bash
python main.py
```

**方式二：uvicorn 命令（推荐生产）**

```bash
# 使用 pip 依赖
uvicorn api.app:create_app --host 0.0.0.0 --port 8000

# 使用 Poetry 虚拟环境
poetry run uvicorn api.app:create_app --host 0.0.0.0 --port 8000
```

**常用 uvicorn 参数**
- `--workers N`：多进程模式（Windows 下建议 `--workers 1`）
- `--log-level info`：日志级别
- `--ssl-keyfile` / `--ssl-certfile`：HTTPS 证书

### 接口文档

服务启动后，在浏览器访问：

- **Swagger UI**：http://localhost:8000/docs
- **ReDoc**：http://localhost:8000/redoc
- **OpenAPI JSON**：http://localhost:8000/openapi.json

---

## 前端部署

### 依赖安装

```bash
cd frontend
npm install
```

> CI 环境使用 pnpm：`pnpm install`

### 开发模式

启动 Vite 开发服务器，支持热更新：

```bash
npm run dev
```

默认监听 `http://localhost:5173`，Vite 会自动代理 `/api` 请求到后端（见 `vite.config.js`）。

### 生产构建

```bash
npm run build
```

构建产物输出到 `frontend/dist/` 目录，可直接部署到任意静态文件服务器。

### 预览构建结果

```bash
npm run preview
```

在本地预览生产构建的静态文件，默认端口 4173。

### Nginx 配置示例

将前端静态文件与后端 API 通过反向代理统一部署：

```nginx
server {
    listen 80;
    server_name easycode.example.com;

    # 前端静态文件
    root /var/www/easycode/frontend/dist;
    index index.html;

    # Vue Router history 模式支持
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 反向代理
    location /api/ {
        proxy_pass         http://127.0.0.1:8000/api/;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        # WebSocket 支持（如需要）
        proxy_http_version 1.1;
        proxy_set_header   Upgrade           $http_upgrade;
        proxy_set_header   Connection        "upgrade";

        # 超时配置（自动化执行可能耗时较长）
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
```

> **HTTPS 建议**：生产环境请务必配置 TLS 证书（Let's Encrypt 等），将 `listen 80` 重定向至 `listen 443 ssl`。

---

## 测试运行

### 后端测试

先安装测试依赖：

```bash
pip install pytest pytest-asyncio httpx uvicorn
```

运行测试：

```bash
# 运行全部测试
pytest -v

# 运行指定文件
pytest tests/test_blueprint_api.py -v

# 生成覆盖率报告（需安装 pytest-cov）
pytest --cov=core --cov=api --cov-report=html
```

### 前端测试

```bash
cd frontend

# 运行全部测试
npx vitest run

# 监听模式（开发时）
npx vitest

# 覆盖率报告
npx vitest run --coverage
```

---

## CI/CD

项目已内置 GitHub Actions 工作流：`.github/workflows/ci.yml`，在 push / PR 到 `main` 或 `canvas-flow` 分支时自动触发。

### 检查项

| Job | 运行环境 | 检查内容 |
|-----|---------|---------|
| `frontend-tests` | Ubuntu Latest | `pnpm install` → `vitest run` → `vite build` |
| `backend-tests` | Windows Latest | `poetry install` → `pytest tests/ -v` |

### 本地复现 CI 检查

```bash
# 后端：Ruff 代码风格检查
ruff check core/ api/ tests/

# 后端：测试
pytest tests/ -v

# 前端：ESLint 检查
cd frontend && npx eslint "src/**/*.{vue,js}"

# 前端：构建验证
cd frontend && npm run build
```

---

## 生产环境注意事项

### 1. 密钥与加密

- **必须**设置 `EASYCODE_SIGN_SECRET` 与 `EASYCODE_MASTER_SALT`，严禁依赖开发兜底值
- 密钥应通过部署平台的 Secrets 管理（Docker Secrets、K8s Secrets、云厂商密钥服务），禁止硬编码或写入 `.env` 后提交仓库
- 建议定期轮换密钥，轮换后需重新导出所有加密蓝图资产

### 2. 跨域（CORS）配置

- `EASYCODE_CORS_ORIGINS` 需**精确列出**前端实际访问域名，不要使用通配符 `*`
- 示例：`https://easycode.example.com,https://www.example.com`
- 包含端口号（非 80/443 时）：`http://192.168.1.100:8080`

### 3. 速率限制

- 默认 `120/minute`，根据实际并发量调整 `EASYCODE_RATE_LIMIT`
- 格式参考 slowapi：`60/minute`、`10/second`、`1000/hour`
- 高并发场景建议前置 Nginx 做更细粒度限流

### 4. 反向代理与 HTTPS

- 不要直接暴露 uvicorn 到公网，前置 Nginx / Caddy 等反向代理
- 反向代理负责：静态文件承载、HTTPS 终止、GZIP 压缩、HTTP/2、限流
- 示例 Caddyfile：
  ```caddy
  easycode.example.com {
      root * /var/www/easycode/frontend/dist
      try_files {path} /index.html
      file_server

      handle /api/* {
          reverse_proxy 127.0.0.1:8000
      }
  }
  ```

### 5. 日志与监控

- uvicorn 日志建议落盘并配置轮转：
  ```bash
  uvicorn api.app:create_app \
      --host 0.0.0.0 --port 8000 \
      --log-level info \
      --log-config logging.json
  ```
- 推荐使用 `logrotate`（Linux）或 PowerShell 定时脚本（Windows）按大小/日期切割日志
- 关键监控指标：请求量、5xx 错误率、API 响应延迟、自动化执行成功率
- Windows 环境可通过「性能监视器」采集 CPU / 内存 / GDI 对象数

### 6. Windows 桌面权限

- 自动化能力（截图、点击、OCR、窗口操作）依赖桌面会话
- **建议以管理员身份运行**终端后启动服务，可获得更高的窗口控制与自动化权限
- 不要在 Windows 服务（Service）模式下运行，Session 0 隔离会导致桌面交互失败
- 远程桌面场景：断开 RDP 会话前请使用 `tscon` 保留活跃会话，否则截图/自动化将失效
  ```cmd
  tscon %sessionname% /dest:console
  ```

---

## 项目验证清单

部署完成后，请按以下清单逐项验证：

| 序号 | 检查项 | 验证方法 | 预期结果 |
|------|--------|---------|---------|
| 1 | 后端启动无报错 | 执行 `python main.py` | 控制台输出 `Uvicorn running on http://0.0.0.0:8000`，无 Exception / Traceback |
| 2 | Swagger 可访问 | 浏览器打开 `http://localhost:8000/docs` | 显示 FastAPI Swagger UI，接口列表可展开，「Try it out」可用 |
| 3 | 后端测试全通过 | 执行 `pytest tests/ -v` | **93 条全部通过**，`passed` 数量与 CI 一致，无 error / failure |
| 4 | 前端生产构建成功 | `cd frontend && npm run build` | 无报错退出码 0，`dist/` 目录生成 `index.html` 与 `assets/` 资源 |
| 5 | IDE 打开示例项目 | 前端登录后点击「打开项目」，选择内置示例项目 | 工作流画布正常加载，节点可见，连线正确，无控制台报错 |
| 6 | 截图功能正常 | 在画布中添加「截图」节点，执行当前节点 | 返回图片数据，截图内容与真实桌面一致 |
| 7 | OCR 识别正常 | 添加「OCR 识别」节点，框选含文字的屏幕区域 | 正确返回识别出的文本内容 |
| 8 | 图片识别正常 | 添加「图像识别」节点，上传模板图并点击匹配 | 正确返回匹配坐标与置信度，无 OpenCV 异常 |
| 9 | 蓝图加密导出 | 在 IDE 中导出受签名保护的蓝图文件 | 文件可正常重新导入，签名校验通过，篡改后导入失败 |

> **注**：第 6~8 项需要真实 Windows 桌面环境，无法在 CI 无头环境中验证。
