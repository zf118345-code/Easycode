// frontend/src/composables/useUndoRedo.js
// Undo/Redo 历史栈 composable，支持蓝图状态回溯
import { ref, computed } from 'vue'
import { logger } from '@/utils/logger'
import { useProjectStore } from '@/stores/projectStore'
import { getGraph, MAIN_GRAPH_ID } from '@/utils/flowModel'

const MAX_HISTORY = 50

/**
 * @param {Object} options - { getState, setState, maxHistory }
 *   getState: () => 当前状态快照（返回深拷贝）
 *   setState: (snapshot) => 恢复到指定状态
 *   maxHistory: 最大历史记录数
 */
export function useUndoRedo(options = {}) {
    const maxHistory = options.maxHistory || MAX_HISTORY
    const undoStack = ref([])
    const redoStack = ref([])

    const canUndo = computed(() => undoStack.value.length > 0)
    const canRedo = computed(() => redoStack.value.length > 0)

    /**
     * 获取当前状态快照
     */
    function getSnapshot() {
        if (options.getState) {
            return options.getState()
        }
        // 默认：从 projectStore 获取蓝图快照
        return null
    }

    /**
     * 恢复状态
     */
    function restoreSnapshot(snapshot) {
        if (options.setState) {
            options.setState(snapshot)
        }
    }

    /**
     * 提交当前状态到历史栈（在修改前调用）
     */
    function commit() {
        const snapshot = getSnapshot()
        if (!snapshot) return

        undoStack.value.push(snapshot)

        // 限制历史长度
        if (undoStack.value.length > maxHistory) {
            undoStack.value.shift()
        }

        // 新操作后清空 redo 栈
        redoStack.value = []
        logger.debug('UndoRedo', `已提交快照 (undo: ${undoStack.value.length}, redo: ${redoStack.value.length})`)
    }

    /**
     * 撤销
     */
    function undo() {
        if (undoStack.value.length === 0) {
            logger.warn('UndoRedo', '无可撤销操作')
            return
        }

        // 当前状态推入 redo 栈
        const current = getSnapshot()
        if (current) {
            redoStack.value.push(current)
        }

        // 弹出并恢复上一个状态
        const snapshot = undoStack.value.pop()
        restoreSnapshot(snapshot)
        logger.info('UndoRedo', `撤销 (undo: ${undoStack.value.length}, redo: ${redoStack.value.length})`)
    }

    /**
     * 重做
     */
    function redo() {
        if (redoStack.value.length === 0) {
            logger.warn('UndoRedo', '无可重做操作')
            return
        }

        // 当前状态推入 undo 栈
        const current = getSnapshot()
        if (current) {
            undoStack.value.push(current)
        }

        // 弹出并恢复下一个状态
        const snapshot = redoStack.value.pop()
        restoreSnapshot(snapshot)
        logger.info('UndoRedo', `重做 (undo: ${undoStack.value.length}, redo: ${redoStack.value.length})`)
    }

    /**
     * 清空历史
     */
    function clear() {
        undoStack.value = []
        redoStack.value = []
        logger.debug('UndoRedo', '历史栈已清空')
    }

    /**
     * 获取历史信息
     */
    function getHistoryInfo() {
        return {
            undoCount: undoStack.value.length,
            redoCount: redoStack.value.length,
            canUndo: canUndo.value,
            canRedo: canRedo.value
        }
    }

    return {
        undoStack,
        redoStack,
        canUndo,
        canRedo,
        commit,
        undo,
        redo,
        clear,
        getHistoryInfo
    }
}

/**
 * 创建按画布数据源集成 Pinia 的 Undo/Redo 实例
 *   mode='workflow'：快照当前主流程或函数图
 *   mode='topology'：快照项目唯一页面地图
 * 使用方式：
 *   const undoRedo = createCanvasUndoRedo('workflow')
 *   undoRedo.commit()  // 修改前调用
 *   // ... 修改数据 ...
 *   undoRedo.undo()    // 撤销
 */
export function createCanvasUndoRedo(mode = 'workflow') {
    const isTopology = mode === 'topology'

    function getState() {
        const store = useProjectStore()
        const graphId = isTopology ? 'page_map' : (store.currentTaskId || MAIN_GRAPH_ID)
        const graph = isTopology
            ? store.blueprint.page_map
            : getGraph(store.blueprint, graphId, 'workflow')
        return JSON.parse(JSON.stringify({ graphId, graph: graph || { nodes: [], edges: [], blocks: [] } }))
    }

    function setState(snapshot) {
        const store = useProjectStore()
        const restored = JSON.parse(JSON.stringify(snapshot?.graph || { nodes: [], edges: [], blocks: [] }))
        if (isTopology) {
            store.blueprint.page_map = restored
            store.saveTopologyDebounced()
        } else if (snapshot?.graphId === MAIN_GRAPH_ID) {
            store.blueprint.main_graph = restored
            store.saveWorkflowImmediately()
        } else {
            const fn = (store.blueprint.functions || []).find(item => item.function_id === snapshot?.graphId)
            if (!fn) return
            fn.graph = restored
            store.saveWorkflowImmediately()
        }
    }

    return useUndoRedo({ getState, setState })
}
