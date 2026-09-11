# 第一方扩展包

- 状态：Implemented（真实浏览器仍需发布候选 Windows 宿主验收）
- 日期：2026-09-07

## 共同规则

浏览器 DOM 与 Excel/CSV 都不是核心内置函数。它们由 `scripts/manage_first_party_extension.py` 在目标项目外生成，带 EasyCode 第一方签名，并且只能经过“导入 → 查看权限 → 显式信任 → 密封构建 → 启用 → 写入 lock”的标准生命周期进入项目。测试也不得从仓库源码直接注册函数。

生成可供界面手动导入的包：

```powershell
.\.venv312\Scripts\python.exe scripts\manage_first_party_extension.py browser build --output D:\Temp\EasyCodeBrowserPackage
.\.venv312\Scripts\python.exe scripts\manage_first_party_extension.py excel build --output D:\Temp\EasyCodeTablePackage
```

也可以用 `install --project <项目路径> --scope project` 自动走相同生命周期。默认不预装；用户可以完整体验真实导入流程。

## 浏览器 DOM 包

包 ID：`com.easycode.firstparty.browserdom`

首期提供 Edge/Chrome 启动和连接、打开地址、页面等待、元素等待/点击/填写/选择、文字/属性/表格读取、标签页切换、同源 iframe 定位、页面元素拾取和标签页关闭。实现使用浏览器原生 DevTools Protocol，不在运行期下载驱动或浏览器；浏览器最小化后 DOM 操作仍不依赖屏幕像素。

包只声明本机 `127.0.0.1/localhost:9222` DevTools 连接、启动应用和下载目录写入权限。它不会开放任意公网网络规则，也没有第二套编辑器：函数照常出现在扩展函数库，参数用普通 Control，结果进入普通变量与字段补全。

跨域 iframe、Firefox/Safari、任意 JavaScript、网络拦截和自动选择器自愈仍在范围外。发布候选必须在干净 Windows 机器对 Edge、Chrome、最小化、多标签页、同源 iframe 和离线运行逐项取证。

## Excel 与 CSV 包

包 ID：`com.easycode.firstparty.tabulardata`

首期提供 CSV 读写、xlsx 工作表列举与读写、二维数据筛选/排序、表头转记录列表。它只依赖 Python 标准库，不要求安装 Office，不访问网络；写入 CSV/xlsx 使用同目录临时文件加原子替换，失败时不覆盖原文件。

首期定位为结构化数据基础包，不伪装成完整 Excel 计算引擎：公式计算、宏、图表、样式保真和已打开 Excel 进程控制均不在本阶段范围内。

## 验收与失败语义

- 未导入、未信任、未密封或未启用时，函数不可执行。
- 包的版本、签名、内容哈希、权限和函数契约进入 `easycode.lock` 与 Player 发布闭包。
- 浏览器连接失败、元素不存在、等待超时、iframe 不可访问都明确失败，不回退到不确定的屏幕点击。
- 表格输入不是二维列表、工作表不存在、文件损坏或写入提交失败都明确失败；不留下伪成功结果。
- `tests/test_first_party_extension_packages.py` 覆盖两个包的真实导入生命周期、函数目录与发布闭包，并覆盖 CSV/xlsx 的无 Office 读写。
