<!-- frontend/src/components/controls/ControlRadioGroup.vue -->
<template>
    <el-radio-group
:model-value="modelValue"
                    class="custom-segmented-radio"
                    @update:model-value="val => $emit('update:modelValue', val)">
        <el-radio-button
v-for="opt in resolvedOptions"
                         :key="opt.value"
                         :value="opt.value">
            {{ opt.label }}
        </el-radio-button>
    </el-radio-group>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  config: { type: Object, required: true },
  modelValue: { required: false },
  context: { type: Object, default: () => ({}) }
})

defineEmits(['update:modelValue'])

const resolvedOptions = computed(() => {
  const options = props.config.options
  if (typeof options === 'function') {
    try {
      const res = options(props.context, props.modelValue)
      return Array.isArray(res) ? res.map(o => typeof o === 'string' ? { value: o, label: o } : o) : []
    } catch {
      return []
    }
  }
  if (Array.isArray(options)) {
    return options.map(o => typeof o === 'string' ? { value: o, label: o } : o)
  }
  return []
})
</script>

<style scoped>
    .custom-segmented-radio {
        display: inline-flex;
        width: 100%;
    }

        .custom-segmented-radio :deep(.el-radio-button) {
            flex: 1;
            display: flex;
        }

        .custom-segmented-radio :deep(.el-radio-button__inner) {
            width: 100%;
            background-color: var(--el-fill-color-blank) !important;
            border-color: var(--el-border-color-light) !important;
            color: var(--el-text-color-regular) !important;
            font-size: 12px !important;
            padding: 6px 10px !important;
        }

        .custom-segmented-radio :deep(.el-radio-button.is-active .el-radio-button__inner) {
            background-color: var(--el-color-primary) !important;
            border-color: var(--el-color-primary) !important;
            color: #fff !important;
            box-shadow: -1px 0 0 0 var(--el-color-primary) !important;
        }
</style>