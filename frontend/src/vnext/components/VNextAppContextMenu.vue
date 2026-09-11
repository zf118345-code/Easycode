<template>
    <div
        v-if="open"
        ref="menuElement"
        class="app-context-menu"
        role="menu"
        aria-label="文本编辑菜单"
        :style="{ left: `${position.x}px`, top: `${position.y}px` }"
        @contextmenu.prevent
        @pointerdown.stop
        @keydown.esc.stop="close(false)"
    >
        <button type="button" role="menuitem" :disabled="!hasSelection" @click="copySelection(false)">复制</button>
        <button type="button" role="menuitem" :disabled="!hasSelection || readOnly" @click="copySelection(true)">剪切</button>
        <button type="button" role="menuitem" :disabled="readOnly" @click="paste">粘贴</button>
        <span aria-hidden="true"></span>
        <button type="button" role="menuitem" @click="selectAll">全选</button>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

type EditableElement = HTMLInputElement | HTMLTextAreaElement | HTMLElement

const open = ref(false)
const target = ref<EditableElement | null>(null)
const position = reactive({ x: 0, y: 0 })
const menuElement = ref<HTMLElement | null>(null)

const textControl = computed(() => target.value instanceof HTMLInputElement || target.value instanceof HTMLTextAreaElement)
const readOnly = computed(() => textControl.value
    ? Boolean((target.value as HTMLInputElement | HTMLTextAreaElement).readOnly || (target.value as HTMLInputElement | HTMLTextAreaElement).disabled)
    : target.value?.getAttribute('contenteditable') === 'false')
const selectedText = computed(() => {
    const element = target.value
    if (!element) return ''
    if (textControl.value) {
        const control = element as HTMLInputElement | HTMLTextAreaElement
        return control.value.slice(control.selectionStart || 0, control.selectionEnd || 0)
    }
    return window.getSelection()?.toString() || ''
})
const hasSelection = computed(() => selectedText.value.length > 0)

function editableFrom(node: EventTarget | null): EditableElement | null {
    if (!(node instanceof HTMLElement)) return null
    if (node instanceof HTMLTextAreaElement) return node
    if (node instanceof HTMLInputElement && !['button', 'checkbox', 'color', 'file', 'hidden', 'image', 'radio', 'range', 'reset', 'submit'].includes(node.type)) return node
    return node.closest<HTMLElement>('[contenteditable="true"]')
}

function openFor(event: MouseEvent): void {
    if (event.defaultPrevented) return
    event.preventDefault()
    const editable = editableFrom(event.target)
    if (!editable) { close(); return }
    target.value = editable
    position.x = Math.min(event.clientX, Math.max(8, window.innerWidth - 150))
    position.y = Math.min(event.clientY, Math.max(8, window.innerHeight - 190))
    open.value = true
    void nextTick(() => menuElement.value?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus())
}

function dispatchInput(element: EditableElement): void {
    element.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText' }))
}

async function writeClipboard(text: string): Promise<void> {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text)
    else document.execCommand('copy')
}

async function copySelection(remove: boolean): Promise<void> {
    const element = target.value
    const text = selectedText.value
    if (!element || !text) return
    await writeClipboard(text)
    if (remove && !readOnly.value) {
        if (textControl.value) {
            const control = element as HTMLInputElement | HTMLTextAreaElement
            control.setRangeText('', control.selectionStart || 0, control.selectionEnd || 0, 'end')
            dispatchInput(control)
        } else document.execCommand('delete')
    }
    close(true)
}

async function paste(): Promise<void> {
    const element = target.value
    if (!element || readOnly.value) return
    let text = ''
    try {
        text = navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''
    } catch {
        close(true)
        return
    }
    if (textControl.value) {
        const control = element as HTMLInputElement | HTMLTextAreaElement
        control.setRangeText(text, control.selectionStart || 0, control.selectionEnd || 0, 'end')
        dispatchInput(control)
    } else document.execCommand('insertText', false, text)
    close(true)
}

function selectAll(): void {
    const element = target.value
    if (!element) return
    if (textControl.value) (element as HTMLInputElement | HTMLTextAreaElement).select()
    else {
        const selection = window.getSelection()
        const range = document.createRange()
        range.selectNodeContents(element)
        selection?.removeAllRanges()
        selection?.addRange(range)
    }
    close(true)
}

function close(restoreFocus = false): void {
    const element = target.value
    open.value = false
    target.value = null
    if (restoreFocus) void nextTick(() => element?.focus())
}

function handlePointerDown(event: PointerEvent): void {
    if (open.value && !menuElement.value?.contains(event.target as Node)) close()
}

function closeFromWindowEvent(): void {
    close()
}

onMounted(() => {
    document.addEventListener('contextmenu', openFor)
    document.addEventListener('pointerdown', handlePointerDown, true)
    window.addEventListener('blur', closeFromWindowEvent)
    window.addEventListener('resize', closeFromWindowEvent)
    window.addEventListener('scroll', closeFromWindowEvent, true)
})
onBeforeUnmount(() => {
    document.removeEventListener('contextmenu', openFor)
    document.removeEventListener('pointerdown', handlePointerDown, true)
    window.removeEventListener('blur', closeFromWindowEvent)
    window.removeEventListener('resize', closeFromWindowEvent)
    window.removeEventListener('scroll', closeFromWindowEvent, true)
})
</script>

<style scoped>
.app-context-menu{position:fixed;z-index:5000;width:142px;padding:5px;border:1px solid var(--app-overlay-border);border-radius:var(--app-radius-md);background:var(--app-bg-overlay);box-shadow:var(--app-shadow-lg)}
.app-context-menu button{width:100%;height: var(--app-control-compact);padding:0 9px;border:0;border-radius:var(--app-radius-sm);background:transparent;color:var(--app-text-regular);font:inherit;font-size:var(--app-font-xs);text-align:left;cursor:pointer}
.app-context-menu button:hover:not(:disabled),.app-context-menu button:focus-visible{outline:0;background:var(--app-bg-hover);color:var(--app-text-primary)}
.app-context-menu button:disabled{opacity:.38;cursor:default}
.app-context-menu>span{display:block;height:1px;margin:4px;background:var(--app-border-subtle)}
</style>
