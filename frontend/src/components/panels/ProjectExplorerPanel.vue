<!-- frontend/src/components/panels/ProjectExplorerPanel.vue -->
<template>
    <div class="project-explorer-panel">
        <!-- 顶部项目路径信息 -->
        <div class="explorer-path-bar">
            <span class="path-label">项目:</span>
            <span class="path-value" :title="store.currentProjectPath">{{ projectFolderName }}</span>
        </div>

        <!-- 流程节点树 -->
        <div class="explorer-tree-body">
            <div v-if="tasksList.length === 0" class="empty-tree-tip">
                <span>当前项目暂无任务组或节点</span>
            </div>

            <div
v-for="(task, tIdx) in tasksList"
                 :key="task.task_id || tIdx"
                 class="task-group-item">
                <!-- 1. 任务组 Header (第一层) -->
                <div
class="group-header"
                     :class="{ 'is-selected': isGroupSelected(task) }"
                     @click="handleGroupClick(task)">
                    <div class="header-left">
                        <span class="toggle-arrow" @click.stop="toggleGroupExpand(task.task_id || tIdx)">
                            <ChevronDown
class="arrow-svg"
                                         :class="{ 'is-collapsed': collapsedGroups.includes(task.task_id || tIdx) }" />
                        </span>
                        <component
:is="collapsedGroups.includes(task.task_id || tIdx) ? Folder : FolderOpen"
                                   class="group-icon" />
                        <span class="group-title">{{ task.task_name || `任务组 ${tIdx + 1}` }}</span>
                    </div>
                    <span class="node-count-badge">{{ (task.nodes || []).length }}</span>
                </div>

                <!-- 2. 节点列表 Body (第二层) -->
                <div
v-show="!collapsedGroups.includes(task.task_id || tIdx)"
                     class="node-list-container">
                    <div
v-for="node in (task.nodes || [])"
                         :key="node.node_id"
                         class="node-tree-item"
                         :class="{ 'is-selected': isNodeSelected(node.node_id) }"
                         @click="handleNodeClick(node)">
                        <component :is="getNodeIcon(node.node_type)" class="node-icon" />
                        <span class="node-title">{{ node.node_name }}</span>
                    </div>

                    <div v-if="(task.nodes || []).length === 0" class="empty-group-tip">
                        组内无节点
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
    import { ref, computed } from 'vue'
    import { useMainStore } from '@/stores'
    import { Folder, FolderOpen, ChevronDown } from 'lucide-vue-next'
    import { getNodeIcon } from '@/config/nodeIconsConfig'

    const store = useMainStore()

    // 记录折叠状态的任务组 ID/索引（两模式共用，与边栏展开状态一样不随模式隔离）
    const collapsedGroups = ref([])

    // 项目目录名
    const projectFolderName = computed(() => {
        const p = store.currentProjectPath || ''
        if (!p) return '未打开项目'
        return p.split(/[/\\]/).pop() || p
    })

    // 任务组与节点列表：随画布模式切换数据源（workflow.json / topology.json 同构 {tasks, edges}）
    const tasksList = computed(() => {
        if (store.canvasMode === 'topology') {
            return store.blueprint?.topology?.tasks || []
        }
        return store.blueprint?.tasks || []
    })

    // 判定组是否选中
    const isGroupSelected = (task) => {
        const groupId = `group_${task.task_id}`
        return store.selectedGroupId === groupId || store.selectedGroupId === task.task_id
    }

    // 判定节点是否选中
    const isNodeSelected = (nodeId) => {
        return (store.selectedNodeIds || []).includes(nodeId)
    }

    // 点击展开/收起组
    const toggleGroupExpand = (groupIdx) => {
        const idx = collapsedGroups.value.indexOf(groupIdx)
        if (idx > -1) {
            collapsedGroups.value.splice(idx, 1)
        } else {
            collapsedGroups.value.push(groupIdx)
        }
    }

    // 点击组：选中组 + 驱动右侧 + 画布镜头对齐组中心
    const handleGroupClick = (task) => {
        const gId = `group_${task.task_id}`
        store.setSelectedGroup(gId)
        store.clearSelection()

        // 发发镜头聚焦事件
        store.setFocusTarget({
            type: 'group',
            id: gId,
            timestamp: Date.now()
        })
    }

    // 点击节点：选中节点 + 驱动右侧 + 画布镜头对齐节点中心
    const handleNodeClick = (node) => {
        store.selectNode(node.node_id)
        store.setSelectedGroup(null)

        // 触发镜头聚焦事件
        store.setFocusTarget({
            type: 'node',
            id: node.node_id,
            timestamp: Date.now()
        })
    }
</script>

<style scoped>
    .project-explorer-panel {
        width: 100%;
        height: 100%;
        display: flex;
        flex-direction: column;
        background: var(--el-bg-color);
        box-sizing: border-box;
        user-select: none;
        overflow: hidden;
    }

    .explorer-path-bar {
        padding: 8px 12px;
        background: rgba(25, 26, 38, 0.95);
        border-bottom: 1px solid var(--el-border-color-light);
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 11px;
        flex-shrink: 0;
    }

    .path-label {
        color: var(--el-text-color-secondary);
    }

    .path-value {
        color: var(--el-color-primary);
        font-weight: 600;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .explorer-tree-body {
        flex: 1;
        padding: 8px;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .task-group-item {
        display: flex;
        flex-direction: column;
    }

    /* 1. 组 Header 样式 */
    .group-header {
        padding: 6px 8px;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        cursor: pointer;
        transition: background 0.2s;
    }

        .group-header:hover {
            background: var(--el-fill-color-light);
        }

        .group-header.is-selected {
            background: rgba(78, 209, 156, 0.15);
            border: 1px solid rgba(78, 209, 156, 0.3);
        }

    .header-left {
        display: flex;
        align-items: center;
        gap: 6px;
        overflow: hidden;
    }

    .toggle-arrow {
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        color: var(--el-text-color-secondary);
    }

    .arrow-svg {
        width: 14px;
        height: 14px;
        transition: transform 0.2s ease;
    }

        .arrow-svg.is-collapsed {
            transform: rotate(-90deg);
        }

    .group-icon {
        width: 15px;
        height: 15px;
        color: #4ed19c;
        flex-shrink: 0;
    }

    .group-title {
        font-size: 12px;
        font-weight: 600;
        color: var(--el-text-color-primary);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .node-count-badge {
        font-size: 10px;
        background: rgba(255, 255, 255, 0.06);
        color: var(--el-text-color-secondary);
        padding: 1px 6px;
        border-radius: 10px;
    }

    /* 2. 节点树节点样式 */
    .node-list-container {
        display: flex;
        flex-direction: column;
        gap: 2px;
        padding-left: 22px;
        margin-top: 2px;
    }

    .node-tree-item {
        padding: 5px 8px;
        border-radius: 4px;
        display: flex;
        align-items: center;
        gap: 8px;
        cursor: pointer;
        transition: background 0.15s;
    }

        .node-tree-item:hover {
            background: var(--el-fill-color-light);
        }

        .node-tree-item.is-selected {
            background: var(--el-color-primary);
            color: #ffffff;
        }

    .node-icon {
        width: 14px;
        height: 14px;
        flex-shrink: 0;
    }

    .node-tree-item.is-selected .node-icon {
        color: #ffffff;
    }

    .node-title {
        font-size: 12px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .empty-tree-tip, .empty-group-tip {
        font-size: 11px;
        color: var(--el-text-color-placeholder);
        padding: 12px;
        text-align: center;
    }

    .empty-group-tip {
        padding: 4px 8px;
        text-align: left;
    }
</style>