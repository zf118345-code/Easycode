<template>
    <el-dialog
        :model-value="modelValue"
        title="计划任务"
        width="760px"
        append-to-body
        :close-on-click-modal="false"
        @update:model-value="$emit('update:modelValue', $event)"
        @open="load">
        <div class="schedule-layout">
            <div class="schedule-form">
                <el-input v-model="draft.name" placeholder="计划名称" />
                <el-select v-model="draft.schedule_type" style="width: 150px">
                    <el-option label="每天定时" value="daily" />
                    <el-option label="固定间隔" value="interval" />
                    <el-option label="仅运行一次" value="once" />
                </el-select>
                <el-time-picker
                    v-if="draft.schedule_type === 'daily'"
                    v-model="draft.schedule_value"
                    value-format="HH:mm:ss"
                    placeholder="每天执行时间" />
                <el-input-number
                    v-else-if="draft.schedule_type === 'interval'"
                    v-model="draft.schedule_value"
                    :min="1"
                    :max="31536000"
                    controls-position="right" />
                <el-date-picker
                    v-else
                    v-model="draft.schedule_value"
                    type="datetime"
                    value-format="YYYY-MM-DDTHH:mm:ss"
                    placeholder="执行日期时间" />
                <template v-if="scope === 'ide'">
                <el-select v-model="draft.task_id" filterable placeholder="选择流程" @change="draft.node_id = ''">
                        <el-option v-for="task in tasks" :key="task.task_id" :label="task.task_name" :value="task.task_id" />
                    </el-select>
                    <el-select v-model="draft.node_id" filterable placeholder="从哪个节点执行">
                        <el-option v-for="node in selectedTaskNodes" :key="node.node_id" :label="node.node_name" :value="node.node_id" />
                    </el-select>
                </template>
                <template v-else>
                    <el-select v-model="draft.profile_name" clearable placeholder="运行配置方案（可选）">
                        <el-option v-for="profile in profiles" :key="profile.name" :label="profile.name" :value="profile.name" />
                    </el-select>
                    <div class="form-note">到点后使用 Player 已配置的入口运行当前实例；可先绑定一个配置方案。</div>
                </template>
                <el-switch v-model="draft.enabled" active-text="启用" inactive-text="停用" />
                <el-button type="primary" :loading="saving" @click="save"><CalendarPlus :size="15" /> {{ draft.id ? '保存修改' : '添加计划' }}</el-button>
                <el-button v-if="draft.id" @click="resetDraft">取消编辑</el-button>
            </div>

            <div class="schedule-list" v-loading="loading">
                <div v-if="!schedules.length" class="empty">暂无计划任务</div>
                <div v-for="item in schedules" :key="item.id" class="schedule-row">
                    <div class="schedule-main">
                        <strong>{{ item.name }}</strong>
                        <span>{{ scheduleLabel(item) }}</span>
                        <small>下次：{{ formatTime(item.next_run_at) }}</small>
                        <small v-if="item.last_status">上次：{{ item.last_status }}<template v-if="item.last_error"> · {{ item.last_error }}</template></small>
                    </div>
                    <el-tag size="small" :type="item.enabled ? 'success' : 'info'">{{ item.enabled ? '启用' : '停用' }}</el-tag>
                    <el-button text title="编辑" @click="edit(item)"><Pencil :size="14" /></el-button>
                    <el-button text type="danger" title="删除" :loading="deletingId === item.id" :disabled="Boolean(deletingId)" @click="remove(item)"><Trash2 :size="14" /></el-button>
                </div>
            </div>
        </div>
        <template #footer>
            <span class="outbox">离线消息队列：待发送 {{ outbox.pending || 0 }}，失败停放 {{ outbox.dead || 0 }}</span>
            <el-button @click="load"><RefreshCw :size="14" /> 刷新</el-button>
            <el-button type="primary" @click="$emit('update:modelValue', false)">关闭</el-button>
        </template>
    </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CalendarPlus, Pencil, RefreshCw, Trash2 } from 'lucide-vue-next'
import { platformApi } from '@/api/platformApi'

const props = defineProps({
    modelValue: { type: Boolean, default: false },
    scope: { type: String, default: 'ide' },
    tasks: { type: Array, default: () => [] },
    instanceId: { type: String, default: 'instance-1' },
    profiles: { type: Array, default: () => [] }
})
defineEmits(['update:modelValue'])
const schedules = ref([])
const loading = ref(false)
const saving = ref(false)
const deletingId = ref('')
const outbox = reactive({})
const defaults = () => ({ id: '', name: '', schedule_type: 'daily', schedule_value: '08:00:00', task_id: '', node_id: '', profile_name: '', enabled: true })
const draft = reactive(defaults())
const selectedTaskNodes = computed(() => props.tasks.find(task => task.task_id === draft.task_id)?.nodes || [])

const resetDraft = () => Object.assign(draft, defaults())
const load = async () => {
    if (loading.value) return
    loading.value = true
    try {
        const [scheduleResult, outboxResult] = await Promise.all([
            platformApi.listSchedules(props.scope), platformApi.outboxStatus(props.scope)
        ])
        schedules.value = scheduleResult?.schedules || []
        Object.assign(outbox, outboxResult || {})
    } catch (error) {
        ElMessage.error(error.message || '计划任务加载失败')
    } finally {
        loading.value = false
    }
}
const validate = () => {
    if (!draft.name.trim()) return '请输入计划名称'
    if (!draft.schedule_value) return '请选择计划时间'
if (props.scope === 'ide' && (!draft.task_id || !draft.node_id)) return '请选择流程和起始节点'
    return ''
}
const save = async () => {
    const error = validate()
    if (error) return ElMessage.warning(error)
    saving.value = true
    try {
        await platformApi.saveSchedule({
            id: draft.id || undefined,
            name: draft.name.trim(), schedule_type: draft.schedule_type,
            schedule_value: String(draft.schedule_value), enabled: draft.enabled,
            payload: props.scope === 'ide'
                ? { task_id: draft.task_id, node_id: draft.node_id }
                : { instance_id: props.instanceId, profile_name: draft.profile_name || '' }
        }, props.scope)
        ElMessage.success(draft.id ? '计划已更新' : '计划已添加')
        resetDraft()
        await load()
    } catch (requestError) {
        ElMessage.error(requestError.message || '保存计划失败')
    } finally {
        saving.value = false
    }
}
const edit = item => {
    Object.assign(draft, defaults(), item, item.payload || {})
    if (draft.schedule_type === 'interval') draft.schedule_value = Number(draft.schedule_value || 1)
}
const remove = async item => {
    if (deletingId.value) return
    try {
        await ElMessageBox.confirm(`确定删除计划「${item.name}」吗？`, '删除计划', { type: 'warning' })
        deletingId.value = item.id
        await platformApi.deleteSchedule(item.id, props.scope)
        if (draft.id === item.id) resetDraft()
        await load()
        ElMessage.success('计划已删除')
    } catch (error) {
        const action = String(error?.action || error || '').toLowerCase()
        if (!['cancel', 'close'].includes(action)) ElMessage.error(error?.message || '删除计划失败')
    } finally {
        deletingId.value = ''
    }
}
const formatTime = value => value ? new Date(value * 1000).toLocaleString() : '未安排'
const scheduleLabel = item => ({ daily: `每天 ${item.schedule_value}`, interval: `每 ${item.schedule_value} 秒`, once: `一次 ${item.schedule_value}` }[item.schedule_type] || item.schedule_value)
</script>

<style scoped>
.schedule-layout { display:grid; grid-template-columns:250px 1fr; gap:14px; min-height:360px; }
.schedule-form { display:flex; flex-direction:column; gap:9px; padding-right:14px; border-right:1px solid var(--el-border-color); }
.schedule-list { display:flex; flex-direction:column; gap:7px; max-height:430px; overflow:auto; }
.schedule-row { display:grid; grid-template-columns:1fr auto 28px 28px; align-items:center; gap:6px; padding:10px; border:1px solid var(--el-border-color); border-radius:7px; }
.schedule-main { display:flex; flex-direction:column; gap:3px; min-width:0; }
.schedule-main span, .schedule-main small, .form-note, .outbox { color:var(--el-text-color-secondary); font-size:11px; overflow-wrap:anywhere; }
.empty { margin:auto; color:var(--el-text-color-secondary); }
.outbox { margin-right:auto; }
</style>
