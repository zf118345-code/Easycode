<!-- frontend/src/components/controls/ControlSlider.vue -->
<template>
    <div class="control-slider-container">
        <el-slider
:model-value="Number(modelValue)"
                   :min="config.min !== undefined ? config.min : 0"
                   :max="config.max !== undefined ? config.max : 100"
                   :step="config.step || 1"
                   class="custom-slider"
                   @update:model-value="val => $emit('update:modelValue', val)" />
        <span v-if="suffix" class="slider-suffix-badge">{{ modelValue }}{{ suffix }}</span>
    </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  config: { type: Object, required: true },
  modelValue: { type: [Number, String], default: 0 }
})

defineEmits(['update:modelValue'])

const suffix = computed(() => props.config.suffix || props.config.unit || '')
</script>

<style scoped>
    .control-slider-container {
        display: flex;
        align-items: center;
        gap: 12px;
        width: 100%;
    }

    .custom-slider {
        flex: 1;
    }

    .slider-suffix-badge {
        font-size: 11px;
        font-weight: 600;
        color: var(--el-color-primary);
        min-width: 36px;
        text-align: right;
    }
</style>