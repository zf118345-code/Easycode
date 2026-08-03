<template>
    <div class="log-panel">
        <div class="log-toolbar">
            <span class="log-count">共 {{ logs.length }} 条日志</span>
            <el-button type="info" link size="small" @click="clearLogs">🗑️ 清空日志</el-button>
        </div>
        <div class="log-container" ref="logContainerRef">
            <div v-for="(item, idx) in logs"
                 :key="idx"
                 class="log-line"
                 :class="getLogLevelClass(item)">
                <span class="log-time">[{{ getItemTime(item) }}]</span>
                <span class="log-text">{{ getItemText(item) }}</span>

                <!-- ⭐ 调试截图悬浮预览 -->
                <template v-if="getItemImage(item)">
                    <el-popover placement="left" :width="350" trigger="hover" append-to-body>
                        <template #reference>
                            <el-tag size="small" type="success" class="img-badge">🖼️ 查看调试截图</el-tag>
                        </template>
                        <div class="img-preview-card">
                            <div class="preview-title">🎯 实际框选识别区域图像</div>
                            <img :src="getItemImage(item)" style="width: 100%; border-radius: 4px; border: 1px solid #67C23A;" />
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

<script>
    import { computed, ref, watch, nextTick } from 'vue'
    import { useMainStore } from '@/stores'

    export default {
        name: 'LogPanel',
        setup() {
            const store = useMainStore()
            const logContainerRef = ref(null)

            const logs = computed(() => store.executionLogs || [])

            watch(
                () => logs.value.length,
                () => {
                    nextTick(() => {
                        if (logContainerRef.value) {
                            logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
                        }
                    })
                }
            )

            const getItemTime = (item) => {
                if (typeof item === 'object' && item !== null) return item.time || 'INFO'
                return 'INFO'
            }

            const getItemText = (item) => {
                if (typeof item === 'object' && item !== null) return item.message || JSON.stringify(item)
                return String(item)
            }

            const getItemImage = (item) => {
                if (typeof item === 'object' && item !== null) return item.image || null
                return null
            }

            const getLogLevelClass = (item) => {
                const msg = getItemText(item)
                if (msg.includes('💥') || msg.includes('❌') || msg.includes('ERROR')) return 'log-error'
                if (msg.includes('⚠️') || msg.includes('WARNING')) return 'log-warn'
                if (msg.includes('🎯') || msg.includes('✅')) return 'log-success'
                return 'log-info'
            }

            const clearLogs = () => {
                store.executionLogs = []
            }

            return {
                logs,
                logContainerRef,
                getItemTime,
                getItemText,
                getItemImage,
                getLogLevelClass,
                clearLogs
            }
        }
    }
</script>

<style scoped>
    .log-panel {
        display: flex;
        flex-direction: column;
        height: 100%;
        background: #0f0f19;
        font-family: 'Consolas', 'Courier New', monospace;
    }

    .log-toolbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 12px;
        background: #181824;
        border-bottom: 1px solid #2d2d3f;
        font-size: 11px;
    }

    .log-count {
        color: #8a8fa8;
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
        color: #6a6a8a;
        font-size: 11px;
        flex-shrink: 0;
    }

    .log-text {
        flex: 1;
    }

    .log-info {
        color: #cfd3e6;
    }

    .log-success {
        color: #67c23a;
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
        color: #67C23A;
        margin-bottom: 6px;
    }

    .empty-log {
        color: #4e5166;
        font-size: 12px;
        text-align: center;
        margin-top: 20px;
    }
</style>