/**
 * Small Player-only compatibility layer for the oldest supported Android
 * System WebView. Program/Profile values are JSON data, so the structured
 * clone fallback deliberately does not pretend to clone browser resources.
 */

const runtime = window as typeof window & {
    globalThis?: typeof globalThis
    structuredClone?: <T>(value: T) => T
}

if (typeof runtime.globalThis === 'undefined') {
    Object.defineProperty(runtime, 'globalThis', {
        configurable: true,
        value: runtime,
        writable: true,
    })
}

if (typeof Object.fromEntries !== 'function') {
    Object.fromEntries = function fromEntries(entries: Iterable<readonly [PropertyKey, unknown]>) {
        const result: Record<PropertyKey, unknown> = {}
        for (const [key, value] of entries) result[key] = value
        return result
    }
}

if (typeof Array.prototype.flatMap !== 'function') {
    Object.defineProperty(Array.prototype, 'flatMap', {
        configurable: true,
        writable: true,
        value(callback: (value: unknown, index: number, array: unknown[]) => unknown, thisArg?: unknown) {
            return Array.prototype.concat.apply([], this.map(callback, thisArg))
        },
    })
}

if (typeof Promise.allSettled !== 'function') {
    Promise.allSettled = function allSettled<T>(values: Iterable<T | PromiseLike<T>>) {
        return Promise.all(Array.from(values, value => Promise.resolve(value).then(
            resolved => ({ status: 'fulfilled' as const, value: resolved }),
            reason => ({ status: 'rejected' as const, reason }),
        )))
    }
}

if (typeof runtime.structuredClone !== 'function') {
    runtime.structuredClone = function jsonStructuredClone<T>(value: T): T {
        if (value === undefined || value === null) return value
        return JSON.parse(JSON.stringify(value)) as T
    }
}
