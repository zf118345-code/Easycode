<template>
    <Teleport to="body">
        <div v-if="open" class="vnext-dialog-backdrop" @mousedown.self="requestBackdropClose">
            <section
                ref="dialogElement"
                class="vnext-dialog"
                :class="[`is-${size}`]"
                :role="alert ? 'alertdialog' : 'dialog'"
                aria-modal="true"
                :aria-labelledby="titleId"
                :aria-describedby="description ? descriptionId : undefined"
                tabindex="-1"
                @keydown="handleKeydown"
            >
                <header class="vnext-dialog__header">
                    <div class="vnext-dialog__heading">
                        <h2 :id="titleId"><slot name="title">{{ title }}</slot></h2>
                        <p v-if="description || $slots.description" :id="descriptionId"><slot name="description">{{ description }}</slot></p>
                    </div>
                    <VNextIconButton v-if="dismissible" label="关闭" @click="requestClose"><X aria-hidden="true" /></VNextIconButton>
                </header>
                <div class="vnext-dialog__body"><slot /></div>
                <footer v-if="$slots.footer" class="vnext-dialog__footer"><slot name="footer" /></footer>
            </section>
        </div>
    </Teleport>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { X } from 'lucide-vue-next'
import { trapDialogFocus, useDialogFocusReturn } from '../../dialogFocus'
import VNextIconButton from './VNextIconButton.vue'

const props = withDefaults(defineProps<{
    open: boolean
    title: string
    description?: string
    size?: 'small' | 'medium' | 'large'
    alert?: boolean
    dismissible?: boolean
    dismissOnBackdrop?: boolean
}>(), { description: '', size: 'medium', alert: false, dismissible: true, dismissOnBackdrop: true })
const emit = defineEmits<{ close: [] }>()
const dialogElement = ref<HTMLElement | null>(null)
const identity = Math.random().toString(36).slice(2)
const titleId = `vnext-dialog-title-${identity}`
const descriptionId = `vnext-dialog-description-${identity}`
useDialogFocusReturn(computed(() => props.open), dialogElement)

function requestClose() { emit('close') }
function requestBackdropClose() { if (props.dismissOnBackdrop) requestClose() }
function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && props.dismissible) { event.preventDefault(); requestClose(); return }
    trapDialogFocus(event)
}
</script>

<style scoped>
.vnext-dialog-backdrop { position: fixed; inset: 0; z-index: var(--app-z-modal); display: grid; place-items: center; padding: 20px; background: color-mix(in srgb, var(--app-bg-base) 76%, transparent); }
.vnext-dialog { width: min(620px, calc(100vw - 32px)); max-height: min(820px, calc(100vh - 32px)); display: grid; grid-template-rows: auto minmax(0, 1fr) auto; overflow: hidden; border: 1px solid var(--app-overlay-border); border-radius: var(--app-radius-lg); background: var(--app-overlay-bg); box-shadow: var(--app-shadow-lg); color: var(--app-text-primary); }
.vnext-dialog.is-small { width: min(420px, calc(100vw - 32px)); }
.vnext-dialog.is-large { width: min(860px, calc(100vw - 32px)); }
.vnext-dialog__header { min-height: 58px; display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 14px 18px; border-bottom: 1px solid var(--app-overlay-separator); }
.vnext-dialog__heading { min-width: 0; }
.vnext-dialog__heading h2 { margin: 0; color: var(--app-text-primary); font-size: var(--app-font-heading); font-weight: 650; line-height: var(--app-line-height-compact); }
.vnext-dialog__heading p { max-width: 72ch; margin: 4px 0 0; color: var(--app-text-secondary); font-size: var(--app-font-interface); line-height: var(--app-line-height-body); }
.vnext-dialog__body { min-height: 0; overflow: auto; padding: 16px 18px; }
.vnext-dialog__footer { min-height: 58px; display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding: 12px 18px; border-top: 1px solid var(--app-overlay-separator); background: var(--app-bg-input); }
@media (max-width: 480px) { .vnext-dialog-backdrop { align-items: end; padding: 12px; } .vnext-dialog { width: 100%; max-height: calc(100vh - 24px); } }
</style>
