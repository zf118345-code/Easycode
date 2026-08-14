<!-- frontend/src/components/panels/VariableInspectorPanel.vue -->
<template>
    <div class="app-panel variable-inspector">
        <div class="app-panel-header">
            <div class="app-panel-title">
                <Bug size="14" />
                <span>变量检查器</span>
            </div>
            <div class="app-panel-actions">
                <el-tag v-if="sessionState.is_paused" size="small" type="warning">已暂停</el-tag>
                <el-tag v-else-if="sessionState.is_running" size="small" type="success">运行中</el-tag>
                <el-tag v-else size="small" type="info">未启动</el-tag>
            </div>
        </div>

        <div class="app-panel-toolbar">
            <el-button size="small" @click="resumeExecution" :disabled="!sessionState.is_paused">
                <Play size="12" /> 继续
            </el-button>
            <el-button size="small" @click="stepExecution" :disabled="!sessionState.is_paused">
                <ChevronRight size="12" /> 单步
            </el-button>
            <el-button size="small" @click="pauseExecution" :disabled="!sessionState.is_running || sessionState.is_paused">
                <Pause size="12" /> 暂停
            </el-button>
            <el-button size="small" type="danger" @click="stopExecution" :disabled="!sessionState.is_running">
                <Square size="12" /> 停止
            </el-button>
            <el-divider direction="vertical" />
            <el-button size="small" @click="refreshState" :disabled="!sessionId">
                <RefreshCw size="12" /> 刷新
            </el-button>
        </div>

        <div class="app-panel-body">
            <!-- 当前执行位置 -->
            <div v-if="sessionState.current_node_id" class="current-position">
                <div class="position-label">当前位置:</div>
                <div class="position-value">
                    <el-tag size="small" type="success">{{ sessionState.current_task_id }}</el-tag>
                    <span class="node-id">{{ sessionState.current_node_id }}</span>
                </div>
            </div>

            <!-- 调用栈 -->
            <div v-if="callStack.length > 0" class="call-stack-section">
                <div class="section-title">调用栈</div>
                <div v-for="(frame, idx) in callStack" :key="idx" class="stack-frame">
                    <span class="frame-index">{{ idx + 1 }}</span>
                    <span class="frame-task">{{ frame.task_id }}</span>
                    <span class="frame-node" v-if="frame.start_node_id">← {{ frame.start_node_id }}</span>
                </div>
            </div>

            <!-- 变量列表 -->
            <div class="variables-section">
                <div class="section-title">
                    运行时变量 ({{ variableList.length }})
                </div>
                <el-table v-if="variableList.length > 0" :data="variableList" size="small" border>
                    <el-table-column prop="name" label="变量名" width="160" />
                    <el-table-column prop="type" label="类型" width="80">
                        <template #default="{ row }">
                            <el-tag size="small" :type="getTypeTag(row.type)">{{ row.type }}</el-tag>
                        </template>
                    </el-table-column>
                    <el-table-column prop="value" label="值" show-overflow-tooltip />
                </el-table>
                <div v-else class="app-panel-empty">
                    <Variable size="32" />
                    <span>暂无运行时变量</span>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Bug, Play, Pause, Square, ChevronRight, RefreshCw, Variable } from 'lucide-vue-next'
import client from '@/api/client'
import { logger } from '@/utils/logger'

const props = defineProps({
    sessionId: { type: String, default: null }
})

const sessionState = ref({
    is_paused: false,
    is_running: false,
    current_node_id: null,
    current_task_id: null,
    pause_reason: null,
    breakpoints: [],
    variables: {},
    executor_variables: {},
    call_stack: [],
    visited_count: {}
})

let pollTimer = null

const variableList = computed(() => {
    const vars = sessionState.value.executor_variables || sessionState.value.variables || {}
    return Object.entries(vars).map(([name, value]) => ({
        name,
        value: formatValue(value),
        type: getType(value)
    }))
})

const callStack = computed(() => {
    return sessionState.value.call_stack || []
})

function formatValue(value) {
    if (value === null) return 'null'
    if (value === undefined) return 'undefined'
    if (typeof value === 'string') return value
    if (typeof value === 'number' || typeof value === 'boolean') return String(value)
    try {
        return JSON.stringify(value)
    } catch {
        return String(value)
    }
}

function getType(value) {
    if (value === null) return 'null'
    if (Array.isArray(value)) return 'array'
    return typeof value
}

function getTypeTag(type) {
    const map = { string: '', number: 'success', boolean: 'warning', array: 'info', object: 'info', null: 'danger' }
    return map[type] || ''
}

async function refreshState() {
    if (!props.sessionId) return
    try {
        const res = await client.get(`/api/debug/${props.sessionId}/state`)
        sessionState.value = res
    } catch (err) {
        logger.error('VariableInspector', '获取调试状态失败', err)
    }
}

async function resumeExecution() {
    if (!props.sessionId) return
    try {
        await client.post(`/api/debug/${props.sessionId}/resume`)
        ElMessage.success('已恢复执行')
        setTimeout(refreshState, 200)
    } catch (err) {
        logger.error('VariableInspector', '恢复执行失败', err)
    }
}

async function stepExecution() {
    if (!props.sessionId) return
    try {
        await client.post(`/api/debug/${props.sessionId}/step`)
        ElMessage.info('单步执行中...')
        setTimeout(refreshState, 300)
    } catch (err) {
        logger.error('VariableInspector', '单步执行失败', err)
    }
}

async function pauseExecution() {
    if (!props.sessionId) return
    try {
        await client.post(`/api/debug/${props.sessionId}/pause`)
        ElMessage.warning('已暂停')
        setTimeout(refreshState, 200)
    } catch (err) {
        logger.error('VariableInspector', '暂停失败', err)
    }
}

async function stopExecution() {
    if (!props.sessionId) return
    try {
        await client.post(`/api/debug/${props.sessionId}/stop`)
        ElMessage.success('已停止调试')
        sessionState.value.is_running = false
    } catch (err) {
        logger.error('VariableInspector', '停止调试失败', err)
    }
}

function startPolling() {
    stopPolling()
    if (props.sessionId) {
        pollTimer = setInterval(refreshState, 1000)
    }
}

function stopPolling() {
    if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
    }
}

watch(() => props.sessionId, (newVal) => {
    if (newVal) {
        refreshState()
        startPolling()
    } else {
        stopPolling()
    }
})

onMounted(() => {
    if (props.sessionId) {
        refreshState()
        startPolling()
    }
})

onUnmounted(() => {
    stopPolling()
})
</script>

<style scoped>
.variable-inspector {
    height: 100%;
}

.current-position {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--app-color-primary-dim);
    border-radius: var(--app-radius-sm);
    margin-bottom: 12px;
}

.position-label {
    font-size: var(--app-font-sm);
    color: var(--el-text-color-secondary);
}

.position-value {
    display: flex;
    align-items: center;
    gap: 6px;
}

.node-id {
    font-size: var(--app-font-sm);
    color: var(--app-color-primary);
    font-family: monospace;
}

.section-title {
    font-size: var(--app-font-sm);
    font-weight: 600;
    color: var(--el-text-color-regular);
    margin: 12px 0 8px;
    padding-bottom: 4px;
    border-bottom: 1px solid var(--app-panel-border);
}

.call-stack-section {
    margin-bottom: 16px;
}

.stack-frame {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 8px;
    font-size: var(--app-font-sm);
    color: var(--el-text-color-regular);
}

.frame-index {
    color: var(--el-text-color-secondary);
    min-width: 20px;
}

.frame-task {
    color: var(--app-color-primary);
    font-family: monospace;
}

.frame-node {
    color: var(--el-text-color-secondary);
    font-size: var(--app-font-xs);
}

.variables-section {
    flex: 1;
}

:deep(.el-table) {
    background: transparent;
    --el-table-bg-color: transparent;
    --el-table-tr-bg-color: transparent;
    --el-table-header-bg-color: var(--app-panel-header-bg);
    --el-table-border-color: var(--app-panel-border);
}
</style>
