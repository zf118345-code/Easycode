import { defineStore } from 'pinia'
import { blueprintApi } from '@/api/blueprintApi'
import { executionApi } from '@/api/executionApi'
import { logger } from '@/utils/logger'

// ⚡ #6 日志条数上限（长任务不无限增长）
const MAX_EXECUTION_LOGS = 500

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
            // ⚡ 并发防护：已有会话在执行/暂停时拒绝二次启动（UI 层已禁用入口，此处为最后防线）
            if (this.executionState === 'running' || this.executionState === 'paused') {
                logger.warn('Store', '已有执行会话，拒绝并发启动')
                return { status: 'busy', error: '已有任务正在执行/暂停，请先停止再运行' }
            }
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
                    this._pushLog({ time: new Date().toLocaleTimeString(), message: '任务启动失败: 未获得 execution_id' })
                    this.executionState = 'error'
                    return res
                }
                this.currentExecutionId = executionId
                this._pushLog({ time: new Date().toLocaleTimeString(), message: `任务 [${taskId}] 已启动...` })
                if (breakpoints?.length) {
                    this._pushLog({
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
                                this._pushLog(typeof logItem === 'string' ? { time: new Date().toLocaleTimeString(), message: logItem } : logItem)
                                logger.debug('SSE-Stream', msg)
                            })
                        }
                        // ⚡ #5 调试状态随 SSE 即时推送（暂停/恢复/单步 0.2s 内反映，取代 1s 轮询）
                        const debugState = payload.debug_state
                        if (debugState && debugState.state === 'paused') {
                            this.executionState = 'paused'
                            this.executionPaused = true
                            this.currentActiveNodeId = debugState.node_id || null
                            const reason = debugState.pause_reason === 'breakpoint' ? '命中断点' : '已暂停'
                            this._pushLog({
                                time: new Date().toLocaleTimeString(),
                                message: `⏸ ${reason} @ ${this.currentActiveNodeId || '未知节点'}`
                            })
                            this.getExecutionVariables().catch(e => logger.warn('拉取变量失败', e))
                        } else if (debugState && debugState.state === 'running') {
                            this.executionState = 'running'
                            this.executionPaused = false
                            if (debugState.node_id) this.currentActiveNodeId = debugState.node_id
                        }
                        if (status.status === 'success') {
                            logger.info('Store', `任务流程结束, 最终状态: success`)
                            this.executionState = 'success'
                            this._pushLog({ time: new Date().toLocaleTimeString(), message: '✅ 任务流程执行完毕' })
                            this._cleanupSession(eventSource)
                        } else if (status.status === 'stopped') {
                            this.executionState = 'stopped'
                            this._pushLog({ time: new Date().toLocaleTimeString(), message: '⛔ 任务已停止' })
                            this._cleanupSession(eventSource)
                        } else if (status.status === 'error') {
                            this.executionState = 'error'
                            this._pushLog({
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
                this._pushLog({ time: new Date().toLocaleTimeString(), message: `启动任务失败: ${err.message}` })
                throw err
            }
        },

        _cleanupSession(eventSource) {
            try { eventSource?.close() } catch {}
            if (this.activeEventSource === eventSource) this.activeEventSource = null
            this.stopDebugPolling()
            // 会话已结束/断开：无条件清理调试态，避免 UI 卡在暂停高亮（状态由调用方按需设置）
            this.currentExecutionId = null
            this.currentActiveNodeId = null
            this.executionPaused = false
            this.executionCurrentVariables = {}
            this.executionPrevVariables = {}
        },

        async stopExecution() {
            if (!this.currentExecutionId) {
                logger.warn('Store', '没有正在运行的执行')
                return
            }
            try {
                await executionApi.stop(this.currentExecutionId)
                // 乐观复位：停止信号已下发，UI 立即回到未启动状态（线程退出由后端收敛）
                this.executionState = 'stopped'
                this.executionPaused = false
                this.currentActiveNodeId = null
                this.executionCurrentVariables = {}
                this.executionPrevVariables = {}
                this.stopDebugPolling()
                this._pushLog({ time: new Date().toLocaleTimeString(), message: '⛔ 已发送停止信号，任务正在退出' })
                logger.info('Store', `已发送停止信号: ${this.currentExecutionId}`)
            } catch (err) {
                logger.error('Store', '停止执行失败', err)
                // 回退：调用旧 blueprintApi.stopExecution
                try { await blueprintApi.stopExecution(this.currentExecutionId) } catch (_) {}
                this.executionState = 'stopped'
                this.executionPaused = false
                this.currentActiveNodeId = null
                this.stopDebugPolling()
            }
        },

        // ===== 调试控制（单步/暂停/恢复） =====
        async pauseExecution() {
            if (!this.currentExecutionId) return
            try {
                await executionApi.pause(this.currentExecutionId)
                this._pushLog({ time: new Date().toLocaleTimeString(), message: '⏸ 已请求暂停（将在下一节点前生效）' })
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
                this._pushLog({ time: new Date().toLocaleTimeString(), message: '▶ 已恢复执行' })
            } catch (err) { logger.error('恢复失败', err); throw err }
        },
        async stepOverExecution() {
            if (!this.currentExecutionId) return
            try {
                await executionApi.step(this.currentExecutionId, 'over')
                this._pushLog({ time: new Date().toLocaleTimeString(), message: '⏭ 单步跳过' })
                setTimeout(() => this.pollDebugState(), 300)
            } catch (err) { logger.error('单步跳过失败', err); throw err }
        },
        async stepIntoExecution() {
            if (!this.currentExecutionId) return
            try {
                await executionApi.step(this.currentExecutionId, 'into')
                this._pushLog({ time: new Date().toLocaleTimeString(), message: '⏬ 单步进入' })
                setTimeout(() => this.pollDebugState(), 300)
            } catch (err) { logger.error('单步进入失败', err); throw err }
        },
        async stepOutExecution() {
            if (!this.currentExecutionId) return
            try {
                await executionApi.step(this.currentExecutionId, 'out')
                this._pushLog({ time: new Date().toLocaleTimeString(), message: '⏫ 单步跳出' })
                setTimeout(() => this.pollDebugState(), 300)
            } catch (err) { logger.error('单步跳出失败', err); throw err }
        },

        // ===== 调试状态轮询 & 变量获取 =====
        async pollDebugState() {
            if (!this.currentExecutionId) return null
            try {
                const state = await executionApi.getDebugState(this.currentExecutionId)
                // ⚡ 会话已结束（cleanup 已清 currentExecutionId）：忽略飞行中的旧响应，
                // 避免"执行："标签在运行结束后被最后一批轮询响应重新点亮
                if (!this.currentExecutionId) return null
                if (state?.status || state?.is_paused !== undefined) {
                    // 兼容两种返回：执行记录状态（status）或调试会话状态（is_paused/current_node_id）
                    const isPaused = state.is_paused === true || state.status === 'paused'
                    const status = state.status || (isPaused ? 'paused' : 'running')
                    this.executionState = status
                    this.executionPaused = isPaused
                    this.currentActiveNodeId = state.current_node_id || state.node_id || this.currentActiveNodeId
                    if (state.callstack) this.executionCallstack = state.callstack
                    // 变量快照：current 始终取实时值；prev 仅暂停时替换，非暂停保留旧值（避免单步瞬间闪为 —）
                    this.executionCurrentVariables = state.executor_variables || state.variables || {}
                    if (isPaused) this.executionPrevVariables = state.prev_variables || {}
                }
                return state
            } catch (err) {
                // 会话已不存在（执行已结束，SSE 终态尚未到达）：静默收敛，不再无效轮询与打印噪音
                if (err?.status === 404 || /调试会话不存在/.test(err?.message || '')) {
                    this.stopDebugPolling()
                    return null
                }
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
            // ⚡ #5 调试状态已随 SSE 即时推送，不再启动 1s 轮询；
            // 保留一次性手动拉取（暂停/单步后立即同步变量快照）
            this.stopDebugPolling()
            this.pollDebugState().catch(() => {})
        },
        stopDebugPolling() {
            if (this._pollTimer) {
                clearInterval(this._pollTimer)
                this._pollTimer = null
            }
        },
        clearLogs() {
            this.executionLogs = []
        },

        // ⚡ #6 日志条数上限：保留最近 500 条，防止长任务 DOM/内存无限增长
        _pushLog(item) {
            this.executionLogs.push(item)
            if (this.executionLogs.length > MAX_EXECUTION_LOGS) {
                this.executionLogs.splice(0, this.executionLogs.length - MAX_EXECUTION_LOGS)
            }
        }
    }
})
