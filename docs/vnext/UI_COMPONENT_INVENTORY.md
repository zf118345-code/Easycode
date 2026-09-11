# EasyCode UI 组件责任清单

- 状态：Implemented baseline（共享地基和强制接入规则已生效；登记的领域特例不复制基础外观）
- 日期：2026-09-07
- 适用范围：`frontend/src/vnext`
- 上位规格：`UI_COMPONENT_SYSTEM_PLAN.md`、`UI_SYSTEM.md`、`CONTROLS.md`

本清单记录 UI 角色的唯一实现者和迁移边界。领域页面保留数据、命令、列表内容和特殊画布行为，不再持有通用控件的基础外观。

## 1. 唯一组件所有者

| UI 角色 | 唯一实现 | 页面职责 | 当前状态 |
| --- | --- | --- | --- |
| 文字按钮 | `VNextButton` | 传入命令、禁用与 loading 条件 | vNext 通用动作已迁移 |
| 图标按钮 | `VNextIconButton` | 传入稳定可访问名称和图标 | 已建立，顶部入口已迁移 |
| 单行输入 | `VNextTextField` | 绑定类型化草稿 | 已建立；类型字段由 Control 外壳承接 |
| 多行输入 | `VNextTextarea` | 绑定文本草稿 | 已建立 |
| 选择器 | `VNextSelect` | 提供选项和值 | 已建立；类型字段由 Control 外壳承接 |
| 开关 | `VNextSwitch` | 提供布尔值和可访问名称 | 已建立 |
| 徽标/加载/分隔 | `VNextBadge`、`VNextSpinner`、`VNextDivider` | 提供领域文案 | 已建立 |
| 左侧容器/标题/搜索 | `VNextNavigationPane`、`VNextPaneHeader`、`VNextListSearch` | 组合领域列表 | 已共享 |
| 左侧列表项 | `VNextNavigationItem` | 提供图标、主次文本和计数 | 八个工作区已迁移 |
| 表单行/区段 | `VNextFormRow`、`VNextFormSection` | 提供 Control 和验证结果 | 已建立 |
| 类型 Control 外壳 | `VNextControlField` | 提供标签、必填、帮助、错误和响应式排列 | 程序参数已接入 |
| 检查器区段 | `VNextInspectorSection` | 提供领域字段 | 已共享 |
| 弹窗 | `VNextDialog` | 提供正文、动作和提交命令 | 新增通用弹窗强制使用；复杂领域工作区可组合共享按钮与焦点契约 |
| 页面状态/通知 | `VNextWorkspaceState`、`VNextInlineNotice` | 提供恢复命令 | 已共享 |
| 底部反馈 | `ProgramBottomFeedbackPanel` | 提供输出、当前值与问题数据 | 共享工作区入口 |

## 2. 工作区责任与迁移证据

| 工作区 | 数据/命令所有者 | 共享骨架 | 关键回归 |
| --- | --- | --- | --- |
| 函数库/程序 | program store | PaneHeader、NavigationPane、ListSearch、WorkspaceState | 插入、搜索、快捷添加、焦点归还 |
| 资源 | workspace store | NavigationItem、Button、InspectorSection | 导入、视觉录入、选择、删除、焦点归还 |
| 项目变量 | project variable store | NavigationItem、Button、InspectorSection | 新建、改名、改值、删除 |
| 运行目标 | target store | NavigationItem、Button、InspectorSection | 选择、保存、默认目标、删除 |
| Player | player schema store | NavigationItem、Button、WorkspaceState | 页面、控件绑定、预览、发布 |
| 运行记录 | replay API/store | PaneHeader、NavigationItem、Button | 会话、时间线、检查器、历史帧 |
| 运行中心 | schedule API/store | NavigationItem、Button、WorkspaceState | 计划、批次、实例、LAN 配对 |
| 扩展 | extension API/store | NavigationItem、Button、ListSearch | 导入、信任、启用、卸载 |

## 3. 合法特例

| 特例 | 原因 | 视觉所有者 | 删除条件 |
| --- | --- | --- | --- |
| 中央语句行和分支行 | 树编辑器、拖放、虚拟化和行级快捷动作，不是普通按钮 | `ProgramStatementList` | 出现可复用的结构化编辑器行协议后复审 |
| 资源卡片与时间线帧 | 空间选择和虚拟滚动，不是导航列表 | 对应领域组件 + 公共 Token | 建立通用虚拟卡片协议后复审 |
| 底栏标签页 | Tab 语义与键盘模型不同于普通按钮 | 底栏组合组件 | `VNextTabs` 接管后删除 |
| 捕获遮罩与区域手柄 | 像素坐标算法需要真实尺寸 | Capture 子系统 | 不删除，只禁止复制到普通页面 |

## 4. 防回退规则

1. `VNextPaneHeader` 的普通动作必须使用 `VNextButton` 或 `VNextIconButton`；Tab 等合法复合控件需登记。
2. 新工作区左栏必须组合 `VNextNavigationPane`、`VNextPaneHeader`、`VNextListSearch`、`VNextNavigationItem`。
3. 页面不得重新定义共享按钮、输入、选择、焦点环和选中竖线的基础状态。
4. 新增裸表单控件必须先证明属于原生语义特例，否则 CI 检查失败。
5. 每次迁移保留既有事件、Store action、API、禁用条件、错误恢复与焦点归还。
