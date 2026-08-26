<template>
    <section class="page-map-panel">
        <label class="search"><Search :size="13" /><input v-model="query" placeholder="搜索页面或操作节点" /></label>
        <div class="map-summary"><div><strong>{{ pages.length }}</strong><span>页面状态</span></div><div><strong>{{ popupPages.length }}</strong><span>随机弹窗</span></div><div><strong>{{ edges.length }}</strong><span>导航连线</span></div></div>
        <div class="map-list">
            <button
                v-for="node in filteredNodes"
                :key="node.node_id"
                class="page-row"
                type="button"
                :class="{ selected: store.selectedNodeIds.includes(node.node_id), operation: node.node_type !== 'page_state' }"
                @click="focusNode(node)">
                <component :is="getNodeIcon(node.node_type)" :size="14" />
                <span>{{ node.node_name }}</span>
                <small>{{ getNodeTypeLabel(node.node_type) }}</small>
                <em v-if="node.params?.is_random_popup">弹窗</em>
                <CircleAlert v-if="node.node_type === 'page_state' && !(node.params?.features || []).length" :size="12" title="尚未配置页面特征" />
            </button>
            <div v-if="!filteredNodes.length" class="empty"><Map :size="24" /><strong>{{ query ? '没有匹配结果' : '页面地图还是空的' }}</strong><span>在画布上添加页面状态，并用操作节点连接页面之间的路径。</span></div>
        </div>
    </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { CircleAlert, Map, Search } from 'lucide-vue-next'
import { useIdeStore } from '@/stores'
import { getNodeIcon } from '@/config/nodeIconsConfig'
import { getNodeConfig } from '@/config/nodeRegistry'
import { notifyActionError } from '@/utils/userActionErrors'

const store = useIdeStore()
const query = ref('')
const graph = computed(() => store.blueprint?.page_map || { nodes: [], edges: [] })
const pages = computed(() => (graph.value.nodes || []).filter(node => node.node_type === 'page_state'))
const popupPages = computed(() => pages.value.filter(node => node.params?.is_random_popup))
const edges = computed(() => graph.value.edges || [])
const getNodeTypeLabel = type => getNodeConfig(type, store.paramsDefinitions).label
const filteredNodes = computed(() => {
    const keyword = query.value.trim().toLowerCase()
    if (!keyword) return graph.value.nodes || []
    return (graph.value.nodes || []).filter(node => `${node.node_name} ${node.node_type} ${getNodeTypeLabel(node.node_type)}`.toLowerCase().includes(keyword))
})

async function openMap() {
    try {
        await store.navigateToGraph('topology')
        store.setFocusTarget({ type: 'graph', id: 'page_map', timestamp: Date.now() })
        return true
    } catch (error) {
        notifyActionError(error, '无法打开页面地图')
        return false
    }
}

async function focusNode(node) {
    if (!await openMap()) return
    store.selectNode(node.node_id)
    store.setFocusTarget({ type: 'node', id: node.node_id, timestamp: Date.now() })
}
</script>

<style scoped>
.page-map-panel{height:100%;display:flex;flex-direction:column;background:var(--app-sidebar-bg);color:var(--app-text-primary);font-size:11px}.search{height:30px;margin:7px;display:flex;align-items:center;gap:6px;padding:0 7px;border:1px solid var(--app-border-subtle);border-radius:6px;background:var(--app-input-bg)}.search:focus-within{border-color:var(--el-color-primary);box-shadow:var(--focus-ring)}.search input{min-width:0;flex:1;border:0;outline:0;background:transparent;color:inherit;font:inherit}.map-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;margin:0 7px 7px;background:var(--app-separator);border:1px solid var(--app-separator);border-radius:7px;overflow:hidden}.map-summary div{display:flex;flex-direction:column;gap:2px;padding:7px;background:var(--app-bg-panel);text-align:center}.map-summary strong{font-size:13px}.map-summary span{color:var(--app-text-placeholder);font-size:10px}.map-list{min-height:0;flex:1;overflow:auto;padding:2px 6px 12px}.page-row{width:100%;height:29px;display:flex;align-items:center;gap:7px;padding:0 8px;border:0;border-radius:5px;background:transparent;color:var(--app-text-secondary);text-align:left;cursor:pointer}.page-row:hover,.page-row.selected{background:var(--el-fill-color-light);color:var(--app-text-primary)}.page-row.selected{box-shadow:inset 2px 0 var(--el-color-primary)}.page-row span{min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.page-row small{max-width:70px;overflow:hidden;color:var(--app-text-placeholder);font-size:10px;text-overflow:ellipsis;white-space:nowrap}.page-row em{padding:1px 4px;border-radius:4px;background:color-mix(in srgb,var(--el-color-warning) 14%,transparent);color:var(--el-color-warning);font-size:10px;font-style:normal}.page-row>svg:last-child{color:var(--el-color-warning)}.empty{min-height:170px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;padding:18px;color:var(--app-text-placeholder);text-align:center}.empty strong{color:var(--app-text-secondary)}.empty span{max-width:220px;line-height:1.5}
</style>
