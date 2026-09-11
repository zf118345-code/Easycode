import { nextTick, onBeforeUnmount, watch, type Ref, type WatchSource } from 'vue'

const FOCUSABLE_SELECTOR = [
    'button:not([disabled])',
    'a[href]',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
].join(',')

/** Keeps keyboard focus inside a rendered modal without taking ownership of its state. */
export function trapDialogFocus(event: KeyboardEvent) {
    if (event.key !== 'Tab') return
    const dialog = event.currentTarget as HTMLElement
    const focusable = [...dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)]
        .filter(element => !element.hidden && element.getAttribute('aria-hidden') !== 'true')
    if (!focusable.length) { event.preventDefault(); dialog.focus(); return }
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
}

/** Owns initial focus and restores the trigger when an in-app modal closes. */
export function useDialogFocusReturn(isOpen: WatchSource<boolean>, dialogElement: Ref<HTMLElement | null>) {
    let returnFocus: HTMLElement | null = null

    watch(isOpen, async (open) => {
        if (open) {
            returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
            await nextTick()
            const dialog = dialogElement.value
            const initial = dialog?.querySelector<HTMLElement>('[data-dialog-initial-focus]')
                || dialog?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)
                || dialog
            initial?.focus()
            return
        }
        if (returnFocus?.isConnected) returnFocus.focus()
        returnFocus = null
    }, { immediate: true })

    onBeforeUnmount(() => {
        if (returnFocus?.isConnected) returnFocus.focus()
    })
}
