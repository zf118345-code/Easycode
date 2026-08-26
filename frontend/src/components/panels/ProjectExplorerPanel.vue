<template>
    <section class="outline-panel" @click="menu.visible = false">
        <header class="outline-toolbar">
            <button class="project-button" type="button" :title="project.currentProjectPath" @click="openMain">
                <FolderTree :size="15" /><span>{{ projectName }}</span>
            </button>
            <button class="icon-button" type="button" title="在主流程中新建区块" aria-label="在主流程中新建区块" @click="createBlock"><PanelsTopLeft :size="15" /></button>
        </header>
        <label class="outline-search">
            <Search :size="13" />
            <input v-model="query" placeholder="搜索主流程节点或区块" />
            <button v-if="query" type="button" title="清空搜索" aria-label="清空搜索" @click="query = ''"><X :size="12" /></button>
        </label>

        <div class="outline-body" role="tree" aria-label="主流程大纲">
            <button class="root-row" type="button" :class="{ active: isMainCanvas }" @click="openMain">
                <Workflow :size="15" /><span>主流程</span><small>{{ nodes.length }}</small>
            </button>

            <div v-if="!filteredBlocks.length && !filteredLooseNodes.length" class="empty-state">
                <PanelsTopLeft :size="24" />
                <strong>{{ query ? '没有匹配结果' : '主流程还是空的' }}</strong>
                <span>{{ query ? '换一个名称或节点类型试试。' : '在画布右键创建节点；需要整理时再添加区块。' }}</span>
            </div>

            <div v-for="item in filteredBlocks" :key="item.block.block_id" class="block-section">
                <button class="block-row" type="button" :aria-expanded="!collapsed.has(item.block.block_id)" @click="selectBlock(item)" @dblclick.stop="renameBlock(item.block)" @contextmenu.prevent.stop="openMenu($event, 'block', item)">
                    <ChevronRight :size="13" :class="{ expanded: !collapsed.has(item.block.block_id) }" @click.stop="toggle(item.block.block_id)" />
                    <PanelsTopLeft :size="14" /><span>{{ item.block.name }}</span><small>{{ item.nodes.length }}</small>
                </button>
                <button v-for="node in collapsed.has(item.block.block_id) ? [] : item.nodes" :key="node.node_id" class="node-row nested" :class="{ selected: ui.selectedNodeIds.includes(node.node_id), primary: ui.primaryNodeId === node.node_id }" type="button" @click="selectNode($event, node)" @dblclick.stop="renameNode(node)" @contextmenu.prevent.stop="openMenu($event, 'node', node)">
                    <component :is="getNodeIcon(node.node_type)" :size="14" /><span>{{ node.node_name }}</span>
                </button>
            </div>

            <div v-if="filteredLooseNodes.length" class="loose-section">
                <div class="section-label"><Unlink2 :size="12" /><span>未归入区块</span><small>{{ filteredLooseNodes.length }}</small></div>
                <button v-for="node in filteredLooseNodes" :key="node.node_id" class="node-row" :class="{ selected: ui.selectedNodeIds.includes(node.node_id), primary: ui.primaryNodeId === node.node_id }" type="button" @click="selectNode($event, node)" @dblclick.stop="renameNode(node)" @contextmenu.prevent.stop="openMenu($event, 'node', node)">
                    <component :is="getNodeIcon(node.node_type)" :size="14" /><span>{{ node.node_name }}</span>
                </button>
            </div>
        </div>

        <div v-if="menu.visible" class="outline-menu" :style="{ left: `${menu.x}px`, top: `${menu.y}px` }" @click.stop>
            <button v-if="menu.kind === 'node'" type="button" @click="locateNode(menu.target)"><LocateFixed :size="14" />在画布中定位</button>
            <button type="button" @click="menu.kind === 'node' ? renameNode(menu.target) : renameBlock(menu.target.block)"><Pencil :size="14" />重命名</button>
            <button v-if="menu.kind === 'node'" class="danger" type="button" @click="deleteNode(menu.target)"><Trash2 :size="14" />删除节点</button>
            <button v-else class="danger" type="button" @click="deleteBlock(menu.target)"><Trash2 :size="14" />删除区块…</button>
        </div>
    </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChevronRight, FolderTree, LocateFixed, PanelsTopLeft, Pencil, Search, Trash2, Unlink2, Workflow, X } from 'lucide-vue-next'
import { useIdeStore, useUiStore } from '@/stores'
import { getNodeIcon } from '@/config/nodeIconsConfig'
import { containedNodeIds, findFreeBlockPosition, normalizeBlock } from '@/utils/canvasBlocks'
import { findSelectionPath } from '@/utils/graphSelection'
import { MAIN_GRAPH_ID } from '@/utils/flowModel'

const project = useIdeStore()
const ui = useUiStore()
const query = ref('')
const collapsed = ref(new Set())
const menu = reactive({ visible: false, x: 0, y: 0, kind: '', target: null })

const graph = computed(() => project.blueprint?.main_graph || { nodes: [], edges: [], blocks: [] })
const nodes = computed(() => graph.value.nodes || [])
const projectName = computed(() => project.currentProjectName || (project.currentProjectPath || '').split(/[/\\]/).pop() || '当前项目')
const isMainCanvas = computed(() => project.canvasMode === 'workflow' && project.currentTaskId === MAIN_GRAPH_ID)
const renderedNodes = computed(() => nodes.value.map(node => ({ ...node, w: node.size?.w || 160, h: node.size?.h || 96 })))
const blockItems = computed(() => (graph.value.blocks || []).map(block => {
    const ids = new Set(containedNodeIds(block, renderedNodes.value))
    return { block, nodes: nodes.value.filter(node => ids.has(node.node_id)) }
}))
const claimedIds = computed(() => new Set(blockItems.value.flatMap(item => item.nodes.map(node => node.node_id))))
const matches = value => !query.value.trim() || String(value || '').toLowerCase().includes(query.value.trim().toLowerCase())
const filteredBlocks = computed(() => blockItems.value.map(item => ({ ...item, nodes: item.nodes.filter(node => matches(`${node.node_name} ${node.node_type}`)) })).filter(item => matches(item.block.name) || item.nodes.length))
const filteredLooseNodes = computed(() => nodes.value.filter(node => !claimedIds.value.has(node.node_id) && matches(`${node.node_name} ${node.node_type}`)))

async function openMain() {
    ui.clearSelection()
    await project.loadTaskData(MAIN_GRAPH_ID)
    await project.setCanvasMode('workflow')
    ui.setFocusTarget({ type: 'graph', id: MAIN_GRAPH_ID, timestamp: Date.now() })
}

async function createBlock() {
    await openMain()
    const blocks = graph.value.blocks || (graph.value.blocks = [])
    const names = new Set(blocks.map(item => item.name))
    let name = '新区块', index = 1
    while (names.has(name)) name = `新区块${index++}`
    const position = findFreeBlockPosition(blocks, { x: 80, y: 80 })
    const block = normalizeBlock({ block_id: `block_${crypto.randomUUID().replaceAll('-', '')}`, name, ...position, width: 400, height: 260 })
    blocks.push(block)
    await project.saveWorkflowImmediately()
    ui.setFocusTarget({ type: 'block', id: block.block_id, timestamp: Date.now() })
}

function toggle(id) {
    const next = new Set(collapsed.value)
    next.has(id) ? next.delete(id) : next.add(id)
    collapsed.value = next
}

async function selectBlock(item) {
    await openMain()
    ui.selectNodes(item.nodes.map(node => node.node_id), { primaryId: item.nodes[0]?.node_id || null, anchorId: item.nodes[0]?.node_id || null })
    ui.setFocusTarget({ type: 'block', id: item.block.block_id, timestamp: Date.now() })
}

async function selectNode(event, node) {
    await openMain()
    if (event.shiftKey) {
        const anchor = ui.selectionAnchorId || ui.primaryNodeId
        const path = anchor ? findSelectionPath(graph.value.edges, anchor, node.node_id) : null
        if (path) ui.selectPath(path.nodeIds, path.edgeIds, anchor, node.node_id)
        else ui.selectNode(node.node_id)
    } else if (event.ctrlKey || event.metaKey) ui.toggleNodeSelection(node.node_id)
    else ui.selectNode(node.node_id)
    ui.setFocusTarget({ type: 'node', id: node.node_id, timestamp: Date.now() })
}

function locateNode(node) { menu.visible = false; selectNode({}, node) }

async function renameNode(node) {
    menu.visible = false
    try {
        const result = await ElMessageBox.prompt('节点名称只影响阅读，不改变稳定 ID。', '重命名节点', { inputValue: node.node_name, inputPattern: /\S+/, inputErrorMessage: '名称不能为空', confirmButtonText: '保存', cancelButtonText: '取消' })
        node.node_name = result.value.trim()
        await project.saveWorkflowImmediately()
    } catch { /* cancel */ }
}

async function renameBlock(block) {
    menu.visible = false
    try {
        const result = await ElMessageBox.prompt('区块只用于整理画布，不影响执行语义。', '重命名区块', { inputValue: block.name, inputPattern: /\S+/, inputErrorMessage: '名称不能为空', confirmButtonText: '保存', cancelButtonText: '取消' })
        block.name = result.value.trim()
        await project.saveWorkflowImmediately()
    } catch { /* cancel */ }
}

async function deleteNode(node) {
    menu.visible = false
    if (node.fixed) return ElMessage.warning('固定入口节点不能删除')
    try { await ElMessageBox.confirm(`删除节点“${node.node_name}”？相关连线也会删除，可使用撤销恢复。`, '删除节点', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }) } catch { return }
    graph.value.nodes = nodes.value.filter(item => item.node_id !== node.node_id)
    graph.value.edges = (graph.value.edges || []).filter(edge => edge.source_node !== node.node_id && edge.target_node !== node.node_id)
    ui.clearSelection()
    await project.saveWorkflowImmediately()
}

async function deleteBlock(item) {
    menu.visible = false
    let deleteNodes = false
    try {
        await ElMessageBox.confirm(`区块“${item.block.name}”完整包含 ${item.nodes.length} 个节点。默认只删除区块。`, '删除区块', { type: 'warning', distinguishCancelAndClose: true, confirmButtonText: '仅删除区块', cancelButtonText: item.nodes.length ? '区块和节点一起删除' : '取消', closeOnClickModal: false })
    } catch (action) {
        if (action !== 'cancel' || !item.nodes.length) return
        deleteNodes = true
    }
    graph.value.blocks = (graph.value.blocks || []).filter(block => block.block_id !== item.block.block_id)
    if (deleteNodes) {
        const ids = new Set(item.nodes.filter(node => !node.fixed).map(node => node.node_id))
        graph.value.nodes = nodes.value.filter(node => !ids.has(node.node_id))
        graph.value.edges = (graph.value.edges || []).filter(edge => !ids.has(edge.source_node) && !ids.has(edge.target_node))
    }
    await project.saveWorkflowImmediately()
}

function openMenu(event, kind, target) {
    menu.visible = true
    menu.kind = kind
    menu.target = target
    menu.x = event.clientX
    menu.y = event.clientY
}
</script>

<style scoped>
.outline-panel{height:100%;min-width:0;display:flex;flex-direction:column;background:var(--app-sidebar-bg);color:var(--app-text-primary);font-size:12px}.outline-toolbar{height:40px;display:flex;align-items:center;gap:4px;padding:0 7px;border-bottom:1px solid var(--app-separator)}.project-button{min-width:0;flex:1;height:30px;display:flex;align-items:center;gap:7px;padding:0 7px;border:0;border-radius:6px;background:transparent;color:inherit;text-align:left;cursor:pointer}.project-button:hover,.icon-button:hover{background:var(--el-fill-color-light)}.project-button span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:650}.icon-button{width:28px;height:28px;display:grid;place-items:center;padding:0;border:0;border-radius:6px;background:transparent;color:var(--app-text-secondary);cursor:pointer}.outline-search{height:34px;margin:7px;display:flex;align-items:center;gap:6px;padding:0 8px;border:1px solid var(--app-border-subtle);border-radius:6px;background:var(--app-input-bg)}.outline-search:focus-within{border-color:var(--el-color-primary)}.outline-search input{min-width:0;flex:1;border:0;outline:0;background:transparent;color:inherit;font:inherit}.outline-search button{display:grid;place-items:center;padding:2px;border:0;background:transparent;color:var(--app-text-placeholder);cursor:pointer}.outline-body{min-height:0;flex:1;overflow:auto;padding:2px 6px 12px}.root-row,.block-row,.node-row{width:100%;height:29px;display:flex;align-items:center;gap:7px;padding:0 7px;border:0;border-radius:5px;background:transparent;color:inherit;text-align:left;cursor:pointer}.root-row:hover,.block-row:hover,.node-row:hover{background:var(--el-fill-color-light)}.root-row.active{color:var(--el-color-primary);background:var(--app-color-primary-dim)}.root-row span,.block-row span,.node-row span{min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.root-row small,.block-row small,.section-label small{color:var(--app-text-placeholder);font-size:10px}.block-section{margin-top:2px}.block-row{color:var(--app-text-secondary);font-weight:600}.block-row>svg:first-child{transition:transform .12s ease}.block-row>svg:first-child.expanded{transform:rotate(90deg)}.node-row{padding-left:25px;color:var(--app-text-secondary)}.node-row.nested{padding-left:43px}.node-row.selected{background:var(--app-color-primary-dim);color:var(--app-text-primary)}.node-row.primary{box-shadow:inset 2px 0 var(--el-color-primary)}.section-label{height:27px;display:flex;align-items:center;gap:6px;padding:0 8px;margin-top:5px;color:var(--app-text-placeholder);font-size:10.5px;text-transform:uppercase;letter-spacing:.04em}.section-label span{flex:1}.empty-state{min-height:180px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;padding:18px;color:var(--app-text-placeholder);text-align:center}.empty-state strong{color:var(--app-text-secondary);font-size:12px}.empty-state span{max-width:220px;font-size:10.5px;line-height:1.5}.outline-menu{position:fixed;z-index:6000;min-width:180px;padding:5px;border:1px solid var(--app-overlay-border);border-radius:8px;background:var(--app-overlay-bg);box-shadow:var(--app-shadow-lg)}.outline-menu button{width:100%;height:30px;display:flex;align-items:center;gap:8px;padding:0 8px;border:0;border-radius:5px;background:transparent;color:var(--app-text-primary);font-size:11px;text-align:left;cursor:pointer}.outline-menu button:hover{background:var(--el-fill-color-light)}.outline-menu button.danger{color:var(--el-color-danger)}
</style>
