<template><aside class="vnext-navigation-pane" v-bind="$attrs"><slot /></aside></template>

<script setup lang="ts">
defineOptions({ inheritAttrs: false })
</script>

<style scoped>
.vnext-navigation-pane { box-sizing: border-box; min-width: 0; min-height: 0; display: flex; flex-direction: column; overflow: hidden; padding: 0 !important; border-right: 1px solid var(--app-border-subtle) !important; background: var(--app-bg-sidebar) !important; color: var(--app-text-regular); }
.vnext-navigation-pane :deep(.vnext-pane-header__actions button) {
    width: var(--app-control-compact) !important;
    min-width: var(--app-control-compact) !important;
    max-width: var(--app-control-compact) !important;
    padding: 0 !important;
    gap: 0 !important;
    overflow: hidden;
    font-size: 0 !important;
}
.vnext-navigation-pane :deep(.vnext-pane-header__actions),
.vnext-navigation-pane :deep(.vnext-pane-header__actions > *) { gap: var(--app-spacing-xs) !important; }
.vnext-navigation-pane :deep(.vnext-pane-header__actions button > span) { display: none !important; }
</style>
