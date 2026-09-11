<template>
    <textarea class="vnext-textarea" :value="modelValue" :rows="rows" :disabled="disabled" :readonly="readonly" :placeholder="placeholder" :aria-invalid="invalid || undefined" @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)" />
</template>
<script setup lang="ts">
withDefaults(defineProps<{ modelValue?: string; rows?: number; disabled?: boolean; readonly?: boolean; placeholder?: string; invalid?: boolean }>(), { modelValue: '', rows: 3, disabled: false, readonly: false, placeholder: '', invalid: false })
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>
<style scoped>
.vnext-textarea { box-sizing: border-box; width: 100%; min-height: calc(var(--app-control-default) * 2); padding: 8px 10px; resize: vertical; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); background: var(--app-bg-control); color: var(--app-text-regular); font: inherit; font-size: var(--app-font-interface); line-height: var(--app-line-height-regular); transition: border-color var(--app-motion-fast), box-shadow var(--app-motion-fast), background-color var(--app-motion-fast); }
.vnext-textarea:hover:not(:disabled):not(:read-only) { border-color: var(--app-border-strong); }
.vnext-textarea:focus-visible { outline: 0; border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.vnext-textarea[aria-invalid="true"] { border-color: var(--app-color-danger); }
.vnext-textarea:disabled { opacity: .5; cursor: not-allowed; }
.vnext-textarea:read-only { background: var(--app-bg-raised); color: var(--app-text-secondary); }
.vnext-textarea::placeholder { color: var(--app-text-muted); }
</style>
