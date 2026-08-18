<!-- frontend/src/components/controls/ControlSelect.vue -->
<template>
    <el-select
:model-value="modelValue"
               :placeholder="config.label ? `请选择${config.label}` : '请选择...'"
               :disabled="config.readonly"
               style="width: 100%;"
               @update:model-value="val => $emit('update:modelValue', val)">
        <el-option
v-for="opt in resolvedOptions"
                   :key="opt.value"
                   :label="opt.label"
                   :value="opt.value" />
    </el-select>
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
                const result = options(props.context, props.modelValue)
                return Array.isArray(result) ? result.map(opt => typeof opt === 'string' ? { value: opt, label: opt } : opt) : []
            } catch {
                return []
            }
        }
        if (Array.isArray(options)) {
            return options.map(opt => typeof opt === 'string' ? { value: opt, label: opt } : opt)
        }
        return []
    })
</script>