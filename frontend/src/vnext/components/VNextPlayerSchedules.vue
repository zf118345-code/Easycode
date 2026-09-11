<template>
    <details class="player-schedules">
        <summary><span><CalendarClock :size="13" />运行计划</span><em>{{ enabledCount ? `${enabledCount} 个启用` : '未设置' }}</em></summary>
        <p class="schedule-note">由 Android 系统尽力唤醒当前 APK。截图、输入等授权失效时会记录阻止原因，不会盲目操作。</p>
        <button v-if="!editing" type="button" class="schedule-create" :disabled="disabled || !profiles.length" @click="newSchedule"><Plus :size="12" />新建计划</button>
        <div v-if="editing" class="schedule-editor">
            <label><span>名称</span><input v-model.trim="draft.name" maxlength="80" /></label>
            <label><span>运行方案</span><select v-model="draft.profile_id"><option v-for="profile in profiles" :key="profile.profile_id" :value="profile.profile_id">{{ profile.name }}</option></select></label>
            <label><span>何时运行</span><select v-model="draft.trigger_kind"><option value="one_time">仅一次</option><option value="daily">每天</option><option value="interval">固定间隔</option></select></label>
            <label v-if="draft.trigger_kind === 'one_time'"><span>运行时间</span><input v-model="draft.one_time" type="datetime-local" /></label>
            <label v-else-if="draft.trigger_kind === 'daily'"><span>每天时间</span><input v-model="draft.daily_time" type="time" /></label>
            <label v-else><span>间隔分钟</span><input v-model.number="draft.interval_minutes" type="number" min="1" max="43200" step="1" /></label>
            <label><span>任务正忙</span><select v-model="draft.overlap_policy"><option value="queue_once">空闲后补跑一次</option><option value="skip">跳过这次</option></select></label>
            <label><span>错过时间</span><select v-model="draft.misfire_policy"><option value="run_once">1 小时内补跑一次</option><option value="skip">跳过这次</option></select></label>
            <label class="schedule-enabled"><span>启用计划</span><input v-model="draft.enabled" type="checkbox" /></label>
            <div class="schedule-editor-actions"><button type="button" @click="cancelEdit">取消</button><button type="button" class="primary" :disabled="busy || !draft.name || !draft.profile_id" @click="save">保存计划</button></div>
        </div>
        <div v-for="item in schedules" :key="item.schedule_id" class="schedule-row">
            <button type="button" class="schedule-main" :disabled="busy" @click="edit(item)">
                <span><strong>{{ item.name }}</strong><small>{{ item.profile_name }} · {{ triggerLabel(item) }}</small></span>
                <em>{{ item.enabled ? nextLabel(item.next_trigger_at) : '已停用' }}</em>
            </button>
            <button type="button" title="立即运行一次" aria-label="立即运行一次" :disabled="busy || disabled" @click="runNow(item.schedule_id)"><Play :size="12" aria-hidden="true" /></button>
            <button type="button" title="删除计划" aria-label="删除计划" :disabled="busy || disabled" @click="pendingDelete = item.schedule_id"><Trash2 :size="12" aria-hidden="true" /></button>
        </div>
        <details v-if="occurrences.length" class="schedule-history"><summary>最近触发</summary><p v-for="item in occurrences.slice(-6).reverse()" :key="item.occurrence_id"><span>{{ statusLabel(item.status, item.reason) }} · {{ occurrenceName(item) }}</span><time>{{ timeLabel(item.discovered_at) }}</time></p></details>
        <VNextConfirmDialog :open="Boolean(pendingDelete)" title="删除运行计划" message="只停止未来触发；已经开始的任务不会被停止。" confirm-label="确认删除" tone="warning" :busy="busy" @cancel="pendingDelete = ''" @confirm="remove" />
    </details>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { CalendarClock, Play, Plus, Trash2 } from 'lucide-vue-next'
import { vnextApi } from '../playerApi'
import type { AndroidPlayerSchedule, AndroidScheduleOccurrence, PlayerProfile } from '../types'
import VNextConfirmDialog from './VNextConfirmDialog.vue'

const props = defineProps<{ profiles: PlayerProfile[]; disabled?: boolean }>()
const emit = defineEmits<{ feedback: [detail: { ok: boolean; message: string }] }>()
const schedules = ref<AndroidPlayerSchedule[]>([])
const occurrences = ref<AndroidScheduleOccurrence[]>([])
const editing = ref(false)
const busy = ref(false)
const pendingDelete = ref('')
const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
const draft = reactive({ schedule_id: '', revision: 0, name: '', profile_id: '', enabled: true, trigger_kind: 'daily' as 'one_time' | 'daily' | 'interval', one_time: '', daily_time: '08:00', interval_minutes: 60, misfire_policy: 'run_once' as 'skip' | 'run_once', overlap_policy: 'queue_once' as 'skip' | 'queue_once' })
const enabledCount = computed(() => schedules.value.filter(item => item.enabled).length)

function localDateTime(instant?: string) {
    const date = instant ? new Date(instant) : new Date(Date.now() + 5 * 60_000)
    const offset = date.getTimezoneOffset() * 60_000
    return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}
function reset() { Object.assign(draft, { schedule_id: '', revision: 0, name: '', profile_id: props.profiles[0]?.profile_id || '', enabled: true, trigger_kind: 'daily', one_time: localDateTime(), daily_time: '08:00', interval_minutes: 60, misfire_policy: 'run_once', overlap_policy: 'queue_once' }) }
function newSchedule() { reset(); editing.value = true }
function cancelEdit() { editing.value = false; reset() }
function edit(item: AndroidPlayerSchedule) {
    Object.assign(draft, { schedule_id: item.schedule_id, revision: item.revision, name: item.name, profile_id: item.profile_id, enabled: item.enabled, trigger_kind: item.trigger.kind, one_time: item.trigger.kind === 'one_time' ? localDateTime(item.trigger.at) : localDateTime(), daily_time: item.trigger.kind === 'daily' ? item.trigger.local_time.slice(0, 5) : '08:00', interval_minutes: item.trigger.kind === 'interval' ? Math.round(item.trigger.interval_ms / 60_000) : 60, misfire_policy: item.misfire_policy, overlap_policy: item.overlap_policy })
    editing.value = true
}
function payload() {
    const trigger = draft.trigger_kind === 'one_time'
        ? { kind: 'one_time', at: new Date(draft.one_time).toISOString() }
        : draft.trigger_kind === 'daily'
          ? { kind: 'daily', local_time: draft.daily_time, timezone_id: timezone }
          : { kind: 'interval', anchor_time: new Date().toISOString(), interval_ms: Math.round(draft.interval_minutes * 60_000) }
    return { ...(draft.schedule_id ? { schedule_id: draft.schedule_id, expected_revision: draft.revision } : {}), name: draft.name, profile_id: draft.profile_id, enabled: draft.enabled, trigger, misfire_policy: draft.misfire_policy, max_lateness_ms: 3_600_000, overlap_policy: draft.overlap_policy }
}
async function refresh() { const result = await vnextApi.playerRuntimeSchedules(); schedules.value = result.schedules; occurrences.value = result.occurrences }
async function save() { busy.value = true; try { await vnextApi.savePlayerRuntimeSchedule(payload()); await refresh(); editing.value = false; emit('feedback', { ok: true, message: '运行计划已保存' }) } catch (error) { emit('feedback', { ok: false, message: error instanceof Error ? error.message : '计划保存失败' }) } finally { busy.value = false } }
async function runNow(id: string) { busy.value = true; try { await vnextApi.runPlayerRuntimeScheduleNow(id); emit('feedback', { ok: true, message: '已提交立即运行，结果会写入最近触发' }); setTimeout(() => void refresh(), 700) } catch (error) { emit('feedback', { ok: false, message: error instanceof Error ? error.message : '计划启动失败' }) } finally { busy.value = false } }
async function remove() { const id = pendingDelete.value; if (!id) return; busy.value = true; try { await vnextApi.deletePlayerRuntimeSchedule(id); schedules.value = schedules.value.filter(item => item.schedule_id !== id); pendingDelete.value = ''; editing.value = false; emit('feedback', { ok: true, message: '运行计划已删除' }) } catch (error) { emit('feedback', { ok: false, message: error instanceof Error ? error.message : '计划删除失败' }) } finally { busy.value = false } }
function triggerLabel(item: AndroidPlayerSchedule) { return item.trigger.kind === 'one_time' ? `仅一次 ${timeLabel(item.trigger.at)}` : item.trigger.kind === 'daily' ? `每天 ${item.trigger.local_time.slice(0, 5)}` : `每 ${Math.round(item.trigger.interval_ms / 60_000)} 分钟` }
function timeLabel(value = '') { if (!value) return '时间未知'; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }
function nextLabel(value = '') { return value ? `下次 ${timeLabel(value)}` : '等待触发' }
function occurrenceName(item: AndroidScheduleOccurrence) { return schedules.value.find(plan => plan.schedule_id === item.schedule_id)?.name || item.profile_name || '运行计划' }
function statusLabel(status: string, reason = '') { const labels: Record<string, string> = { completed: '已完成', running: '运行中', queued: '已排队', stopped: '已停止', skipped: '已跳过', blocked: '未启动', failed: '失败', checking: '检查中' }; const reasons: Record<string, string> = { capture_permission_missing: '截图授权失效', accessibility_permission_missing: '控件服务未开启', interactive_confirmation_required: '需要人工确认', instance_busy: '实例正忙', missed_deadline: '错过时限', process_interrupted: '进程中断' }; return reasons[reason] || labels[status] || status }
onMounted(async () => { reset(); try { await refresh() } catch (error) { emit('feedback', { ok: false, message: error instanceof Error ? error.message : '计划加载失败' }) } })
</script>

<style scoped>
.player-schedules {
    border-top: 1px solid var(--app-border-subtle);
    padding-top: var(--app-spacing-sm);
}
.player-schedules > summary {
    min-height: var(--app-control-default);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--app-spacing-sm);
    color: var(--app-text-primary);
    cursor: pointer;
}
.player-schedules > summary span { display: inline-flex; align-items: center; gap: var(--app-spacing-xs); }
.player-schedules > summary em { color: var(--app-text-placeholder); font-size: var(--app-font-caption); font-style: normal; }
.schedule-note { margin: var(--app-spacing-xs) 0 var(--app-spacing-sm); color: var(--app-text-placeholder); font-size: var(--app-font-caption); line-height: 1.45; }
.schedule-create,
.schedule-editor-actions button,
.schedule-row > button {
    min-height: var(--app-control-default);
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-secondary);
    cursor: pointer;
}
.schedule-create { display: inline-flex; align-items: center; gap: var(--app-spacing-xs); padding: 0 var(--app-spacing-sm); }
.schedule-editor {
    display: grid;
    gap: var(--app-spacing-xs);
    margin: var(--app-spacing-xs) 0 var(--app-spacing-sm);
    padding: var(--app-spacing-sm);
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-md);
    background: var(--app-bg-input);
    container-type: inline-size;
}
.schedule-editor label {
    min-width: 0;
    min-height: var(--app-control-default);
    display: grid;
    grid-template-columns: minmax(76px, 88px) minmax(0, 1fr);
    align-items: center;
    gap: var(--app-spacing-xs);
    color: var(--app-text-secondary);
    font-size: var(--app-font-caption);
}
.schedule-editor label > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.schedule-editor input:not([type=checkbox]),
.schedule-editor select {
    min-width: 0;
    width: 100%;
    height: var(--app-control-default);
    padding: 0 var(--app-spacing-sm);
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    outline: 0;
    background: var(--app-bg-base);
    color: var(--app-text-primary);
}
.schedule-editor input:focus-visible,
.schedule-editor select:focus-visible { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.schedule-enabled input {
    width: 16px;
    height: 16px;
    margin: 0;
    accent-color: var(--app-color-primary);
}
.schedule-editor-actions { display: flex; justify-content: flex-end; gap: var(--app-spacing-xs); padding-top: var(--app-spacing-xs); }
.schedule-editor-actions button { padding: 0 var(--app-spacing-sm); }
.schedule-editor-actions .primary { border-color: var(--app-color-primary); background: var(--app-color-primary); color: var(--app-color-on-primary); }
.schedule-row { display: grid; grid-template-columns: minmax(0, 1fr) var(--app-control-default) var(--app-control-default); gap: var(--app-spacing-xs); margin-top: var(--app-spacing-xs); }
.schedule-main { min-width: 0; display: flex; align-items: center; justify-content: space-between; gap: var(--app-spacing-sm); padding: var(--app-spacing-xs) var(--app-spacing-sm); text-align: left; }
.schedule-main span { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.schedule-main strong { color: var(--app-text-primary); font-size: var(--app-font-caption); }
.schedule-main small { overflow: hidden; color: var(--app-text-placeholder); font-size: var(--app-font-caption); text-overflow: ellipsis; white-space: nowrap; }
.schedule-main em { flex: 0 0 auto; max-width: 42%; color: var(--app-text-secondary); font-size: var(--app-font-caption); font-style: normal; text-align: right; }
.schedule-row > button:not(.schedule-main) { display: grid; place-items: center; padding: 0; }
.schedule-history { margin-top: var(--app-spacing-sm); color: var(--app-text-secondary); font-size: var(--app-font-caption); }
.schedule-history > summary { cursor: pointer; }
.schedule-history p { display: flex; justify-content: space-between; gap: var(--app-spacing-xs); margin: var(--app-spacing-xs) 0 0; }
.schedule-history time { color: var(--app-text-placeholder); }
button:hover:not(:disabled) { border-color: var(--app-border-strong); background: var(--app-bg-hover); color: var(--app-text-primary); }
button:disabled { opacity: .45; cursor: not-allowed; }

@container (max-width: 250px) {
    .schedule-editor label { grid-template-columns: minmax(0, 1fr); align-items: stretch; }
}
</style>
