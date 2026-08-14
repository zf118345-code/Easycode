<!-- frontend/src/components/panels/ExecutionLogPanel.vue -->
<template>
    <div class="app-panel execution-log-panel">
        <div class="app-panel-header">
            <div class="app-panel-title">
                <ScrollText size="14" />
                <span>调试执行日志</span>
                <el-tag v-if="currentExecutionId" size="small" type="primary" class="tag-session">
                    #{{ String(currentExecutionId).slice(-6) }}
                </el-tag>
            </div>
            <div class="app-panel-actions">
                <el-button size="small" :icon="ScrollText" @click="manualPoll" :disabled="!currentExecutionId">
                    刷新
                </el-button>
                <el-button size="small" type="danger" plain @click="clearLogs">清空</el-button>
                <el-switch
v-model="autoScroll" size="small" inline-prompt
                           active-text="自动滚动" inactive-text="手动滚动" />
            </div>
        </div>

        <!-- 日志列表 -->
        <div ref="logListRef" class="log-list">
            <div v-if="!logs || logs.length === 0" class="log-empty">
                <Terminal size="32" class="empty-icon" />
                <div class="empty-text">暂无执行日志</div>
                <div class="empty-sub">运行工作流后将在这里显示节点执行结果、状态、SSE 事件流。</div>
            </div>

            <div
v-for="(log, i) in logs" :key="i"
                 class="log-row"
                 :class="[ 'level-' + (log.level || 'info'), { 'is-err': log.level === 'error' || log.level === 'fatal' } ]">
                <span class="log-time">[{{ log.timestamp || formatTime(log.time || Date.now()) }}]</span>
                <span class="log-level">{{ (log.level || 'info').toUpperCase() }}</span>
                <span class="log-node" v-if="log.node_id || log.nodeId">
                    📍{{ log.node_id || log.nodeId }}
                </span>
                <span class="log-state" v-if="log.state || log.status">
                    🔁{{ log.state || log.status }}
                </span>
                <span class="log-msg">{{ log.message || log.msg || log.text || JSON.stringify(log) }}</span>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { ScrollText, Terminal } from 'lucide-vue-next'
import { useExecutionStore } from '@/stores'

const execStore = useExecutionStore()
const logs = computed(() => execStore.executionLogs || [])
const currentExecutionId = computed(() => execStore.currentExecutionId)

const logListRef = ref(null)
const autoScroll = ref(true)

function formatTime(t) {
    try {
        const d = new Date(t)
        const pad = n => String(n).padStart(2, '0')
        return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${String(d.getMilliseconds()).padStart(3,'0')}`
    } catch { return '' }
}

async function manualPoll() {
    try { await execStore.pollDebugState?.() } catch (_) {}
}

function clearLogs() { execStore.clearLogs?.() }

function scrollToBottom() {
    if (!autoScroll.value) return
    nextTick(() => {
        const el = logListRef.value
        if (el) el.scrollTop = el.scrollHeight
    })
}

let pollTimer = null
onMounted(() => {
    scrollToBottom()
    pollTimer = setInterval(() => {
        if (execStore.isRunning || execStore.isPaused) {
            manualPoll()
        }
    }, 1500)
})
onUnmounted(() => {
    if (pollTimer) clearInterval(pollTimer)
})

watch(() => logs.value.length, () => scrollToBottom())
watch(() => currentExecutionId.value, () => scrollToBottom())
</script>

<style scoped>
.execution-log-panel { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.log-list {
    flex: 1; overflow-y: auto;
    font-family: ui-monospace, Consolas, 'JetBrains Mono', Menlo, monospace;
    font-size: 12px; line-height: 1.7;
    padding: 10px 14px;
    background: #0e0f1a;
    color: #cfd3e6;
}
.log-row {
    padding: 2px 0; border-bottom: 1px dashed rgba(255,255,255,0.04);
    display: flex; gap: 8px; flex-wrap: wrap; align-items: baseline;
    white-space: pre-wrap; word-break: break-word;
}
.log-time  { color: #6e7499; flex-shrink: 0; }
.log-level { flex-shrink: 0; min-width: 56px; font-weight: 700; }
.level-info .log-level   { color: #4ed19c; }
.level-warn .log-level, .level-warning .log-level { color: #ffb020; }
.level-error .log-level, .is-err .log-level { color: #f56c6c; }
.level-debug .log-level { color: #95a0ff; }
.level-success .log-level { color: #4ed19c; }

.log-node, .log-state {
    padding: 0 6px; border-radius: 4px;
    background: rgba(255,255,255,0.04);
    color: #b8bfe0; font-size: 11px; flex-shrink: 0;
}
.log-state { color: #ffb020; }
.log-msg { color: #e6e9f5; }

.log-empty {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    height: 100%; color: #6e7499; gap: 8px;
}
.empty-icon { opacity: .4; }
.empty-text { font-size: 14px; color: #95a0c2; }
.empty-sub  { font-size: 12px; color: #5e6387; }

.tag-session { margin-left: 8px; font-family: monospace; }
</style>
