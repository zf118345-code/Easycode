<template>
    <section class="outline-panel" @click="menu.visible = false">
        <label class="outline-search">
            <Search :size="13" />
            <input v-model="query" placeholder="搜索主流程节点" />
            <button v-if="query" type="button" title="清空搜索" aria-label="清空搜索" @click="query = ''"><X :size="12" /></button>
        </label>

        <div class="outline-body" role="tree" aria-label="主流程大纲">
            <button class="root-row" type="button" :class="{ active: isMainCanvas }" @click="openMain">
                <Workflow :size="15" /><span>主流程</span><small>{{ nodes.length }}</small>
            </button>

            <div v-if="!filteredNodes.length" class="empty-state">
                <Workflow :size="24" />
                <strong>{{ query ? '没有匹配节点' : '主流程还是空的' }}</strong>
                <span>{{ query ? '换一个名称或节点类型试试。' : '从画布工具栏或右键菜单创建第一个节点。' }}</span>
            </div>

            <button
                v-for="node in filteredNodes"
                :key="node.node_id"
                class="node-row"
                :class="{ selected: ui.selectedNodeIds.includes(node.node_id), primary: ui.primaryNodeId === node.node_id }"
                type="button"
                @click="selectNode($event, node)"
                @dblclick.stop="renameNode(node)"
                @contextmenu.prevent.stop="openMenu($event, node)">
                <component :is="getNodeIcon(node.node_type)" :size="14" />
                <span>{{ node.node_name }}</span>
                <small>{{ getNodeTypeLabel(node.node_type) }}</small>
            </button>
        </div>

        <div v-if="menu.visible" class="outline-menu" role="menu" aria-label="节点操作" :style="{ left: `${menu.x}px`, top: `${menu.y}px` }" @click.stop>
            <button type="button" role="menuitem" @click="locateNode(menu.target)"><LocateFixed :size="14" />在画布中定位</button>
            <button type="button" role="menuitem" @click="renameNode(menu.target)"><Pencil :size="14" />重命名</button>
            <button class="danger" type="button" role="menuitem" @click="deleteNode(menu.target)"><Trash2 :size="14" />删除节点</button>
        </div>
    </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { LocateFixed, Pencil, Search, Trash2, Workflow, X } from 'lucide-vue-next'
import { useIdeStore, useUiStore } from '@/stores'
import { getNodeIcon } from '@/config/nodeIconsConfig'
import { getNodeConfig } from '@/config/nodeRegistry'
import { findSelectionPath } from '@/utils/graphSelection'
import { MAIN_GRAPH_ID } from '@/utils/flowModel'
import { notifyActionError } from '@/utils/userActionErrors'

const project = useIdeStore()
const ui = useUiStore()
const query = ref('')
const menu = reactive({ visible: false, x: 0, y: 0, target: null })

const graph = computed(() => project.blueprint?.main_graph || { nodes: [], edges: [] })
const nodes = computed(() => graph.value.nodes || [])
const isMainCanvas = computed(() => project.canvasMode === 'workflow' && project.currentTaskId === MAIN_GRAPH_ID)
const getNodeTypeLabel = type => getNodeConfig(type, project.paramsDefinitions).label
const filteredNodes = computed(() => {
    const keyword = query.value.trim().toLowerCase()
    if (!keyword) return nodes.value
    return nodes.value.filter(node => `${node.node_name} ${node.node_type} ${getNodeTypeLabel(node.node_type)}`.toLowerCase().includes(keyword))
})

async function openMain() {
    try {
        await project.navigateToGraph('workflow', MAIN_GRAPH_ID)
        ui.setFocusTarget({ type: 'graph', id: MAIN_GRAPH_ID, timestamp: Date.now() })
    } catch (error) {
        notifyActionError(error, '无法打开主流程')
    }
}

async function ensureMain() {
    if (!isMainCanvas.value) {
        await project.navigateToGraph('workflow', MAIN_GRAPH_ID)
    }
}

async function selectNode(event, node) {
    try {
        await ensureMain()
    } catch (error) {
        notifyActionError(error, '无法打开主流程')
        return
    }
    if (event.shiftKey) {
        const anchor = ui.selectionAnchorId || ui.primaryNodeId
        const path = anchor ? findSelectionPath(graph.value.edges, anchor, node.node_id) : null
        if (path) ui.selectPath(path.nodeIds, path.edgeIds, anchor, node.node_id)
        else ui.selectNode(node.node_id)
    } else if (event.ctrlKey || event.metaKey) ui.toggleNodeSelection(node.node_id)
    else ui.selectNode(node.node_id)
    ui.setFocusTarget({ type: 'node', id: node.node_id, timestamp: Date.now() })
}

function locateNode(node) {
    menu.visible = false
    selectNode({}, node)
}

async function renameNode(node) {
    menu.visible = false
    try {
        const result = await ElMessageBox.prompt('节点名称只影响阅读，不改变稳定 ID。', '重命名节点', {
            inputValue: node.node_name,
            inputPattern: /\S+/,
            inputErrorMessage: '名称不能为空',
            confirmButtonText: '保存',
            cancelButtonText: '取消'
        })
        node.node_name = result.value.trim()
        await project.saveWorkflowImmediately()
    } catch (error) { notifyActionError(error, '重命名节点失败') }
}

async function deleteNode(node) {
    menu.visible = false
    if (node.fixed) return ElMessage.warning('固定入口节点不能删除')
    try {
        await ElMessageBox.confirm(`删除节点“${node.node_name}”？相关连线也会删除，可使用撤销恢复。`, '删除节点', {
            type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
        })
    } catch { return }
    graph.value.nodes = nodes.value.filter(item => item.node_id !== node.node_id)
    graph.value.edges = (graph.value.edges || []).filter(edge => edge.source_node !== node.node_id && edge.target_node !== node.node_id)
    ui.clearSelection()
    try {
        await project.saveWorkflowImmediately()
    } catch (error) {
        notifyActionError(error, '删除节点后保存失败')
    }
}

function openMenu(event, target) {
    Object.assign(menu, { visible: true, x: event.clientX, y: event.clientY, target })
}

function dismissMenu(event) {
    if (event.type === 'keydown' && event.key !== 'Escape') return
    if (event.type === 'pointerdown' && event.target?.closest?.('.outline-menu')) return
    menu.visible = false
}

onMounted(() => {
    window.addEventListener('pointerdown', dismissMenu)
    window.addEventListener('keydown', dismissMenu)
})
onUnmounted(() => {
    window.removeEventListener('pointerdown', dismissMenu)
    window.removeEventListener('keydown', dismissMenu)
})
</script>

<style scoped>
.outline-panel{height:100%;min-width:0;display:flex;flex-direction:column;background:var(--app-sidebar-bg);color:var(--app-text-primary);font-size:12px}.root-row small,.node-row small{color:var(--app-text-placeholder);font-size:10px}.outline-search{height:34px;margin:7px;display:flex;align-items:center;gap:6px;padding:0 8px;border:1px solid var(--app-border-subtle);border-radius:6px;background:var(--app-input-bg)}.outline-search:focus-within{border-color:var(--el-color-primary);box-shadow:var(--focus-ring)}.outline-search input{min-width:0;flex:1;border:0;outline:0;background:transparent;color:inherit;font:inherit}.outline-search button{display:grid;place-items:center;padding:2px;border:0;background:transparent;color:var(--app-text-placeholder);cursor:pointer}.outline-body{min-height:0;flex:1;overflow:auto;padding:2px 6px 12px}.root-row,.node-row{width:100%;height:29px;display:flex;align-items:center;gap:7px;padding:0 7px;border:0;border-radius:5px;background:transparent;color:inherit;text-align:left;cursor:pointer}.root-row:hover,.node-row:hover{background:var(--el-fill-color-light)}.root-row.active{color:var(--el-color-primary);background:var(--app-color-primary-dim)}.root-row span,.node-row span{min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.node-row{padding-left:25px;color:var(--app-text-secondary)}.node-row.selected{background:var(--app-color-primary-dim);color:var(--app-text-primary)}.node-row.primary{box-shadow:inset 2px 0 var(--el-color-primary)}.node-row small{max-width:76px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.empty-state{min-height:180px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;padding:18px;color:var(--app-text-placeholder);text-align:center}.empty-state strong{color:var(--app-text-secondary);font-size:12px}.empty-state span{max-width:220px;font-size:10.5px;line-height:1.5}.outline-menu{position:fixed;z-index:6000;min-width:180px;padding:5px;border:1px solid var(--app-overlay-border);border-radius:var(--app-radius-md);background:var(--app-overlay-bg);box-shadow:var(--app-shadow-md)}.outline-menu button{width:100%;height:30px;display:flex;align-items:center;gap:8px;padding:0 8px;border:0;border-radius:5px;background:transparent;color:var(--app-text-primary);font-size:11px;text-align:left;cursor:pointer}.outline-menu button:hover{background:var(--el-fill-color-light)}.outline-menu button.danger{color:var(--el-color-danger)}
</style>
