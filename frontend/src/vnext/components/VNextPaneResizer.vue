<template>
    <div
        class="pane-resizer"
        :class="[`is-${orientation}`, { 'is-dragging': dragging }]"
        role="separator"
        tabindex="0"
        :aria-label="label"
        :aria-orientation="orientation"
        :aria-valuemin="min"
        :aria-valuemax="max"
        :aria-valuenow="modelValue"
        @pointerdown="startDrag"
        @keydown="handleKeydown"
        @dblclick="restoreDefault"
    ><span aria-hidden="true"></span></div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

const props = withDefaults(defineProps<{
    modelValue: number
    orientation: 'vertical' | 'horizontal'
    min: number
    max: number
    defaultValue: number
    label: string
    reverse?: boolean
    step?: number
}>(), { reverse: false, step: 16 })

const emit = defineEmits<{
    'update:modelValue': [value: number]
    commit: [value: number]
}>()

const dragging = ref(false)
let startCoordinate = 0
let startValue = 0
let currentValue = 0
let previousBodyCursor = ''

function clamp(value: number): number {
    return Math.max(props.min, Math.min(props.max, Math.round(value)))
}

function coordinate(event: PointerEvent): number {
    return props.orientation === 'vertical' ? event.clientX : event.clientY
}

function startDrag(event: PointerEvent): void {
    if (event.button !== 0) return
    event.preventDefault()
    dragging.value = true
    startCoordinate = coordinate(event)
    startValue = props.modelValue
    currentValue = props.modelValue
    previousBodyCursor = document.body.style.cursor
    document.body.style.cursor = props.orientation === 'vertical' ? 'col-resize' : 'row-resize'
    document.body.classList.add('is-resizing-pane')
    window.addEventListener('pointermove', continueDrag)
    window.addEventListener('pointerup', finishDrag, { once: true })
    window.addEventListener('pointercancel', finishDrag, { once: true })
}

function continueDrag(event: PointerEvent): void {
    if (!dragging.value) return
    const delta = coordinate(event) - startCoordinate
    currentValue = clamp(startValue + delta * (props.reverse ? -1 : 1))
    emit('update:modelValue', currentValue)
}

function finishDrag(): void {
    if (!dragging.value) return
    dragging.value = false
    document.body.classList.remove('is-resizing-pane')
    document.body.style.cursor = previousBodyCursor
    window.removeEventListener('pointermove', continueDrag)
    window.removeEventListener('pointerup', finishDrag)
    window.removeEventListener('pointercancel', finishDrag)
    emit('commit', currentValue)
}

function handleKeydown(event: KeyboardEvent): void {
    const smaller = props.orientation === 'vertical'
        ? (props.reverse ? 'ArrowRight' : 'ArrowLeft')
        : (props.reverse ? 'ArrowDown' : 'ArrowUp')
    const larger = props.orientation === 'vertical'
        ? (props.reverse ? 'ArrowLeft' : 'ArrowRight')
        : (props.reverse ? 'ArrowUp' : 'ArrowDown')
    if (event.key === 'Home') {
        event.preventDefault()
        restoreDefault()
        return
    }
    if (event.key !== smaller && event.key !== larger) return
    event.preventDefault()
    const multiplier = event.shiftKey ? 4 : 1
    const next = clamp(props.modelValue + (event.key === larger ? 1 : -1) * props.step * multiplier)
    emit('update:modelValue', next)
    emit('commit', next)
}

function restoreDefault(): void {
    const next = clamp(props.defaultValue)
    emit('update:modelValue', next)
    emit('commit', next)
}

onBeforeUnmount(() => {
    document.body.classList.remove('is-resizing-pane')
    document.body.style.cursor = previousBodyCursor
    window.removeEventListener('pointermove', continueDrag)
    window.removeEventListener('pointerup', finishDrag)
    window.removeEventListener('pointercancel', finishDrag)
})
</script>

<style scoped>
.pane-resizer {
    position: relative;
    z-index: 6;
    display: grid;
    place-items: center;
    flex: none;
    outline: 0;
    background: transparent;
    touch-action: none;
}

.pane-resizer.is-vertical { width: 5px; cursor: col-resize; }
.pane-resizer.is-horizontal { height: 5px; cursor: row-resize; }
.pane-resizer > span { display: block; border-radius: 2px; background: transparent; transition: background-color var(--app-transition-fast); }
.pane-resizer.is-vertical > span { width: 1px; height: 100%; }
.pane-resizer.is-horizontal > span { width: 100%; height: 1px; }
.pane-resizer:hover > span,
.pane-resizer:focus-visible > span,
.pane-resizer.is-dragging > span { background: var(--app-color-primary); }
.pane-resizer:focus-visible { box-shadow: var(--focus-ring); }
</style>
