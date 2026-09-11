<template><span class="vnext-badge" :class="`is-${tone}`"><slot /></span></template>
<script setup lang="ts">withDefaults(defineProps<{ tone?: 'neutral' | 'accent' | 'success' | 'warning' | 'danger' }>(), { tone: 'neutral' })</script>
<style scoped>
.vnext-badge { min-width: 0; height: 20px; display: inline-flex; align-items: center; justify-content: center; padding: 0 7px; border: 1px solid var(--app-border-subtle); border-radius: 999px; background: var(--app-bg-raised); color: var(--app-text-secondary); font-size: var(--app-font-xs); font-weight: 550; line-height: 1; white-space: nowrap; }
.vnext-badge.is-accent { border-color: color-mix(in srgb, var(--app-color-primary) 48%, var(--app-border-subtle)); color: var(--app-color-primary); }
.vnext-badge.is-success { color: var(--app-color-success); }
.vnext-badge.is-warning { color: var(--app-color-warning); }
.vnext-badge.is-danger { color: var(--app-color-danger); }
</style>
