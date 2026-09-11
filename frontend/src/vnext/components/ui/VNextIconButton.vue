<template>
    <button
        ref="buttonElement"
        class="vnext-icon-button"
        :class="[`is-${role}`, `is-${size}`, `is-${tone}`]"
        type="button"
        :title="title || label"
        :aria-label="label"
        :aria-pressed="pressed === undefined ? undefined : pressed"
        :disabled="disabled"
    ><slot /></button>
</template>

<script setup lang="ts">
import { ref } from 'vue'

withDefaults(defineProps<{
    label: string
    title?: string
    role?: 'title' | 'toolbar' | 'field'
    size?: 'compact' | 'default' | 'touch'
    tone?: 'neutral' | 'danger'
    pressed?: boolean
    disabled?: boolean
}>(), {
    title: '',
    role: 'toolbar',
    size: 'compact',
    tone: 'neutral',
    pressed: undefined,
    disabled: false,
})
const buttonElement = ref<HTMLButtonElement | null>(null)
defineExpose({ focus: () => buttonElement.value?.focus(), element: buttonElement })
</script>

<style scoped>
.vnext-icon-button {
    --icon-button-size: var(--app-control-compact);
    width: var(--icon-button-size);
    min-width: var(--icon-button-size);
    height: var(--icon-button-size);
    min-height: var(--icon-button-size);
    display: inline-grid;
    flex: 0 0 var(--icon-button-size);
    place-items: center;
    padding: 0;
    border: 1px solid transparent;
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-secondary);
    font: inherit;
    line-height: 1;
    appearance: none;
    cursor: pointer;
    transition: background-color var(--app-motion-fast), color var(--app-motion-fast), opacity var(--app-motion-fast);
}
.vnext-icon-button.is-default { --icon-button-size: var(--app-control-default); }
.vnext-icon-button.is-touch { --icon-button-size: var(--app-control-touch); }
.vnext-icon-button.is-field { border-color: var(--app-border-default); background: var(--app-bg-input); }
.vnext-icon-button:hover:not(:disabled), .vnext-icon-button:focus-visible { background: var(--app-bg-hover); color: var(--app-text-primary); }
.vnext-icon-button:active:not(:disabled), .vnext-icon-button[aria-pressed="true"] { background: var(--app-bg-active); color: var(--app-text-primary); }
.vnext-icon-button.is-danger:hover:not(:disabled), .vnext-icon-button.is-danger:focus-visible { color: var(--app-color-danger); }
.vnext-icon-button:focus-visible { outline: 0; box-shadow: var(--focus-ring); }
.vnext-icon-button:disabled { opacity: .35; cursor: not-allowed; }
.vnext-icon-button :deep(svg) { width: 14px; height: 14px; display: block; stroke-width: 2; }
</style>
