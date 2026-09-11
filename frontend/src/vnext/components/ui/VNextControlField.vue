<template>
    <div class="vnext-control-field" :class="{ 'is-disabled': disabled, 'has-error': Boolean(error), 'is-stacked': stacked }" role="group" :aria-labelledby="titleId">
        <div class="vnext-control-field__heading">
            <span class="vnext-control-field__title">
                <span :id="titleId" :title="label">{{ label }}</span>
                <span v-if="required" class="vnext-control-field__required" aria-label="必填">*</span>
                <VNextIconButton v-if="helpAvailable" class="expression-help-trigger" role="field" size="compact" :label="`${label}的填写帮助`" :disabled="disabled" :pressed="helpOpen" @click="emit('toggleHelp')"><CircleHelp /></VNextIconButton>
            </span>
            <div v-if="$slots.actions" class="vnext-control-field__actions"><slot name="actions" /></div>
        </div>
        <div class="vnext-control-field__control"><slot /></div>
        <p v-if="helpOpen && helpText" :id="helpId" class="vnext-control-field__help parameter-help" role="note">{{ helpText }}</p>
        <p v-if="error" :id="errorId" class="vnext-control-field__error parameter-error" role="alert">{{ error }}</p>
    </div>
</template>

<script setup lang="ts">
import { CircleHelp } from 'lucide-vue-next'
import VNextIconButton from './VNextIconButton.vue'

withDefaults(defineProps<{
    label: string
    titleId: string
    helpId?: string
    errorId?: string
    required?: boolean
    disabled?: boolean
    stacked?: boolean
    helpText?: string
    helpAvailable?: boolean
    helpOpen?: boolean
    error?: string
}>(), { helpId: '', errorId: '', required: false, disabled: false, stacked: false, helpText: '', helpAvailable: false, helpOpen: false, error: '' })
const emit = defineEmits<{ toggleHelp: [] }>()
</script>

<style scoped>
.vnext-control-field { container-type: inline-size; min-width: 0; display: grid; grid-template-columns: minmax(76px, 96px) minmax(0, 1fr); align-items: center; column-gap: var(--app-spacing-sm); row-gap: var(--app-form-label-control-gap); }
.vnext-control-field__heading { min-width: 0; min-height: 18px; display: flex; align-items: center; justify-content: space-between; gap: var(--app-spacing-sm); }
.vnext-control-field__title { min-width: 0; display: inline-flex; align-items: center; gap: 4px; color: var(--app-text-primary); font-size: var(--app-font-interface); font-weight: 550; line-height: var(--app-line-height-compact); }
.vnext-control-field__title > span:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vnext-control-field__required { color: var(--app-color-danger); }
.vnext-control-field__actions { display: flex; align-items: center; gap: var(--app-spacing-xs); }
.vnext-control-field__control { min-width: 0; grid-column: 2; }
.vnext-control-field__help, .vnext-control-field__error { margin: 0; font-size: var(--app-font-interface); line-height: var(--app-line-height-regular); }
.vnext-control-field__help, .vnext-control-field__error { grid-column: 2; }
.vnext-control-field__help { color: var(--app-text-secondary); }
.vnext-control-field__error { color: var(--app-color-danger); }
.vnext-control-field.is-disabled { opacity: .72; }
.vnext-control-field.is-stacked { display: block; }
.vnext-control-field.is-stacked .vnext-control-field__heading { margin-bottom: var(--app-form-label-control-gap); }
.vnext-control-field.is-stacked .vnext-control-field__help, .vnext-control-field.is-stacked .vnext-control-field__error { margin-top: var(--app-form-feedback-gap); }
@container (max-width: 220px) {
    .vnext-control-field__heading, .vnext-control-field__control, .vnext-control-field__help, .vnext-control-field__error { grid-column: 1 / -1; }
}
</style>
