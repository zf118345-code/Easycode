// src/stores/index.js
import { defineStore } from 'pinia'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

export const useMainStore = defineStore('main', {
  state: () => ({
    // ===== 核心：当前项目路径 =====
    currentProjectPath: localStorage.getItem('currentProjectPath') || null,
    currentProjectName: null,
    recentProjects: JSON.parse(localStorage.getItem('recentProjects') || '[]'),

    // ===== 任务相关 =====
    tasks: [],
    currentTaskId: null,
    currentTaskData: null,
    nodes: [],
    selectedNodeId: null,
    params: {},
    batchMode: false,
    selectedNodeIds: [],
    taskNodesCache: {},

    // ===== 工作面板上下文 =====
    currentContext: {
      windowTitle: '',
      isEmulator: false,
      deviceId: '',
      androidWidth: 0,
      androidHeight: 0,
      offsetTop: 0,
      offsetBottom: 0,
      offsetLeft: 0,
      offsetRight: 0
    }
  }),

  actions: {
    // ==================== 参数加载 ====================
    async loadParams() {
      if (Object.keys(this.params).length) return
      try {
        const res = await axios.get('/api/params')
        this.params = res.data
      } catch (err) {
        console.error('加载参数定义失败', err)
      }
    },

    // ==================== 最近项目 ====================
    addRecentProject(path, name) {
      const entry = { path, name, lastOpened: Date.now() }
      this.recentProjects = [
        entry,
        ...this.recentProjects.filter(p => p.path !== path)
      ].slice(0, 10)
      localStorage.setItem('recentProjects', JSON.stringify(this.recentProjects))
    },



    // ==================== 任务管理 ====================
    async loadTasks() {
      if (!this.currentProjectPath) return
      try {
        const res = await axios.get('/api/tasks', {
          params: { project_path: this.currentProjectPath }
        })
        this.tasks = res.data.tasks || []
        this.taskOrder = res.data.order || []
        this.clearTaskNodesCache()
        if (this.tasks.length) {
          this.currentTaskId = this.tasks[0].task_id
          await this.loadTaskData(this.currentTaskId)
        } else {
          this.currentTaskId = null
          this.currentTaskData = null
          this.nodes = []
        }
      } catch (err) {
        console.error('加载任务列表失败', err)
        this.tasks = []
        this.taskOrder = []
      }
    },

    async loadTaskData(taskId) {
      if (!this.currentProjectPath || !taskId) return
      try {
        const res = await axios.get(`/api/tasks/${taskId}`, {
          params: { project_path: this.currentProjectPath }
        })
        this.currentTaskData = res.data
        this.nodes = res.data.nodes || []
        this.currentTaskId = taskId
      } catch (err) {
        console.error('加载任务数据失败', err)
        this.currentTaskData = null
        this.nodes = []
      }
    },

    async saveCurrentTask(noReload = false) {
      if (!this.currentProjectPath || !this.currentTaskId || !this.currentTaskData) {
        console.warn('没有可保存的任务')
        return
      }
      try {
        this.currentTaskData.nodes = this.nodes
        await axios.put(`/api/tasks/${this.currentTaskId}`, {
          project_path: this.currentProjectPath,
          task_data: this.currentTaskData
        })
        if (!noReload) {
          await this.loadTasks()
          await this.loadTaskData(this.currentTaskId)
        }
        return true
      } catch (err) {
        console.error('保存任务失败', err)
        throw err
      }
    },

    async saveTaskOrder(order) {
      if (!this.currentProjectPath) return
      try {
        await axios.post('/api/tasks/order', {
          project_path: this.currentProjectPath,
          order
        })
      } catch (err) {
        console.error('保存任务顺序失败', err)
      }
    },

    async createNewTask(taskName) {
      if (!this.currentProjectPath) throw new Error('请先打开项目')
      if (this.tasks.some(t => t.task_name === taskName)) {
        throw new Error('任务名称已存在')
      }
      const newTaskData = {
        task_name: taskName,
        loop_count: 1,
        loop_interval: 0,
        nodes: []
      }
      try {
        const res = await axios.post('/api/tasks', {
          project_path: this.currentProjectPath,
          task_data: newTaskData
        })
        await this.loadTasks()
        if (res.data.task_id) {
          this.currentTaskId = res.data.task_id
          await this.loadTaskData(res.data.task_id)
        }
        return true
      } catch (err) {
        if (err.response?.status === 400) {
          throw new Error(err.response.data.detail || '任务名称已存在')
        }
        throw err
      }
    },

    async deleteTask(taskId) {
      if (!this.currentProjectPath) return
      try {
        await axios.delete(`/api/tasks/${taskId}`, {
          params: { project_path: this.currentProjectPath }
        })
        await this.loadTasks()
        if (this.tasks.length) {
          await this.loadTaskData(this.tasks[0].task_id)
        }
      } catch (err) {
        console.error('删除任务失败', err)
        throw err
      }
    },

    // ==================== 执行任务 ====================
    async runTask(taskId, startNodeId = null) {
      if (!this.currentProjectPath) {
        throw new Error('请先打开项目')
      }
      try {
        const res = await axios.post('/api/run', {
          project_path: this.currentProjectPath,
          task_id: taskId,
          start_node_id: startNodeId
        })
        return res.data
      } catch (err) {
        console.error('执行任务失败', err)
        throw err
      }
    },

    // ==================== 模板区域 ====================
    async getRegions() {
      if (!this.currentProjectPath) return {}
      try {
        const res = await axios.get('/api/regions', {
          params: { project_path: this.currentProjectPath }
        })
        return res.data
      } catch (err) {
        console.error('获取区域配置失败', err)
        return {}
      }
    },

    async updateRegion(relativePath, region) {
      if (!this.currentProjectPath) return
      try {
        await axios.post('/api/regions', {
          project_path: this.currentProjectPath,
          relative_path: relativePath,
          region
        })
      } catch (err) {
        console.error('更新区域失败', err)
        throw err
      }
    },

    async syncTemplates() {
      if (!this.currentProjectPath) return
      try {
        const res = await axios.post('/api/templates/sync', {
          project_path: this.currentProjectPath
        })
        return res.data
      } catch (err) {
        console.error('同步模板失败', err)
        throw err
      }
    },

    // ==================== 任务节点列表 ====================
    async loadTaskNodes(taskId) {
      if (!taskId) return []
      if (this.taskNodesCache[taskId]) return this.taskNodesCache[taskId]
      try {
        const res = await axios.get(`/api/tasks/${taskId}/nodes`, {
          params: { project_path: this.currentProjectPath }
        })
        const nodes = res.data || []
        this.taskNodesCache[taskId] = nodes
        return nodes
      } catch (err) {
        console.error('加载任务节点失败', err)
        return []
      }
    },

    clearTaskNodesCache() {
      this.taskNodesCache = {}
    },

    // ==================== 节点选择 ====================
    selectNode(nodeId) {
      this.selectedNodeId = nodeId
    },

    // ==================== 批量操作 ====================
    toggleBatchMode() {
      this.batchMode = !this.batchMode
      if (!this.batchMode) {
        this.selectedNodeIds = []
      }
    },

    toggleNodeSelection(nodeId) {
      const idx = this.selectedNodeIds.indexOf(nodeId)
      if (idx > -1) {
        this.selectedNodeIds.splice(idx, 1)
      } else {
        this.selectedNodeIds.push(nodeId)
      }
    },

    selectAllNodes() {
      const allIds = this.nodes.map(n => n.node_id)
      if (this.selectedNodeIds.length === allIds.length) {
        this.selectedNodeIds = []
      } else {
        this.selectedNodeIds = allIds
      }
    },

    async batchDeleteNodes() {
      if (!this.selectedNodeIds.length) return
      try {
        await ElMessageBox.confirm(
          `确定要删除选中的 ${this.selectedNodeIds.length} 个节点吗？`,
          '批量删除',
          { type: 'warning' }
        )
        this.nodes = this.nodes.filter(n => !this.selectedNodeIds.includes(n.node_id))
        this.currentTaskData.nodes = this.nodes
        await this.saveCurrentTask()
        this.selectedNodeIds = []
        this.batchMode = false
        ElMessage.success('批量删除成功')
      } catch (err) {
        if (err !== 'cancel') console.error(err)
      }
    },

    async batchSetDelay(delayMs) {
      if (!this.selectedNodeIds.length) return
      const delay = parseInt(delayMs)
      if (isNaN(delay) || delay < 0) {
        ElMessage.warning('延迟必须为大于等于0的整数')
        return
      }
      this.nodes.forEach(n => {
        if (this.selectedNodeIds.includes(n.node_id)) {
          n.delay_before = delay
        }
      })
      this.currentTaskData.nodes = this.nodes
      await this.saveCurrentTask()
      ElMessage.success(`已为 ${this.selectedNodeIds.length} 个节点设置延迟 ${delay}ms`)
      this.selectedNodeIds = []
      this.batchMode = false
    },

    // ==================== 工作面板上下文 ====================

    getCurrentContext() {
      return this.currentContext
    },

   // ==================== 上下文管理（前后端同步） ====================

    async loadContext() {
      /* 加载后端保存的上下文 */
      if (!this.currentProjectPath) return
      try {
        const res = await axios.get('/api/context', {
          params: { project_path: this.currentProjectPath }
        })
        if (res.data) {
          // 将后端返回的字段映射到前端格式
          this.currentContext = {
            windowTitle: res.data.windowTitle || '',
            isEmulator: res.data.isEmulator || false,
            deviceId: res.data.deviceId || '',
            androidWidth: res.data.androidWidth || 0,
            androidHeight: res.data.androidHeight || 0,
            offsetTop: res.data.offsetTop || 0,
            offsetBottom: res.data.offsetBottom || 0,
            offsetLeft: res.data.offsetLeft || 0,
            offsetRight: res.data.offsetRight || 0
          }
        }
      } catch (err) {
        console.error('加载上下文失败', err)
      }
    },

    async saveContext() {
      /* 保存上下文到后端 */
      if (!this.currentProjectPath) return
      try {
        await axios.post('/api/context', {
          project_path: this.currentProjectPath,
          context: this.currentContext
        })
      } catch (err) {
        console.error('保存上下文失败', err)
        throw err
      }
    },

    // 修改 setCurrentContext，增加同步到后端的功能
    async setCurrentContext(context) {
      this.currentContext = { ...this.currentContext, ...context }
      // 同步到后端
      await this.saveContext()
    },

    // 修改 loadProjectByPath，加载项目后也加载上下文
    async loadProjectByPath(projectPath) {
      if (!projectPath) {
        throw new Error('项目路径不能为空')
      }
      // 验证路径是否存在
      try {
        const verifyRes = await axios.get('/api/projects/verify', {
          params: { project_path: projectPath }
        })
        if (!verifyRes.data.exists) {
          throw new Error(`项目路径不存在: ${projectPath}`)
        }
      } catch (err) {
        if (err.response?.status === 404) {
          throw new Error(`项目路径不存在: ${projectPath}`)
        }
        throw err
      }

      // 存储路径
      this.currentProjectPath = projectPath
      this.currentProjectName = projectPath.split(/[\\/]/).pop()
      localStorage.setItem('currentProjectPath', projectPath)
      this.addRecentProject(projectPath, this.currentProjectName)

      // 加载任务数据
      await this.loadTasks()
      // 加载保存的上下文
      await this.loadContext()
      return true
    },

    // ==================== 重置 ====================
    resetTaskState() {
      this.tasks = []
      this.currentTaskId = null
      this.currentTaskData = null
      this.nodes = []
      this.selectedNodeId = null
      this.clearTaskNodesCache()
    }
  },

  getters: {
    selectedNode: (state) => state.nodes.find(n => n.node_id === state.selectedNodeId),
  }
})