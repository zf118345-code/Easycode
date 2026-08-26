<template>
    <section class="page-map-panel">
        <header><button class="open-map" type="button" @click="openMap"><Map :size="15" /><span>页面地图</span><small>{{ pages.length }} 个页面</small></button><button type="button" title="新建区块" aria-label="在页面地图中新建区块" @click="createBlock"><PanelsTopLeft :size="15" /></button></header>
        <label class="search"><Search :size="13" /><input v-model="query" placeholder="搜索页面或操作节点" /></label>
        <div class="map-summary"><div><strong>{{ pages.length }}</strong><span>页面状态</span></div><div><strong>{{ popupPages.length }}</strong><span>随机弹窗</span></div><div><strong>{{ edges.length }}</strong><span>导航连线</span></div></div>
        <div class="map-list">
            <div v-for="item in filteredBlockItems" :key="item.block.block_id" class="block-group">
                <button class="block-row" type="button" @click="focusBlock(item.block)">
                    <ChevronRight :size="13" :class="{ expanded: !collapsed.has(item.block.block_id) }" @click.stop="toggleBlock(item.block.block_id)" />
                    <PanelsTopLeft :size="14" /><span>{{ item.block.name }}</span><small>{{ item.nodes.length }}</small>
                </button>
                <button v-for="node in collapsed.has(item.block.block_id) ? [] : item.nodes" :key="node.node_id" class="page-row nested" type="button" :class="{ selected: store.selectedNodeIds.includes(node.node_id), operation: node.node_type !== 'page_state' }" @click="focusNode(node)">
                    <component :is="getNodeIcon(node.node_type)" :size="14" /><span>{{ node.node_name }}</span><em v-if="node.params?.is_random_popup">弹窗</em><CircleAlert v-if="node.node_type === 'page_state' && !(node.params?.features || []).length" :size="12" title="尚未配置页面特征" />
                </button>
            </div>
            <div v-if="filteredLooseNodes.length" class="section-label"><Unlink2 :size="12" />未归入区块</div>
            <button v-for="node in filteredLooseNodes" :key="node.node_id" class="page-row" type="button" :class="{ selected: store.selectedNodeIds.includes(node.node_id), operation: node.node_type !== 'page_state' }" @click="focusNode(node)">
                <component :is="getNodeIcon(node.node_type)" :size="14" /><span>{{ node.node_name }}</span><em v-if="node.params?.is_random_popup">弹窗</em><CircleAlert v-if="node.node_type === 'page_state' && !(node.params?.features || []).length" :size="12" title="尚未配置页面特征" />
            </button>
            <div v-if="!visibleNodeCount && !filteredBlockItems.length" class="empty"><Map :size="24" /><strong>{{ query ? '没有匹配结果' : '页面地图还是空的' }}</strong><span>在画布上添加页面状态，并用操作节点连接页面之间的路径。</span></div>
        </div>
    </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ChevronRight, CircleAlert, Map, PanelsTopLeft, Search, Unlink2 } from 'lucide-vue-next'
import { useIdeStore } from '@/stores'
import { getNodeIcon } from '@/config/nodeIconsConfig'
import { containedNodeIds, findFreeBlockPosition, normalizeBlock } from '@/utils/canvasBlocks'

const store = useIdeStore()
const query = ref('')
const collapsed = ref(new Set())
const graph = computed(() => store.blueprint?.page_map || { nodes: [], edges: [], blocks: [] })
const pages = computed(() => (graph.value.nodes || []).filter(node => node.node_type === 'page_state'))
const popupPages = computed(() => pages.value.filter(node => node.params?.is_random_popup))
const edges = computed(() => graph.value.edges || [])
const blocks = computed(() => graph.value.blocks || [])
const matches = node => !query.value.trim() || `${node.node_name} ${node.node_type}`.toLowerCase().includes(query.value.trim().toLowerCase())
const renderedNodes = computed(() => (graph.value.nodes || []).map(node => ({ ...node, w: node.size?.w || 160, h: node.size?.h || 96 })))
const blockItems = computed(() => blocks.value.map(block => {
    const ids = new Set(containedNodeIds(block, renderedNodes.value))
    return { block, nodes: (graph.value.nodes || []).filter(node => ids.has(node.node_id)) }
}))
const claimedIds = computed(() => new Set(blockItems.value.flatMap(item => item.nodes.map(node => node.node_id))))
const filteredBlockItems = computed(() => blockItems.value
    .map(item => ({ ...item, nodes: item.nodes.filter(matches) }))
    .filter(item => matches({ node_name: item.block.name, node_type: 'block' }) || item.nodes.length))
const filteredLooseNodes = computed(() => (graph.value.nodes || []).filter(node => !claimedIds.value.has(node.node_id) && matches(node)))
const visibleNodeCount = computed(() => filteredLooseNodes.value.length + filteredBlockItems.value.reduce((sum, item) => sum + item.nodes.length, 0))

async function openMap() { await store.setCanvasMode('topology'); store.setFocusTarget({ type: 'graph', id: 'page_map', timestamp: Date.now() }) }
async function focusNode(node) { await openMap(); store.selectNode(node.node_id); store.setFocusTarget({ type: 'node', id: node.node_id, timestamp: Date.now() }) }
async function focusBlock(block) { await openMap(); store.clearSelection(); store.setFocusTarget({ type: 'block', id: block.block_id, timestamp: Date.now() }) }
function toggleBlock(blockId) { const next = new Set(collapsed.value); next.has(blockId) ? next.delete(blockId) : next.add(blockId); collapsed.value = next }
async function createBlock() {
    await openMap()
    const names = new Set(blocks.value.map(item => item.name)); let name = '新区块', index = 1; while (names.has(name)) name = `新区块${index++}`
    const position = findFreeBlockPosition(blocks.value, { x: 80, y: 80 })
    const block = normalizeBlock({ block_id: `block_${crypto.randomUUID().replaceAll('-', '')}`, name, ...position, width: 400, height: 260 })
    graph.value.blocks.push(block)
    await store.saveTopologyData()
    store.setFocusTarget({ type: 'block', id: block.block_id, timestamp: Date.now() })
}
</script>

<style scoped>
.page-map-panel{height:100%;display:flex;flex-direction:column;background:var(--app-sidebar-bg);color:var(--app-text-primary);font-size:11px}.page-map-panel>header{height:40px;display:flex;align-items:center;gap:4px;padding:0 7px;border-bottom:1px solid var(--app-separator)}header>button{height:29px;display:grid;place-items:center;padding:0 7px;border:0;border-radius:6px;background:transparent;color:var(--app-text-secondary);cursor:pointer}.open-map{min-width:0;flex:1!important;display:flex!important;gap:7px;text-align:left}.open-map span{flex:1;color:var(--app-text-primary);font-weight:650}.open-map small{color:var(--app-text-placeholder);font-size:10px}header>button:hover{background:var(--el-fill-color-light)}.search{height:30px;margin:7px;display:flex;align-items:center;gap:6px;padding:0 7px;border:1px solid var(--app-border-subtle);border-radius:6px;background:var(--app-input-bg)}.search input{min-width:0;flex:1;border:0;outline:0;background:transparent;color:inherit;font:inherit}.map-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;margin:0 7px 7px;background:var(--app-separator);border:1px solid var(--app-separator);border-radius:7px;overflow:hidden}.map-summary div{display:flex;flex-direction:column;gap:2px;padding:7px;background:var(--app-bg-panel);text-align:center}.map-summary strong{font-size:13px}.map-summary span{color:var(--app-text-placeholder);font-size:10px}.map-list{min-height:0;flex:1;overflow:auto;padding:2px 6px 12px}.block-row,.page-row{width:100%;height:29px;display:flex;align-items:center;gap:7px;padding:0 8px;border:0;border-radius:5px;background:transparent;color:var(--app-text-secondary);text-align:left;cursor:pointer}.block-row:hover,.page-row:hover,.page-row.selected{background:var(--el-fill-color-light);color:var(--app-text-primary)}.block-row>svg:first-child{transition:transform .12s ease}.block-row>svg:first-child.expanded{transform:rotate(90deg)}.block-row span,.page-row span{min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.block-row small{color:var(--app-text-placeholder);font-size:10px}.page-row.nested{padding-left:29px}.page-row.selected{box-shadow:inset 2px 0 var(--el-color-primary)}.page-row em{padding:1px 4px;border-radius:4px;background:color-mix(in srgb,var(--el-color-warning) 14%,transparent);color:var(--el-color-warning);font-size:10px;font-style:normal}.page-row>svg:last-child{color:var(--el-color-warning)}.section-label{height:27px;display:flex;align-items:center;gap:6px;padding:0 8px;color:var(--app-text-placeholder);font-size:10px;text-transform:uppercase;letter-spacing:.06em}.empty{min-height:170px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;padding:18px;color:var(--app-text-placeholder);text-align:center}.empty strong{color:var(--app-text-secondary)}.empty span{max-width:220px;line-height:1.5}
</style>
