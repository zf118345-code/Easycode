// src/stores/index.js
import { defineStore } from 'pinia'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

export const useMainStore = defineStore('main', {
  state: () => ({
    workspaceHandle: null,
    projects: [],
    currentProject: null,
    tasks: [],
    currentTaskId: null,
    currentTaskData: null,
    nodes: [],
    selectedNodeId: null,
    params: {},
    batchMode: false,
    selectedNodeIds: [],
    taskNodesCache: {},  // { taskId: [node, ...] }
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
    async loadParams() {
      if (Object.keys(this.params).length) return
      try {
        const res = await axios.get('/api/params')
        this.params = res.data
      } catch (err) {
        console.error('加载参数定义失败', err)
      }
    },

    // 加载任务节点列表（用于跳转配置）
    async loadTaskNodes(taskId) {
      if (!taskId) return []
      if (this.taskNodesCache[taskId]) return this.taskNodesCache[taskId]
      try {
        const res = await axios.get(`/api/projects/${this.currentProject}/tasks/${taskId}`)
        const nodes = res.data.nodes || []
        this.taskNodesCache[taskId] = nodes
        return nodes
      } catch (err) {
        console.error('加载任务节点失败', err)
        return []
      }
    },

    // 清空缓存
    clearTaskNodesCache() {
      this.taskNodesCache = {}
    },

    // 工作区管理
    async setWorkspaceRoot() {
      if (!window.showDirectoryPicker) {
        ElMessage.error('当前浏览器不支持选择文件夹，请使用 Chrome/Edge 93+')
        return
      }
      try {
        const handle = await window.showDirectoryPicker({ mode: 'readwrite' })
        this.workspaceHandle = handle
        await this.scanProjects()
        if (this.projects.length) {
          this.currentProject = this.projects[0]
          await this.loadProjectData()
          this.saveWorkspace(handle.name, this.currentProject)
        }
        ElMessage.success(`工作区已设置，发现 ${this.projects.length} 个项目`)
      } catch (err) {
        if (err.name !== 'AbortError') {
          ElMessage.error('选择工作区失败: ' + err.message)
        }
      }
    },

    saveWorkspace(workspaceName, projectName) {
      localStorage.setItem('lastWorkspace', workspaceName)
      localStorage.setItem('lastProject', projectName)
    },

    async scanProjects() {
      if (!this.workspaceHandle) return
      this.projects = []
      for await (const [name, handle] of this.workspaceHandle.entries()) {
        if (handle.kind === 'directory') {
          try {
            await handle.getFileHandle('project.json')
            this.projects.push(name)
          } catch {}
        }
      }
    },

    async loadProjectData() {
      if (!this.workspaceHandle || !this.currentProject) return
      try {
        const projectHandle = await this.workspaceHandle.getDirectoryHandle(this.currentProject)
        try {
          const tasksHandle = await projectHandle.getDirectoryHandle('tasks')
          await this.uploadDirectory(tasksHandle, this.currentProject, 'tasks')
        } catch {}
        try {
          const templatesHandle = await projectHandle.getDirectoryHandle('templates')
          await this.uploadDirectory(templatesHandle, this.currentProject, 'templates')
        } catch {}
        try {
          const fileHandle = await projectHandle.getFileHandle('project.json')
          const file = await fileHandle.getFile()
          await this.uploadFile(this.currentProject, 'project.json', file)
        } catch {}
        await this.loadTasks()
      } catch (err) {
        console.error('加载项目数据失败', err)
        ElMessage.error('加载项目数据失败: ' + err.message)
      }
    },

    async uploadDirectory(dirHandle, projectName, relativeBase) {
      for await (const [name, handle] of dirHandle.entries()) {
        const relPath = `${relativeBase}/${name}`
        if (handle.kind === 'directory') {
          await this.uploadDirectory(handle, projectName, relPath)
        } else {
          const file = await handle.getFile()
          await this.uploadFile(projectName, relPath, file)
        }
      }
    },

    async uploadFile(projectName, relativePath, file) {
      const formData = new FormData()
      formData.append('project_name', projectName)
      formData.append('relative_path', relativePath)
      formData.append('file', file)
      try {
        await axios.post('/api/projects/import/file', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
      } catch (err) {
        console.error(`上传文件失败: ${relativePath}`, err)
      }
    },

    async loadTasks() {
      if (!this.currentProject) return
      try {
        const res = await axios.get(`/api/projects/${this.currentProject}/tasks`)
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
      if (!this.currentProject || !taskId) return
      try {
        const res = await axios.get(`/api/projects/${this.currentProject}/tasks/${taskId}`)
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
      if (!this.currentProject || !this.currentTaskId || !this.currentTaskData) {
        console.warn('没有可保存的任务')
        return
      }
      try {
        this.currentTaskData.nodes = this.nodes
        await axios.put(`/api/projects/${this.currentProject}/tasks/${this.currentTaskId}`, {
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
      if (!this.currentProject) return
      try {
        await axios.post(`/api/projects/${this.currentProject}/tasks/order`, { order })
      } catch (err) {
        console.error('保存任务顺序失败', err)
      }
    },

    async createNewTask(taskName) {
      if (!this.currentProject) throw new Error('请先选择项目')
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
        const res = await axios.post(`/api/projects/${this.currentProject}/tasks`, {
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

    selectNode(nodeId) {
      this.selectedNodeId = nodeId
    },

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

    setCurrentContext(context) {
      this.currentContext = { ...this.currentContext, ...context }
    },
    getCurrentContext() {
      return this.currentContext
    },

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