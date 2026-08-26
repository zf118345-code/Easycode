<template>
    <div class="gesture-path-editor">
        <div v-for="(point, index) in visiblePoints" :key="index" class="path-point-card">
            <div class="point-heading">
                <span class="point-index">{{ pointLabel(index) }}</span>
                <div class="point-actions">
                    <button type="button" class="icon-button" title="从工作面板取点" @click="pickPoint(index)"><MapPinned /></button>
                    <button v-if="!isLongPress" type="button" class="icon-button" title="上移" :disabled="index === 0" @click="movePoint(index, -1)"><ArrowUp /></button>
                    <button v-if="!isLongPress" type="button" class="icon-button" title="下移" :disabled="index === points.length - 1" @click="movePoint(index, 1)"><ArrowDown /></button>
                    <button v-if="!isLongPress" type="button" class="icon-button danger" title="删除" :disabled="points.length <= minPoints" @click="removePoint(index)"><Trash2 /></button>
                </div>
            </div>
            <div class="point-grid">
                <label><span>X</span><el-input-number :model-value="point.position[0]" :min="0" :controls="false" @change="value => updateCoordinate(index, 0, value)" /></label>
                <label><span>Y</span><el-input-number :model-value="point.position[1]" :min="0" :controls="false" @change="value => updateCoordinate(index, 1, value)" /></label>
                <label v-if="index > 0 && !isLongPress"><span>移动</span><el-input-number :model-value="point.move_ms" :min="0" :max="30000" :step="10" :controls="false" @change="value => updateField(index, 'move_ms', value)" /><em>ms</em></label>
                <label v-if="!isLongPress"><span>{{ index === 0 ? '按下保持' : '到点保持' }}</span><el-input-number :model-value="point.hold_ms" :min="0" :max="30000" :step="10" :controls="false" @change="value => updateField(index, 'hold_ms', value)" /><em>ms</em></label>
            </div>
        </div>
        <button v-if="!isLongPress" type="button" class="add-point" :disabled="points.length >= maxPoints" @click="addPoint"><Plus />添加途径点</button>
        <div v-if="isLongPress && points.length > 1" class="mode-hint">长按模式只使用第一个点；切回拖拽后其余路径仍会保留。</div>
    </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowDown, ArrowUp, MapPinned, Plus, Trash2 } from 'lucide-vue-next'
import { captureApi } from '@/api/captureApi'
import { useIdeStore, useUiStore } from '@/stores'

const props = defineProps({ config: { type: Object, required: true }, modelValue: { type: Array, default: () => [] }, context: { type: Object, default: () => ({}) } })
const emit = defineEmits(['update:modelValue', 'update'])
const store = useIdeStore()
const uiStore = useUiStore()
const minPoints = computed(() => Math.max(2, Number(props.config.min_points || 2)))
const maxPoints = computed(() => Math.min(32, Math.max(minPoints.value, Number(props.config.max_points || 32))))
const isLongPress = computed(() => props.context?.action === 'long_press')
const finiteOr = (value, fallback) => Number.isFinite(Number(value)) ? Number(value) : fallback
const normalize = value => {
    const source = Array.isArray(value) && value.length ? value : (props.config.default || [])
    return source.slice(0, maxPoints.value).map((item, index) => ({
        position: [Number(item?.position?.[0]) || 0, Number(item?.position?.[1]) || 0],
        move_ms: index === 0 ? 0 : Math.max(0, finiteOr(item?.move_ms, 300)),
        hold_ms: Math.max(0, Number(item?.hold_ms) || 0)
    }))
}
const points = ref(normalize(props.modelValue))
watch(() => props.modelValue, value => { points.value = normalize(value) }, { deep: true })
const visiblePoints = computed(() => isLongPress.value ? points.value.slice(0, 1) : points.value)
const commit = () => {
    const value = points.value.map(item => ({ position: [...item.position], move_ms: item.move_ms, hold_ms: item.hold_ms }))
    emit('update:modelValue', value)
    emit('update', value)
}
const pointLabel = index => index === 0 ? '起点' : (index === points.value.length - 1 ? '终点' : `途径点 ${index}`)
const updateCoordinate = (index, axis, value) => { points.value[index].position[axis] = Math.max(0, Number(value) || 0); commit() }
const updateField = (index, field, value) => { points.value[index][field] = Math.max(0, Number(value) || 0); commit() }
const addPoint = () => {
    if (points.value.length >= maxPoints.value) return
    const last = points.value.at(-1) || { position: [480, 270] }
    points.value.push({ position: [last.position[0] + 20, last.position[1]], move_ms: 300, hold_ms: 0 })
    commit()
}
const removePoint = index => { if (points.value.length > minPoints.value) { points.value.splice(index, 1); commit() } }
const movePoint = (index, offset) => {
    const target = index + offset
    if (target < 0 || target >= points.value.length) return
    const copy = points.value[index]
    points.value[index] = points.value[target]
    points.value[target] = copy
    points.value[0].move_ms = 0
    commit()
}
const pickPoint = async index => {
    if (!store.currentProjectPath) return ElMessage.warning('请先打开项目')
    if (store.isRunning || store.isPaused) return ElMessage.warning('请先停止当前任务')
    const requestId = `gesture_${globalThis.crypto.randomUUID().replaceAll('-', '')}`
    uiStore.cancelFieldCapture()
    uiStore.setFieldCaptureHandler(requestId, async payload => {
        const point = payload?.point
        if (!Array.isArray(point) || point.length < 2) throw new Error('没有返回有效坐标')
        points.value[index].position = [Number(point[0]) || 0, Number(point[1]) || 0]
        commit()
        return { message: `${pointLabel(index)}已更新` }
    })
    try {
        await captureApi.trigger({ field_capture: { request_id: requestId, selection_mode: 'point', category: 'image', max_rects: 1, title: `设置${pointLabel(index)}` } })
    } catch (error) {
        uiStore.cancelFieldCapture(requestId)
        ElMessage.error(error?.message || '取点失败')
    }
}
</script>

<style scoped>
.gesture-path-editor { width: 100%; display: flex; flex-direction: column; gap: 8px; }
.path-point-card { padding: 9px; border: 1px solid var(--el-border-color-light); border-radius: var(--app-radius-md, 8px); background: var(--el-fill-color-extra-light); }
.point-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 7px; }
.point-index { font-size: 12px; font-weight: 600; color: var(--el-text-color-primary); }
.point-actions { display: flex; gap: 3px; }
.icon-button { width: 25px; height: 25px; padding: 5px; border: 0; border-radius: 6px; background: transparent; color: var(--el-text-color-secondary); cursor: pointer; }
.icon-button:hover:not(:disabled) { background: var(--el-fill-color); color: var(--el-color-primary); }
.icon-button.danger:hover:not(:disabled) { color: var(--el-color-danger); }
.icon-button:disabled { opacity: .3; cursor: default; }
.icon-button svg, .add-point svg { width: 14px; height: 14px; }
.point-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }
.point-grid label { display: flex; align-items: center; gap: 5px; min-width: 0; font-size: 11px; color: var(--el-text-color-secondary); }
.point-grid label span { min-width: 18px; white-space: nowrap; }
.point-grid label:nth-child(n+3) span { min-width: 48px; }
.point-grid em { font-style: normal; font-size: 10px; }
.point-grid :deep(.el-input-number) { width: 100%; }
.point-grid :deep(.el-input__wrapper) { padding: 0 6px; }
.add-point { height: 30px; display: flex; align-items: center; justify-content: center; gap: 6px; border: 1px dashed var(--el-border-color); border-radius: 7px; background: transparent; color: var(--el-text-color-secondary); cursor: pointer; }
.add-point:hover:not(:disabled) { color: var(--el-color-primary); border-color: var(--el-color-primary); background: color-mix(in srgb, var(--el-color-primary) 7%, transparent); }
.add-point:disabled { opacity: .4; cursor: default; }
.mode-hint { font-size: 11px; line-height: 1.5; color: var(--el-text-color-secondary); }
</style>
