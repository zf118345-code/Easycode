# EasyCode 全局 UI 组件系统改造计划

> 状态：In progress（用户已批准实施；既有共享外壳与视觉收敛作为行为基线，阶段 A–J 的单一组件所有权改造仍需完成）  
> 日期：2026-09-07  
> 主视角：脚本作者  
> 次视角：高级开发者、Player 操作者  
> 视觉方向：保留 EasyCode 现有暖黑石墨、克制橙色和专业桌面密度，不进行品牌换肤  
> 权威上位文档：[PRODUCT.md](../../PRODUCT.md)、[ARCHITECTURE.md](../ARCHITECTURE.md)、[design.md](../../design.md)、[TEST_HARNESS.md](../TEST_HARNESS.md)、[DECISIONS.md](../DECISIONS.md)、[UI_SYSTEM.md](UI_SYSTEM.md)、[CONTROLS.md](CONTROLS.md)

## 1. 决策摘要

EasyCode 前端改造为一套统一 UI 系统搭建的产品。页面不再拥有按钮、输入框、标题栏、列表、表单、弹窗、状态反馈等基础视觉规则，而是组合受控的共享组件。相同角色只能由同一组件实现；不同领域可以保留不同内容结构，但必须消费相同的令牌、状态、无障碍和交互契约。

后续新增页面或功能必须优先组合共享组件。后续调整按钮高度、圆角、颜色、图标尺寸、表单节奏或交互状态时，应修改共享令牌或组件，使所有消费位置同步更新；不得再逐页复制和修改 CSS。

类型化 Control 是这套 UI 系统内负责“编辑什么值、如何校验和提交”的专业组件子系统，不是平行的第二套 UI。通用表单外壳负责标签、布局、帮助、错误、字段动作和响应式；Control 负责类型、值编辑、候选、捕获、验证和类型化提交。IDE 与 Player 共享 Control 契约和核心，允许依据鼠标/触控环境采用明确的密度投影。

本改造不改变 ProgramDocument、ECIR、函数契约、API、Store 业务语义、Player Schema、发布格式、运行目标语义或 Capture 结果契约。

## 2. 任务卡

| 项目 | 内容 |
| --- | --- |
| 主要用户 | 频繁在函数库、资源、变量、目标、Player、记录、计划和扩展之间切换的脚本作者 |
| 次要用户 | 维护扩展契约的高级开发者；填写并运行发布表单的 Player 操作者 |
| 触发 | 用户打开或切换工作区、编辑表单、调用 Control、处理状态和完成操作 |
| 用户购买的结果 | 在任何页面都能凭已有经验理解层级、找到动作、预测状态和完成任务 |
| 频率与紧迫性 | 每次使用 EasyCode 都发生；属于高频、全局质量问题 |
| 前置条件 | 当前项目、业务功能、数据契约和运行语义保持可用 |
| 错误成本 | 丢失草稿、错误保存、错误目标、隐藏能力、焦点丢失或已有功能不可达均不可接受 |
| 可观察成功 | 同角色计算样式、交互状态和文案一致；新增页面不复制基础 CSS；完整业务路径回归通过 |
| 恢复预期 | 任一迁移切片失败时只回退该组件消费层，不回退或改写用户项目数据 |

## 3. 当前代码事实与问题账本

文档口径说明：`UI_SYSTEM.md` 第 5 节记录的是 2026-09-07 当时共享外壳、共享 CSS 角色和浏览器画面的冻结证据；它证明现有视觉基线可保留，不证明 Button、Input、Dialog 等基础角色已经只有一个实现所有者。本计划以“源码出口、页面消费和防回退门”作为更高一层完成标准，两份文档不再互相替代。

2026-09-07 的静态盘点结果：

- `frontend/src/vnext` 中有 56 个 Vue 文件、约 448 个原生 `<button>`、140 个 `<input>`、45 个 `<select>`、30 个对话框语义入口。
- 54 个 Vue 文件拥有 scoped 样式；至少 19 个文件分别声明标题/图标按钮相关规则。
- 至少 16 个文件分别声明弹窗、遮罩或模态样式；按钮、空态、错误、加载与危险操作也存在多个页面所有者。
- `components/ui` 已有 ActivityRail、NavigationPane、PaneHeader、ListSearch、WorkspaceState、InlineNotice、InspectorSection 等原语，但覆盖不完整；部分页面在消费共享骨架的同时仍保留旧私有 CSS。
- 运行目标标题按钮实测已被共享规则投影为 28×28px，但 `VNextTargetWorkspace.vue` 仍声明自己的 header button、hover、focus 和 disabled 规则。这证明当前一致性依赖 CSS 优先级，而非单一组件所有权。

### 3.1 摩擦分级

| 编号 | 级别 | 证据 | 后果 | 改造原则 | 验证 |
| --- | --- | --- | --- | --- | --- |
| F-01 | P2 | 相同标题动作由多个页面 CSS 重复声明 | 状态或加载顺序变化后再次漂移 | 同角色单一组件、单一样式所有者 | 禁止规则 + 计算样式矩阵 |
| F-02 | P2 | 表单与 Control 同时拥有标签、布局、错误和动作外观 | 字段高度、换行、错误位置不稳定 | 表单外壳管布局，Control 管值语义 | Control Harness 与真实表单回归 |
| F-03 | P2 | 弹窗、空态、加载、错误和通知存在多个实现 | 恢复入口、焦点和文案不可预测 | 状态与覆盖层组件化 | 键盘、失败与恢复测试 |
| F-04 | P2 | 页面可以在共享组件外重新定义 hover/focus/disabled | 鼠标和键盘体验不一致 | 状态只能由原子组件拥有 | CSS/AST 防回退检查 |
| F-05 | P3 | 图标尺寸、笔画、基线和文字垂直位置缺少统一验收 | 精细观察下显得偏上、偏下或松散 | 数学居中 + 光学校准 + 缩放实测 | 像素截图和边界框测量 |
| F-06 | P3 | 页面局部硬编码值与 Token 并存 | 全局微调无法同步生效 | 语义 Token 唯一来源 | 硬编码探测与差异清单 |

本轮规划未发现由一致性直接导致的 P0/P1 功能事故；实施仍必须把数据保护和功能可达性置于视觉质量之前。

## 4. 不可破坏的产品不变量

### UICS-001 业务事实不变

- ProgramDocument 仍是项目函数唯一可编辑事实。
- UI 组件只接收和发出既有类型化值、命令和事件，不产生第二数据源。
- 不改变 API URL、请求体、响应体、Store action、权限、发布闭包或运行逻辑。

### UICS-002 编辑事务不变

- 输入、失焦、Enter、切换、保存、取消、冲突与恢复保持原语义。
- 组件迁移不得把自动保存改成显式保存，也不得反向改变。
- 尚未提交的 Control 草稿在切换、关闭和失败时保持既有保存/保留策略。

### UICS-003 功能入口不丢失

- 迁移前后的页面、菜单、快捷键、空态和上下文入口调用同一真实命令。
- 不因“精简”隐藏唯一入口；重复入口只有在确认命令仍可发现后才能移除。
- 禁用动作必须保留可理解的原因和恢复方式。

### UICS-004 跨端语义不变

- IDE、Windows Player、ADB Player 与 Android 本机 Player 使用同一字段契约和校验。
- 桌面与触控可以使用不同高度，但字段含义、错误、默认值、条件显示和提交结果一致。
- Capture、文件、目录、图片、OCR 和控件选择仍遵守宿主权限及原子回填契约。

## 5. 目标 UI 系统

### 5.1 层级与所有权

```text
Design Tokens
└── UI Primitives
    ├── Button / IconButton / Icon
    ├── Input / Select / Switch / Slider
    ├── Text / Badge / Divider / Spinner
    └── Tooltip / Focus / Motion
        └── UI Composites
            ├── PaneHeader / WorkspaceHeader / Toolbar
            ├── NavigationList / ObjectListItem / Search
            ├── FormRow / FieldAction / InspectorSection
            ├── Dialog / Menu / Popover / Notice
            └── WorkspaceState / BottomFeedback
                └── Typed Controls
                    ├── scalar / enum / expression
                    ├── reference / resource / target
                    ├── geometry / capture / file
                    └── list / dict / record / JSON
                        └── Workspace Templates and Pages
```

页面负责领域内容、数据连接和命令编排；共享组件负责视觉、布局、交互状态和无障碍；Control 负责类型化值编辑。

### 5.2 组件目录

| 家族 | 规范组件 | 必须覆盖的变体与状态 |
| --- | --- | --- |
| 按钮 | `VNextButton` | neutral/primary/danger；compact/default/touch；default/hover/active/focus/disabled/loading |
| 图标按钮 | `VNextIconButton` | title/toolbar/field；pressed；tooltip；badge；14/16px 图标 |
| 图标 | `VNextIcon` | Lucide、统一 stroke、尺寸、装饰/语义 aria |
| 标题 | `VNextPaneHeader`、`VNextWorkspaceHeader` | 标题、meta、说明、动作组、窄宽省略 |
| 搜索与工具栏 | `VNextListToolbar`、`VNextListSearch` | 搜索、筛选、排序、批量动作、清空 |
| 列表 | `VNextNavigationList`、`VNextObjectListItem` | compact/rich/multiline/child；hover/focus/selected/disabled/loading |
| 表单 | `VNextFormRow`、`VNextFormSection` | required、help、error、unit、field action、multiline、responsive |
| 检查器 | `VNextInspectorBody/Section/Disclosure/Feedback` | 空、加载、编辑、保存、失败、冲突 |
| 覆盖层 | `VNextDialog`、`VNextPopover`、`VNextMenu`、`VNextTooltip` | 焦点圈定、Escape、定位、遮罩、提交/取消 |
| 状态 | `VNextWorkspaceState`、`VNextInlineNotice`、`VNextToast` | loading/empty/filtered/selection/error/success/offline/permission |
| 反馈 | `VNextBottomFeedbackPanel` | 输出、当前值、问题；标签、关闭、调整高度 |
| Control 外壳 | `VNextControlField` | label、value、actions、help、error、disabled reason、Player density |
| 类型 Control | 现有 Control 家族迁移 | 值类型、候选、捕获、校验、草稿、提交、只读、平台能力 |

组件名称可以在实施审计中与现有命名合并，不能为了改名制造无价值的大范围 churn。

## 6. 视觉与交互规格

### UICS-010 密度与几何

- 4px 为基础节奏；间距只能使用已批准 Token。
- 桌面紧凑动作 28px，常规 Control 32px，富信息行 44/52px，Player 触控 Control 36–40px。
- 同角色宽高、内边距、圆角、边框和组间距必须一致。
- 只有真实双行内容使用富信息行；单行内容不得为“显得重要”而增高。

### UICS-011 图标与文字光学对齐

- 功能图标全部使用 Lucide；同一命令只能映射一个主图标。
- 图标组件使用 `display: block` 或等价方式消除 SVG 基线空隙；外层使用 flex/grid 双轴居中。
- 纯图标按钮默认 28×28px、图标 14×14px；其他角色由组件变体确定，页面不得直接传任意尺寸。
- 图标和文字分别读取边界框，检查视觉中心与控件中心；不能只凭 `align-items:center` 宣称完成。
- 混合图标文字按钮固定 gap、line-height 和文字基线；不在页面中使用零散 `top:1px`、transform 或 margin 修正。
- 确需光学校准时，只允许在共享组件中使用命名 Token，并记录适用字体、尺寸和缩放等级。
- 100%、125%、150%、200% 缩放下检查图标、中文、英文、数字和标点，不允许出现偏上、偏下、模糊或半像素边线。

### UICS-012 状态完整性

每个交互组件必须定义：

- default：中性、清晰、不过度抢占注意力；
- hover：只提升一个背景层级；
- active：提供可见按下反馈，不引发布局位移；
- focus-visible：清晰焦点环，不与错误边框混淆；
- disabled：仍可辨认，保持尺寸，说明可恢复原因；
- loading：保持按钮/字段宽度，阻止重复提交；
- selected/pressed：持续状态不同于瞬时 hover；
- error/success：使用语义色并辅以图标或文字，不只靠颜色。

### UICS-013 表单与 Control 组合

- `FormRow` 决定标签、Control、单位、动作、帮助与错误的布局。
- Control 不重复渲染外层字段标签、必填标记或页面级帮助。
- Control 负责类型、值、候选、校验、专用交互与类型化提交。
- 能一行完成的字段保持一行；内容区低于规范阈值或契约明确多行时才回落。
- 字段动作与 Control 同高；表单外轻量动作使用统一 InlineAction。
- 资源、目标、文件、目录和图片使用直接选择/捕获 Control，不伪装成自由文本。
- IDE 与 Player 共享同一 Control 能力注册表，Player 仅采用触控密度与宿主动作投影。

### UICS-014 信息层级与文案

- 页面标题、区块标题、字段标签、正文、辅助说明和诊断信息分别使用固定角色。
- 相同命令在页面、菜单、快捷键、空态和错误恢复中使用同一名称。
- 常驻帮助只保留格式风险、不可逆后果和反直觉默认值。
- 错误文案说明：发生了什么、保留了什么、用户下一步可以做什么。
- 内部 ID、实现类型、哈希和路径默认进入技术信息，不与业务字段平级。

## 7. 实施阶段与完成门

### 阶段 A：行为基线与组件清单

任务：

- 建立所有页面、组件、Control、覆盖层和状态入口清单。
- 为每个可操作入口记录 command、props、emits、Store action、API、禁用条件、焦点归还和错误恢复。
- 给每个重复实现标记：共享组件、待迁移、合法特例、待删除。
- 记录 1920×1080、1440×900、1280×720、1024×768、760×720 基线截图。
- 为保存、取消、删除、创建、选择、捕获、运行和发布补足特征测试。

完成门：所有现有功能有责任人、组件归属和至少一种可验证路径；任何未知行为先查明，不带入迁移。

### 阶段 B：Token 收口

任务：

- 审核颜色、文字、边框、圆角、间距、高度、阴影、z-index、焦点和 motion Token。
- 将重复值映射为语义 Token；区分桌面与 Player 密度。
- 建立允许硬编码白名单：像素算法、真实资源尺寸、平台安全区等。
- 删除同义 Token，保留兼容别名直到消费迁移完成。

完成门：基础视觉调整可以通过 Token 在 Harness 中同步影响全部组件，不改变布局语义。

### 阶段 C：原子组件

任务：

- 建立 Button、IconButton、Icon、基础输入、Select、Switch、Spinner、Badge、Divider、Tooltip。
- 每个组件实现完整状态、键盘、可访问名称、禁用原因和 loading。
- 建立专用 Component Harness，展示所有尺寸、状态、长中文和图标组合。
- 完成图标/文字光学对齐测量。

完成门：页面无需 CSS 即可获得完整按钮和输入状态；同角色计算样式严格一致。

### 阶段 D：结构组件

任务：

- 收口 AppHeader、ActivityRail、NavigationPane、PaneHeader、WorkspaceHeader、InspectorHeader。
- 收口 ListToolbar、ListSearch、NavigationList、ObjectListItem、Tabs、Disclosure。
- 收口 FormRow、FormSection、FieldAction、InlineAction、FooterActions。
- 收口 Dialog、Popover、Menu、Tooltip、Notice、WorkspaceState、BottomFeedbackPanel。

完成门：共享结构拥有布局和状态；页面只传内容、领域状态和命令。

### 阶段 E：Control 子系统接入

任务：

- 为每个 Control 建立类型、编辑投影、校验、错误、只读、禁用、加载、Player 和平台能力矩阵。
- 标量、枚举、表达式、引用、几何、资源、文件、捕获、列表、字典、Record、JSON 全部接入 `VNextControlField`。
- 删除 Control 内重复的标签、字段外壳、按钮和错误布局。
- 验证 `@`、`.`、命名空间候选、IME、光标、草稿和类型化提交不变。
- 验证图片/OCR 测试、灰度预览、区域选择、文件/目录和 Capture 原子回填不变。

完成门：同一种 Control 在程序检查器、变量、目标、Player 和扩展表单中使用相同核心；差异仅来自声明的 host/density/capability。

### 阶段 F：第一方工作区迁移

迁移顺序：

1. 函数库与程序编辑器；
2. 资源；
3. 项目变量；
4. 运行目标；
5. Player 设计器；
6. 运行记录；
7. 运行中心；
8. 扩展。

每个工作区执行同一清单：

- 替换标题、按钮、搜索、列表、表单、状态、弹窗和通知；
- 保留原事件、refs、Store action、API 和 disabled 条件；
- 删除已被共享组件承接的局部 CSS；
- 验证空、加载、失败、禁用、保存、冲突和长内容；
- 完成鼠标、键盘和窄宽实机走查；
- 通过后才进入下一工作区。

完成门：八个工作区不再声明基础组件视觉规则；相同角色能映射到同一组件和 Token。

### 阶段 G：Player、Capture 与跨端

任务：

- 迁移 Windows/ADB Player 外壳、表单、运行控制、日志、计划和方案管理。
- 迁移 Android Player 的同语义触控投影。
- 统一 Capture 准备、冻结、选择、清空、取消、确认、禁用和失败状态。
- 保留 Windows、ADB、Android 各自真实权限、系统窗口和输入实现。
- 验证离线、无开发后端、权限拒绝、应用切换、方向变化和旧坐标拒绝。

完成门：跨端业务语义一致；桌面与触控差异均有明确组件变体，不由页面私有 CSS 产生。

### 阶段 H：扩展消费边界

任务：

- 扩展工作区和扩展函数表单只消费批准组件。
- 扩展 Schema 声明组件角色、Control、权限和平台能力，不能注入任意主题 CSS。
- 中立 Harness 扩展验证标题、列表、表单、状态、Player 和卸载回收。

完成门：新增扩展不会形成第九套 UI；禁用/卸载后入口和样式完全回收。

### 阶段 I：删除重复实现与建立防回退门

任务：

- 删除 `.target-sidebar header button`、`.resource-tree header button`、`.header-actions button`、`.quiet-icon` 等已经迁移的重复规则。
- 增加 ESLint/AST 检查：禁止在受控 header action 中使用裸 `<button>`。
- 禁止业务页面定义共享组件内部元素样式和未登记的硬编码视觉值。
- 建立合法特例登记表：语义、原因、组件 owner、测试和删除条件。
- 检查死 CSS、孤立组件、重复图标映射和无入口状态。

完成门：每个基础视觉角色只有一个实现所有者；违规新增代码在 CI 中失败。

### 阶段 J：最终打磨与冻结

只进行两轮有界视觉检查：第一轮批量发现并一次修复，第二轮确认，不进行无止境局部打磨。

检查清单：

- 图标与中文/英文/数字在按钮中上下、左右光学居中；
- 文字按钮没有偏上、偏下或因 line-height 产生漂移；
- 同排 Control、图标动作、单位和错误标识边界对齐；
- 标题靠近所属内容，不贴近上一分隔线；
- 相同表单节奏一致，说明文字不制造重复高度；
- Hover、active、focus、disabled、loading 不引发布局跳动；
- 1px 边线在不同缩放下清晰，无半像素模糊；
- 长中文、英文、路径、数字、空值和极端数量不溢出；
- 滚动条、文本选择、光标、Tooltip、菜单和系统表面使用同一主题；
- reduced motion 下没有依赖动画才能理解的状态；
- 控制台无错误和警告，交互没有明显输入延迟或布局抖动。

完成门：权威规范、实现、测试和证据一致；未经登记的页面视觉所有权为零。

## 8. 页面迁移检查表

每个页面必须逐项回答“是”：

### 外壳

- [ ] 使用批准的页面/工作区模板。
- [ ] 标题、meta、说明和动作位于规定角色。
- [ ] 左栏、主区、检查器和底部反馈边界清晰。
- [ ] 不为视觉对称增加没有任务价值的栏或空面板。

### 操作

- [ ] 同类按钮使用同一组件和图标。
- [ ] 主操作每个视觉组最多一个。
- [ ] 危险操作具有明确确认和影响说明。
- [ ] disabled/loading 保持布局并说明原因。
- [ ] 菜单、快捷键和空态复用同一命令。

### 表单与 Control

- [ ] 标签、必填、默认值、单位、帮助和错误完整。
- [ ] 能一行展示的字段保持一行。
- [ ] 字段动作与 Control 同高、同状态体系。
- [ ] Control 不重复拥有外层表单布局。
- [ ] 草稿、保存、取消、失败和冲突不丢数据。
- [ ] Player 暴露、捕获和平台限制符合字段契约。

### 状态与恢复

- [ ] loading、empty、filtered、selection、error、success 均有正确范围。
- [ ] 错误说明保留内容和下一步动作。
- [ ] 取消返回原上下文，完成后焦点位置可预测。
- [ ] 离线、权限不足、宿主不可用不冒充普通字段错误。

### 视觉与无障碍

- [ ] 图标、文字、控件和行高完成光学校准。
- [ ] 焦点可见、顺序合理、名称可读。
- [ ] 状态不只依赖颜色。
- [ ] 中文 IME、长文字、缩放和窄宽可用。
- [ ] 页面没有复制共享组件 CSS。

## 9. 验证矩阵

### 9.1 自动验证

- 组件单元测试：props、emits、slots、状态和无障碍名称。
- Control 契约测试：类型、默认值、校验、候选、草稿、序列化和 Player 投影。
- 业务特征测试：共享组件替换前后命令、Store、API 与持久化结果等价。
- CSS/AST 规则：裸按钮、私有 header/control 样式、硬编码、Emoji、`transition: all`。
- Playwright：计算尺寸、间距、颜色、图标边界框、焦点、键盘和视觉截图。
- 全量 TypeScript、ESLint、Vitest、生产构建和自动无障碍扫描。

### 9.2 浏览器证据

| 视口 | 状态 |
| --- | --- |
| 1920×1080 | 完整宽屏、长内容、三栏 |
| 1440×900 | 默认工作视口、八工作区 |
| 1280×720 | 最低完整桌面体验 |
| 1024×768 | 收窄侧栏、覆盖检查器 |
| 760×720 | 窄宽抽屉、无水平溢出 |

每个组件家族覆盖 default、hover、active、focus、disabled、loading、error、empty、long content。浏览器控制台必须为 0 错误、0 警告。

### 9.3 缩放与输入

- Windows 100%、125%、150%、200% 缩放。
- 鼠标、键盘、中文 IME；触控端验证真实触控目标。
- 手工检查焦点顺序、焦点归还、Escape、Tab、Enter、Space、方向键和屏幕阅读名称。

### 9.4 真实宿主证据

- Windows IDE 与开发浏览器证据单独记录。
- 独立 Windows Player 在关闭 IDE/开发后端后验证。
- Android APK 在断开数据线并关闭 IDE/后端后真机验证。
- Capture、OCR、图片、文件、目录、权限与方向变化必须在对应真实宿主验证。
- 浏览器窄屏或 ADB screencap 不能冒充 Android 本机运行时证据。

## 10. 功能保护与回退策略

- 在独立分支中按组件家族和工作区形成小型、可审查提交，不使用一次性全仓机械改写。
- 每个切片先补行为特征测试，再替换视图层，最后删除旧 CSS。
- 组件适配层首先保持既有 props、emits、refs 和事件顺序；只有独立产品需求才能改变契约。
- 新旧实现不得长期并存；单个迁移切片允许短期兼容，但通过完成门后必须删除旧所有权。
- 若迁移导致功能、焦点、草稿或宿主行为回归，只回退当前切片；不通过修改用户数据或添加迁移层掩盖问题。
- 不使用 `!important` 作为长期统一机制；它只可在迁移期阻止已知旧规则，完成时必须清理。

## 11. 全局完成标准

### UICS-100 组件覆盖

- 100% 第一方页面的基础 UI 角色映射到组件目录。
- 100% 类型化 Control 接入统一字段外壳与状态契约。
- 扩展贡献 UI 只能组合批准组件。

### UICS-101 单一所有权

- 同角色只有一个样式与状态所有者。
- 业务页面不声明共享组件内部视觉规则。
- 未登记的视觉硬编码和重复组件为零。

### UICS-102 视觉一致

- 任取不同页面的同角色组件，计算高度、宽度、内边距、间距、圆角、图标、颜色和状态一致。
- 图标和文字在全部批准缩放下完成数学与光学居中。
- 页面结构可以因任务不同而不同，但层级、密度、反馈和词汇保持同一产品语言。

### UICS-103 功能等价

- 所有既有入口、命令、保存、校验、捕获、运行、发布和恢复路径通过回归。
- ProgramDocument、API、Player、Runtime 和发布契约无非授权变化。
- 切换、失败、冲突和取消不丢草稿或用户数据。

### UICS-104 可持续统一

- 新页面只组合组件即可达到视觉基线。
- 修改共享 Token/组件能在 Harness 与全部消费页面同步生效。
- CI 能阻止新增裸标题按钮、重复基础 CSS、无状态组件和无可访问名称动作。

### UICS-105 验证完整

- 自动测试、类型检查、Lint、构建和无障碍扫描通过。
- 规定视口、缩放和真实浏览器证据通过。
- Windows Player 和 Android 真机证据与浏览器证据分开通过或明确标为未验证。

## 12. 明确范围外

- 不重新设计 EasyCode 品牌、信息架构或领域模型。
- 不修改函数、表达式、Control 值类型、运行、发布和权限语义。
- 不以组件统一为理由删除低频但唯一的真实功能。
- 不强迫列表、编辑器、资源、运行记录和 Capture 使用相同页面布局。
- 不为了视觉对称增加虚假栏目、卡片、说明、动画或入口。
- 不兼容已废弃旧项目格式，也不为旧测试项目引入迁移层。

## 13. 最终交付物

- 更新后的 `design.md`、`UI_SYSTEM.md`、`CONTROLS.md` 与必要 ADR。
- 组件目录、Token 目录、状态矩阵、图标映射和合法特例登记表。
- Component/Control Harness。
- 全部第一方工作区、Player、Capture 和扩展消费层迁移。
- 已删除的重复样式与组件清单。
- 自动回归、视觉矩阵、无障碍和真实宿主证据。
- 完成报告，严格区分自动通过、浏览器通过、Windows 宿主通过、Android 真机通过、未验证和受环境阻塞。

## 14. 需求追踪表

| 需求 | 状态 | 主要阶段 | 必须产生的证据 |
| --- | --- | --- | --- |
| UICS-001 业务事实不变 | Planned | A、E–H | Store/API/ProgramDocument 特征测试 |
| UICS-002 编辑事务不变 | Planned | A、E、F | 草稿、保存、取消、冲突与恢复测试 |
| UICS-003 功能入口不丢失 | Planned | A、F–H | 命令映射表与端到端入口走查 |
| UICS-004 跨端语义不变 | Planned | E、G | IDE/Player 契约测试与真实宿主证据 |
| UICS-010 密度与几何 | Planned | B–D、J | 计算样式和视口截图矩阵 |
| UICS-011 图标与文字光学对齐 | Planned | C、J | SVG/文字边界框与缩放截图 |
| UICS-012 状态完整性 | Planned | C–H | 组件状态 Harness 与键盘测试 |
| UICS-013 表单与 Control 组合 | Planned | D、E | Control 矩阵、表单回归和 Player 投影 |
| UICS-014 信息层级与文案 | Planned | D、F–H | 页面审查表和术语映射 |
| UICS-100 组件覆盖 | Planned | F–H | 全页面组件归属清单 |
| UICS-101 单一所有权 | Planned | I | AST/CSS 防回退检查与删除清单 |
| UICS-102 视觉一致 | Planned | J | 跨页面计算样式与视觉证据 |
| UICS-103 功能等价 | Planned | A–J | 全量自动测试与关键任务回归 |
| UICS-104 可持续统一 | Planned | C、H、I | 新页面/中立扩展 Harness 与 CI 失败样例 |
| UICS-105 验证完整 | Planned | J | 自动、浏览器、Windows、Android 分类报告 |

## 15. 风险与控制

| 风险 | 触发方式 | 控制措施 | 失败处理 |
| --- | --- | --- | --- |
| 功能回归 | 替换组件时改变事件或提交时机 | 先补特征测试，保留 props/emits/refs 顺序 | 停止该切片并回退视图适配层 |
| 草稿丢失 | Control 重挂载、key 或焦点策略变化 | 记录草稿所有权，测试切换/关闭/冲突 | 保留旧 Control，修复所有权后重试 |
| CSS 双重所有权 | 旧 scoped 规则仍参与层叠 | 迁移后立即删除旧规则，CI 禁止回归 | 完成门失败，不进入下一页面 |
| 过度组件化 | 不同任务被强迫使用同一布局 | 统一角色，不统一领域拓扑；特例需登记 | 拆出有真实语义的组件变体 |
| 组件 API 膨胀 | 页面需求不断增加布尔 props | 优先 slots、语义 variant 和组合 | 重新划分组件职责，不加页面 CSS |
| 性能下降 | 通用组件引入多余 watcher、DOM 或依赖 | Harness 测 DOM、渲染与包体；隐藏区停止工作 | 保留轻量实现并优化组件边界 |
| 原生宿主漂移 | 浏览器验证代替 Windows/Android 真实行为 | 按宿主单独验收权限、Capture 和生命周期 | 标为未验证，不宣称完成 |
| 无障碍回归 | 自定义按钮、菜单或弹窗破坏语义 | 原生元素优先，键盘和读屏名称纳入组件契约 | 阻止合并直至焦点和名称恢复 |
| 视觉过度统一 | 危险、主操作和选中状态失去区分 | 使用同体系下的语义 tone，不抹平角色 | 恢复语义变体，不允许页面自绘 |

## 16. 实施前唯一确认

本计划采用以下已知方向，不再为局部 CSS 数值逐项询问：

- 保留现有视觉世界和紧凑呼吸感；
- 相同角色严格统一，不同领域结构按真实任务保留；
- Control 属于统一 UI 系统中的专业子系统；
- 功能、数据、运行和发布语义不变；
- 通过组件所有权和 CI 规则保证后续新增页面继续统一。

若用户明确回复开始实施，执行从阶段 A 开始，并在规格冻结、行为基线和未知项清单完成之前不进入批量页面迁移。
