<template>
    <div v-if="visible" class="screenshot-overlay" @keydown.stop="handleKeyDown" tabindex="0" ref="overlayRef">
        <div class="main-layout">
            <!-- 左侧：工作区 Canvas 画面 -->
            <div class="canvas-wrapper" ref="containerRef">
                <canvas ref="canvasRef"
                        @mousedown="onMouseDown"
                        @mousemove="onMouseMove"
                        @mouseup="onMouseUp"></canvas>
            </div>

            <!-- 右侧：固定微调与放大预览面板 -->
            <div class="sidebar-panel">
                <div class="panel-header">
                    <span v-if="mode === 'template'">📷 模板截图录入</span>
                    <span v-else-if="mode === 'point'">📍 坐标点提取</span>
                    <span v-else-if="mode === 'region'">📐 区域框选</span>
                </div>

                <!-- 选点模式预览 -->
                <div v-if="mode === 'point'" class="panel-section">
                    <div class="section-title">标定点局域放大</div>
                    <div class="preview-box">
                        <canvas ref="pointCanvasRef" width="160" height="160"></canvas>
                    </div>
                    <div class="data-group">
                        <div class="data-item">
                            <span class="label">工作区相对坐标:</span>
                            <span class="value">{{ point ? `${point.x}, ${point.y}` : '未点击选点' }}</span>
                        </div>
                    </div>
                    <div class="tips-box">
                        <p>💡 点击左侧画板标定坐标点</p>
                        <p>💡 **方向键 (↑↓←→)** 微调像素点位</p>
                        <p>💡 **回车 (Enter)** 确认并填入</p>
                    </div>
                </div>

                <!-- 选区 / 模板模式预览 -->
                <div v-else class="panel-section">
                    <div class="section-title">选区高精放大预览</div>
                    <div class="preview-box">
                        <canvas ref="regionCanvasRef" width="220" height="150"></canvas>
                    </div>
                    <div class="data-group">
                        <div class="data-item">
                            <span class="label">起点 (X, Y):</span>
                            <span class="value">{{ selection ? `${selection.x}, ${selection.y}` : '0, 0' }}</span>
                        </div>
                        <div class="data-item">
                            <span class="label">尺寸 (W × H):</span>
                            <span class="value highlight">{{ selection ? `${selection.w} × ${selection.h}` : '0 × 0' }}</span>
                        </div>
                    </div>
                    <div class="tips-box">
                        <p>💡 拖拽鼠标划定框选范围</p>
                        <p>💡 **方向键 (↑↓←→)** 平移位置</p>
                        <p>💡 **Shift + 方向键** 调整宽高</p>
                        <p>💡 **回车 (Enter)** 确认并进入保存</p>
                    </div>
                </div>

                <div class="panel-footer">
                    <el-button type="success" style="width: 100%; margin-bottom: 8px;" @click="confirmSelection">
                        确认选择 (Enter)
                    </el-button>
                    <el-button type="info" style="width: 100%; margin-left: 0;" @click="close">
                        取消 (Esc)
                    </el-button>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
    import { ref, reactive, computed, nextTick } from 'vue'
    import { ElMessage } from 'element-plus'
    import { useMainStore } from '@/stores'
    import axios from 'axios'

    export default {
        name: 'ScreenshotTool',
        emits: ['template-crop-selected', 'point-selected', 'region-selected'],
        setup(props, { emit }) {
            const store = useMainStore()

            const visible = ref(false)
            const mode = ref('template')
            const isPausedForDialog = ref(false)

            const canvasRef = ref(null)
            const containerRef = ref(null)
            const pointCanvasRef = ref(null)
            const regionCanvasRef = ref(null)
            const overlayRef = ref(null)

            let imgObj = null
            let isDrawing = false
            let startImgPoint = { x: 0, y: 0 }

            const drawScale = reactive({ scale: 1, offsetX: 0, offsetY: 0, imgW: 0, imgH: 0 })

            const selection = ref(null)
            const point = ref(null)

            const open = async (targetMode = 'template') => {
                mode.value = targetMode
                selection.value = null
                point.value = null
                isPausedForDialog.value = false

                try {
                    const res = await axios.get('/api/screenshot/full', {
                        params: { project_path: store.currentProjectPath }
                    })
                    if (!res.data.image) {
                        return ElMessage.error('获取工作区截图失败')
                    }

                    visible.value = true
                    await nextTick()

                    if (overlayRef.value) overlayRef.value.focus()

                    imgObj = new Image()
                    imgObj.src = 'data:image/png;base64,' + res.data.image
                    imgObj.onload = () => {
                        initAspectCanvas(res.data.width, res.data.height)
                    }
                } catch (err) {
                    ElMessage.error('调出截图工具失败')
                }
            }

            const setPauseState = (paused) => {
                isPausedForDialog.value = paused
            }

            const initAspectCanvas = (rawW, rawH) => {
                const canvas = canvasRef.value
                if (!canvas || !containerRef.value) return

                const screenW = containerRef.value.clientWidth
                const screenH = containerRef.value.clientHeight

                canvas.width = screenW
                canvas.height = screenH

                const scaleW = screenW / rawW
                const scaleH = screenH / rawH
                const scale = Math.min(scaleW, scaleH, 1)

                const drawW = rawW * scale
                const drawH = rawH * scale
                const offsetX = (screenW - drawW) / 2
                const offsetY = (screenH - drawH) / 2

                drawScale.scale = scale
                drawScale.offsetX = offsetX
                drawScale.offsetY = offsetY
                drawScale.imgW = rawW
                drawScale.imgH = rawH

                redrawCanvas()
            }

            const screenToImgPos = (clientX, clientY) => {
                const rect = containerRef.value.getBoundingClientRect()
                const xInCanvas = clientX - rect.left
                const yInCanvas = clientY - rect.top

                const ix = Math.round((xInCanvas - drawScale.offsetX) / drawScale.scale)
                const iy = Math.round((yInCanvas - drawScale.offsetY) / drawScale.scale)
                const clampedX = Math.max(0, Math.min(drawScale.imgW, ix))
                const clampedY = Math.max(0, Math.min(drawScale.imgH, iy))
                return { x: clampedX, y: clampedY }
            }

            const imgToCanvasPos = (imgX, imgY) => {
                const cx = imgX * drawScale.scale + drawScale.offsetX
                const cy = imgY * drawScale.scale + drawScale.offsetY
                return { x: cx, y: cy }
            }

            const redrawCanvas = () => {
                const canvas = canvasRef.value
                if (!canvas || !imgObj) return
                const ctx = canvas.getContext('2d')

                ctx.clearRect(0, 0, canvas.width, canvas.height)
                ctx.fillStyle = 'rgba(15, 15, 25, 0.95)'
                ctx.fillRect(0, 0, canvas.width, canvas.height)

                const { offsetX, offsetY, imgW, imgH, scale } = drawScale
                const drawW = imgW * scale
                const drawH = imgH * scale

                ctx.drawImage(imgObj, offsetX, offsetY, drawW, drawH)

                ctx.strokeStyle = '#409eff'
                ctx.lineWidth = 1.5
                ctx.strokeRect(offsetX, offsetY, drawW, drawH)

                if (selection.value && (mode.value === 'template' || mode.value === 'region')) {
                    const { x, y, w, h } = selection.value
                    const p1 = imgToCanvasPos(x, y)
                    const p2 = imgToCanvasPos(x + w, y + h)
                    const cw = p2.x - p1.x
                    const ch = p2.y - p1.y

                    if (w > 0 && h > 0) {
                        ctx.drawImage(imgObj, x, y, w, h, p1.x, p1.y, cw, ch)
                        ctx.strokeStyle = '#67C23A'
                        ctx.lineWidth = 2
                        ctx.strokeRect(p1.x, p1.y, cw, ch)
                    }
                }

                if (point.value && mode.value === 'point') {
                    const cp = imgToCanvasPos(point.value.x, point.value.y)
                    ctx.beginPath()
                    ctx.arc(cp.x, cp.y, 6, 0, Math.PI * 2)
                    ctx.fillStyle = '#FF4D4F'
                    ctx.fill()
                    ctx.strokeStyle = '#FFFFFF'
                    ctx.lineWidth = 2
                    ctx.stroke()

                    ctx.beginPath()
                    ctx.moveTo(cp.x - 12, cp.y); ctx.lineTo(cp.x + 12, cp.y)
                    ctx.moveTo(cp.x, cp.y - 12); ctx.lineTo(cp.x, cp.y + 12)
                    ctx.strokeStyle = '#FF4D4F'
                    ctx.lineWidth = 1.5
                    ctx.stroke()
                }

                updateSidebarPreviews()
            }

            const updateSidebarPreviews = () => {
                if (mode.value === 'point' && point.value) {
                    nextTick(() => {
                        const pCanvas = pointCanvasRef.value
                        if (!pCanvas || !imgObj) return
                        const pCtx = pCanvas.getContext('2d')
                        pCtx.clearRect(0, 0, 160, 160)
                        pCtx.drawImage(imgObj, point.value.x - 20, point.value.y - 20, 40, 40, 0, 0, 160, 160)
                        pCtx.strokeStyle = '#FF4D4F'
                        pCtx.lineWidth = 1
                        pCtx.beginPath()
                        pCtx.moveTo(80, 0); pCtx.lineTo(80, 160)
                        pCtx.moveTo(0, 80); pCtx.lineTo(160, 80)
                        pCtx.stroke()
                    })
                }

                if ((mode.value === 'region' || mode.value === 'template') && selection.value) {
                    const { x, y, w, h } = selection.value
                    if (w <= 0 || h <= 0) return
                    nextTick(() => {
                        const rCanvas = regionCanvasRef.value
                        if (!rCanvas || !imgObj) return
                        const rCtx = rCanvas.getContext('2d')
                        rCtx.clearRect(0, 0, rCanvas.width, rCanvas.height)
                        rCtx.fillStyle = '#0f0f19'
                        rCtx.fillRect(0, 0, rCanvas.width, rCanvas.height)

                        const pScale = Math.min(220 / w, 150 / h)
                        const pw = w * pScale
                        const ph = h * pScale
                        const px = (220 - pw) / 2
                        const py = (150 - ph) / 2

                        rCtx.drawImage(imgObj, x, y, w, h, px, py, pw, ph)
                        rCtx.strokeStyle = '#67C23A'
                        rCtx.lineWidth = 1.5
                        rCtx.strokeRect(px, py, pw, ph)
                    })
                }
            }

            const onMouseDown = (e) => {
                if (isPausedForDialog.value) return
                isDrawing = true
                const imgPos = screenToImgPos(e.clientX, e.clientY)
                startImgPoint = imgPos

                if (mode.value === 'point') {
                    point.value = { ...imgPos }
                    redrawCanvas()
                } else {
                    selection.value = { x: imgPos.x, y: imgPos.y, w: 0, h: 0 }
                }
            }

            const onMouseMove = (e) => {
                if (isPausedForDialog.value || !isDrawing) return
                const imgPos = screenToImgPos(e.clientX, e.clientY)

                if (mode.value === 'point') {
                    point.value = { ...imgPos }
                } else {
                    const x = Math.min(startImgPoint.x, imgPos.x)
                    const y = Math.min(startImgPoint.y, imgPos.y)
                    const w = Math.abs(imgPos.x - startImgPoint.x)
                    const h = Math.abs(imgPos.y - startImgPoint.y)
                    selection.value = { x, y, w, h }
                }
                redrawCanvas()
            }

            const onMouseUp = () => { isDrawing = false }

            const handleKeyDown = (e) => {
                if (isPausedForDialog.value) return

                if (e.key === 'Escape') return close()
                if (e.key === 'Enter') return confirmSelection()

                if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
                    e.preventDefault()
                    const dx = e.key === 'ArrowLeft' ? -1 : e.key === 'ArrowRight' ? 1 : 0
                    const dy = e.key === 'ArrowUp' ? -1 : e.key === 'ArrowDown' ? 1 : 0

                    if (mode.value === 'point' && point.value) {
                        point.value.x = Math.max(0, Math.min(drawScale.imgW, point.value.x + dx))
                        point.value.y = Math.max(0, Math.min(drawScale.imgH, point.value.y + dy))
                        redrawCanvas()
                    } else if (selection.value) {
                        if (e.shiftKey) {
                            selection.value.w = Math.max(1, selection.value.w + dx)
                            selection.value.h = Math.max(1, selection.value.h + dy)
                        } else {
                            selection.value.x = Math.max(0, Math.min(drawScale.imgW - selection.value.w, selection.value.x + dx))
                            selection.value.y = Math.max(0, Math.min(drawScale.imgH - selection.value.h, selection.value.y + dy))
                        }
                        redrawCanvas()
                    }
                }
            }

            const confirmSelection = () => {
                if (mode.value === 'point') {
                    if (!point.value) return ElMessage.warning('请先点击工作区选点')
                    emit('point-selected', [point.value.x, point.value.y])
                    close()
                    return
                }

                if (mode.value === 'region') {
                    if (!selection.value || selection.value.w === 0) return ElMessage.warning('请先划定框选区域')
                    emit('region-selected', [selection.value.x, selection.value.y, selection.value.w, selection.value.h])
                    close()
                    return
                }

                if (mode.value === 'template') {
                    if (!selection.value || selection.value.w === 0) return ElMessage.warning('请先划定截取区域')
                    emit('template-crop-selected', [selection.value.x, selection.value.y, selection.value.w, selection.value.h])
                }
            }

            const close = () => { visible.value = false; isPausedForDialog.value = false }

            return {
                visible,
                mode,
                canvasRef,
                containerRef,
                pointCanvasRef,
                regionCanvasRef,
                overlayRef,
                selection,
                point,
                open,
                setPauseState,
                onMouseDown,
                onMouseMove,
                onMouseUp,
                handleKeyDown,
                confirmSelection,
                close
            }
        }
    }
</script>

<style scoped>
    /* ⭐ 专业平滑层级：截图工具蒙层统一设为 z-index: 1000 */
    .screenshot-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 1000;
        outline: none;
        background: #0f0f19;
    }

    .main-layout {
        display: flex;
        width: 100vw;
        height: 100vh;
    }

    .canvas-wrapper {
        flex: 1;
        height: 100%;
        position: relative;
        overflow: hidden;
        cursor: crosshair;
    }

    .sidebar-panel {
        width: 280px;
        height: 100%;
        background: #181824;
        border-left: 1px solid #2d2d3f;
        display: flex;
        flex-direction: column;
        padding: 16px;
        box-shadow: -4px 0 16px rgba(0, 0, 0, 0.4);
    }

    .panel-header {
        font-size: 16px;
        font-weight: 600;
        color: #409eff;
        padding-bottom: 12px;
        border-bottom: 1px solid #2d2d3f;
        margin-bottom: 16px;
    }

    .panel-section {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .section-title {
        font-size: 13px;
        color: #a2a7c7;
        font-weight: 500;
    }

    .preview-box {
        background: #09090d;
        border: 1px dashed #3d3d5a;
        border-radius: 6px;
        padding: 8px;
        display: flex;
        justify-content: center;
        align-items: center;
    }

    .data-group {
        display: flex;
        flex-direction: column;
        gap: 6px;
        background: #202030;
        padding: 10px;
        border-radius: 6px;
    }

    .data-item {
        display: flex;
        justify-content: space-between;
        font-size: 12px;
        color: #cfd3e6;
    }

    .highlight {
        color: #67c23a;
        font-weight: 600;
    }

    .tips-box {
        background: rgba(64, 158, 255, 0.08);
        border-left: 3px solid #409eff;
        padding: 8px 10px;
        border-radius: 0 4px 4px 0;
        font-size: 11px;
        color: #a2a7c7;
        line-height: 1.6;
    }

    .panel-footer {
        padding-top: 12px;
        border-top: 1px solid #2d2d3f;
    }
</style>