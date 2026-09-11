<template>
    <main class="player-console">
        <VNextDesktopTitlebar :managed-close="true" @request-close="requestConsoleClose">
            <div class="console-brand"><Braces :size="17" /><strong>EasyCode Player</strong><span>多实例控制台</span></div>
            <template #meta>
                <div class="console-title-actions">
                    <div class="console-summary"><i :class="{ active: activeCount }" />{{ activeCount ? `${activeCount} 个实例运行中` : '全部空闲' }}</div>
                    <VNextIconButton :label="detailsOpen ? '仅显示实例列表' : '展开实例详情'" @click="toggleDetails">
                        <PanelRightClose v-if="detailsOpen" /><PanelRightOpen v-else />
                    </VNextIconButton>
                </div>
            </template>
        </VNextDesktopTitlebar>

        <div :class="['console-layout', { 'details-collapsed': !detailsOpen }]" :style="{ '--instance-pane-width': `${instancePaneWidth}px` }">
            <VNextNavigationPane class="instance-pane" aria-label="Player 实例">
                <VNextPaneHeader title="实例" :meta="instances.length" :icon-only-actions="true">
                    <template #actions>
                        <VNextIconButton label="为当前产品新建实例" :disabled="!createInstallationId || creating" @click="createInstance"><LoaderCircle v-if="creating" class="spin" /><Plus v-else /></VNextIconButton>
                        <VNextIconButton label="刷新实例" :disabled="loading" @click="load"><RefreshCw /></VNextIconButton>
                    </template>
                </VNextPaneHeader>

                <div v-if="loading && !instances.length" class="pane-state"><LoaderCircle class="spin" /><span>正在读取实例</span></div>
                <div v-else-if="!instances.length" class="pane-state"><Boxes /><span>{{ enabledInstallations.length ? '还没有 Player 实例' : '未检测到已安装 Player' }}</span><small>{{ enabledInstallations.length ? '点击顶部加号创建第一个实例。' : '请先运行签名 Player 安装包。' }}</small></div>
                <div v-else class="instance-list" role="listbox" aria-label="Player 实例列表">
                    <article v-for="instance in instances" :key="instance.instance_id" role="presentation" :class="['instance-row', { selected: selectedId === instance.instance_id }]">
                        <button type="button" role="option" :aria-selected="selectedId === instance.instance_id" @click="selectInstance(instance.instance_id)">
                            <span class="instance-icon"><Monitor :size="15" /></span>
                            <span class="instance-copy"><strong>{{ instance.display_name }}</strong><small>{{ instanceSubtitle(instance) }}</small></span>
                            <span :class="['status-dot', statusTone(instance.console?.status)]" :title="statusLabel(instance.console?.status)" />
                        </button>
                        <div class="instance-actions">
                            <div class="instance-control-actions" aria-label="实例操作">
                                <VNextIconButton v-if="!isActive(instance.instance_id)" label="运行此实例" @click="runInstance(instance.instance_id)"><Play /></VNextIconButton>
                                <VNextIconButton v-if="runStatus(instance.instance_id) === 'running'" label="暂停当前任务" @click="control(instance.instance_id, 'pause')"><Pause /></VNextIconButton>
                                <VNextIconButton v-if="runStatus(instance.instance_id) === 'paused'" label="继续当前任务" @click="control(instance.instance_id, 'resume')"><Play /></VNextIconButton>
                                <VNextIconButton v-if="isActive(instance.instance_id)" label="停止当前任务" tone="danger" @click="control(instance.instance_id, 'stop')"><Square /></VNextIconButton>
                                <VNextIconButton label="刷新实例" :disabled="isActive(instance.instance_id)" @click="restart(instance.instance_id)"><RotateCw /></VNextIconButton>
                                <VNextIconButton label="删除实例" tone="danger" :disabled="isActive(instance.instance_id)" @click="pendingDelete = instance"><Trash2 /></VNextIconButton>
                            </div>
                        </div>
                    </article>
                </div>
            </VNextNavigationPane>

            <VNextPaneResizer
                v-if="detailsOpen"
                v-model="instancePaneWidth"
                class="console-pane-resizer"
                orientation="vertical"
                :min="220"
                :max="480"
                :default-value="270"
                label="调整实例列表宽度"
                @commit="persistConsoleLayout"
            />

            <section v-show="detailsOpen" class="instance-stage">
                <div v-if="globalError" class="console-notice error" role="alert"><CircleAlert :size="15" /><span>{{ globalError }}</span><button type="button" aria-label="关闭错误提示" title="关闭错误提示" @click="globalError = ''"><X :size="14" /></button></div>
                <div v-else-if="consoleFeedback" class="console-notice success" role="status"><CircleCheck :size="15" /><span>{{ consoleFeedback }}</span><button type="button" aria-label="关闭提示" title="关闭提示" @click="consoleFeedback = ''"><X :size="14" /></button></div>
                <div v-if="selectedBusy" class="stage-loading"><LoaderCircle class="spin" /><strong>正在启动独立实例</strong><span>首次连接会验证签名包并建立隔离运行进程。</span></div>
                <div v-else-if="selectedSession?.error_message || selectedBootstrapState?.error_message" class="stage-loading error">
                    <CircleAlert /><strong>实例暂时不可用</strong><span>{{ selectedSession?.error_message || selectedBootstrapState?.error_message }}</span>
                    <div class="stage-recovery-actions">
                        <VNextButton size="compact" aria-label="复制诊断摘要" @click="copySelectedDiagnostic"><template #icon><Copy /></template>复制摘要</VNextButton>
                        <VNextButton size="compact" aria-label="导出最近诊断包" @click="downloadSelectedDiagnostics"><template #icon><Download /></template>诊断包</VNextButton>
                        <VNextButton size="compact" tone="primary" appearance="solid" @click="restart(selectedId)">原位重启</VNextButton>
                    </div>
                </div>
                <template v-else-if="selectedSession?.frame_url">
                    <iframe
                        v-for="session in mountedSessions"
                        v-show="session.instance_id === selectedId"
                        :key="session.instance_id"
                        :data-instance-id="session.instance_id"
                        :src="session.frame_url"
                        :title="`${session.instance_name} Player`"
                        allow="clipboard-read; clipboard-write"
                    />
                </template>
                <div v-else class="stage-empty"><Layers3 :size="28" /><strong>{{ selectedId ? '选择实例后即可开始配置' : '选择一个 Player 实例' }}</strong><span>参数、目标、日志和运行操作会显示在这里；切换实例不会中断后台任务。</span><VNextButton v-if="selectedId" tone="primary" appearance="solid" :loading="selectedBusy" @click="connect(selectedId)">连接实例</VNextButton></div>
            </section>
        </div>
        <VNextConfirmDialog
            :open="pendingConsoleClose"
            title="停止全部任务并退出？"
            :message="closeStatus?.active_count === 1
                ? '当前有 1 个 Player 实例仍在运行。退出将安全停止该任务并完整关闭 Player。'
                : `当前有 ${closeStatus?.active_count || 0} 个 Player 实例仍在运行。退出将安全停止全部任务并完整关闭 Player。`"
            confirm-label="停止全部并退出"
            tone="warning"
            :busy="closingConsole"
            :dismiss-on-backdrop="false"
            @cancel="cancelConsoleClose"
            @confirm="confirmConsoleClose"
        />
        <VNextConfirmDialog
            :open="Boolean(pendingDelete)"
            title="删除 Player 实例"
            :message="pendingDelete ? `删除“${pendingDelete.display_name}”？该实例必须处于空闲且未被计划引用；本机配置和日志会移入可恢复目录。` : ''"
            confirm-label="删除实例"
            tone="warning"
            :busy="deleting"
            @cancel="pendingDelete = null"
            @confirm="deleteInstance"
        />
    </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { Boxes, Braces, CircleAlert, CircleCheck, Copy, Download, Layers3, LoaderCircle, Monitor, PanelRightClose, PanelRightOpen, Pause, Play, Plus, RefreshCw, RotateCw, Square, Trash2, X } from 'lucide-vue-next'
import VNextButton from './components/ui/VNextButton.vue'
import VNextConfirmDialog from './components/VNextConfirmDialog.vue'
import VNextDesktopTitlebar from './components/ui/VNextDesktopTitlebar.vue'
import VNextIconButton from './components/ui/VNextIconButton.vue'
import VNextNavigationPane from './components/ui/VNextNavigationPane.vue'
import VNextPaneHeader from './components/ui/VNextPaneHeader.vue'
import VNextPaneResizer from './components/VNextPaneResizer.vue'
import { playerConsoleApi, type PlayerConsoleBootstrap, type PlayerConsoleCloseStatus, type PlayerConsoleInstance, type PlayerConsoleSession } from './playerConsoleApi'
import { sendNativeWindowCommand } from './nativeWindowBridge'

const loading = ref(false)
const creating = ref(false)
const deleting = ref(false)
const pendingDelete = ref<PlayerConsoleInstance | null>(null)
const selectedId = ref('')
const selectedBusy = ref(false)
const globalError = ref('')
const consoleFeedback = ref('')
const pendingConsoleClose = ref(false)
const closingConsole = ref(false)
const closeStatus = ref<PlayerConsoleCloseStatus | null>(null)
const instancePaneWidth = ref(readStoredNumber('easycode.playerConsole.instancePaneWidth', 270, 220, 480))
const detailsOpen = ref(readStoredBoolean('easycode.playerConsole.detailsOpen', true))
const data = ref<PlayerConsoleBootstrap>({ schema_version: 1, installations: [], instances: [] })
const sessions = reactive<Record<string, PlayerConsoleSession>>({})
const readyFrames = new Set<string>()
const pendingRuns = new Set<string>()
let pollTimer = 0
let refreshing = false

const instances = computed(() => data.value.instances)
const enabledInstallations = computed(() => data.value.installations.filter((item) => item.enabled))
const createInstallationId = computed(() => {
    const selected = instances.value.find((item) => item.instance_id === selectedId.value)
    if (selected?.installation_id) return selected.installation_id
    const requested = new URLSearchParams(location.search).get('product_id') || ''
    return enabledInstallations.value.find((item) => item.product_id === requested)?.installation_id
        || enabledInstallations.value[0]?.installation_id
        || ''
})
const selectedSession = computed(() => sessions[selectedId.value] || null)
const selectedInstance = computed(() => instances.value.find((item) => item.instance_id === selectedId.value) || null)
const selectedBootstrapState = computed(() => instances.value.find((item) => item.instance_id === selectedId.value)?.console || null)
const mountedSessions = computed(() => Object.values(sessions).filter((item) => Boolean(item.frame_url)))
const activeCount = computed(() => instances.value.filter((item) => ['queued', 'running', 'paused'].includes(sessionFor(item.instance_id)?.execution?.status || '')).length)

function readStoredNumber(key: string, fallback: number, min: number, max: number) {
    try {
        const value = Number(localStorage.getItem(key))
        return Number.isFinite(value) ? Math.max(min, Math.min(max, value)) : fallback
    } catch { return fallback }
}
function readStoredBoolean(key: string, fallback: boolean) {
    try {
        const value = localStorage.getItem(key)
        return value === null ? fallback : value === 'true'
    } catch { return fallback }
}
function persistConsoleLayout() {
    try {
        localStorage.setItem('easycode.playerConsole.instancePaneWidth', String(instancePaneWidth.value))
        localStorage.setItem('easycode.playerConsole.detailsOpen', String(detailsOpen.value))
    } catch { /* View state persistence is best-effort. */ }
}
function toggleDetails() {
    detailsOpen.value = !detailsOpen.value
    persistConsoleLayout()
}

function sessionFor(instanceId: string) { return sessions[instanceId] || instances.value.find((item) => item.instance_id === instanceId)?.console }
function runStatus(instanceId: string) { return sessionFor(instanceId)?.execution?.status || '' }
function isActive(instanceId: string) { return ['queued', 'running', 'paused'].includes(runStatus(instanceId)) }
function statusTone(status = '') { return ['queued', 'running'].includes(status) ? 'active' : status === 'paused' ? 'paused' : ['failed', 'unreachable'].includes(status) ? 'error' : 'idle' }
function statusLabel(status = '') { return ({ running: '运行中', queued: '准备中', paused: '已暂停', failed: '运行失败', unreachable: '连接中断', stopped: '未连接', ready: '就绪' } as Record<string, string>)[status] || '就绪' }
function instanceSubtitle(instance: PlayerConsoleInstance) {
    const session = sessionFor(instance.instance_id)
    return `${instance.installation?.display_name || 'Player'} · ${statusLabel(session?.status)}`
}
function report(error: unknown) { globalError.value = error instanceof Error ? error.message : String(error) }

function diagnosticSummary(instance: PlayerConsoleInstance) {
    const session = sessionFor(instance.instance_id)
    const execution = session?.execution
    const lines = [
        'EasyCode Player 诊断摘要',
        `时间：${new Date().toLocaleString()}`,
        `产品：${instance.installation?.display_name || instance.product_id}`,
        `版本：${instance.installation?.release_id || '未知'}`,
        `实例：${instance.display_name} (${instance.instance_id})`,
        `实例状态：${statusLabel(session?.status || instance.console?.status)}`,
        `工作进程：PID ${session?.process_id || 0} / 端口 ${session?.port || 0}`,
        `运行：${execution?.execution_id || '无'} / ${execution?.status || '无'}`,
        `错误：${execution?.error || session?.error_message || instance.error_message || '无'}`,
        `错误 ID：${session?.error_id || '无'}`,
    ]
    const recentEvents = (execution?.events || []).slice(-8)
    if (recentEvents.length) {
        lines.push('最近日志：')
        for (const event of recentEvents) {
            lines.push(`${String(event.timestamp || '').slice(11, 19) || '--:--:--'} [${event.category || '运行'}] ${event.message || ''}`)
        }
    }
    return lines.join('\n')
}

async function copyDiagnosticSummary(instance: PlayerConsoleInstance) {
    globalError.value = ''
    try {
        await navigator.clipboard.writeText(diagnosticSummary(instance))
        consoleFeedback.value = '诊断摘要已复制，可直接发给开发者。'
    } catch (error) {
        report(error instanceof Error ? error : new Error('复制诊断摘要失败'))
    }
}

async function downloadDiagnostics(instance: PlayerConsoleInstance) {
    globalError.value = ''
    try {
        const blob = await playerConsoleApi.downloadDiagnostics(instance.instance_id)
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `${instance.display_name}-EasyCode诊断包.zip`
        document.body.appendChild(link)
        link.click()
        link.remove()
        window.setTimeout(() => URL.revokeObjectURL(url), 1_000)
        consoleFeedback.value = '诊断包已生成；请把下载的 ZIP 发给开发者。'
    } catch (error) {
        report(error instanceof Error ? error : new Error('诊断包生成失败'))
    }
}

function copySelectedDiagnostic() {
    if (selectedInstance.value) void copyDiagnosticSummary(selectedInstance.value)
}
function downloadSelectedDiagnostics() {
    if (selectedInstance.value) void downloadDiagnostics(selectedInstance.value)
}

async function load() {
    loading.value = true
    try {
        data.value = await playerConsoleApi.bootstrap()
        if (!selectedId.value && instances.value.length) {
            const requested = new URLSearchParams(location.search).get('product_id') || ''
            selectedId.value = instances.value.find((item) => item.product_id === requested)?.instance_id || instances.value[0].instance_id
            await connect(selectedId.value)
        }
    } catch (error) { report(error) } finally { loading.value = false }
}

async function selectInstance(instanceId: string) {
    selectedId.value = instanceId
    if (!sessions[instanceId]?.frame_url) await connect(instanceId)
}

async function connect(instanceId: string) {
    if (!instanceId) return
    selectedBusy.value = true
    try { sessions[instanceId] = await playerConsoleApi.connect(instanceId) } catch (error) { report(error) } finally { selectedBusy.value = false }
}

async function createInstance() {
    if (!createInstallationId.value) return
    creating.value = true
    try {
        const result = await playerConsoleApi.createInstance(createInstallationId.value)
        await load()
        await selectInstance(result.instance.instance_id)
    } catch (error) { report(error) } finally { creating.value = false }
}

async function deleteInstance() {
    const instance = pendingDelete.value
    if (!instance) return
    deleting.value = true
    const index = instances.value.findIndex((item) => item.instance_id === instance.instance_id)
    const nextId = instances.value[index + 1]?.instance_id || instances.value[index - 1]?.instance_id || ''
    try {
        await playerConsoleApi.deleteInstance(instance.instance_id, instance.revision)
        delete sessions[instance.instance_id]
        selectedId.value = nextId
        pendingDelete.value = null
        await load()
        if (selectedId.value) await connect(selectedId.value)
    } catch (error) { report(error) } finally { deleting.value = false }
}

async function refreshConnected() {
    if (refreshing || document.hidden) return
    refreshing = true
    try {
        await Promise.allSettled(Object.keys(sessions).map(async (instanceId) => { sessions[instanceId] = await playerConsoleApi.state(instanceId) }))
    } finally {
        refreshing = false
    }
}
function handleVisibilityChange() { if (!document.hidden) void refreshConnected() }

async function control(instanceId: string, action: 'pause' | 'resume' | 'stop') {
    try { await playerConsoleApi.control(instanceId, action); sessions[instanceId] = await playerConsoleApi.state(instanceId) } catch (error) { report(error) }
}
async function restart(instanceId: string) {
    try {
        selectedBusy.value = true
        readyFrames.delete(instanceId)
        pendingRuns.delete(instanceId)
        sessions[instanceId] = await playerConsoleApi.restart(instanceId)
    } catch (error) { report(error) } finally { selectedBusy.value = false }
}

function frameFor(instanceId: string) {
    return Array.from(document.querySelectorAll<HTMLIFrameElement>('iframe[data-instance-id]'))
        .find((frame) => frame.dataset.instanceId === instanceId) || null
}
function postRunCommand(instanceId: string) {
    const frame = frameFor(instanceId)
    const frameUrl = sessionFor(instanceId)?.frame_url || ''
    if (!frame?.contentWindow || !frameUrl) return false
    frame.contentWindow.postMessage(
        { event: 'easycode-player-console-command', version: 1, command: 'run' },
        new URL(frameUrl).origin,
    )
    pendingRuns.delete(instanceId)
    consoleFeedback.value = `已启动“${instances.value.find((item) => item.instance_id === instanceId)?.display_name || instanceId}”。`
    return true
}
async function runInstance(instanceId: string) {
    if (isActive(instanceId)) return
    globalError.value = ''
    pendingRuns.add(instanceId)
    try {
        if (!sessionFor(instanceId)?.frame_url) await connect(instanceId)
        await nextTick()
        if (readyFrames.has(instanceId)) postRunCommand(instanceId)
    } catch (error) {
        pendingRuns.delete(instanceId)
        report(error)
    }
}

function instanceIdFromFrameSource(source: MessageEventSource | null) {
    const frame = Array.from(document.querySelectorAll<HTMLIFrameElement>('iframe[data-instance-id]'))
        .find((item) => item.contentWindow === source)
    return frame?.dataset.instanceId || ''
}
function handleFrameMessage(event: MessageEvent) {
    if (!event.data || typeof event.data !== 'object') return
    const instanceId = instanceIdFromFrameSource(event.source)
    const frameUrl = sessionFor(instanceId)?.frame_url || ''
    if (!instanceId || !frameUrl || event.origin !== new URL(frameUrl).origin) return
    const message = event.data as { event?: string; version?: number; action?: string }
    if (message.version !== 1) return
    if (message.event === 'easycode-player-ready') {
        readyFrames.add(instanceId)
        if (pendingRuns.has(instanceId)) postRunCommand(instanceId)
        return
    }
    if (message.event !== 'easycode-player-console-support') return
    const instance = instances.value.find((item) => item.instance_id === instanceId)
    if (!instance) return
    if (message.action === 'copy-summary') void copyDiagnosticSummary(instance)
    else if (message.action === 'download-diagnostics') void downloadDiagnostics(instance)
}

async function completeConsoleClose(stopActive: boolean) {
    if (closingConsole.value) return
    closingConsole.value = true
    globalError.value = ''
    try {
        const result = await playerConsoleApi.prepareClose(stopActive)
        if (!result.ready) {
            closeStatus.value = result
            pendingConsoleClose.value = true
            return
        }
        pendingConsoleClose.value = false
        if (!await sendNativeWindowCommand('close-confirmed')) {
            throw new Error('原生窗口连接不可用，Player 尚未关闭')
        }
    } catch (error) {
        pendingConsoleClose.value = false
        await sendNativeWindowCommand('close-cancelled')
        report(error)
    } finally {
        closingConsole.value = false
    }
}
async function requestConsoleClose() {
    if (closingConsole.value || pendingConsoleClose.value) return
    globalError.value = ''
    try {
        closeStatus.value = await playerConsoleApi.closeStatus()
        if (closeStatus.value.active_count > 0) {
            pendingConsoleClose.value = true
            return
        }
        await completeConsoleClose(false)
    } catch (error) {
        await sendNativeWindowCommand('close-cancelled')
        report(error)
    }
}
function cancelConsoleClose() {
    if (closingConsole.value) return
    pendingConsoleClose.value = false
    closeStatus.value = null
    void sendNativeWindowCommand('close-cancelled')
}
async function confirmConsoleClose() {
    await completeConsoleClose(true)
}

onMounted(async () => {
    window.addEventListener('message', handleFrameMessage)
    await load()
    document.addEventListener('visibilitychange', handleVisibilityChange)
    pollTimer = window.setInterval(refreshConnected, 2000)
})
onBeforeUnmount(() => {
    window.clearInterval(pollTimer)
    window.removeEventListener('message', handleFrameMessage)
    document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<style scoped>
.player-console { width: 100vw; height: 100vh; display: grid; grid-template-rows: var(--app-height-app-header) minmax(0, 1fr); overflow: hidden; background: var(--app-bg-base); color: var(--app-text-regular); font-family: var(--app-font-sans); font-size: var(--app-font-interface); }
.console-brand, .console-summary, .console-title-actions { display: flex; align-items: center; gap: 8px; }
.console-brand svg { color: var(--app-color-primary); }
.console-brand strong { color: var(--app-text-primary); font-size: var(--app-font-page-title); }
.console-brand span, .console-summary { color: var(--app-text-secondary); font-size: var(--app-font-interface); }
.console-summary i, .status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--app-text-disabled); }
.console-summary i.active, .status-dot.active { background: var(--app-color-success); box-shadow: 0 0 0 3px color-mix(in srgb, var(--app-color-success) 18%, transparent); }
.console-layout { min-width: 0; min-height: 0; display: grid; grid-template-columns: var(--instance-pane-width, 270px) 5px minmax(0, 1fr); }
.console-layout.details-collapsed { grid-template-columns: minmax(220px, 1fr); }
.instance-pane { min-height: 0; grid-column: 1; }
.console-pane-resizer { grid-column: 2; grid-row: 1; }
.instance-list { min-height: 0; display: flex; flex: 1; flex-direction: column; gap: 2px; overflow: auto; padding: 6px; }
.instance-row { border-radius: var(--app-radius-sm); overflow: hidden; }
.instance-row.selected { background: var(--app-bg-active); box-shadow: inset 2px 0 var(--app-color-primary); }
.instance-row > button { box-sizing: border-box; width: 100%; min-height: 48px; display: grid; grid-template-columns: 28px minmax(0, 1fr) 12px; align-items: center; gap: 6px; padding: 7px 9px; border: 0; background: transparent; color: inherit; text-align: left; cursor: pointer; }
.instance-row > button:hover { background: var(--app-bg-hover); }
.instance-icon { width: 28px; height: 28px; display: grid; place-items: center; border-radius: var(--app-radius-sm); background: var(--app-bg-raised); color: var(--app-text-secondary); }
.instance-copy { min-width: 0; display: grid; gap: 2px; }
.instance-copy strong, .instance-copy small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.instance-copy strong { color: var(--app-text-primary); font-size: var(--app-font-interface); font-weight: 600; }
.instance-copy small { color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.status-dot.paused { background: var(--app-color-warning); }.status-dot.error { background: var(--app-color-danger); }
.instance-actions { display: grid; gap: 5px; padding: 0 8px 7px 40px; }
.instance-control-actions { min-height: var(--app-control-compact); display: flex; align-items: center; gap: 2px; }
.pane-state, .stage-empty, .stage-loading { min-height: 0; display: flex; flex: 1; flex-direction: column; align-items: center; justify-content: center; gap: 9px; color: var(--app-text-secondary); text-align: center; }
.pane-state svg { width: 20px; }.pane-state small { max-width: 20ch; }
.instance-stage { position: relative; min-width: 0; min-height: 0; grid-column: 3; overflow: hidden; background: var(--app-bg-base); }
.instance-stage iframe { width: 100%; height: 100%; display: block; border: 0; background: var(--app-bg-base); }
.stage-empty strong, .stage-loading strong { color: var(--app-text-primary); font-size: var(--app-font-page-title); }.stage-empty span, .stage-loading span { max-width: 52ch; line-height: 1.6; }
.stage-loading.error { color: var(--app-color-danger); }
.stage-recovery-actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px; }
.console-notice { position: absolute; z-index: 5; top: 10px; left: 50%; min-width: 280px; max-width: min(620px, calc(100% - 28px)); display: grid; grid-template-columns: 18px minmax(0, 1fr) 24px; align-items: center; gap: 7px; padding: 9px 10px; border: 1px solid color-mix(in srgb, var(--app-color-danger) 50%, var(--app-border-default)); border-radius: var(--app-radius-sm); background: var(--app-bg-overlay); color: var(--app-text-primary); box-shadow: var(--app-shadow-overlay); transform: translateX(-50%); }
.console-notice.success { border-color: color-mix(in srgb, var(--app-color-success) 50%, var(--app-border-default)); }
.console-notice.success > svg { color: var(--app-color-success); }
.console-notice > button { width: 24px; height: 24px; display: grid; place-items: center; border: 0; background: transparent; color: var(--app-text-secondary); cursor: pointer; }.console-notice > button:hover { color: var(--app-text-primary); }
.spin { animation: spin .8s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 900px) { .console-layout { --instance-pane-width: 220px; }.console-brand span { display: none; } }
@media (prefers-reduced-motion: reduce) { .spin { animation-duration: 1.6s; } }
</style>
