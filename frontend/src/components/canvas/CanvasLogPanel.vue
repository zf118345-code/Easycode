<!-- frontend/src/components/canvas/CanvasLogPanel.vue
  运行日志面板（唯一日志入口）：运行控制台与调试执行日志统一展示（同一 executionLogs 数据源）。
  工具栏：自动滚动开关 + 清空。日志由 SSE 实时推送，无需自挂轮询。
-->
<template>
    <div class="canvas-log-panel-embedded">
        <div class="log-toolbar">
            <el-switch
                v-model="autoScroll" size="small" inline-prompt
                active-text="自动滚动" inactive-text="手动滚动" />
            <el-button size="small" type="danger" plain @click="clearLogs">清空</el-button>
        </div>
        <div ref="logBodyRef" class="log-panel-body" @scroll="onScroll">
            <div v-if="!logs.length" class="log-placeholder-text">暂无最新运行日志输出...</div>
            <!-- ⚡ #6 虚拟滚动：只渲染可视区（固定行高窗口化），长任务日志不再拖垮 DOM -->
            <div v-else class="log-virtual-spacer" :style="{ height: totalHeight + 'px' }">
                <div
v-for="(item, i) in visibleLogs"
                     :key="startIndex + i"
                     class="log-line"
                     :class="getLogLevelClass(item)"
                     :style="{ transform: `translateY(${(startIndex + i) * ROW_HEIGHT}px)` }">
                    <span class="log-time">[{{ getItemTime(item) }}]</span>
                    <span class="log-text">{{ getItemText(item) }}</span>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
    import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
    import { useMainStore, useExecutionStore } from '@/stores'

    const store = useMainStore()
    const execStore = useExecutionStore()
    const logBodyRef = ref(null)
    const autoScroll = ref(true)

    // ⚡ #6 虚拟滚动窗口化：固定行高估计 + 可视区渲染（overscan 前后各 10 行）
    const ROW_HEIGHT = 18
    const OVERSCAN = 10
    const scrollTop = ref(0)
    const viewportHeight = ref(300)
    let resizeObserver = null

    const logs = computed(() => store.executionLogs || [])
    const totalHeight = computed(() => logs.value.length * ROW_HEIGHT)
    const startIndex = computed(() => Math.max(0, Math.floor(scrollTop.value / ROW_HEIGHT) - OVERSCAN))
    const endIndex = computed(() =>
        Math.min(logs.value.length, Math.ceil((scrollTop.value + viewportHeight.value) / ROW_HEIGHT) + OVERSCAN))
    const visibleLogs = computed(() => logs.value.slice(startIndex.value, endIndex.value))

    function onScroll() {
        if (logBodyRef.value) scrollTop.value = logBodyRef.value.scrollTop
    }

    const getItemTime = (item) => {
        if (typeof item === 'object' && item !== null) return item.time || 'INFO'
        return 'INFO'
    }

    const getItemText = (item) => {
        if (typeof item === 'object' && item !== null) return item.message || JSON.stringify(item)
        return String(item)
    }

    const getLogLevelClass = (item) => {
        const msg = getItemText(item)
        if (msg.includes('💥') || msg.includes('❌') || msg.includes('ERROR')) return 'log-error'
        if (msg.includes('⚠️') || msg.includes('WARNING')) return 'log-warn'
        if (msg.includes('🎯') || msg.includes('✅')) return 'log-success'
        return 'log-info'
    }

    function clearLogs() {
        execStore.clearLogs?.()
    }

    function scrollToBottom() {
        if (!autoScroll.value) return
        nextTick(() => {
            if (logBodyRef.value) {
                logBodyRef.value.scrollTop = logBodyRef.value.scrollHeight
                scrollTop.value = logBodyRef.value.scrollTop
            }
        })
    }

    watch(() => logs.value.length, scrollToBottom)

    onMounted(() => {
        if (logBodyRef.value) {
            viewportHeight.value = logBodyRef.value.clientHeight || 300
            resizeObserver = new ResizeObserver(() => {
                if (logBodyRef.value) viewportHeight.value = logBodyRef.value.clientHeight || 300
            })
            resizeObserver.observe(logBodyRef.value)
        }
    })
    onUnmounted(() => resizeObserver?.disconnect())
</script>

<style scoped>
    .canvas-log-panel-embedded {
        width: 100%;
        height: 100%;
        background: var(--el-bg-color);
        display: flex;
        flex-direction: column;
        overflow: hidden;
        user-select: text;
    }

    .log-toolbar {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 10px;
        padding: 6px 12px;
        border-bottom: 1px solid var(--el-border-color-lighter);
        background: var(--el-fill-color-lighter);
        flex-shrink: 0;
    }

    .log-panel-body {
        flex: 1;
        padding: 8px 12px;
        font-size: 11px;
        color: var(--el-text-color-regular);
        overflow-y: auto;
        font-family: 'Consolas', 'Courier New', monospace;
    }

    .log-placeholder-text {
        color: var(--el-text-color-placeholder);
        text-align: center;
        padding: 10px 0;
    }

    .log-virtual-spacer {
        position: relative;
        width: 100%;
    }

    .log-line {
        font-size: 11px;
        line-height: 1.5;
        white-space: pre-wrap;
        word-break: break-all;
        display: flex;
        gap: 6px;
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 18px;
        overflow: hidden;
    }

    .log-time {
        color: var(--el-text-color-secondary);
        flex-shrink: 0;
    }

    .log-info {
        color: var(--el-text-color-regular);
    }

    .log-success {
        color: var(--el-color-primary);
    }

    .log-warn {
        color: #e6a23c;
    }

    .log-error {
        color: #f56c6c;
        font-weight: bold;
    }
</style>
