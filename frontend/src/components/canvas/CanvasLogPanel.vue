<!-- frontend/src/components/canvas/CanvasLogPanel.vue -->
<template>
    <div class="canvas-log-panel-embedded">
        <div ref="logBodyRef" class="log-panel-body">
            <div v-if="!logs.length" class="log-placeholder-text">暂无最新运行日志输出...</div>
            <div v-for="(item, idx) in logs"
                 :key="idx"
                 class="log-line"
                 :class="getLogLevelClass(item)">
                <span class="log-time">[{{ getItemTime(item) }}]</span>
                <span class="log-text">{{ getItemText(item) }}</span>
            </div>
        </div>
    </div>
</template>

<script setup>
    import { ref, computed, watch, nextTick } from 'vue'
    import { useMainStore } from '@/stores'

    const store = useMainStore()
    const logBodyRef = ref(null)

    const logs = computed(() => store.executionLogs || [])

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

    watch(() => logs.value.length, () => {
        nextTick(() => {
            if (logBodyRef.value) {
                logBodyRef.value.scrollTop = logBodyRef.value.scrollHeight
            }
        })
    })
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

    .log-line {
        font-size: 11px;
        line-height: 1.5;
        white-space: pre-wrap;
        word-break: break-all;
        display: flex;
        gap: 6px;
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