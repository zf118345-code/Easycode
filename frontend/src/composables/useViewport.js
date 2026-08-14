// frontend/src/composables/useViewport.js
// 画布视口状态与操作：平移 / 缩放 / 重置 / 适配节点
import { ref, computed } from 'vue'

/**
 * 画布视口 composable
 * 封装视口的平移、缩放状态及相应操作方法。
 * @returns {{
 *   viewport: import('vue').Ref<{x:number,y:number,zoom:number}>,
 *   isPanning: import('vue').Ref<boolean>,
 *   panStart: import('vue').Ref<{x:number,y:number}>,
 *   viewportStyle: import('vue').ComputedRef<{transform:string,transformOrigin:string}>,
 *   onCanvasWheel: (e:WheelEvent)=>void,
 *   startPan: (e:MouseEvent)=>void,
 *   onPanMove: (e:MouseEvent)=>void,
 *   stopPan: ()=>void,
 *   zoomIn: ()=>void,
 *   zoomOut: ()=>void,
 *   resetView: ()=>void,
 *   fitViewToNodes: (nodes:Array<Object>, containerEl:HTMLElement|null|undefined)=>void
 * }}
 */
export function useViewport() {
    // 视口状态：x/y 为画布偏移，zoom 为缩放比例
    const viewport = ref({ x: 0, y: 0, zoom: 1 })
    // 是否处于平移中
    const isPanning = ref(false)
    // 平移起点（记录鼠标按下时相对 viewport 的偏移）
    const panStart = ref({ x: 0, y: 0 })

    // 视口样式：通过 transform 实现平移与缩放，transformOrigin 固定 0 0
    const viewportStyle = computed(() => ({
        transform: `translate(${viewport.value.x}px, ${viewport.value.y}px) scale(${viewport.value.zoom})`,
        transformOrigin: '0 0'
    }))

    /**
     * 滚轮缩放：以鼠标位置为中心进行缩放
     * zoom 范围限制在 0.2 - 4（统一 workflow / topology 行为）
     */
    const onCanvasWheel = (e) => {
        e.preventDefault()
        const delta = e.deltaY > 0 ? 0.9 : 1.1
        const newZoom = Math.max(0.2, Math.min(4, viewport.value.zoom * delta))
        if (newZoom === viewport.value.zoom) return

        const rect = e.currentTarget.getBoundingClientRect()
        const mouseX = e.clientX - rect.left
        const mouseY = e.clientY - rect.top

        const worldX = (mouseX - viewport.value.x) / viewport.value.zoom
        const worldY = (mouseY - viewport.value.y) / viewport.value.zoom

        viewport.value.zoom = newZoom
        viewport.value.x = mouseX - worldX * newZoom
        viewport.value.y = mouseY - worldY * newZoom
    }

    /**
     * 开始平移：记录平移起点
     */
    const startPan = (e) => {
        isPanning.value = true
        panStart.value = {
            x: e.clientX - viewport.value.x,
            y: e.clientY - viewport.value.y
        }
    }

    /**
     * 平移中：根据鼠标位置更新 viewport 偏移
     */
    const onPanMove = (e) => {
        if (!isPanning.value) return
        viewport.value.x = e.clientX - panStart.value.x
        viewport.value.y = e.clientY - panStart.value.y
    }

    /**
     * 停止平移
     */
    const stopPan = () => {
        isPanning.value = false
    }

    /**
     * 放大视口（工具栏：×1.2，上限 4）
     */
    const zoomIn = () => {
        viewport.value.zoom = Math.min(4, viewport.value.zoom * 1.2)
    }

    /**
     * 缩小视口（工具栏：×0.8，下限 0.2）
     */
    const zoomOut = () => {
        viewport.value.zoom = Math.max(0.2, viewport.value.zoom * 0.8)
    }

    /**
     * 重置视口到默认状态
     */
    const resetView = () => {
        viewport.value = { x: 0, y: 0, zoom: 1 }
    }

    /**
     * 适配视口到给定节点集合：计算节点边界框并居中显示
     * @param {Array<Object>} nodes - 节点数组，需包含 position / w / h
     * @param {HTMLElement|null|undefined} containerEl - 画布容器元素
     */
    const fitViewToNodes = (nodes, containerEl) => {
        if (!nodes.length || !containerEl) return
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
        nodes.forEach(n => {
            const pos = n.position || { x: 0, y: 0 }
            const w = n.w || 160
            const h = n.h || 120
            minX = Math.min(minX, pos.x)
            minY = Math.min(minY, pos.y)
            maxX = Math.max(maxX, pos.x + w)
            maxY = Math.max(maxY, pos.y + h)
        })
        const centerX = (minX + maxX) / 2
        const centerY = (minY + maxY) / 2
        const containerW = containerEl.clientWidth
        const containerH = containerEl.clientHeight
        viewport.value.x = containerW / 2 - centerX * viewport.value.zoom
        viewport.value.y = containerH / 2 - centerY * viewport.value.zoom
    }

    return {
        viewport,
        isPanning,
        panStart,
        viewportStyle,
        onCanvasWheel,
        startPan,
        onPanMove,
        stopPan,
        zoomIn,
        zoomOut,
        resetView,
        fitViewToNodes
    }
}
