<!-- frontend/src/layouts/IdeLayout.vue -->
<template>
    <div class="ide-shell-layout">
        <!-- 1. 顶部主菜单栏 -->
        <TopMenuBar @run="handleRun" @open-settings="settingsVisible = true" />

        <!-- 1.1 调试工具栏（工业级：▶⏸⏹⏭⏬⏫ + 断点统计 + 激活节点） -->
        <div class="debug-toolbar-bar">
            <DebugToolbar />
        </div>

        <!-- 1.1 调试工具栏（工业级：▶⏸⏹⏭⏬⏫ + 断点统计 + 激活节点） -->
        <div class="debug-toolbar-bar">
            <DebugToolbar />
        </div>

        <!-- 2. 全局主工作区 -->
        <div class="ide-workspace-root">
<!-- 左侧固定 40px 图标栏 -->
            <div class="fixed-dock-left">
                <ActivityBar
position="left"
                             :items="leftPanelsConfig"
                             :active-id="leftActive"
                             @select="toggleLeftPanel" />
                <div class="bottom-toggle-dock">
                    <el-tooltip
v-for="item in bottomPanelsConfig"
                                :key="item.id"
                                effect="dark"
                                :content="item.title"
                                placement="right"
                                :show-after="300"
                                popper-class="ide-sidebar-tooltip">
                        <div
class="activity-icon-item"
                             :class="{ 'is-active': store.uiState.bottomPanelExpanded && bottomActive === item.id }"
                             @click="toggleBottomPanel(item.id)">
                            <component :is="item.icon" class="act-svg" />
                        </div>
                    </el-tooltip>
                </div>
            </div>

            <!-- 中间大区域 -->
            <div class="ide-middle-area">
<!-- 上半行：左侧面板 + 画布 + 右侧面板 -->
                <div class="ide-upper-row">
                    <!-- 左侧展开面板 -->
                    <ToolWindow
v-if="store.uiState.leftPanelExpanded && currentLeftPanel"
                                :title="currentLeftPanel.title"
                                :width="store.uiState.leftPanelWidth + 'px'"
                                class="ide-card-panel"
                                @close="store.updateUiState('leftPanelExpanded', false)">
                        <component :is="currentLeftPanel.component" />
                    </ToolWindow>

                    <!-- 左侧 5px 拖拽调节分割线 -->
                    <div
v-if="store.uiState.leftPanelExpanded && currentLeftPanel"
                         class="splitter-v"
                         @mousedown="startLeftResize" />

                    <!-- 中央画布区域：根据 canvasMode 动态挂载对应画布 -->
                    <div class="ide-center-viewport ide-card-panel">
                        <div class="pane-content-inner">
                            <!-- ⚡ 动态画布组件：workflow 模式挂载 WorkflowCanvas，topology 模式挂载 TopologyCanvas -->
                            <component :is="currentCanvasComponent" :key="store.canvasMode" />
                        </div>
                    </div>

                    <!-- 右侧 5px 拖拽调节分割线 -->
                    <div
v-if="store.uiState.rightPanelExpanded && currentRightPanel"
                         class="splitter-v"
                         @mousedown="startRightResize" />

                    <!-- 右侧展开面板：拓扑模式下显示拓扑节点编辑器 -->
                    <ToolWindow
v-if="store.uiState.rightPanelExpanded && currentRightPanel"
                                :title="rightPanelTitle"
                                :width="store.uiState.rightPanelWidth + 'px'"
                                class="ide-card-panel"
                                @close="store.updateUiState('rightPanelExpanded', false)">
                        <!-- 拓扑模式：内联拓扑节点编辑器 -->
                        <div v-if="store.canvasMode === 'topology'" class="topo-inspector-inline">
                            <template v-if="store.currentTopologyNode">
                                <div class="topo-insp-section">
                                    <div class="topo-insp-label">节点 ID</div>
                                    <div class="topo-insp-value">{{ store.currentTopologyNode.node_id }}</div>
                                </div>
                                <div class="topo-insp-section">
                                    <div class="topo-insp-label">节点名称</div>
                                    <div class="topo-insp-value">{{ store.currentTopologyNode.label }}</div>
                                </div>
                                <div class="topo-insp-section">
                                    <div class="topo-insp-label">节点类型</div>
                                    <div class="topo-insp-value">{{ store.currentTopologyNode.type }}</div>
                                </div>
                                <div class="topo-insp-section">
                                    <div class="topo-insp-label">出口数量</div>
                                    <div class="topo-insp-value">{{ (store.currentTopologyNode.exits || []).length }}</div>
                                </div>
                                <div class="topo-insp-section">
                                    <div class="topo-insp-label">关联连线</div>
                                    <div class="topo-insp-value">{{ topologyRelatedEdgeCount }}</div>
                                </div>
                                <div class="topo-insp-actions">
                                    <el-button size="small" type="primary" plain @click="topoInspectorAction('editParams')">
                                        编辑参数
                                    </el-button>
                                    <el-button size="small" type="success" plain @click="topoInspectorAction('addExit')">
                                        新增出口
                                    </el-button>
                                    <el-button size="small" type="warning" plain @click="topoInspectorAction('editCondition')">
                                        编辑条件
                                    </el-button>
                                    <el-button size="small" type="danger" plain @click="topoInspectorAction('delete')">
                                        删除节点
                                    </el-button>
                                </div>
                            </template>
                            <div v-else class="topo-insp-empty">
                                请在画布中选中一个拓扑节点以查看属性
                            </div>
                        </div>
                        <!-- 业务流程模式：原有检查器组件 -->
                        <component v-else :is="currentRightPanel.component" />
                    </ToolWindow>
                </div>

                <!-- 底部 5px 拖拽调节分割线 -->
                <div
v-if="store.uiState.bottomPanelExpanded && currentBottomPanel"
                     class="splitter-h"
                     @mousedown="startBottomResize" />

                <!-- 下半行：底部工具窗口 -->
                <ToolWindow
v-if="store.uiState.bottomPanelExpanded && currentBottomPanel"
                            :title="currentBottomPanel.title"
                            width="100%"
                            :height="store.uiState.bottomPanelHeight + 'px'"
                            class="ide-card-panel"
                            @close="store.updateUiState('bottomPanelExpanded', false)">
                    <component :is="currentBottomPanel.component" />
                </ToolWindow>
</div>

            <!-- 右侧固定 40px 图标栏 -->
            <div class="fixed-dock-right">
                <ActivityBar
position="right"
                             :items="rightPanelsConfig"
                             :active-id="rightActive"
                             @select="toggleRightPanel" />
            </div>
</div>

        <!-- 3. 底部纯净状态栏 -->
        <footer class="ide-status-footer">
            <div class="status-left">
                <span class="status-dot">●</span>
                <span>就绪</span>
                <span class="status-divider">|</span>
                <span>画布模式: {{ canvasModeLabel }}</span>
                <span class="status-divider">|</span>
                <span>项目路径: {{ store.currentProjectPath || '未打开' }}</span>
            </div>
            <div class="status-right">
                <span>执行状态: 空闲</span>
                <span class="status-divider">|</span>
                <span>UTF-8</span>
                <span class="status-divider">|</span>
                <span>Vue 3.5</span>
            </div>
        </footer>

        <!-- 面板设置弹窗 -->
        <PanelSettingsDialog v-model:visible="settingsVisible" @apply="handleApplyContext" />
    </div>
</template>

<script setup>
    import { ref, computed } from 'vue'
    import { useMainStore } from '@/stores'
    import { ElMessage } from 'element-plus'

    import TopMenuBar from '@/components/shell/TopMenuBar.vue'
    import ActivityBar from '@/components/shell/ActivityBar.vue'
    import ToolWindow from '@/components/shell/ToolWindow.vue'
    import WorkflowCanvas from '@/components/WorkflowCanvas.vue'
    import TopologyCanvas from '@/components/TopologyCanvas.vue'
    import PanelSettingsDialog from '@/components/PanelSettingsDialog.vue'
    import DebugToolbar from '@/components/DebugToolbar.vue'

    import { leftPanelsConfig, rightPanelsConfig, bottomPanelsConfig } from '@/config/panelsConfig'

    const store = useMainStore()
    const settingsVisible = ref(false)

    // ⚡ 根据画布模式动态选择画布组件
    const currentCanvasComponent = computed(() => {
        return store.canvasMode === 'topology' ? TopologyCanvas : WorkflowCanvas
    })

    // ⚡ 拓扑模式下，右侧面板标题替换为拓扑节点编辑器（组件通过内联模板渲染）
    const rightActive = ref('inspector')
    const currentRightPanel = computed(() => {
        // 拓扑模式下复用右侧面板挂载点，内容由内联模板渲染
        if (store.canvasMode === 'topology') {
            return rightPanelsConfig.find(p => p.id === 'inspector') || rightPanelsConfig[0]
        }
        return rightPanelsConfig.find(p => p.id === rightActive.value)
    })

    const rightPanelTitle = computed(() => {
        return store.canvasMode === 'topology' ? '拓扑节点编辑器' : (currentRightPanel.value?.title || '属性面板')
    })

    // ⚡ 状态栏画布模式文案
    const canvasModeLabel = computed(() => {
        return store.canvasMode === 'topology' ? '页面拓扑' : '业务流程'
    })

    // ⚡ 当前选中拓扑节点的关联连线数
    const topologyRelatedEdgeCount = computed(() => {
        const node = store.currentTopologyNode
        if (!node) return 0
        return store.topologyEdges.filter(e => e.source === node.node_id || e.target === node.node_id).length
    })

    // ⚡ 拓扑节点编辑器快捷操作（通过自定义事件与画布通信）
    const emit = defineEmits(['topoInspectorAction'])
    const topoInspectorAction = (action) => {
        // 派发事件供 TopologyCanvas 监听，或直接提示
        emit('topoInspectorAction', { action, nodeId: store.selectedTopologyNodeId })
        ElMessage.info(`拓扑节点操作: ${action}（请在画布中完成编辑）`)
    }

    // 左侧面板选项与切换（状态联动 store.uiState）
    const leftActive = ref('explorer')
    const currentLeftPanel = computed(() => leftPanelsConfig.find(p => p.id === leftActive.value))

    const toggleLeftPanel = (id) => {
        if (leftActive.value === id && store.uiState.leftPanelExpanded) {
            store.updateUiState('leftPanelExpanded', false)
        } else {
            leftActive.value = id
            store.updateUiState('leftPanelExpanded', true)
        }
    }

    // 右侧面板切换（状态联动 store.uiState）
    const toggleRightPanel = (id) => {
        if (rightActive.value === id && store.uiState.rightPanelExpanded) {
            store.updateUiState('rightPanelExpanded', false)
        } else {
            rightActive.value = id
            store.updateUiState('rightPanelExpanded', true)
        }
    }

    // 底部面板选项与切换（状态联动 store.uiState）
    const bottomActive = ref('console')
    const currentBottomPanel = computed(() => bottomPanelsConfig.find(p => p.id === bottomActive.value))

    const toggleBottomPanel = (id) => {
        if (bottomActive.value === id && store.uiState.bottomPanelExpanded) {
            store.updateUiState('bottomPanelExpanded', false)
        } else {
            bottomActive.value = id
            store.updateUiState('bottomPanelExpanded', true)
        }
    }

    // ⚡ 左侧面板拖拽调整宽度（实时保存到 JSON）
    const startLeftResize = (e) => {
        e.preventDefault()
        const startX = e.clientX
        const startW = store.uiState.leftPanelWidth
        const onMouseMove = (moveEvent) => {
            const dx = moveEvent.clientX - startX
            const newW = Math.max(160, Math.min(startW + dx, 600))
            store.updateUiState('leftPanelWidth', newW)
        }
        const onMouseUp = () => {
            window.removeEventListener('mousemove', onMouseMove)
            window.removeEventListener('mouseup', onMouseUp)
        }
        window.addEventListener('mousemove', onMouseMove)
        window.addEventListener('mouseup', onMouseUp)
    }

    // ⚡ 右侧面板拖拽调整宽度（实时保存到 JSON）
    const startRightResize = (e) => {
        e.preventDefault()
        const startX = e.clientX
        const startW = store.uiState.rightPanelWidth
        const onMouseMove = (moveEvent) => {
            const dx = startX - moveEvent.clientX
            const newW = Math.max(200, Math.min(startW + dx, 600))
            store.updateUiState('rightPanelWidth', newW)
        }
        const onMouseUp = () => {
            window.removeEventListener('mousemove', onMouseMove)
            window.removeEventListener('mouseup', onMouseUp)
        }
        window.addEventListener('mousemove', onMouseMove)
        window.addEventListener('mouseup', onMouseUp)
    }

    // ⚡ 底部面板拖拽调整高度（实时保存到 JSON）
    const startBottomResize = (e) => {
        e.preventDefault()
        const startY = e.clientY
        const startH = store.uiState.bottomPanelHeight
        const onMouseMove = (moveEvent) => {
            const dy = startY - moveEvent.clientY
            const newH = Math.max(80, Math.min(startH + dy, 500))
            store.updateUiState('bottomPanelHeight', newH)
        }
        const onMouseUp = () => {
            window.removeEventListener('mousemove', onMouseMove)
            window.removeEventListener('mouseup', onMouseUp)
        }
        window.addEventListener('mousemove', onMouseMove)
        window.addEventListener('mouseup', onMouseUp)
    }

    const handleRun = async () => {
        if (!store.currentTaskId) return ElMessage.warning('请先选择任务')
        await store.runTask(store.currentTaskId, null)
        ElMessage.success('任务已启动')
    }

    const handleApplyContext = async (ctx) => {
        await store.setCurrentContext(ctx)
        ElMessage.success('工作面板切换成功')
    }
</script>

<style scoped>
    .ide-shell-layout {
        width: 100vw;
        height: 100vh;
        display: flex;
        flex-direction: column;
        background: #12131e;
        overflow: hidden;
        box-sizing: border-box;
    }

    .ide-workspace-root {
        flex: 1;
        display: flex;
        position: relative;
        overflow: hidden;
        background: #12131e;
    }

    .debug-toolbar-bar {
        display: flex; align-items: center;
        padding: 6px 12px;
        background: linear-gradient(180deg, #1a1b2e 0%, #161728 100%);
        border-bottom: 1px solid var(--el-border-color-lighter, #25273f);
        flex-shrink: 0;
        gap: 12px;
    }

    .fixed-dock-left, .fixed-dock-right {
        width: 40px;
        height: 100%;
        background: #181926;
        flex-shrink: 0;
        z-index: 60;
        user-select: none;
        display: flex;
        flex-direction: column;
    }

    .fixed-dock-left {
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }

    .fixed-dock-right {
        border-left: 1px solid rgba(255, 255, 255, 0.05);
    }

    .fixed-dock-left :deep(.activity-bar) {
        flex: 1;
        border-right: none !important;
        width: 100%;
    }

    .bottom-toggle-dock {
        flex-shrink: 0;
        padding-bottom: 8px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        border-top: 1px solid rgba(255, 255, 255, 0.05);
        padding-top: 8px;
    }

    .activity-icon-item {
        width: 32px;
        height: 32px;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        color: var(--el-text-color-secondary);
        transition: all 0.2s ease;
    }

        .activity-icon-item:hover {
            background: var(--el-fill-color-light);
            color: var(--el-text-color-primary);
        }

        .activity-icon-item.is-active {
            background: rgba(78, 209, 156, 0.15);
            color: var(--el-color-primary);
        }

    .act-svg {
        width: 18px;
        height: 18px;
    }

    .ide-middle-area {
        flex: 1;
        display: flex;
        flex-direction: column;
        position: relative;
        overflow: hidden;
        padding: 4px;
        box-sizing: border-box;
    }

    .ide-upper-row {
        flex: 1;
        display: flex;
        position: relative;
        overflow: hidden;
    }

    .ide-center-viewport {
        flex: 1;
        display: flex;
        flex-direction: column;
        position: relative;
        overflow: hidden;
        background: #2b2d3d;
    }

    .pane-content-inner {
        flex: 1;
        position: relative;
        overflow: hidden;
    }

    .ide-card-panel {
        border-radius: 8px !important;
        overflow: hidden !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.06) !important;
    }

    .splitter-v {
        width: 5px;
        height: 100%;
        cursor: col-resize;
        flex-shrink: 0;
        background: transparent;
        transition: background 0.2s ease;
        z-index: 10;
    }

        .splitter-v:hover {
            background: var(--el-color-primary);
        }

    .splitter-h {
        width: 100%;
        height: 5px;
        cursor: row-resize;
        flex-shrink: 0;
        background: transparent;
        transition: background 0.2s ease;
        z-index: 10;
    }

        .splitter-h:hover {
            background: var(--el-color-primary);
        }

    .ide-status-footer {
        height: 26px;
        background: #181926;
        border-top: 1px solid var(--el-border-color-light);
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 12px;
        font-size: 11px;
        color: var(--el-text-color-secondary);
        flex-shrink: 0;
        user-select: none;
        z-index: 1000;
    }

    .status-left, .status-right {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .status-dot {
        color: var(--el-color-primary);
        font-size: 10px;
    }

    .status-divider {
        color: var(--el-border-color-light);
    }

    /* ⚡ 内联拓扑节点编辑器样式 */
    .topo-inspector-inline {
        padding: 12px;
        font-size: 12px;
        color: var(--el-text-color-regular);
    }

    .topo-insp-section {
        margin-bottom: 10px;
    }

    .topo-insp-label {
        font-size: 11px;
        color: var(--el-text-color-secondary);
        margin-bottom: 2px;
    }

    .topo-insp-value {
        font-size: 12px;
        color: var(--el-text-color-primary);
        word-break: break-all;
        background: var(--el-fill-color-light);
        padding: 4px 8px;
        border-radius: 4px;
    }

    .topo-insp-actions {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-top: 14px;
    }

    .topo-insp-empty {
        text-align: center;
        color: var(--el-text-color-placeholder);
        font-size: 12px;
        padding: 40px 12px;
    }
</style>
