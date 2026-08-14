<template>
    <div class="node-list-panel">
        <div class="panel-header">
            <span class="title">节点列表</span>
            <div class="header-actions">
                <el-button size="small" :type="store.batchMode ? 'primary' : 'default'" @click="store.toggleBatchMode()">
                    {{ store.batchMode ? '退出批量' : '批量操作' }}
                </el-button>
                <el-dropdown @command="createNode">
                    <el-button size="small" type="primary"> + 新建 <el-icon><ArrowDown /></el-icon> </el-button>
                    <template #dropdown>
                        <el-dropdown-menu>
                            <el-dropdown-item v-for="(def, type) in store.params" :key="type" :command="type">
                                {{ def.label || type }}
                            </el-dropdown-item>
                        </el-dropdown-menu>
                    </template>
                </el-dropdown>
            </div>
        </div>

        <div v-if="store.batchMode" class="batch-toolbar">
            <el-checkbox :model-value="selectAll" @change="store.selectAllNodes()">全选</el-checkbox>
            <span class="batch-info">已选 {{ store.selectedNodeIds.length }} 个节点</span>
            <el-button size="small" @click="showBatchDelayDialog">⏱ 批量延迟</el-button>
            <el-button size="small" type="danger" @click="store.batchDeleteNodes()">🗑 批量删除</el-button>
        </div>

        <draggable v-model="store.nodes" item-key="node_id" class="node-list" handle=".drag-handle" @end="onDragEnd">
            <template #item="{ element: node, index }">
                <div class="node-item" :class="{ active: store.selectedNodeId === node.node_id, 'batch-mode': store.batchMode }" @click="store.selectNode(node.node_id)">
                    <el-checkbox v-if="store.batchMode" :model-value="store.selectedNodeIds.includes(node.node_id)" @change.stop="store.toggleNodeSelection(node.node_id)" class="batch-checkbox" />

                    <!-- ⭐ 第一行：等待（居左） + 循环（居右） -->
                    <div class="node-row first-row">
                        <div class="left-group">
                            <el-icon><Timer /></el-icon>
                            <span class="label">延迟：</span>
                            <span v-if="editingDelay !== node.node_id" class="value" @dblclick="startEditDelay(node)">{{ node.delay_before }} ms</span>
                            <el-input v-else v-model="editDelayValue" size="small" type="number" @blur="finishEditDelay(node)" @keyup.enter="finishEditDelay(node)" class="inline-input" ref="delayInput" />
                            <el-button link size="small" class="edit-icon" @click.stop="startEditDelay(node)"><el-icon><Edit /></el-icon></el-button>
                        </div>
                        <div class="right-group">
                            <span class="label">循环：</span>
                            <span v-if="editingLoop !== node.node_id" class="value" @dblclick="startEditLoop(node)">{{ node.loop_count === -1 ? '无限' : node.loop_count }}</span>
                            <el-input v-else v-model="editLoopValue" size="small" type="number" @blur="finishEditLoop(node)" @keyup.enter="finishEditLoop(node)" class="inline-input" ref="loopInput" />
                            <el-button link size="small" class="edit-icon" @click.stop="startEditLoop(node)"><el-icon><Edit /></el-icon></el-button>
                        </div>
                    </div>

                    <!-- ⭐ 第二行：序号+类型图标+节点名（居左） + 拖动&更多操作（居右） -->
                    <div class="node-row second-row">
                        <div class="left-group">
                            <span class="index">{{ index + 1 }}.</span>
                            <el-icon class="node-icon" :style="{ color: getNodeColor(node.node_type) }"><component :is="getNodeIcon(node.node_type)" /></el-icon>
                            <span v-if="editingName !== node.node_id" class="node-name" @dblclick="startEditName(node)">{{ node.node_name }}</span>
                            <el-input v-else v-model="editNameValue" size="small" maxlength="10" @blur="finishEditName(node)" @keyup.enter="finishEditName(node)" class="inline-input" ref="nameInput" />
                            <el-button link size="small" class="edit-icon" @click.stop="startEditName(node)"><el-icon><Edit /></el-icon></el-button>
                        </div>
                        <div class="right-group" @click.stop>
                            <el-icon class="drag-handle"><Rank /></el-icon>
                            <el-dropdown @command="(cmd) => handleNodeMenu(cmd, node)">
                                <el-button link size="small"><el-icon><More /></el-icon></el-button>
                                <template #dropdown>
                                    <el-dropdown-menu>
                                        <el-dropdown-item command="run">▶ 从当前节点执行</el-dropdown-item>
                                        <el-dropdown-item command="disable">{{ node.enabled ? '⏸ 禁用节点' : '▶ 启用节点' }}</el-dropdown-item>
                                        <el-dropdown-item divided command="delete">🗑 删除节点</el-dropdown-item>
                                    </el-dropdown-menu>
                                </template>
                            </el-dropdown>
                        </div>
                    </div>
                </div>
            </template>
        </draggable>
        <div v-if="!store.nodes.length" class="empty">暂无节点</div>

        <el-dialog title="批量设置延迟" v-model="batchDelayDialog" width="400px" append-to-body>
            <el-form>
                <el-form-item label="延迟(ms)">
                    <el-input-number v-model="batchDelayValue" :min="0" />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="batchDelayDialog = false">取消</el-button>
                <el-button type="primary" @click="confirmBatchDelay">确定</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script>
    import draggable from 'vuedraggable'
    import { useMainStore } from '@/stores'
    import { ElMessage, ElMessageBox } from 'element-plus'
    import { Timer, Edit, Rank, More, ArrowDown, Position, VideoPlay, Clock, Document, Grid, Folder, Search, Share, Setting, Reading, Operation } from '@element-plus/icons-vue'

    export default {
        components: { draggable, Timer, Edit, Rank, More, ArrowDown, Position, VideoPlay, Clock, Document, Grid, Folder, Search, Share, Setting, Reading, Operation },
        setup() {
            const store = useMainStore()
            return { store }
        },
        data() {
            return {
                editingName: null, editNameValue: '',
                editingDelay: null, editDelayValue: '',
                editingLoop: null, editLoopValue: '',
                batchDelayDialog: false, batchDelayValue: 0
            }
        },
        computed: {
            selectAll: {
                get() {
                    const nodes = this.store.nodes || []
                    const selected = this.store.selectedNodeIds || []
                    return nodes.length > 0 && selected.length === nodes.length
                },
                set() { this.store.selectAllNodes() }
            }
        },
        watch: {
            'store.batchMode'(val) { if (!val) this.store.clearSelection() }
        },
        methods: {
            getNodeIcon(type) {
                const map = {
                    click: 'Position',
                    wait: 'Clock',
                    log: 'Document',
                    set_window: 'Folder',
                    image_recognition: 'Search',
                    branch: 'Share',
                    logic_check: 'Operation',
                    ocr_recognition: 'Reading',
                    variable_op: 'Setting',
                    script_call: 'VideoPlay'
                }
                return map[type] || 'Document'
            },
            getNodeColor(type) {
                const map = {
                    click: '#409EFF',
                    wait: '#E6A23C',
                    log: '#909399',
                    set_window: '#67C23A',
                    image_recognition: '#F56C6C',
                    branch: '#9B59B6',
                    logic_check: '#E67E22',
                    ocr_recognition: '#3498DB',
                    variable_op: '#1ABC9C',
                    script_call: '#2ECC71'
                }
                return map[type] || '#909399'
            },
            startEditName(node) {
                this.editingName = node.node_id
                this.editNameValue = node.node_name
                this.$nextTick(() => { const input = this.$refs.nameInput; if (input) input.focus() })
            },
            finishEditName(node) {
                const name = this.editNameValue.trim()
                if (name.length > 10) { ElMessage.warning('节点名称不能超过10个字符'); this.editingName = null; return }
                if (name) { node.node_name = name; this.saveNode(node) }
                this.editingName = null
            },
            startEditDelay(node) {
                this.editingDelay = node.node_id; this.editDelayValue = node.delay_before
                this.$nextTick(() => { const input = this.$refs.delayInput; if (input) input.focus() })
            },
            finishEditDelay(node) {
                let val = parseInt(this.editDelayValue); if (isNaN(val) || val < 0) val = 0
                node.delay_before = val; this.saveNode(node); this.editingDelay = null
            },
            startEditLoop(node) {
                this.editingLoop = node.node_id; this.editLoopValue = node.loop_count
                this.$nextTick(() => { const input = this.$refs.loopInput; if (input) input.focus() })
            },
            finishEditLoop(node) {
                let val = parseInt(this.editLoopValue); if (isNaN(val) || val < -1) val = 1
                node.loop_count = val; this.saveNode(node); this.editingLoop = null
            },
            async saveNode(node) {
                try {
                    const taskData = this.store.currentTaskData
                    if (taskData) {
                        const target = taskData.nodes.find(n => n.node_id === node.node_id)
                        if (target) Object.assign(target, { node_name: node.node_name, delay_before: node.delay_before, loop_count: node.loop_count, enabled: node.enabled, params: node.params })
                        await this.store.saveCurrentTask(true)
                    }
                } catch (err) { console.error('保存节点失败', err); ElMessage.error('保存失败') }
            },
            async onDragEnd() {
                try {
                    const taskData = this.store.currentTaskData
                    if (taskData) { taskData.nodes = this.store.nodes; await this.store.saveCurrentTask(true) }
                } catch (err) { console.error('拖拽排序失败', err); ElMessage.error('保存顺序失败') }
            },
            handleNodeMenu(command, node) {
                switch (command) {
                    case 'run': this.runFromNode(node); break
                    case 'disable': node.enabled = !node.enabled; this.saveNode(node); break
                    case 'delete': this.deleteNode(node); break
                }
            },
            async runFromNode(node) {
                const taskId = this.store.currentTaskId
                if (!taskId) {
                    ElMessage.warning('请先选择一个任务')
                    return
                }
                try {
                    ElMessage.info(`从节点 ${node.node_name} 开始执行...`)
                    const result = await this.store.runTask(taskId, node.node_id)
                    if (result.status === 'started') {
                        ElMessage.success('执行已启动')
                    } else {
                        ElMessage.error('执行失败: ' + (result.message || '未知错误'))
                    }
                } catch (err) {
                    ElMessage.error('执行请求失败: ' + (err.message || '未知错误'))
                }
            },
            async deleteNode(node) {
                try {
                    await ElMessageBox.confirm(`确定要删除节点 "${node.node_name}" 吗？`, '确认删除', { type: 'warning' })
                    const idx = this.store.nodes.findIndex(n => n.node_id === node.node_id)
                    if (idx > -1) {
                        this.store.nodes.splice(idx, 1)
                        const taskData = this.store.currentTaskData
                        if (taskData) { taskData.nodes = this.store.nodes; await this.store.saveCurrentTask(true) }
                        if (this.store.selectedNodeId === node.node_id) this.store.selectNode(null)
                        ElMessage.success('节点已删除')
                    }
                } catch (err) { if (err !== 'cancel') console.error('删除失败', err) }
            },
            async createNode(nodeType) {
                const def = this.store.params[nodeType]
                if (!def) { ElMessage.warning(`未知节点类型: ${nodeType}`); return }
                const nodeId = `node_${Date.now()}`
                const newNode = {
                    node_id: nodeId,
                    node_name: def.label || nodeType,
                    node_type: nodeType,
                    params: {},
                    delay_before: 0,
                    loop_count: 1,
                    enabled: true,
                    on_success: { type: 'next', target: null, target_node: null, return_on_complete: false },
                    on_failure: { type: 'next', target: null, target_node: null, return_on_complete: false },
                    position: null
                }
                const nodeDefaults = this.store.params[nodeType]?.params || {}
                for (const [key, config] of Object.entries(nodeDefaults)) {
                    if (config.type === 'list_int2' || config.type === 'list_int4') {
                        newNode.params[key] = [0, 0, 0, 0].slice(0, config.type === 'list_int2' ? 2 : 4)
                    } else if (config.type === 'list_dict') {
                        newNode.params[key] = []
                    } else if (config.type === 'dict') {
                        const subDefaults = {}
                        for (const [subKey, subConfig] of Object.entries(config.sub || {})) {
                            if (subConfig.default !== undefined) {
                                if (Array.isArray(subConfig.default)) {
                                    subDefaults[subKey] = [...subConfig.default]
                                } else {
                                    subDefaults[subKey] = subConfig.default
                                }
                            }
                        }
                        if (Object.keys(subDefaults).length) {
                            newNode.params[key] = subDefaults
                        }
                    } else if (config.default !== undefined) {
                        newNode.params[key] = config.default
                    }
                }
                this.store.nodes.push(newNode)
                const taskData = this.store.currentTaskData
                if (taskData) { taskData.nodes = this.store.nodes; await this.store.saveCurrentTask(true) }
                ElMessage.success(`已添加节点: ${newNode.node_name}`)
            },
            showBatchDelayDialog() { this.batchDelayValue = 0; this.batchDelayDialog = true },
            async confirmBatchDelay() { await this.store.batchSetDelay(this.batchDelayValue); this.batchDelayDialog = false }
        }
    }
</script>

<style scoped>
    .node-list-panel {
        display: flex;
        flex-direction: column;
        height: 100%;
        background: var(--el-bg-color);
    }

    .panel-header {
        padding: 8px 12px;
        background: var(--el-fill-color-blank);
        border-bottom: 1px solid var(--el-border-color-light);
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 13px;
        font-weight: 600;
        color: var(--el-text-color-primary);
    }

    .header-actions {
        display: flex;
        gap: 6px;
    }

    .batch-toolbar {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 12px;
        background: var(--el-fill-color-blank);
        border-bottom: 1px solid var(--el-border-color-light);
        font-size: 12px;
    }

    .batch-info {
        color: var(--el-color-primary);
        font-weight: bold;
    }

    .node-list {
        flex: 1;
        overflow-y: auto;
        padding: 6px;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    /* ⭐ 节点卡片容器：垂直两行布局 */
    .node-item {
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 8px 12px;
        border-radius: 8px;
        background: var(--el-fill-color-blank);
        border: 1px solid var(--el-border-color-light);
        cursor: pointer;
        transition: all 0.2s ease;
        user-select: none;
        box-sizing: border-box;
        width: 100%;
    }

        .node-item:hover {
            border-color: var(--el-color-primary);
            background: var(--el-fill-color-light);
        }

        .node-item.active {
            border-color: var(--el-color-primary);
            background: rgba(78, 209, 156, 0.15);
        }

    /* ⭐⭐ 核心行样式：两端 100% 强行推开 */
    .node-row {
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
        width: 100% !important;
    }

    .left-group, .right-group {
        display: flex;
        align-items: center;
        gap: 6px;
    }

    /* 第一行：延迟与循环 */
    .first-row .label {
        font-size: 11px;
        color: var(--el-text-color-secondary);
    }

    .first-row .value {
        font-size: 11px;
        color: var(--el-text-color-regular);
        font-weight: 500;
    }

    /* 第二行：序号、名称与右侧操作栏 */
    .second-row .index {
        font-size: 13px;
        font-weight: bold;
        color: var(--el-text-color-secondary);
    }

    .second-row .node-name {
        font-size: 13px;
        font-weight: 600;
        color: var(--el-text-color-primary);
    }

    .node-item.active .second-row .node-name {
        color: var(--el-color-primary);
    }

    .drag-handle {
        cursor: move;
        color: var(--el-text-color-secondary);
        font-size: 14px;
        user-select: none;
        margin-left: 2px;
    }

    .edit-icon {
        padding: 0 !important;
        height: auto !important;
        font-size: 12px;
        opacity: 0.6;
    }

        .edit-icon:hover {
            opacity: 1;
        }

    .inline-input {
        width: 70px;
    }

    .empty {
        text-align: center;
        color: var(--el-text-color-placeholder);
        font-size: 12px;
        padding: 20px 0;
    }
</style>