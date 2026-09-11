<template>
    <div class="publish-backdrop" @mousedown.self="emit('close')">
        <section ref="dialogElement" class="publish-dialog" role="dialog" aria-modal="true" aria-labelledby="publish-title" tabindex="-1" @keydown="trapDialogFocus" @keydown.esc.stop="emit('close')">
            <header>
                <div class="title-copy">
                    <span class="title-icon"><PackageCheck :size="18" aria-hidden="true" /></span>
                    <div><h2 id="publish-title">检查并交付 Player</h2><p>先验证程序、表单、资源与平台闭包，再生成带作者签名的不可变产物。</p></div>
                </div>
                <VNextIconButton label="关闭发布窗口" data-dialog-initial-focus @click="emit('close')"><X /></VNextIconButton>
            </header>

            <div class="publish-content">
                <VNextWorkspaceState v-if="loading" class="publish-state" compact kind="loading" title="正在执行发布前检查"><template #icon><LoaderCircle class="spin" :size="20" /></template></VNextWorkspaceState>
                <VNextWorkspaceState v-else-if="loadError" class="publish-state error" compact kind="error" title="检查没有完成" :description="loadError"><template #icon><CircleAlert :size="20" /></template><template #actions><VNextButton size="compact" @click="refresh">重新检查</VNextButton></template></VNextWorkspaceState>
                <template v-else-if="report">
                    <section :class="['summary-card', report.valid ? 'ready' : 'blocked']">
                        <CircleCheck v-if="report.valid" :size="21" aria-hidden="true" />
                        <CircleAlert v-else :size="21" aria-hidden="true" />
                        <div><strong>{{ report.valid ? '项目可以发布' : `还有 ${report.errors.length} 项必须处理` }}</strong><span>{{ report.valid ? '发布器会生成内容清单、逐文件哈希和 Ed25519 作者签名。' : '当前项目不会生成半成品；处理完错误后重新检查。' }}</span></div>
                    </section>

                    <section class="facts" aria-label="发布摘要">
                        <div><span>项目源码</span><strong>{{ report.source_included ? '包含（已阻止）' : '不进入 Player' }}</strong></div>
                        <div><span>目标平台</span><strong>{{ platformLabel }}</strong></div>
                        <div><span>运行能力</span><strong>{{ report.required_capabilities.length ? `${report.required_capabilities.length} 项` : '纯基础运行' }}</strong></div>
                        <div v-if="hasAndroid"><span>最低 Android 版本</span><strong>Android {{ androidVersionLabel }}（API {{ report.minimum_android_api }}）</strong></div>
                        <div v-if="hasWindows"><span>独立 Windows Player</span><strong :class="{ muted: !readiness?.ready }">{{ readiness?.ready ? '运行时已就绪' : '当前开发环境未构建' }}</strong></div>
                    </section>

                    <details v-if="hasAndroid && report.android_api_requirements.length" class="android-requirements">
                        <summary>查看 Android 版本要求来源 · {{ report.android_api_requirements.length }} 项</summary>
                        <ul><li v-for="(item, index) in report.android_api_requirements" :key="`${item.display_name}-${index}`"><span>{{ item.display_name }}</span><strong>Android {{ androidName(item.minimum_android_api) }}+</strong></li></ul>
                    </details>

                    <VNextPublishUpdates :workspace="workspace" />

                    <section v-if="report.errors.length" class="diagnostic-section">
                        <h3>必须处理</h3>
                        <ul><li v-for="(item, index) in report.errors" :key="`error-${item.code || index}`"><CircleAlert :size="14" /><span><strong v-if="item.code">{{ item.code }}</strong>{{ item.message }}</span></li></ul>
                    </section>
                    <section v-if="report.warnings.length" class="diagnostic-section warnings">
                        <h3>建议检查</h3>
                        <ul><li v-for="(item, index) in report.warnings" :key="`warning-${item.code || index}`"><TriangleAlert :size="14" /><span><strong v-if="item.code">{{ item.code }}</strong>{{ item.message }}</span></li></ul>
                    </section>
                    <section v-if="hasWindows && readiness && !readiness.ready" class="runtime-note">
                        <MonitorCog :size="16" aria-hidden="true" />
                        <div><strong>为什么暂时不能生成独立 Player？</strong><span>当前开发环境缺少预构建的通用 Player 运行时。仍可生成签名 .ecplayer；正式安装版会随 IDE 携带这套运行时。</span><code v-if="readiness.missing.length">{{ readiness.missing[0] }}</code></div>
                    </section>
                    <section v-if="result" class="result-card" aria-live="polite">
                        <CircleCheck :size="17" aria-hidden="true" />
                        <div><strong>{{ resultLabel }}</strong><span>{{ result.path }}</span><small v-if="result.release_id">版本 {{ result.release_id }} · {{ result.signature?.key_id }}</small></div>
                        <VNextIconButton label="复制产物路径" @click="copyResultPath"><Copy /></VNextIconButton>
                    </section>
                    <p v-if="actionError" class="action-error" role="alert">{{ actionError }}</p>
                </template>
            </div>

            <footer>
                <VNextButton :disabled="loading || Boolean(actionBusy)" @click="refresh"><template #icon><RefreshCw /></template>重新检查</VNextButton>
                <span class="footer-spacer"></span>
                <VNextButton :disabled="!report?.valid || Boolean(actionBusy)" @click="publishBundle"><template #icon><FileArchive /></template>生成 .ecplayer</VNextButton>
                <VNextButton v-if="hasAndroid" tone="primary" appearance="solid" :loading="actionBusy === 'android-package'" :disabled="!report?.valid || Boolean(actionBusy && actionBusy !== 'android-package')" @click="packageAndroidPlayer"><template #icon><Package /></template>生成 Android 测试 APK</VNextButton>
                <VNextButton v-if="hasWindows" tone="primary" appearance="solid" :loading="actionBusy === 'package'" :disabled="!report?.valid || !readiness?.ready || Boolean(actionBusy && actionBusy !== 'package')" @click="packagePlayer"><template #icon><Package /></template>生成独立 Player</VNextButton>
            </footer>
        </section>
    </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { CircleAlert, CircleCheck, Copy, FileArchive, LoaderCircle, MonitorCog, Package, PackageCheck, RefreshCw, TriangleAlert, X } from 'lucide-vue-next'
import { vnextApi } from '../api'
import { trapDialogFocus, useDialogFocusReturn } from '../dialogFocus'
import type { WorkspaceIdentity } from '../types'
import VNextPublishUpdates from './VNextPublishUpdates.vue'
import VNextWorkspaceState from './ui/VNextWorkspaceState.vue'
import VNextButton from './ui/VNextButton.vue'
import VNextIconButton from './ui/VNextIconButton.vue'

interface Diagnostic { code?: string; message: string }
interface PublishReport {
    valid: boolean
    errors: Diagnostic[]
    warnings: Diagnostic[]
    source_included: boolean
    required_capabilities: string[]
    supported_platforms: string[]
    android_build_declared: boolean
    minimum_android_api: number
    android_api_requirements: Array<{ display_name: string; minimum_android_api: number; statement_ids?: string[] }>
}
interface Readiness { ready: boolean; missing: string[] }
interface PublishResult {
    path: string
    release_id?: string
    signature?: { key_id?: string }
    kind: 'bundle' | 'package' | 'android-package'
}

const props = defineProps<{ workspace: WorkspaceIdentity }>()
const emit = defineEmits<{ close: [] }>()
const dialogElement = ref<HTMLElement | null>(null)
useDialogFocusReturn(() => true, dialogElement)
const loading = ref(true)
const loadError = ref('')
const report = ref<PublishReport | null>(null)
const readiness = ref<Readiness | null>(null)
const actionBusy = ref<'' | 'bundle' | 'package' | 'android-package'>('')
const actionError = ref('')
const result = ref<PublishResult | null>(null)
const platformNames: Record<string, string> = { windows: 'Windows', android_adb: 'Android ADB', android_local: 'Android 本机' }
const platformLabel = computed(() => report.value?.supported_platforms.map((item) => platformNames[item] || item).join('、') || '无操作目标')
const hasAndroid = computed(() => report.value?.android_build_declared || false)
const hasWindows = computed(() => report.value?.supported_platforms.includes('windows') || false)
const androidNames: Record<number, string> = { 21: '5.0', 22: '5.1', 23: '6.0', 24: '7.0', 25: '7.1', 26: '8.0', 27: '8.1', 28: '9', 29: '10', 30: '11', 31: '12', 32: '12L', 33: '13', 34: '14', 35: '15' }
const androidName = (api: number) => androidNames[api] || `API ${api}`
const androidVersionLabel = computed(() => androidName(report.value?.minimum_android_api || 21))
const resultLabel = computed(() => result.value?.kind === 'android-package' ? 'Android 测试 APK 已生成' : result.value?.kind === 'package' ? '独立 Player 已生成' : '签名项目包已生成')

async function refresh() {
    loading.value = true
    loadError.value = ''
    actionError.value = ''
    result.value = null
    try {
        const [nextReport, nextReadiness] = await Promise.all([
            vnextApi.playerPublishReport(props.workspace),
            vnextApi.playerPackageReadiness(props.workspace),
        ])
        report.value = {
            ...nextReport,
            required_capabilities: nextReport.required_capabilities || [],
            supported_platforms: nextReport.supported_platforms || [],
            android_build_declared: Boolean(nextReport.android_build_declared),
            minimum_android_api: nextReport.minimum_android_api || 21,
            android_api_requirements: nextReport.android_api_requirements || [],
        }
        readiness.value = nextReadiness
    } catch (error) {
        loadError.value = error instanceof Error ? error.message : '发布前检查失败'
    } finally {
        loading.value = false
    }
}

async function publishBundle() {
    if (!report.value?.valid || actionBusy.value) return
    actionBusy.value = 'bundle'
    actionError.value = ''
    try {
        const built = await vnextApi.publishPlayer(props.workspace)
        result.value = { ...built, kind: 'bundle' }
    } catch (error) {
        actionError.value = error instanceof Error ? error.message : '项目包生成失败'
    } finally {
        actionBusy.value = ''
    }
}

async function packagePlayer() {
    if (!report.value?.valid || !readiness.value?.ready || actionBusy.value) return
    actionBusy.value = 'package'
    actionError.value = ''
    try {
        const built = await vnextApi.packagePlayer(props.workspace)
        result.value = { ...built, kind: 'package' }
    } catch (error) {
        actionError.value = error instanceof Error ? error.message : '独立 Player 生成失败'
    } finally {
        actionBusy.value = ''
    }
}

async function packageAndroidPlayer() {
    if (!report.value?.valid || !hasAndroid.value || actionBusy.value) return
    actionBusy.value = 'android-package'
    actionError.value = ''
    try {
        const built = await vnextApi.packageAndroidPlayer(props.workspace)
        result.value = { ...built, path: built.apk_path, kind: 'android-package' }
    } catch (error) {
        actionError.value = error instanceof Error ? error.message : 'Android APK 生成失败'
    } finally {
        actionBusy.value = ''
    }
}

async function copyResultPath() {
    if (!result.value?.path) return
    try { await navigator.clipboard.writeText(result.value.path) }
    catch { actionError.value = '系统没有允许复制，请手动选择产物路径。' }
}

onMounted(refresh)
</script>

<style scoped>
.android-requirements{margin-top:10px;border:1px solid var(--app-border-subtle);border-radius: var(--app-radius-md);background:var(--app-bg-panel);color:var(--app-text-secondary);font-size: var(--app-font-caption)}.android-requirements summary{padding:10px 12px;cursor:pointer;color:var(--app-text-regular)}.android-requirements ul{margin:0;padding:0 12px 8px;list-style:none}.android-requirements li{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-top:1px solid var(--app-border-subtle)}.android-requirements strong{color:var(--app-text-primary);font-weight:550;white-space:nowrap}
.publish-backdrop{position:fixed;inset:0;z-index:120;background:rgba(5,5,4,.7);display:grid;place-items:center;padding:20px}.publish-dialog{width:min(760px,100%);max-height:min(820px,calc(100vh - 32px));display:grid;grid-template-rows:auto minmax(0,1fr) auto;border:1px solid var(--app-overlay-border);border-radius:var(--app-radius-lg);background:var(--app-bg-raised);box-shadow:var(--app-shadow-lg);overflow:hidden}.publish-dialog>header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:17px 18px;border-bottom:1px solid var(--app-border-subtle)}.title-copy{display:flex;align-items:flex-start;gap:11px}.title-icon{width:34px;height: var(--app-control-default);flex:0 0 auto;display:grid;place-items:center;border-radius: var(--app-radius-md);background:var(--app-color-primary-dim);color:var(--app-color-primary)}h2{margin:0;color:var(--app-text-primary);font-size: var(--app-font-page-title);font-weight:600}header p{margin:4px 0 0;color:var(--app-text-secondary);font-size: var(--app-font-compact);line-height:1.5}.icon-button{width:28px;height: var(--app-control-compact);display:grid;place-items:center;border:0;border-radius: var(--app-radius-sm);background:transparent;color:var(--app-text-secondary)}.icon-button:hover,.icon-button:focus-visible{background:var(--app-bg-hover);color:var(--app-text-primary);outline:0;box-shadow:var(--focus-ring)}.publish-content{min-height:260px;overflow:auto;padding:16px 18px}.publish-state{min-height:260px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;color:var(--app-text-secondary);text-align:center}.publish-state.error{color:var(--app-color-danger)}.publish-state button{height: var(--app-control-compact);margin-top:5px;padding:0 10px;border:1px solid var(--app-border-default);border-radius: var(--app-radius-sm);background:transparent;color:inherit}.summary-card{display:flex;align-items:flex-start;gap:10px;padding:13px 14px;border:1px solid var(--app-border-subtle);border-radius:9px;background:var(--app-bg-panel)}.summary-card.ready>svg{color:var(--app-color-success)}.summary-card.blocked>svg{color:var(--app-color-danger)}.summary-card div{display:flex;flex-direction:column;gap:3px}.summary-card strong{color:var(--app-text-primary);font-size: var(--app-font-body)}.summary-card span{color:var(--app-text-secondary);font-size: var(--app-font-caption);line-height:1.5}.facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;margin-top:14px;overflow:hidden;border:1px solid var(--app-border-subtle);border-radius: var(--app-radius-md);background:var(--app-border-subtle)}.facts div{min-height:54px;display:flex;flex-direction:column;justify-content:center;gap:3px;padding:9px 12px;background:var(--app-bg-panel)}.facts span{color:var(--app-text-muted);font-size: var(--app-font-caption)}.facts strong{color:var(--app-text-primary);font-size: var(--app-font-compact);font-weight:550}.facts strong.muted{color:var(--app-text-secondary)}.diagnostic-section{margin-top:16px}.diagnostic-section h3{margin:0 0 7px;color:var(--app-color-danger);font-size: var(--app-font-caption);font-weight:600}.diagnostic-section.warnings h3{color:var(--app-color-warning)}.diagnostic-section ul{margin:0;padding:0;list-style:none}.diagnostic-section li{display:flex;align-items:flex-start;gap:8px;padding:8px 9px;border-bottom:1px solid var(--app-border-subtle);color:var(--app-text-regular);font-size: var(--app-font-caption);line-height:1.5}.diagnostic-section li>svg{flex:0 0 auto;margin-top:1px;color:var(--app-color-danger)}.diagnostic-section.warnings li>svg{color:var(--app-color-warning)}.diagnostic-section li strong{margin-right:7px;color:var(--app-text-muted);font-family:var(--app-font-mono)}.runtime-note,.result-card{display:flex;align-items:flex-start;gap:9px;margin-top:15px;padding:11px 12px;border:1px solid var(--app-border-subtle);border-radius: var(--app-radius-md);background:var(--app-bg-panel)}.runtime-note>svg{color:var(--app-text-secondary)}.runtime-note div,.result-card div{min-width:0;display:flex;flex:1;flex-direction:column;gap:3px}.runtime-note strong,.result-card strong{color:var(--app-text-primary);font-size: var(--app-font-caption)}.runtime-note span,.result-card span,.result-card small{color:var(--app-text-secondary);font-size: var(--app-font-caption);line-height:1.5;overflow-wrap:anywhere}.runtime-note code{margin-top:3px;color:var(--app-text-muted);font-size: var(--app-font-caption);overflow-wrap:anywhere}.result-card{border-color:color-mix(in srgb,var(--app-color-success) 35%,var(--app-border-subtle))}.result-card>svg{color:var(--app-color-success)}.result-card button{width:28px;height: var(--app-control-compact);display:grid;place-items:center;border:0;border-radius: var(--app-radius-sm);background:transparent;color:var(--app-text-secondary)}.result-card button:hover{background:var(--app-bg-hover);color:var(--app-text-primary)}.action-error{margin:12px 0 0;color:var(--app-color-danger);font-size: var(--app-font-caption)}.publish-dialog>footer{display:flex;align-items:center;gap:8px;padding:12px 18px;border-top:1px solid var(--app-border-subtle)}.footer-spacer{flex:1}.publish-dialog footer button{height: var(--app-control-default);display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:0 11px;border-radius: var(--app-radius-md);font:inherit}.secondary{border:1px solid var(--app-border-default);background:transparent;color:var(--app-text-regular)}.primary{border:1px solid var(--app-color-primary);background:var(--app-color-primary);color:var(--app-color-on-primary)}button:disabled{opacity:.4;cursor:default}.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:620px){.publish-backdrop{padding:8px}.facts{grid-template-columns:1fr}.publish-dialog>footer{flex-wrap:wrap}.footer-spacer{display:none}.publish-dialog>footer button{flex:1}.publish-dialog>footer .secondary:first-child{flex-basis:100%}}
</style>
