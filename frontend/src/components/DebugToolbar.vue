<!--
  调试工具栏（三态主控版）：
  ① 主控按钮：就绪=运行（需选中节点）/ 运行中=暂停 / 暂停=运行到下一个断点
  ② 下一步（仅暂停时可用） ③ 停止（运行中/暂停时可用，退出并复位）
  状态徽标 + 断点计数 + 命中节点
-->
<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { useMainStore, useExecutionStore, useUiStore } from '@/stores'
import { ElMessage } from 'element-plus'
import {
    Play, Pause, Square, SkipForward, CircleDot, CircleDashed, Clock, Target
} from 'lucide-vue-next'

const store = useMainStore()
const execStore = useExecutionStore()
const uiStore = useUiStore()

const hasTasks = computed(() => (store.blueprint?.tasks?.length || 0) > 0)

const isRunning = computed(() => execStore.isRunning)
const isPaused = computed(() => execStore.isPaused)
const isStopped = computed(() => !isRunning.value && !isPaused.value)
const breakpointCount = computed(() => uiStore.getBreakpointList?.()?.length ?? uiStore.breakpoints?.size ?? 0)
const currentActiveNodeId = computed(() => execStore.currentActiveNodeId)
const activeNodeLabel = computed(() => {
    // 命中显示节点名（找不到回落 node_id）
    const id = currentActiveNodeId.value
    if (!id) return ''
    const tasks = store.blueprint?.tasks || []
    for (const task of tasks) {
        const found = (task.nodes || []).find(n => n.node_id === id)
        if (found) return found.node_name || id
    }
    return id
})
const stateText = computed(() => {
    if (isPaused.value) return '已暂停'
    if (isRunning.value) return '执行中'
    return '就绪'
})
const stateClass = computed(() => ({
    'state-stopped': isStopped.value,
    'state-running': isRunning.value,
    'state-paused': isPaused.value,
}))

// ===== 主控按钮：就绪=从选中节点运行 / 运行中=暂停 / 暂停=继续到下一断点 =====
const selectedRunNodeId = computed(() => uiStore.selectedNodeIds?.[0] || uiStore.selectedNodeId || null)
const mainBtnDisabled = computed(() => {
    if (isRunning.value || isPaused.value) return false
    return !hasTasks.value || !selectedRunNodeId.value
})
const mainBtnTitle = computed(() => {
    if (isPaused.value) return '继续运行到下一个断点 (F5)'
    if (isRunning.value) return '暂停 (F6)'
    if (!selectedRunNodeId.value) return '请先在画布中选中一个节点'
    return '从选中节点开始运行 (F5)'
})
const mainBtnHint = computed(() => (isPaused.value ? 'F5' : isRunning.value ? 'F6' : 'F5'))

function findTaskIdByNode(nodeId) {
    const tasks = store.blueprint?.tasks || []
    for (const task of tasks) {
        if ((task.nodes || []).some(n => n.node_id === nodeId)) return task.task_id
    }
    return null
}

// ===== 操作 =====
async function runSelectedTask() {
    const nodeId = selectedRunNodeId.value
    if (!nodeId) {
        ElMessage.warning('请先在画布中选中一个节点再运行')
        return
    }
    const taskId = findTaskIdByNode(nodeId)
    if (!taskId) {
        ElMessage.warning('未找到该节点所属的任务')
        return
    }
    try {
        const result = await execStore.runTask(taskId, nodeId)
        if (result?.status === 'started') ElMessage.success('任务已启动')
        else ElMessage.error('启动失败：' + (result?.error || JSON.stringify(result || {})))
    } catch (err) {
        ElMessage.error('启动失败：' + err.message)
    }
}
async function handleMainButton() {
    if (isPaused.value || isRunning.value) {
        await togglePause()  // 暂停→继续 / 运行中→暂停
        return
    }
    await runSelectedTask()
}
async function togglePause() {
    try {
        if (isPaused.value) {
            await execStore.resumeExecution()
            ElMessage.info('继续执行')
        } else {
            await execStore.pauseExecution()
            ElMessage.info('已请求暂停')
        }
    } catch (e) { ElMessage.error(e.message) }
}
async function stopExec() {
    try {
        await execStore.stopExecution()
        ElMessage.info('已停止执行')
    } catch (e) { ElMessage.error(e.message) }
}
async function stepNext() { try { await execStore.stepOverExecution() } catch(e){ ElMessage.error(e.message) } }
function clearAllBreakpoints() {
    uiStore.clearBreakpoints()
    ElMessage.info('已清除所有断点')
}

// ===== 快捷键 F5/F6/F9/F10/Shift+F5 =====
function _onDebugHotkey(e) {
    const key = e.key || ''
    if (e.target && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return

    // F5：运行 / 继续
    if (key === 'F5' && !e.shiftKey) {
        e.preventDefault(); e.stopPropagation()
        if (isPaused.value) togglePause()
        else if (isStopped.value) runSelectedTask()
        return
    }
    // F6：暂停（运行中）
    if (key === 'F6') {
        e.preventDefault(); e.stopPropagation()
        if (isRunning.value && !isPaused.value) togglePause()
        return
    }
    // F9：切换当前选中节点的断点
    if (key === 'F9') {
        e.preventDefault(); e.stopPropagation()
        const sel = uiStore.selectedNodeId
        if (!sel) { ElMessage.warning('请先选中一个节点，然后按 F9 切换断点'); return }
        const added = uiStore.toggleBreakpoint(sel)
        ElMessage.info(added ? '🔴 已设置断点' : '⚪ 已移除断点')
        return
    }
    // F10：下一步（暂停时）
    if (key === 'F10') { e.preventDefault(); e.stopPropagation(); if (isPaused.value) stepNext() }
    // Shift+F5：停止
    if (key === 'F5' && e.shiftKey) { e.preventDefault(); e.stopPropagation(); stopExec() }
}
onMounted(() => window.addEventListener('keydown', _onDebugHotkey, true))
onUnmounted(() => window.removeEventListener('keydown', _onDebugHotkey, true))
</script>

<template>
    <div class="debug-toolbar">
        <!-- 状态徽标 -->
        <div class="dbg-state" :class="stateClass">
            <CircleDot v-if="isPaused" class="state-icon" />
            <Clock v-else-if="isRunning" class="state-icon" />
            <CircleDashed v-else class="state-icon" />
            <span class="state-label">{{ stateText }}</span>
        </div>

        <div class="dbg-sep" />

        <!-- ① 主控按钮：就绪=运行（需选中节点）/ 运行中=暂停 / 暂停=运行到下一个断点 -->
        <button
            class="dbg-btn"
            :class="{ primary: isPaused }"
            :disabled="mainBtnDisabled"
            @click="handleMainButton"
            :title="mainBtnTitle">
            <Pause v-if="isRunning && !isPaused" class="dbg-icon" :size="16" />
            <Play v-else class="dbg-icon" :size="16" />
            <span class="dbg-hint">{{ mainBtnHint }}</span>
        </button>

        <!-- ② 下一步：仅暂停时可用（执行当前节点后暂停，不跳到断点） -->
        <button class="dbg-btn" :disabled="!isPaused" @click="stepNext" title="下一步，执行当前节点后暂停 (F10)">
            <SkipForward class="dbg-icon" :size="16" />
            <span class="dbg-hint">F10</span>
        </button>

        <!-- ③ 停止：运行中/暂停时可用（退出流程并复位为未启动状态） -->
        <button class="dbg-btn danger" :disabled="!isRunning && !isPaused" @click="stopExec" title="停止，退出流程并复位 (Shift+F5)">
            <Square class="dbg-icon" :size="16" />
            <span class="dbg-hint">S+F5</span>
        </button>

        <div class="dbg-sep" />

        <!-- 断点统计 -->
        <div class="dbg-meta" title="总断点数量 (F9 切换选中节点断点)">
            <span class="bp-dot-inline" />
            <span class="dbg-count">{{ breakpointCount }}</span>
            <span class="dbg-meta-label">断点</span>
            <button v-if="breakpointCount > 0" class="dbg-mini-btn" @click="clearAllBreakpoints" title="清除所有断点">清除</button>
        </div>

        <!-- 激活节点（显示节点名；与断点无关，仅指示当前执行位置） -->
        <div v-if="currentActiveNodeId" class="dbg-meta active-node" title="当前执行节点">
            <Target class="dbg-active-icon" :size="12" />
            <span class="dbg-meta-label">执行：</span>
            <span class="dbg-node-id">{{ activeNodeLabel }}</span>
        </div>
    </div>
</template>

<style scoped>
.debug-toolbar {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background: var(--el-bg-color-page, #1a1b2e);
    border: 1px solid var(--el-border-color-lighter, #2a2c48);
    border-radius: 10px;
    flex-wrap: nowrap;
    user-select: none;
}
.dbg-sep { width: 1px; height: 22px; background: var(--el-border-color-lighter); margin: 0 4px; opacity: .7; }

.dbg-btn {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 6px 10px; min-height: 30px;
    background: var(--el-fill-color-light);
    color: var(--el-text-color-regular);
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 6px;
    cursor: pointer;
    transition: all .15s;
    font-size: 12px;
}
.dbg-btn:hover:not(:disabled) { background: var(--el-color-primary); color: #fff; border-color: var(--el-color-primary); }
.dbg-btn:disabled { opacity: .35; cursor: not-allowed; }
.dbg-btn.primary { background: rgba(78, 209, 156, 0.12); color: #4ed19c; border-color: rgba(78, 209, 156, 0.4); }
.dbg-btn.primary:hover:not(:disabled) { background: #4ed19c; color: #1a1a1a; }
.dbg-btn.danger { color: #f56c6c; }
.dbg-btn.danger:hover:not(:disabled) { background: #f56c6c; color: #fff; border-color: #f56c6c; }

.dbg-icon { flex-shrink: 0; }
.dbg-hint {
    font-size: 10px; opacity: .7; font-weight: 600;
    padding: 1px 4px; border-radius: 3px;
    background: rgba(255,255,255,0.06);
}

.dbg-state {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 10px; border-radius: 999px;
    font-size: 12px; font-weight: 600;
    border: 1px solid var(--el-border-color-lighter);
}
.state-stopped { color: var(--el-text-color-secondary); }
.state-running { color: #4ed19c; background: rgba(78, 209, 156, 0.1); border-color: rgba(78, 209, 156, 0.4); }
.state-paused  { color: #ffb020; background: rgba(255, 176, 32, 0.1); border-color: rgba(255, 176, 32, 0.4); }
.state-icon    { width: 12px; height: 12px; }

.dbg-meta {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 10px; border-radius: 6px;
    font-size: 12px;
    background: var(--el-fill-color-lighter);
    color: var(--el-text-color-regular);
}
.dbg-count { font-weight: 700; color: var(--el-color-danger, #e5484d); min-width: 18px; text-align: center; }
.dbg-meta-label { opacity: .7; }
.dbg-mini-btn {
    font-size: 11px;
    padding: 1px 6px; margin-left: 4px;
    background: rgba(229,72,77,0.12); color: #e5484d;
    border: 1px solid rgba(229,72,77,0.35);
    border-radius: 4px; cursor: pointer;
}
.dbg-mini-btn:hover { background: #e5484d; color: #fff; }

.dbg-meta.active-node { background: rgba(255,176,32,0.1); color: #ffb020; border: 1px solid rgba(255,176,32,0.35); }
.dbg-active-icon { font-size: 12px; }
.dbg-node-id { font-family: monospace; font-weight: 600; }

.bp-dot-inline {
    display: inline-block; width: 10px; height: 10px; border-radius: 50%;
    background: #e5484d; box-shadow: 0 0 4px rgba(229, 72, 77, 0.7);
}
</style>
