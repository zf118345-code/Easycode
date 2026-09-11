<template>
    <section :class="['extension-workspace', { 'detail-panel-collapsed': !detailVisible }]" aria-label="扩展管理">
        <VNextNavigationPane class="package-pane">
            <VNextPaneHeader class="pane-heading" title="扩展" :meta="visiblePackages.length">
                <template #actions><div class="heading-actions">
                    <VNextIconButton label="导入扩展到当前项目" :disabled="busy" @click="importFolder('project')"><FolderInput /></VNextIconButton>
                    <VNextIconButton label="导入扩展到当前用户" :disabled="busy" @click="importFolder('user')"><UserRoundPlus /></VNextIconButton>
                    <VNextIconButton label="新建扩展骨架" :disabled="busy" @click="openCreate"><Plus /></VNextIconButton>
                </div></template>
            </VNextPaneHeader>
            <VNextListSearch v-if="packages.length || query" v-model="query" placeholder="搜索扩展包或发布者" aria-label="搜索扩展" />
            <div v-if="!loading && visiblePackages.length" class="package-list app-navigation-list" role="listbox" aria-label="扩展包列表">
                <section v-for="group in groupedPackages" :key="group.scope" class="scope-group">
                    <header><span>{{ scopeLabel(group.scope) }}</span><small>{{ group.items.length }}</small></header>
                    <VNextNavigationItem v-for="item in group.items" :key="packageKey(item)" role="option" class="package-row" density="rich" selectable :selected="packageKey(item) === selectedKey" @click="selectPackage(item)">
                        <span class="package-glyph" :data-state="packageState(item)"><Package :size="15" /></span>
                        <span class="package-copy"><strong>{{ item.display_name }}</strong></span>
                        <span class="row-status" :data-state="packageState(item)">{{ packageStateLabel(item) }}</span>
                    </VNextNavigationItem>
                </section>
            </div>
        </VNextNavigationPane>

        <main class="detail-pane">
            <VNextWorkspaceState v-if="loading || detailLoading" class="detail-state" kind="loading" :title="loading ? '正在读取扩展' : '正在校验扩展包'"><template #icon><LoaderCircle :size="20" class="spin" /></template></VNextWorkspaceState>
            <VNextWorkspaceState v-else-if="!visiblePackages.length" class="detail-state" :kind="query ? 'filtered' : 'empty'" :title="query ? '没有匹配的扩展' : '还没有扩展'" :description="query ? '换一个关键词，或清空搜索。' : '导入已经签名的扩展包；需要开发新扩展时可使用标题栏的新建入口。'"><template #icon><Boxes :size="26" /></template><template #actions><VNextButton v-if="query" size="compact" @click="query = ''">清空搜索</VNextButton><VNextButton v-else size="compact" @click="importFolder('project')">导入到当前项目</VNextButton></template></VNextWorkspaceState>
            <VNextWorkspaceState v-else-if="!selectedPackage" class="detail-state" kind="selection" title="选择一个扩展" description="查看它提供的函数和可用状态。"><template #icon><Boxes :size="26" /></template></VNextWorkspaceState>
            <template v-else>
                <header class="detail-header">
                    <div class="package-title"><span class="package-glyph large" :data-state="packageState(selectedPackage)"><Package :size="18" /></span><span><strong>{{ selectedPackage.display_name }}</strong><small>{{ selectedPackage.version ? `版本 ${selectedPackage.version}` : '未标注版本' }}</small></span></div>
                    <div class="detail-header-actions"><div class="summary-badges">
                        <span :data-tone="selectedPackage.signature_verified ? 'success' : 'danger'"><BadgeCheck v-if="selectedPackage.signature_verified" :size="13" /><ShieldAlert v-else :size="13" />{{ selectedPackage.signature_verified ? '签名有效' : '签名无效' }}</span>
                        <span :data-tone="selectedPackage.lock_current ? 'success' : 'neutral'"><LockKeyhole :size="13" />{{ selectedPackage.lock_current ? '锁定一致' : '未锁定' }}</span>
                    </div><button v-if="compactLayout && props.detailOpen === undefined" ref="actionPaneTrigger" type="button" class="action-pane-trigger" aria-label="打开扩展状态与操作" title="扩展状态与操作" @click="openActionPane"><PanelRightOpen :size="15" /></button></div>
                </header>
                <div class="detail-scroll">
                    <p v-if="selectedPackage.description" class="package-description">{{ selectedPackage.description }}</p>
                    <section v-if="selectedPackage.diagnostics.length" class="detail-section">
                        <header><span>校验诊断</span><small>{{ selectedPackage.diagnostics.length }}</small></header>
                        <ul class="diagnostic-list"><li v-for="item in selectedPackage.diagnostics" :key="`${item.code}:${item.message}`" :data-severity="item.severity"><CircleAlert :size="14" /><span><strong>{{ diagnosticLabel(item.severity) }}</strong><small>{{ item.message }}</small></span></li></ul>
                    </section>
                    <section class="detail-section">
                        <header><span>函数契约</span><small>{{ selectedPackage.function_contracts.length }}</small></header>
                        <div v-if="!selectedPackage.function_contracts.length" class="section-empty">这个扩展没有声明函数贡献。</div>
                        <article v-for="contract in selectedPackage.function_contracts" :key="contract.function_id" class="contract-card">
                            <header><span><Braces :size="14" /><strong>{{ contract.qualified_name }}</strong></span></header>
                            <p v-if="contract.description">{{ contract.description }}</p>
                            <dl><div><dt>参数</dt><dd>{{ parameterSummary(contract) }}</dd></div><div><dt>适用目标</dt><dd>{{ contract.targets.map(targetLabel).join('、') || '无目标' }}</dd></div></dl>
                        </article>
                    </section>
                    <details class="developer-details">
                        <summary><span>开发者信息</span><small>{{ selectedPackage.host_variants.length }} 个运行模块</small></summary>
                        <section class="detail-section">
                            <header><span>函数标识与执行限制</span></header>
                            <dl v-for="contract in selectedPackage.function_contracts" :key="`technical:${contract.function_id}`" class="technical-contract"><div><dt>{{ contract.qualified_name }}</dt><dd>{{ contract.function_id }}</dd></div><div><dt>返回</dt><dd>{{ contract.return_type }}</dd></div><div><dt>超时</dt><dd>{{ contract.timeout_ms }} ms</dd></div></dl>
                        </section>
                        <section class="detail-section">
                            <header><span>运行模块</span><small>{{ selectedPackage.host_variants.length }}</small></header>
                            <div v-if="!selectedPackage.host_variants.length" class="section-empty">没有可运行模块，不能发布或调用。</div>
                            <article v-for="variant in selectedPackage.host_variants" :key="variant.variant_id" class="variant-row">
                                <span class="variant-icon"><Cpu :size="15" /></span><span><strong>{{ variant.variant_id }}</strong><small>{{ hostLabel(variant.host) }} · {{ variant.runtime }}</small></span>
                                <span class="variant-targets">{{ variant.targets.map(targetLabel).join(' · ') }}<small v-if="variant.minimum_android_api">Android {{ androidVersionLabel(variant.minimum_android_api) }}+</small></span>
                                <span class="variant-state" :data-tone="variant.artifact ? 'success' : 'neutral'">{{ variant.artifact ? '已密封' : '开发态' }}</span>
                                <button v-if="isAndroidJvmVariant(variant) && canMutate" type="button" class="variant-action" :disabled="busy || !selectedPackage.trusted || selectedPackage.enabled" :title="selectedPackage.enabled ? '替换模块前请先停用扩展' : '选择外部 IDE 编译的 JAR，校验后密封'" @click="sealAndroidJvm(variant.variant_id)"><FileInput :size="13" />{{ variant.artifact ? '替换 JAR' : '导入 JAR' }}</button>
                            </article>
                        </section>
                        <section v-if="selectedPackage.contributions.length" class="detail-section">
                            <header><span>界面与数据贡献</span><small>{{ selectedPackage.contributions.length }}</small></header>
                            <article v-for="item in selectedPackage.contributions" :key="item.contribution_id" class="contribution-row"><Puzzle :size="14" /><span><strong>{{ item.kind }}</strong><small>{{ item.contribution_id }}</small></span><code>{{ item.path }}</code></article>
                        </section>
                    </details>
                </div>
            </template>
        </main>

        <button v-if="detailAsOverlay && detailVisible" type="button" class="action-pane-scrim" aria-label="关闭扩展状态与操作" @click="closeActionPane" />
        <aside v-if="detailVisible" :class="['action-pane', { 'is-compact': detailAsOverlay }]" aria-label="扩展状态与操作" @keydown.esc="closeActionPane">
            <VNextPaneHeader class="pane-heading" role="inspector" title="扩展状态"><template #actions><VNextIconButton v-if="detailAsOverlay" ref="actionPaneClose" class="action-pane-close" label="关闭扩展状态与操作" @click="closeActionPane"><X /></VNextIconButton></template></VNextPaneHeader>
            <VNextWorkspaceState v-if="!selectedPackage && packages.length" class="pane-state compact" compact kind="selection" title="选择扩展后管理状态"><template #icon><SlidersHorizontal :size="19" /></template></VNextWorkspaceState>
            <template v-else-if="selectedPackage"><div class="action-scroll app-inspector-body app-inspector-form">
                <section class="status-card"><div><span>安装范围</span><strong>{{ scopeLabel(selectedPackage.scope) }}</strong></div><div><span>信任</span><strong>{{ selectedPackage.trusted ? '已信任' : '未信任' }}</strong></div><div><span>项目状态</span><strong>{{ selectedPackage.enabled ? '已启用' : '未启用' }}</strong></div><div><span>发布产物</span><strong>{{ selectedPackage.sealed_artifacts.length ? '已构建' : '未构建' }}</strong></div></section>
                <section class="action-section app-inspector-section"><h3>生命周期</h3>
                    <button v-if="!selectedPackage.trusted && canMutate" type="button" class="primary-action" :disabled="busy || !selectedPackage.valid || !selectedPackage.signature_verified" @click="perform('trust')"><ShieldCheck :size="15" />信任此发布者代码</button>
                    <button v-if="!selectedPackage.enabled" type="button" :class="{ 'primary-action': selectedPackage.trusted }" :disabled="busy || !selectedPackage.trusted || !selectedPackage.valid" @click="perform('enable')"><Power :size="15" />启用并写入项目锁</button>
                    <button v-else type="button" :disabled="busy" @click="confirmAction = 'disable'; loadReferences()"><PowerOff :size="15" />停用扩展</button>
                    <button type="button" :disabled="busy || !selectedPackage.trusted || !selectedPackage.valid" @click="perform('build')"><Hammer :size="15" />构建密封运行产物</button>
                    <button type="button" :disabled="busy" @click="perform('validate')"><ScanSearch :size="15" />重新校验</button>
                    <button type="button" :disabled="busy || !selectedPackage.trusted" @click="perform('tests')"><FlaskConical :size="15" />运行契约测试</button>
                    <button type="button" :disabled="busy" @click="perform('open')"><FolderOpen :size="15" />打开扩展文件夹</button>
                    <button type="button" :disabled="busy" @click="loadReferences"><Link2 :size="15" />检查项目引用</button>
                </section>
                <section class="action-section app-inspector-section"><h3>权限</h3>
                    <div v-if="!selectedPackage.permissions.length" class="section-empty small">无需额外权限</div><ul v-else class="permission-list"><li v-for="permission in selectedPackage.permissions" :key="permission"><KeyRound :size="13" />{{ permission }}</li></ul>
                    <div class="network-summary"><Network :size="14" /><span><strong>{{ networkLabel }}</strong><small>{{ selectedPackage.network?.rules.length || 0 }} 条网络规则</small></span></div>
                </section>
                <details class="action-disclosure app-inspector-disclosure"><summary>运行隔离说明</summary><p>{{ workerNotice }}</p></details>
                <section v-if="referencesLoaded" class="action-section app-inspector-section"><h3>项目引用 <span>{{ references.length }}</span></h3><div v-if="!references.length" class="section-empty small">当前项目没有引用这个扩展。</div><ul v-else class="reference-list"><li v-for="item in references" :key="`${item.path}:${item.json_path}:${item.identifier}`"><strong>{{ item.identifier }}</strong><small>{{ item.path }} · {{ item.json_path }}</small></li></ul></section>
                <section v-if="canMutate" class="action-section app-inspector-section danger-zone"><h3>移除</h3><button v-if="selectedPackage.trusted" type="button" :disabled="busy || selectedPackage.enabled" @click="confirmAction = 'untrust'"><ShieldOff :size="15" />取消本机信任</button><button type="button" class="danger-action" :disabled="busy || selectedPackage.enabled" @click="confirmAction = 'delete'; loadReferences()"><Trash2 :size="15" />删除扩展包</button></section>
            </div></template>
        </aside>

        <VNextInlineNotice v-if="message.text" class="workspace-message" :tone="message.tone" :message="message.text" dismissible @dismiss="message.text = ''" />
        <div v-if="creating" class="dialog-backdrop" @mousedown.self="creating = false"><section ref="createDialogElement" class="create-dialog" role="dialog" aria-modal="true" aria-labelledby="extension-create-title" tabindex="-1" @keydown="trapDialogFocus" @keydown.esc.stop="creating = false">
            <header><div><h2 id="extension-create-title">新建外部扩展骨架</h2><p>EasyCode 只生成清单、契约、源码入口和测试骨架；代码请在外部 IDE 编写。</p></div><button type="button" aria-label="关闭" @click="creating = false"><X :size="15" /></button></header>
            <form @submit.prevent="createPackage"><label class="inline-field">包 ID<input v-model.trim="draft.package_id" required pattern="[a-z0-9][a-z0-9_.-]{2,95}" placeholder="例如：com.example.pathfinder" /></label><label class="inline-field">显示名称<input v-model.trim="draft.display_name" required maxlength="80" placeholder="例如：路径规划" /></label><label class="inline-field">发布者 ID<input v-model.trim="draft.publisher_id" required pattern="[a-z0-9][a-z0-9_.-]{2,95}" placeholder="例如：com.example" /></label><label class="inline-field">发布者名称<input v-model.trim="draft.publisher_name" required maxlength="80" placeholder="例如：示例工作室" /></label><label class="inline-field">安装范围<select v-model="draft.scope"><option value="project">当前项目</option><option value="user">当前用户</option></select></label><label class="wide multiline-field">说明<textarea v-model.trim="draft.description" maxlength="240" placeholder="说明扩展解决的问题和适用场景" /></label><footer><button type="button" @click="creating = false">取消</button><button type="submit" class="primary-action" :disabled="busy">创建并打开文件夹</button></footer></form>
        </section></div>
        <div v-if="confirmAction" class="dialog-backdrop" @mousedown.self="confirmAction = ''"><section ref="confirmDialogElement" class="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="extension-confirm-title" tabindex="-1" @keydown="trapDialogFocus" @keydown.esc.stop="confirmAction = ''"><header><TriangleAlert :size="18" /><div><h2 id="extension-confirm-title">{{ confirmTitle }}</h2><p>{{ confirmDescription }}</p></div></header><ul v-if="references.length" class="reference-list blocking"><li v-for="item in references" :key="`${item.path}:${item.json_path}`"><strong>{{ item.identifier }}</strong><small>{{ item.path }} · {{ item.json_path }}</small></li></ul><footer><button type="button" data-dialog-initial-focus @click="confirmAction = ''">取消</button><button type="button" class="danger-action" :disabled="busy || Boolean(references.length)" @click="confirmLifecycle">确认</button></footer></section></div>
    </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { BadgeCheck, Boxes, Braces, CircleAlert, Cpu, FileInput, FlaskConical, FolderInput, FolderOpen, Hammer, KeyRound, Link2, LoaderCircle, LockKeyhole, Network, Package, PanelRightOpen, Plus, Power, PowerOff, Puzzle, ScanSearch, ShieldAlert, ShieldCheck, ShieldOff, SlidersHorizontal, Trash2, TriangleAlert, UserRoundPlus, X } from 'lucide-vue-next'
import { extensionApi } from '../extensionApi'
import type { ExtensionFunctionContract, ExtensionHostVariant, ExtensionPackage, ExtensionReference, ExtensionScope } from '../extensionTypes'
import { trapDialogFocus, useDialogFocusReturn } from '../dialogFocus'
import { useVNextStore } from '../store'
import VNextPaneHeader from './ui/VNextPaneHeader.vue'
import VNextListSearch from './ui/VNextListSearch.vue'
import VNextNavigationPane from './ui/VNextNavigationPane.vue'
import VNextWorkspaceState from './ui/VNextWorkspaceState.vue'
import VNextInlineNotice from './ui/VNextInlineNotice.vue'
import VNextButton from './ui/VNextButton.vue'
import VNextIconButton from './ui/VNextIconButton.vue'
import VNextNavigationItem from './ui/VNextNavigationItem.vue'

const store = useVNextStore()
const props = withDefaults(defineProps<{ detailOpen?: boolean; detailOverlay?: boolean }>(), { detailOpen: undefined, detailOverlay: undefined })
const emit = defineEmits<{ 'update:detail-open': [open: boolean] }>()
const loading = ref(true), detailLoading = ref(false), busy = ref(false), query = ref(''), selectedKey = ref(''), workerNotice = ref('Worker 提供超时、取消、日志、序列化和崩溃隔离；它不是抵御恶意代码的安全沙箱。')
const packages = ref<ExtensionPackage[]>([]), selectedPackage = ref<ExtensionPackage | null>(null), references = ref<ExtensionReference[]>([])
const referencesLoaded = ref(false), creating = ref(false), confirmAction = ref<'' | 'disable' | 'untrust' | 'delete'>('')
const createDialogElement = ref<HTMLElement | null>(null), confirmDialogElement = ref<HTMLElement | null>(null)
const compactLayout = ref(false), actionPaneOpen = ref(false)
const detailVisible = computed(() => props.detailOpen ?? (!compactLayout.value || actionPaneOpen.value))
const detailAsOverlay = computed(() => props.detailOverlay ?? compactLayout.value)
const actionPaneTrigger = ref<HTMLButtonElement | null>(null), actionPaneClose = ref<InstanceType<typeof VNextIconButton> | null>(null)
let compactMedia: MediaQueryList | null = null
const message = reactive<{ tone: 'success' | 'error'; text: string }>({ tone: 'success', text: '' })
const draft = reactive({ package_id: '', display_name: '', publisher_id: '', publisher_name: '', description: '', scope: 'project' as 'project' | 'user' })
useDialogFocusReturn(creating, createDialogElement)
useDialogFocusReturn(() => Boolean(confirmAction.value), confirmDialogElement)
const visiblePackages = computed(() => { const text = query.value.trim().toLocaleLowerCase(); return text ? packages.value.filter((item) => [item.display_name, item.package_id, item.publisher?.publisher_id || '', item.publisher?.display_name || ''].some((value) => value.toLocaleLowerCase().includes(text))) : packages.value })
const groupedPackages = computed(() => (['project', 'user', 'official'] as ExtensionScope[]).map((scope) => ({ scope, items: visiblePackages.value.filter((item) => item.scope === scope) })).filter((group) => group.items.length))
const canMutate = computed(() => selectedPackage.value?.scope !== 'official')
const networkLabel = computed(() => { const level = selectedPackage.value?.network?.level || 'none'; return level === 'public' ? '允许公网' : level === 'local_lan' ? '仅局域网' : '禁止联网' })
const confirmTitle = computed(() => confirmAction.value === 'delete' ? '删除这个扩展包？' : confirmAction.value === 'untrust' ? '取消本机信任？' : '停用这个扩展？')
const confirmDescription = computed(() => references.value.length ? `发现 ${references.value.length} 处项目引用，请先处理引用；EasyCode 不会留下失效调用。` : confirmAction.value === 'delete' ? '扩展目录将被移入项目回收位置；此操作不会删除任何引用。' : confirmAction.value === 'untrust' ? '取消信任后，开发代码不能执行；已启用扩展必须先停用。' : '停用会原子更新项目与 easycode.lock，不会静默替换为其他版本。')
const packageKey = (item: ExtensionPackage) => `${item.scope}:${item.package_id}`
const scopeLabel = (scope: ExtensionScope) => scope === 'official' ? '官方内置' : scope === 'user' ? '用户安装' : '当前项目'
const packageState = (item: ExtensionPackage) => !item.valid || !item.signature_verified ? 'invalid' : item.enabled ? 'enabled' : item.trusted ? 'trusted' : 'installed'
const packageStateLabel = (item: ExtensionPackage) => packageState(item) === 'invalid' ? '无效' : packageState(item) === 'enabled' ? '已启用' : packageState(item) === 'trusted' ? '已信任' : '已安装'
const diagnosticLabel = (severity: ExtensionPackage['diagnostics'][number]['severity']) => severity === 'error' ? '错误' : severity === 'warning' ? '警告' : '提示'
const hostLabel = (host: string) => host === 'android_native' ? 'Android 本机' : 'Windows'
const androidVersionLabel = (api: number) => ({ 21: '5.0', 22: '5.1', 23: '6.0', 24: '7.0', 25: '7.1', 26: '8.0', 27: '8.1', 28: '9', 29: '10', 30: '11', 31: '12', 32: '12L', 33: '13', 34: '14', 35: '15', 36: '16', 37: '17' } as Record<number, string>)[api] || `API ${api}`
const isAndroidJvmVariant = (variant: ExtensionHostVariant) => variant.host === 'android_native' && variant.runtime === 'android-kotlin-v1'
const targetLabel = (target: string) => target === 'android_native' ? 'Android 本机' : target === 'android_adb' ? 'ADB' : target === 'windows' ? 'Windows' : '无操作目标'
const parameterSummary = (contract: ExtensionFunctionContract) => contract.parameters.length ? contract.parameters.map((item) => `${item.display_name}${item.required ? '' : '（可选）'}：${extensionTypeLabel(item.value_type)}`).join(' · ') : '无参数'
const extensionTypeLabel = (valueType: string): string => ({
    string: '文本', text: '文本', bool: '开关', int64: '整数', float64: '小数',
    duration: '持续时间', point: '坐标', rect: '区域', path: '路径',
    'list<string>': '文本列表', 'map<string,string>': '文本字典', json_value: 'JSON 数据',
}[valueType] || valueType)

function showError(error: unknown): void { message.tone = 'error'; message.text = error instanceof Error ? error.message : '扩展操作失败' }
async function refresh(preferredKey = selectedKey.value): Promise<void> { if (!store.workspace) return; loading.value = true; try { const result = await extensionApi.list(store.workspace); packages.value = result.packages; workerNotice.value = result.worker_notice; const next = packages.value.find((item) => packageKey(item) === preferredKey) || packages.value[0] || null; if (next) await selectPackage(next); else { selectedKey.value = ''; selectedPackage.value = null } } catch (error) { showError(error) } finally { loading.value = false } }
async function selectPackage(item: ExtensionPackage): Promise<void> { if (!store.workspace) return; selectedKey.value = packageKey(item); detailLoading.value = true; references.value = []; referencesLoaded.value = false; try { selectedPackage.value = await extensionApi.detail(store.workspace, item.package_id, item.scope) } catch (error) { selectedPackage.value = item; showError(error) } finally { detailLoading.value = false } }
function openCreate(): void { Object.assign(draft, { package_id: '', display_name: '', publisher_id: '', publisher_name: '', description: '', scope: 'project' }); creating.value = true }
function syncCompactLayout(event?: MediaQueryListEvent): void {
    compactLayout.value = event?.matches ?? compactMedia?.matches ?? false
    if (!compactLayout.value) actionPaneOpen.value = false
}
async function openActionPane(): Promise<void> { actionPaneOpen.value = true; emit('update:detail-open', true); await nextTick(); actionPaneClose.value?.focus() }
async function closeActionPane(): Promise<void> { actionPaneOpen.value = false; emit('update:detail-open', false); await nextTick(); actionPaneTrigger.value?.focus() }
async function createPackage(): Promise<void> { if (!store.workspace) return; busy.value = true; try { const result = await extensionApi.scaffold(store.workspace, { ...draft }); creating.value = false; await refresh(packageKey(result.package)); await extensionApi.openFolder(store.workspace, result.package.package_id, result.package.scope); message.tone = 'success'; message.text = '扩展骨架已创建并打开。请在外部 IDE 完善清单、契约与实现后返回校验。' } catch (error) { showError(error) } finally { busy.value = false } }
async function importFolder(scope: 'project' | 'user'): Promise<void> { if (!store.workspace) return; busy.value = true; try { const path = await store.chooseFolder(); if (!path) return; const result = await extensionApi.importFolder(store.workspace, path, scope); await refresh(packageKey(result.package)); message.tone = 'success'; message.text = scope === 'project' ? '签名扩展已导入当前项目；它尚未自动获得信任或启用。' : '签名扩展已安装到当前用户；当前项目仍需显式启用。' } catch (error) { showError(error) } finally { busy.value = false } }
async function sealAndroidJvm(variantId: string): Promise<void> { const item = selectedPackage.value; if (!store.workspace || !item || item.scope === 'official') return; busy.value = true; try { const path = await store.chooseFile('选择 Android 扩展 JAR', ['jar']); if (!path) return; await extensionApi.sealAndroidJvm(store.workspace, item.package_id, item.scope, variantId, path); await refresh(packageKey(item)); message.tone = 'success'; message.text = `Android 变体 ${variantId} 已校验、密封并签名；启用后会进入项目锁与 APK 静态闭包。` } catch (error) { showError(error) } finally { busy.value = false } }
async function perform(action: 'trust' | 'enable' | 'build' | 'validate' | 'tests' | 'open'): Promise<void> { const item = selectedPackage.value; if (!store.workspace || !item) return; busy.value = true; try { let text = ''; if (action === 'trust' && item.scope !== 'official') { await extensionApi.trust(store.workspace, item.package_id, item.scope); text = '已在本机显式信任这个发布者代码。' } if (action === 'enable') { await extensionApi.enable(store.workspace, item.package_id, item.scope); text = '扩展已启用，精确版本和内容已写入 easycode.lock。' } if (action === 'build') { await extensionApi.build(store.workspace, item.package_id, item.scope); text = '密封运行产物已构建并签名。' } if (action === 'validate') { await extensionApi.validate(store.workspace, item.package_id, item.scope); text = '清单、签名、契约、变体和密封产物校验完成。' } if (action === 'tests') { const result = await extensionApi.runTests(store.workspace, item.package_id, item.scope); text = result.passed ? `契约测试通过（${result.total} 项）。` : `契约测试未通过（${result.total} 项），请查看校验诊断。` } if (action === 'open') { await extensionApi.openFolder(store.workspace, item.package_id, item.scope); text = '扩展文件夹已交给系统打开。' } await store.refreshFunctions(); await refresh(packageKey(item)); message.tone = 'success'; message.text = text } catch (error) { showError(error) } finally { busy.value = false } }
async function loadReferences(): Promise<void> { const item = selectedPackage.value; if (!store.workspace || !item) return; busy.value = true; try { const result = await extensionApi.references(store.workspace, item.package_id, item.scope); references.value = result.references; referencesLoaded.value = true; if (!confirmAction.value) { message.tone = 'success'; message.text = references.value.length ? `发现 ${references.value.length} 处项目引用。` : '当前项目没有引用这个扩展。' } } catch (error) { showError(error) } finally { busy.value = false } }
async function confirmLifecycle(): Promise<void> { const item = selectedPackage.value; if (!store.workspace || !item || references.value.length) return; busy.value = true; const action = confirmAction.value; try { if (action === 'disable') await extensionApi.disable(store.workspace, item.package_id, item.scope); if (action === 'untrust' && item.scope !== 'official') await extensionApi.untrust(store.workspace, item.package_id, item.scope); if (action === 'delete' && item.scope !== 'official') await extensionApi.delete(store.workspace, item.package_id, item.scope); confirmAction.value = ''; message.tone = 'success'; message.text = action === 'delete' ? '扩展包已移除。' : action === 'untrust' ? '本机信任已取消。' : '扩展已停用，项目锁已原子更新。'; await store.refreshFunctions(); await refresh(action === 'delete' ? '' : packageKey(item)) } catch (error) { showError(error) } finally { busy.value = false } }
onMounted(() => {
    compactMedia = window.matchMedia?.('(max-width: 820px)') || null
    syncCompactLayout()
    compactMedia?.addEventListener?.('change', syncCompactLayout)
    void refresh()
})
onBeforeUnmount(() => compactMedia?.removeEventListener?.('change', syncCompactLayout))
</script>

<style scoped>
.extension-workspace.detail-panel-collapsed{grid-template-columns:280px minmax(420px,1fr)}
.action-pane.is-compact{position:absolute;z-index:31;right:0;top:0;bottom:0;width:min(320px,calc(100% - 44px));box-shadow:-12px 0 30px #0008}.action-pane-scrim{position:absolute;z-index:30;inset:0;padding:0;border:0;background:#05050588;cursor:default}
.extension-workspace{position:relative;display:grid;grid-template-columns:280px minmax(420px,1fr) 310px;min-width:0;height:100%;overflow:hidden;background:var(--app-bg-base);color:var(--app-text-primary)}.package-pane,.action-pane,.detail-pane{min-width:0;min-height:0;background:var(--app-bg-sidebar)}.package-pane,.action-pane{display:flex;flex-direction:column}.package-pane{border-right:1px solid var(--app-border-subtle)}.action-pane{border-left:1px solid var(--app-border-subtle)}.detail-pane{display:flex;flex-direction:column;background:var(--app-bg-base)}
.pane-heading{height:var(--app-height-pane-header);flex:0 0 auto;display:flex;align-items:center;justify-content:space-between;padding:0 12px;border-bottom:1px solid var(--app-border-subtle)}.pane-heading>div{display:flex;align-items:center;gap:8px}.pane-heading strong{font-size: var(--app-font-body)}.pane-heading span{font-size: var(--app-font-caption);color:var(--app-text-secondary)}button,input,select,textarea{font:inherit;color:inherit}.heading-actions button,.workspace-message button,.create-dialog header>button{display:grid;place-items:center;width:28px;height: var(--app-control-compact);padding:0;border:0;border-radius: var(--app-radius-sm);background:transparent;color:var(--app-text-regular);cursor:pointer}.heading-actions button:hover,.workspace-message button:hover,.create-dialog header>button:hover{background:var(--app-bg-hover);color:var(--app-text-primary)}button:disabled{opacity:.42;cursor:not-allowed}
.package-search{height: var(--app-control-default);margin:10px 10px 6px;display:flex;align-items:center;gap:7px;padding:0 9px;border:1px solid var(--app-border-default);border-radius: var(--app-radius-md);background:var(--app-bg-input);color:var(--app-text-secondary)}.package-search:focus-within{border-color:var(--app-color-primary)}.package-search input{min-width:0;flex:1;border:0;outline:0;background:transparent;font-size: var(--app-font-compact)}.pane-state,.detail-state{display:flex;flex:1;min-height:0;align-items:center;justify-content:center;flex-direction:column;gap:8px;padding:24px;text-align:center;color:var(--app-text-secondary);font-size: var(--app-font-compact)}.pane-state strong,.detail-state strong{color:var(--app-text-primary);font-size: var(--app-font-body)}.pane-state span,.detail-state span{max-width:280px;line-height:1.6}.pane-state.compact{gap:9px}.spin{animation:spin .9s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
.package-list{min-height:0;overflow:auto;padding:3px 7px 14px}.scope-group>header{display:flex;align-items:center;justify-content:space-between;height: var(--app-control-compact);padding:0 6px;color:var(--app-text-secondary);font-size: var(--app-font-caption)}.package-row{width:100%;height:47px;display:flex;align-items:center;gap:8px;padding:0 8px;margin:1px 0;border:0;border-radius: var(--app-radius-md);background:transparent;text-align:left;cursor:pointer}.package-row:hover{background:var(--app-bg-hover)}.package-row.selected{background:color-mix(in srgb,var(--app-color-primary) 14%,transparent)}.package-glyph{display:grid;place-items:center;width:27px;height:27px;flex:0 0 auto;border-radius: var(--app-radius-md);background:var(--app-bg-raised);color:var(--app-text-regular)}.package-glyph[data-state=enabled],.package-glyph[data-state=trusted]{color:var(--app-color-success)}.package-glyph[data-state=invalid]{color:var(--app-color-danger)}.package-glyph.large{width:34px;height: var(--app-control-default)}.package-copy{display:flex;min-width:0;flex:1;flex-direction:column;gap:3px}.package-copy strong,.package-copy small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.package-copy strong{font-size: var(--app-font-compact)}.package-copy small,.row-status{color:var(--app-text-secondary);font-size: var(--app-font-caption)}.row-status[data-state=enabled]{color:var(--app-color-success)}.row-status[data-state=invalid]{color:var(--app-color-danger)}
.detail-header{height:var(--app-height-workspace-header-described);flex:0 0 auto;display:flex;align-items:center;justify-content:space-between;padding:0 18px;border-bottom:1px solid var(--app-border-subtle)}.detail-header-actions{display:flex;align-items:center;gap:7px}.package-title{display:flex;min-width:0;align-items:center;gap:10px}.package-title>span:last-child{display:flex;min-width:0;flex-direction:column;gap:4px}.package-title strong,.package-title small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.package-title strong{font-size: var(--app-font-page-title)}.package-title small{color:var(--app-text-secondary);font-size: var(--app-font-caption)}.summary-badges{display:flex;gap:6px}.summary-badges>span,.variant-state{display:flex;align-items:center;gap:4px;padding:4px 7px;border:1px solid var(--app-border-subtle);border-radius:999px;color:var(--app-text-secondary);font-size: var(--app-font-caption)}.summary-badges>[data-tone=success],.variant-row>[data-tone=success]{color:var(--app-color-success)}.summary-badges>[data-tone=danger]{color:var(--app-color-danger)}.action-pane-trigger,.action-pane-close{width:28px;height: var(--app-control-compact);display:grid;flex:0 0 auto;place-items:center;padding:0;border:0;border-radius: var(--app-radius-sm);background:transparent;color:var(--app-text-regular);cursor:pointer}.action-pane-trigger:hover,.action-pane-close:hover{background:var(--app-bg-hover);color:var(--app-text-primary)}.detail-scroll,.action-scroll{min-height:0;overflow:auto}.detail-scroll{padding:18px 20px 48px}.package-description{margin:0 0 18px;color:var(--app-text-regular);font-size: var(--app-font-compact);line-height:1.65}.detail-section{max-width:900px;margin:0 0 22px}.detail-section>header{height:31px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--app-border-subtle);font-size: var(--app-font-compact)}.detail-section>header small,.action-section h3 span{font-size: var(--app-font-caption);color:var(--app-text-secondary)}.section-empty{padding:18px 0;color:var(--app-text-secondary);font-size: var(--app-font-caption)}.section-empty.small{padding:6px 0 10px}
.diagnostic-list,.permission-list,.reference-list{padding:0;margin:8px 0;list-style:none}.diagnostic-list li{display:flex;gap:8px;padding:9px 10px;margin-bottom:5px;border-radius: var(--app-radius-md);background:var(--app-bg-raised);color:var(--app-text-secondary)}.diagnostic-list li[data-severity=error]{color:var(--app-color-danger)}.diagnostic-list li[data-severity=warning]{color:var(--app-color-warning)}.diagnostic-list li>span{display:flex;flex-direction:column;gap:3px}.diagnostic-list small{font-size: var(--app-font-caption);color:var(--app-text-regular)}.contract-card{padding:11px 0;border-bottom:1px solid var(--app-border-subtle)}.contract-card>header{display:flex;justify-content:space-between}.contract-card>header>span{display:flex;align-items:center;gap:7px}.contract-card>header strong{font-size: var(--app-font-compact)}.contract-card>header small{color:var(--app-color-primary);font-family:var(--app-font-mono);font-size:var(--app-font-interface)}.contract-card p{margin:7px 0;color:var(--app-text-regular);font-size: var(--app-font-caption)}.contract-card dl{display:grid;grid-template-columns:1fr 1fr;gap:5px 18px;margin:8px 0 0}.contract-card dl div{display:grid;grid-template-columns:56px minmax(0,1fr);gap:6px}.contract-card dt{color:var(--app-text-secondary);font-size: var(--app-font-caption)}.contract-card dd{margin:0;overflow-wrap:anywhere;color:var(--app-text-regular);font-size: var(--app-font-caption)}
.developer-details{max-width:900px;border-bottom:1px solid var(--app-border-subtle)}.developer-details>summary{min-height:42px;display:flex;align-items:center;justify-content:space-between;color:var(--app-text-regular);font-size: var(--app-font-caption);cursor:pointer}.developer-details>summary:hover{color:var(--app-text-primary)}.developer-details>summary small{color:var(--app-text-secondary);font-size: var(--app-font-caption)}.developer-details[open]>summary{border-bottom:1px solid var(--app-border-subtle)}.developer-details .detail-section{margin:12px 0 18px}.technical-contract{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:12px;margin:0;padding:9px 0;border-bottom:1px solid var(--app-border-subtle)}.technical-contract div{min-width:0}.technical-contract dt{color:var(--app-text-secondary);font-size: var(--app-font-caption)}.technical-contract dd{margin:3px 0 0;overflow-wrap:anywhere;color:var(--app-text-regular);font-size: var(--app-font-caption)}
.variant-row{display:grid;grid-template-columns:27px minmax(140px,1fr) minmax(90px,auto) auto auto;align-items:center;gap:9px;padding:9px 0;border-bottom:1px solid var(--app-border-subtle)}.variant-icon{display:grid;place-items:center;width:27px;height:27px;border-radius: var(--app-radius-sm);background:var(--app-bg-raised);color:var(--app-text-secondary)}.variant-row>span:nth-child(2){display:flex;flex-direction:column;gap:3px}.variant-row strong{font-size: var(--app-font-caption)}.variant-row small,.variant-targets{color:var(--app-text-secondary);font-size: var(--app-font-caption)}.variant-targets{display:flex;flex-direction:column;gap:2px}.variant-action{min-height:27px;display:flex;align-items:center;gap:5px;padding:0 8px;border:1px solid var(--app-border-default);border-radius: var(--app-radius-sm);background:var(--app-bg-raised);font-size: var(--app-font-caption);cursor:pointer}.variant-action:hover:not(:disabled){background:var(--app-bg-hover)}.contribution-row{display:grid;grid-template-columns:20px minmax(130px,1fr) auto;align-items:center;gap:7px;padding:9px 0;border-bottom:1px solid var(--app-border-subtle)}.contribution-row>span{display:flex;flex-direction:column}.contribution-row strong{font-size: var(--app-font-caption)}.contribution-row small,.contribution-row code{color:var(--app-text-secondary);font-size: var(--app-font-caption)}
.action-scroll{padding:12px 12px 42px}.status-card{display:grid;grid-template-columns:1fr 1fr;gap:1px;padding:1px;margin-bottom:14px;border-radius: var(--app-radius-md);overflow:hidden;background:var(--app-border-subtle)}.status-card div{display:flex;flex-direction:column;gap:5px;padding:9px;background:var(--app-bg-raised)}.status-card span{font-size: var(--app-font-caption);color:var(--app-text-secondary)}.status-card strong{font-size: var(--app-font-caption)}.action-section{padding:11px 0;border-top:1px solid var(--app-border-subtle)}.action-section h3{display:flex;justify-content:space-between;margin:0 0 8px;font-size: var(--app-font-caption)}.action-section>button{width:100%;min-height: var(--app-control-default);display:flex;align-items:center;gap:7px;padding:7px 9px;margin:5px 0;border:1px solid var(--app-border-default);border-radius: var(--app-radius-md);background:var(--app-bg-raised);font-size: var(--app-font-caption);cursor:pointer}.action-section>button:hover:not(:disabled){background:var(--app-bg-hover)}.action-section>button.primary-action,.create-dialog .primary-action{border-color:transparent;background:var(--app-color-primary);color:#fff}.danger-action{color:var(--app-color-danger)}.permission-list{display:flex;flex-wrap:wrap;gap:5px}.permission-list li{display:flex;align-items:center;gap:4px;padding:4px 6px;border-radius: var(--app-radius-sm);background:var(--app-bg-raised);font-size: var(--app-font-caption)}.network-summary{display:flex;align-items:center;gap:8px;padding:8px 0}.network-summary>span{display:flex;flex-direction:column}.network-summary strong{font-size: var(--app-font-caption)}.network-summary small{font-size: var(--app-font-caption);color:var(--app-text-secondary)}.worker-notice p{margin:0;color:var(--app-text-secondary);font-size: var(--app-font-caption);line-height:1.55}.reference-list li{display:flex;flex-direction:column;gap:3px;padding:7px;margin-bottom:4px;border-radius: var(--app-radius-sm);background:var(--app-bg-raised)}.reference-list strong{font-size: var(--app-font-caption)}.reference-list small{overflow-wrap:anywhere;color:var(--app-text-secondary);font-size: var(--app-font-caption)}
.action-disclosure{padding:10px 0;border-top:1px solid var(--app-border-subtle)}.action-disclosure summary{color:var(--app-text-regular);font-size: var(--app-font-caption);cursor:pointer}.action-disclosure p{margin:8px 0 0;color:var(--app-text-secondary);font-size: var(--app-font-caption);line-height:1.55}
.workspace-message{position:absolute;left:50%;bottom:14px;z-index:10;display:flex;align-items:center;gap:7px;max-width:70%;padding:8px 9px 8px 11px;transform:translateX(-50%);border:1px solid var(--app-border-default);border-radius: var(--app-radius-md);background:var(--app-bg-overlay);box-shadow:0 9px 24px #0007;font-size: var(--app-font-caption)}.workspace-message span{flex:1}.workspace-message[data-tone=success]>svg{color:var(--app-color-success)}.workspace-message[data-tone=error]>svg{color:var(--app-color-danger)}
.dialog-backdrop{position:absolute;inset:0;z-index:30;display:grid;place-items:center;padding:20px;background:#050505aa;backdrop-filter:blur(2px)}.create-dialog,.confirm-dialog{width:min(600px,calc(100% - 28px));border:1px solid var(--app-border-default);border-radius: var(--app-radius-lg);background:var(--app-bg-overlay);box-shadow:0 20px 60px #0009}.create-dialog>header,.confirm-dialog>header{display:flex;align-items:flex-start;justify-content:space-between;padding:17px 18px;border-bottom:1px solid var(--app-border-subtle)}.create-dialog h2,.confirm-dialog h2{margin:0;font-size: var(--app-font-page-title)}.create-dialog p,.confirm-dialog p{margin:5px 0 0;color:var(--app-text-secondary);font-size: var(--app-font-caption)}.create-dialog form{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:16px 18px}.create-dialog label{min-width:0;font-size: var(--app-font-caption)}.create-dialog label.inline-field{display:grid;grid-template-columns:minmax(64px,82px) minmax(0,1fr);align-items:center;gap:8px}.create-dialog label.multiline-field{display:flex;flex-direction:column;gap:var(--app-form-label-control-gap)}.create-dialog label.wide,.create-dialog form>footer{grid-column:1/-1}.create-dialog input,.create-dialog select,.create-dialog textarea{min-width:0;height:var(--app-control-default);padding:0 9px;border:1px solid var(--app-border-default);border-radius: var(--app-radius-md);outline:0;background:var(--app-bg-input);font-size: var(--app-font-caption)}.create-dialog textarea{height:auto;min-height:68px;padding-block:7px;resize:vertical}.create-dialog input:focus,.create-dialog select:focus,.create-dialog textarea:focus{border-color:var(--app-color-primary)}.create-dialog footer,.confirm-dialog footer{display:flex;justify-content:flex-end;gap:7px}.create-dialog footer button,.confirm-dialog footer button{min-height: var(--app-control-default);padding:0 12px;border:1px solid var(--app-border-default);border-radius: var(--app-radius-md);background:var(--app-bg-raised);font-size: var(--app-font-caption)}.confirm-dialog{width:min(480px,calc(100% - 28px));padding-bottom:13px}.confirm-dialog>header{justify-content:flex-start;gap:10px}.confirm-dialog>header>svg{color:var(--app-color-warning)}.confirm-dialog .reference-list{max-height:180px;overflow:auto;margin:10px 16px}.confirm-dialog footer{padding:10px 16px 0}
.extension-workspace small,
.extension-workspace dt,
.extension-workspace dd,
.extension-workspace code,
.extension-workspace .row-status,
.extension-workspace .variant-targets,
.extension-workspace .variant-action,
.extension-workspace .contribution-row strong,
.extension-workspace .permission-list li,
.extension-workspace .status-card span,
.extension-workspace .worker-notice p,
.extension-workspace .reference-list strong { font-size: var(--app-font-xs); }
@media(max-width:1080px){.extension-workspace{grid-template-columns:240px minmax(360px,1fr) 280px}.contract-card dl{grid-template-columns:1fr}.summary-badges{display:none}}@media(max-width:820px){.extension-workspace{grid-template-columns:220px minmax(0,1fr)}.action-pane.is-compact{position:absolute;z-index:31;right:0;top:0;bottom:0;width:min(320px,calc(100% - 44px));box-shadow:-12px 0 30px #0008}.action-pane-scrim{position:absolute;z-index:30;inset:0;padding:0;border:0;background:#05050588;cursor:default}.variant-row{grid-template-columns:27px 1fr auto auto}.variant-targets{display:none}.detail-header{padding-inline:12px}.detail-scroll{padding-inline:14px}}
@media(min-width:701px){.extension-workspace{grid-template-columns:var(--workspace-sidebar-width,260px) minmax(420px,1fr) 310px}}
@media(min-width:701px){.extension-workspace.detail-panel-collapsed{grid-template-columns:var(--workspace-sidebar-width,260px) minmax(0,1fr)}}
@media(min-width:701px) and (max-width:1080px){.extension-workspace{grid-template-columns:var(--workspace-sidebar-width,260px) minmax(0,1fr)}}
.package-row { height: var(--app-list-row-rich); }

/* Shared form hierarchy: major sections, subordinate disclosures, then fields. */
.detail-scroll { padding-block: var(--app-form-section-padding) 48px; }
.package-description,
.detail-section { margin-bottom: var(--app-form-section-gap); }
.detail-section > header { min-height: var(--app-form-disclosure-height); height: auto; font-size: var(--app-font-sm); font-weight: 600; }
.detail-section > header small,
.action-section h3 span { font-size: var(--app-font-xs); font-weight: 400; }
.developer-details > summary,
.action-disclosure summary { min-height: var(--app-form-disclosure-height); display: flex; align-items: center; font-size: var(--app-font-sm); }
.developer-details > summary { height: auto; }
.developer-details .detail-section { margin-block: var(--app-form-heading-field-gap) var(--app-form-section-padding); }
.action-section { padding-block: var(--app-form-section-padding); }
.action-section h3 { margin-bottom: var(--app-form-heading-field-gap); color: var(--app-text-primary); font-size: var(--app-font-sm); }
.action-section > button { min-height: var(--app-control-default); padding-block: 0; }
.action-disclosure { padding-block: 0; }
.action-disclosure p { margin: var(--app-form-heading-field-gap) 0 var(--app-form-section-padding); }
.create-dialog form { gap: var(--app-form-field-gap); }
@media(max-width:620px){.dialog-backdrop{padding:10px}.create-dialog form{grid-template-columns:1fr}.create-dialog label.inline-field{grid-template-columns:1fr;align-items:stretch;gap:var(--app-form-label-control-gap)}}
</style>
