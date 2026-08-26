const CHANNEL_NAME = 'easycode-resource-mutations'
const STORAGE_KEY = 'easycode-resource-mutation'
const LOCAL_EVENT = 'easycode-resource-mutation'

export function publishResourceMutation(payload) {
    const message = {
        ...payload,
        eventId: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
        timestamp: Date.now()
    }
    window.dispatchEvent(new CustomEvent(LOCAL_EVENT, { detail: message }))
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(message))
    } catch {
        /* storage may be disabled in an embedded host */
    }
    if (typeof BroadcastChannel !== 'undefined') {
        const channel = new BroadcastChannel(CHANNEL_NAME)
        channel.postMessage(message)
        channel.close()
    }
}

export function subscribeResourceMutations(callback) {
    const seen = new Set()
    const deliver = (message) => {
        if (!message || (message.eventId && seen.has(message.eventId))) return
        if (message.eventId) {
            seen.add(message.eventId)
            setTimeout(() => seen.delete(message.eventId), 5000)
        }
        callback(message)
    }
    const onLocal = (event) => deliver(event.detail)
    const onStorage = (event) => {
        if (event.key !== STORAGE_KEY || !event.newValue) return
        try { deliver(JSON.parse(event.newValue)) } catch { /* ignore malformed events */ }
    }
    window.addEventListener(LOCAL_EVENT, onLocal)
    window.addEventListener('storage', onStorage)

    let channel = null
    if (typeof BroadcastChannel !== 'undefined') {
        channel = new BroadcastChannel(CHANNEL_NAME)
        channel.onmessage = (event) => deliver(event.data)
    }
    return () => {
        window.removeEventListener(LOCAL_EVENT, onLocal)
        window.removeEventListener('storage', onStorage)
        channel?.close()
    }
}
