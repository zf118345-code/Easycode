<template>
    <section class="runtime-panel">
        <nav class="service-tabs">
            <button v-for="item in tabs" :key="item.id" :class="{ active: tab === item.id }" :title="item.label" @click="tab = item.id"><component :is="item.icon" /><span>{{ item.label }}</span></button>
        </nav>
        <div class="service-body" v-loading="loading">
            <template v-if="tab === 'overview'">
                <header class="section-header"><div><strong>运行服务</strong><small>项目级持久化与多实例协调基础设施</small></div><button class="icon-button" @click="loadAll"><RefreshCw /></button></header>
                <div class="metric-grid">
                    <div v-for="metric in metrics" :key="metric.key"><span>{{ metric.label }}</span><b>{{ overview.counts?.[metric.key] || 0 }}</b></div>
                </div>
                <div class="info-card"><Database :size="15" /><div><strong>独立运行数据库</strong><small>{{ overview.database || '尚未初始化' }}</small></div></div>
                <div class="info-card"><ShieldCheck :size="15" /><div><strong>可靠性语义</strong><small>消息采用领取/确认；资源使用带过期时间的租约；远程发送失败进入离线补发队列。</small></div></div>
            </template>

            <template v-else-if="tab === 'schedules'">
                <header class="section-header"><div><strong>计划任务</strong><small>每日、固定间隔或单次运行</small></div></header>
                <button class="primary-action" @click="scheduleVisible = true"><CalendarClock />管理计划任务</button>
                <p class="section-note">计划由后端常驻服务维护，即使 IDE 页面暂时不在前台也会按时触发；IDE 后端退出期间不会执行。</p>
            </template>

            <template v-else-if="tab === 'state'">
                <header class="section-header"><div><strong>持久状态</strong><small>跨流程、跨重启保存进度</small></div><button class="icon-button" @click="loadStates"><RefreshCw /></button></header>
                <div class="compact-form"><el-input v-model="stateDraft.namespace" placeholder="命名空间" /><el-input v-model="stateDraft.key" placeholder="键" /><el-input v-model="stateDraft.value" type="textarea" :rows="2" placeholder="JSON 或普通文本" /><el-button type="primary" @click="saveState">保存状态</el-button></div>
                <div class="record-list"><div v-for="item in states" :key="`${item.namespace}:${item.key}`" class="record-row"><div><strong>{{ item.namespace }} / {{ item.key }}</strong><small>{{ stringify(item.value) }}</small></div><button class="icon-button danger" @click="removeState(item)"><Trash2 /></button></div><div v-if="!states.length" class="empty">暂无持久状态</div></div>
            </template>

            <template v-else-if="tab === 'messages'">
                <header class="section-header"><div><strong>本地消息</strong><small>同一电脑上的 IDE / Player / 多开实例协同</small></div><button class="icon-button" @click="loadMessages"><RefreshCw /></button></header>
                <div class="compact-form"><el-input v-model="messageDraft.channel" placeholder="频道" /><el-input v-model="messageDraft.sender" placeholder="发送者（可选）" /><el-input v-model="messageDraft.payload" type="textarea" :rows="2" placeholder="消息 JSON 或文本" /><el-button type="primary" @click="publishMessage">发布消息</el-button></div>
                <div class="claim-line"><el-input v-model="consumer" placeholder="消费者 ID" /><el-button @click="claimMessages">领取待处理消息</el-button></div>
                <div class="record-list"><div v-for="item in messages" :key="item.id" class="record-row"><div><strong>#{{ item.channel }} · {{ item.sender || '匿名' }}</strong><small>{{ stringify(item.payload) }}</small><em>{{ item.status }} · {{ formatTime(item.created_at) }}</em></div><el-button v-if="item.status === 'claimed' && item.claimed_by === consumer" text type="success" @click="ackMessage(item)">确认</el-button></div><div v-if="!messages.length" class="empty">暂无消息</div></div>
            </template>

            <template v-else-if="tab === 'leases'">
                <header class="section-header"><div><strong>资源租约</strong><small>防止多个实例同时占用同一账号、窗口或设备</small></div><button class="icon-button" @click="loadLeases"><RefreshCw /></button></header>
                <div class="compact-form"><el-input v-model="leaseDraft.resource_key" placeholder="资源键，例如 emulator-1" /><el-input v-model="leaseDraft.owner" placeholder="实例/所有者 ID" /><el-input-number v-model="leaseDraft.ttl_seconds" :min="5" :max="86400" /><el-button type="primary" @click="acquireLease">获取租约</el-button></div>
                <div class="record-list"><div v-for="item in leases" :key="item.resource_key" class="record-row"><div><strong>{{ item.resource_key }}</strong><small>所有者：{{ item.owner }}</small><em>到期：{{ formatTime(item.expires_at) }}</em></div><el-button v-if="ownedTokens[item.resource_key]" text type="danger" @click="releaseLease(item)">释放</el-button></div><div v-if="!leases.length" class="empty">暂无有效租约</div></div>
            </template>

            <template v-else>
                <header class="section-header"><div><strong>局域网协调</strong><small>跨电脑消息、离线补发与分布式租约</small></div></header>
                <div class="compact-form"><el-input v-model="remote.endpoint" placeholder="协调器地址，例如 http://192.168.1.10:8000" /><el-input v-model="remote.token" type="password" show-password placeholder="EASYCODE_COORDINATOR_TOKEN" /><el-input v-model="remote.channel" placeholder="频道" /><el-input v-model="remote.consumer" placeholder="本机消费者 ID" /><el-input v-model="remote.payload" type="textarea" :rows="2" placeholder="消息 JSON 或文本" /><div class="button-row"><el-button type="primary" @click="publishRemote">发送</el-button><el-button @click="claimRemote">领取</el-button></div></div>
                <div class="record-list"><div v-for="item in remoteMessages" :key="item.id" class="record-row"><div><strong>#{{ item.channel }} · {{ item.sender || '远程' }}</strong><small>{{ stringify(item.payload) }}</small></div><el-button text type="success" @click="ackRemote(item)">确认</el-button></div><div v-if="!remoteMessages.length" class="empty">尚未领取远程消息</div></div>
                <div class="subsection-title"><KeyRound :size="14" /><div><strong>远程资源租约</strong><small>跨电脑互斥占用账号、模拟器或业务资源</small></div></div>
                <div class="compact-form"><el-input v-model="remoteLease.resource_key" placeholder="资源键，例如 account-01" /><el-input v-model="remoteLease.owner" placeholder="本机实例/所有者 ID" /><el-input-number v-model="remoteLease.ttl_seconds" :min="5" :max="86400" /><div class="button-row"><el-button type="primary" @click="acquireRemoteLease">获取</el-button><el-button :disabled="!remoteLeaseToken" @click="renewRemoteLease">续租</el-button><el-button :disabled="!remoteLeaseToken" type="danger" plain @click="releaseRemoteLease">释放</el-button></div></div>
                <div v-if="remoteLeaseToken" class="lease-token"><ShieldCheck :size="14" /><span>当前持有 {{ remoteLease.resource_key }}，令牌仅保存在本次界面会话中。</span></div>
                <p class="section-note">协调器必须显式配置令牌后才允许监听局域网地址；消息发送失败会进入当前 {{ scope === 'player' ? 'Player' : '项目' }} 的 outbox 自动重试。租约为实时互斥操作，断网时不会伪报成功。</p>
            </template>
        </div>
        <PlatformScheduleDialog v-model="scheduleVisible" :scope="scope" :tasks="tasks" :instance-id="instanceId" :profiles="profiles" />
    </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CalendarClock, Database, Gauge, KeyRound, MessagesSquare, Network, RefreshCw, ShieldCheck, Trash2 } from 'lucide-vue-next'
import { platformApi } from '@/api/platformApi'
import { useProjectStore } from '@/stores'
import PlatformScheduleDialog from '@/components/PlatformScheduleDialog.vue'

const props = defineProps({
    scope: { type: String, default: 'ide' },
    instanceId: { type: String, default: 'instance-1' },
    profiles: { type: Array, default: () => [] },
    tasks: { type: Array, default: () => [] }
})
// Player installs an isolated, empty Pinia instance. It never loads IDE recent
// projects; the store is used only to obtain IDE task choices when this same
// panel is mounted inside the editor.
const store = useProjectStore()
const tab = ref('overview')
const pendingOperations = ref(0)
const loading = computed(() => pendingOperations.value > 0)
const scheduleVisible = ref(false)
const overview = reactive({ counts: {}, database: '' })
const states = ref([])
const messages = ref([])
const leases = ref([])
const remoteMessages = ref([])
const defaultOwner = props.scope === 'player' ? props.instanceId : 'ide-1'
const consumer = ref(defaultOwner)
const ownedTokens = reactive({})
const stateDraft = reactive({ namespace: 'default', key: '', value: '' })
const messageDraft = reactive({ channel: 'default', sender: defaultOwner, payload: '' })
const leaseDraft = reactive({ resource_key: '', owner: defaultOwner, ttl_seconds: 30 })
const remote = reactive({ endpoint: '', token: '', channel: 'default', consumer: defaultOwner, payload: '' })
const remoteLease = reactive({ resource_key: '', owner: defaultOwner, ttl_seconds: 30 })
const remoteLeaseToken = ref('')
const scope = computed(() => props.scope === 'player' ? 'player' : 'ide')
const tasks = computed(() => (
    scope.value === 'player'
        ? props.tasks
        : (props.tasks.length ? props.tasks : [{
            task_id: 'main', task_name: '主流程', ...(store.blueprint?.main_graph || {})
        }])
))
const tabs = [
    { id: 'overview', label: '概览', icon: Gauge }, { id: 'schedules', label: '计划', icon: CalendarClock },
    { id: 'state', label: '状态', icon: Database }, { id: 'messages', label: '消息', icon: MessagesSquare },
    { id: 'leases', label: '租约', icon: KeyRound }, { id: 'remote', label: '局域网', icon: Network }
]
const metrics = [
    { key: 'schedules_enabled', label: '启用计划' }, { key: 'states', label: '持久状态' },
    { key: 'messages', label: '待处理消息' }, { key: 'leases', label: '有效租约' },
    { key: 'outbox_pending', label: '离线待发' }, { key: 'outbox_dead', label: '停放失败' }
]
const parseValue = value => { try { return JSON.parse(value) } catch { return value } }
const stringify = value => typeof value === 'string' ? value : JSON.stringify(value)
const formatTime = value => value ? new Date(Number(value) * 1000).toLocaleString() : '—'
const isUserCancel = error => ['cancel', 'close'].includes(String(error?.action || error || '').toLowerCase())
const guard = async operation => {
    pendingOperations.value += 1
    try {
        return await operation()
    } catch (error) {
        if (!isUserCancel(error)) ElMessage.error(error?.message || '运行服务操作失败')
        return undefined
    } finally {
        pendingOperations.value = Math.max(0, pendingOperations.value - 1)
    }
}
const loadOverview = () => guard(async () => Object.assign(overview, await platformApi.overview(scope.value)))
const loadStates = () => guard(async () => { states.value = (await platformApi.listStates(scope.value))?.states || [] })
const loadMessages = () => guard(async () => { messages.value = (await platformApi.listMessages(scope.value))?.messages || [] })
const loadLeases = () => guard(async () => { leases.value = (await platformApi.listLeases(scope.value))?.leases || [] })
const loadAll = async () => { await Promise.all([loadOverview(), loadStates(), loadMessages(), loadLeases()]) }
const saveState = () => guard(async () => { if (!stateDraft.key.trim()) return ElMessage.warning('请输入状态键'); await platformApi.setState(stateDraft.key.trim(), parseValue(stateDraft.value), stateDraft.namespace || 'default', scope.value); stateDraft.key = ''; stateDraft.value = ''; await loadStates() })
const removeState = item => guard(async () => { await ElMessageBox.confirm(`删除 ${item.namespace}/${item.key}？`, '删除状态', { type: 'warning' }); await platformApi.deleteState(item.key, item.namespace, scope.value); await loadStates() })
const publishMessage = () => guard(async () => { await platformApi.publishMessage({ channel: messageDraft.channel || 'default', sender: messageDraft.sender, payload: parseValue(messageDraft.payload) }, scope.value); messageDraft.payload = ''; await loadMessages() })
const claimMessages = () => guard(async () => { await platformApi.claimMessages({ channel: messageDraft.channel || 'default', consumer: consumer.value || defaultOwner }, scope.value); await loadMessages() })
const ackMessage = item => guard(async () => { await platformApi.ackMessage(item.id, consumer.value || defaultOwner, scope.value); await loadMessages() })
const acquireLease = () => guard(async () => { if (!leaseDraft.resource_key || !leaseDraft.owner) return ElMessage.warning('请填写资源键和所有者'); const result = await platformApi.acquireLease({ ...leaseDraft }, scope.value); ownedTokens[result.resource_key] = result.token; await loadLeases() })
const releaseLease = item => guard(async () => { await platformApi.releaseLease({ resource_key: item.resource_key, owner: item.owner, token: ownedTokens[item.resource_key] }, scope.value); delete ownedTokens[item.resource_key]; await loadLeases() })
const remotePayload = () => ({ endpoint: remote.endpoint, token: remote.token, channel: remote.channel || 'default', consumer: remote.consumer || defaultOwner })
const publishRemote = () => guard(async () => { if (!remote.endpoint || !remote.token) return ElMessage.warning('请填写协调器地址和令牌'); const result = await platformApi.publishRemote({ ...remotePayload(), payload: parseValue(remote.payload), sender: remote.consumer }, scope.value); remote.payload = ''; ElMessage.success(result.queued ? '网络不可用，消息已进入离线补发队列' : '远程消息已发送'); await loadOverview() })
const claimRemote = () => guard(async () => { remoteMessages.value = (await platformApi.claimRemote(remotePayload()))?.messages || [] })
const ackRemote = item => guard(async () => { await platformApi.ackRemote(item.id, remotePayload()); remoteMessages.value = remoteMessages.value.filter(message => message.id !== item.id) })
const remoteLeasePayload = () => ({ endpoint: remote.endpoint, token: remote.token, resource_key: remoteLease.resource_key, owner: remoteLease.owner, ttl_seconds: remoteLease.ttl_seconds })
const validateRemoteLease = () => {
    if (!remote.endpoint || !remote.token) { ElMessage.warning('请先填写协调器地址和令牌'); return false }
    if (!remoteLease.resource_key || !remoteLease.owner) { ElMessage.warning('请填写远程资源键和所有者'); return false }
    return true
}
const acquireRemoteLease = () => guard(async () => { if (!validateRemoteLease()) return; const result = await platformApi.acquireRemoteLease(remoteLeasePayload()); remoteLeaseToken.value = result.token; ElMessage.success('远程租约已获取') })
const renewRemoteLease = () => guard(async () => { if (!validateRemoteLease() || !remoteLeaseToken.value) return; const result = await platformApi.renewRemoteLease({ ...remoteLeasePayload(), lease_token: remoteLeaseToken.value }); if (!result.renewed) throw new Error('远程租约已过期或不再属于当前实例'); ElMessage.success('远程租约已续期') })
const releaseRemoteLease = () => guard(async () => { if (!validateRemoteLease() || !remoteLeaseToken.value) return; const result = await platformApi.releaseRemoteLease({ ...remoteLeasePayload(), lease_token: remoteLeaseToken.value }); if (!result.released) throw new Error('远程租约不存在或令牌不匹配'); remoteLeaseToken.value = ''; ElMessage.success('远程租约已释放') })
onMounted(loadOverview)
watch(tab, value => ({ overview: loadOverview, state: loadStates, messages: loadMessages, leases: loadLeases }[value]?.()))
watch(() => props.instanceId, value => { if (props.scope === 'player' && value) { consumer.value = value; messageDraft.sender = value; leaseDraft.owner = value; remote.consumer = value; remoteLease.owner = value } })
</script>

<style scoped>
.runtime-panel { height:100%; display:flex; flex-direction:column; overflow:hidden; background:var(--app-sidebar-bg); }
.service-tabs { display:grid; grid-template-columns:repeat(3,1fr); gap:3px; padding:7px; border-bottom:1px solid var(--app-separator); }
.service-tabs button { min-width:0; height:30px; display:flex; align-items:center; justify-content:center; gap:4px; border:0; border-radius:6px; background:transparent; color:var(--el-text-color-secondary); font-size:10px; cursor:pointer; }.service-tabs button.active,.service-tabs button:hover { background:var(--el-fill-color-light); color:var(--el-color-primary); }.service-tabs svg { width:13px; }
.service-body { flex:1; overflow:auto; padding:10px; }.section-header { display:flex; align-items:center; margin-bottom:10px; }.section-header>div { flex:1; display:flex; flex-direction:column; gap:2px; }.section-header strong { font-size:13px; }.section-header small,.section-note { color:var(--el-text-color-secondary); font-size:10.5px; line-height:1.5; }
.icon-button { width:28px; height:28px; display:grid; place-items:center; padding:0; border:0; border-radius:6px; background:transparent; color:var(--el-text-color-secondary); cursor:pointer; }.icon-button:hover { background:var(--el-fill-color-light); color:var(--el-color-primary); }.icon-button.danger:hover { color:var(--el-color-danger); }.icon-button svg { width:14px; }
.metric-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:6px; }.metric-grid div { padding:9px; border:1px solid var(--el-border-color-light); border-radius:7px; display:flex; flex-direction:column; gap:3px; }.metric-grid span { color:var(--el-text-color-secondary); font-size:10px; }.metric-grid b { font-size:17px; }
.info-card { margin-top:8px; padding:9px; display:flex; gap:8px; border-radius:7px; background:var(--el-fill-color-extra-light); }.info-card>svg { flex:0 0 auto; color:var(--el-color-primary); }.info-card div { min-width:0; display:flex; flex-direction:column; gap:3px; }.info-card strong { font-size:11px; }.info-card small { color:var(--el-text-color-secondary); font-size:10px; overflow-wrap:anywhere; line-height:1.4; }
.primary-action { width:100%; height:34px; display:flex; justify-content:center; align-items:center; gap:6px; border:0; border-radius:7px; background:var(--el-color-primary); color:#07150f; cursor:pointer; }.primary-action svg { width:15px; }
.compact-form { display:flex; flex-direction:column; gap:6px; padding-bottom:10px; border-bottom:1px solid var(--app-separator); }.button-row,.claim-line { display:flex; gap:6px; }.claim-line { margin:8px 0; }.button-row>* { flex:1; }
.subsection-title { display:flex; align-items:center; gap:7px; margin:14px 0 8px; }.subsection-title>div { display:flex; flex-direction:column; }.subsection-title strong { font-size:11px; }.subsection-title small { color:var(--el-text-color-secondary); font-size:10px; }.lease-token { display:flex; align-items:center; gap:6px; margin-top:8px; padding:7px; border-radius:6px; background:color-mix(in srgb,var(--el-color-success) 10%,transparent); color:var(--el-color-success); font-size:10px; }
.record-list { display:flex; flex-direction:column; gap:5px; margin-top:8px; }.record-row { display:flex; align-items:center; gap:5px; padding:8px; border:1px solid var(--el-border-color-light); border-radius:7px; }.record-row>div { min-width:0; flex:1; display:flex; flex-direction:column; gap:2px; }.record-row strong { font-size:10.5px; overflow-wrap:anywhere; }.record-row small { color:var(--el-text-color-secondary); font-size:10px; white-space:pre-wrap; overflow-wrap:anywhere; }.record-row em { color:var(--el-text-color-placeholder); font-size:10px; font-style:normal; }.empty { padding:20px 0; text-align:center; color:var(--el-text-color-placeholder); font-size:10.5px; }
</style>
