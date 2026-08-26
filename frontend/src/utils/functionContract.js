const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/

const escapeRegExp = value => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

export function formatScopedReference(scope, name) {
    const cleanScope = String(scope || '').replace(/^\$/, '').replace(/[.{]$/, '')
    const cleanName = String(name || '').trim()
    if (!cleanScope || !cleanName) return ''
    return IDENTIFIER.test(cleanName) ? `$${cleanScope}.${cleanName}` : `$${cleanScope}{${cleanName}}`
}

export function rewriteScopedReferences(value, scope, previousName, nextName) {
    if (typeof value === 'string') {
        const replacement = formatScopedReference(scope, nextName)
        const escaped = escapeRegExp(previousName)
        return value
            .replace(new RegExp(`\\$${scope}\\{${escaped}\\}`, 'g'), replacement)
            .replace(new RegExp(`\\$${scope}\\.${escaped}(?![A-Za-z0-9_])`, 'g'), replacement)
    }
    if (Array.isArray(value)) return value.map(item => rewriteScopedReferences(item, scope, previousName, nextName))
    if (value && typeof value === 'object') {
        return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, rewriteScopedReferences(item, scope, previousName, nextName)]))
    }
    return value
}

export function containsScopedReference(value, scope, name) {
    if (typeof value === 'string') return rewriteScopedReferences(value, scope, name, '__easycode_probe__') !== value
    if (Array.isArray(value)) return value.some(item => containsScopedReference(item, scope, name))
    if (value && typeof value === 'object') return Object.values(value).some(item => containsScopedReference(item, scope, name))
    return false
}
