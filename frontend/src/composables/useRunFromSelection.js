import { computed, unref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '@/api/client'
import { useExecutionStore, useProjectStore, useUiStore } from '@/stores'

export function useRunFromSelection(options = {}) {
    const projectStore = useProjectStore()
    const uiStore = useUiStore()
    const executionStore = useExecutionStore()

    const selectedNodeIds = computed(() => uiStore.selectedNodeIds || [])
    const selectedNodeId = computed(() => selectedNodeIds.value.length === 1 ? selectedNodeIds.value[0] : null)
    const externallyBlocked = computed(() => Boolean(unref(options.blocked)))

    const disabledReason = computed(() => {
        if (projectStore.readOnly) return '项目以只读方式打开，不能运行或修改脚本'
        if (uiStore.canvasMode !== 'workflow') return '请切换到业务流程后执行节点'
        if (executionStore.isRunning || executionStore.isPaused) return '已有任务正在执行或暂停，请先停止'
        if (externallyBlocked.value) return options.blockedReason || '当前模式下不能运行节点'
        if (selectedNodeIds.value.length === 0) return '请先选中一个节点'
        if (selectedNodeIds.value.length > 1) return '只能从一个当前节点开始执行'
        return ''
    })
    const canRun = computed(() => !disabledReason.value)

    const findTaskId = nodeId => (projectStore.blueprint?.main_graph?.nodes || []).some(node => node.node_id === nodeId) ? 'main' : null

    const runFromNode = async nodeId => {
        if (nodeId && (uiStore.selectedNodeIds?.length !== 1 || uiStore.selectedNodeIds[0] !== nodeId)) {
            uiStore.selectNode(nodeId)
        }
        const reason = disabledReason.value
        if (reason) {
            ElMessage.warning(reason)
            return { status: 'blocked', reason }
        }
        const currentNodeId = selectedNodeId.value
        const taskId = findTaskId(currentNodeId)
        if (!taskId) {
            const reason = '未找到当前节点所属的业务流程'
            ElMessage.error(reason)
            return { status: 'blocked', reason }
        }
        try {
            const report = await client.post('/api/exporter/preflight', {
                project_path: projectStore.currentProjectPath,
                entry_task_id: taskId,
                entry_node_id: currentNodeId,
                scope: 'debug'
            })
            const errors = (report.issues || []).filter(issue => issue.severity === 'error')
            if (errors.length) {
                await ElMessageBox.alert(
                    errors.slice(0, 12).map(issue => `• ${issue.message}`).join('\n'),
                    `运行前检查失败（${errors.length} 项）`,
                    { type: 'error', confirmButtonText: '返回修改' }
                )
                return { status: 'blocked', report }
            }
            if (report.counts?.warning) {
                ElMessage.warning(`运行前检查发现 ${report.counts.warning} 项警告，IDE 调试仍可继续`)
            }
            const result = await executionStore.runTask(taskId, currentNodeId)
            if (result?.status === 'started') ElMessage.success('已从当前节点开始执行')
            else ElMessage.error(`启动失败：${result?.error || '未知错误'}`)
            return result
        } catch (error) {
            ElMessage.error(`运行前检查失败：${error?.message || error}`)
            return { status: 'error', error }
        }
    }

    const runSelectedNode = () => runFromNode(selectedNodeId.value)

    return { selectedNodeId, selectedNodeIds, canRun, disabledReason, runFromNode, runSelectedNode }
}
