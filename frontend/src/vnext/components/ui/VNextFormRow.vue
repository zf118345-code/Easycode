<template>
    <div class="vnext-form-row app-form-row" :class="{ 'is-stacked': stacked, 'has-error': Boolean(error) }">
        <div class="vnext-form-row__label">
            <label v-if="label" :for="forId">{{ label }}<span v-if="required" aria-hidden="true"> *</span></label>
            <slot v-else name="label" />
            <slot name="label-actions" />
        </div>
        <div class="vnext-form-row__body">
            <div class="vnext-form-row__control"><slot /></div>
            <div v-if="$slots.actions" class="vnext-form-row__actions"><slot name="actions" /></div>
            <p v-if="error" class="vnext-form-row__feedback is-error" role="alert">{{ error }}</p>
            <p v-else-if="help || $slots.help" class="vnext-form-row__feedback"><slot name="help">{{ help }}</slot></p>
        </div>
    </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
    label?: string
    forId?: string
    help?: string
    error?: string
    required?: boolean
    stacked?: boolean
}>(), { label: '', forId: '', help: '', error: '', required: false, stacked: false })
</script>

<style scoped>
.vnext-form-row { min-width: 0; display: grid; grid-template-columns: minmax(76px, 96px) minmax(0, 1fr); align-items: start; gap: var(--app-form-label-control-gap) 10px; }
.vnext-form-row__label { min-width: 0; min-height: var(--app-control-default); display: flex; align-items: center; gap: 5px; color: var(--app-text-regular); font-size: var(--app-font-interface); font-weight: 550; line-height: var(--app-line-height-compact); }
.vnext-form-row__label label { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vnext-form-row__label span { color: var(--app-color-danger); }
.vnext-form-row__body { min-width: 0; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--app-form-feedback-gap) 6px; }
.vnext-form-row__control { min-width: 0; }
.vnext-form-row__actions { min-width: 0; display: flex; align-items: center; gap: var(--app-spacing-xs); }
.vnext-form-row__feedback { grid-column: 1 / -1; margin: 0; color: var(--app-text-secondary); font-size: var(--app-font-caption); line-height: var(--app-line-height-compact); }
.vnext-form-row__feedback.is-error { color: var(--app-color-danger); }
.vnext-form-row.is-stacked { grid-template-columns: minmax(0, 1fr); }
.vnext-form-row.is-stacked .vnext-form-row__label { min-height: auto; }
@container (max-width: 220px) { .vnext-form-row { grid-template-columns: minmax(0, 1fr); } .vnext-form-row__label { min-height: auto; } }
</style>
