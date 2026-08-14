import { defineStore } from 'pinia'
import { blueprintApi } from '@/api/blueprintApi'
import { logger } from '@/utils/logger'
import { useTopologyStore } from './topologyStore'
import debounce from 'lodash-es/debounce'

export const DEFAULT_UI_STATE = {
    leftPanelExpanded: true,
    leftPanelWidth: 260,
    rightPanelExpanded: true,
    rightPanelWidth: 320,
    bottomPanelExpanded: true,
    bottomPanelHeight: 200,
    minimapExpanded: true
}

export const useProjectStore = defineStore('project', {
    state: () => ({
        currentProjectPath: localStorage.getItem('lastProjectPath') || null,
        currentProjectName: '',
        // 内存合并视图：project.json + workflow.json + topology.json 的聚合（组件消费）
        blueprint: {
            project_name: '',
            tasks: [],
            variables: {},
            ui_state: { ...DEFAULT_UI_STATE },
            edges: [],
            topology: { tasks: [], edges: [] }
        },
        paramsDefinitions: {},
        currentTaskId: null,
        recentProjects: JSON.parse(localStorage.getItem('recentProjects') || '[]'),
        taskNodesVersion: 0
    }),

    getters: {
        tasks: (state) => state.blueprint.tasks || [],
        currentTaskData: (state) => state.blueprint,
        currentTask: (state) => (state.blueprint.tasks || []).find(t => t.task_id === state.currentTaskId),
        nodes: (state) => {
            const task = (state.blueprint.tasks || []).find(t => t.task_id === state.currentTaskId)
            return task ? task.nodes || [] : []
        },
        params: (state) => state.paramsDefinitions,
        uiState: (state) => ({
            ...DEFAULT_UI_STATE,
            ...(state.blueprint?.ui_state || {})
        }),
        // ===== 画布数据源（Step 3 统一画布使用） =====
        workflowData: (state) => ({
            tasks: state.blueprint.tasks || [],
            edges: state.blueprint.edges || []
        }),
        topologyData() {
            // topology.json 文件结构 {tasks, edges}（经 topologyStore 同步，响应式）
            return useTopologyStore().syncTopologyToBlueprint()
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

            const { useContextStore } = await import('./contextStore')
            await useContextStore().loadContext()
        },

        async loadProjectData() {
            if (!this.currentProjectPath) return
            try {
                const [meta, workflow, topology] = await Promise.all([
                    blueprintApi.getBlueprint(this.currentProjectPath),
                    blueprintApi.getWorkflow(this.currentProjectPath),
                    blueprintApi.getTopology(this.currentProjectPath)
                ])
                const data = {
                    project_name: meta?.project_name || this.currentProjectName,
                    variables: meta?.variables || {},
                    ui_state: meta?.ui_state ? { ...DEFAULT_UI_STATE, ...meta.ui_state } : { ...DEFAULT_UI_STATE },
                    tasks: workflow?.tasks || [],
                    edges: workflow?.edges || [],
                    topology: topology && (Array.isArray(topology.tasks) || Array.isArray(topology.nodes))
                        ? topology
                        : { tasks: [], edges: [] }
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

                const { useTopologyStore } = await import('./topologyStore')
                useTopologyStore().loadTopologyFromBlueprint(this.blueprint)
            } catch (err) {
                logger.error('Store', 'loadProjectData 失败', err)
                this.blueprint = {
                    project_name: this.currentProjectName,
                    tasks: [],
                    variables: {},
                    ui_state: { ...DEFAULT_UI_STATE },
                    edges: [],
                    topology: { tasks: [], edges: [] }
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
            this.saveProjectMetaDebounced()
        },

        toggleMinimap() {
            this.updateUiState('minimapExpanded', !this.uiState.minimapExpanded)
        },

        toggleLogPanel() {
            this.updateUiState('bottomPanelExpanded', !this.uiState.bottomPanelExpanded)
        },

        async loadTasks() {
            await this.loadProjectData()
            return this.tasks
        },

        // ===== 三文件保存 =====

        async saveProjectMeta() {
            if (!this.currentProjectPath) return
            try {
                await blueprintApi.saveBlueprint(this.currentProjectPath, {
                    project_name: this.blueprint.project_name,
                    variables: this.blueprint.variables || {},
                    ui_state: this.blueprint.ui_state || {}
                })
            } catch (err) {
                console.error('保存项目元数据失败', err)
                throw err
            }
        },

        async saveWorkflowImmediately() {
            if (!this.currentProjectPath) return
            try {
                await blueprintApi.saveWorkflow(this.currentProjectPath, {
                    tasks: this.blueprint.tasks || [],
                    edges: this.blueprint.edges || []
                })
            } catch (err) {
                console.error('保存流程画布失败', err)
                throw err
            }
        },

        async saveTopologyData() {
            if (!this.currentProjectPath) return
            try {
                const { useTopologyStore } = await import('./topologyStore')
                this.blueprint.topology = useTopologyStore().syncTopologyToBlueprint()
                await blueprintApi.saveTopology(this.currentProjectPath, this.blueprint.topology)
            } catch (err) {
                console.error('保存拓扑地图失败', err)
                throw err
            }
        },

        saveProjectMetaDebounced: debounce(async function () {
            if (!this.currentProjectPath) return
            try {
                await this.saveProjectMeta()
            } catch (err) {
                console.error('防抖保存项目元数据失败', err)
            }
        }, 400),

        saveTopologyDebounced: debounce(async function () {
            if (!this.currentProjectPath) return
            try {
                await this.saveTopologyData()
            } catch (err) {
                console.error('防抖保存拓扑地图失败', err)
            }
        }, 400),

        saveBlueprintDebounced: debounce(async function () {
            if (!this.currentProjectPath) return
            try {
                await Promise.all([this.saveProjectMeta(), this.saveWorkflowImmediately(), this.saveTopologyData()])
            } catch (err) {
                console.error('防抖保存蓝图失败', err)
            }
        }, 400),

        async saveBlueprintImmediately() {
            if (!this.currentProjectPath) return
            try {
                await Promise.all([this.saveProjectMeta(), this.saveWorkflowImmediately(), this.saveTopologyData()])
            } catch (err) {
                console.error('保存蓝图失败', err)
                throw err
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
        }
    }
})
