<template><button type="button" class="vnext-switch" role="switch" :aria-checked="modelValue" :aria-label="label" :disabled="disabled" @click="emit('update:modelValue', !modelValue)"><span class="vnext-switch__thumb" aria-hidden="true" /></button></template>
<script setup lang="ts">
withDefaults(defineProps<{ modelValue?: boolean; label: string; disabled?: boolean }>(), { modelValue: false, disabled: false })
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
</script>
<style scoped>
.vnext-switch { box-sizing: border-box; width: 32px; height: 18px; display: inline-flex; align-items: center; padding: 2px; border: 1px solid var(--app-border-default); border-radius: 999px; background: var(--app-bg-active); appearance: none; cursor: pointer; transition: background-color var(--app-motion-fast), border-color var(--app-motion-fast), opacity var(--app-motion-fast); }
.vnext-switch__thumb { width: 12px; height: 12px; display: block; border-radius: 50%; background: var(--app-text-secondary); transform: translateX(0); transition: transform var(--app-motion-normal), background-color var(--app-motion-fast); }
.vnext-switch[aria-checked="true"] { border-color: var(--app-color-primary); background: color-mix(in srgb, var(--app-color-primary) 30%, var(--app-bg-active)); }
.vnext-switch[aria-checked="true"] .vnext-switch__thumb { background: var(--app-color-primary); transform: translateX(14px); }
.vnext-switch:hover:not(:disabled) { border-color: var(--app-border-strong); }
.vnext-switch:focus-visible { outline: 0; box-shadow: var(--focus-ring); }
.vnext-switch:disabled { opacity: .35; cursor: not-allowed; }
@media (prefers-reduced-motion: reduce) { .vnext-switch__thumb { transition: none; } }
</style>
