// frontend/src/stores/index.js
// 修复：loadProjectData 增加 try/catch，拓扑数据同步到 blueprint.topology
// 修复：saveBlueprintDebounced 发送完整 blueprint（含 topology/edges）
// 新增：stopExecution 停止执行 action
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
            ui_state: { ...DEFAULT_UI_STATE },
            edges: [],
            topology: { nodes: [], edges: [] }
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
        activeEventSource: null,

        // 双画布模式
        canvasMode: 'workflow',
        // 拓扑地图蓝图数据
        topologyBlueprint: { nodes: [], edges: [] },
        selectedTopologyNodeId: null,
        // 当前执行的 execution_id（用于停止）
        currentExecutionId: null
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
        uiState: (state) => ({
            ...DEFAULT_UI_STATE,
            ...(state.blueprint?.ui_state || {})
        }),
        topologyNodes: (state) => state.topologyBlueprint.nodes || [],
        topologyEdges: (state) => state.topologyBlueprint.edges || [],
        currentTopologyNode: (state) => {
            const nodes = state.topologyBlueprint.nodes || []
            return nodes.find(n => n.node_id === state.selectedTopologyNodeId) || null
        }
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
            try {
                await blueprintApi.verifyProject(path)
            } catch (err) {
                logger.error('Store', '验证项目路径失败', err)
            }
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
            try {
                const data = await blueprintApi.getBlueprint(this.currentProjectPath)

                // 兜底：确保关键字段存在
                if (!data.ui_state) {
                    data.ui_state = { ...DEFAULT_UI_STATE }
                } else {
                    data.ui_state = { ...DEFAULT_UI_STATE, ...data.ui_state }
                }
                if (!data.tasks) data.tasks = []
                if (!data.variables) data.variables = {}
                if (!data.edges) data.edges = []
                if (!data.topology) data.topology = { nodes: [], edges: [] }

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

                // 同步载入拓扑蓝图数据
                this.loadTopologyFromBlueprint()
            } catch (err) {
                logger.error('Store', 'loadProjectData 失败', err)
                // 不抛出，让 UI 继续渲染空状态
                this.blueprint = {
                    project_name: this.currentProjectName,
                    tasks: [],
                    variables: {},
                    ui_state: { ...DEFAULT_UI_STATE },
                    edges: [],
                    topology: { nodes: [], edges: [] }
                }
            }
        },

        updateUiState(keyOrObject, value) {
            if (!this.blueprint.ui_state) {
                this.blueprint.ui_state = { ...DEFAULT_UI_STATE }
            }
            if (typeof keyOrObject === 'object') {
                Object.assign(this.blueprint.ui_state, keyOrObject)
            } else if (typeof keyOrObject === 'string') {
                this.blueprint.ui_state[keyOrObject] = value
            }
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
                // 确保拓扑数据同步到 blueprint
                this.syncTopologyToBlueprint()
                await blueprintApi.saveBlueprint(this.currentProjectPath, this.blueprint)
            } catch (err) {
                console.error('防抖保存蓝图失败', err)
            }
        }, 400),

        async saveBlueprintImmediately() {
            if (!this.currentProjectPath) return
            try {
                this.syncTopologyToBlueprint()
                await blueprintApi.saveBlueprint(this.currentProjectPath, this.blueprint)
            } catch (err) {
                console.error('保存蓝图失败', err)
                throw err
            }
        },

        // 同步拓扑运行态数据到 blueprint.topology
        syncTopologyToBlueprint() {
            if (!this.blueprint) return
            this.blueprint.topology = {
                nodes: JSON.parse(JSON.stringify(this.topologyBlueprint.nodes || [])),
                edges: JSON.parse(JSON.stringify(this.topologyBlueprint.edges || []))
            }
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
            this.updateUiState('bottomPanelExpanded', true)

            logger.info('Store', `正在准备启动任务: ${taskId}`)

            try {
                // 确保最新蓝图数据已保存
                await this.saveBlueprintImmediately()

                const res = await blueprintApi.runTask(this.currentProjectPath, taskId, startNodeId, this.blueprint)
                const executionId = res.execution_id || res.data?.execution_id

                if (!executionId) {
                    logger.error('Store', '启动任务失败: 未获得 execution_id', res)
                    this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: '任务启动失败: 未获得 execution_id' })
                    return res
                }

                this.currentExecutionId = executionId
                this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: `任务 [${taskId}] 已启动...` })

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

                        if (status.status === 'success' || status.status === 'error' || status.status === 'stopped') {
                            logger.info('Store', `任务流程结束, 最终状态: ${status.status}`)
                            this.executionLogs.push({
                                time: new Date().toLocaleTimeString(),
                                message: status.status === 'success' ? '任务流程执行完毕' : (status.status === 'stopped' ? '任务已停止' : `任务终止: ${status.message}`)
                            })
                            eventSource.close()
                            this.activeEventSource = null
                            this.currentExecutionId = null
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
                this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: `启动任务失败: ${err.message}` })
                throw err
            }
        },

        // 新增：停止当前执行
        async stopExecution() {
            if (!this.currentExecutionId) {
                logger.warn('Store', '没有正在运行的执行')
                return
            }
            try {
                await blueprintApi.stopExecution(this.currentExecutionId)
                logger.info('Store', `已发送停止信号: ${this.currentExecutionId}`)
            } catch (err) {
                logger.error('Store', '停止执行失败', err)
            }
        },

        toggleMinimap() {
            this.updateUiState('minimapExpanded', !this.uiState.minimapExpanded)
        },

        toggleLogPanel() {
            this.updateUiState('bottomPanelExpanded', !this.uiState.bottomPanelExpanded)
        },

        // ===================== 双画布模式 / 拓扑画布 =====================

        setCanvasMode(mode) {
            if (mode !== 'workflow' && mode !== 'topology') return
            if (this.canvasMode === mode) return
            this.canvasMode = mode
            if (mode === 'topology') {
                this.selectedTopologyNodeId = null
            }
            this.updateUiState('canvasMode', mode)
        },

        loadTopologyFromBlueprint() {
            const topo = this.blueprint?.topology
            if (topo && Array.isArray(topo.nodes) && Array.isArray(topo.edges)) {
                this.topologyBlueprint = {
                    nodes: JSON.parse(JSON.stringify(topo.nodes)),
                    edges: JSON.parse(JSON.stringify(topo.edges))
                }
            } else {
                this.topologyBlueprint = { nodes: [], edges: [] }
            }
            this.selectedTopologyNodeId = null
        },

        saveTopologyToBlueprint() {
            this.syncTopologyToBlueprint()
            this.saveBlueprintDebounced()
        },

        addTopologyNode(nodeData) {
            if (!nodeData || !nodeData.node_id) return
            const exists = (this.topologyBlueprint.nodes || []).some(n => n.node_id === nodeData.node_id)
            if (exists) return
            const node = {
                node_id: nodeData.node_id,
                node_name: nodeData.node_name || nodeData.label || '页面状态',
                type: nodeData.type || 'page_state',
                page_id: nodeData.page_id || '',
                label: nodeData.label || '',
                position: nodeData.position || { x: 0, y: 0 },
                features: nodeData.features || [],
                feature_mode: nodeData.feature_mode || 'and',
                exits: nodeData.exits || [],
                params: nodeData.params || {},
                condition: nodeData.condition || null
            }
            this.topologyBlueprint.nodes.push(node)
            this.saveTopologyToBlueprint()
        },

        updateTopologyNode(nodeId, data) {
            if (!nodeId || !data) return
            const node = (this.topologyBlueprint.nodes || []).find(n => n.node_id === nodeId)
            if (!node) return
            Object.assign(node, data)
            this.saveTopologyToBlueprint()
        },

        removeTopologyNode(nodeId) {
            if (!nodeId) return
            this.topologyBlueprint.nodes = (this.topologyBlueprint.nodes || []).filter(n => n.node_id !== nodeId)
            this.topologyBlueprint.edges = (this.topologyBlueprint.edges || []).filter(e => {
                return e.source !== nodeId && e.target !== nodeId
            })
            if (this.selectedTopologyNodeId === nodeId) {
                this.selectedTopologyNodeId = null
            }
            this.saveTopologyToBlueprint()
        },

        addTopologyEdge(edgeData) {
            if (!edgeData) return
            const edgeId = edgeData.edge_id || `edge_${Date.now()}`
            const exists = (this.topologyBlueprint.edges || []).some(e => e.edge_id === edgeId)
            if (exists) return
            // 修复：只阻止完全相同的边（source + target + source_port 都相同）
            // 允许同一对节点之间存在多条不同端口的连线（如成功+失败）
            const dupRoute = (this.topologyBlueprint.edges || []).some(e =>
                e.source === edgeData.source &&
                e.target === edgeData.target &&
                (e.source_port || 'exit') === (edgeData.source_port || 'exit'))
            if (dupRoute) return
            const edge = {
                edge_id: edgeId,
                source: edgeData.source,
                target: edgeData.target,
                source_exit: edgeData.source_exit || 'default',
                source_port: edgeData.source_port || 'exit',
                label: edgeData.label || '',
                condition: edgeData.condition || null,
                action: edgeData.action || ''
            }
            this.topologyBlueprint.edges.push(edge)
            this.saveTopologyToBlueprint()
        },

        removeTopologyEdge(edgeId) {
            if (!edgeId) return
            this.topologyBlueprint.edges = (this.topologyBlueprint.edges || []).filter(e => e.edge_id !== edgeId)
            this.saveTopologyToBlueprint()
        }
    }
})