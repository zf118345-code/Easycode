<!--
  调试工具栏组件（工业级风格）：
  提供 ▶ 运行/开始、⏸ 暂停、▶ 继续、⏹ 停止、⏭ 单步跳过(F10)、⏬ 单步进入(F11)、⏫ 单步跳出(Shift+F11)
  同时显示：执行状态、断点总数量、当前激活节点 ID
-->
<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { useMainStore, useExecutionStore, useUiStore } from '@/stores'
import { ElMessage } from 'element-plus'
import {
    Play, Pause, Square, SkipForward, ArrowDownToLine, ArrowUpFromLine, CircleDot, CircleDashed, Clock, Target
} from 'lucide-vue-next'

const store = useMainStore()
const execStore = useExecutionStore()
const uiStore = useUiStore()

// ===== 当前选择任务（若无选中任务则禁用 ▶ 运行） =====
const selectedTaskId = computed(() => store.currentTaskId)
const hasTasks = computed(() => (store.blueprint?.tasks?.length || 0) > 0)

const isRunning = computed(() => execStore.isRunning)
const isPaused = computed(() => execStore.isPaused)
const isStopped = computed(() => !isRunning.value && !isPaused.value)
const breakpointCount = computed(() => uiStore.getBreakpointList?.()?.length ?? uiStore.breakpoints?.size ?? 0)
const currentActiveNodeId = computed(() => execStore.currentActiveNodeId)
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

// ===== 操作 =====
async function runSelectedTask() {
    if (!selectedTaskId.value) {
        ElMessage.warning('请先在左侧列表中选中一个任务再运行')
        return
    }
    try {
        const result = await execStore.runTask(selectedTaskId.value)
        if (result?.status === 'started') ElMessage.success('任务已启动')
        else ElMessage.error('启动失败：' + JSON.stringify(result || {}))
    } catch (err) {
        ElMessage.error('启动失败：' + err.message)
    }
}
async function pauseExec() { try { await execStore.pauseExecution(); ElMessage.info('已请求暂停') } catch(e){ ElMessage.error(e.message) } }
async function resumeExec() { try { await execStore.resumeExecution(); ElMessage.info('继续执行') } catch(e){ ElMessage.error(e.message) } }
async function stopExec() {
    try {
        await execStore.stopExecution()
        ElMessage.info('已停止执行')
    } catch (e) { ElMessage.error(e.message) }
}
async function stepOver() { try { await execStore.stepOverExecution() } catch(e){ ElMessage.error(e.message) } }
async function stepInto() { try { await execStore.stepIntoExecution() } catch(e){ ElMessage.error(e.message) } }
async function stepOut()  { try { await execStore.stepOutExecution()  } catch(e){ ElMessage.error(e.message) } }
function clearAllBreakpoints() {
    uiStore.clearBreakpoints()
    ElMessage.info('已清除所有断点')
}

// ===== 快捷键 F5/F9/F10/F11/Shift+F11 =====
function _onDebugHotkey(e) {
    const key = e.key || ''
    if (e.target && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return

    // F5：继续/重跑
    if (key === 'F5') {
        e.preventDefault(); e.stopPropagation()
        if (isPaused.value) resumeExec()
        else if (isStopped.value) runSelectedTask()
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
    // F10：单步跳过
    if (key === 'F10') { e.preventDefault(); e.stopPropagation(); if (isPaused.value) stepOver() }
    // F11：单步进入
    if (key === 'F11' && !e.shiftKey) { e.preventDefault(); e.stopPropagation(); if (isPaused.value) stepInto() }
    // Shift+F11：单步跳出
    if (key === 'F11' && e.shiftKey) { e.preventDefault(); e.stopPropagation(); if (isPaused.value) stepOut() }
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

        <!-- ▶ 运行（停止/就绪时可用） -->
        <button
class="dbg-btn" :disabled="isRunning && !isPaused || !hasTasks"
                @click="runSelectedTask" title="运行选中任务 (F5)">
            <Play class="dbg-icon" :size="16" />
            <span class="dbg-hint">F5</span>
        </button>

        <!-- ⏸ 暂停（运行中可用） -->
        <button class="dbg-btn" :disabled="!isRunning || isPaused" @click="pauseExec" title="暂停 (请求)">
            <Pause class="dbg-icon" :size="16" />
        </button>

        <!-- ▶ 继续（暂停时可用，与 F5 统一） -->
        <button class="dbg-btn primary" :disabled="!isPaused" @click="resumeExec" title="继续执行 (F5)">
            <Play class="dbg-icon" :size="16" />
            <span class="dbg-hint">F5</span>
        </button>

        <!-- ⏭ 单步跳过（暂停时可用） -->
        <button class="dbg-btn" :disabled="!isPaused" @click="stepOver" title="单步跳过 Step Over (F10)">
            <SkipForward class="dbg-icon" :size="16" />
            <span class="dbg-hint">F10</span>
        </button>

        <!-- ⏬ 单步进入 -->
        <button class="dbg-btn" :disabled="!isPaused" @click="stepInto" title="单步进入 Step Into (F11)">
            <ArrowDownToLine class="dbg-icon" :size="16" />
            <span class="dbg-hint">F11</span>
        </button>

        <!-- ⏫ 单步跳出 -->
        <button class="dbg-btn" :disabled="!isPaused" @click="stepOut" title="单步跳出 Step Out (Shift+F11)">
            <ArrowUpFromLine class="dbg-icon" :size="16" />
            <span class="dbg-hint">S+F11</span>
        </button>

        <div class="dbg-sep" />

        <!-- ⏹ 停止 -->
        <button class="dbg-btn danger" :disabled="!isRunning && !isPaused" @click="stopExec" title="停止 (Shift+F5)">
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

        <!-- 激活节点 -->
        <div v-if="currentActiveNodeId" class="dbg-meta active-node" title="当前调试命中节点">
            <Target class="dbg-active-icon" :size="12" />
            <span class="dbg-meta-label">命中：</span>
            <span class="dbg-node-id">{{ currentActiveNodeId }}</span>
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
