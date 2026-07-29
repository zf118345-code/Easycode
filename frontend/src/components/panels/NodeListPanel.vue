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
          <div class="node-row first-row">
            <div class="left-group">
              <el-icon><Timer /></el-icon>
              <span class="label">延迟：</span>
              <span v-if="editingDelay !== node.node_id" class="value" @dblclick="startEditDelay(node)">{{ node.delay_before }} ms</span>
              <el-input v-else v-model="editDelayValue" size="small" type="number" @blur="finishEditDelay(node)" @keyup.enter="finishEditDelay(node)" class="inline-input" ref="delayInput" />
              <el-button type="text" size="small" class="edit-icon" @click.stop="startEditDelay(node)"><el-icon><Edit /></el-icon></el-button>
            </div>
            <div class="right-group">
              <span class="label">循环：</span>
              <span v-if="editingLoop !== node.node_id" class="value" @dblclick="startEditLoop(node)">{{ node.loop_count === -1 ? '无限' : node.loop_count }}</span>
              <el-input v-else v-model="editLoopValue" size="small" type="number" @blur="finishEditLoop(node)" @keyup.enter="finishEditLoop(node)" class="inline-input" ref="loopInput" />
              <el-button type="text" size="small" class="edit-icon" @click.stop="startEditLoop(node)"><el-icon><Edit /></el-icon></el-button>
            </div>
          </div>
          <div class="node-row second-row">
            <div class="left-group">
              <span class="index">{{ index + 1 }}.</span>
              <el-icon class="node-icon" :style="{ color: getNodeColor(node.node_type) }"><component :is="getNodeIcon(node.node_type)" /></el-icon>
              <span v-if="editingName !== node.node_id" class="node-name" @dblclick="startEditName(node)">{{ node.node_name }}</span>
              <el-input v-else v-model="editNameValue" size="small" maxlength="10" @blur="finishEditName(node)" @keyup.enter="finishEditName(node)" class="inline-input" ref="nameInput" />
              <el-button type="text" size="small" class="edit-icon" @click.stop="startEditName(node)"><el-icon><Edit /></el-icon></el-button>
            </div>
            <div class="right-group">
              <el-icon class="drag-handle"><Rank /></el-icon>
              <el-dropdown @command="(cmd) => handleNodeMenu(cmd, node)">
                <el-button type="text" size="small"><el-icon><More /></el-icon></el-button>
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
import { Timer, Edit, Rank, More, ArrowDown, Position, VideoPlay, Clock, Document, Grid, Folder, Search, Share, Setting } from '@element-plus/icons-vue'
import axios from 'axios'

export default {
  components: { draggable, Timer, Edit, Rank, More, ArrowDown, Position, VideoPlay, Clock, Document, Grid, Folder, Search, Share, Setting },
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
      set(val) { this.store.selectAllNodes() }
    }
  },
  watch: {
    'store.batchMode'(val) { if (!val) this.store.selectedNodeIds = [] }
  },
  methods: {
    getNodeIcon(type) {
      const map = { click: 'Position', wait: 'Clock', log: 'Document', set_window: 'Folder', resize_window: 'Grid', reset_window: 'Setting', image_recognition: 'Search', branch: 'Share', script_call: 'VideoPlay' }
      return map[type] || 'Document'
    },
    getNodeColor(type) {
      const map = { click: '#409EFF', wait: '#E6A23C', log: '#909399', set_window: '#67C23A', resize_window: '#67C23A', reset_window: '#67C23A', image_recognition: '#F56C6C', branch: '#9B59B6', script_call: '#1ABC9C' }
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
      const project = this.store.currentProject
      const taskId = this.store.currentTaskId
      if (!project || !taskId) { ElMessage.warning('请先选择项目和任务'); return }
      try {
        ElMessage.info(`从节点 ${node.node_name} 开始执行...`)
        const res = await axios.post(`/api/projects/${project}/run`, { task_id: taskId, start_node_id: node.node_id })
        if (res.data.status === 'success') { ElMessage.success('执行完成') }
        else { ElMessage.error('执行失败: ' + (res.data.message || '未知错误')) }
      } catch (err) { ElMessage.error('执行请求失败: ' + (err.response?.data?.detail || err.message)); console.error(err) }
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
        if (config.default !== undefined) { newNode.params[key] = config.default }
        else if (config.type === 'dict') {
          const subDefaults = {}
          for (const [subKey, subConfig] of Object.entries(config.sub || {})) {
            if (subConfig.default !== undefined) subDefaults[subKey] = subConfig.default
          }
          if (Object.keys(subDefaults).length) newNode.params[key] = subDefaults
        } else if (config.type === 'list_dict') { newNode.params[key] = [] }
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
  background: #282a3a;
  border-radius: 4px;
  overflow: hidden;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 36px;
  padding: 0 12px;
  background: #32324a;
  border-bottom: 1px solid #3d3d5a;
  flex-shrink: 0;
}
.panel-header .title {
  color: #cfd3e6;
  font-weight: 500;
  font-size: 13px;
}
.header-actions {
  display: flex;
  gap: 6px;
}
.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px;
  background: #3d3d5a;
  border-bottom: 1px solid #4d4d6a;
  flex-shrink: 0;
}
.batch-toolbar .batch-info {
  color: #8a8fa8;
  font-size: 12px;
}
.node-list {
  flex: 1;
  list-style: none;
  margin: 0;
  padding: 4px 0;
  overflow-y: auto;
}
.node-item {
  background: #3d3d5a;
  margin: 4px 8px;
  padding: 6px 10px;
  border-radius: 4px;
  border: 1px solid transparent;
  transition: border-color 0.2s, background 0.2s;
  display: flex;
  flex-direction: column;
  gap: 4px;
  cursor: pointer;
}
.node-item.active {
  border-color: #409EFF;
  background: #4a4a6a;
}
.node-item.batch-mode {
  padding-left: 36px;
  position: relative;
}
.batch-checkbox {
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
}
.node-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.first-row .left-group,
.first-row .right-group {
  display: flex;
  align-items: center;
  gap: 4px;
}
.first-row .label {
  color: #8a8fa8;
  font-size: 12px;
}
.first-row .value {
  color: #cfd3e6;
  font-size: 12px;
}
.inline-input {
  width: 60px;
  height: 22px;
}
.inline-input .el-input__inner {
  height: 22px;
  padding: 0 4px;
  font-size: 12px;
}
.edit-icon {
  padding: 0;
  font-size: 12px;
  color: #8a8fa8;
}
.edit-icon:hover {
  color: #cfd3e6;
}
.second-row .left-group {
  display: flex;
  align-items: center;
  gap: 6px;
}
.second-row .index {
  color: #8a8fa8;
  font-size: 12px;
  min-width: 20px;
}
.node-icon {
  font-size: 16px;
}
.node-name {
  color: #cfd3e6;
  font-size: 13px;
  font-weight: 500;
}
.right-group {
  display: flex;
  align-items: center;
  gap: 2px;
}
.drag-handle {
  cursor: grab;
  color: #6a6a8a;
  font-size: 16px;
}
.drag-handle:hover {
  color: #cfd3e6;
}
.empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8a8fa8;
}
</style>