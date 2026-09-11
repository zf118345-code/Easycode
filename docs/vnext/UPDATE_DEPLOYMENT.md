# v6 签名更新部署参考

状态：参考实现；用于自建静态 HTTPS Feed 和协议联调，不代表 EasyCode 官方托管已经连接。

## 1. 边界

发布签名在作者受控的 IDE 主机完成。Feed 目录只包含公钥、签名元数据和不可变产物；发布私钥、上传凭据、ProgramDocument、运行方案值、日志、截图、任务结果、设备标识和原始安装分组码都不得进入 Feed。

IDE、Player 应用和项目内容分别使用 `ide`、`player_application`、`project_content` 产品域。客户端 Feed URL 必须指向该域根，例如：

```text
https://updates.example.test/feed/<product_id>/project_content
```

同一 Feed 根可以承载多个产品和产品域，但它们的信任与版本状态不能合并。

## 2. 生成静态 Feed

先在 IDE 作者发布页启用自建更新并保存 `updates.json`。也可以在受控发布机使用命令行初始化仓库：

```powershell
.venv312\Scripts\python.exe scripts\update_feed_v6.py init `
  --root D:\update-feed `
  --product-id <product_id> `
  --domain project_content
```

后续使用同一工具的 `publish-content` 或 `publish-artifact` 子命令发布不可变产物，再用 `rollout`、`required`、`revoke-required` 和 `rotate-online-keys` 管理签名策略。以 `--help` 输出为当前参数事实；不要复制或上传项目外的 DPAPI 密钥目录。

发布目录的稳定布局是：

```text
<repository>/<product_id>/<domain>/
  metadata/root.json
  metadata/timestamp.json
  metadata/snapshot.json
  metadata/targets.json
  metadata/rollout.json
  metadata/policy.json
  metadata/<revision>.<role>.json
  artifacts/<release_id>/<immutable artifact>
```

已发布的 `release_id`、版本化元数据和产物不可原地覆盖。恢复旧业务内容时发布更高序号的修复版本。

## 3. 运行参考服务

参考服务是只读 ASGI 应用：

```powershell
$env:EASYCODE_UPDATE_FEED_ROOT = 'D:\update-feed'
.venv312\Scripts\python.exe -m uvicorn api.update_feed_app:app --host 127.0.0.1 --port 8766
```

生产部署必须由反向代理、对象存储或 CDN 提供有效 HTTPS；不要直接把开发 HTTP 监听暴露到公网。代理必须保留 `ETag`、`If-None-Match`、`Range`、`If-Range`、`Content-Range` 和 HEAD 语义，不得修改响应体。`metadata/*.json` 应短缓存或重新验证；`metadata/versioned/*` 与 `artifacts/*` 可以长期不可变缓存。

参考服务没有登录、上传、签名、VIP、收费、授权、设备舰队、终端心跳或自动遥测。写入与签名由发布工具完成，静态目录可以直接同步到标准 HTTPS 对象存储。

## 4. 客户端配置与迁移

Bundle 内只有启用域才包含 `update/config.json`。配置固定 `product_id`、域、初始 HTTPS Feed URL、可信根和强制策略检查能力，并由 `.ecplayer` 完整性签名覆盖。普通终端不能编辑源 URL；源或镜像迁移必须通过满足旧根和新根阈值的签名根轮换发布。

关闭全部更新后重新发布 Bundle，终端不会创建更新身份、调度器或 UI，也不会执行更新 DNS/TCP/HTTP。仅关闭普通自动检查时，若作者已启用强制策略能力，客户端仍会按披露的低频计划只请求签名策略，不下载产物。

## 5. 平台安装边界

项目内容使用客户端 A/B 槽并在所有相关进程到达安全点后切换。Player 应用包只验证并暂存：Windows 需要真实安装助手承接原子替换和重启恢复；Android APK 需要系统 PackageInstaller 承接用户确认、签名、版本、ABI、权限和数据保留。没有这些平台承接时状态保持 `awaiting_platform_install` 并返回明确 `unavailable`，不得用普通文件复制伪装安装完成。

部署放行前必须按 [`TESTING.md`](TESTING.md) 第 8 节分别记录自动验证、人工验证、未验证、失败和环境阻塞。
