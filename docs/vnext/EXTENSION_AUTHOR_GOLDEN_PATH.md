# EasyCode 扩展包黄金路径

- 状态：Approved and implemented
- 日期：2026-09-07
- 示例包：`com.easycode.examples.minimalpython`

## 用户看到的完整流程

1. 扩展作者在目标项目外得到一个包含 Manifest、函数契约、实现、许可证和签名的普通文件夹。
2. 用户在 EasyCode“扩展”页点击“导入扩展文件夹”，选择该文件夹。
3. 导入只复制并校验包，不自动信任、不自动启用，也不执行代码。
4. 用户查看发布者、权限、网络声明、目标平台和诊断后，显式信任发布者。
5. 用户构建密封产物并运行包内契约测试。
6. 用户启用扩展；精确版本、签名指纹、内容哈希、函数契约和密封变体写入项目 `easycode.lock`。
7. 扩展函数出现在普通函数库“扩展”页，插入、参数 Control、返回值、日志和 Player 发布均复用现有模型。
8. 禁用或卸载前先检查引用；存在引用时阻止操作并给出可修复位置。无引用时禁用会原子更新项目与 lock，随后才能卸载。

“官方随附”仍使用完全相同的包产物，只改变只读安装范围和发行方式；不得复制成核心函数实现。

## 生成一个可手动导入的最小包

使用项目 Python 3.12 环境：

```powershell
.\.venv312\Scripts\python.exe scripts\manage_minimal_python_extension.py build --output D:\Temp\EasyCodeMinimalPackage
```

命令会打印 `package_path`。在 EasyCode 扩展页选择该目录，即可亲自走完导入流程。

最小包只贡献 `示例扩展.两个数相加`，无文件、网络、输入或捕获权限。它故意保持简单，用来定位扩展生命周期问题，而不是展示复杂业务能力。

## 自动黄金路径

以下命令同样从外部签名包导入，不允许直接引用源码绕过安装器：

```powershell
.\.venv312\Scripts\python.exe scripts\manage_minimal_python_extension.py install --project D:\Projects\MyEasyCodeProject --scope project
.\.venv312\Scripts\python.exe scripts\manage_minimal_python_extension.py remove --project D:\Projects\MyEasyCodeProject --scope project
```

把 `project` 改为 `user` 可验证用户范围。测试 `tests/test_minimal_python_extension_golden_path.py` 对两个范围都执行：签名导入、显式信任、密封构建、启用写锁、契约调用、目录可见性、禁用和卸载。

## 失败语义

- 无效或篡改包：导入阶段拒绝，不产生半安装目录。
- 未信任：允许查看，禁止启用或执行。
- 未密封：函数不会进入可发布运行闭包。
- 缺包或哈希漂移：项目保持原 lock，不静默换版本，并显示恢复入口。
- 仍有引用：禁用和卸载均停止，不修改 ProgramDocument 或 Player Schema。
- 用户范围卸载：移动到本机扩展回收目录；项目范围卸载通过项目事务删除。
