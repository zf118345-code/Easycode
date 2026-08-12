<!-- frontend/src/components/controls/ControlDict.vue -->
<template>
    <div class="dict-container">
        <ParamRenderer v-for="(subConfig, subKey) in config.sub"
                       :key="subKey"
                       :config="subConfig"
                       :value="localDict ? localDict[subKey] : undefined"
                       :label="subConfig.label || subKey"
                       :context="localDict"
                       @update="val => handleSubUpdate(subKey, val)" />
    </div>
</template>

<script setup>
import { computed } from 'vue'
import ParamRenderer from '@/components/ParamRenderer.vue'

const props = defineProps({
  config: { type: Object, required: true },
  modelValue: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['update:modelValue'])

const localDict = computed(() => props.modelValue || {})

const handleSubUpdate = (subKey, val) => {
  const updated = { ...localDict.value, [subKey]: val }
  emit('update:modelValue', updated)
}
</script>

<style scoped>
    .dict-container {
        padding-left: 12px;
        border-left: 2px solid var(--el-border-color-light);
        margin-top: 4px;
        width: 100%;
    }
</style>