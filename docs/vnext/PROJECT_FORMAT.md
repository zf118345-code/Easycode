# vNext 项目格式 6

状态：`Approved`（格式 6、ProgramDocument、扩展 Manifest/lock 与发布隔离边界已冻结）

最近修订：2026-09-01

## 1. 目录

```text
project.json
easycode.lock
program/
  functions/<function_id>.json
  variables.json
assets/
  registry.json
  image/
  ocr/
  page/
extensions/<package_id>/
  easycode-extension.json
  easycode-extension.sig
  contracts/
  src/
  dist/
extension-data/<package_id>/
player/
  form.json
  profiles.json
tests/
.easycode/
  view-state.json
  history/
  cache/
  recovery/
```

- `program/functions/*.json` 保存项目函数 ProgramDocument，是项目函数唯一可编辑事实。
- `program/variables.json` 保存项目变量定义，不保存某次运行值。
- `extensions/<package_id>/` 可保存项目级扩展的 `easycode-extension.json`、签名、独立函数契约、外部 IDE 源码和 `dist/*.ecxrt` 密封产物；源码只用于受信任开发，Publisher 只读取 lock 选择的密封产物。
- `extension-data/<package_id>/` 保存功能扩展的项目业务数据，每个包声明独立 Schema 版本且不得写入其他命名空间。
- `.easycode/view-state.json` 只保存本机折叠、滚动、选择和面板尺寸，不参与编译或业务事务。
- `image/ocr/page` 是默认用途目录，不是互斥资源类型；长期引用始终使用稳定 `asset_id`。
- `player/form.json` 保存作者定义的渲染器无关 Player Schema、稳定字段绑定和逐字段终端动作策略；动作默认集合为空。
- `player/profiles.json` 只保存作者随项目提供的运行方案模板，不保存某个终端用户的本机运行方案、操作系统授权、外部文件引用或私有图片覆盖。终端运行数据位于 Player 的产品/实例数据目录。
- 录制帧、会话索引、不可变分析输入快照、分析报告和导出暂存不属于项目格式，也不写入 `.easycode/`。它们位于 IDE 测试环境或 `product_id + Player instance` 隔离的版本化本机数据目录，不能进入 Git、`.ecplayer`、Android APK 或项目内容更新。

## 2. project.json

项目清单至少包含：`format_version: 6`、稳定 `project_id`、项目元数据、`entry_function_id`、`program_model_version`、最低编译器/运行时版本、`targets_schema_version`、判别式目标定义、默认目标 ID、已启用功能扩展 ID，以及 Player/发布配置引用。Android 基础 Runtime 支持 API 21；项目不手写 `minSdk`，Compiler 从实际函数、语言机制、Player 动作与扩展闭包推导最高 API 要求，ECIR 同时保存数值和稳定语句依据，发布报告与成品 APK 必须一致。`compileSdk/targetSdk` 固定为 37；正式发布 ABI 为 `arm64-v8a + armeabi-v7a`，`x86_64` 只能作为独立开发/模拟器产物，不进入正式通用包。项目可以引用应用标识、版本、编译器派生的权限清单和外部签名配置名称，但 release 只接受项目外部 keystore/CI secret；签名密钥、口令、设备授权令牌等秘密不得写入项目或 `.ecplayer`。网络级别和权限闭包不由项目手写总开关决定；Compiler 根据函数、扩展依赖与作者实际发布的 Player 字段动作生成可重建报告。

目标注册表虽然与项目元数据同存于 `project.json`，但以 `targets_schema_version + targets + default_target_id` 的规范化内容单独计算 revision。修改目标必须提交 `expected_revision`；项目名称等无关字段变化不制造虚假目标冲突。发布器把规范化目标块及其 revision 写入 `.ecplayer`，Bundle Loader 在运行前重新校验 Schema、默认引用和 revision。Windows 目标、ADB 目标与 Android 本机目标不能保留其他类型字段；ADB 首版保存明确的 `device_serial`，不保存自动发现或厂商猜测规则。

项目清单不保存窗口句柄、ADB 临时连接、机器绝对路径、界面选择或运行期变量值。显示名不得作为 ProgramDocument、Player 或扩展对象的长期绑定键。

## 3. ProgramDocument 文件

每个项目函数独占 `program/functions/<function_id>.json`，并至少包含 `schema_version`、`document_id`、函数稳定 ID、函数契约、局部符号和语句树。语句树内每个持久化可配置值节点包含在项目中唯一的稳定 `value_id`；移动子树保留 ID，复制子树递归生成新 ID，删除后的 ID 不静默复用。

异常区域可以缺省或保存一个可选 `retry_policy`。策略中的最大再试次数与间隔使用带稳定 `value_id` 的类型化值节点；策略不存在即表示关闭，不再保存另一份函数级重试配置。包含直接或传递副作用时，区域保存基于规范化主体内容和 `easycode.lock` 函数契约指纹计算的审核指纹；主体、引用函数或契约变化后，旧指纹不再有效。该审核事实只证明作者看过重复副作用风险，不表示运行时会回滚或保证外部操作幂等。

调用 `目录.递归删除` 的语句保存独立作者危险审核事实。审核指纹由稳定 `statement_id`、目录参数绑定的规范化值树、函数契约指纹和权限版本计算；任何一项变化后旧审核失效。该事实只授权项目进入编译/发布检查，不包含终端实际路径或操作系统权限，也不能替代 IDE 调试或 Player 对 `authorization_root_id + execution_config_revision` 的实际执行确认。

规范化序列化使用 UTF-8、统一换行、固定字段顺序、稳定数值表示和确定性集合排序。相同业务模型必须产生相同规范化字节；内容哈希由这些字节计算。滚动、折叠、选择、临时诊断、运行状态和 Control 草稿不得写入 ProgramDocument。

没有默认值的必填参数以显式 `unset` 值节点持久化。包含 `unset` 的文档可以保存，但不能编译、运行或发布。损坏 JSON、未知 Schema、重复稳定 ID 和破损结构不能由 IDE 静默修补并覆盖。

## 4. easycode.lock 与扩展数据

`easycode.lock` 锁定每个被引用官方/扩展函数的稳定 `function_id`、精确契约版本与规范化契约指纹，并锁定纯值操作注册表版本/内容哈希、扩展包、原生依赖、编译器/ECIR 版本、依赖图和内容哈希。打开项目不得静默升级，也不得用当前注册表中的同名函数替换锁定函数。

兼容更新与破坏性迁移都必须先计算 ProgramDocument 调用、Player 绑定、目标平台和发布闭包影响。开发者确认后，ProgramDocument、Player Schema 与 `easycode.lock` 作为同一项目事务提交；取消、写入失败或迁移后验证失败时三者保持原版本。函数显示名、分类和搜索别名不进入锁定身份。

项目级扩展实现与业务数据必须分离：

- `extensions/<package_id>/easycode-extension.json` 是扩展唯一业务清单，Manifest 线格式固定为版本 `1`；旧 `capability.json` 不兼容；
- `extensions/<package_id>/` 可包含 Python/原生源码、测试、独立函数契约和密封运行产物；开发源码不能进入发布；
- `extension-data/<package_id>/` 保存该扩展自己的版本化业务事实；
- `easycode.lock` 记录实际启用版本、Manifest/发布者指纹、信任模式、精确依赖、所选宿主变体、密封产物哈希和函数契约指纹；
- `.easycode/cache` 只保存可重建缓存。

安装范围、项目启用状态和本机信任决定不属于 Manifest 自声明字段。Python/原生代码只有在本机批准为可信代码后才可执行；另一台机器读取同一项目时若缺少发布者信任或本机批准，只能保持未启用/声明式检查，不能依据 lock 静默执行。

禁用扩展不自动删除其数据。禁用、更新或卸载前，Extension Service 先计算 ProgramDocument、Player、资源和其他扩展引用，再用项目事务提交锁文件与配置；存在引用时默认阻止。

## 5. 自动保存、冲突与恢复

结构命令由 Program Service 校验并原子保存成功后，前端才采用返回的新 ProgramDocument 与 revision；Control 内未提交的输入继续留在本地草稿。连续界面状态使用短防抖保存，失焦、切换函数、运行、发布和关闭前冲刷已提交命令。

保存流程固定为：Schema/引用校验 → 比较基线内容哈希 → 同目录临时文件写入 → 原子替换 → 发布新哈希。失败时保留内存模型、Control 草稿和撤销历史。

外部修改导致基线不一致时，IDE 展示当前命令使用的共同基线与磁盘 revision，并允许重新加载后重交仍保留的 Control 草稿，或保留界面稍后处理。由于可编辑事实只通过原子结构命令提交，不提供会抹掉无关外部改动的整文档强制覆盖。系统不得静默选择版本，也不得自动重试形成持续 409。

每次 ProgramDocument 替换或删除前，先在 `.easycode/history/program/functions/` 写入修改前快照。恢复前再次保留当前有效版本；若当前文件损坏，则先把原始坏字节移入 `.easycode/recovery/program/functions/` 的证据副本。项目检查发现损坏时只进入显式恢复状态，用户未选择历史版本前不得激活编辑工作区或覆盖磁盘。

Control 内未提交输入只属于编辑会话。合法输入提交为结构命令；不合法输入在切换或关闭前要求修复或放弃，并可进入 `.easycode/recovery`，但不能伪装成已保存 ProgramDocument。

## 6. 视图状态

`.easycode/view-state.json` 可以保存活动工作区、打开函数、语句折叠、滚动、面板尺寸和最后选择。它按稳定 ID 引用对象，读取失败时恢复默认布局；删除它不得改变程序、页面、Player 或发布结果。

功能扩展的拓扑布局等派生视图也进入独立视图命名空间，不能写回决定业务路径的扩展字段。

## 7. 发布边界

`.ecplayer` 包含签名 ECIR、函数契约、Player Schema、目标配置、资源、启用扩展运行闭包和发布报告。它不包含：

- `program/` 与 ProgramDocument；
- `.easycode/`；
- 扩展源码、测试和外部 IDE 配置；
- 扩展构建脚本、包管理清单、开发入口或 lock 未选择的变体；
- 未进入依赖闭包的资源或扩展数据；
- IDE 视图状态和编辑元数据。

`.ecplayer` 是平台中立的逻辑发布内容，不等于终端安装包。Windows 发布器把它与 Windows Runtime 组成独立 Player Bundle；Android 发布器把兼容内容、Android Runtime、小屏 Player UI、资源与目标平台扩展闭包组成签名 APK。Android APK 不得引用 Windows 盘符、IDE 项目目录、Python 环境或开发机动态依赖。

发布闭包必须包含离线启动和执行所需的 OCR 数据、字体/图标、原生库与扩展产物，并附带“无网络 / 本机或局域网 / 公网”能力报告。签名密钥、本地授权私钥、远端凭据和遥测令牌不进入项目或发布内容；运行时不得因缺少预热缓存转而下载必需依赖。

项目发布配置可以保存稳定更新 `product_id`、Player 应用/项目内容更新模式、提供方无关的更新源引用、通道和作者策略，但不得保存发布私钥、上传令牌、作者登录会话或终端安装状态。官方托管与自建源的上传凭据只进入 IDE 本机安全存储；导出的签名 Feed 不依赖专有项目字段。发布结果使用不可变 `release_id`、单调 `release_sequence`、平台/架构/Runtime/ECIR 兼容范围、大小、哈希和签名；这些属于发布/维护事实，不写入 ProgramDocument。任务运行网络与在线维护网络分别计算和展示。完整契约见 [`UPDATES.md`](UPDATES.md)。

## 8. 版本边界

新建项目固定使用格式 `6`。格式 6 不兼容旧画布项目、`.easy` 项目或格式 5；打开旧格式时只显示“此项目版本不受支持，请新建格式 6 项目”，不提供迁移、修复、静默初始化或兼容写回。

未来升级必须声明可读版本范围、只读策略、Schema 事务、失败恢复和发布兼容矩阵，不能仅凭缺少字段猜测版本。

## 8.1 扩展清单与锁版本

格式 6 固定使用 `easycode-extension.json` 的 `manifest_version: 1`、`easycode.lock` 的 `lock_version: 1` 和密封产物格式 `ecx-runtime-1`。Manifest 分别声明 `host` 与 `targets`；Windows/ADB 发布选择 Windows 宿主变体，Android APK 选择 Android 本机变体。完整字段、信任与发布闭包见 [`EXTENSIONS.md`](EXTENSIONS.md)。

格式 6 项目缺少 lock、Manifest/lock 哈希漂移、所选变体无密封产物、密封产物签名不符或发布包发现扩展源码时，Compiler/Publisher 必须停止并定位 `package_id + variant_id`，不能复制整个扩展目录或在运行时下载补齐。

## 9. Player Schema 与终端动作格式

`player/form.json` 中每个字段至少拥有稳定 `control_id`、判别式源绑定、类型指纹、Control 契约、默认值/校验/显示条件和终端动作列表。源绑定继续指向稳定函数、语句、参数、`value_id`、项目变量、资源或目标 ID；终端动作不能改变绑定目标、值来源种类或 ProgramDocument 结构。

终端动作项至少包含稳定 `action_id`、动作种类、允许平台集合和该动作的类型化约束。文件/目录动作还包含读取/写入访问模式及允许的文件类型；图片动作区分“从当前画面截取图片”和“从设备选择图片”；手势路径动作不得与文件路径动作共用种类。动作列表缺省或为空即表示不向终端开放，不能通过旧版本缺字段推断为全部开放。

Player Schema 只保存作者授权与静态约束，不保存：

- 终端用户是否曾同意 MediaProjection、Accessibility 或文件授权；
- 活动 Capture Session、系统选择器请求或未确认候选；
- 终端本机绝对路径、Android 文档 URI、外部文件/目录引用；
- Player 私有图片覆盖、运行方案当前值或临时错误状态。
- 录制会话、帧、分析报告、导出文件及其本机空间/保留设置。
- 递归删除实际执行确认；该确认属于 IDE 调试配置或当前 Player 实例运行方案的终端事实，并绑定 `authorization_root_id`、稳定调用、执行配置 revision 与函数契约指纹。

这些终端事实进入按 `product_id + Player instance` 隔离的数据目录，并以运行方案 revision 原子更新。Player Capture 使用运行期判别式 `PlayerControlDestination` 定位 `product_id + release_id + profile_id + profile_revision + control_id + action_id + target_id`；只有已保存且具有稳定 `profile_id + profile_revision` 的方案能发起字段动作，未保存草稿不创建临时身份。该边界由 ADR-060 和 `AC-PLY-CAP-008` 放行；它不是项目文件，也不能写回 `player/form.json`、ProgramDocument 或签名 ECIR。

Compiler/Publisher 对每个动作验证字段类型、目标平台和宿主实现，并把通过验证的动作编译为签名 Player Schema 与最小权限/能力闭包。未知动作、重复 `action_id`、不兼容返回类型、缺少宿主实现或越权平台声明都会阻止发布；未发布的动作不进入 Windows Bundle/Android APK 的权限、服务或原生模块闭包。

## 10. 需求与验收追踪

- `[REQ-FMT-001]` 新建项目固定写入 `format_version: 6`，项目函数只保存为 `program/functions/*.json` ProgramDocument；格式 5、旧画布和 `.easy` 不迁移或兼容写回。
- `[REQ-FMT-002]` 格式 6 使用 `easycode-extension.json` v1、`easycode.lock` v1 和 `ecx-runtime-1`；Manifest、lock、契约与产物以规范化哈希/签名闭合。
- `[REQ-FMT-003]` lock 固定工具链、官方函数、扩展发布者/信任、精确依赖、宿主变体、密封产物与契约指纹；打开项目不静默解析到其他版本。
- `[REQ-FMT-004]` `.ecplayer`、Windows Bundle 与 APK 不包含 ProgramDocument、`.easycode/`、扩展源码/测试/开发配置或未锁依赖。
- `[REQ-FMT-005]` 所有保存和跨文档迁移使用 revision/hash、原子替换与项目事务；失败保留内存模型、撤销历史和原磁盘版本。

对应验收为 `TESTING.md` 的 `[AC-VN-PGM-001..004]`、`[AC-VN-FMT-001..004]` 与 `[AC-VN-EXT-001..008]`。
