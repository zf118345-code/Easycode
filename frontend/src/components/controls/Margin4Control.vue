<!-- frontend/src/components/controls/Margin4Control.vue -->
<template>
    <div class="margin4-control">
        <div class="input-grid">
            <div v-for="(item, idx) in fields" :key="item.key" class="field-item">
                <span class="field-label">{{ item.label }}</span>
                <el-input-number v-model="getValues[idx]"
                                 :controls="false"
                                 size="small"
                                 class="compact-num-input"
                                 @change="emitUpdate" />
            </div>
        </div>
    </div>
</template>

<script setup>
    import { computed } from 'vue'

    const props = defineProps({
        modelValue: { type: Array, default: () => [0, 0, 0, 0] },
        config: { type: Object, default: () => ({}) }
    })

    const emit = defineEmits(['update:modelValue', 'change'])

    const fields = [
        { key: 'top', label: 'T' },
        { key: 'bottom', label: 'B' },
        { key: 'left', label: 'L' },
        { key: 'right', label: 'R' }
    ]

    // 响应式直接映射数组项，无需 watch
    const getValues = computed(() => {
        const arr = Array.isArray(props.modelValue) ? props.modelValue : [0, 0, 0, 0]
        return fields.map((_, i) => Number(arr[i]) || 0)
    })

    const emitUpdate = () => {
        const result = [...getValues.value]
        emit('update:modelValue', result)
        emit('change', result)
    }
</script>

<style scoped>
    .margin4-control {
        width: 100%;
    }

    .input-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 6px;
        width: 100%;
    }

    .field-item {
        display: flex;
        align-items: center;
        background: var(--el-fill-color-blank);
        border: 1px solid var(--el-border-color-light);
        border-radius: 6px;
        padding: 2px 6px;
    }

    .field-label {
        font-size: 11px;
        font-weight: 600;
        color: var(--el-text-color-secondary);
        margin-right: 4px;
        user-select: none;
    }

    .compact-num-input {
        width: 100% !important;
    }

        .compact-num-input :deep(.el-input__wrapper) {
            padding: 0 !important;
            box-shadow: none !important;
            background: transparent !important;
        }

        .compact-num-input :deep(.el-input__inner) {
            text-align: center !important;
            font-size: 12px !important;
            font-weight: 600 !important;
            color: var(--el-text-color-primary) !important;
        }
</style>