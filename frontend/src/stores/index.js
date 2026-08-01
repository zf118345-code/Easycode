// src/stores/index.js

import { defineStore } from 'pinia'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { logger } from '@/utils/logger'

export const useMainStore = defineStore('main', {
    state: () => ({
        currentProjectPath: localStorage.getItem('currentProjectPath') || null,
        currentProjectName: null,
        recentProjects: JSON.parse(localStorage.getItem('recentProjects') || '[]'),
        tasks: [],
        currentTaskId: null,
        currentTaskData: null,
        nodes: [],
        selectedNodeId: null,
        params: {},
        batchMode: false,
        selectedNodeIds: [],
        taskNodesCache: {},
        taskNodesVersion: 0,
        executionLogs: [],
        currentContext: {
            workMode: 'window',
            windowTitle: '',
            isEmulator: false,
            offsetTop: 0,
            offsetBottom: 0,
            offsetLeft: 0,
            offsetRight: 0,
            targetContentWidth: 0,
            targetContentHeight: 0
        }
    }),

    actions: {
        async loadParams() {
            if (Object.keys(this.params).length) return
            try {
                const res = await axios.get('/api/params')
                this.params = res.data
            } catch (err) {
                logger.error('Store', '加载参数定义失败', err)
            }
        },

        // ====== 上下文管理 ======
        async loadContext() {
            if (!this.currentProjectPath) return
            try {
                const res = await axios.get('/api/context', {
                    params: { project_path: this.currentProjectPath }
                })
                if (res.data) {
                    this.currentContext = {
                        workMode: res.data.workMode || (res.data.windowTitle ? 'window' : 'desktop'),
                        windowTitle: res.data.windowTitle || '',
                        isEmulator: res.data.isEmulator || false,
                        offsetTop: res.data.offsetTop || 0,
                        offsetBottom: res.data.offsetBottom || 0,
                        offsetLeft: res.data.offsetLeft || 0,
                        offsetRight: res.data.offsetRight || 0,
                        targetContentWidth: res.data.targetContentWidth || 0,
                        targetContentHeight: res.data.targetContentHeight || 0
                    }
                }
            } catch (err) {
                logger.error('Store', '加载上下文失败', err)
            }
        },

        async saveContext() {
            if (!this.currentProjectPath) return
            try {
                const payload = {
                    project_path: this.currentProjectPath,
                    context: this.currentContext
                }
                await axios.post('/api/context', payload)
            } catch (err) {
                logger.error('Store', '保存上下文失败', err)
                throw err
            }
        },

        async setCurrentContext(context) {
            this.currentContext = { ...this.currentContext, ...context }
            await this.saveContext()
        },

        // ====== 项目加载 ======
        async loadProjectByPath(projectPath) {
            if (!projectPath) throw new Error('项目路径不能为空')
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

            this.currentProjectPath = projectPath
            this.currentProjectName = projectPath.split(/[\\/]/).pop()
            localStorage.setItem('currentProjectPath', projectPath)
            this.addRecentProject(projectPath, this.currentProjectName)

            await this.loadTasks()
            await this.loadContext()
            return true
        },

        addRecentProject(path, name) {
            const entry = { path, name, lastOpened: Date.now() }
            this.recentProjects = [
                entry,
                ...this.recentProjects.filter(p => p.path !== path)
            ].slice(0, 10)
            localStorage.setItem('recentProjects', JSON.stringify(this.recentProjects))
        },

        // ====== 任务管理 ======
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
                    // 如果当前未选择任务，或者当前任务不在列表中，默认选中第一个
                    const exists = this.tasks.some(t => t.task_id === this.currentTaskId)
                    const targetId = exists ? this.currentTaskId : this.tasks[0].task_id
                    await this.loadTaskData(targetId)
                } else {
                    this.currentTaskId = null
                    this.currentTaskData = null
                    this.nodes = []
                    this.selectedNodeId = null
                }
            } catch (err) {
                logger.error('Store', '加载任务列表失败', err)
                this.tasks = []
                this.taskOrder = []
            }
        },

        // ⭐ 核心优化：确保加载任务数据时，强行重置节点列表与选择状态
        async loadTaskData(taskId) {
            if (!this.currentProjectPath || !taskId) return
            try {
                const res = await axios.get(`/api/tasks/${taskId}`, {
                    params: { project_path: this.currentProjectPath }
                })
                this.currentTaskId = taskId
                this.currentTaskData = res.data
                // 深度深拷贝断开旧引用，确保 Vue 响应式节点列表刷新
                this.nodes = JSON.parse(JSON.stringify(res.data.nodes || []))
                this.selectedNodeId = null
                logger.info('Store', `✅ 成功切换任务 [${res.data.task_name}] | 关联节点数: ${this.nodes.length}`)
            } catch (err) {
                logger.error('Store', '加载任务数据失败', err)
                this.currentTaskData = null
                this.nodes = []
                this.selectedNodeId = null
            }
        },

        // ⭐ 核心优化：指定保存某个任务的数据，避免改属性时被老数据覆盖
        async saveTaskData(taskPayload) {
            if (!this.currentProjectPath || !taskPayload || !taskPayload.task_id) return
            try {
                await axios.put(`/api/tasks/${taskPayload.task_id}`, {
                    project_path: this.currentProjectPath,
                    task_data: taskPayload
                })
                logger.info('Store', `✅ 任务 [${taskPayload.task_name}] 属性保存成功`)
                return true
            } catch (err) {
                logger.error('Store', '保存指定任务数据失败', err)
                throw err
            }
        },

        async saveCurrentTask(noReload = false) {
            if (!this.currentProjectPath || !this.currentTaskId || !this.currentTaskData) {
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
                logger.error('Store', '保存任务失败', err)
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
                logger.error('Store', '保存任务顺序失败', err)
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
            } catch (err) {
                logger.error('Store', '删除任务失败', err)
                throw err
            }
        },

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

                if (res.data.execution_id) {
                    this.pollExecutionLogs(res.data.execution_id)
                }
                return res.data
            } catch (err) {
                logger.error('Store', '执行任务请求失败', err)
                throw err
            }
        },

        pollExecutionLogs(executionId) {
            let loggedCount = 0
            console.group(`🎬 [后端执行日志轮询] Execution ID: ${executionId}`)

            const timer = setInterval(async () => {
                try {
                    const res = await axios.get(`/api/execution/${executionId}`)
                    const { status, logs } = res.data

                    if (logs && logs.length > loggedCount) {
                        const newLogs = logs.slice(loggedCount)
                        newLogs.forEach(line => {
                            if (line.includes('[ERROR]')) console.error(line)
                            else if (line.includes('[WARNING]')) console.warn(line)
                            else console.log(`🐍 ${line}`)
                        })
                        loggedCount = logs.length
                        this.executionLogs = logs
                    }

                    if (status.status === 'success' || status.status === 'error') {
                        clearInterval(timer)
                        console.log(`🏁 [后端执行结束] 状态: ${status.status} | 消息: ${status.message}`)
                        console.groupEnd()
                    }
                } catch (err) {
                    clearInterval(timer)
                    console.groupEnd()
                }
            }, 300)
        },

        async loadTaskNodes(taskId) {
            if (!taskId) return []
            if (this.taskNodesCache[taskId]) {
                return this.taskNodesCache[taskId]
            }
            try {
                const res = await axios.get(`/api/tasks/${taskId}/nodes`, {
                    params: { project_path: this.currentProjectPath }
                })
                const nodes = res.data || []
                this.taskNodesCache[taskId] = nodes
                this.taskNodesVersion++
                return nodes
            } catch (err) {
                logger.error('Store', '加载任务节点失败', err)
                this.taskNodesCache[taskId] = []
                this.taskNodesVersion++
                return []
            }
        },

        clearTaskNodesCache() {
            this.taskNodesCache = {}
        },

        selectNode(nodeId) {
            this.selectedNodeId = nodeId
        },

        toggleBatchMode() {
            this.batchMode = !this.batchMode
            if (!this.batchMode) this.selectedNodeIds = []
        },
        toggleNodeSelection(nodeId) {
            const idx = this.selectedNodeIds.indexOf(nodeId)
            if (idx > -1) this.selectedNodeIds.splice(idx, 1)
            else this.selectedNodeIds.push(nodeId)
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
                if (err !== 'cancel') logger.error('Store', '批量删除错误', err)
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
        }
    },

    getters: {
        selectedNode: (state) => state.nodes.find(n => n.node_id === state.selectedNodeId),
    }
})