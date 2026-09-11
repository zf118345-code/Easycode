<template>
    <header class="vnext-desktop-titlebar" @pointerdown.left="beginDrag">
        <div class="vnext-desktop-titlebar__identity"><slot /></div>
        <div class="vnext-desktop-titlebar__end">
            <div class="vnext-desktop-titlebar__meta"><slot name="meta" /></div>
            <div v-if="nativeWindow" class="vnext-desktop-titlebar__controls" @pointerdown.stop>
                <button type="button" aria-label="最小化窗口" title="最小化" @click="sendNativeWindowCommand('minimize')"><Minus /></button>
                <button type="button" aria-label="最大化或还原窗口" title="最大化/还原" @click="sendNativeWindowCommand('maximize')"><Maximize2 /></button>
                <button type="button" class="close" aria-label="关闭窗口" title="关闭" @click="requestClose"><X /></button>
            </div>
        </div>
    </header>
</template>

<script setup lang="ts">
import { Maximize2, Minus, X } from 'lucide-vue-next'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { nativeWindowAvailable, nativeWindowBridge, sendNativeWindowCommand } from '../../nativeWindowBridge'

const nativeWindow = ref(false)
const props = withDefaults(defineProps<{ managedClose?: boolean }>(), { managedClose: false })
const emit = defineEmits<{ 'request-close': [] }>()

function updateAvailability() { nativeWindow.value = nativeWindowAvailable() }
function requestClose() {
    if (props.managedClose) emit('request-close')
    else void sendNativeWindowCommand('close')
}
function beginDrag(event: PointerEvent) {
    if (event.button === 0 && nativeWindow.value) void sendNativeWindowCommand('drag')
}
function handleNativeMessage(event: MessageEvent) {
    if (event.data?.event === 'desktop-window-close-requested') {
        if (props.managedClose) emit('request-close')
        else void sendNativeWindowCommand('close-confirmed')
        return
    }
    if (event.data?.event === 'desktop-shell-ready' || event.data?.event === 'desktop-window-state') updateAvailability()
}

onMounted(() => {
    window.addEventListener('pywebviewready', updateAvailability)
    nativeWindowBridge()?.addEventListener?.('message', handleNativeMessage)
    updateAvailability()
})
onBeforeUnmount(() => {
    window.removeEventListener('pywebviewready', updateAvailability)
    nativeWindowBridge()?.removeEventListener?.('message', handleNativeMessage)
})
</script>

<style scoped>
.vnext-desktop-titlebar { min-width: 0; height: var(--app-height-app-header); display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-left: 14px; border-bottom: 1px solid var(--app-border-subtle); background: var(--app-bg-chrome); color: var(--app-text-regular); user-select: none; }
.vnext-desktop-titlebar__identity, .vnext-desktop-titlebar__end, .vnext-desktop-titlebar__meta { min-width: 0; display: flex; align-items: center; }
.vnext-desktop-titlebar__identity { flex: 1; gap: 8px; }.vnext-desktop-titlebar__end { flex: 0 0 auto; gap: 12px; }.vnext-desktop-titlebar__meta { color: var(--app-text-secondary); }
.vnext-desktop-titlebar__identity :deep(> svg) { color: var(--app-color-primary); }.vnext-desktop-titlebar__identity :deep(strong) { color: var(--app-text-primary); font-size: var(--app-font-body); }.vnext-desktop-titlebar__meta :deep(span) { font-size: var(--app-font-caption); }
.vnext-desktop-titlebar__controls { align-self: stretch; display: flex; align-items: center; gap: 2px; padding: 0 6px 0 0; }
.vnext-desktop-titlebar__controls button { width: 34px; height: 28px; display: grid; place-items: center; padding: 0; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-secondary); cursor: pointer; }
.vnext-desktop-titlebar__controls button:hover { background: var(--app-bg-hover); color: var(--app-text-primary); }.vnext-desktop-titlebar__controls button:active { background: var(--app-bg-active); }.vnext-desktop-titlebar__controls button.close:hover { background: var(--app-color-danger); color: var(--app-color-on-primary); }
.vnext-desktop-titlebar__controls button:focus-visible { outline: 0; box-shadow: inset var(--focus-ring); }.vnext-desktop-titlebar__controls svg { width: 14px; height: 14px; display: block; stroke-width: 2; }
</style>
