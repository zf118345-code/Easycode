// frontend/src/composables/useContextMenu.js
// 画布右键菜单状态管理与命中检测：封装 customContextMenu / spawnMenu 的显示、关闭与右键目标检测逻辑
import { reactive, ref } from 'vue'
import { getNextZIndex } from '@/utils/zIndexManager'

/**
 * 画布右键菜单 composable
 * 提供 customContextMenu（通用右键菜单）与 spawnMenu（衍生连线菜单）的状态管理，
 * 以及基于 DOM 命中检测的 detectAndShow 与节点级 showNodeContextMenu。
 */
export function useContextMenu() {
    const customContextMenu = reactive({
        visible: false,
        x: 0,
        y: 0,
        targetType: 'canvas',  // 'node' | 'group' | 'canvas_in_group' | 'canvas_public'
        targetId: null,
        targetName: '',
        clientX: 0,
        clientY: 0
    })

    const spawnMenu = ref({
        visible: false,
        x: 0,
        y: 0,
        sourceNodeId: null,
        portType: 'succ',
        clientX: 0,
        clientY: 0
    })

    const closeSpawnMenu = () => {
        spawnMenu.value.visible = false
    }

    const closeContextMenu = () => {
        customContextMenu.visible = false
    }

    const closeAllMenus = () => {
        closeSpawnMenu()
        closeContextMenu()
    }

    const showSpawnMenu = (x, y, sourceNodeId, portType, clientX, clientY) => {
        spawnMenu.value.visible = true
        spawnMenu.value.x = x
        spawnMenu.value.y = y
        spawnMenu.value.sourceNodeId = sourceNodeId
        spawnMenu.value.portType = portType
        spawnMenu.value.clientX = clientX
        spawnMenu.value.clientY = clientY
    }

    const getMenuZIndex = (e) => {
        return getNextZIndex()
    }

    const detectAndShow = (e, renderNodes, dynamicGroups, containerRef, viewport) => {
        e.preventDefault()
        customContextMenu.visible = false

        // 1. 检测节点
        const nodeCard = e.target.closest('.canvas-node-card')
        if (nodeCard) {
            const nodeId = nodeCard.getAttribute('data-node-id')
            const nodeObj = renderNodes.find(n => n.node_id === nodeId)
            if (nodeObj) {
                customContextMenu.visible = true
                customContextMenu.x = e.clientX
                customContextMenu.y = e.clientY
                customContextMenu.targetType = 'node'
                customContextMenu.targetId = nodeObj.node_id
                customContextMenu.targetName = nodeObj.node_name
                customContextMenu.clientX = e.clientX
                customContextMenu.clientY = e.clientY
                return
            }
        }

        // 2. 检测组
        const groupBox = e.target.closest('.canvas-group-box') || e.target.closest('.group-title-badge')
        if (groupBox) {
            const groupId = groupBox.getAttribute('data-group-id')
            const groupObj = dynamicGroups.find(g => g.groupId === groupId)
            if (groupObj) {
                customContextMenu.visible = true
                customContextMenu.x = e.clientX
                customContextMenu.y = e.clientY
                customContextMenu.targetType = 'group'
                customContextMenu.targetId = groupObj.taskId
                customContextMenu.targetName = groupObj.groupName
                customContextMenu.clientX = e.clientX
                customContextMenu.clientY = e.clientY
                return
            }
        }

        // 3. 检测画布空白区（组内 or 公共）
        if (!containerRef) return
        const rect = containerRef.getBoundingClientRect()
        const clientX = e.clientX - rect.left
        const clientY = e.clientY - rect.top
        const worldX = (clientX - viewport.x) / viewport.zoom
        const worldY = (clientY - viewport.y) / viewport.zoom

        let hitGroup = null
        for (const g of dynamicGroups) {
            const box = g.box
            if (worldX >= box.x && worldX <= box.x + box.w && worldY >= box.y && worldY <= box.y + box.h) {
                hitGroup = g
                break
            }
        }

        customContextMenu.visible = true
        customContextMenu.x = e.clientX
        customContextMenu.y = e.clientY
        customContextMenu.clientX = e.clientX
        customContextMenu.clientY = e.clientY

        if (hitGroup) {
            customContextMenu.targetType = 'canvas_in_group'
            customContextMenu.targetId = hitGroup.taskId
            customContextMenu.targetName = hitGroup.groupName
        } else {
            customContextMenu.targetType = 'canvas_public'
            customContextMenu.targetId = null
            customContextMenu.targetName = ''
        }
    }

    const showNodeContextMenu = (e, node, containerEl) => {
        customContextMenu.visible = true
        customContextMenu.targetType = 'node'
        customContextMenu.targetId = node.node_id
        customContextMenu.targetName = node.node_name
        customContextMenu.clientX = e.clientX
        customContextMenu.clientY = e.clientY
        const rect = containerEl?.getBoundingClientRect?.()
        customContextMenu.x = rect ? (e.clientX - rect.left) + 8 : e.offsetX
        customContextMenu.y = rect ? (e.clientY - rect.top) + 8 : e.offsetY
        closeSpawnMenu()
    }

    return {
        customContextMenu,
        spawnMenu,
        closeAllMenus,
        closeSpawnMenu,
        closeContextMenu,
        showSpawnMenu,
        detectAndShow,
        showNodeContextMenu,
        getMenuZIndex
    }
}
