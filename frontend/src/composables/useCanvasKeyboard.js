// frontend/src/composables/useCanvasKeyboard.js
// 画布基础快捷键：Ctrl+S 保存 / Delete 删除选中节点 / Ctrl+A 全选
import { onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useProjectStore } from '@/stores/projectStore'
import { useUiStore } from '@/stores/uiStore'
import { handleError } from '@/utils/errorHandler'
import { logger } from '@/utils/logger'

/**
 * 画布键盘快捷键 composable
 * @param {Object} options - { onSave, onDelete, onSelectAll }
 *   onSave: 自定义保存回调（可选，默认调用 projectStore.saveBlueprintImmediately）
 *   onDelete: 自定义删除回调（可选，默认删除 uiStore.selectedNodeIds 对应的节点）
 *   onSelectAll: 自定义全选回调（可选，默认选中当前任务所有节点）
 */
export function useCanvasKeyboard(options = {}) {
    let isInputFocused = false

    function checkInputFocus() {
        const el = document.activeElement
        if (!el) return false
        const tag = el.tagName?.toLowerCase()
        return tag === 'input' || tag === 'textarea' || el.isContentEditable || el.classList.contains('el-input__inner')
    }

    async function handleSave(e) {
        e.preventDefault()
        e.stopPropagation()
        logger.info('Keyboard', 'Ctrl+S: 保存蓝图')
        try {
            if (options.onSave) {
                options.onSave()
            } else {
                const projectStore = useProjectStore()
                await projectStore.saveBlueprintImmediately()
                ElMessage.success('蓝图已保存')
            }
        } catch (err) {
            handleError(err, { tag: 'Keyboard', fallback: '保存失败' })
        }
    }

    function handleDelete(e) {
        if (checkInputFocus()) return
        e.preventDefault()
        e.stopPropagation()
        logger.info('Keyboard', 'Delete: 删除选中节点')

        if (options.onDelete) {
            options.onDelete()
            return
        }

        const uiStore = useUiStore()
        const projectStore = useProjectStore()
        const idsToDelete = uiStore.selectedNodeIds?.length > 0
            ? [...uiStore.selectedNodeIds]
            : (uiStore.selectedNodeId ? [uiStore.selectedNodeId] : [])

        if (idsToDelete.length === 0) {
            ElMessage.warning('请先选中要删除的节点')
            return
        }

        // 从当前任务的节点列表中移除
        const task = projectStore.currentTask
        if (task && task.nodes) {
            task.nodes = task.nodes.filter(n => !idsToDelete.includes(n.node_id))
        }

        // 同时移除关联的边
        if (projectStore.blueprint.edges) {
            projectStore.blueprint.edges = projectStore.blueprint.edges.filter(
                e => !idsToDelete.includes(e.source_node) && !idsToDelete.includes(e.target_node)
            )
        }

        uiStore.clearSelection()
        projectStore.saveBlueprintDebounced()
        ElMessage.success(`已删除 ${idsToDelete.length} 个节点`)
    }

    function handleSelectAll(e) {
        if (checkInputFocus()) return
        e.preventDefault()
        e.stopPropagation()
        logger.info('Keyboard', 'Ctrl+A: 全选节点')

        if (options.onSelectAll) {
            options.onSelectAll()
            return
        }

        const projectStore = useProjectStore()
        const uiStore = useUiStore()
        const nodes = projectStore.nodes
        if (nodes && nodes.length > 0) {
            uiStore.selectNodes(nodes.map(n => n.node_id))
        }
    }

    function handleKeydown(e) {
        const ctrl = e.ctrlKey || e.metaKey

        // Ctrl+S
        if (ctrl && e.key === 's') {
            handleSave(e)
            return
        }

        // Ctrl+A
        if (ctrl && e.key === 'a') {
            handleSelectAll(e)
            return
        }

        // Delete / Backspace
        if (e.key === 'Delete' || e.key === 'Backspace') {
            handleDelete(e)
            return
        }
    }

    onMounted(() => {
        window.addEventListener('keydown', handleKeydown)
    })

    onUnmounted(() => {
        window.removeEventListener('keydown', handleKeydown)
    })
}
