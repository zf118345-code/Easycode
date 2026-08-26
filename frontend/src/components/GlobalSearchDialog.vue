<template>
    <el-dialog v-model="visible" title="全局搜索与引用查找" width="760px" append-to-body @opened="focusInput">
        <el-input ref="inputRef" v-model="query" size="large" clearable placeholder="搜索主流程、函数、页面、变量或资源… (Ctrl+P)" />
        <div class="search-layout">
            <div class="results-pane">
                <div class="pane-title">结果 {{ results.length }}</div>
                <button v-for="item in results" :key="`${item.kind}:${item.id}`" class="result-row" @click="activate(item)" @mouseenter="selected = item">
                    <span class="kind">{{ kindLabel[item.kind] || item.kind }}</span>
                    <span class="result-copy"><strong>{{ item.title }}</strong><small>{{ item.subtitle }}</small></span>
                </button>
                <div v-if="!results.length" class="empty">没有匹配项</div>
            </div>
            <div class="refs-pane">
                <div class="pane-title">引用 {{ references.length }}</div>
                <div v-if="selected" class="selected-title">{{ selected.title }}</div>
                <button v-for="item in references" :key="`${item.kind}:${item.id}`" class="result-row" @click="activate(item)">
                    <span class="kind">{{ kindLabel[item.kind] || item.kind }}</span>
                    <span class="result-copy"><strong>{{ item.title }}</strong><small>{{ item.subtitle }}</small></span>
                </button>
                <div v-if="selected && !references.length" class="empty">当前对象没有被其他节点引用</div>
            </div>
        </div>
    </el-dialog>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import { useIdeStore, useProjectStore, useUiStore } from '@/stores'
import { buildSearchIndex, findReferences, searchIndex } from '@/utils/searchIndex'

const visible = defineModel({ type: Boolean, default: false })
const projectStore = useProjectStore()
const uiStore = useUiStore()
const ideStore = useIdeStore()
const query = ref('')
const selected = ref(null)
const inputRef = ref(null)
const kindLabel = { main: '主流程', function: '函数', page_map: '页面地图', node: '节点', page: '页面', variable: '变量', template: '资源' }
const index = computed(() => buildSearchIndex(projectStore.blueprint))
const results = computed(() => searchIndex(index.value, query.value))
const references = computed(() => selected.value ? findReferences(index.value, selected.value.kind, selected.value.id) : [])

const focusInput = () => nextTick(() => inputRef.value?.focus())
const activate = async (item) => {
    selected.value = item
    if (item.canvas === 'topology') await ideStore.setCanvasMode('topology')
    else if (item.canvas === 'function') { await projectStore.loadTaskData(item.taskId); await ideStore.setCanvasMode('function') }
    else if (item.canvas === 'workflow') await ideStore.setCanvasMode('workflow')
    if (item.taskId && item.canvas !== 'topology') await projectStore.loadTaskData(item.taskId)
    if (item.nodeId) {
        uiStore.selectNode(item.nodeId)
        uiStore.setFocusTarget({ nodeId: item.nodeId, taskId: item.taskId, at: Date.now() })
        visible.value = false
    } else if (item.kind === 'main' || item.kind === 'function') {
        await projectStore.loadTaskData(item.id)
        visible.value = false
    }
}
</script>

<style scoped>
.search-layout { display:grid; grid-template-columns:1fr 1fr; gap:12px; height:420px; margin-top:12px; }
.results-pane,.refs-pane { overflow:auto; border:1px solid var(--el-border-color); border-radius:8px; padding:6px; }
.pane-title { position:sticky; top:-6px; z-index:1; padding:8px; background:var(--el-bg-color); color:var(--el-text-color-secondary); font-size:12px; }
.selected-title { padding:6px 8px; color:var(--el-color-primary); font-size:12px; }
.result-row { width:100%; border:0; background:transparent; color:inherit; display:flex; gap:8px; text-align:left; padding:8px; border-radius:6px; cursor:pointer; }
.result-row:hover { background:var(--el-fill-color-light); }
.kind { flex:0 0 34px; font-size:10px; color:var(--el-color-primary); padding-top:2px; }
.result-copy { min-width:0; display:flex; flex-direction:column; gap:3px; }
.result-copy strong,.result-copy small { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.result-copy small,.empty { color:var(--el-text-color-secondary); font-size:11px; }
.empty { padding:18px 8px; text-align:center; }
</style>
