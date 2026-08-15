<!-- frontend/src/components/canvas/CanvasEdgeLayer.vue -->
<!--
    统一世界图层（grid + edges），WorkflowCanvas 与 TopologyCanvas 共用。
    坐标系约定：
      - SVG 不设 viewBox：user 单位 = CSS px = 世界坐标，与节点卡片 1:1；
      - SVG 尺寸按可见世界区域动态计算（viewport + 容器尺寸 + 余量），随视口变化重算，
        不再使用巨型固定画布（避免超大合成层）；
      - 网格由本 SVG 矢量绘制（世界坐标 20px 间距，每 5 格一条主线），任何缩放倍率下
        都精确清晰——画布背景不再绘制网格，网格/连线/节点共用同一套坐标与同一张网格。
    Renders:
      1. vector grid (minor + major lines)
      2. clickable hit area (wide transparent path under each edge)
      3. the visible edge path (color-coded by success/failure)
      4. flow animation overlay
      5. edge labels
      6. real-time drag preview line
-->
<template>
    <svg
        class="canvas-edges-layer"
        :viewBox="viewBoxValue"
        preserveAspectRatio="none"
        :style="svgStyle">
        <defs>
            <!-- success markers (green) -->
            <marker
                id="arrow-succ-right" viewBox="0 0 10 10" refX="9" refY="5"
                markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#4ed19c" />
            </marker>
            <marker
                id="arrow-succ-left" viewBox="0 0 10 10" refX="1" refY="5"
                markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 10 0 L 0 5 L 10 10 z" fill="#4ed19c" />
            </marker>
            <marker
                id="arrow-succ-up" viewBox="0 0 10 10" refX="5" refY="1"
                markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 10 L 5 0 L 10 10 z" fill="#4ed19c" />
            </marker>
            <marker
                id="arrow-succ-down" viewBox="0 0 10 10" refX="5" refY="9"
                markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 0 L 5 10 L 10 0 z" fill="#4ed19c" />
            </marker>

            <!-- failure markers (red) -->
            <marker
                id="arrow-fail-right" viewBox="0 0 10 10" refX="9" refY="5"
                markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#f56c6c" />
            </marker>
            <marker
                id="arrow-fail-left" viewBox="0 0 10 10" refX="1" refY="5"
                markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 10 0 L 0 5 L 10 10 z" fill="#f56c6c" />
            </marker>
            <marker
                id="arrow-fail-up" viewBox="0 0 10 10" refX="5" refY="1"
                markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 10 L 5 0 L 10 10 z" fill="#f56c6c" />
            </marker>
            <marker
                id="arrow-fail-down" viewBox="0 0 10 10" refX="5" refY="9"
                markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 0 L 5 10 L 10 0 z" fill="#f56c6c" />
            </marker>

            <!-- default gray marker -->
            <marker
                id="arrow-default" viewBox="0 0 10 10" refX="9" refY="5"
                markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#8b93a7" />
            </marker>
        </defs>

        <!-- Vector grid（世界坐标，与连线/节点同源） -->
        <path v-if="gridPathMinor" :d="gridPathMinor" class="canvas-grid-line" />
        <path v-if="gridPathMajor" :d="gridPathMajor" class="canvas-grid-line canvas-grid-line-major" />

        <!-- Edges group: each edge has 3 layers (hit / visible / flow) plus label -->
        <g v-for="edge in edges" :key="edge.id" class="edge-group">
            <!-- Wide transparent hit target for easier click -->
            <path
                v-if="edge.path"
                :d="edge.path"
                :class="['edge-hit-area', { 'is-selected': edge.selected }]"
                @click.stop="$emit('edge-click', edge)" />

            <!-- Visible edge -->
            <path
                v-if="edge.path"
                :d="edge.path"
                :class="['edge-path', { 'is-selected': edge.selected, 'is-failure': edge.isFail }]"
                :marker-end="edge.markerUrl"
                @click.stop="$emit('edge-click', edge)" />

            <!-- Flow animation overlay -->
            <path
                v-if="edge.path && !edge.selected"
                :d="edge.path"
                :class="['edge-flow-path', { 'is-failure': edge.isFail }]" />

            <!-- Edge label -->
            <text
                v-if="edge.label"
                :x="edge.labelX"
                :y="edge.labelY"
                class="edge-label"
                text-anchor="middle">{{ edge.label }}</text>
        </g>

        <!-- Live drag preview：无箭头，终点用连线颜色的发光球（松手后正常边恢复箭头） -->
        <g
            v-if="drawingConnection?.active"
            class="preview-drawing"
            :class="{ 'is-failure': isPreviewFailure }">
            <path :d="previewPathD" class="edge-path preview-path" />
            <circle
                :cx="drawingConnection?.currentX"
                :cy="drawingConnection?.currentY"
                r="6"
                class="preview-drag-ball" />
        </g>
    </svg>
</template>

<script setup>
    import { computed } from 'vue'
    import { getSimpleOrthoPath } from '@/utils/canvasRouter'
    import { GRID_SIZE } from '@/utils/canvasShared'

    const props = defineProps({
        edges:           { type: Array,  default: () => [] },
        drawingConnection:{ type: Object, default: null },
        viewport:        { type: Object, default: () => ({ x: 0, y: 0, zoom: 1 }) },
        containerSize:   { type: Object, default: () => ({ width: 1200, height: 800 }) }
    })

    defineEmits(['edge-click'])

    const GRID_MAJOR_EVERY = 5       // 每 5 格一条主线

    // 可见世界区域（世界坐标）
    const worldBox = computed(() => {
        const zoom = props.viewport.zoom || 1
        return {
            left: -props.viewport.x / zoom,
            top: -props.viewport.y / zoom,
            width: (props.containerSize.width || 0) / zoom,
            height: (props.containerSize.height || 0) / zoom
        }
    })

    // 动态 viewBox = 精确可见世界窗口（无余量）：user 单位 = 世界坐标，
    // 经 preserveAspectRatio="none" 严格 1:1 映射到容器，与节点完全同源
    const viewBoxValue = computed(() => {
        const b = worldBox.value
        return `${b.left} ${b.top} ${b.width} ${b.height}`
    })

    // SVG 元素盒 = 精确可见世界窗口（世界坐标即 CSS px）：
    //   left/top = 窗口原点，width/height = 窗口尺寸，可与负坐标窗口对齐。
    // 配合同参数的 viewBox → viewBox 内部缩放系数恒为 1，
    // 唯一的缩放由视口 transform 施加一次，与节点卡片完全同一套坐标系。
    const svgStyle = computed(() => {
        const b = worldBox.value
        return {
            position: 'absolute',
            left: `${b.left}px`,
            top: `${b.top}px`,
            width: `${b.width}px`,
            height: `${b.height}px`,
            overflow: 'visible'
        }
    })

    // 网格线路径（世界坐标 20px 间距，主线每 5 格；向窗口外多画一格，由 overflow visible 补齐）
    const gridPathMinor = computed(() => buildGridPath(worldBox.value, false))
    const gridPathMajor = computed(() => buildGridPath(worldBox.value, true))

    function buildGridPath(box, majorOnly) {
        const step = majorOnly ? GRID_SIZE * GRID_MAJOR_EVERY : GRID_SIZE
        const left = Math.floor(box.left / step) * step - step
        const top = Math.floor(box.top / step) * step - step
        const right = Math.ceil((box.left + box.width) / step) * step + step
        const bottom = Math.ceil((box.top + box.height) / step) * step + step
        if (!box.width || !box.height) return ''
        const segs = []
        for (let x = left; x <= right; x += step) {
            segs.push(`M ${x} ${top} V ${bottom}`)
        }
        for (let y = top; y <= bottom; y += step) {
            segs.push(`M ${left} ${y} H ${right}`)
        }
        return segs.join(' ')
    }

    const previewPathD = computed(() => {
        if (!props.drawingConnection?.active) return ''
        const start = {
            x: props.drawingConnection.sourceX ?? props.drawingConnection.currentX,
            y: props.drawingConnection.sourceY ?? props.drawingConnection.currentY
        }
        const end = {
            x: props.drawingConnection.currentX,
            y: props.drawingConnection.currentY
        }
        try {
            return getSimpleOrthoPath(start, end, props.drawingConnection.portType)
        } catch (e) {
            return `M ${start.x} ${start.y} L ${end.x} ${end.y}`
        }
    })

    // 预览线颜色：failure 红、其余成功绿（发光球同色）
    const isPreviewFailure = computed(() => {
        const t = props.drawingConnection?.portType
        return t === 'fail' || t === 'failure'
    })
</script>
