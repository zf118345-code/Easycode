<template>
    <details class="player-devices" @toggle="onToggle">
        <summary><span><RadioTower :size="13" />设备协作</span><em>{{ summary }}</em></summary>
        <p class="device-note">同机或局域网内传递消息；消息、查看状态、远程启动分别授权，不经过 EasyCode 云端。</p>
        <VNextWorkspaceState v-if="busy && !lan" class="device-empty" compact kind="loading" title="正在读取设备状态"><template #icon><LoaderCircle :size="16" class="spin" /></template></VNextWorkspaceState>
        <template v-else-if="lan && instance">
            <label class="device-field"><span>本实例名称</span>
                <span class="inline-edit"><input v-model.trim="instanceName" maxlength="160" /><button type="button" :disabled="busy || !instanceName || instanceName === instance.display_name" @click="renameInstance"><Save :size="12" />保存</button></span>
            </label>
            <div class="device-listener">
                <span><strong>{{ lan.running ? '局域网监听已开启' : '局域网监听已关闭' }}</strong><small>{{ lan.running ? `${lan.addresses.join('、') || '本机'}:${lan.port}` : '关闭时仍可运行不需要消息的脚本' }}</small></span>
                <button type="button" :disabled="busy" @click="toggleListener">{{ lan.running ? '关闭' : '开启' }}</button>
            </div>
            <div class="device-actions">
                <button type="button" :disabled="busy" @click="createSession"><QrCode :size="12" />让其他设备连接</button>
                <button type="button" :disabled="busy" @click="connecting = !connecting"><Link :size="12" />连接其他设备</button>
                <button type="button" :disabled="busy" @click="refresh"><RotateCw :size="12" />刷新</button>
            </div>
            <section v-if="session" class="pair-card">
                <strong>在另一台设备输入</strong>
                <img v-if="pairQr" :src="pairQr" alt="设备配对二维码" />
                <code>{{ session.code }}</code>
                <small>地址 {{ session.addresses.join('、') }} · 端口 {{ session.port }}</small>
                <small>会话 {{ session.session_id }}</small>
                <small>指纹 {{ session.short_fingerprint }}</small>
            </section>
            <section v-if="connecting" class="connect-card">
                <label class="device-field"><span>设备地址</span><span class="connect-address-control"><input v-model.trim="connectDraft.address" aria-label="设备地址" inputmode="decimal" placeholder="192.168.1.20" /><span aria-hidden="true">:</span><input v-model.number="connectDraft.port" class="connect-port" aria-label="端口" type="number" min="1" max="65535" /></span></label>
                <label class="device-field"><span>会话编号</span><input v-model.trim="connectDraft.session_id" placeholder="粘贴对方会话编号" /></label>
                <label class="device-field"><span>配对码</span><input v-model.trim="connectDraft.code" inputmode="numeric" placeholder="1234-5678" /></label>
                <button v-if="!pendingPairing" type="button" class="primary" :disabled="busy || !canBegin" @click="beginPairing">请求连接</button>
                <button v-else type="button" class="primary" :disabled="busy" @click="completePairing">对方确认后，完成连接</button>
            </section>
            <section v-for="pending in pendingRequests" :key="pending.pending_id" class="pending-card">
                <span><strong>{{ pending.device_name }}</strong><small>{{ pending.platform }} · {{ pending.fingerprint }}</small></span>
                <div class="permission-grid">
                    <label><input v-model="pendingPermissions.messages" type="checkbox" />收发消息</label>
                    <label><input v-model="pendingPermissions.status" type="checkbox" />查看实例</label>
                    <label><input v-model="pendingPermissions.remote_start" type="checkbox" />远程启动</label>
                </div>
                <button type="button" :disabled="busy || !pendingPermissions.messages" @click="confirmPairing(pending.pending_id)">确认授权</button>
            </section>
            <section v-if="lan.paired_devices.length" class="peer-list">
                <strong>已配对设备</strong>
                <article v-for="peer in lan.paired_devices" :key="peer.host_id">
                    <span><strong>{{ peer.device_name }}</strong><small>{{ peer.platform }} · {{ peer.last_error_id ? `连接异常 ${peer.last_error_id}` : '身份已固定' }}</small></span>
                    <div class="permission-grid">
                        <label><input v-model="peer.permissions.messages" type="checkbox" />收发消息</label>
                        <label><input v-model="peer.permissions.status" type="checkbox" />查看实例</label>
                        <label><input v-model="peer.permissions.remote_start" type="checkbox" />远程启动</label>
                    </div>
                    <div class="peer-actions"><button type="button" :disabled="busy" @click="savePeerPermissions(peer)">保存权限</button><button type="button" :disabled="busy" @click="refreshPeer(peer.host_id)">刷新实例</button><button type="button" class="danger-text" :disabled="busy" @click="revoke(peer.host_id)">撤销</button></div>
                </article>
            </section>
            <section v-if="messages?.copies.length" class="message-list">
                <strong>最近消息</strong>
                <div v-for="copy in messages.copies.slice(0, 8)" :key="copy.message_id"><span>{{ copy.recipient_display_name || '当前实例' }}</span><em>{{ statusLabel(copy.status) }}</em></div>
            </section>
        </template>
        <VNextInlineNotice v-if="error" class="device-error" tone="error" :message="error" />
    </details>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { Link, LoaderCircle, QrCode, RadioTower, RotateCw, Save } from 'lucide-vue-next'
import QRCode from 'qrcode'
import { vnextApi } from '../playerApi'
import type { PlayerLanPairingSession, PlayerLanPeer, PlayerLanPermissions, PlayerLanStatus, PlayerMessageInstance, PlayerMessageStatus } from '../types'
import VNextInlineNotice from './ui/VNextInlineNotice.vue'
import VNextWorkspaceState from './ui/VNextWorkspaceState.vue'

const emit = defineEmits<{ feedback: [payload: { ok: boolean; message: string }] }>()
const lan = ref<PlayerLanStatus | null>(null), instance = ref<PlayerMessageInstance | null>(null), messages = ref<PlayerMessageStatus | null>(null)
const session = ref<PlayerLanPairingSession | null>(null), pendingPairing = ref<Record<string, unknown> | null>(null)
const pairQr = ref('')
const instanceName = ref(''), connecting = ref(false), busy = ref(false), error = ref('')
const connectDraft = reactive({ address: '', port: 41663, session_id: '', code: '' })
const defaultPermissions = (): PlayerLanPermissions => ({ messages: true, status: true, remote_start: false, allowed_products: [], allowed_instances: [] })
const pendingPermissions = reactive<PlayerLanPermissions>(defaultPermissions())
const summary = computed(() => !lan.value ? '未加载' : lan.value.running ? `${lan.value.paired_devices.length} 台已配对` : '未开启')
const canBegin = computed(() => connectDraft.address && connectDraft.port > 0 && connectDraft.session_id && connectDraft.code)
const pendingRequests = computed(() => lan.value?.pairing_sessions.flatMap(item => item.pending || []).filter(item => item.status === 'pending') || [])
function message(reason: unknown) { return reason instanceof Error ? reason.message : '设备协作操作失败' }
async function action(task: () => Promise<void>) { busy.value = true; error.value = ''; try { await task() } catch (reason) { error.value = message(reason) } finally { busy.value = false } }
async function load() {
    const [nextLan, nextInstance, nextMessages] = await Promise.all([vnextApi.playerRuntimeLan(), vnextApi.playerRuntimeMessageInstance(), vnextApi.playerRuntimeMessages()])
    lan.value = nextLan; instance.value = nextInstance; messages.value = nextMessages; instanceName.value = nextInstance.display_name
}
function onToggle(event: Event) { if ((event.currentTarget as HTMLDetailsElement).open && !lan.value) void action(load) }
function refresh() { void action(load) }
function toggleListener() { void action(async () => { if (lan.value?.running) await vnextApi.stopPlayerRuntimeLan(); else await vnextApi.startPlayerRuntimeLan(); await load() }) }
function renameInstance() { void action(async () => { instance.value = await vnextApi.renamePlayerRuntimeMessageInstance(instanceName.value); instanceName.value = instance.value.display_name; emit('feedback', { ok: true, message: '实例名称已保存' }) }) }
function createSession() { void action(async () => { session.value = await vnextApi.createPlayerRuntimePairingSession(); pairQr.value = session.value.qr_payload ? await QRCode.toDataURL(session.value.qr_payload, { width: 176, margin: 1 }) : ''; await load() }) }
function beginPairing() { void action(async () => { pendingPairing.value = await vnextApi.beginPlayerRuntimePairing({ ...connectDraft, permissions: defaultPermissions() }); emit('feedback', { ok: true, message: '连接请求已送达，请在另一台设备确认' }) }) }
function completePairing() { void action(async () => { const result = await vnextApi.completePlayerRuntimePairing(pendingPairing.value || {}); if (result.status && result.status !== 'confirmed') throw new Error('另一台设备还没有确认'); pendingPairing.value = null; connecting.value = false; await load(); emit('feedback', { ok: true, message: '设备配对完成' }) }) }
function confirmPairing(pendingId: string) { void action(async () => { await vnextApi.confirmPlayerRuntimePairing(pendingId, { ...pendingPermissions }); await load(); emit('feedback', { ok: true, message: '设备权限已确认' }) }) }
function savePeerPermissions(peer: PlayerLanPeer) { void action(async () => { await vnextApi.setPlayerRuntimeLanPermissions(peer.host_id, { ...peer.permissions }); await load(); emit('feedback', { ok: true, message: '设备权限已保存' }) }) }
function refreshPeer(hostId: string) { void action(async () => { await vnextApi.refreshPlayerRuntimeLanPeer(hostId); await load(); emit('feedback', { ok: true, message: '远端实例目录已刷新' }) }) }
function revoke(hostId: string) { void action(async () => { await vnextApi.revokePlayerRuntimeLanPeer(hostId); await load(); emit('feedback', { ok: true, message: '设备授权已撤销' }) }) }
function statusLabel(value: string) { return ({ waiting_send: '等待发送', waiting_read: '等待读取', read: '已读取', expired: '已过期', cancelled: '已取消', failed: '发送失败' } as Record<string, string>)[value] || value }
</script>

<style scoped>
.player-devices {
    border-top: 1px solid var(--app-border-subtle);
    padding-top: var(--app-spacing-sm);
    container-type: inline-size;
}
.player-devices summary {
    min-height: var(--app-control-default);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--app-spacing-sm);
    list-style: none;
    color: var(--app-text-primary);
    cursor: pointer;
}
.player-devices summary span,
.device-empty { display: flex; align-items: center; gap: var(--app-spacing-xs); }
.player-devices summary em { color: var(--app-text-placeholder); font-size: var(--app-font-caption); font-style: normal; }
.device-note,
.player-devices small { color: var(--app-text-placeholder); font-size: var(--app-font-caption); line-height: 1.45; }
.device-note { margin: var(--app-spacing-xs) 0 var(--app-spacing-sm); }
.device-field {
    min-width: 0;
    min-height: var(--app-control-default);
    display: grid;
    grid-template-columns: minmax(82px, 92px) minmax(0, 1fr);
    align-items: center;
    gap: var(--app-spacing-xs);
    font-size: var(--app-font-compact);
}
.device-field > span:first-child {
    min-width: 0;
    overflow: hidden;
    color: var(--app-text-secondary);
    text-overflow: ellipsis;
    white-space: nowrap;
}
.inline-edit {
    min-width: 0;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--app-spacing-xs);
}
.connect-address-control {
    min-width: 0;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto 72px;
    align-items: center;
    gap: var(--app-spacing-xs);
}
.connect-address-control > span { color: var(--app-text-placeholder); }
.player-devices input:not([type=checkbox]) {
    min-width: 0;
    width: 100%;
    height: var(--app-control-default);
    padding: 0 var(--app-spacing-sm);
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    outline: 0;
    background: var(--app-bg-input);
    color: var(--app-text-primary);
}
.player-devices input:not([type=checkbox]):focus-visible { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.player-devices input[type=checkbox] { width: 16px; height: 16px; margin: 0; padding: 0; accent-color: var(--app-color-primary); }
.player-devices button {
    min-height: var(--app-control-default);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--app-spacing-xs);
    padding: 0 var(--app-spacing-sm);
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    background: var(--app-bg-raised);
    color: var(--app-text-regular);
    cursor: pointer;
}
.player-devices button:hover:not(:disabled) { border-color: var(--app-border-strong); background: var(--app-bg-hover); color: var(--app-text-primary); }
.player-devices button:focus-visible { outline: 0; box-shadow: var(--focus-ring); }
.player-devices button:disabled { opacity: .45; cursor: not-allowed; }
.device-listener {
    min-height: var(--app-control-default);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--app-spacing-sm);
    padding: var(--app-spacing-sm) 0;
}
.device-listener span,
.pending-card > span,
.peer-list article > span { min-width: 0; display: grid; }
.device-actions,
.peer-actions { display: flex; flex-wrap: wrap; gap: var(--app-spacing-xs); }
.pair-card,
.connect-card,
.pending-card,
.peer-list,
.message-list {
    display: grid;
    gap: var(--app-spacing-xs);
    margin-top: var(--app-spacing-sm);
    padding: var(--app-spacing-sm);
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-md);
    background: var(--app-bg-sidebar);
}
.pair-card img { width: 132px; height: 132px; justify-self: center; padding: 4px; border-radius: var(--app-radius-sm); background: #fff; }
.pair-card code { color: var(--app-color-primary); font-size: var(--app-font-xl); letter-spacing: 2px; text-align: center; }
.connect-card > button,
.pending-card > button { justify-self: end; }
.peer-list article { display: grid; gap: var(--app-spacing-xs); padding: var(--app-spacing-sm) 0; border-bottom: 1px solid var(--app-border-subtle); }
.peer-list article:last-child { border-bottom: 0; }
.permission-grid { display: flex; flex-wrap: wrap; gap: var(--app-spacing-sm); }
.permission-grid label { display: flex; align-items: center; gap: var(--app-spacing-xs); color: var(--app-text-secondary); font-size: var(--app-font-caption); }
.message-list div { display: flex; justify-content: space-between; gap: var(--app-spacing-sm); font-size: var(--app-font-caption); }
.message-list em { color: var(--app-text-secondary); font-style: normal; }
.device-error { margin-top: var(--app-spacing-sm); color: var(--app-color-danger); font-size: var(--app-font-caption); }
.danger-text { color: var(--app-color-danger) !important; }
.primary { border-color: var(--app-color-primary) !important; background: var(--app-color-primary) !important; color: var(--app-color-on-primary) !important; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

@container (max-width: 258px) {
    .device-field { grid-template-columns: minmax(0, 1fr); align-items: stretch; }
    .connect-address-control { grid-template-columns: minmax(0, 1fr) auto 64px; }
}

@media (prefers-reduced-motion: reduce) {
    .spin { animation: none; }
}
</style>
