<!-- frontend/src/components/controls/ControlSwitch.vue -->
<template>
    <el-switch
:model-value="modelValue"
               class="custom-fixed-switch"
               @update:model-value="val => $emit('update:modelValue', val)" />
</template>

<script setup>
defineProps({
  config: { type: Object, required: true },
  modelValue: { type: Boolean, default: false }
})
defineEmits(['update:modelValue'])
</script>

<style scoped>
    :deep(.custom-fixed-switch .el-switch__core) {
        background-color: var(--el-fill-color-blank, #181926) !important;
        border-color: var(--el-border-color-light, #313352) !important;
    }

    :deep(.custom-fixed-switch.is-checked .el-switch__core) {
        background-color: var(--el-color-primary, #4ed19c) !important;
        border-color: var(--el-color-primary, #4ed19c) !important;
    }
</style>