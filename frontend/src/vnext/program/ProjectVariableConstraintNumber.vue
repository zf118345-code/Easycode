<template>
    <label class="constraint-field app-form-row"><span class="app-form-label">{{ label }}</span><input class="app-form-control" type="number" :step="integer ? 1 : 'any'" :value="value" :disabled="disabled" @change="commit" /></label>
</template>
<script setup lang="ts">
import { computed } from 'vue'
const props = withDefaults(defineProps<{ label: string; field: string; constraints: Record<string, unknown>; integer?: boolean; disabled?: boolean }>(), { integer: false, disabled: false })
const emit = defineEmits<{ change: [field: string, value: number | null] }>()
const value = computed(() => props.constraints[props.field] ?? '')
function commit(event: Event): void {
    const raw = (event.target as HTMLInputElement).value
    emit('change', props.field, raw === '' ? null : props.integer ? Math.trunc(Number(raw)) : Number(raw))
}
</script>
<style scoped>
.constraint-field { --app-form-row-label-min: 62px; --app-form-row-label-max: 72px; color: var(--app-text-regular); font-size: var(--app-font-xs); }
input { width: 100%; min-height: var(--app-control-default); padding: 0 10px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); outline: 0; background: var(--app-bg-input); color: var(--app-text-primary); font: inherit; }
input:focus { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
</style>
