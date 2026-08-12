<!-- frontend/src/components/controls/ControlTextarea.vue -->
<template>
    <el-input :model-value="modelValue"
              type="textarea"
              :rows="config.rows || 3"
              :autosize="config.autosize !== undefined ? config.autosize : { minRows: 2, maxRows: 6 }"
              :placeholder="config.placeholder || config.label || 'ÇëÊäÈëÄÚÈÝ...'"
              class="custom-textarea-control"
              @update:model-value="val => $emit('update:modelValue', val)" />
</template>

<script setup>
defineProps({
  config: { type: Object, required: true },
  modelValue: { type: String, default: '' }
})

defineEmits(['update:modelValue'])
</script>

<style scoped>
    .custom-textarea-control :deep(.el-textarea__inner) {
        background-color: var(--el-fill-color-blank) !important;
        border-color: var(--el-border-color-light) !important;
        color: var(--el-text-color-primary) !important;
        font-size: 12px !important;
        font-family: var(--el-font-family-monospace, monospace) !important;
    }
</style>