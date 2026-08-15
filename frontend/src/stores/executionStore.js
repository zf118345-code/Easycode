import { defineStore } from 'pinia'
import { blueprintApi } from '@/api/blueprintApi'
import { executionApi } from '@/api/executionApi'
import { logger } from '@/utils/logger'

export const useExecutionStore = defineStore('execution', {
    state: () => ({
        executionLogs: [],
        activeEventSource: null,
        currentExecutionId: null,
        // ===== 调试会话状态 =====
        executionState: 'idle', // idle | running | paused | success | error | stopped
        executionPaused: false,
        executionVariables: [],  // [{ name, type, value, level }]
        executionCurrentVariables: {},  // 暂停时变量快照（对象 {name: value}，变量监控面板用）
        executionPrevVariables: {},     // 上一节点变量快照（对比用）
        executionCallstack: [],  // [{ function, node_id, task_id, line? }]
        currentActiveNodeId: null, // 调试命中时高亮的节点
        _pollTimer: null
    }),

    getters: {
        isRunning(state) { return state.executionState === 'running' },
        isPaused(state) { return state.executionState === 'paused' },
        hasSession(state) { return !!state.currentExecutionId }
    },

    actions: {
        async runTask(taskId, startNodeId, options = {}) {
            if (this.activeEventSource) {
                this.activeEventSource.close()
                this.activeEventSource = null
            }
            this.executionLogs = []
            this.executionVariables = []
            this.executionCallstack = []
            this.executionState = 'running'
            this.executionPaused = false
            this.currentActiveNodeId = null

            const { useProjectStore } = await import('./projectStore')
            const projectStore = useProjectStore()

            // 如果带断点，则传给启动请求（让后端在启动时同步断点）
            const { useUiStore } = await import('./uiStore')
            const breakpoints = options.breakpoints ?? useUiStore().getBreakpointList()

            projectStore.updateUiState('bottomPanelExpanded', true)
            logger.info('Store', `正在准备启动任务: ${taskId}`)
            try {
                await projectStore.saveBlueprintImmediately()
                const res = await blueprintApi.runTask(
                    projectStore.currentProjectPath,
                    taskId,
                    startNodeId,
                    {
                        ...projectStore.blueprint,
                        __debug: { breakpoints }
                    }
                )
                const executionId = res.execution_id || res.data?.execution_id
                if (!executionId) {
                    logger.error('Store', '启动任务失败: 未获得 execution_id', res)
                    this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: '任务启动失败: 未获得 execution_id' })
                    this.executionState = 'error'
                    return res
                }
                this.currentExecutionId = executionId
                this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: `任务 [${taskId}] 已启动...` })
                if (breakpoints?.length) {
                    this.executionLogs.push({
                        time: new Date().toLocaleTimeString(),
                        message: `⚙ 调试模式开启，已下发 ${breakpoints.length} 个断点`
                    })
                }
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
                        // SSE 推送调试状态（命中断点时）
                        if (status.state === 'paused' || payload.debug_state === 'paused') {
                            this.executionState = 'paused'
                            this.executionPaused = true
                            this.currentActiveNodeId = status.node_id || payload.node_id || null
                            if (payload.callstack) this.executionCallstack = payload.callstack
                            this.executionLogs.push({
                                time: new Date().toLocaleTimeString(),
                                message: `⏸ 命中断点 @ ${this.currentActiveNodeId || '未知节点'}`
                            })
                            this.getExecutionVariables().catch(e => logger.warn('拉取变量失败', e))
                        } else if (status.state === 'running') {
                            this.executionState = 'running'
                            this.executionPaused = false
                        }
                        if (status.status === 'success') {
                            logger.info('Store', `任务流程结束, 最终状态: success`)
                            this.executionState = 'success'
                            this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: '✅ 任务流程执行完毕' })
                            this._cleanupSession(eventSource)
                        } else if (status.status === 'stopped') {
                            this.executionState = 'stopped'
                            this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: '⛔ 任务已停止' })
                            this._cleanupSession(eventSource)
                        } else if (status.status === 'error') {
                            this.executionState = 'error'
                            this.executionLogs.push({
                                time: new Date().toLocaleTimeString(),
                                message: `❌ 任务终止: ${status.message || '未知错误'}`
                            })
                            this._cleanupSession(eventSource)
                        }
                    } catch (e) {
                        logger.error('Store', '解析 SSE 日志流数据失败', e)
                    }
                }
                eventSource.onerror = (err) => {
                    logger.warn('Store', 'SSE 日志流连接已关闭或断开', err)
                    this._cleanupSession(eventSource)
                }
                // 调试状态轮询：暂停/单步/变量快照以后端调试会话为准
                this.startDebugPolling()
                return res
            } catch (err) {
                logger.error('Store', 'runTask 触发异常', err)
                this.executionState = 'error'
                this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: `启动任务失败: ${err.message}` })
                throw err
            }
        },

        _cleanupSession(eventSource) {
            try { eventSource?.close() } catch {}
            if (this.activeEventSource === eventSource) this.activeEventSource = null
            this.stopDebugPolling()
            if (['success', 'error', 'stopped'].includes(this.executionState)) {
                this.currentExecutionId = null
                this.currentActiveNodeId = null
                this.executionPaused = false
            }
        },

        async stopExecution() {
            if (!this.currentExecutionId) {
                logger.warn('Store', '没有正在运行的执行')
                return
            }
            try {
                await executionApi.stop(this.currentExecutionId)
                logger.info('Store', `已发送停止信号: ${this.currentExecutionId}`)
            } catch (err) {
                logger.error('Store', '停止执行失败', err)
                // 回退：调用旧 blueprintApi.stopExecution
                try { await blueprintApi.stopExecution(this.currentExecutionId) } catch (_) {}
            }
        },

        // ===== 调试控制（单步/暂停/恢复） =====
        async pauseExecution() {
            if (!this.currentExecutionId) return
            try {
                await executionApi.pause(this.currentExecutionId)
                this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: '⏸ 已请求暂停（将在下一节点前生效）' })
                // 状态由调试轮询确认（暂停是异步生效，不做乐观置位）
            } catch (err) { logger.error('暂停失败', err); throw err }
        },
        async resumeExecution() {
            if (!this.currentExecutionId) return
            try {
                await executionApi.resume(this.currentExecutionId)
                this.executionState = 'running'
                this.executionPaused = false
                this.currentActiveNodeId = null
                this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: '▶ 已恢复执行' })
            } catch (err) { logger.error('恢复失败', err); throw err }
        },
        async stepOverExecution() {
            if (!this.currentExecutionId) return
            try {
                await executionApi.step(this.currentExecutionId, 'over')
                this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: '⏭ 单步跳过' })
                setTimeout(() => this.pollDebugState(), 300)
            } catch (err) { logger.error('单步跳过失败', err); throw err }
        },
        async stepIntoExecution() {
            if (!this.currentExecutionId) return
            try {
                await executionApi.step(this.currentExecutionId, 'into')
                this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: '⏬ 单步进入' })
                setTimeout(() => this.pollDebugState(), 300)
            } catch (err) { logger.error('单步进入失败', err); throw err }
        },
        async stepOutExecution() {
            if (!this.currentExecutionId) return
            try {
                await executionApi.step(this.currentExecutionId, 'out')
                this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: '⏫ 单步跳出' })
                setTimeout(() => this.pollDebugState(), 300)
            } catch (err) { logger.error('单步跳出失败', err); throw err }
        },

        // ===== 调试状态轮询 & 变量获取 =====
        async pollDebugState() {
            if (!this.currentExecutionId) return null
            try {
                const state = await executionApi.getDebugState(this.currentExecutionId)
                if (state?.status || state?.is_paused !== undefined) {
                    // 兼容两种返回：执行记录状态（status）或调试会话状态（is_paused/current_node_id）
                    const isPaused = state.is_paused === true || state.status === 'paused'
                    const status = state.status || (isPaused ? 'paused' : 'running')
                    this.executionState = status
                    this.executionPaused = isPaused
                    this.currentActiveNodeId = state.current_node_id || state.node_id || this.currentActiveNodeId
                    if (state.callstack) this.executionCallstack = state.callstack
                    // 变量快照：一次轮询取全量（当前值 + 上一节点值），暂停时才有对比意义
                    if (isPaused) {
                        this.executionCurrentVariables = state.executor_variables || state.variables || {}
                        this.executionPrevVariables = state.prev_variables || {}
                    } else {
                        this.executionCurrentVariables = {}
                        this.executionPrevVariables = {}
                    }
                }
                return state
            } catch (err) {
                logger.warn('调试轮询失败', err)
                return null
            }
        },
        async getExecutionVariables(level = 0) {
            if (!this.currentExecutionId) { this.executionVariables = []; return [] }
            try {
                const vars = await executionApi.getVariables(this.currentExecutionId, level)
                this.executionVariables = Array.isArray(vars) ? vars : (vars?.variables || [])
                return this.executionVariables
            } catch (err) {
                logger.warn('拉取变量失败', err)
                return []
            }
        },
        startDebugPolling(intervalMs = 1000) {
            this.stopDebugPolling()
            let failCount = 0
            this._pollTimer = setInterval(async () => {
                if (!this.currentExecutionId) { this.stopDebugPolling(); return }
                const state = await this.pollDebugState()
                if (state === null) {
                    // 轮询失败（会话不存在/已结束/后端旧版）：连续 3 次自动停止，避免无效请求空转
                    failCount += 1
                    if (failCount >= 3) this.stopDebugPolling()
                } else {
                    failCount = 0
                }
            }, intervalMs)
        },
        stopDebugPolling() {
            if (this._pollTimer) {
                clearInterval(this._pollTimer)
                this._pollTimer = null
            }
        },
        clearLogs() {
            this.executionLogs = []
        }
    }
})
