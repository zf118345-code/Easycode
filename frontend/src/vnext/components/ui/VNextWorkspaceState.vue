<template>
    <section
        class="vnext-workspace-state"
        :class="[{ compact }, `is-${kind}`]"
        :role="kind === 'error' ? 'alert' : 'status'"
        :aria-live="kind === 'error' ? 'assertive' : 'polite'"
        :data-ui-state="kind"
    >
        <span v-if="$slots.icon" class="vnext-workspace-state__icon" aria-hidden="true"><slot name="icon" /></span>
        <strong>{{ title }}</strong>
        <p v-if="description">{{ description }}</p>
        <div v-if="$slots.actions" class="vnext-workspace-state__actions"><slot name="actions" /></div>
    </section>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
    kind?: 'loading' | 'empty' | 'filtered' | 'selection' | 'error' | 'disabled'
    title: string
    description?: string
    compact?: boolean
}>(), {
    kind: 'empty',
    description: '',
    compact: false,
})
</script>

<style scoped>
.vnext-workspace-state {
    box-sizing: border-box;
    width: 100%;
    min-height: 160px;
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    gap: 7px;
    padding: 28px;
    color: var(--app-text-secondary);
    text-align: center;
}

.vnext-workspace-state.compact { min-height: 112px; padding: 18px; }
.vnext-workspace-state__icon { display: grid; place-items: center; color: var(--app-text-placeholder); }
.vnext-workspace-state.is-error .vnext-workspace-state__icon,
.vnext-workspace-state.is-error > strong { color: var(--app-color-danger); }
.vnext-workspace-state > strong { color: var(--app-text-primary); font-size: var(--app-font-body); font-weight: 600; }
.vnext-workspace-state > p { max-width: 44ch; margin: 0; font-size: var(--app-font-caption); line-height: var(--app-line-height-body); }
.vnext-workspace-state__actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px; margin-top: 3px; }
.vnext-workspace-state__actions :deep(button) {
    min-height: var(--app-control-compact);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 0 10px;
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    background: var(--app-bg-raised);
    color: var(--app-text-regular);
    font: inherit;
    font-size: var(--app-font-caption);
    cursor: pointer;
}
.vnext-workspace-state__actions :deep(button:hover:not(:disabled)),
.vnext-workspace-state__actions :deep(button:focus-visible) {
    border-color: var(--app-border-strong);
    background: var(--app-bg-hover);
    color: var(--app-text-primary);
    outline: 0;
    box-shadow: var(--focus-ring);
}
.vnext-workspace-state__actions :deep(button:disabled) { opacity: .48; cursor: not-allowed; }
</style>
