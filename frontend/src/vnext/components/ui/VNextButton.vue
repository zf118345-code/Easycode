<template>
    <button
        ref="buttonElement"
        class="vnext-button"
        :class="[`is-${tone}`, `is-${appearance}`, `is-${size}`, { 'is-block': block, 'is-loading': loading }]"
        :type="type"
        :disabled="disabled || loading"
        :aria-busy="loading || undefined"
    >
        <span v-if="loading" class="vnext-button__spinner" aria-hidden="true" />
        <span v-if="$slots.icon" class="vnext-button__icon" aria-hidden="true"><slot name="icon" /></span>
        <span class="vnext-button__label"><slot /></span>
        <span v-if="$slots.trailing" class="vnext-button__icon" aria-hidden="true"><slot name="trailing" /></span>
    </button>
</template>

<script setup lang="ts">
import { ref } from 'vue'

withDefaults(defineProps<{
    tone?: 'neutral' | 'primary' | 'danger'
    appearance?: 'solid' | 'outline' | 'ghost'
    size?: 'compact' | 'default' | 'touch'
    type?: 'button' | 'submit' | 'reset'
    disabled?: boolean
    loading?: boolean
    block?: boolean
}>(), {
    tone: 'neutral',
    appearance: 'outline',
    size: 'default',
    type: 'button',
    disabled: false,
    loading: false,
    block: false,
})
const buttonElement = ref<HTMLButtonElement | null>(null)
defineExpose({ focus: (options?: FocusOptions) => buttonElement.value?.focus(options), element: buttonElement })
</script>

<style scoped>
.vnext-button {
    --button-height: var(--app-control-default);
    min-width: 0;
    height: var(--button-height);
    min-height: var(--button-height);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 0 12px;
    border: 1px solid transparent;
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-regular);
    font: inherit;
    font-size: var(--app-font-interface);
    font-weight: 550;
    line-height: var(--app-line-height-compact);
    white-space: nowrap;
    appearance: none;
    cursor: pointer;
    user-select: none;
    transition: background-color var(--app-motion-fast), border-color var(--app-motion-fast), color var(--app-motion-fast), opacity var(--app-motion-fast);
}

.vnext-button.is-compact { --button-height: var(--app-control-compact); padding-inline: 9px; }
.vnext-button.is-touch { --button-height: var(--app-control-touch); padding-inline: 15px; }
.vnext-button.is-block { width: 100%; }
.vnext-button.is-outline { border-color: var(--app-border-default); background: var(--app-bg-raised); }
.vnext-button.is-ghost { border-color: transparent; background: transparent; color: var(--app-text-secondary); }
.vnext-button.is-solid.is-neutral { background: var(--app-bg-active); color: var(--app-text-primary); }
.vnext-button.is-solid.is-primary { background: var(--app-color-primary); color: var(--app-color-on-primary); }
.vnext-button.is-solid.is-danger { background: var(--app-color-danger); color: var(--app-color-on-primary); }
.vnext-button.is-outline.is-primary { border-color: color-mix(in srgb, var(--app-color-primary) 58%, var(--app-border-default)); color: var(--app-color-primary); }
.vnext-button.is-outline.is-danger { border-color: color-mix(in srgb, var(--app-color-danger) 58%, var(--app-border-default)); color: var(--app-color-danger); }
.vnext-button:hover:not(:disabled) { border-color: var(--app-border-strong); background: var(--app-bg-hover); color: var(--app-text-primary); }
.vnext-button.is-solid.is-primary:hover:not(:disabled) { border-color: transparent; background: var(--app-color-primary-hover); color: var(--app-color-on-primary); }
.vnext-button.is-solid.is-danger:hover:not(:disabled) { border-color: transparent; background: color-mix(in srgb, var(--app-color-danger) 86%, white); color: var(--app-color-on-primary); }
.vnext-button:active:not(:disabled) { background: var(--app-bg-active); }
.vnext-button.is-solid.is-primary:active:not(:disabled) { background: var(--app-color-primary-pressed); }
.vnext-button:focus-visible { outline: 0; box-shadow: var(--focus-ring); }
.vnext-button:disabled { opacity: .35; cursor: not-allowed; }
.vnext-button.is-loading { cursor: wait; }
.vnext-button__label { min-width: 0; display: block; overflow: hidden; line-height: var(--app-line-height-compact); text-overflow: ellipsis; }
.vnext-button__icon { width: 14px; height: 14px; display: grid; flex: 0 0 14px; place-items: center; }
.vnext-button__icon :deep(svg) { width: 14px; height: 14px; display: block; stroke-width: 2; }
.vnext-button__spinner { width: 13px; height: 13px; flex: 0 0 13px; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: vnext-button-spin .7s linear infinite; }
@keyframes vnext-button-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .vnext-button__spinner { animation-duration: 1.4s; } }
</style>
