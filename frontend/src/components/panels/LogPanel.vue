<!-- frontend/src/components/panels/LogPanel.vue -->
<template>
    <div class="log-panel">
        <div class="log-toolbar">
            <span class="log-count">共 {{ logs.length }} 条日志 ({{ runStatus }})</span>
            <el-button type="info" link size="small" @click="clearLogs">🗑️ 清空日志</el-button>
        </div>
        <div class="log-container" ref="logContainerRef">
            <div
v-for="(item, idx) in logs"
                 :key="idx"
                 class="log-line"
                 :class="getLogLevelClass(item)">
                <span class="log-time">[{{ item.time || 'INFO' }}]</span>
                <span class="log-text">{{ item.message }}</span>

                <!-- 调试截图悬浮预览 -->
                <template v-if="item.image">
                    <el-popover placement="left" :width="350" trigger="hover" append-to-body>
                        <template #reference>
                            <el-tag size="small" type="success" class="img-badge">🖼️ 查看调试截图</el-tag>
                        </template>
                        <div class="img-preview-card">
                            <div class="preview-title">🎯 实际框选识别区域图像</div>
                            <img :src="item.image" style="width: 100%; border-radius: 4px; border: 1px solid #67C23A;" />
                        </div>
                    </el-popover>
                </template>
            </div>
            <div v-if="!logs.length" class="empty-log">
                ⚡ 暂无执行日志，点击“运行”后将在此处实时显示...
            </div>
        </div>
    </div>
</template>

<script setup>
    import { ref, watch, nextTick, onUnmounted } from 'vue'
    import { useMainStore } from '@/stores'

    const store = useMainStore()
    const logContainerRef = ref(null)
    const logs = ref([])
    const runStatus = ref('就绪')

    let eventSource = null

    // 监听 store 中当前活跃的 executionId 并自动开启 SSE 订阅
    watch(() => store.currentExecutionId, (execId) => {
        if (eventSource) {
            eventSource.close()
            eventSource = null
        }

        if (!execId) return

        logs.value = []
        eventSource = new EventSource(`/api/execution/${execId}/stream`)

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)
                if (data.status) {
                    runStatus.value = data.status.message || data.status.status
                }
                if (data.logs && data.logs.length > 0) {
                    logs.value.push(...data.logs)
                }
                if (data.status && ['success', 'error'].includes(data.status.status)) {
                    eventSource.close()
                    eventSource = null
                }
            } catch (e) {
                console.error('解析 SSE 数据异常', e)
            }
        }

        eventSource.onerror = () => {
            if (eventSource) {
                eventSource.close()
                eventSource = null
            }
        }
    }, { immediate: true })

    watch(() => logs.value.length, () => {
        nextTick(() => {
            if (logContainerRef.value) {
                logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
            }
        })
    })

    const getLogLevelClass = (item) => {
        const msg = item.message || ''
        if (msg.includes('💥') || msg.includes('❌') || msg.includes('ERROR')) return 'log-error'
        if (msg.includes('⚠️') || msg.includes('WARNING')) return 'log-warn'
        if (msg.includes('🎯') || msg.includes('✅')) return 'log-success'
        return 'log-info'
    }

    const clearLogs = () => {
        logs.value = []
    }

    onUnmounted(() => {
        if (eventSource) {
            eventSource.close()
        }
    })
</script>

<style scoped>
    .log-panel {
        display: flex;
        flex-direction: column;
        height: 100%;
        background: var(--el-bg-color-page);
        font-family: 'Consolas', 'Courier New', monospace;
    }

    .log-toolbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 12px;
        background: var(--el-bg-color);
        border-bottom: 1px solid var(--el-border-color-light);
        font-size: 11px;
    }

    .log-count {
        color: var(--el-text-color-secondary);
    }

    .log-container {
        flex: 1;
        padding: 8px 12px;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .log-line {
        font-size: 12px;
        line-height: 1.5;
        white-space: pre-wrap;
        word-break: break-all;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .log-time {
        color: var(--el-text-color-secondary);
        font-size: 11px;
        flex-shrink: 0;
    }

    .log-text {
        flex: 1;
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

    .img-badge {
        cursor: pointer;
        margin-left: 6px;
    }

    .preview-title {
        font-size: 12px;
        font-weight: bold;
        color: var(--el-color-primary);
        margin-bottom: 6px;
    }

    .empty-log {
        color: var(--el-text-color-placeholder);
        font-size: 12px;
        text-align: center;
        margin-top: 20px;
    }
</style>