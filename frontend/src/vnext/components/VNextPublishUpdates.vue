<template>
    <details class="update-author" :open="configurationEnabled">
        <summary>
            <span><CloudCog :size="15" />签名在线维护</span>
            <em>{{ configurationEnabled ? '已启用' : '关闭' }}</em>
        </summary>
        <div v-if="loading" class="update-loading"><LoaderCircle :size="14" class="spin" />读取更新配置…</div>
        <div v-else-if="error" class="update-error" role="alert">
            <CircleAlert :size="14" /><span>{{ error }}</span><button type="button" @click="load">重试</button>
        </div>
        <div v-else-if="configuration" class="update-body">
            <p>任务执行仍可离线。启用后，Player 只访问这里固定并签名的 Feed；不会上传日志、截图、运行结果或设备身份。</p>
            <div class="domain-switches">
                <label v-for="domain in domainNames" :key="domain.id">
                    <input v-model="configuration.domains[domain.id].enabled" type="checkbox" @change="prepareDomain(domain.id)" />
                    <span><strong>{{ domain.label }}</strong><small>{{ domain.description }}</small></span>
                </label>
            </div>
            <template v-for="domain in domainNames" :key="`${domain.id}-settings`">
                <section v-if="configuration.domains[domain.id].enabled" class="domain-settings">
                    <header><strong>{{ domain.label }}</strong><span>{{ configuration.domains[domain.id].pinned_root ? '信任根已固定' : '等待初始化仓库' }}</span></header>
                    <div class="field-grid">
                        <label class="inline-field">产品 ID<input v-model.trim="configuration.domains[domain.id].product_id" maxlength="256" /></label>
                        <label class="inline-field">通道<select v-model="configuration.domains[domain.id].channel"><option value="stable">稳定</option><option value="test">作者测试</option></select></label>
                        <label class="wide inline-field">静态 HTTPS Feed<input v-model.trim="configuration.domains[domain.id].feed_base_url" maxlength="2048" placeholder="https://updates.example.com/feed/…" /></label>
                        <label class="wide inline-field">本机 Feed 目录<input v-model.trim="repositoryRoots[domain.id]" maxlength="32767" placeholder="D:\EasyCodeFeed" /></label>
                    </div>
                    <label class="policy-toggle"><input v-model="configuration.domains[domain.id].required_policy_capability" type="checkbox" /><span>允许独立低频检查签名最低版本策略</span></label>
                    <div class="domain-actions">
                        <button type="button" :disabled="busy || !repositoryRoots[domain.id]" @click="initialize(domain.id)"><KeyRound :size="13" />初始化签名 Feed</button>
                        <span v-if="configuration.domains[domain.id].provider === 'easycode_hosted'">当前参考构建未连接官方作者账号；不会伪造托管状态。</span>
                    </div>
                </section>
            </template>
            <section v-if="configuration.domains.project_content.enabled && configuration.domains.project_content.pinned_root" class="release-tools">
                <header><strong>发布项目内容</strong><span>只允许 ECIR、资源、Player Schema 与兼容数据</span></header>
                <div class="field-grid compact">
                    <label class="inline-field">显示版本<input v-model.trim="releaseVersion" maxlength="120" placeholder="1.1.0" /></label>
                    <label class="inline-field">目标<select v-model="releaseTarget"><option value="windows:x86_64">Windows x86_64</option><option value="windows:arm64">Windows arm64</option><option value="android:arm64-v8a">Android arm64-v8a</option></select></label>
                    <label class="wide multiline-field">发布说明<textarea v-model.trim="releaseNotes" maxlength="4000" rows="3" placeholder="说明这次内容变化" /></label>
                </div>
                <div class="domain-actions"><button type="button" :disabled="busy || !releaseVersion || !repositoryRoots.project_content" @click="publishContent"><UploadCloud :size="13" />构建并发布不可变版本</button></div>
                <div v-if="publishedReleaseId" class="rollout-tools">
                    <code :title="publishedReleaseId">{{ publishedReleaseId }}</code>
                    <label class="inline-field rollout-percent">稳定通道比例 <input v-model.number="rolloutPercent" type="number" min="0" max="100" step="1" /><span>%</span></label>
                    <label class="multiline-field">白名单分组码<textarea v-model="whitelistCodes" rows="2" placeholder="每行一个；原始值只在本机哈希"></textarea></label>
                    <button type="button" :disabled="busy" @click="publishRollout"><Gauge :size="13" />发布灰度策略</button>
                    <div v-if="configuration.domains.project_content.required_policy_capability && rolloutPercent === 100" class="required-policy">
                        <strong>最低版本策略</strong>
                        <div class="field-grid compact">
                            <label class="inline-field">生效时间<input v-model="effectiveAt" type="datetime-local" /></label>
                            <label class="inline-field">宽限截止<input v-model="graceDeadline" type="datetime-local" /></label>
                            <label class="wide multiline-field">原因<textarea v-model.trim="requiredReason" maxlength="500" rows="2" placeholder="说明为何旧版本不能再开始新任务" /></label>
                        </div>
                        <button type="button" class="warning" :disabled="busy || !effectiveAt || !graceDeadline || !requiredReason" @click="publishRequired"><ShieldAlert :size="13" />发布签名最低版本策略</button>
                    </div>
                </div>
            </section>
            <p v-if="notice" class="update-notice" aria-live="polite">{{ notice }}</p>
            <p v-if="actionError" class="update-error-text" role="alert">{{ actionError }}</p>
            <footer><button type="button" class="save" :disabled="busy" @click="save"><Save :size="13" />保存更新配置</button></footer>
        </div>
    </details>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { CircleAlert, CloudCog, Gauge, KeyRound, LoaderCircle, Save, ShieldAlert, UploadCloud } from 'lucide-vue-next'
import { vnextApi } from '../api'
import type { AuthorUpdateConfiguration, WorkspaceIdentity } from '../types'

const props = defineProps<{ workspace: WorkspaceIdentity }>()
const loading = ref(true), error = ref(''), actionError = ref(''), notice = ref(''), busy = ref(false)
const configuration = ref<AuthorUpdateConfiguration | null>(null)
const repositoryRoots = reactive({ player_application: '', project_content: '' })
const releaseVersion = ref(''), releaseNotes = ref(''), releaseTarget = ref<'windows:x86_64' | 'windows:arm64' | 'android:arm64-v8a'>('windows:x86_64')
const publishedReleaseId = ref(''), rolloutPercent = ref(0), whitelistCodes = ref('')
const effectiveAt = ref(''), graceDeadline = ref(''), requiredReason = ref('')
const domainNames = [
    { id: 'player_application' as const, label: 'Player 应用', description: 'Runtime、宿主、权限、ABI 与 APK/Windows 包' },
    { id: 'project_content' as const, label: '项目内容', description: '签名 ECIR、资源和 Player 表单' },
]
const configurationEnabled = computed(() => Boolean(configuration.value && Object.values(configuration.value.domains).some((item) => item.enabled)))

function prepareDomain(domain: 'player_application' | 'project_content') {
    const value = configuration.value?.domains[domain]
    if (!value) return
    if (value.enabled) {
        value.product_id ||= `${props.workspace.project_id}.${domain}`
        value.provider = 'self_hosted'
    } else {
        value.product_id = ''
        value.feed_base_url = ''
        value.required_policy_capability = false
        value.pinned_root = null
    }
}
async function load() {
    loading.value = true; error.value = ''
    try { configuration.value = (await vnextApi.updateConfiguration(props.workspace)).configuration }
    catch (value) { error.value = value instanceof Error ? value.message : '无法读取更新配置' }
    finally { loading.value = false }
}
async function save() {
    if (!configuration.value || busy.value) return
    busy.value = true; actionError.value = ''; notice.value = ''
    domainNames.forEach((item) => prepareDomain(item.id))
    try {
        configuration.value = (await vnextApi.saveUpdateConfiguration(props.workspace, configuration.value)).configuration
        notice.value = configurationEnabled.value ? '更新配置已保存。启用的域会进入下一次签名 Player 闭包。' : '在线更新已关闭；下一次发布不会携带端点、调度器或入口。'
    } catch (value) { actionError.value = value instanceof Error ? value.message : '更新配置保存失败' }
    finally { busy.value = false }
}
async function initialize(domain: 'player_application' | 'project_content') {
    if (!configuration.value || busy.value) return
    busy.value = true; actionError.value = ''; notice.value = ''
    try {
        domainNames.forEach((item) => prepareDomain(item.id))
        configuration.value = (
            await vnextApi.saveUpdateConfiguration(props.workspace, configuration.value)
        ).configuration
        const result = await vnextApi.initializeUpdateRepository(props.workspace, { domain, repository_root: repositoryRoots[domain] })
        configuration.value.domains[domain].pinned_root = result.pinned_root as Record<string, unknown>
        notice.value = `${domain === 'project_content' ? '项目内容' : 'Player 应用'} Feed 已初始化；私钥只保存在本机安全存储。`
    } catch (value) { actionError.value = value instanceof Error ? value.message : '签名 Feed 初始化失败' }
    finally { busy.value = false }
}
async function publishContent() {
    if (busy.value) return
    busy.value = true; actionError.value = ''; notice.value = ''
    const [platform, architecture] = releaseTarget.value.split(':') as ['windows' | 'android', string]
    try {
        const result = await vnextApi.publishProjectContentUpdate(props.workspace, { repository_root: repositoryRoots.project_content, platform, architecture, display_version: releaseVersion.value, notes: releaseNotes.value })
        const release = result.release as { release_id?: string }
        publishedReleaseId.value = String(release?.release_id || '')
        notice.value = '不可变内容版本已签名并写入静态 Feed；尚未命中任何终端，需继续发布灰度策略。'
    } catch (value) { actionError.value = value instanceof Error ? value.message : '项目内容发布失败' }
    finally { busy.value = false }
}
async function publishRollout() {
    if (!publishedReleaseId.value || busy.value) return
    busy.value = true; actionError.value = ''
    try {
        await vnextApi.setUpdateRollout(props.workspace, {
            domain: 'project_content', repository_root: repositoryRoots.project_content, release_id: publishedReleaseId.value,
            channel: 'stable', percent_bps: Math.round(rolloutPercent.value * 100),
            whitelist_codes: whitelistCodes.value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean),
            whitelist_hashes: [], paused: false, rollout_id: '',
        })
        notice.value = `稳定通道策略已发布：${rolloutPercent.value}%${whitelistCodes.value.trim() ? '，并包含本机哈希白名单' : ''}。`
    } catch (value) { actionError.value = value instanceof Error ? value.message : '灰度策略发布失败' }
    finally { busy.value = false }
}
async function publishRequired() {
    if (busy.value) return
    busy.value = true; actionError.value = ''
    const [platform, architecture] = releaseTarget.value.split(':')
    try {
        await vnextApi.setRequiredUpdatePolicy(props.workspace, {
            domain: 'project_content', repository_root: repositoryRoots.project_content, release_id: publishedReleaseId.value,
            effective_at: new Date(effectiveAt.value).toISOString(), grace_deadline: new Date(graceDeadline.value).toISOString(),
            reason: requiredReason.value, platform_targets: [`${platform}:${architecture}`],
        })
        notice.value = '签名最低版本策略已发布。它只会在终端取得策略且宽限结束后阻止新任务。'
    } catch (value) { actionError.value = value instanceof Error ? value.message : '最低版本策略发布失败' }
    finally { busy.value = false }
}
onMounted(load)
</script>

<style scoped>
.update-author{margin-top:16px;border-top:1px solid var(--app-border-subtle);color:var(--app-text-regular)}summary{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:13px 2px;cursor:pointer;list-style:none}summary::-webkit-details-marker{display:none}summary span{display:flex;align-items:center;gap:7px;color:var(--app-text-primary);font-size: var(--app-font-compact);font-weight:600}summary em{color:var(--app-text-muted);font-size: var(--app-font-caption);font-style:normal}.update-body{display:flex;flex-direction:column;gap:12px;padding-bottom:4px}.update-body>p{max-width:70ch;margin:0;color:var(--app-text-secondary);font-size: var(--app-font-caption);line-height:1.55}.domain-switches{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.domain-switches>label{display:flex;align-items:flex-start;gap:8px;padding:9px 10px;border-radius: var(--app-radius-md);background:var(--app-bg-panel);cursor:pointer}.domain-switches span{min-width:0;display:flex;flex-direction:column;gap:2px}.domain-switches strong{color:var(--app-text-primary);font-size: var(--app-font-caption)}.domain-switches small{color:var(--app-text-secondary);font-size: var(--app-font-caption);line-height:1.4}.domain-settings,.release-tools{padding:11px 12px;border:1px solid var(--app-border-subtle);border-radius: var(--app-radius-lg)}.domain-settings>header,.release-tools>header{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px}.domain-settings header strong,.release-tools header strong{color:var(--app-text-primary);font-size: var(--app-font-caption)}.domain-settings header span,.release-tools header span{color:var(--app-text-muted);font-size: var(--app-font-caption);text-align:end}.field-grid{display:grid;grid-template-columns:minmax(0,1fr) 190px;gap:8px}.field-grid.compact{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.field-grid label,.rollout-tools>label{min-width:0;color:var(--app-text-secondary);font-size: var(--app-font-caption)}.field-grid label.inline-field,.rollout-tools>label.inline-field{min-height:var(--app-control-default);display:grid;grid-template-columns:minmax(76px,104px) minmax(0,1fr);align-items:center;gap:8px}.field-grid.compact label.inline-field{grid-template-columns:minmax(58px,76px) minmax(0,1fr)}.field-grid label.multiline-field,.rollout-tools>label.multiline-field{display:flex;flex-direction:column;gap:var(--app-form-label-control-gap)}.field-grid .wide{grid-column:1/-1}.field-grid input,.field-grid select,.field-grid textarea,.rollout-tools input,.rollout-tools textarea{min-width:0;height:var(--app-control-default);padding:0 8px;border:1px solid var(--app-border-default);border-radius: var(--app-radius-sm);background:var(--app-bg-input);color:var(--app-text-primary);font:inherit}.field-grid textarea,.rollout-tools textarea{height:auto;min-height:64px;padding-block:7px;resize:vertical}.rollout-tools>.rollout-percent{grid-template-columns:minmax(108px,132px) minmax(68px,100px) auto;justify-content:start}.rollout-percent>span{display:block;color:var(--app-text-secondary);font-weight:400}.policy-toggle{display:flex;align-items:center;gap:7px;margin-top:9px;color:var(--app-text-secondary);font-size: var(--app-font-caption)}.domain-actions{display:flex;align-items:center;gap:9px;margin-top:10px}.domain-actions span{color:var(--app-color-warning);font-size: var(--app-font-caption)}.domain-actions button,.rollout-tools button,.update-error button,.update-body footer button{min-height: var(--app-control-compact);display:inline-flex;align-items:center;justify-content:center;gap:5px;padding:0 9px;border:1px solid var(--app-border-default);border-radius: var(--app-radius-sm);background:transparent;color:var(--app-text-regular);font:inherit;font-size: var(--app-font-caption)}.rollout-tools{display:flex;flex-direction:column;gap:9px;margin-top:11px;padding-top:11px;border-top:1px solid var(--app-border-subtle)}.rollout-tools code{overflow:hidden;color:var(--app-text-muted);font-size: var(--app-font-caption);text-overflow:ellipsis;white-space:nowrap}.required-policy{display:flex;flex-direction:column;gap:8px;padding-top:9px;border-top:1px solid var(--app-border-subtle)}.required-policy>strong{color:var(--app-color-warning);font-size: var(--app-font-caption)}.required-policy .warning{align-self:flex-start;border-color:color-mix(in srgb,var(--app-color-warning) 50%,var(--app-border-default));color:var(--app-color-warning)}.update-loading,.update-error{display:flex;align-items:center;gap:7px;padding:10px;color:var(--app-text-secondary);font-size: var(--app-font-caption)}.update-error{color:var(--app-color-danger)}.update-error-text{color:var(--app-color-danger)!important}.update-notice{color:var(--app-color-success)!important}.update-body footer{display:flex;justify-content:flex-end}.update-body footer .save{border-color:var(--app-color-primary);background:var(--app-color-primary);color:var(--app-color-on-primary)}button:disabled{opacity:.45;cursor:default}button:not(:disabled):hover{background:var(--app-bg-hover)}input:focus-visible,select:focus-visible,textarea:focus-visible,button:focus-visible,summary:focus-visible{outline:0;box-shadow:var(--focus-ring)}.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:620px){.domain-switches,.field-grid,.field-grid.compact{grid-template-columns:1fr}.field-grid .wide{grid-column:auto}.field-grid label.inline-field,.field-grid.compact label.inline-field,.rollout-tools>label.inline-field,.rollout-tools>.rollout-percent{grid-template-columns:1fr;align-items:stretch;gap:var(--app-form-label-control-gap)}.rollout-percent>span{display:none}.domain-settings>header,.release-tools>header{align-items:flex-start;flex-direction:column}.domain-settings header span,.release-tools header span{text-align:start}}
</style>
