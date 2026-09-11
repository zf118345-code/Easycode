<template>
    <header
        class="vnext-pane-header"
        :class="{
            'has-description': Boolean(description || $slots.description),
            'has-icon-only-actions': iconOnlyActions,
        }"
        :data-ui-role="role"
    >
        <div class="vnext-pane-header__identity">
            <div class="vnext-pane-header__title-row">
                <component :is="headingTag" class="vnext-pane-header__title">
                    <slot name="title">{{ title }}</slot>
                </component>
                <span v-if="meta || $slots.meta" class="vnext-pane-header__meta">
                    <slot name="meta">{{ meta }}</slot>
                </span>
            </div>
            <p v-if="description || $slots.description" class="vnext-pane-header__description">
                <slot name="description">{{ description }}</slot>
            </p>
        </div>
        <div v-if="$slots.actions" class="vnext-pane-header__actions">
            <slot name="actions" />
        </div>
    </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
    title?: string
    meta?: string | number
    description?: string
    role?: 'pane' | 'workspace' | 'inspector'
    headingLevel?: 1 | 2 | 3
    iconOnlyActions?: boolean
}>(), {
    title: '',
    meta: '',
    description: '',
    role: 'pane',
    headingLevel: 2,
    iconOnlyActions: false,
})

const headingTag = computed(() => `h${props.headingLevel}`)
</script>

<style scoped>
.vnext-pane-header {
    box-sizing: border-box;
    min-width: 0;
    height: var(--app-height-pane-header) !important;
    min-height: var(--app-height-pane-header) !important;
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 0 var(--app-pane-inline-padding) !important;
    border-bottom: 1px solid var(--app-border-subtle) !important;
    background: var(--app-bg-sidebar) !important;
    color: var(--app-text-regular);
}

.vnext-pane-header[data-ui-role="workspace"] {
    height: var(--app-height-workspace-header) !important;
    min-height: var(--app-height-workspace-header) !important;
    padding-inline: var(--app-workspace-inline-padding) !important;
    background: var(--app-bg-base) !important;
}

.vnext-pane-header.has-description {
    height: var(--app-height-workspace-header-described) !important;
    min-height: var(--app-height-workspace-header-described) !important;
    align-items: flex-start;
    padding-block: 9px !important;
}

.vnext-pane-header__identity {
    min-width: 0;
    display: flex;
    flex: 1;
    flex-direction: column;
    justify-content: center;
    gap: 2px;
}

.vnext-pane-header__title-row,
.vnext-pane-header__actions {
    min-width: 0;
    display: flex;
    align-items: center;
}

.vnext-pane-header__title-row { gap: 7px; }
.vnext-pane-header__actions { flex: 0 0 auto; gap: var(--app-spacing-xs); }
.vnext-pane-header__actions :deep(> *) { min-width: 0; display: flex; align-items: center; gap: var(--app-spacing-xs) !important; }

.vnext-pane-header__title {
    min-width: 0;
    margin: 0;
    overflow: hidden;
    color: var(--app-text-primary);
    font-size: var(--app-font-pane-title);
    font-weight: 600;
    line-height: var(--app-line-height-compact);
    text-overflow: ellipsis;
    white-space: nowrap;
}

.vnext-pane-header[data-ui-role="workspace"] .vnext-pane-header__title {
    font-size: var(--app-font-page-title);
}

.vnext-pane-header__meta,
.vnext-pane-header__description {
    color: var(--app-text-secondary);
    font-weight: 400;
}

.vnext-pane-header__meta { font-size: var(--app-font-pane-title); }
.vnext-pane-header[data-ui-role="workspace"] .vnext-pane-header__meta { font-size: var(--app-font-page-title); }
.vnext-pane-header__description { font-size: var(--app-font-interface); }

.vnext-pane-header__actions :deep(button) {
    box-sizing: border-box;
    min-width: var(--app-control-compact) !important;
    height: var(--app-control-compact) !important;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 0 8px !important;
    border: 1px solid transparent !important;
    border-radius: var(--app-radius-sm) !important;
    background: transparent !important;
    color: var(--app-text-secondary) !important;
    font: inherit;
    font-size: var(--app-font-xs);
    line-height: 1;
    white-space: nowrap;
    appearance: none;
    cursor: pointer;
    transition:
        background-color var(--app-motion-fast),
        color var(--app-motion-fast),
        opacity var(--app-motion-fast);
}
.vnext-pane-header.has-icon-only-actions .vnext-pane-header__actions :deep(button) {
    width: var(--app-control-compact) !important;
    min-width: var(--app-control-compact) !important;
    max-width: var(--app-control-compact) !important;
    padding: 0 !important;
    gap: 0 !important;
    overflow: hidden;
    font-size: 0 !important;
}
.vnext-pane-header.has-icon-only-actions .vnext-pane-header__actions :deep(button > span) { display: none !important; }
.vnext-pane-header__actions :deep(button svg) {
    width: 14px !important;
    height: 14px !important;
    flex: 0 0 14px;
    stroke-width: 2;
}
.vnext-pane-header__actions :deep(button:hover:not(:disabled)),
.vnext-pane-header__actions :deep(button:focus-visible) { outline: 0 !important; border-color: transparent !important; background: var(--app-bg-hover) !important; color: var(--app-text-primary) !important; }
.vnext-pane-header__actions :deep(button:active:not(:disabled)),
.vnext-pane-header__actions :deep(button[aria-pressed="true"]:not(:disabled)) { background: var(--app-bg-active) !important; color: var(--app-text-primary) !important; }
.vnext-pane-header__actions :deep(button:focus-visible) { box-shadow: var(--focus-ring) !important; }
.vnext-pane-header__actions :deep(button:disabled) { background: transparent !important; color: var(--app-text-secondary) !important; opacity: .35 !important; cursor: not-allowed !important; }

.vnext-pane-header__meta { flex: 0 0 auto; white-space: nowrap; }
.vnext-pane-header__description {
    max-width: 72ch;
    margin: 0;
    overflow: hidden;
    line-height: var(--app-line-height-compact);
    text-overflow: ellipsis;
    white-space: nowrap;
}
</style>
