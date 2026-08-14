<!-- frontend/src/components/controls/ControlNumber.vue -->
<template>
    <!-- 普通无单位数字输入框 -->
    <el-input-number
v-if="!hasSuffix"
                     :model-value="modelValue"
                     :min="config.min !== undefined ? config.min : 0"
                     :max="config.max !== undefined ? config.max : Infinity"
                     :step="config.step || (config.type === 'float' ? 0.1 : 1)"
                     :precision="config.type === 'float' ? 2 : 0"
                     :controls="false"
                     class="pure-number-input"
                     @update:model-value="val => $emit('update:modelValue', val)" />

    <!-- 带有单位/后缀的输入框 (由 config.suffix 或 config.unit 驱动) -->
    <el-input
v-else
              :model-value="modelValue"
              type="number"
              :min="config.min !== undefined ? config.min : 0"
              :max="config.max !== undefined ? config.max : Infinity"
              class="number-input-with-suffix"
              @update:model-value="val => $emit('update:modelValue', Number(val))">
        <template #suffix>
            <span class="input-unit-suffix">{{ displaySuffix }}</span>
        </template>
    </el-input>
</template>

<script setup>
    import { computed } from 'vue'

    const props = defineProps({
        config: { type: Object, required: true },
        modelValue: { type: [Number, String], default: 0 },
        label: { type: String, default: '' }
    })
    defineEmits(['update:modelValue'])

    const displaySuffix = computed(() => {
        return props.config.suffix || props.config.unit || ''
    })

    const hasSuffix = computed(() => {
        return !!displaySuffix.value
    })
</script>

<style scoped>
    .pure-number-input {
        width: 100% !important;
    }

    .number-input-with-suffix :deep(.el-input__wrapper) {
        background-color: var(--el-fill-color-blank) !important;
        box-shadow: 0 0 0 1px var(--el-border-color-light) inset !important;
        padding-left: 10px !important;
        padding-right: 8px !important;
    }

    .number-input-with-suffix :deep(.el-input__inner) {
        text-align: left !important;
        font-size: 12px;
        color: var(--el-text-color-primary);
    }

    .input-unit-suffix {
        font-size: 11px;
        font-weight: 600;
        color: var(--el-text-color-secondary);
        margin-left: 2px;
        white-space: nowrap;
        user-select: none;
    }
</style>