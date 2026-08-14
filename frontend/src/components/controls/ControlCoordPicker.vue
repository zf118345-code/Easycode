<!-- frontend/src/components/controls/ControlCoordPicker.vue -->
<template>
    <div class="coord-picker-wrapper">
        <!-- 顶栏：左侧标题，右侧“取点 / 框选区域”按钮 -->
        <div class="coord-header-row">
            <span class="coord-title">{{ label }}</span>
            <button
type="button"
                    class="app-btn-secondary"
                    @click="$emit('openScreenshot', is2D ? 'point' : 'region')">
                <component :is="is2D ? MapPinned : SquareDashedMousePointer" class="app-btn-icon" />
                <span>{{ is2D ? '取点' : '框选区域' }}</span>
            </button>
        </div>

        <!-- 数值输入控件行 (统一遍历渲染，精简 template) -->
        <div class="coord-row">
            <div v-for="(tag, idx) in activeTags" :key="tag" class="coord-item">
                <span class="coord-tag">{{ tag }}</span>
                <el-input-number v-model="coordValue[idx]" :min="0" :controls="false" size="small" @change="updateVal" />
            </div>
        </div>
    </div>
</template>

<script setup>
    // ControlCoordPicker.vue script 部分
    import { computed, ref, watch } from 'vue'
    import { MapPinned, SquareDashedMousePointer } from 'lucide-vue-next'

    const props = defineProps({
        config: { type: Object, required: true },
        modelValue: { type: Array, default: () => [] },
        value: { type: Array, default: () => [] },
        label: { type: String, default: '' }
    })

    const emit = defineEmits(['update:modelValue', 'update', 'openScreenshot'])

    const is2D = computed(() => props.config.type && props.config.type.startsWith('list_int2'))
    const activeTags = computed(() => is2D.value ? ['X', 'Y'] : ['X', 'Y', 'W', 'H'])

    const normalizeValue = (val) => {
        const arr = Array.isArray(val) ? val : []
        const targetLen = is2D.value ? 2 : 4
        const result = []
        for (let i = 0; i < targetLen; i++) {
            result[i] = Number(arr[i]) || 0
        }
        return result
    }

    const coordValue = ref(normalizeValue(props.modelValue || props.value))

    // ⚡ 增强 watch：兼容 modelValue 和 value 两种通信方式
    watch(() => props.modelValue || props.value, (newVal) => {
        coordValue.value = normalizeValue(newVal)
    }, { deep: true, immediate: true })

    const updateVal = () => {
        emit('update:modelValue', [...coordValue.value])
        emit('update', [...coordValue.value])
    }
</script>

<style scoped>
    .coord-picker-wrapper {
        width: 100%;
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-bottom: 8px;
    }

    .coord-header-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        width: 100%;
    }

    .coord-title {
        font-size: 13px;
        color: var(--el-text-color-primary);
        font-weight: 500;
    }

    .coord-row {
        display: flex;
        gap: 6px;
        width: 100%;
    }

    .coord-item {
        flex: 1;
        display: flex;
        align-items: center;
        background: var(--el-fill-color-blank);
        border: 1px solid var(--el-border-color-light);
        border-radius: var(--app-radius-sm, 4px);
        padding: 2px 4px;
    }

    .coord-tag {
        font-size: 11px;
        color: var(--el-text-color-secondary);
        font-weight: 500;
        margin-right: 2px;
    }

    :deep(.el-input-number) {
        width: 100% !important;
        background-color: transparent !important;
        border: none !important;
    }

    :deep(.el-input-number__decrease),
    :deep(.el-input-number__increase) {
        display: none !important;
    }

    :deep(.el-input-number .el-input__wrapper) {
        background-color: transparent !important;
        box-shadow: none !important;
        padding: 0 !important;
    }

    :deep(.el-input-number .el-input__inner) {
        text-align: center !important;
        color: var(--el-text-color-primary) !important;
    }
</style>