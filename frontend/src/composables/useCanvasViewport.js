import { ref, computed } from 'vue'

export function useCanvasViewport(containerRef) {
    const viewport = ref({ x: 0, y: 0, zoom: 1 })
    const isPanning = ref(false)
    const panStart = ref({ x: 0, y: 0 })

    const viewportStyle = computed(() => ({
        transform: `translate(${viewport.value.x}px, ${viewport.value.y}px) scale(${viewport.value.zoom})`,
        transformOrigin: '0 0'
    }))

    const handleCanvasWheel = (e, drawMinimap) => {
        e.preventDefault()
        if (!containerRef.value) return

        const rect = containerRef.value.getBoundingClientRect()
        const mouseX = e.clientX - rect.left
        const mouseY = e.clientY - rect.top

        const oldZoom = viewport.value.zoom
        const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9
        const newZoom = Math.min(Math.max(oldZoom * zoomFactor, 0.2), 4)

        if (newZoom === oldZoom) return

        const worldX = (mouseX - viewport.value.x) / oldZoom
        const worldY = (mouseY - viewport.value.y) / oldZoom

        viewport.value.zoom = newZoom
        viewport.value.x = mouseX - worldX * newZoom
        viewport.value.y = mouseY - worldY * newZoom

        if (typeof drawMinimap === 'function') {
            drawMinimap()
        }
    }

    return {
        viewport,
        isPanning,
        panStart,
        viewportStyle,
        handleCanvasWheel
    }
}