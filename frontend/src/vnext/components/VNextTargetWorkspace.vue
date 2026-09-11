<template>
    <div class="target-workspace" data-testid="target-workspace">
        <VNextNavigationPane class="target-sidebar" aria-label="运行目标列表">
            <VNextPaneHeader title="运行目标" :meta="`${store.targets.length} 个`">
                <template #actions><VNextIconButton label="新建运行目标" :disabled="store.targetBusy || readOnly || dirty" @click="openCreate"><Plus aria-hidden="true" /></VNextIconButton></template>
            </VNextPaneHeader>
            <div class="target-list app-navigation-list" role="listbox" aria-label="运行目标" @keydown="handleListKeydown">
                <VNextNavigationItem
                    density="rich" selectable
                    role="option"
                    :selected="selectedTargetId === null"
                    data-target-id="none"
                    @click="requestSelection(null)"
                >
                    <Crosshair :size="15" aria-hidden="true" />
                    <span><strong>无操作目标</strong><small>纯计算、文件、消息和日志</small></span>
                    <em v-if="store.defaultTargetId === null">默认</em>
                </VNextNavigationItem>
                <VNextNavigationItem
                    v-for="target in store.targets"
                    :key="target.target_id"
                    density="rich" selectable
                    role="option"
                    :selected="selectedTargetId === target.target_id"
                    :data-target-id="target.target_id"
                    @click="requestSelection(target.target_id)"
                >
                    <Monitor v-if="target.type === 'windows'" :size="15" aria-hidden="true" />
                    <Smartphone v-else :size="15" aria-hidden="true" />
                    <span><strong>{{ target.name }}</strong><small>{{ targetBindingSummary(target) }}</small></span>
                    <em v-if="target.target_id === store.defaultTargetId">默认</em>
                </VNextNavigationItem>
            </div>
        </VNextNavigationPane>

        <main class="target-summary" aria-live="polite">
            <div v-if="selectedTarget" class="summary-content">
                <div class="summary-icon">
                    <Monitor v-if="selectedTarget.type === 'windows'" :size="24" aria-hidden="true" />
                    <Smartphone v-else :size="24" aria-hidden="true" />
                </div>
                <div class="summary-heading">
                    <span>{{ targetTypeLabel(selectedTarget.type) }}</span>
                    <h1>{{ selectedTarget.name }}</h1>
                    <p>{{ targetBindingSummary(selectedTarget) }}</p>
                </div>
                <div class="summary-actions">
                    <button ref="editTargetButton" type="button" class="primary-action" @click="openInspector"><PencilLine :size="14" />编辑设置</button>
                    <button v-if="selectedTarget.target_id !== store.defaultTargetId" type="button" :disabled="store.targetBusy || readOnly" @click="makeDefault">设为默认</button>
                    <button type="button" class="danger-action" :disabled="store.targetBusy || readOnly" @click="requestDelete"><Trash2 :size="14" />删除</button>
                </div>
            </div>
            <VNextWorkspaceState v-else class="summary-empty" kind="selection" title="无操作目标" description="适用于纯计算、文件处理、消息协作和日志脚本。视觉与输入函数会在检查或运行前明确阻止。">
                <template #icon><Crosshair :size="28" /></template>
                <template #actions><VNextButton v-if="store.defaultTargetId !== null" size="compact" :disabled="store.targetBusy || readOnly" @click="makeNoTargetDefault">设为默认运行方式</VNextButton><span v-else><CircleCheck :size="14" aria-hidden="true" />当前默认运行方式</span></template>
            </VNextWorkspaceState>
        </main>

        <button v-if="inspectorOpen" type="button" class="inspector-scrim" aria-label="关闭运行目标检查器" @click="closeInspector" />
        <aside :class="['target-inspector', { 'is-open': inspectorOpen }]" aria-label="运行目标设置" @keydown.esc.stop="closeInspector">
            <VNextPaneHeader role="inspector" :title="selectedTarget?.name || '无操作目标'">
                <template #actions><VNextIconButton label="关闭检查器" @click="closeInspector"><X /></VNextIconButton></template>
            </VNextPaneHeader>
            <form v-if="draft" class="target-form app-inspector-form" @submit.prevent="saveDraft">
                <div class="form-scroll app-inspector-body">
                    <section>
                        <h2>基本信息</h2>
                        <label class="field app-form-row"><span class="app-form-label">名称</span><input v-model="draft.name" class="app-form-control" data-testid="target-name" :disabled="store.targetBusy || readOnly" maxlength="160" autocomplete="off" /></label>
                        <div class="readonly-field app-form-row" title="目标类型不能原地更改"><span class="app-form-label">类型</span><strong class="app-form-control">{{ targetTypeLabel(draft.type) }}</strong></div>
                    </section>

                    <section v-if="draft.type === 'windows'">
                        <h2>Windows 绑定</h2>
                        <label class="field app-form-row"><span class="app-form-label">工作区域</span>
                            <select class="app-form-control" :value="draft.work_area.mode" data-testid="target-work-area" :disabled="store.targetBusy || readOnly" @change="changeWindowsWorkArea">
                                <option value="desktop">整个桌面</option>
                                <option value="client">窗口客户区</option>
                                <option value="window">完整窗口</option>
                                <option value="region">自定义区域</option>
                            </select>
                        </label>
                        <template v-if="draft.work_area.mode !== 'desktop'">
                            <div class="field app-form-row window-binding-field">
                                <span class="app-form-label">窗口标题</span>
                                <div class="window-binding-control">
                                    <input :value="draft.window_title" class="app-form-control" data-testid="target-window-title" :disabled="store.targetBusy || readOnly" maxlength="512" placeholder="输入标题，或捕获具体窗口" @input="updateWindowTitle(draft, $event, 'edit')" />
                                    <VNextIconButton role="field" size="default" label="捕获目标窗口" :disabled="store.targetBusy || readOnly || Boolean(windowAction)" data-testid="capture-target-window" @click="captureWindow(draft, 'edit')"><Crosshair aria-hidden="true" /></VNextIconButton>
                                    <VNextIconButton role="field" size="default" label="测试目标窗口" :disabled="store.targetBusy || readOnly || !draft.window_title.trim() || Boolean(windowAction)" data-testid="test-target-window" @click="testWindow(draft, 'edit')"><LocateFixed aria-hidden="true" /></VNextIconButton>
                                </div>
                                <small v-if="editWindowFeedback.message" class="app-form-help window-binding-feedback" :data-tone="editWindowFeedback.tone">{{ editWindowFeedback.message }}</small>
                            </div>
                            <label class="field app-form-row"><span class="app-form-label">匹配方式</span>
                                <select :value="draft.window_match" class="app-form-control" :disabled="store.targetBusy || readOnly" @change="updateWindowMatch(draft, $event, 'edit')">
                                    <option value="contains">标题包含</option>
                                    <option value="exact">标题完全一致</option>
                                    <option value="regex">正则表达式</option>
                                </select>
                            </label>
                        </template>
                        <div v-if="draft.work_area.mode === 'region'" class="region-grid" aria-label="自定义区域">
                            <label><span>X</span><input v-model.number="draft.work_area.region[0]" type="number" min="0" step="1" :disabled="store.targetBusy || readOnly" /></label>
                            <label><span>Y</span><input v-model.number="draft.work_area.region[1]" type="number" min="0" step="1" :disabled="store.targetBusy || readOnly" /></label>
                            <label><span>宽</span><input v-model.number="draft.work_area.region[2]" type="number" min="1" step="1" :disabled="store.targetBusy || readOnly" /></label>
                            <label><span>高</span><input v-model.number="draft.work_area.region[3]" type="number" min="1" step="1" :disabled="store.targetBusy || readOnly" /></label>
                        </div>
                        <label class="check-field">
                            <input v-model="draft.allow_physical_fallback" type="checkbox" :disabled="store.targetBusy || readOnly || draft.work_area.mode === 'desktop'" />
                            <span><strong>{{ draft.work_area.mode === 'desktop' ? '固定使用物理输入' : '允许后台输入失败时回退物理输入' }}</strong><small>{{ draft.work_area.mode === 'desktop' ? '桌面没有可归属的后台窗口，不能关闭。' : '触发回退时日志会记录原因和真实输入路径。' }}</small></span>
                        </label>
                    </section>

                    <section v-else-if="draft.type === 'android_adb'">
                        <h2>ADB 绑定</h2>
                        <label class="field app-form-row"><span class="app-form-label">设备序列号</span><input v-model="draft.device_serial" class="app-form-control" data-testid="target-adb-serial" :disabled="store.targetBusy || readOnly" maxlength="256" autocomplete="off" placeholder="例如：emulator-5554" /><small class="app-form-help">离线时不会自动切换其他设备。</small></label>
                        <VNextAdbDevicePicker :model-value="draft.device_serial" :disabled="store.targetBusy || readOnly" @select="draft.device_serial = $event" />
                    </section>

                    <section v-else>
                        <h2>Android 本机</h2>
                        <p class="field-help">表示安装 Player 的当前 Android 手机，不配置 Windows 窗口或 ADB 序列号。</p>
                    </section>

                    <p v-if="editError || store.targetError" class="form-error" role="alert">{{ editError || store.targetError }}</p>
                </div>
                <footer>
                    <button v-if="draft.target_id !== store.defaultTargetId" type="button" :disabled="store.targetBusy || readOnly || dirty" @click="makeDefault">设为默认</button>
                    <button type="button" class="danger-outline" :disabled="store.targetBusy || readOnly || dirty" @click="requestDelete"><Trash2 :size="14" />删除</button>
                    <span class="footer-spacer"></span>
                    <button type="button" :disabled="!dirty || store.targetBusy" @click="discardChanges">放弃修改</button>
                    <button type="submit" class="primary" :disabled="!dirty || store.targetBusy || readOnly">保存设置</button>
                </footer>
            </form>
            <VNextWorkspaceState v-else class="inspector-empty no-target-config" compact kind="selection" title="无操作目标" description="适用于纯计算、文件、消息和日志；视觉与输入函数会被检查器阻止。">
                <template #icon><Crosshair :size="26" /></template>
                <template #actions><VNextButton v-if="store.defaultTargetId !== null" size="compact" :disabled="store.targetBusy || readOnly" @click="makeNoTargetDefault">设为默认</VNextButton><em v-else><CircleCheck :size="14" aria-hidden="true" />当前默认</em></template>
            </VNextWorkspaceState>
        </aside>

        <div v-if="createOpen" class="dialog-backdrop" @mousedown.self="closeCreate">
            <section class="target-dialog create-target-dialog" role="dialog" aria-modal="true" aria-labelledby="create-target-title" @keydown="trapDialogFocus" @keydown.esc="closeCreate">
                <header><div><h2 id="create-target-title">新建运行目标</h2></div><button type="button" aria-label="关闭" @click="closeCreate"><X :size="15" /></button></header>
                <form @submit.prevent="createTarget">
                    <fieldset class="type-picker">
                        <legend>目标类型</legend>
                        <label v-for="option in createTypeOptions" :key="option.value" :class="{ active: createDraft.type === option.value }">
                            <input :checked="createDraft.type === option.value" type="radio" name="target-type" :value="option.value" @change="setCreateType(option.value)" />
                            <span><strong>{{ option.label }}</strong><small>{{ option.description }}</small></span>
                        </label>
                    </fieldset>
                    <label class="field app-form-row"><span class="app-form-label">名称</span><input ref="createNameInput" v-model="createDraft.name" class="app-form-control" data-testid="create-target-name" maxlength="160" autocomplete="off" /></label>
                    <template v-if="createDraft.type === 'windows'">
                        <label class="field app-form-row"><span class="app-form-label">工作区域</span><select class="app-form-control" :value="createDraft.work_area.mode" data-testid="create-target-work-area" @change="changeCreateWindowsWorkArea"><option value="desktop">整个桌面</option><option value="client">窗口客户区</option><option value="window">完整窗口</option><option value="region">自定义区域</option></select></label>
                        <template v-if="createDraft.work_area.mode !== 'desktop'">
                            <div class="field app-form-row window-binding-field">
                                <span class="app-form-label">窗口标题</span>
                                <div class="window-binding-control">
                                    <input :value="createDraft.window_title" class="app-form-control" data-testid="create-target-window-title" maxlength="512" placeholder="输入标题，或捕获具体窗口" @input="updateWindowTitle(createDraft as WindowsTargetDefinition, $event, 'create')" />
                                    <VNextIconButton role="field" size="default" label="捕获目标窗口" :disabled="store.targetBusy || readOnly || Boolean(windowAction)" data-testid="capture-create-target-window" @click="captureWindow(createDraft as WindowsTargetDefinition, 'create')"><Crosshair aria-hidden="true" /></VNextIconButton>
                                    <VNextIconButton role="field" size="default" label="测试目标窗口" :disabled="store.targetBusy || readOnly || !createDraft.window_title.trim() || Boolean(windowAction)" data-testid="test-create-target-window" @click="testWindow(createDraft as WindowsTargetDefinition, 'create')"><LocateFixed aria-hidden="true" /></VNextIconButton>
                                </div>
                                <small v-if="createWindowFeedback.message" class="app-form-help window-binding-feedback" :data-tone="createWindowFeedback.tone">{{ createWindowFeedback.message }}</small>
                            </div>
                            <label class="field app-form-row"><span class="app-form-label">匹配方式</span><select :value="createDraft.window_match" class="app-form-control" @change="updateWindowMatch(createDraft as WindowsTargetDefinition, $event, 'create')"><option value="contains">标题包含</option><option value="exact">标题完全一致</option><option value="regex">正则表达式</option></select></label>
                        </template>
                        <div v-if="createDraft.work_area.mode === 'region'" class="region-grid"><label><span>X</span><input v-model.number="createDraft.work_area.region[0]" type="number" min="0" step="1" /></label><label><span>Y</span><input v-model.number="createDraft.work_area.region[1]" type="number" min="0" step="1" /></label><label><span>宽</span><input v-model.number="createDraft.work_area.region[2]" type="number" min="1" step="1" /></label><label><span>高</span><input v-model.number="createDraft.work_area.region[3]" type="number" min="1" step="1" /></label></div>
                        <label class="check-field"><input v-model="createDraft.allow_physical_fallback" type="checkbox" :disabled="createDraft.work_area.mode === 'desktop'" /><span><strong>{{ createDraft.work_area.mode === 'desktop' ? '固定使用物理输入' : '允许后台输入失败时回退物理输入' }}</strong></span></label>
                    </template>
                    <template v-else-if="createDraft.type === 'android_adb'">
                        <label class="field app-form-row"><span class="app-form-label" title="ADB 设备序列号">设备序列号</span><input v-model="createDraft.device_serial" class="app-form-control" data-testid="create-target-adb-serial" maxlength="256" autocomplete="off" placeholder="例如：emulator-5554" /></label>
                        <VNextAdbDevicePicker :model-value="createDraft.device_serial" :disabled="store.targetBusy || readOnly" @select="createDraft.device_serial = $event" />
                    </template>
                    <p v-else class="field-help">Android 本机目标始终表示安装 Player 的当前手机。</p>
                    <p v-if="createError" class="form-error" role="alert">{{ createError }}</p>
                    <footer><button type="button" @click="closeCreate">取消</button><button type="submit" class="primary" :disabled="store.targetBusy || readOnly">创建目标</button></footer>
                </form>
            </section>
        </div>

        <div v-if="unsavedPrompt" class="dialog-backdrop">
            <section class="target-dialog compact-dialog" role="alertdialog" aria-modal="true" aria-labelledby="unsaved-target-title" @keydown="trapDialogFocus">
                <header><div><h2 id="unsaved-target-title">先处理未保存修改</h2><p>切换目标不会自动丢弃右侧草稿。</p></div></header>
                <footer><button type="button" @click="cancelPendingSelection">继续编辑</button><button type="button" class="danger-outline" @click="discardAndSwitch">放弃并切换</button></footer>
            </section>
        </div>

        <div v-if="deleteCandidate" class="dialog-backdrop">
            <section class="target-dialog delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-target-title" @keydown="trapDialogFocus">
                <header><div><h2 id="delete-target-title">{{ deleteReferenceError ? '暂时无法检查引用' : deleteReferences.length ? '运行目标仍在使用' : '删除运行目标？' }}</h2><p>{{ deleteReferenceError || (deleteReferences.length ? '先处理这些稳定引用，才能删除目标。' : `将从项目中删除“${deleteCandidate.name}”。`) }}</p></div></header>
                <ul v-if="deleteReferences.length" class="reference-list">
                    <li v-for="(reference, index) in deleteReferences" :key="`${reference.kind}:${index}`">
                        <button v-if="reference.function_id" type="button" @click="openReference(reference)"><span>{{ reference.function_name || '项目函数' }}</span><small>{{ referenceLabel(reference) }}</small></button>
                        <div v-else><span>{{ referenceName(reference) }}</span><small>{{ referenceLabel(reference) }}</small></div>
                    </li>
                </ul>
                <footer><button type="button" @click="closeDelete">关闭</button><button v-if="deleteReferenceError" type="button" class="primary" :disabled="store.targetBusy" @click="requestDelete">重新检查</button><button v-else-if="!deleteReferences.length" type="button" class="danger" :disabled="store.targetBusy" @click="confirmDelete">确认删除</button></footer>
            </section>
        </div>

        <div v-if="store.targetConflict" class="dialog-backdrop">
            <section class="target-dialog compact-dialog" role="alertdialog" aria-modal="true" aria-labelledby="target-conflict-title" @keydown="trapDialogFocus">
                <header><div><h2 id="target-conflict-title">运行目标已在外部修改</h2><p>当前草稿没有覆盖磁盘内容。重新加载后再继续配置。</p></div></header>
                <footer><button type="button" class="primary" :disabled="store.targetBusy" @click="reloadConflict">重新加载目标配置</button></footer>
            </section>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { CircleCheck, Crosshair, LocateFixed, Monitor, PencilLine, Plus, Smartphone, Trash2, X } from 'lucide-vue-next'
import { vnextApi } from '../api'
import { vnextCaptureSession } from '../captureSession'
import { trapDialogFocus } from '../dialogFocus'
import { useVNextStore } from '../store'
import type { CapturedWindowBinding, TargetDefinition, TargetReferenceDefinition, WindowsTargetDefinition } from '../types'
import VNextAdbDevicePicker from './VNextAdbDevicePicker.vue'
import VNextPaneHeader from './ui/VNextPaneHeader.vue'
import VNextNavigationPane from './ui/VNextNavigationPane.vue'
import VNextNavigationItem from './ui/VNextNavigationItem.vue'
import VNextWorkspaceState from './ui/VNextWorkspaceState.vue'
import VNextButton from './ui/VNextButton.vue'
import VNextIconButton from './ui/VNextIconButton.vue'

const props = withDefaults(defineProps<{
    readOnly?: boolean
    ensureCaptureSession?: () => Promise<void>
}>(), { readOnly: false, ensureCaptureSession: undefined })
const emit = defineEmits<{ openReference: [reference: TargetReferenceDefinition] }>()
const store = useVNextStore()
const selectedTargetId = ref<string | null>(null)
const draft = ref<TargetDefinition | null>(null)
const inspectorOpen = ref(false)
const editError = ref('')
const createOpen = ref(false)
const createDraft = ref<TargetDefinition>(newTarget('windows'))
const createError = ref('')
const createNameInput = ref<HTMLInputElement | null>(null)
const editTargetButton = ref<HTMLButtonElement | null>(null)
const pendingSelection = ref<{ targetId: string | null } | null>(null)
const unsavedPrompt = ref(false)
const deleteCandidate = ref<TargetDefinition | null>(null)
const deleteReferences = ref<TargetReferenceDefinition[]>([])
const deleteReferenceError = ref('')
type WindowFeedback = { message: string; tone: 'neutral' | 'success' | 'error' }
type WindowScope = 'edit' | 'create'
const windowAction = ref('')
const editWindowFeedback = ref<WindowFeedback>({ message: '', tone: 'neutral' })
const createWindowFeedback = ref<WindowFeedback>({ message: '', tone: 'neutral' })
let selectionInitialized = false

const createTypeOptions = [
    { value: 'windows' as const, label: 'Windows', description: '窗口、桌面或自定义区域' },
    { value: 'android_adb' as const, label: 'Android ADB', description: '模拟器或 USB 调试设备' },
    { value: 'android_local' as const, label: 'Android 本机', description: '安装 Player 的当前手机' },
]
const selectedTarget = computed(() => store.targets.find((item) => item.target_id === selectedTargetId.value) || null)
const dirty = computed(() => Boolean(draft.value && selectedTarget.value && fingerprint(draft.value) !== fingerprint(selectedTarget.value)))

watch(
    () => `${store.workspace?.workspace_id || ''}:${store.workspace?.generation || 0}`,
    () => {
        selectionInitialized = false
        selectedTargetId.value = null
        draft.value = null
        inspectorOpen.value = false
        editError.value = ''
        pendingSelection.value = null
        unsavedPrompt.value = false
        deleteCandidate.value = null
        deleteReferences.value = []
        deleteReferenceError.value = ''
        windowAction.value = ''
        editWindowFeedback.value = { message: '', tone: 'neutral' }
        createWindowFeedback.value = { message: '', tone: 'neutral' }
    },
)
watch(
    () => [store.targets, store.defaultTargetId] as const,
    () => {
        if (!selectionInitialized) {
            selectedTargetId.value = store.defaultTargetId || store.targets[0]?.target_id || null
            selectionInitialized = true
        }
        const stillExists = selectedTargetId.value === null || store.targets.some((item) => item.target_id === selectedTargetId.value)
        if (!stillExists) selectedTargetId.value = store.defaultTargetId || store.targets[0]?.target_id || null
        if (!dirty.value) syncDraft()
    },
    { deep: true, immediate: true },
)
watch(selectedTargetId, () => { syncDraft(); editError.value = '' })

function cloneTarget<T extends TargetDefinition>(target: T): T { return JSON.parse(JSON.stringify(target)) as T }
function fingerprint(target: TargetDefinition): string { return JSON.stringify(target) }
function newTarget(type: TargetDefinition['type']): TargetDefinition {
    const id = `target_${globalThis.crypto?.randomUUID?.().replaceAll('-', '') || `${Date.now()}${Math.random().toString(36).slice(2)}`}`
    if (type === 'windows') return { target_id: id, name: 'Windows 桌面', type, window_title: '', window_match: 'contains', work_area: { mode: 'desktop' }, allow_physical_fallback: true }
    if (type === 'android_adb') return { target_id: id, name: 'Android 模拟器', type, device_serial: '' }
    return { target_id: id, name: '当前手机', type }
}
function syncDraft(): void { draft.value = selectedTarget.value ? cloneTarget(selectedTarget.value) : null }
function targetTypeLabel(type: TargetDefinition['type']): string { return type === 'windows' ? 'Windows' : type === 'android_adb' ? 'Android ADB' : 'Android 本机' }
function targetBindingSummary(target: TargetDefinition): string {
    if (target.type === 'android_adb') return target.device_serial
    if (target.type === 'android_local') return '当前手机'
    if (target.work_area.mode === 'desktop') return '整个 Windows 桌面'
    const captured = target.window_binding ? ' · 已捕获' : ''
    if (target.work_area.mode === 'region') return `${target.window_title} · ${target.work_area.region.join(', ')}${captured}`
    const area = target.work_area.mode === 'client' ? '窗口客户区' : '完整窗口'
    return `${target.window_title.trim() === target.name.trim() ? area : `${target.window_title} · ${area}`}${captured}`
}
function validateTarget(target: TargetDefinition, excludingId = ''): string {
    const name = target.name.trim()
    if (!name) return '请输入目标名称'
    if (store.targets.some((item) => item.target_id !== excludingId && item.name.trim().toLocaleLowerCase() === name.toLocaleLowerCase())) return '目标名称不能重复'
    if (target.type === 'android_adb') {
        if (!target.device_serial.trim()) return '请填写明确的 ADB 设备序列号'
        if (/\s/.test(target.device_serial.trim())) return 'ADB 设备序列号不能包含空白字符'
    }
    if (target.type === 'android_local' && store.targets.some((item) => item.target_id !== excludingId && item.type === 'android_local')) return '一个项目只能登记一个 Android 本机目标'
    if (target.type === 'windows') {
        if (target.work_area.mode !== 'desktop' && !target.window_title.trim()) return '窗口模式必须填写窗口标题'
        if (target.work_area.mode === 'region') {
            const [x, y, width, height] = target.work_area.region
            if (![x, y, width, height].every(Number.isInteger) || x < 0 || y < 0 || width <= 0 || height <= 0) return '自定义区域必须使用非负整数坐标和大于 0 的宽高'
        }
        if (target.window_match === 'regex' && target.window_title) {
            try { new RegExp(target.window_title) } catch { return '窗口标题正则表达式无效' }
        }
        if (target.window_binding && (target.window_match !== 'exact' || target.window_binding.title !== target.window_title.trim())) return '捕获的窗口绑定与标题不一致，请重新捕获'
    }
    return ''
}
function setWindowsWorkArea(target: WindowsTargetDefinition, mode: WindowsTargetDefinition['work_area']['mode']): void {
    const previous = target.work_area
    if (mode === 'desktop') {
        target.work_area = { mode: 'desktop' }
        target.window_title = ''
        target.window_binding = undefined
        target.allow_physical_fallback = true
    } else if (mode === 'region') {
        target.work_area = { mode: 'region', region: previous.mode === 'region' ? previous.region : [0, 0, 1280, 720] }
    } else {
        target.work_area = { mode }
    }
}
function selectedWorkArea(event: Event): WindowsTargetDefinition['work_area']['mode'] {
    return (event.target as HTMLSelectElement).value as WindowsTargetDefinition['work_area']['mode']
}
function changeWindowsWorkArea(event: Event): void { if (draft.value?.type === 'windows') setWindowsWorkArea(draft.value, selectedWorkArea(event)) }
function changeCreateWindowsWorkArea(event: Event): void { if (createDraft.value.type === 'windows') setWindowsWorkArea(createDraft.value, selectedWorkArea(event)) }

function feedback(scope: WindowScope) { return scope === 'edit' ? editWindowFeedback : createWindowFeedback }
function resetWindowBinding(target: WindowsTargetDefinition, scope: WindowScope): void {
    target.window_binding = undefined
    feedback(scope).value = { message: '', tone: 'neutral' }
}
function updateWindowTitle(target: WindowsTargetDefinition, event: Event, scope: WindowScope): void {
    const title = (event.target as HTMLInputElement).value
    if (target.window_title !== title) resetWindowBinding(target, scope)
    target.window_title = title
}
function updateWindowMatch(target: WindowsTargetDefinition, event: Event, scope: WindowScope): void {
    const mode = (event.target as HTMLSelectElement).value as WindowsTargetDefinition['window_match']
    if (target.window_match !== mode) resetWindowBinding(target, scope)
    target.window_match = mode
}
async function captureWindow(target: WindowsTargetDefinition, scope: WindowScope): Promise<void> {
    const state = feedback(scope)
    windowAction.value = `${scope}:capture`
    state.value = { message: '请在冻结画面中点击要绑定的窗口', tone: 'neutral' }
    try {
        await props.ensureCaptureSession?.()
        await vnextCaptureSession.captureWindow(async (payload) => {
            const binding = payload.binding as CapturedWindowBinding | undefined
            if (!binding?.binding_id || !binding.title) throw new Error('窗口捕获结果无效')
            target.window_title = binding.title
            target.window_match = 'exact'
            target.window_binding = binding
            state.value = { message: `已捕获当前窗口实例${binding.executable_name ? ` · ${binding.executable_name}` : ''}，保存后生效`, tone: 'success' }
            windowAction.value = ''
        }, {
            onCancel: () => {
                state.value = { message: '已取消捕获，原设置未改变', tone: 'neutral' }
                windowAction.value = ''
            },
            onError: (message) => {
                state.value = { message, tone: 'error' }
                windowAction.value = ''
            },
        })
    } catch (error) {
        state.value = { message: error instanceof Error ? error.message : '窗口捕获失败', tone: 'error' }
        windowAction.value = ''
    }
}
async function testWindow(target: WindowsTargetDefinition, scope: WindowScope): Promise<void> {
    const state = feedback(scope)
    if (!store.workspace) { state.value = { message: '请先打开项目', tone: 'error' }; return }
    windowAction.value = `${scope}:test`
    state.value = { message: '正在查找目标窗口…', tone: 'neutral' }
    try {
        const result = await vnextApi.testWindowsTarget(store.workspace, cloneTarget(target))
        state.value = { message: `${result.message}${result.application ? ` · ${result.application}` : ''}`, tone: 'success' }
    } catch (error) {
        state.value = { message: error instanceof Error ? error.message : '目标窗口测试失败', tone: 'error' }
    } finally { windowAction.value = '' }
}

function requestSelection(targetId: string | null): void {
    if (targetId === selectedTargetId.value) return
    if (dirty.value) { pendingSelection.value = { targetId }; unsavedPrompt.value = true; return }
    selectedTargetId.value = targetId
}
function handleListKeydown(event: KeyboardEvent): void {
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const ids: Array<string | null> = [null, ...store.targets.map((item) => item.target_id)]
    const current = Math.max(0, ids.findIndex((item) => item === selectedTargetId.value))
    const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? ids.length - 1 : event.key === 'ArrowDown' ? Math.min(ids.length - 1, current + 1) : Math.max(0, current - 1)
    requestSelection(ids[nextIndex] ?? null)
    void nextTick(() => document.querySelector<HTMLElement>(`[data-target-id="${ids[nextIndex] || 'none'}"]`)?.focus())
}
function cancelPendingSelection(): void { pendingSelection.value = null; unsavedPrompt.value = false }
function discardAndSwitch(): void { const next = pendingSelection.value?.targetId ?? null; pendingSelection.value = null; unsavedPrompt.value = false; selectedTargetId.value = next; syncDraft() }
function discardChanges(): void { syncDraft(); editError.value = '' }
function openInspector(): void {
    inspectorOpen.value = true
    void nextTick(() => document.querySelector<HTMLElement>('.target-inspector input:not(:disabled), .target-inspector select:not(:disabled)')?.focus())
}
function closeInspector(): void {
    inspectorOpen.value = false
    void nextTick(() => editTargetButton.value?.focus())
}

async function saveDraft(): Promise<void> {
    if (!draft.value || !selectedTarget.value) return
    editError.value = validateTarget(draft.value, draft.value.target_id)
    if (editError.value) return
    try { await store.updateTarget(cloneTarget(draft.value)); inspectorOpen.value = false } catch (error) { editError.value = error instanceof Error ? error.message : '保存失败' }
}
async function makeDefault(): Promise<void> {
    if (!selectedTarget.value) return
    try { await store.saveTargets(store.targets, selectedTarget.value.target_id) } catch { /* store owns error */ }
}
async function makeNoTargetDefault(): Promise<void> { try { await store.saveTargets(store.targets, null) } catch { /* store owns error */ } }

function openCreate(): void {
    createDraft.value = newTarget('windows')
    createError.value = ''
    createWindowFeedback.value = { message: '', tone: 'neutral' }
    createOpen.value = true
    void nextTick(() => createNameInput.value?.focus())
}
function closeCreate(): void { if (!store.targetBusy) createOpen.value = false }
function setCreateType(type: TargetDefinition['type']): void { createDraft.value = newTarget(type); createError.value = ''; void nextTick(() => createNameInput.value?.focus()) }
async function createTarget(): Promise<void> {
    createError.value = validateTarget(createDraft.value)
    if (createError.value) return
    const target = cloneTarget(createDraft.value)
    try {
        const nextDefault = store.targets.length === 0 ? target.target_id : store.defaultTargetId
        await store.saveTargets([...store.targets, target], nextDefault)
        createOpen.value = false
        selectedTargetId.value = target.target_id
        syncDraft()
        inspectorOpen.value = true
    } catch (error) { createError.value = error instanceof Error ? error.message : '创建失败' }
}

async function requestDelete(): Promise<void> {
    if (!selectedTarget.value) return
    deleteCandidate.value = selectedTarget.value
    deleteReferences.value = []
    deleteReferenceError.value = ''
    try { deleteReferences.value = await store.targetReferences(selectedTarget.value.target_id) }
    catch (error) { deleteReferenceError.value = error instanceof Error ? error.message : '引用检查失败' }
}
function closeDelete(): void { if (!store.targetBusy) { deleteCandidate.value = null; deleteReferences.value = []; deleteReferenceError.value = '' } }
async function confirmDelete(): Promise<void> {
    if (!deleteCandidate.value) return
    const id = deleteCandidate.value.target_id
    try {
        await store.saveTargets(store.targets.filter((item) => item.target_id !== id), store.defaultTargetId === id ? null : store.defaultTargetId)
        deleteCandidate.value = null
        deleteReferences.value = []
        selectedTargetId.value = store.defaultTargetId || store.targets[0]?.target_id || null
        syncDraft()
    } catch (error) {
        if (store.targetBlockedReferences.length) deleteReferences.value = [...store.targetBlockedReferences]
        else deleteReferenceError.value = error instanceof Error ? error.message : '删除失败'
    }
}
function openReference(reference: TargetReferenceDefinition): void { closeDelete(); emit('openReference', reference) }
function referenceName(reference: TargetReferenceDefinition): string { return reference.variable_name || reference.path || (reference.kind === 'player_form' ? 'Player 表单' : reference.kind) }
function referenceLabel(reference: TargetReferenceDefinition): string { return reference.field_path || reference.field || reference.location || reference.statement_id || reference.value_id || '稳定目标引用' }
async function reloadConflict(): Promise<void> { try { await store.refreshTargets(); syncDraft(); editError.value = '' } catch { /* store owns error */ } }
</script>

<style scoped>
.target-workspace { position: relative; width: 100%; height: 100%; min-width: 0; min-height: 0; display: grid; grid-template-columns: minmax(224px, 260px) minmax(0, 1fr); overflow: hidden; background: var(--app-bg-base); color: var(--app-text-regular); }
.target-sidebar, .target-inspector { min-width: 0; min-height: 0; background: var(--app-bg-sidebar); }
.target-sidebar { display: grid; grid-template-rows: var(--app-height-pane-header) minmax(0, 1fr) auto; border-right: 1px solid var(--app-border-subtle); }
.target-sidebar > header, .target-inspector > header { min-height: var(--app-height-pane-header); display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 0 10px 0 12px; border-bottom: 1px solid var(--app-border-subtle); }
.target-sidebar > header > div, .target-inspector > header > div { min-width: 0; display: flex; align-items: baseline; gap: 7px; }
.target-sidebar header strong, .target-inspector header strong { overflow: hidden; color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.target-sidebar header small, .target-inspector header span { color: var(--app-text-placeholder); font-size: var(--app-font-xs); }
.target-sidebar header button { height: var(--app-control-compact); display: inline-flex; align-items: center; gap: 5px; padding: 0 7px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-secondary); font: inherit; cursor: pointer; }
.target-sidebar header button:hover:not(:disabled), .target-sidebar header button:focus-visible { background: var(--app-bg-hover); color: var(--app-text-primary); outline: 0; box-shadow: var(--focus-ring); }
.target-sidebar button:disabled { opacity: .4; cursor: default; }
.target-list { min-height: 0; overflow: auto; padding: 6px; }
.target-list > button { width: 100%; min-height: var(--app-list-row-rich); display: grid; grid-template-columns: 20px minmax(0, 1fr) auto; align-items: center; gap: 7px; padding: 5px 8px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-regular); font: inherit; text-align: start; cursor: pointer; }
.target-list > button:hover, .target-list > button:focus-visible { background: var(--app-bg-hover); outline: 0; box-shadow: var(--focus-ring); }
.target-list > button > svg { color: var(--app-text-secondary); }
.target-list > button.active > svg { color: var(--app-color-primary); }
.target-list button > span { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.target-list button strong, .target-list button small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.target-list button strong { font-size: var(--app-font-sm); font-weight: 500; }
.target-list button small { color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.target-list button em { color: var(--app-color-primary); font-size: var(--app-font-xs); font-style: normal; }
.target-summary { display: none; min-width: 0; min-height: 0; overflow: auto; padding: clamp(24px, 5vw, 64px); }
.summary-content { width: min(680px, 100%); margin: 0 auto; }
.summary-icon { width: 48px; height: 48px; display: grid; place-items: center; margin-bottom: 18px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-lg); background: var(--app-bg-raised); color: var(--app-color-primary); }
.summary-heading > span { color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.summary-heading h1 { margin: 5px 0 4px; color: var(--app-text-primary); font-size: var(--app-font-xl); font-weight: 650; line-height: 1.3; }
.summary-heading p { margin: 0; color: var(--app-text-secondary); font-size: var(--app-font-sm); }
.summary-actions { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 24px; }
.summary-actions button, .summary-empty button { min-height: var(--app-control-default); display: inline-flex; align-items: center; gap: 6px; padding: 0 11px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); background: var(--app-bg-raised); color: var(--app-text-regular); font: inherit; cursor: pointer; }
.summary-actions button:hover:not(:disabled), .summary-empty button:hover:not(:disabled), .summary-actions button:focus-visible, .summary-empty button:focus-visible { border-color: var(--app-border-strong); background: var(--app-bg-hover); color: var(--app-text-primary); outline: 0; box-shadow: var(--focus-ring); }
.summary-actions .primary-action { border-color: var(--app-color-primary); color: var(--app-color-primary); }
.summary-actions .danger-action { color: var(--app-color-danger); }
.summary-empty { min-height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 7px; text-align: center; color: var(--app-text-secondary); }
.summary-empty > svg { color: var(--app-text-placeholder); }
.summary-empty strong { margin-top: 4px; color: var(--app-text-primary); font-size: var(--app-font-md); }
.summary-empty p { max-width: 420px; margin: 0 0 8px; font-size: var(--app-font-sm); line-height: 1.6; }
.summary-empty > span { display: inline-flex; align-items: center; gap: 5px; color: var(--app-color-success); font-size: var(--app-font-xs); }
.target-inspector { display: grid; grid-template-rows: var(--app-height-pane-header) minmax(0, 1fr); border-left: 1px solid var(--app-border-subtle); }
.inspector-scrim { display: none; }
.target-inspector > header > div { flex-direction: column; align-items: flex-start; gap: 0; }
.inspector-close { display: none; width: 28px; height: var(--app-control-compact); place-items: center; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-secondary); cursor: pointer; }
.target-form { min-height: 0; display: grid; grid-template-rows: minmax(0, 1fr) auto; }
.form-scroll { container-type: inline-size; min-height: 0; overflow: auto; padding: 0 14px 18px; }
.target-form section { width: min(720px, 100%); padding: var(--app-form-section-padding) 0; border-bottom: 1px solid var(--app-border-subtle); }
.target-form h2, .type-picker legend { margin: 0 0 var(--app-form-heading-field-gap); color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 600; }
.field { --app-form-row-label-min: 84px; --app-form-row-label-max: 104px; margin-bottom: var(--app-form-field-gap); color: var(--app-text-regular); font-size: var(--app-font-sm); }
.target-form section > .field:last-child { margin-bottom: 0; }
.field > small { color: var(--app-text-placeholder); font-size: var(--app-font-xs); line-height: 1.5; }
.field input, .field select, .region-grid input { width: 100%; height: var(--app-control-default); padding: 0 9px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); outline: 0; background: var(--app-bg-input); color: var(--app-text-primary); font: inherit; }
.field input:focus, .field select:focus, .region-grid input:focus { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.window-binding-control { min-width: 0; display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 6px; }
.window-binding-control > input { min-width: 0; }
.window-binding-feedback[data-tone="success"] { color: var(--app-color-success); }
.window-binding-feedback[data-tone="error"] { color: var(--app-color-danger); }
.readonly-field { --app-form-row-label-min: 84px; --app-form-row-label-max: 104px; min-height: var(--app-control-default); font-size: var(--app-font-sm); }
.readonly-field > strong { min-height: var(--app-control-default); display: flex; align-items: center; color: var(--app-text-primary); font-weight: 500; }
.region-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 7px; margin-bottom: 12px; }
.region-grid label { min-width: 0; display: flex; flex-direction: column; gap: 5px; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.region-grid input { padding: 0 6px; }
.check-field { display: flex; align-items: flex-start; gap: 8px; color: var(--app-text-regular); font-size: var(--app-font-sm); cursor: pointer; }
.check-field input { margin-top: 3px; accent-color: var(--app-color-primary); }
.check-field > span { display: flex; flex-direction: column; gap: 2px; }
.check-field strong { color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 500; }
.check-field small, .field-help { color: var(--app-text-secondary); font-size: var(--app-font-xs); line-height: 1.55; }
.field-help { margin: 8px 0 0; }
.form-error { margin: 12px 0 0; color: var(--app-color-danger); font-size: var(--app-font-xs); line-height: 1.5; }
.target-form > footer, .target-dialog footer { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 14px; border-top: 1px solid var(--app-border-subtle); }
.target-form > footer .footer-spacer { flex: 1; }
.target-form > footer button, .target-dialog footer button { height: var(--app-control-default); padding: 0 11px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-regular); font: inherit; cursor: pointer; }
.target-form > footer button.primary, .target-dialog footer button.primary { border-color: var(--app-color-primary); background: var(--app-color-primary); color: var(--app-color-on-primary); }
.target-form > footer button:disabled, .target-dialog footer button:disabled { opacity: .4; cursor: default; }
.inspector-empty { display: grid; place-items: center; padding: 24px; color: var(--app-text-secondary); font-size: var(--app-font-sm); text-align: center; }
.no-target-config { align-content: center; gap: 8px; }
.no-target-config strong { color: var(--app-text-primary); font-size: var(--app-font-md); }
.no-target-config > span { max-width: 420px; line-height: 1.55; }
.no-target-config button { min-height: var(--app-control-default); margin-top: 6px; padding: 0 11px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); background: var(--app-bg-raised); color: var(--app-text-regular); }
.no-target-config em { display: inline-flex; align-items: center; gap: 5px; color: var(--app-color-success); font-style: normal; }
.dialog-backdrop { position: fixed; inset: 0; z-index: 2300; display: grid; place-items: center; padding: 18px; background: rgba(7, 7, 6, .72); }
.target-dialog { container-type: inline-size; width: min(560px, calc(100vw - 28px)); max-height: min(760px, calc(100vh - 32px)); overflow: auto; border: 1px solid var(--app-overlay-border); border-radius: var(--app-radius-lg); background: var(--app-bg-raised); box-shadow: var(--app-shadow-lg); }
.target-dialog > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; padding: 15px 16px; border-bottom: 1px solid var(--app-border-subtle); }
.target-dialog h2 { margin: 0; color: var(--app-text-primary); font-size: var(--app-font-md); font-weight: 600; }
.target-dialog header p { margin: 4px 0 0; color: var(--app-text-secondary); font-size: var(--app-font-xs); line-height: 1.5; }
.target-dialog header > button { width: 28px; height: var(--app-control-compact); display: grid; place-items: center; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-secondary); cursor: pointer; }
.create-target-dialog form { padding: 16px; }
.create-target-dialog form > footer { margin: 16px -16px -16px; }
.type-picker { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 7px; margin: 0 0 16px; padding: 0; border: 0; }
.type-picker legend { grid-column: 1 / -1; }
.type-picker label { min-width: 0; min-height: 76px; display: flex; align-items: flex-start; gap: 7px; padding: 9px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); cursor: pointer; }
.type-picker label.active { border-color: var(--app-color-primary); background: var(--app-color-primary-dim); }
.type-picker input { margin-top: 2px; accent-color: var(--app-color-primary); }
.type-picker span { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.type-picker strong { color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 500; }
.type-picker small { color: var(--app-text-secondary); font-size: var(--app-font-xs); line-height: 1.4; }
.compact-dialog { width: min(430px, calc(100vw - 28px)); }
.danger-outline { color: var(--app-color-danger) !important; }
.target-dialog footer button.danger { border-color: var(--app-color-danger); background: var(--app-color-danger); color: white; }
.reference-list { max-height: min(340px, 48vh); margin: 0; padding: 8px; overflow: auto; list-style: none; }
.reference-list button, .reference-list li > div { width: 100%; min-height: var(--app-list-row-rich); display: flex; flex-direction: column; align-items: flex-start; justify-content: center; gap: 3px; padding: 5px 9px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-regular); font: inherit; text-align: start; }
.reference-list button { cursor: pointer; }
.reference-list button:hover, .reference-list button:focus-visible { background: var(--app-bg-hover); outline: 0; box-shadow: var(--focus-ring); }
.reference-list small { color: var(--app-text-secondary); font-size: var(--app-font-xs); }
@container (max-width: 300px) {
    .field.app-form-row,
    .readonly-field.app-form-row { grid-template-columns: minmax(0, 1fr); row-gap: var(--app-form-label-control-gap); }
    .field.app-form-row > .app-form-help,
    .field.app-form-row > .app-form-error { grid-column: 1; }
    .region-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 1099px) {
    .target-workspace { grid-template-columns: minmax(210px, 240px) minmax(0, 1fr); }
    .target-summary { display: block; }
    .inspector-scrim { position: absolute; z-index: 39; inset: 0; display: block; padding: 0; border: 0; background: rgba(7, 7, 6, .62); cursor: default; }
    .target-inspector { position: absolute; z-index: 40; inset: 0 0 0 auto; width: min(390px, calc(100% - 48px)); display: none; box-shadow: var(--app-shadow-lg); }
    .target-inspector.is-open { display: grid; }
    .inspector-close { display: grid; }
}
@media (max-width: 819px) {
    .target-workspace { grid-template-columns: minmax(190px, 220px) minmax(0, 1fr); }
    .target-summary { padding: 22px; }
    .type-picker { grid-template-columns: 1fr; }
    .type-picker label { min-height: 56px; }
}
@media (min-width: 1100px) { .target-workspace { grid-template-columns: var(--workspace-sidebar-width, 260px) minmax(0, 1fr); } }
@media (min-width: 701px) and (max-width: 1099px) { .target-workspace { grid-template-columns: var(--workspace-sidebar-width, 260px) minmax(0, 1fr); } }
</style>
