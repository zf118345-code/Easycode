<!-- frontend/src/components/controls/ControlString.vue -->
<template>
    <el-input :model-value="modelValue"
              :placeholder="config.label || ''"
              @update:model-value="val => $emit('update:modelValue', val)" />
</template>

<script setup>
    defineProps({
        config: { type: Object, required: true },
        modelValue: { type: String, default: '' }
    })
    defineEmits(['update:modelValue'])
</script>