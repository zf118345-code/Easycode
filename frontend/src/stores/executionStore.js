import { defineStore } from 'pinia'
import { blueprintApi } from '@/api/blueprintApi'
import { logger } from '@/utils/logger'

export const useExecutionStore = defineStore('execution', {
    state: () => ({
        executionLogs: [],
        activeEventSource: null,
        currentExecutionId: null
    }),

    actions: {
        async runTask(taskId, startNodeId) {
            if (this.activeEventSource) {
                this.activeEventSource.close()
                this.activeEventSource = null
            }
            this.executionLogs = []

            const { useProjectStore } = await import('./projectStore')
            const projectStore = useProjectStore()

            projectStore.updateUiState('bottomPanelExpanded', true)
            logger.info('Store', `正在准备启动任务: ${taskId}`)
            try {
                await projectStore.saveBlueprintImmediately()
                const res = await blueprintApi.runTask(projectStore.currentProjectPath, taskId, startNodeId, projectStore.blueprint)
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
        }
    }
})
