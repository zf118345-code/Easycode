<template>
    <el-dialog v-model="visible" title="全局搜索与引用查找" width="760px" append-to-body @opened="focusInput">
        <el-input
            ref="inputRef"
            v-model="query"
            size="large"
            clearable
            placeholder="搜索主流程、函数、页面、变量或资源… (Ctrl+P)"
            role="combobox"
            aria-controls="global-search-results"
            :aria-expanded="visible"
            :aria-activedescendant="activeResultId"
            @keydown.down.prevent="moveActiveResult(1)"
            @keydown.up.prevent="moveActiveResult(-1)"
            @keydown.enter.prevent="activateCurrentResult"
            @keydown.esc.stop="visible = false" />
        <div class="search-layout">
            <div id="global-search-results" class="results-pane" role="listbox" aria-label="搜索结果">
                <div class="pane-title">结果 {{ results.length }}</div>
                <button
                    v-for="(item, resultIndex) in results"
                    :id="resultDomId(item)"
                    :key="`${item.kind}:${item.id}`"
                    type="button"
                    role="option"
                    class="result-row"
                    :class="{ 'is-active': activeResultIndex === resultIndex }"
                    :aria-selected="activeResultIndex === resultIndex"
                    :disabled="activating"
                    @click="activate(item)"
                    @mouseenter="setActiveResult(resultIndex)">
                    <span class="kind">{{ kindLabel[item.kind] || item.kind }}</span>
                    <span class="result-copy"><strong>{{ item.title }}</strong><small>{{ item.subtitle }}</small></span>
                </button>
                <div v-if="!results.length" class="empty">没有匹配项</div>
            </div>
            <div class="refs-pane">
                <div class="pane-title">引用 {{ references.length }}</div>
                <div v-if="selected" class="selected-title">{{ selected.title }}</div>
                <button v-for="item in references" :key="`${item.kind}:${item.id}`" type="button" class="result-row" @click="activate(item)">
                    <span class="kind">{{ kindLabel[item.kind] || item.kind }}</span>
                    <span class="result-copy"><strong>{{ item.title }}</strong><small>{{ item.subtitle }}</small></span>
                </button>
                <div v-if="selected && !references.length" class="empty">当前对象没有被其他节点引用</div>
            </div>
        </div>
    </el-dialog>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useIdeStore, useProjectStore, useUiStore } from '@/stores'
import { MAIN_GRAPH_ID } from '@/utils/flowModel'
import { buildSearchIndex, findReferences, searchIndex } from '@/utils/searchIndex'

const visible = defineModel({ type: Boolean, default: false })
const projectStore = useProjectStore()
const uiStore = useUiStore()
const ideStore = useIdeStore()
const query = ref('')
const selected = ref(null)
const inputRef = ref(null)
const activeResultIndex = ref(-1)
const activating = ref(false)
const kindLabel = { main: '主流程', function: '函数', page_map: '页面地图', node: '节点', page: '页面', variable: '变量', template: '资源' }
const searchRecords = computed(() => buildSearchIndex(projectStore.blueprint))
const results = computed(() => searchIndex(searchRecords.value, query.value))
const references = computed(() => selected.value ? findReferences(searchRecords.value, selected.value.kind, selected.value.id) : [])
const resultDomId = item => `global-search-result-${item.kind}-${item.id}`.replace(/[^a-zA-Z0-9_-]/g, '-')
const activeResultId = computed(() => {
    const item = results.value[activeResultIndex.value]
    return item ? resultDomId(item) : undefined
})

const setActiveResult = index => {
    activeResultIndex.value = index
    selected.value = results.value[index] || null
}
const moveActiveResult = direction => {
    const count = results.value.length
    if (!count) return setActiveResult(-1)
    const current = activeResultIndex.value < 0 ? (direction > 0 ? -1 : 0) : activeResultIndex.value
    setActiveResult((current + direction + count) % count)
}
const focusInput = () => nextTick(() => {
    inputRef.value?.focus()
    if (results.value.length) setActiveResult(0)
})
const activateCurrentResult = () => {
    const item = results.value[activeResultIndex.value]
    if (item) activate(item)
}
const activate = async (item) => {
    if (!item || activating.value) return
    activating.value = true
    selected.value = item
    try {
        if (item.canvas === 'topology') await ideStore.navigateToGraph('topology')
        else if (item.canvas === 'function') await ideStore.navigateToGraph('function', item.taskId || item.id)
        else if (item.canvas === 'workflow') await ideStore.navigateToGraph('workflow', item.taskId || MAIN_GRAPH_ID)
        if (item.nodeId) {
            uiStore.selectNode(item.nodeId)
            uiStore.setFocusTarget({ nodeId: item.nodeId, taskId: item.taskId, at: Date.now() })
            visible.value = false
        } else if (item.kind === 'main' || item.kind === 'function' || item.kind === 'page_map') {
            visible.value = false
        }
    } catch (error) {
        ElMessage.error(error?.message || '无法打开搜索结果，请先处理当前画布的保存错误')
    } finally {
        activating.value = false
    }
}

watch(results, value => {
    if (!value.length) setActiveResult(-1)
    else setActiveResult(Math.min(Math.max(activeResultIndex.value, 0), value.length - 1))
})

watch(visible, isVisible => {
    if (!isVisible) {
        activating.value = false
        activeResultIndex.value = -1
        selected.value = null
    }
})
</script>

<style scoped>
.search-layout { display:grid; grid-template-columns:1fr 1fr; gap:12px; height:420px; margin-top:12px; }
.results-pane,.refs-pane { overflow:auto; border:1px solid var(--el-border-color); border-radius:8px; padding:6px; }
.pane-title { position:sticky; top:-6px; z-index:1; padding:8px; background:var(--el-bg-color); color:var(--el-text-color-secondary); font-size:12px; }
.selected-title { padding:6px 8px; color:var(--el-color-primary); font-size:12px; }
.result-row { width:100%; border:0; background:transparent; color:inherit; display:flex; gap:8px; text-align:left; padding:8px; border-radius:6px; cursor:pointer; }
.result-row:hover,.result-row.is-active { background:var(--el-fill-color-light); }
.result-row.is-active { box-shadow:inset 2px 0 var(--el-color-primary); }
.result-row:disabled { cursor:progress; opacity:.68; }
.kind { flex:0 0 34px; font-size:10px; color:var(--el-color-primary); padding-top:2px; }
.result-copy { min-width:0; display:flex; flex-direction:column; gap:3px; }
.result-copy strong,.result-copy small { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.result-copy small,.empty { color:var(--el-text-color-secondary); font-size:11px; }
.empty { padding:18px 8px; text-align:center; }
</style>
