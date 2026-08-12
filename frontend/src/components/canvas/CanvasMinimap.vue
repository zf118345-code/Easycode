<!-- frontend/src/components/canvas/CanvasMinimap.vue -->
<template>
    <div v-show="store.minimapExpanded" class="minimap-container">
        <div class="minimap-header" @click="store.toggleMinimap">
            <span>È«¾°µ¼º½</span>
            <span class="collapse-icon">¨‹</span>
        </div>
        <div class="minimap-body">
            <canvas ref="canvasRef"
                    width="200"
                    height="150"
                    @click="handleMinimapClick" />
        </div>
    </div>
</template>

<script setup>
    import { ref, watch, onMounted } from 'vue'
    import { useMainStore } from '@/stores'

    const props = defineProps({
        renderNodes: { type: Array, default: () => [] },
        dynamicGroups: { type: Array, default: () => [] },
        viewport: { type: Object, required: true }
    })

    const emit = defineEmits(['navigate'])

    const store = useMainStore()
    const canvasRef = ref(null)

    const drawMinimap = () => {
        const canvas = canvasRef.value
        if (!canvas) return
        const ctx = canvas.getContext('2d')

        ctx.clearRect(0, 0, canvas.width, canvas.height)
        ctx.fillStyle = '#181926'
        ctx.fillRect(0, 0, canvas.width, canvas.height)

        const nodes = props.renderNodes
        const groups = props.dynamicGroups
        if (!nodes.length && !groups.length) return

        let minX = -1000, minY = -1000, maxX = 3000, maxY = 3000
        nodes.forEach(n => {
            minX = Math.min(minX, n.position.x - 200)
            minY = Math.min(minY, n.position.y - 200)
            maxX = Math.max(maxX, n.position.x + n.w + 200)
            maxY = Math.max(maxY, n.position.y + n.h + 200)
        })

        const worldW = maxX - minX
        const worldH = maxY - minY
        const mapScale = Math.min(canvas.width / worldW, canvas.height / worldH)

        const toMapCoord = (wx, wy) => ({
            x: (wx - minX) * mapScale + (canvas.width - worldW * mapScale) / 2,
            y: (wy - minY) * mapScale + (canvas.height - worldH * mapScale) / 2
        })

        ctx.strokeStyle = '#4ed19c33'
        ctx.lineWidth = 1
        groups.forEach(g => {
            const p = toMapCoord(g.box.x, g.box.y)
            ctx.strokeRect(p.x, p.y, g.box.w * mapScale, g.box.h * mapScale)
        })

        nodes.forEach(n => {
            const p = toMapCoord(n.position.x, n.position.y)
            ctx.fillStyle = n.selected ? '#409EFF' : '#4ed19c'
            ctx.fillRect(p.x, p.y, Math.max(4, n.w * mapScale), Math.max(3, n.h * mapScale))
        })

        const containerW = window.innerWidth
        const containerH = window.innerHeight
        const viewLeft = -props.viewport.x / props.viewport.zoom
        const viewTop = -props.viewport.y / props.viewport.zoom
        const viewW = containerW / props.viewport.zoom
        const viewH = containerH / props.viewport.zoom

        const vpCoord = toMapCoord(viewLeft, viewTop)
        ctx.strokeStyle = '#409EFF'
        ctx.lineWidth = 1.5
        ctx.strokeRect(vpCoord.x, vpCoord.y, viewW * mapScale, viewH * mapScale)
        ctx.fillStyle = 'rgba(64, 158, 255, 0.1)'
        ctx.fillRect(vpCoord.x, vpCoord.y, viewW * mapScale, viewH * mapScale)
    }

    const handleMinimapClick = (e) => {
        const canvas = canvasRef.value
        if (!canvas) return
        const rect = canvas.getBoundingClientRect()
        const clickX = e.clientX - rect.left
        const clickY = e.clientY - rect.top

        const nodes = props.renderNodes
        let minX = -1000, minY = -1000, maxX = 3000, maxY = 3000
        nodes.forEach(n => {
            minX = Math.min(minX, n.position.x - 200)
            minY = Math.min(minY, n.position.y - 200)
            maxX = Math.max(maxX, n.position.x + n.w + 200)
            maxY = Math.max(maxY, n.position.y + n.h + 200)
        })

        const worldW = maxX - minX
        const worldH = maxY - minY
        const mapScale = Math.min(canvas.width / worldW, canvas.height / worldH)

        const targetWorldX = (clickX - (canvas.width - worldW * mapScale) / 2) / mapScale + minX
        const targetWorldY = (clickY - (canvas.height - worldH * mapScale) / 2) / mapScale + minY

        emit('navigate', { targetWorldX, targetWorldY })
    }

    watch([() => props.renderNodes, () => props.viewport], () => {
        drawMinimap()
    }, { deep: true })

    onMounted(() => {
        drawMinimap()
    })
</script>

<style scoped>
    .minimap-container {
        position: absolute;
        right: 20px;
        bottom: 20px;
        width: 200px;
        background: rgba(38, 40, 61, 0.9);
        border: 1px solid var(--el-border-color-light);
        border-radius: var(--app-radius-md, 8px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        z-index: 998;
        overflow: hidden;
        user-select: none;
        transition: height 0.2s;
    }

    .minimap-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 10px;
        background: rgba(25, 26, 38, 0.95);
        font-size: 12px;
        font-weight: bold;
        color: var(--el-color-primary);
        cursor: pointer;
        border-bottom: 1px solid var(--el-border-color-light);
    }

        .minimap-header:hover {
            background: var(--el-fill-color-light);
        }

    .collapse-icon {
        font-size: 10px;
        color: var(--el-text-color-secondary);
    }

    .minimap-body {
        width: 200px;
        height: 150px;
        background: #181926;
        cursor: crosshair;
        display: flex;
        justify-content: center;
        align-items: center;
    }

        .minimap-body canvas {
            display: block;
        }
</style>