// frontend/src/stores/index.js
import { defineStore } from 'pinia'
import { blueprintApi } from '@/api/blueprintApi'
import { workspaceApi } from '@/api/workspaceApi'
import { logger } from '@/utils/logger'
import debounce from 'lodash-es/debounce'

// 默认 UI 布局配置
const DEFAULT_UI_STATE = {
    leftPanelExpanded: true,
    leftPanelWidth: 260,
    rightPanelExpanded: true,
    rightPanelWidth: 320,
    bottomPanelExpanded: true,
    bottomPanelHeight: 200,
    minimapExpanded: true
}

export const useMainStore = defineStore('main', {
    state: () => ({
        currentProjectPath: localStorage.getItem('lastProjectPath') || null,
        currentProjectName: '',
        blueprint: {
            project_name: '',
            tasks: [],
            variables: {},
            ui_state: { ...DEFAULT_UI_STATE } // ⚡ 存在项目 JSON 里的 UI 界面布局数据
        },
        paramsDefinitions: {},
        currentTaskId: null,
        selectedNodeId: null,
        recentProjects: JSON.parse(localStorage.getItem('recentProjects') || '[]'),
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
        },
        executionLogs: [],
        taskNodesVersion: 0,

        selectedNodeIds: [],
        selectedGroupId: null,
        activeEventSource: null
    }),

    getters: {
        tasks: (state) => state.blueprint.tasks || [],
        currentTaskData: (state) => state.blueprint,
        currentTask: (state) => (state.blueprint.tasks || []).find(t => t.task_id === state.currentTaskId),
        nodes: (state) => {
            const task = (state.blueprint.tasks || []).find(t => t.task_id === state.currentTaskId)
            return task ? task.nodes || [] : []
        },
        selectedNode: (state) => {
            for (const task of (state.blueprint.tasks || [])) {
                const node = (task.nodes || []).find(n => n.node_id === state.selectedNodeId)
                if (node) return node
            }
            return null
        },
        params: (state) => state.paramsDefinitions,

        // ⚡ 快捷获取 UI 布局状态（防止字段为空，提供兜底默认值）
        uiState: (state) => ({
            ...DEFAULT_UI_STATE,
            ...(state.blueprint?.ui_state || {})
        })
    },

    actions: {
        async loadParams() {
            try {
                this.paramsDefinitions = await blueprintApi.getParams()
            } catch (err) {
                console.error('加载节点参数定义失败', err)
            }
        },

        async loadProjectByPath(path) {
            if (!path) return
            await blueprintApi.verifyProject(path)
            this.currentProjectPath = path
            this.currentProjectName = path.split(/[\\/]/).pop() || path
            localStorage.setItem('lastProjectPath', path)

            const existing = this.recentProjects.filter(p => p.path !== path)
            this.recentProjects = [{ name: this.currentProjectName, path }, ...existing].slice(0, 5)
            localStorage.setItem('recentProjects', JSON.stringify(this.recentProjects))

            await this.loadProjectData()
            await this.loadContext()
        },

        async loadProjectData() {
            if (!this.currentProjectPath) return
            const data = await blueprintApi.getBlueprint(this.currentProjectPath)

            // ⚡ 读取保存的 ui_state，若为空则补充默认值
            if (!data.ui_state) {
                data.ui_state = { ...DEFAULT_UI_STATE }
            } else {
                data.ui_state = { ...DEFAULT_UI_STATE, ...data.ui_state }
            }

            this.blueprint = data
            this.currentProjectName = data.project_name || this.currentProjectName

            if (data.tasks && data.tasks.length > 0) {
                if (!this.currentTaskId || !data.tasks.some(t => t.task_id === this.currentTaskId)) {
                    this.currentTaskId = data.tasks[0].task_id
                }
            } else {
                this.currentTaskId = null
            }
            this.taskNodesVersion++
        },

        // ⚡ 统一修改并保存 UI 状态（支持单项或批量更新，自动防抖落盘）
        updateUiState(keyOrObject, value) {
            if (!this.blueprint.ui_state) {
                this.blueprint.ui_state = { ...DEFAULT_UI_STATE }
            }

            if (typeof keyOrObject === 'object') {
                Object.assign(this.blueprint.ui_state, keyOrObject)
            } else if (typeof keyOrObject === 'string') {
                this.blueprint.ui_state[keyOrObject] = value
            }

            // 自动触发放抖落盘写入 project_blueprint.json
            this.saveBlueprintDebounced()
        },

        async loadTasks() {
            await this.loadProjectData()
            return this.tasks
        },

        async loadContext() {
            if (!this.currentProjectPath) return
            try {
                const ctx = await workspaceApi.getContext(this.currentProjectPath)
                if (ctx) {
                    this.currentContext = {
                        workMode: ctx.windowTitle ? 'window' : 'desktop',
                        ...ctx
                    }
                }
            } catch (err) {
                console.error('加载工作区上下文失败', err)
            }
        },

        async setCurrentContext(context) {
            this.currentContext = { ...context }
            if (this.currentProjectPath) {
                await workspaceApi.saveContext(this.currentProjectPath, context)
            }
        },

        saveBlueprintDebounced: debounce(async function () {
            if (!this.currentProjectPath) return
            try {
                await blueprintApi.saveBlueprint(this.currentProjectPath, this.blueprint)
            } catch (err) {
                console.error('防抖保存蓝图失败', err)
            }
        }, 400),

        async saveBlueprintImmediately() {
            if (!this.currentProjectPath) return
            await blueprintApi.saveBlueprint(this.currentProjectPath, this.blueprint)
        },

        async saveCurrentTask() {
            await this.saveBlueprintImmediately()
        },

        async loadTaskNodes(taskId) {
            if (!this.currentProjectPath || !taskId) return []
            return await blueprintApi.getTaskNodes(taskId, this.currentProjectPath)
        },

        async createNewTask(taskName) {
            if (!this.currentProjectPath) return
            const res = await blueprintApi.createTask(this.currentProjectPath, { task_name: taskName, nodes: [] })
            await this.loadProjectData()
            return res
        },

        async runTask(taskId, startNodeId) {
            if (this.activeEventSource) {
                this.activeEventSource.close()
                this.activeEventSource = null
            }

            this.executionLogs = []
            // 运行任务时如果底部面板被收起了，自动展开
            this.updateUiState('bottomPanelExpanded', true)

            logger.info('Store', `正在准备启动任务: ${taskId}`)

            try {
                const res = await blueprintApi.runTask(this.currentProjectPath, taskId, startNodeId, this.blueprint)
                const executionId = res.execution_id || res.data?.execution_id

                if (!executionId) {
                    logger.error('Store', '启动任务失败: 未获得 execution_id', res)
                    this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: '❌ 任务启动失败: 未获得 execution_id' })
                    return res
                }

                this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: `🚀 任务 [${taskId}] 已启动...` })

                const sseUrl = `/api/execution/${executionId}/stream`
                const eventSource = new EventSource(sseUrl)
                this.activeEventSource = eventSource

                eventSource.onmessage = (event) => {
                    try {
                        const payload = JSON.parse(event.data)
                        const newLogs = payload.logs || []
                        const status = payload.status || {}

                        if (Array.isArray(newLogs) && newLogs.length > 0) {
                            newLogs.forEach(logItem => {
                                const msg = typeof logItem === 'string' ? logItem : logItem.message
                                this.executionLogs.push(typeof logItem === 'string' ? { time: new Date().toLocaleTimeString(), message: logItem } : logItem)
                                logger.debug('SSE-Stream', msg)
                            })
                        }

                        if (status.status === 'success' || status.status === 'error') {
                            logger.info('Store', `任务流程结束, 最终状态: ${status.status}`)
                            this.executionLogs.push({
                                time: new Date().toLocaleTimeString(),
                                message: status.status === 'success' ? '🎉 任务流程执行完毕 ✅' : `💥 任务终止: ${status.message}`
                            })
                            eventSource.close()
                            this.activeEventSource = null
                        }
                    } catch (e) {
                        logger.error('Store', '解析 SSE 日志流数据失败', e)
                    }
                }

                eventSource.onerror = (err) => {
                    logger.warn('Store', 'SSE 日志流连接已关闭或断开', err)
                    eventSource.close()
                    this.activeEventSource = null
                }

                return res
            } catch (err) {
                logger.error('Store', 'runTask 触发异常', err)
                this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: `❌ 启动任务失败: ${err.message}` })
                throw err
            }
        },

        toggleMinimap() {
            this.updateUiState('minimapExpanded', !this.uiState.minimapExpanded)
        },

        toggleLogPanel() {
            this.updateUiState('bottomPanelExpanded', !this.uiState.bottomPanelExpanded)
        }
    }
})