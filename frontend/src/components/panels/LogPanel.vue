<template>
    <div class="log-panel">
        <div class="log-toolbar">
            <span class="log-count">共 {{ logs.length }} 条日志</span>
            <el-button type="info" link size="small" @click="clearLogs">🗑️ 清空日志</el-button>
        </div>
        <div class="log-container" ref="logContainerRef">
            <div v-for="(line, idx) in logs"
                 :key="idx"
                 class="log-line"
                 :class="getLogLevelClass(line)">
                {{ line }}
            </div>
            <div v-if="!logs.length" class="empty-log">
                ⚡ 暂无执行日志，运行任务后将在此处实时显示日志...
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

    // 日志变动自动滚动到底部
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

    const getLogLevelClass = (line) => {
      if (line.includes('[ERROR]') || line.includes('💥')) return 'log-error'
      if (line.includes('[WARNING]') || line.includes('⚠️')) return 'log-warn'
      if (line.includes('🎯') || line.includes('✅')) return 'log-success'
      return 'log-info'
    }

    const clearLogs = () => {
      store.executionLogs = []
    }

    return {
      logs,
      logContainerRef,
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
        gap: 4px;
    }

    .log-line {
        font-size: 12px;
        line-height: 1.5;
        white-space: pre-wrap;
        word-break: break-all;
        color: #a2a7c7;
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

    .empty-log {
        color: #4e5166;
        font-size: 12px;
        text-align: center;
        margin-top: 20px;
    }
</style>