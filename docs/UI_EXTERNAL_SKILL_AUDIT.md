# EasyCode 外部设计技能审计

> 审计日期：2026-08-26  
> 审计范围：`frontend/src`、三入口生产构建、`design.md` 及现有前后端承接清单  
> 使用方法：Impeccable 作为主审计框架；Taste Skill 与 Redesign Existing Projects 只采用适合桌面 IDE 的规则。

## 1. 引入结论

已安装并纳入工作流的技能：

| 技能 | 本项目用途 | 安装位置 |
| --- | --- | --- |
| Impeccable | UI 审计、问题分级、实现完整性、可访问性、性能与主题检查 | `%USERPROFILE%/.codex/skills/impeccable` |
| Design Taste Frontend | 设计意图、信息层级、状态完整性、内容真实性与视觉一致性 | `%USERPROFILE%/.codex/skills/taste-skill` |
| Redesign Existing Projects | 在不破坏既有技术栈和功能的前提下做存量界面重构 | `%USERPROFILE%/.codex/skills/redesign-skill` |

没有引入 Taste Skill 中偏营销页、图片生成、强动效的技能。EasyCode 是高密度桌面 IDE，不应套用 Hero、大图、滚动叙事、React/Tailwind 或强制 GSAP 等网页模板规则。

规则优先级固定为：用户明确需求 → EasyCode 产品目标与 `design.md` → 桌面 IDE 的 Operate 模式 → 外部技能中兼容的规则。项目继续使用 Vue、Pinia、Element Plus 和 Lucide，不为追随技能默认值迁移框架或替换图标体系。

## 2. Design Read

### 产品模式

- 模式：Operate，高频、专业、键鼠优先、需要长期使用。
- 核心对象：项目、唯一主流程、函数契约、唯一页面地图、能力、资源、变量和运行会话。
- 核心任务：快速搭建大型脚本、调试、捕获、发布与 Player 运维。
- 主要风险：入口重复、信息噪声、表单纵向膨胀、大型流程性能下降、视觉状态与真实后端状态脱节。

### 设计旋钮

| 旋钮 | 值 | 含义 |
| --- | ---: | --- |
| Design Variance | 4/10 | 允许画布和捕获有产品辨识度，Shell 与表单保持稳定克制 |
| Motion Intensity | 2/10 | 动效只解释状态和空间关系，不做装饰性运动 |
| Visual Density | 8/10 | 桌面 IDE 保持高信息密度，但通过层级、折叠和按需展示获得呼吸感 |

## 3. 实现完整性结论

EasyCode 当前不是“套了皮肤的网页”，而是形成了产品特定的信息架构：命令栏、主流程/函数/页面地图三类画布、项目大纲、检查器、捕获、调试、能力库、运行服务和 Player 各自承担明确职责。现有主要入口都有真实 store、API 或运行时状态承接。

本轮没有发现 P0 阻断问题，也没有发现生产界面使用假统计或演示数据兜底。上一轮识别出的核心键盘路径、项目树规模保护、三入口 UI 依赖拆分、普通 UI 主题收口和布局型悬停动画均已实施，不需要推翻当前架构。

## 4. 五维评分

| 维度 | 分数 | 结论 |
| --- | ---: | --- |
| Accessibility | 4/4 | 画布菜单、项目树、资源卡片与断点入口均有语义、焦点和键盘闭环 |
| Performance | 4/4 | 项目树与画布均有视口裁剪；三入口依赖按需拆分且无超 500 kB 单块 |
| Theming | 3/4 | 普通菜单、状态、Tooltip、Player 与核心画布色已收口；节点类型领域色仍需持续集中治理 |
| Responsive | 3/4 | 顶栏、Player、工具中心和复杂弹窗已有降级布局；仍需按规范矩阵做全部容器验证 |
| Implementation Integrity | 4/4 | 产品结构、真实数据、状态和交互语义一致，没有为了展示而虚构功能 |
| **总分** | **18/20** | **已达到本轮发布门槛；剩余工作是响应式矩阵和领域色长期治理** |

## 5. 问题清单

### 已修复：核心键盘路径

以下核心交互已经完成：

- `CanvasContextMenu.vue`：真实按钮和 `menu/menuitem` 语义，打开聚焦首项，方向键、Home/End、Esc 完整。
- `ProjectExplorerPanel.vue`：roving tabindex，方向键树导航，Enter/Space、F2、菜单键和焦点归还。
- `FileBrowser.vue`：资源卡片具备 `option/aria-selected`，Space 选择，Enter 选择/确认。
- `CanvasNodeCard.vue`：断点槽改为 `button + aria-pressed`，保留紧凑外观并扩大点击目标。

专项单测覆盖画布菜单循环焦点、Esc 关闭、资源卡片键盘确认、资源树方向键焦点。

### 已修复：大型脚本资源树规模保护

- 项目资源树改为扁平索引、固定 `30px` 行高和前后 8 行 overscan。
- 文件夹分桶从重复筛选改为一次线性分组。
- 1000 节点专项测试中，虚拟树总高度保持正确，实际 DOM 行数低于 40。
- 画布既有 `filterNodesToViewport` 在 250 节点以上启用，只渲染视口节点；日志继续沿用既有虚拟化。

后续只需继续维护 500/1,000/3,000 节点基准，不再为资源树挂载完整 DOM。

### 已修复：Element Plus 三入口按需加载

IDE、Player、Capture 均使用显式组件注册和颗粒化样式；构建不再强制把 Element Plus 合并为单个公共块。修复前：

- `vendor-element-plus` JavaScript：810.54 kB，gzip 254.51 kB。
- `vendor-element-plus` CSS：363.78 kB，gzip 48.51 kB。
- Vite 对超过 500 kB 的块发出警告。

修复后：最大 JavaScript 块为 IDE 入口 `336.95 kB`（gzip `113.15 kB`），构建无大块警告；Player 只预加载自身需要的共享模块和控件。Element Plus CSS 总体由 `363.78 kB` 降至按入口拆分后的最大共享样式 `97.59 kB`，加各入口实际样式。

### 持续治理：主题令牌

本轮已将普通菜单、画布卡片/连线基础色、断点、调试工具栏、Player 状态、Activity Bar Tooltip 和悬浮层迁移到 `--app-*` Token。剩余字面量主要来自主题定义、节点类型色、捕获高亮和端口领域色，不作为发布阻断项。

治理方式：

1. 保留真正的数据色、端口色、节点类型色，并集中到语义映射表。
2. 普通背景、边框、文字、悬停、阴影全部迁移到 `--app-*` Token。
3. 禁止新增无法说明语义的十六进制颜色；代码评审必须说明新增色属于主题还是数据可视化。
4. 浅色主题目前仅是映射预留，不应在产品中宣称已支持。

### P2：响应式覆盖需要从“有断点”升级为“有矩阵”

顶栏、Player、工具中心、能力库和历史帧工作台已有媒体查询，但大部分检查器、文件管理器、项目属性弹窗仍依赖 Element Plus 的固定宽度。桌面产品不要求手机布局，但必须支持 900×700、720×640、Windows 125%–200% DPI 以及 320–620px 的属性栏容器。

验收时以功能可达为标准：低频命令可进入更多菜单，固定底栏不得盖住字段，弹窗不得超出屏幕，按钮文字不得被截断成不可辨识图标。

### 已修复：布局型动效

- 创建菜单不再通过 padding 产生悬停位移。
- 业务样式中的 `transition: all` 已替换为明确属性。
- 图片卡片悬停不再上浮；保留动作按钮使用 opacity/transform 进入。
- SVG 端口缩放和描边属于画布领域反馈；`prefers-reduced-motion` 下由全局规则关闭非必要动画。

验收标准：动画显式列出 `opacity/transform/color/background-color/border-color`；交互位移优先使用 `transform`；`prefers-reduced-motion` 下禁用非必要动画。

## 6. 保留项

以下做法符合三个技能中适用于 EasyCode 的原则，应保持：

- 单层命令栏 + Activity Bar + 上下文工具窗口，而不是首页式卡片导航。
- 检查器“摘要—核心—识别/执行—高级—固定底栏”的结构。
- 低频复合功能进入中心工作台或弹窗，不挤占常驻侧栏。
- 变量使用扁平行和跨分类搜索，不使用大卡片堆叠。
- Lucide 作为唯一通用图标系统；状态同时使用文字/形状，不能只靠颜色。
- 后端加载、空、失败、成功四态真实呈现，不使用演示数据填充。
- 捕获热路径保留原生宿主，Vue 负责资源和业务表单，不强求所有桌面交互都在浏览器 DOM 内完成。

## 7. 后续执行顺序

1. 按 `design.md` 的尺寸与 DPI 矩阵继续完成响应式视觉回归。
2. 用 500/1,000/3,000 节点基准长期监测筛选、滚动、模式切换与画布拖动。
3. 将剩余节点类型色集中为领域语义映射，避免业务组件新增普通 UI 色字面量。
4. 记录桌面打包后的真实冷启动和 Player 内存，而不仅依赖 Web 资源体积。

## 8. 本轮证据

- Impeccable detector：对 `frontend/src` 的最终扫描返回 `[]`，没有静态规则问题。
- 生产构建：IDE、Player、Capture 三入口构建成功，3624 个模块转换完成。
- 构建耗时：7.30 秒；最大 JavaScript 块为 IDE 入口 `333.58 kB`（gzip `111.80 kB`），无超过 500 kB 的块。
- 资源树专项测试：1000 节点仅渲染可视窗口，键盘焦点跨虚拟行正确移动。
- 前端全量回归：47 个测试文件、231 项测试全部通过；本轮核心入口 ESLint 0 error。
- 后端 v3 核心回归：58 项通过，覆盖严格 Schema、函数运行、发布前检查、离线回放、能力、Player、事务保存和真实 HTTP 画布往返。
- `D:\PycharmProjects\testisok`：严格 v3 五文档重建、主流程调用函数、稳定资源、离线页面回放与发布前检查全部通过。
- 既有功能承接审计：见 `docs/UI_FRONTEND_AUDIT.md`。
- 唯一规范源：`design.md`。
