<!-- frontend/src/components/panels/VariableInspectorPanel.vue
  变量监控（调试时仪表盘）：展示暂停时的变量快照——当前值 vs 上一节点值，便于单步对比观察。
  数据全部来自 executionStore（轮询由 store 统一管理，面板零自建请求），
  暗色绿主题：变化值绿色高亮淡出，无彩色类型标签。
-->
<template>
    <div class="app-panel variable-inspector">
        <div class="app-panel-header">
            <div class="app-panel-title">
                <Activity size="14" />
                <span>变量监控</span>
            </div>
            <div class="app-panel-actions">
                <span v-if="store.isPaused" class="status-text is-paused">● 已暂停<template v-if="store.currentActiveNodeId"> @ {{ store.currentActiveNodeId }}</template></span>
                <span v-else-if="store.isRunning" class="status-text is-running">● 运行中</span>
                <span v-else class="status-text">○ 未启动</span>
            </div>
        </div>

        <div class="app-panel-toolbar">
            <el-input
                v-model="searchText"
                size="small"
                placeholder="搜索变量..."
                clearable
                class="var-search">
                <template #prefix><Search size="12" /></template>
            </el-input>
            <span class="var-count">{{ filteredList.length }} 个变量</span>
        </div>

        <div class="app-panel-body">
            <!-- 变量列表：变量名 | 当前值 | 上一节点值 -->
            <div v-if="filteredList.length > 0" class="var-table">
                <div class="var-row var-head">
                    <span class="var-cell var-name">变量名</span>
                    <span class="var-cell var-value">当前值</span>
                    <span class="var-cell var-value">上一节点值</span>
                </div>
                <div
                    v-for="item in filteredList"
                    :key="item.name"
                    class="var-row"
                    :class="{ 'is-changed': item.changed }">
                    <span class="var-cell var-name" :title="item.name">{{ item.name }}</span>
                    <span class="var-cell var-value" :title="item.current">{{ item.current }}</span>
                    <span class="var-cell var-value is-prev" :title="item.prev">{{ item.prev }}</span>
                </div>
            </div>
            <div v-else class="app-panel-empty">
                <Activity size="28" />
                <span v-if="store.isPaused">暂无变量</span>
                <span v-else>暂停后显示变量快照（当前值 vs 上一节点值）</span>
            </div>
        </div>
    </div>
</template>

<script setup>
    import { ref, computed } from 'vue'
    import { Activity, Search } from 'lucide-vue-next'
    import { useMainStore } from '@/stores'

    const store = useMainStore()
    const searchText = ref('')

    function formatValue(value) {
        if (value === null || value === undefined) return 'null'
        if (typeof value === 'string') return value
        if (typeof value === 'number' || typeof value === 'boolean') return String(value)
        try {
            const s = JSON.stringify(value)
            return s && s.length > 60 ? s.slice(0, 60) + '…' : s
        } catch {
            return String(value)
        }
    }

    // 合并当前/上一快照为对比列表（以当前值为准，上一值缺省显示 —）
    const variableList = computed(() => {
        const current = store.executionCurrentVariables || {}
        const prev = store.executionPrevVariables || {}
        const names = new Set([...Object.keys(current), ...Object.keys(prev)])
        const list = []
        for (const name of names) {
            const cur = formatValue(current[name])
            const pre = name in prev ? formatValue(prev[name]) : '—'
            list.push({
                name,
                current: cur,
                prev: pre,
                changed: name in prev && cur !== pre
            })
        }
        return list.sort((a, b) => a.name.localeCompare(b.name))
    })

    const filteredList = computed(() => {
        const q = searchText.value.trim().toLowerCase()
        if (!q) return variableList.value
        return variableList.value.filter(v => v.name.toLowerCase().includes(q))
    })
</script>

<style scoped>
    .variable-inspector {
        height: 100%;
        display: flex;
        flex-direction: column;
    }

    .status-text {
        font-size: 11px;
        color: var(--el-text-color-secondary);
    }
    .status-text.is-paused { color: #e5484d; }
    .status-text.is-running { color: #4ed19c; }

    .var-search {
        max-width: 160px;
    }
    .var-count {
        font-size: 11px;
        color: var(--el-text-color-secondary);
        margin-left: 8px;
    }

    .var-table {
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 8px;
        overflow: hidden;
    }
    .var-row {
        display: flex;
        align-items: center;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        font-size: 12px;
        transition: background 0.3s;
    }
    .var-row:last-child { border-bottom: none; }
    .var-row.is-changed { background: rgba(78, 209, 156, 0.1); }
    .var-row.is-changed .var-value { color: #4ed19c; }

    .var-head {
        background: rgba(255, 255, 255, 0.03);
        color: var(--el-text-color-secondary);
        font-size: 11px;
    }
    .var-cell {
        padding: 6px 10px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .var-name {
        flex: 1.2;
        font-family: monospace;
        color: var(--el-text-color-regular);
        min-width: 0;
    }
    .var-value {
        flex: 1;
        color: var(--el-text-color-regular);
        min-width: 0;
        font-family: monospace;
    }
    .var-value.is-prev {
        color: var(--el-text-color-secondary);
    }
</style>
