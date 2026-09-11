<template>
    <select
        class="vnext-select"
        :class="[`is-${size}`, { 'has-error': invalid }]"
        :value="modelValue ?? ''"
        :aria-invalid="invalid || undefined"
        @change="emitValue"
    ><slot /></select>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
    modelValue?: string | number | null
    size?: 'compact' | 'default' | 'touch'
    invalid?: boolean
}>(), { modelValue: '', size: 'default', invalid: false })
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
function emitValue(event: Event) { emit('update:modelValue', (event.target as HTMLSelectElement).value) }
</script>

<style scoped>
.vnext-select {
    --field-height: var(--app-control-default);
    width: 100%;
    min-width: 0;
    height: var(--field-height);
    min-height: var(--field-height);
    padding: 0 30px 0 10px;
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-md);
    outline: 0;
    background: var(--app-bg-input);
    color: var(--app-text-primary);
    font: inherit;
    font-size: var(--app-font-interface);
    line-height: 1;
    cursor: pointer;
    transition: background-color var(--app-motion-fast), border-color var(--app-motion-fast), box-shadow var(--app-motion-fast);
}
.vnext-select.is-compact { --field-height: var(--app-control-compact); }
.vnext-select.is-touch { --field-height: var(--app-control-touch); font-size: var(--app-font-mobile-input); }
.vnext-select:hover:not(:disabled) { border-color: var(--app-border-strong); }
.vnext-select:focus { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.vnext-select.has-error { border-color: var(--app-color-danger); }
.vnext-select:disabled { color: var(--app-text-disabled); opacity: .65; cursor: not-allowed; }
</style>
