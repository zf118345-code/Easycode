# 扩展平台

状态：`Approved`（首版清单、贡献点、信任、锁定、宿主变体与发布闭包已冻结）

最近修订：2026-09-03

## 1. 定位

EasyCode 使用受控扩展点承接项目特有能力和可选领域功能。用户界面统一使用“扩展”，不提供只有外观、没有安装、启用、运行、发布与失败恢复闭环的插件入口。

扩展分为三层：

| 层级 | 能力 | 首版开放范围 |
| --- | --- | --- |
| 函数扩展 | 注册函数契约及 Python/原生实现 | 项目级、用户级和官方包；执行实现必须取得本机可信代码批准 |
| 功能扩展 | 注册命名空间数据、声明式工作区、函数、编译/运行/Player 模块 | 声明式安全子集可供未信任包使用；可执行贡献必须取得可信代码批准 |
| 目标驱动扩展 | 接入帧、输入、设备和原生权限 | 仅官方或管理员明确批准的受信任实现 |

`easycode-extension.json` 是扩展包唯一业务清单，`easycode.lock` 是当前项目解析、信任和交付选择的唯一锁定事实。旧 `capability.json`、目录扫描猜测、Python 签名反推和显示名匹配不进入首版兼容路径。

## 2. 安全与信任边界

Python、C++、Kotlin 或其他会执行代码的扩展属于可信本地代码。用户或管理员必须在安装/首次启用前看到发布者指纹、代码来源、权限、网络级别、宿主变体和依赖，并明确批准；包不能在自己的 Manifest 中声明“我已受信任”。

Worker 提供以下可靠性边界：进程生命周期、依赖目录、超时、取消、结构化日志、参数/返回序列化、崩溃检测和资源回收。它不是抵御恶意代码的安全沙箱：受信任 Python/原生代码可能直接使用操作系统 API 访问同一用户有权访问的文件、网络或进程。权限清单仍必须用于 EasyCode 宿主 API 的强制检查、作者/用户审核、发布闭包和网络报告，但产品不得把它宣传为对恶意本地代码的完整隔离。

未取得可信代码批准的第三方包只能贡献不执行扩展代码的声明式安全子集：函数/类型文档、数据 Schema、使用批准 Control 和批准命令的声明式列表/表单视图、静态帮助与 Harness 元数据。它不能贡献 Python/原生入口、编译步骤、运行服务、Player 原生模块、目标驱动、任意 Vue/HTML/JavaScript、动态表达式或自定义网络客户端。

安装范围、项目启用状态、可信代码决定、撤销时间和批准者保存在本机扩展注册表/项目配置；Manifest 只声明包自身事实。`easycode.lock` 记录构建本项目时实际采用的发布者指纹与信任模式，使同一项目不会在另一台机器上静默获得更高权限。

## 3. `easycode-extension.json` 线格式

Manifest 使用 UTF-8 JSON、固定 `manifest_version: 1` 和严格 Schema。未知行为字段、未知贡献类型、重复稳定 ID 或路径越出包根均阻止发现；纯展示扩展字段只能放入 `display.metadata`，不得改变行为。

规范示例：

```json
{
  "manifest_version": 1,
  "package_id": "com.example.vision-tools",
  "publisher_id": "publisher.example",
  "version": "1.2.3",
  "display": {
    "name": "示例视觉工具",
    "description": "提供一个类型化视觉函数",
    "homepage": "https://example.invalid/vision-tools",
    "metadata": {}
  },
  "tier": "function",
  "requires": {
    "easycode": ">=6.0.0 <7.0.0",
    "program_schema": 1,
    "ecir": 1
  },
  "activation": ["on_project_enable", "on_function_call"],
  "dependencies": [
    {
      "package_id": "org.example.shared-types",
      "version": ">=1.0.0 <2.0.0",
      "optional": false
    }
  ],
  "permissions": ["target.frame.read"],
  "network": {
    "level": "none",
    "rules": []
  },
  "contributions": {
    "function_contracts": [
      {
        "contribution_id": "functions.main",
        "path": "contracts/functions.json"
      }
    ],
    "data_schemas": [],
    "workspaces": [],
    "compiler_steps": [],
    "runtime_modules": [
      {
        "contribution_id": "runtime.vision-tools",
        "variant_bindings": ["windows-x64-py312"]
      }
    ],
    "player_modules": [],
    "harness_adapters": [],
    "target_drivers": []
  },
  "variants": [
    {
      "variant_id": "windows-x64-py312",
      "host": "windows",
      "targets": ["windows", "android_adb", "none"],
      "runtime": "python-worker-3.12",
      "development_entry": "src/entry.py",
      "artifact": {
        "path": "dist/vision-tools-windows-x64.ecxrt",
        "format": "ecx-runtime-1",
        "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "signature": "dist/vision-tools-windows-x64.ecxrt.sig"
      }
    }
  ],
  "data": {
    "schema": "schemas/project-data.json",
    "schema_version": 1
  },
  "licenses": [
    {
      "id": "MIT",
      "path": "LICENSE"
    }
  ]
}
```

扩展根目录还必须包含同级 `easycode-extension.sig`。签名信封使用 `publisher_id` 对应的 Ed25519 密钥签署一个规范化载荷：`easycode-extension.json` 的 SHA-256 与除 Manifest、签名信封和 Manifest 已声明密封产物外的精确 `files[]` 清单；每项文件记录规范化相对路径、大小和 SHA-256。安装时重新枚举并逐项比对，未知文件、删除、替换、路径穿越和符号链接均使签名验证失败。密封产物及其独立签名由 Manifest 和 `easycode.lock` 继续锁定，从而形成覆盖开发包与发布产物的两级完整性闭包。

字段契约：

| 字段 | 规则 |
| --- | --- |
| `manifest_version` | 首版固定为整数 `1`；未知版本只读诊断，不猜测兼容 |
| `package_id` | 全局稳定、小写反向域名形式；安装后不可因显示名改变 |
| `publisher_id` | 对应签名发布者身份；实际公钥指纹由包签名和本机信任库确认 |
| `version` | 语义化版本；依赖解析只使用版本与稳定包 ID |
| `display` | 名称、说明、主页和无行为元数据；不参与身份和权限 |
| `tier` | `function / feature / target_driver` 三选一 |
| `requires` | EasyCode、Program Schema 和 ECIR 的兼容范围；缺失或不兼容时阻止启用 |
| `activation` | 只允许 `on_project_enable / on_function_call / on_workspace_open / on_run_start`；触发不授予权限 |
| `dependencies` | 稳定包 ID、版本范围和可选性；解析后在 lock 中写精确版本与哈希 |
| `permissions` | 使用注册表中的稳定权限 ID；未知权限阻止启用和发布 |
| `network` | `none / local_lan / public` 及规范化主机/端口规则；与函数的动态网络规则共同进入发布报告 |
| `contributions` | 仅允许已版本化贡献点；所有路径都相对包根并由 Manifest 签名覆盖 |
| `variants` | 把运行宿主与可操作目标分开声明，并引用开发入口和/或密封产物 |
| `data` | 包命名空间业务数据的 Schema 路径与版本；没有业务数据时为 `null` |
| `licenses` | SPDX ID/自定义许可证文件及交付要求；缺少所需材料阻止发布 |

函数契约保存在 Manifest 引用的独立 JSON 文件中，而不是从 Python 函数签名猜测。每项声明稳定 `function_id`、`contract_version`、参数/返回、异常、平台、宿主/目标能力、权限、副作用、摘要和实现绑定；规范化指纹进入 `easycode.lock`。

## 4. 宿主与目标变体

`host` 只允许 `windows` 或 `android_native`；`targets` 只允许 `windows / android_adb / android_native / none`。两者含义不可合并：

- Windows 宿主变体可以声明 `windows`、`android_adb` 和 `none`；Windows 上操作模拟器仍选择 Windows 变体。
- Android 本机宿主变体只能声明 `android_native` 和 `none`，不得选择 Python/Windows 变体。
- Android 本机宿主变体必须显式声明 `minimum_android_api: 21..37`；该值进入 Manifest 签名、`easycode.lock`、函数契约投影、最终 ECIR 依据和 APK `minSdk`。API 21 是基础 Runtime 下限，不生成一条重复的“提级依据”；只有高于 21 的变体才进入发布摘要来源。发布前和 Android 设备加载前都必须比较 lock、密封运行描述、ECIR 依据与发布报告，任一缺失、篡改或不一致均在执行扩展代码前失败。Windows 变体不得声明此字段，平台也不以测试设备版本替作者猜测。
- `targets` 是该变体能承接的上限；每个函数契约还要声明更细的目标能力，Compiler 取两者交集。
- 只有开发入口而没有当前宿主密封产物的变体可以在明确受信任的开发模式调试，但不能发布。
- Android 只接受发布工具认可、ABI 完整且签名有效的 Kotlin/JVM 或 C++/NDK `ecx-runtime-1` 产物。Python-only 变体不能进入 APK。
- `android-kotlin-v1` 的密封描述必须把一个 `.jar` 文件声明为 `module`，`entrypoints` 映射到实现稳定 EasyCode Android 扩展 ABI 的 JVM 二进制类名。该 JAR 只在 APK 构建期通过验证后静态链接；内容更新和运行时不得下载、解压加载或替换可执行代码。运行时调用由独立 `:extension_worker` 进程承接，APK 内生成的注册表必须与签名 lock、发布描述和模块哈希精确一致。

`development_entry` 仅供外部 IDE/本机开发调试定位，不是发布入口。EasyCode 不执行 Manifest 中的任意构建命令；开发者或受控工具链生成密封产物后，Extension Service 重新计算哈希、验证签名并刷新 lock。

Android Kotlin/JVM 的作者工作流程固定为：在 Android Studio、Gradle 或其他外部 IDE 把实现编译成 JAR → 在 EasyCode 对应 Android 宿主变体选择“导入 JAR” → 后端校验 JAR 路径、规模、入口类、源码/原生库/DEX 泄漏和旧 JAR 签名 → 生成确定性 `ecx-runtime-1` 并用当前发布者身份重签 Manifest 与产物 → 再由作者启用扩展写入 lock。已启用扩展必须先停用才能替换 JAR，避免锁定内容在项目运行期漂移。

## 5. 贡献点

每个贡献对象都具有包内唯一、稳定的 `contribution_id`；引用时使用 `package_id + contribution_id`。首版允许：

- `function_contracts`：声明式函数/类型契约；可被安全读取，真正执行仍要求兼容运行变体。
- `data_schemas`：包命名空间数据 Schema 与版本迁移描述；迁移实现若执行代码则要求信任。
- `workspaces`：批准 Control、列表、表单、命令和扩展数据投影组成的声明式工作区；不能注入任意前端代码。
- `compiler_steps`：读取本扩展唯一模型并产生经过命名空间约束的 ECIR/依赖结果；只向官方或可信代码开放。
- `runtime_modules`：密封运行模块及入口；只向可信代码开放。
- `player_modules`：声明式 Player 区块或密封原生模块；代码模块要求可信代码并进入包体/权限报告。
- `harness_adapters`：开发/测试适配器，不进入正式产品清单或 Player 发布闭包。
- `target_drivers`：帧、输入、设备或权限驱动；只向官方或管理员批准的受信任包开放。

普通第三方扩展不能增加 ProgramDocument 语句种类、修改核心 Store、读写其他包数据、绕过 Control Registry 或用工作区创建第二份业务事实。功能扩展自己的版本化命名空间模型是该扩展唯一业务事实；列表、图形和其他视图只能投影或通过受约束命令修改该模型。

## 6. `easycode.lock` 线格式

锁文件使用 UTF-8 确定性 JSON 和 `lock_version: 1`。最小结构如下：

```json
{
  "lock_version": 1,
  "project_format": 6,
  "toolchain": {
    "compiler_version": "6.0.0",
    "program_schema": 1,
    "ecir": 1,
    "pure_value_registry_version": 9,
    "pure_value_registry_sha256": "7777777777777777777777777777777777777777777777777777777777777777"
  },
  "official_functions": [
    {
      "function_id": "official.log.output",
      "contract_version": "1.0.0",
      "contract_fingerprint": "8888888888888888888888888888888888888888888888888888888888888888"
    }
  ],
  "extensions": [
    {
      "package_id": "com.example.vision-tools",
      "version": "1.2.3",
      "scope": "project",
      "manifest_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
      "content_sha256": "9999999999999999999999999999999999999999999999999999999999999999",
      "publisher_id": "publisher.example",
      "publisher_key_fingerprint": "2222222222222222222222222222222222222222222222222222222222222222",
      "publisher_public_key": "base64-encoded-ed25519-public-key",
      "trust_mode": "local_trusted_code",
      "dependencies": [
        {
          "package_id": "org.example.shared-types",
          "version": "1.4.0",
          "content_sha256": "3333333333333333333333333333333333333333333333333333333333333333"
        }
      ],
      "selected_variants": [
        {
          "target": "windows",
          "host": "windows",
          "variant_id": "windows-x64-py312",
          "runtime": "python_worker",
          "artifact_sha256": "4444444444444444444444444444444444444444444444444444444444444444",
          "artifact_signature_sha256": "5555555555555555555555555555555555555555555555555555555555555555"
        }
      ],
      "function_contracts": [
        {
          "function_id": "com.example.vision-tools.detect",
          "contract_version": "1.0.0",
          "contract_fingerprint": "6666666666666666666666666666666666666666666666666666666666666666"
        }
      ]
    }
  ]
}
```

`trust_mode` 只允许 `official / publisher_trusted / local_trusted_code / declarative_only`，它记录本机解析时采用的信任结果，不来自 Manifest。另一台机器缺少对应发布者信任或本机批准时只能降级为未启用/声明式检查，不能直接执行 lock 中的代码。

打开项目不得静默升级 lock。兼容更新和破坏性迁移都先展示受影响 ProgramDocument、Player、平台、权限和发布闭包；确认后把 ProgramDocument、Player Schema、项目启用列表和 lock 作为项目事务提交。失败或取消保持旧锁可构建。

## 7. 开发、启停与失败语义

Python/原生扩展使用 PyCharm、VS Code 或其他外部 IDE 开发。EasyCode 只提供骨架、导入、外部打开、Manifest/契约审核、受信任开发运行、测试、启停、引用分析、密封产物校验和发布检查，不内置完整代码编辑器。

未启用扩展必须为零工作区、零命令、零函数入口、零 Worker、零轮询、零编译输入、零 ECIR/Player 依赖和零包体污染。启用前校验 Manifest、签名、信任、依赖、当前宿主变体、函数契约和数据 Schema；任一步失败都不改变原启用状态。

禁用、更新或卸载前计算 ProgramDocument、Player Schema、资源、扩展数据和其他扩展引用。存在引用时默认阻止并给出稳定 ID 定位。扩展崩溃、超时、非法返回或依赖缺失产生结构化诊断，不能拖垮 IDE/Player 或伪报函数成功。

## 8. 发布与源码隔离

密封运行产物使用 `ecx-runtime-1` 不可变容器，包含目标宿主执行所需的编译代码、运行数据、依赖、许可证索引和入口元数据，并由 Manifest 中的哈希/签名及 `easycode.lock` 固定。密封表示发布后不可由项目编辑器修改且可以验证完整性；它不承诺防逆向、加密保密或 DRM。

Publisher 只从 lock 的 `selected_variants` 收集密封产物。以下内容一旦出现在 `.ecplayer`、Windows Bundle 或 APK 中即构成发布失败：

- 扩展 `src/`、`tests/`、Python/C++/Kotlin/Java 源码与类型存根；
- 构建脚本、包管理清单、外部 IDE 配置、版本控制数据和开发入口；
- Manifest 未声明或 lock 未固定的运行依赖、模型、字体、网络端点或许可证；
- 与目标宿主/ABI 不匹配的变体，或运行期下载依赖的入口。

Bundle Loader 在加载前再次验证格式、签名、Manifest/lock/产物哈希、路径穿越、符号链接、体积、ABI、函数契约、权限和网络结论。验证失败保持当前已安装版本并返回可定位诊断，不尝试联网补齐。

## 9. 首版范围

首版支持项目内扩展、用户级共享扩展和随 IDE 分发的官方扩展；不建设公开市场、评分、付费、自动推荐或脱离固定信任链的任意远程代码安装。在线 Player/项目更新只分发已经签名并通过相同闭包检查的完整内容，不改变此边界。

首版不交付页面导航扩展、Page Model、`页面.*` 函数、扫描服务、拓扑投影或 Player 依赖。`image / ocr / page` 始终是通用资源分类；保存到 `page` 不激活任何扩展。中立 Harness 扩展只在测试环境验证贡献点和生命周期，不进入产品扩展清单或正式发布包。

## 10. 需求

### 10.1 展示与交互制作标准

扩展不是一块可任意嵌入的网页。所有贡献先进入平台已有的信息架构，再由平台组件投影：

- 函数扩展进入函数库“扩展”分页，按命名空间分组；列表只展示名称，说明、参数、权限、目标与返回类型进入统一检查器。
- 参数必须声明稳定类型和 Control 契约，直接复用 IDE/Player 的输入框、选择器、采集按钮、校验、引用和值表达式；扩展不得绘制第二套表单。
- 声明式工作区默认作为扩展中心的子视图；只有高频、独立且用户主动固定的工作区才可出现在活动栏。卸载时固定入口同时撤销。
- Player 贡献只能进入作者明确选择的页面/区段，服从同一栅格、间距、错误和权限说明；扩展不能覆盖作者页面或弹出系统业务确认框。
- 名称必须回答“对象 + 动作”，命名空间不得使用“官方”“系统”等保留来源；图标从平台图标集合选择，不能以图片模拟按钮或文字。
- 每个可见入口都必须同时具备启用、禁用、只读、加载、空、错误、权限不足和引用阻断状态。没有后端承接的展示入口不得发布。
- 扩展关闭后必须达到零入口、零命令、零 Worker、零轮询和零发布污染；删除前显示精确引用并跳转，不能静默留下失效卡片。

项目级中立展示扩展由 `scripts/manage_extension_showcase.py` 管理。它覆盖文本、布尔、数值、列表、可选默认值、返回绑定、签名 Worker、契约测试、目录投影与可卸载生命周期。它只用于 DDT/Harness，不属于正式产品扩展。

声明式工作区还必须提交 `WorkspaceUiContractV1`，并在发现阶段通过宿主校验。公开 TypeScript 契约与共享组件出口位于 `frontend/src/vnext/uiSystem.ts` 和 `frontend/src/vnext/components/ui/index.ts`。契约固定声明界面系统版本、稳定工作区 ID、用户名称、拓扑、主对象、页面动作、状态所有权、检查器、窄屏方式、键盘入口、权限摘要和危险命令。宿主拒绝以下贡献：同屏多个主操作、状态缺失、带检查器却没有互斥抽屉、危险操作没有稳定命令 ID，或试图提交 HTML、JavaScript、Vue 与全局 CSS。

扩展作者只描述内容和命令，不描述像素。标题栏、列表、表单、空状态、通知、对话框、焦点、响应式抽屉和 Player 触控尺寸全部由 EasyCode 宿主渲染。这样扩展可随主题与平台一起升级，卸载后也不会留下样式和交互残片。

- `[REQ-EXT-001]` 每个扩展使用严格 `easycode-extension.json` v1 声明稳定包/发布者身份、版本、层级、兼容范围、激活、依赖、权限、网络、贡献、宿主/目标变体、数据与许可证。
- `[REQ-EXT-002]` 项目使用确定性 `easycode.lock` v1 锁定工具链、官方函数、扩展清单、发布者指纹/信任模式、精确依赖、所选变体、密封产物及函数契约哈希；打开项目不得静默升级。
- `[REQ-EXT-003]` 未启用扩展为零入口、零后台、零编译/Player 依赖和零包体污染；启停、更新和卸载以引用分析与项目事务完成。
- `[REQ-EXT-004]` Worker 提供故障与生命周期隔离，但产品不得把 Python/原生可执行扩展宣传为恶意代码沙箱；执行代码前必须取得本机可信代码批准。
- `[REQ-EXT-005]` 未信任包只能使用不执行代码的声明式安全贡献子集，不能贡献任意前端、编译/运行模块或目标驱动。
- `[REQ-EXT-006]` Manifest 分别声明运行宿主和可操作目标；Windows/ADB 使用 Windows 变体，Android 本机发布使用经过 ABI/签名校验且显式声明最低 Android API 的 Android 变体。
- `[REQ-EXT-007]` 功能扩展使用自身版本化命名空间模型作为唯一业务事实；普通第三方扩展不能修改 ProgramDocument Schema、核心 Store 或其他扩展数据。
- `[REQ-EXT-008]` 发布只携带 lock 选择的密封运行产物；扩展源码、测试、构建/IDE 配置和未锁依赖必须在发布前或加载前被拒绝。
- `[REQ-EXT-009]` 发布器从真实函数、贡献、产物和权限计算平台/网络/许可证闭包；缺少变体、依赖或材料时阻止发布，不在运行期下载。
- `[REQ-EXT-010]` Manifest、贡献点、函数契约、lock 与密封产物都使用规范化哈希和签名验证；篡改、路径越界、未知版本或重复稳定 ID 不得进入启用状态。
- `[REQ-EXT-011]` 项目级、用户级和官方扩展可以被发现；公开市场、评分、付费和任意远程代码安装不属于首版。
- `[REQ-EXT-012]` 官方、用户和项目扩展使用同一 Manifest、签名、密封产物和运行契约；安装范围不得形成第二种包格式。
- `[REQ-EXT-013]` 新领域扩展在提升为官方随附包前，必须以用户或项目范围真实导入并完成信任、启用、锁定、调用、发布、禁用和卸载。
- `[REQ-EXT-014]` 自动验收必须从可分发包开始，不得直接把仓库源码路径登记为已安装扩展；官方提升复用相同产物。
- `[REQ-EXT-015]` 项目创建向导只能在显示版本、体积、权限和平台后由用户勾选推荐包，不得静默预装到项目。
- `[REQ-EXT-012]` 首版产品和发布物不包含页面导航扩展或入口；中立 Harness 扩展不得出现在产品清单。
- `[REQ-EXT-013]` Android Kotlin/JVM 扩展由外部工具链编译 JAR，EasyCode 提供变体级导入、结构/入口/发布者校验、确定性密封和签名事务；不执行扩展自带构建脚本，不接受源码、DEX、原生库或失效 JAR 签名混入该产物。
- `[REQ-EXT-014]` 扩展权限使用平台维护的稳定 ID 注册表。未知或重复权限在解析时失败；函数权限必须属于扩展已声明权限，Android 变体的 `minimum_android_api` 不得低于所用权限下限。发布器将实际入口函数的权限、扩展声明权限和对应 Android Manifest 权限写入不可编辑注册表，设备端与签名描述逐项复核；成品 APK 检查器还必须证明 Manifest 已请求扩展闭包所需系统权限。该注册表用于审核、构建闭包和宿主 API 边界，不把受信任本地代码宣传为 OS 沙箱。
- `[REQ-EXT-015]` 扩展内容只能进入平台登记的函数库、声明式工作区、Player Control、目标驱动和发布槽位；函数目录必须保留来源和包身份，关闭扩展后不得残留任何可见或运行入口。
- `[REQ-EXT-016]` 扩展函数沿用统一参数输入器及核心值语法，但只能作为独立流程语句插入；扩展不得注册私有表达式命名空间、纯操作、运算符或解析别名。需要表达式内算法时由核心提案与跨平台注册表流程统一纳入，不能通过 Manifest 绕过。

## 11. Harness 放行

- `[AC-VN-EXT-001]` 有效/无效 Manifest、签名、依赖、权限、贡献点、宿主/目标变体和数据 Schema 均经过严格 Schema 与集成测试。
- `[AC-VN-EXT-002]` 相同解析输入生成规范化等价 lock；本机版本漂移、发布者指纹变化、信任缺失和依赖冲突不会静默改写项目。
- `[AC-VN-EXT-003]` 未启用扩展没有入口、Worker、轮询、编译输入、ECIR/Player 依赖或包体文件；启停事务失败回到原状态。
- `[AC-VN-EXT-004]` 未信任包的可执行贡献被阻止，声明式安全视图不能注入脚本或越权命令；可信代码批准、撤销和换机缺失具有真实状态。
- `[AC-VN-EXT-005]` Worker 的超时、取消、崩溃、非法返回、序列化失败和缺失依赖产生定位到 `package_id + contribution_id/function_id` 的诊断，不拖垮宿主。
- `[AC-VN-EXT-006]` Windows/ADB 与 Android 真机分别加载锁定密封变体；Python-only、ABI/签名不兼容或缺少目标能力的扩展在发布前失败。
- `[AC-VN-EXT-007]` 发布包扫描证明不存在扩展源码、测试、构建/IDE 配置、未锁依赖或运行期下载入口；Bundle Loader 拒绝篡改、路径越界和哈希漂移。
- `[AC-VN-EXT-008]` 中立扩展覆盖函数、声明式工作区、命名空间数据、受信任编译/运行模块、禁用回收和发布闭包，但不进入产品清单或正式包。
- `[AC-VN-EXT-009]` 未知、重复、未声明、API 下限不足和 APK 注册表篡改的扩展权限均在执行前失败；合法权限确定性投影到 Android Manifest 权限，成品缺少任一所需权限时构建失败。
- `[AC-SCOPE-PAGE-001]` IDE、Windows Bundle 与 Android APK 均不存在页面导航包、入口、`页面.*`、Page Model、扫描服务或拓扑组件。

## 12. 当前实现证据

实现入口：

- `core/vnext/extension_schema_v6.py`：严格 Manifest、函数契约、签名信封、lock 和 `ecx-runtime-1` Schema，以及路径、ID、哈希、签名和发布闭包校验。
- `core/vnext/extensions.py`、`core/vnext/extension_worker_v6.py`：official/user/project 发现，安装、信任、启停、引用分析、外部 IDE 骨架、契约测试、密封构建和隔离 Worker 调用。
- `core/vnext/publish.py`、`core/vnext/player_bundle.py`：只收集 lock 选择的密封变体，Player 加载时再次验证并调用扩展入口。
- `api/routers/vnext_router.py` 与 `frontend/src/vnext/components/VNextExtensionWorkspace.vue`：真实后端生命周期和主工作区三栏投影；不提供内置 Python 编辑器或签名推断。

自动验证：

- `tests/test_vnext_extensions_v6.py` 覆盖严格 Schema、签名文件闭包篡改、稳定参数映射、确定性 lock、引用阻断、Worker 超时、旧源码接口退役，以及“签名扩展 → 发布 → Player 加载 → 密封函数实际返回”的纵向闭环。
- 同一组扩展/Android 交付测试还覆盖权限注册表、权限 API 下限、构建报告闭包及 APK Manifest 权限解析；`EmbeddedExtensionRegistryTest` 在 Android 设备加载层验证注册表权限不能高于或偏离签名扩展描述。
- `tests/test_vnext_scope_guards.py`、`tests/test_vnext_bundle_signing_v6.py`、`tests/test_vnext_distribution_v6.py` 覆盖 Android 变体阻断、源码排除、Bundle 签名和分发闭包。
- `frontend/src/vnext/__tests__/VNextExtensionWorkspace.test.ts` 覆盖三栏生命周期、真实操作入口和 Python 编辑器退役。

真实 Android Kotlin/JVM 证据（2026-09-03）：

- `tests/fixtures/android_extension` 已用 JDK 17 真实编译成 JAR，通过产品的导入、入口类校验、发布者签名、密封、启用锁定与 APK 静态链接链；该纯计算闭包的成品 Manifest 保持 `minSdk=21`。
- API 34 x86_64 模拟器与 API 33 arm64-v8a 物理手机分别完成四次真实运行：成功返回、`extension.execution_failed`、`extension.timeout`、超时后再次成功。每次成功的 Worker PID 与 Player 主进程不同；超时后 Worker 已消失而主进程仍存活。
- 可重复执行入口为 `scripts/create_android_extension_harness.py` 和 `scripts/verify_android_extension_device.py`；最新结构化证据保存在 `output/g6-android-extension-harness/run-20260903-3/emulator-device-evidence.json` 与 `physical-device-evidence.json`。同目录的 APK evidence 同时记录从成品 Manifest 反查的 `minSdk` 与全部请求权限。

仍需真实宿主验证：独立 Windows Player 可执行文件中的 Worker 生命周期；Android Kotlin/JVM 已有连接状态下的模拟器与物理真机证据，但断开数据线、IDE 与开发后端后的独立启动仍须在 Android 总完成门中验收。C++/NDK 变体仍未实现，不对外宣称支持。
