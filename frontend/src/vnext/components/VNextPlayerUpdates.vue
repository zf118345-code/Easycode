<template>
    <section class="player-updates" aria-label="在线更新">
        <header>
            <span><RefreshCcwDot :size="13" />在线更新</span>
            <button type="button" :disabled="Boolean(busy)" title="刷新本机更新状态" @click="refresh()"><RefreshCw :size="12" :class="{ spin: busy === 'refresh' }" /></button>
        </header>
        <div v-if="blockingPolicy" class="policy-block" role="alert">
            <ShieldAlert :size="14" /><div><strong>需要更新后才能开始新任务</strong><p>{{ blockingPolicy.message }}</p><small>已运行或主动暂停的任务不会被中断。</small></div>
        </div>
        <details v-for="[domainId, domain] in domainEntries" :key="domainId" class="update-domain">
            <summary>
                <span>{{ domainLabel(domainId) }}</span>
                <em :class="domain.state">{{ stateLabel(domain.state) }}</em>
            </summary>
            <div class="domain-body">
                <p class="version" :title="domain.current_release_id">当前序号 {{ domain.current_release_sequence }} · {{ compactId(domain.current_release_id) }}</p>
                <p v-if="domain.selected_release" class="available">可用 {{ domain.selected_release.display_version }} · 序号 {{ domain.selected_release.release_sequence }}</p>
                <p v-if="domain.last_error" class="domain-error" role="alert">{{ domain.last_error.message }}</p>
                <p v-if="domain.state === 'waiting_safe_point'" class="domain-note">已验证并暂存；任务、暂停现场或未提交表单结束后自动允许切换。</p>
                <p v-if="domain.state === 'awaiting_platform_install'" class="domain-note">{{ domain.platform_message || '等待系统安装边界。当前宿主不可用时会保留旧版本并明确显示原因。' }}</p>
                <div class="update-actions">
                    <button type="button" :disabled="Boolean(busy)" @click="check(domainId)"><Search :size="12" />手动检查</button>
                    <button v-if="domain.state === 'available'" type="button" :disabled="Boolean(busy)" @click="download(domainId)"><Download :size="12" />下载</button>
                    <button v-if="['staged','waiting_safe_point','awaiting_platform_install','failed'].includes(domain.state) && domain.selected_release" type="button" :disabled="Boolean(busy)" @click="apply(domainId)"><PackageOpen :size="12" />{{ runtimeActive ? '安全后应用' : '应用' }}</button>
                </div>
                <div class="preferences">
                    <label><input v-model="domain.preferences.automatic_check" type="checkbox" :disabled="Boolean(busy)" @change="savePreferences(domainId)" /><span>自动检查普通更新</span></label>
                    <label><input v-model="domain.preferences.automatic_download" type="checkbox" :disabled="Boolean(busy)" @change="savePreferences(domainId)" /><span>自动下载</span></label>
                    <label><input v-model="domain.preferences.automatic_apply" type="checkbox" :disabled="Boolean(busy)" @change="savePreferences(domainId)" /><span>空闲时自动应用</span></label>
                </div>
                <p v-if="domain.required_policy_capability" class="policy-disclosure">关闭普通检查不会关闭已披露的低频签名最低版本策略检查；它不下载或安装文件。</p>
                <details class="group-code" @toggle="loadGroupCode(domainId, $event)">
                    <summary>测试分组码</summary>
                    <div v-if="groupCodes[domainId]">
                        <code :title="groupCodes[domainId]">{{ groupCodes[domainId] }}</code>
                        <button type="button" title="复制分组码" @click="copyGroup(domainId)"><Copy :size="12" /></button>
                        <button type="button" @click="resetGroup(domainId)"><RotateCcw :size="12" />重置</button>
                    </div>
                    <small>重置会退出现有作者白名单，并改变后续稳定灰度分组；不会降级已安装版本。</small>
                </details>
            </div>
        </details>
        <p v-if="error" class="panel-error" role="alert">{{ error }}</p>
        <small class="privacy">更新请求不携带分组码、日志、截图、运行数据或硬件身份。</small>
        <VNextConfirmDialog
            :open="Boolean(resetCandidate)"
            title="重置测试分组码？"
            message="重置后会退出当前作者白名单，并改变后续稳定灰度分组；已经安装的版本不会降级。"
            confirm-label="重置分组码"
            tone="warning"
            @cancel="resetCandidate = null"
            @confirm="confirmResetGroup"
        />
        <VNextConfirmDialog
            :open="Boolean(applyCandidate)"
            title="准备安装 Player 更新？"
            message="更新会先在后台完整验证并暂存。准备完成后，请关闭当前 Player；EasyCode 会替换整套应用、启动新版本，并在启动失败时自动恢复旧版本。正在运行或暂停的任务不会被强行中断。"
            confirm-label="准备安装"
            tone="warning"
            @cancel="applyCandidate = null"
            @confirm="confirmApplicationApply"
        />
    </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, toRaw, watch } from 'vue'
import { Copy, Download, PackageOpen, RefreshCcwDot, RefreshCw, RotateCcw, Search, ShieldAlert } from 'lucide-vue-next'
import { vnextApi } from '../playerApi'
import type { PlayerUpdateDomainStatus, PlayerUpdatesResponse } from '../types'
import VNextConfirmDialog from './VNextConfirmDialog.vue'

type DomainId = 'player_application' | 'project_content'
const props = defineProps<{ initial: PlayerUpdatesResponse; runtimeActive: boolean; uncommittedDraft: boolean }>()
const emit = defineEmits<{ contentApplied: [] }>()
// Vue exposes object props as reactive proxies. Android WebView follows the
// browser structured-clone contract and rejects proxies with DataCloneError.
// Clone the raw transport document so the update panel cannot disappear
// during setup merely because its parent made the bootstrap response reactive.
const updates = ref<PlayerUpdatesResponse>(structuredClone(toRaw(props.initial)))
const busy = ref(''), error = ref('')
const groupCodes = ref<Partial<Record<DomainId, string>>>({})
const resetCandidate = ref<DomainId | null>(null)
const applyCandidate = ref<DomainId | null>(null)
let statusTimer: number | null = null
let safeTimer: number | null = null
const blockingPolicy = computed(() => Object.values(updates.value.domains).find((item) => item?.policy_block)?.policy_block || null)
const domainEntries = computed(() => Object.entries(updates.value.domains).filter(
    (entry): entry is [DomainId, PlayerUpdateDomainStatus] => Boolean(entry[1]),
))
function domainLabel(value: string | number) { return value === 'project_content' ? '项目内容' : 'Player 应用' }
function compactId(value: string) { return value.length > 24 ? `${value.slice(0, 11)}…${value.slice(-8)}` : value }
function stateLabel(value: string) {
    return ({ idle: '已验证/空闲', checking: '检查中', available: '有可用版本', downloading: '下载中', staged: '已暂存', waiting_safe_point: '等待安全点', awaiting_platform_install: '等待系统安装', applying: '应用中', verifying: '验证中', complete: '已完成', failed: '失败', rolled_back: '已回滚' } as Record<string, string>)[value] || value
}
async function refresh(silent = false) {
    if (!silent) busy.value = 'refresh'
    try { updates.value = await vnextApi.playerUpdateStatus(); error.value = '' }
    catch (value) { if (!silent) error.value = value instanceof Error ? value.message : '无法读取更新状态' }
    finally { if (!silent) busy.value = '' }
}
async function action(label: string, work: () => Promise<unknown>) {
    if (busy.value) return
    busy.value = label; error.value = ''
    try { await work(); await refresh(true) }
    catch (value) { error.value = value instanceof Error ? value.message : '更新操作失败' }
    finally { busy.value = '' }
}
function check(domain: DomainId) { return action('check', () => vnextApi.playerUpdateCheck(domain)) }
function download(domain: DomainId) { return action('download', () => vnextApi.playerUpdateDownload(domain)) }
function apply(domain: DomainId) {
    if (domain === 'player_application') {
        applyCandidate.value = domain
        return Promise.resolve()
    }
    return applyNow(domain)
}
function applyNow(domain: DomainId) {
    return action('apply', async () => {
        const result = await vnextApi.playerUpdateApply(domain) as { status?: { state?: string } }
        if (domain === 'project_content' && result.status?.state === 'complete') emit('contentApplied')
    })
}
async function confirmApplicationApply() {
    const domain = applyCandidate.value
    applyCandidate.value = null
    if (domain) await applyNow(domain)
}
async function savePreferences(domain: DomainId) {
    const value = updates.value.domains[domain]
    if (!value) return
    await action('preferences', () => vnextApi.savePlayerUpdatePreferences(domain, value.preferences))
}
async function loadGroupCode(domain: DomainId, event: Event) {
    if (!(event.currentTarget as HTMLDetailsElement).open || groupCodes.value[domain]) return
    try { groupCodes.value[domain] = (await vnextApi.playerUpdateGroupCode(domain)).group_code }
    catch (value) { error.value = value instanceof Error ? value.message : '无法读取测试分组码' }
}
async function copyGroup(domain: DomainId) {
    const value = groupCodes.value[domain]
    if (!value) return
    try { await navigator.clipboard.writeText(value) }
    catch { error.value = '系统没有允许复制，请手动选择分组码。' }
}
function resetGroup(domain: DomainId) {
    resetCandidate.value = domain
}
async function confirmResetGroup() {
    const domain = resetCandidate.value
    resetCandidate.value = null
    if (!domain) return
    await action('group', async () => { groupCodes.value[domain] = (await vnextApi.resetPlayerUpdateGroup(domain)).group_code })
}
watch(
    () => [props.runtimeActive, props.uncommittedDraft] as const,
    () => {
        if (safeTimer !== null) window.clearTimeout(safeTimer)
        safeTimer = window.setTimeout(() => {
            void vnextApi.markPlayerUpdateSafePoint(props.runtimeActive, props.uncommittedDraft).catch(() => undefined)
        }, 180)
    },
    { immediate: true },
)
onMounted(() => { statusTimer = window.setInterval(() => { void refresh(true) }, 30_000) })
onBeforeUnmount(() => {
    if (statusTimer !== null) window.clearInterval(statusTimer)
    if (safeTimer !== null) window.clearTimeout(safeTimer)
})
</script>

<style scoped>
.player-updates{display:flex;flex-direction:column;gap:7px;margin-bottom:12px;padding:10px;border:1px solid var(--app-border-subtle);border-radius: var(--app-radius-lg);background:var(--app-bg-input)}.player-updates>header{display:flex;align-items:center;justify-content:space-between}.player-updates>header span{display:flex;align-items:center;gap:6px;color:var(--app-text-primary);font-size: var(--app-font-caption);font-weight:600}.player-updates>header button,.update-actions button,.group-code button{min-height:25px;display:inline-flex;align-items:center;justify-content:center;gap:4px;padding:0 6px;border:1px solid var(--app-border-default);border-radius: var(--app-radius-sm);background:transparent;color:var(--app-text-secondary);font:inherit;font-size: var(--app-font-caption)}.update-domain{border-top:1px solid var(--app-border-subtle)}.update-domain>summary{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 1px;list-style:none;cursor:pointer}.update-domain>summary::-webkit-details-marker,.group-code>summary::-webkit-details-marker{display:none}.update-domain>summary span{color:var(--app-text-regular);font-size: var(--app-font-caption)}.update-domain>summary em{color:var(--app-text-muted);font-size: var(--app-font-caption);font-style:normal}.update-domain>summary em.available{color:var(--app-color-primary)}.update-domain>summary em.failed,.update-domain>summary em.rolled_back{color:var(--app-color-danger)}.domain-body{display:flex;flex-direction:column;gap:7px;padding:0 1px 9px}.domain-body p{margin:0;color:var(--app-text-secondary);font-size: var(--app-font-caption);line-height:1.45;overflow-wrap:anywhere}.domain-body .available{color:var(--app-color-primary)}.domain-body .domain-error,.panel-error{color:var(--app-color-danger)}.domain-note,.policy-disclosure{padding:6px 7px;border-radius: var(--app-radius-sm);background:var(--app-bg-panel)}.update-actions{display:flex;flex-wrap:wrap;gap:5px}.preferences{display:flex;flex-direction:column;gap:0;padding-top:3px}.preferences label{min-height:var(--app-control-default);display:flex;align-items:center;gap:6px;color:var(--app-text-secondary);font-size: var(--app-font-caption);cursor:pointer}.group-code{padding-top:4px;border-top:1px solid var(--app-border-subtle)}.group-code>summary{color:var(--app-text-secondary);font-size: var(--app-font-caption);cursor:pointer}.group-code>div{display:grid;grid-template-columns:minmax(0,1fr) 27px auto;gap:5px;margin-top:6px}.group-code code{min-width:0;overflow:hidden;padding:5px;border-radius: var(--app-radius-sm);background:var(--app-bg-panel);color:var(--app-text-muted);font-size: var(--app-font-caption);text-overflow:ellipsis;white-space:nowrap}.group-code small,.privacy{color:var(--app-text-muted);font-size: var(--app-font-caption);line-height:1.4}.policy-block{display:flex;align-items:flex-start;gap:7px;padding:8px;border-radius: var(--app-radius-sm);background:color-mix(in srgb,var(--app-color-warning) 9%,transparent);color:var(--app-color-warning)}.policy-block div{min-width:0}.policy-block strong{font-size: var(--app-font-caption)}.policy-block p,.policy-block small{margin:3px 0 0;color:color-mix(in srgb,var(--app-color-warning) 78%,var(--app-text-primary));font-size: var(--app-font-caption);line-height:1.4}.panel-error{margin:0;font-size: var(--app-font-caption);line-height:1.4}button:not(:disabled):hover{background:var(--app-bg-hover);color:var(--app-text-primary)}button:disabled{opacity:.45}button:focus-visible,summary:focus-visible,input:focus-visible{outline:0;box-shadow:var(--focus-ring)}.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
</style>
