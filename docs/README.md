# EasyCode 文档索引

本目录只保留当前架构的规范和可长期维护的参考资料。日期化审计、阶段周报和已完成计划不作为事实来源；历史由 Git 保存。

当前 vNext 会改变实现路线的产品与架构基线已经冻结为实施依据。现有代码仍只用于核对事实，不反向决定目标；文档状态为 `Approved` 只表示可以实施，不表示功能已经完成或通过真实宿主验收。细分规格中仍标为 `Proposed` 的非架构数值或交互细节，必须在对应垂直切片开工前关闭，且不得改变已冻结的 ProgramDocument、函数、扩展、平台与发布边界。

## 五个权威入口

| 文档 | 回答的问题 | 更新时机 |
| --- | --- | --- |
| [`../PRODUCT.md`](../PRODUCT.md) | 为谁做、解决什么、当前范围和质量目标 | 产品范围或优先级改变 |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 领域模型、模块边界、持久化与平台契约 | 架构或数据契约改变 |
| [`../design.md`](../design.md) | 信息架构、交互、视觉和 Control 规范 | 交互或设计系统改变 |
| [`TEST_HARNESS.md`](TEST_HARNESS.md) | 如何验证、留证和阻止回归 | 测试能力或放行门改变 |
| [`DECISIONS.md`](DECISIONS.md) | 为什么选择当前方案 | 产生跨模块、长期决定 |

## 细分规范

`vnext/` 保存 ProgramDocument、ECIR、函数、扩展、项目格式、结构化值、集合、资源、目标、跨平台控件、网络、消息、计划、IDE、Player 和测试的细化契约。完整递归纯值模型见 [`vnext/EXPRESSIONS.md`](vnext/EXPRESSIONS.md)，由注册表生成的全部统一输入语法见 [`vnext/EXPRESSION_SYNTAX.md`](vnext/EXPRESSION_SYNTAX.md)，记录、列表、字典、集合变换与外部 JSON 见 [`vnext/COLLECTIONS.md`](vnext/COLLECTIONS.md)，统一控件选择器、三平台适配器与 SurfaceView 降级边界见 [`vnext/CONTROLS.md`](vnext/CONTROLS.md)。细分规范不得覆盖五个权威入口；发现矛盾时先修订上层规范。已取消当前实现授权但需要保留讨论背景的内容放入 `deferred/`，不得出现在活动完成门中。

作者效率与统一 UI 本轮实施范围见 [`vnext/AUTHORING_PLATFORM_EXPANSION_PLAN.md`](vnext/AUTHORING_PLATFORM_EXPANSION_PLAN.md)，最终分级证据见 [`vnext/AUTHORING_PLATFORM_COMPLETION_REPORT.md`](vnext/AUTHORING_PLATFORM_COMPLETION_REPORT.md)。浏览器 DOM 与 Excel/CSV 第一方可导入包的构建、导入、状态和卸载路径见 [`vnext/FIRST_PARTY_EXTENSION_PACKAGES.md`](vnext/FIRST_PARTY_EXTENSION_PACKAGES.md)，共享组件唯一责任见 [`vnext/UI_COMPONENT_INVENTORY.md`](vnext/UI_COMPONENT_INVENTORY.md)。

格式 6 项目不包含可编辑 `.easy` 源码、旧画布或页面拓扑。遗留 Source HTTP 名称仅作为固定结构化 `410` 兼容边界存在，不属于活动 API，也不得出现在新 UI、测试项目或发布产物中；当前实现与验收只追踪 ProgramDocument API。扩展开发目录中的外部 Python/原生源码遵循扩展规范，不属于项目函数源码。

## 单项需求

中大型需求使用 [`templates/FEATURE_SPEC.md`](templates/FEATURE_SPEC.md) 创建规格。规格通过审查后才能进入实现；完成后保留规格和最终验收证据，不保留聊天摘录或重复实施周报。

规格讨论顺序、已关闭阶段和实施回查规则见 [`DISCUSSION_ROADMAP.md`](DISCUSSION_ROADMAP.md)。路线图固定遵循“产品与领域框架 → 编译/运行/扩展 → 领域能力 → 工作区 → Control 与视觉细节”，但不覆盖权威入口和细分功能规格；后续发现会改变实现路线的新事实时，必须先新增或取代 ADR，再恢复对应规格阶段。

## 文档状态

- `Draft`：可讨论，不授权实施。
- `Proposed`：内容完整，等待审批。
- `Approved`：实施依据。
- `Implemented`：实现和验收已通过。
- `Superseded`：被新规格替代，应在当前变更中删除，历史交给 Git。
