import { ref } from 'vue'

export function useConnection() {
    const drawingConnection = ref({
        active: false,
        sourceNodeId: null,
        portType: 'success',
        sourcePortId: 'success',
        sourceX: 0,
        sourceY: 0,
        currentX: 0,
        currentY: 0,
        previewMarkerUrl: 'url(#arrow-preview)'
    })

    const startConnection = (e, nodeId, portType, sourceX = 0, sourceY = 0, sourcePortId = '') => {
        drawingConnection.value = {
            active: true,
            sourceNodeId: nodeId,
            portType: portType,
            sourcePortId: sourcePortId || portType,
            sourceX: sourceX,
            sourceY: sourceY,
            currentX: sourceX,
            currentY: sourceY,
            previewMarkerUrl: 'url(#arrow-preview)'
        }
        e.stopPropagation()
    }

    const onConnectionMove = (e, containerEl, viewport, GRID_SIZE) => {
        if (!drawingConnection.value.active || !containerEl) return
        const rect = containerEl.getBoundingClientRect()
        const clientX = e.clientX - rect.left
        const clientY = e.clientY - rect.top
        const rawX = (clientX - viewport.value.x) / viewport.value.zoom
        const rawY = (clientY - viewport.value.y) / viewport.value.zoom
        drawingConnection.value.currentX = Math.round(rawX / GRID_SIZE) * GRID_SIZE
        drawingConnection.value.currentY = Math.round(rawY / GRID_SIZE) * GRID_SIZE
    }

    const endConnection = () => {
        const wasDrawing = drawingConnection.value.active
        const sourceId = drawingConnection.value.sourceNodeId
        const portType = drawingConnection.value.portType
        const sourcePortId = drawingConnection.value.sourcePortId
        drawingConnection.value.active = false
        return { wasDrawing, sourceId, portType, sourcePortId }
    }

    const cancelConnection = () => {
        drawingConnection.value.active = false
    }

    return {
        drawingConnection,
        startConnection,
        onConnectionMove,
        endConnection,
        cancelConnection
    }
}
