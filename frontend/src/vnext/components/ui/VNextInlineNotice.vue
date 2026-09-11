<template>
    <div
        class="vnext-inline-notice"
        :class="[{ compact }, `is-${tone}`]"
        :role="tone === 'error' ? 'alert' : 'status'"
        :aria-live="tone === 'error' ? 'assertive' : 'polite'"
        :data-ui-feedback="tone"
    >
        <CircleAlert v-if="tone === 'error'" :size="14" aria-hidden="true" />
        <TriangleAlert v-else-if="tone === 'warning'" :size="14" aria-hidden="true" />
        <CircleCheck v-else-if="tone === 'success'" :size="14" aria-hidden="true" />
        <Info v-else :size="14" aria-hidden="true" />
        <span><slot>{{ message }}</slot></span>
        <div v-if="$slots.actions" class="vnext-inline-notice__actions"><slot name="actions" /></div>
        <VNextIconButton v-if="dismissible" class="vnext-inline-notice__dismiss" label="关闭提示" @click="$emit('dismiss')"><X aria-hidden="true" /></VNextIconButton>
    </div>
</template>

<script setup lang="ts">
import { CircleAlert, CircleCheck, Info, TriangleAlert, X } from 'lucide-vue-next'
import VNextIconButton from './VNextIconButton.vue'

withDefaults(defineProps<{
    tone?: 'info' | 'success' | 'warning' | 'error'
    message?: string
    dismissible?: boolean
    compact?: boolean
}>(), {
    tone: 'info',
    message: '',
    dismissible: false,
    compact: false,
})

defineEmits<{ dismiss: [] }>()
</script>

<style scoped>
.vnext-inline-notice {
    box-sizing: border-box;
    min-height: var(--app-control-default);
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 6px 8px 6px 10px;
    border: 1px solid var(--app-border-subtle);
    border-radius: var(--app-radius-sm);
    background: var(--app-bg-raised);
    color: var(--app-text-secondary);
    font-size: var(--app-font-caption);
    line-height: var(--app-line-height-compact);
}
.vnext-inline-notice.compact { min-height: var(--app-control-compact); padding-block: 4px; }
.vnext-inline-notice > svg { flex: 0 0 auto; color: var(--app-color-info); }
.vnext-inline-notice.is-success > svg { color: var(--app-color-success); }
.vnext-inline-notice.is-warning > svg { color: var(--app-color-warning); }
.vnext-inline-notice.is-error > svg { color: var(--app-color-danger); }
.vnext-inline-notice > span { min-width: 0; flex: 1; overflow-wrap: anywhere; }
.vnext-inline-notice__actions { display: flex; align-items: center; gap: 5px; }
.vnext-inline-notice__actions :deep(button) {
    min-width: 26px;
    min-height: 26px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0 7px;
    border: 0;
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
}
.vnext-inline-notice__actions :deep(button:hover) { background: var(--app-bg-hover); color: var(--app-text-primary); }
</style>
