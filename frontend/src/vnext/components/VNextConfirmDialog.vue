<template>
    <Teleport to="body">
        <div v-if="open" class="decision-backdrop" @mousedown.self="requestBackdropCancel">
            <section
                ref="dialogElement"
                class="decision-dialog"
                role="alertdialog"
                aria-modal="true"
                :aria-labelledby="titleId"
                :aria-describedby="messageId"
                tabindex="-1"
                @keydown="handleKeydown"
            >
                <header>
                    <span class="decision-icon" :class="tone" aria-hidden="true">
                        <TriangleAlert v-if="tone === 'warning'" :size="16" />
                        <CircleHelp v-else :size="16" />
                    </span>
                    <div>
                        <h2 :id="titleId">{{ title }}</h2>
                        <p :id="messageId">{{ message }}</p>
                    </div>
                </header>
                <div v-if="$slots.default" class="decision-body">
                    <slot />
                </div>
                <footer>
                    <VNextButton ref="cancelButton" :disabled="busy" @click="requestCancel">
                        {{ cancelLabel }}
                    </VNextButton>
                    <VNextButton :tone="tone === 'warning' ? 'danger' : 'primary'" appearance="solid" :loading="busy" @click="emit('confirm')">
                        {{ confirmLabel }}
                    </VNextButton>
                </footer>
            </section>
        </div>
    </Teleport>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { CircleHelp, TriangleAlert } from 'lucide-vue-next'
import VNextButton from './ui/VNextButton.vue'

const props = withDefaults(defineProps<{
    open: boolean
    title: string
    message: string
    confirmLabel?: string
    cancelLabel?: string
    tone?: 'normal' | 'warning'
    busy?: boolean
    dismissOnBackdrop?: boolean
}>(), {
    confirmLabel: '确认',
    cancelLabel: '取消',
    tone: 'normal',
    busy: false,
    dismissOnBackdrop: true,
})
const emit = defineEmits<{ confirm: []; cancel: [] }>()
const dialogElement = ref<HTMLElement | null>(null)
const cancelButton = ref<InstanceType<typeof VNextButton> | null>(null)
const titleId = `vnext-decision-title-${Math.random().toString(36).slice(2)}`
const messageId = `vnext-decision-message-${Math.random().toString(36).slice(2)}`
let returnFocus: HTMLElement | null = null

function focusableElements() {
    return Array.from(dialogElement.value?.querySelectorAll<HTMLElement>('button:not(:disabled), [href], [tabindex]:not([tabindex="-1"])') || [])
}

function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
        event.preventDefault()
        requestCancel()
        return
    }
    if (event.key !== 'Tab') return
    const elements = focusableElements()
    if (!elements.length) return
    const first = elements[0]
    const last = elements[elements.length - 1]
    if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
    }
}

function requestCancel() {
    if (props.busy) return
    emit('cancel')
}

function requestBackdropCancel() {
    if (!props.dismissOnBackdrop) return
    requestCancel()
}

watch(() => props.open, async (open) => {
    if (open) {
        returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
        await nextTick()
        cancelButton.value?.focus()
    } else if (returnFocus) {
        returnFocus.focus()
        returnFocus = null
    }
}, { immediate: true })

onBeforeUnmount(() => returnFocus?.focus())
</script>

<style scoped>
.decision-backdrop{position:fixed;inset:0;z-index:1200;display:grid;place-items:center;padding:24px;background:color-mix(in srgb,var(--app-bg-base) 72%,transparent)}
.decision-dialog{width:min(420px,calc(100vw - 32px));overflow:hidden;border:1px solid var(--app-border-default);border-radius: var(--app-radius-lg);background:var(--app-bg-panel);box-shadow:0 18px 48px color-mix(in srgb,#000 44%,transparent);color:var(--app-text-primary)}
.decision-dialog header{display:flex;align-items:flex-start;gap:12px;padding:18px 18px 16px}
.decision-icon{display:grid;flex:0 0 30px;width:30px;height: var(--app-control-compact);place-items:center;border-radius: var(--app-radius-md);background:var(--app-bg-hover);color:var(--app-text-secondary)}
.decision-icon.warning{background:color-mix(in srgb,var(--app-color-warning) 12%,transparent);color:var(--app-color-warning)}
.decision-dialog h2{margin:1px 0 0;font-size: var(--app-font-page-title);font-weight:650;line-height:1.35}
.decision-dialog p{margin:7px 0 0;color:var(--app-text-secondary);font-size: var(--app-font-compact);line-height:1.65;overflow-wrap:anywhere}
.decision-body{padding:0 18px 16px;color:var(--app-text-regular);font-size: var(--app-font-caption);line-height:1.55}
.decision-dialog footer{display:flex;justify-content:flex-end;gap:8px;padding:12px 18px;border-top:1px solid var(--app-border-subtle);background:var(--app-bg-input)}
@media (max-width:480px){.decision-backdrop{align-items:end;padding:12px}.decision-dialog{width:100%;border-radius: var(--app-radius-lg)}.decision-dialog footer{display:grid;grid-template-columns:1fr 1fr}}
@media (prefers-reduced-motion:reduce){.decision-backdrop,.decision-dialog{scroll-behavior:auto}}
</style>
