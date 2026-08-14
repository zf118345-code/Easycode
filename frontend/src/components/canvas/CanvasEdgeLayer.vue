<!-- frontend/src/components/canvas/CanvasEdgeLayer.vue -->
<!--
    Shared SVG edges layer for WorkflowCanvas + TopologyCanvas.
    Renders:
      1. subtle grid
      2. clickable hit area (wide transparent path under each edge)
      3. the visible edge path (color-coded by success/failure)
      4. flow animation overlay
      5. edge labels
      6. real-time drag preview line
-->
<template>
    <svg
        class="canvas-edges-layer"
        :width="svgWidth"
        :height="svgHeight"
        :viewBox="`0 0 ${svgWidth} ${svgHeight}`"
        preserveAspectRatio="none">
        <defs>
            <pattern id="grid-pattern" width="20" height="20" patternUnits="userSpaceOnUse">
                <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255,255,255,0.04)" stroke-width="1" />
            </pattern>

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

            <!-- Preview -->
            <marker
id="arrow-preview" viewBox="0 0 10 10" refX="7" refY="5"
                    markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 2 L 10 5 L 0 8 z" fill="#4ed19c" />
            </marker>
        </defs>

        <!-- Background grid -->
        <rect
x="-5000" y="-5000" width="15000" height="15000"
              fill="url(#grid-pattern)" pointer-events="none" />

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

        <!-- Live drag preview -->
        <path
            v-if="drawingConnection?.active"
            :d="previewPathD"
            class="edge-path preview-path"
            :marker-end="drawingConnection?.previewMarkerUrl" />
    </svg>
</template>

<script setup>
    import { computed } from 'vue'
    import { getSimpleOrthoPath } from '@/utils/canvasRouter'

    const props = defineProps({
        edges:           { type: Array,  default: () => [] },
        drawingConnection:{ type: Object, default: null },
        svgWidth:        { type: Number, default: 5000 },
        svgHeight:       { type: Number, default: 3000 }
    })

    defineEmits(['edge-click'])

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
</script>
