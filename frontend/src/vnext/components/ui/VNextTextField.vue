<template>
    <input
        class="vnext-text-field"
        :class="[`is-${size}`, { 'has-error': invalid }]"
        :type="type"
        :value="modelValue ?? ''"
        :aria-invalid="invalid || undefined"
        @input="emitValue"
    />
</template>

<script setup lang="ts">
withDefaults(defineProps<{
    modelValue?: string | number | null
    type?: string
    size?: 'compact' | 'default' | 'touch'
    invalid?: boolean
}>(), { modelValue: '', type: 'text', size: 'default', invalid: false })
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
function emitValue(event: Event) { emit('update:modelValue', (event.target as HTMLInputElement).value) }
</script>

<style scoped>
.vnext-text-field {
    --field-height: var(--app-control-default);
    width: 100%;
    min-width: 0;
    height: var(--field-height);
    min-height: var(--field-height);
    padding: 0 10px;
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-md);
    outline: 0;
    background: var(--app-bg-input);
    color: var(--app-text-primary);
    font: inherit;
    font-size: var(--app-font-interface);
    line-height: 1;
    transition: background-color var(--app-motion-fast), border-color var(--app-motion-fast), box-shadow var(--app-motion-fast);
}
.vnext-text-field.is-compact { --field-height: var(--app-control-compact); }
.vnext-text-field.is-touch { --field-height: var(--app-control-touch); font-size: var(--app-font-mobile-input); }
.vnext-text-field::placeholder { color: var(--app-text-placeholder); }
.vnext-text-field:hover:not(:disabled) { border-color: var(--app-border-strong); }
.vnext-text-field:focus { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.vnext-text-field.has-error { border-color: var(--app-color-danger); }
.vnext-text-field:disabled { color: var(--app-text-disabled); opacity: .65; cursor: not-allowed; }
</style>
