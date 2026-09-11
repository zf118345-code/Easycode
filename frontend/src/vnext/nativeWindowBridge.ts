export type NativeWindowCommand =
    | 'minimize'
    | 'maximize'
    | 'close'
    | 'close-confirmed'
    | 'close-cancelled'
    | 'drag'

export function nativeWindowBridge() {
    return (window as any).chrome?.webview
}

export function nativeWindowAvailable(): boolean {
    return Boolean(nativeWindowBridge()?.postMessage || (window as any).pywebview?.api)
}

export async function sendNativeWindowCommand(command: NativeWindowCommand): Promise<boolean> {
    const webview = nativeWindowBridge()
    if (webview?.postMessage) {
        webview.postMessage({ event: 'window-command', version: 1, command })
        return true
    }
    const api = (window as any).pywebview?.api
    if (!api) return false
    if (command === 'close-cancelled') return true
    const method = command === 'maximize'
        ? 'toggle_maximize'
        : command === 'close-confirmed'
            ? 'close'
            : command
    await api?.[method]?.()
    return true
}
