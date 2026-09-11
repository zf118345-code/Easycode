# Windows Player 安装与卸载

状态：`Approved`（生产 Authenticode 与无开发环境客户机仍属于外部放行证据）

## 1. 产品边界

Windows Player 的安装器使用当前用户安装，不请求管理员权限，默认安装到 `%LOCALAPPDATA%\Programs\EasyCode\Products\<product_id>`。自动化宿主 `EasycodePlayer.exe` 则按 ADR-114 在每个实例启动边界声明 `requireAdministrator` 并触发一次 UAC；安装权限与运行权限不得混为一谈，流程执行途中不得静默提权。程序数据、方案、日志和录制位于独立的 `%LOCALAPPDATA%\EasyCode` 数据根；升级和普通卸载不得删除它们。机器级安装、企业 MSI、Microsoft Store 和运行途中自动提权不属于首个正式版本。

安装介质包含一个 EasyCode 安装程序和一个严格的 `easycode-windows-application-v1` 应用归档。介质清单同时锁定安装程序与应用归档的文件名、长度和 SHA-256；归档内部继续逐文件验证清单、长度、哈希、路径和唯一入口。`scripts/build_vnext_player.py` 的冻结工作根和 `scripts/build_windows_installer.py` 的安装器工作根默认都在 D 盘；六个验收项目必须复用同一冻结 Runtime 目录，不允许按项目重新冻结后仍称为同一候选。生产发布还必须对安装程序、Player、更新助手及原生二进制执行 Authenticode 签名；开发签名候选不能冒充生产安装包。

## 2. 需求

- `REQ-WIN-INSTALL-001`：用户双击安装程序后，在 EasyCode 自有界面看到产品名、版本、安装位置和“创建桌面快捷方式”；只有 Windows 的文件/权限真实边界可以出现系统界面。
- `REQ-WIN-INSTALL-002`：安装前验证外层归档哈希及内层严格清单，任何篡改、缺失、额外文件、符号链接、越界路径或产品/发布身份不一致均在改动安装目录前失败。
- `REQ-WIN-INSTALL-003`：先解包到安装根同卷暂存目录，验证成功后整目录替换；升级失败恢复上一目录，不留下新旧文件混装。
- `REQ-WIN-INSTALL-004`：安装后创建当前用户开始菜单入口，可选创建桌面入口，并写入 `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall`；入口直接启动 `EasycodePlayer.exe` 和锁定的项目包/信任根，不依赖 `.bat`、Python 或 IDE。
- `REQ-WIN-INSTALL-005`：安装完成后把该签名产品和默认实例登记到当前用户 Player Hub；登记失败保留可直接运行的安装并给出修复动作，不伪报计划/批量启动已就绪。
- `REQ-WIN-INSTALL-006`：卸载程序只删除安装标记锁定的精确产品目录、快捷方式和卸载注册项。默认保留用户数据；只有用户另行明确勾选才删除该产品的数据，且删除前再次显示不可恢复范围。
- `REQ-WIN-INSTALL-007`：已安装版本的在线升级继续交给外置 `EasycodeUpdateHelper.exe` 完成健康探针与回滚；再次运行安装程序用于首次安装、离线升级或修复，两条路径使用同一应用归档格式。
- `REQ-WIN-INSTALL-008`：安装、升级、修复、取消、磁盘不足、文件占用、哈希失败、回滚和卸载都写入 `%LOCALAPPDATA%\EasyCode\Installer\logs\latest.jsonl` 的有界结构日志；超过 1 MiB 时只轮换一个 `previous.jsonl`，不记录方案值、项目输入或文件正文。

## 3. 验收

自动验证覆盖严格归档、外层锁定、同卷暂存、升级回滚、安全卸载边界、快捷方式目标、HKCU 卸载项和数据保留。真实 Windows 验收必须在没有系统 Python、IDE 和开发后端的当前用户环境完成首次安装、运行、离线修复、升级、卸载和重装；生产发布另需 Authenticode 和干净客户机证据。
