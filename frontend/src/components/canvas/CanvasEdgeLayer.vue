<!-- frontend/src/components/canvas/CanvasEdgeLayer.vue -->
<template>
    <svg class="canvas-edges-layer">
        <defs>
            <pattern id="grid-pattern" width="20" height="20" patternUnits="userSpaceOnUse">
                <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255, 255, 255, 0.08)" stroke-width="1" />
            </pattern>

            <marker id="arrow-succ-down" viewBox="0 0 10 10" refX="5" refY="8" markerWidth="6" markerHeight="6" orient="0">
                <path d="M 2 2 L 8 2 L 5 9 z" fill="#4ed19c" />
            </marker>
            <marker id="arrow-succ-up" viewBox="0 0 10 10" refX="5" refY="2" markerWidth="6" markerHeight="6" orient="0">
                <path d="M 2 8 L 8 8 L 5 1 z" fill="#4ed19c" />
            </marker>
            <marker id="arrow-succ-right" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="0">
                <path d="M 2 2 L 2 8 L 9 5 z" fill="#4ed19c" />
            </marker>
            <marker id="arrow-succ-left" viewBox="0 0 10 10" refX="2" refY="5" markerWidth="6" markerHeight="6" orient="0">
                <path d="M 8 2 L 8 8 L 1 5 z" fill="#4ed19c" />
            </marker>

            <marker id="arrow-fail-down" viewBox="0 0 10 10" refX="5" refY="8" markerWidth="6" markerHeight="6" orient="0">
                <path d="M 2 2 L 8 2 L 5 9 z" fill="#f56c6c" />
            </marker>
            <marker id="arrow-fail-up" viewBox="0 0 10 10" refX="5" refY="2" markerWidth="6" markerHeight="6" orient="0">
                <path d="M 2 8 L 8 8 L 5 1 z" fill="#f56c6c" />
            </marker>
            <marker id="arrow-fail-right" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="0">
                <path d="M 2 2 L 2 8 L 9 5 z" fill="#f56c6c" />
            </marker>
            <marker id="arrow-fail-left" viewBox="0 0 10 10" refX="2" refY="5" markerWidth="6" markerHeight="6" orient="0">
                <path d="M 8 2 L 8 8 L 1 5 z" fill="#f56c6c" />
            </marker>

            <marker id="arrow-preview" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 2 L 10 5 L 0 8 z" fill="#4ed19c" />
            </marker>
        </defs>

        <rect x="-5000" y="-5000" width="15000" height="15000" fill="url(#grid-pattern)" pointer-events="none" />

        <!-- 连线层 -->
        <g v-for="edge in edges" :key="edge.id">
            <path
                :d="edge.path"
                :class="['edge-path', { 'is-selected': edge.selected, 'is-danger': edge.isFail }]"
                :marker-end="edge.markerUrl"
                @click.stop="$emit('edge-click', edge)" />
            <path
                :d="edge.path"
                :class="['edge-flow-path', { 'is-danger': edge.isFail }]"
                pointer-events="none" />
        </g>

        <!-- 实时拉线预览 -->
        <path v-if="drawingConnection?.active" :d="previewPathD" class="edge-path preview-path" :marker-end="drawingConnection?.previewMarkerUrl" />
    </svg>
</template>

<script setup>
    import { computed } from 'vue'

    const props = defineProps({
        edges: { type: Array, default: () => [] },
        drawingConnection: { type: Object, default: null }
    })

    defineEmits(['edge-click'])

    // 拉线预览路径（简化版正交路径）
    const previewPathD = computed(() => {
        if (!props.drawingConnection?.active) return ''
        return `M ${props.drawingConnection.currentX} ${props.drawingConnection.currentY} L ${props.drawingConnection.currentX} ${props.drawingConnection.currentY}`
    })
</script>
