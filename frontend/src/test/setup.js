import { config } from '@vue/test-utils'

// Unit tests mount feature components without main.js, so Element Plus is not
// globally registered there. Keep unexpected Vue warnings visible while
// suppressing only that known bootstrap difference.
config.global.config.warnHandler = (message, _instance, trace) => {
    const text = String(message || '')
    if (/^Failed to resolve component: el-/.test(text)) return
    if (text === 'Failed to resolve directive: loading') return
    console.warn(`[Vue warn]: ${text}${trace || ''}`)
}
