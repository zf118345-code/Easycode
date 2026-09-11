function genericInner(typeId: string, prefix: string): string | null {
    return typeId.startsWith(`${prefix}<`) && typeId.endsWith('>')
        ? typeId.slice(prefix.length + 1, -1)
        : null
}

function mapParts(typeId: string): [string, string] | null {
    const inner = genericInner(typeId, 'map')
    if (inner === null) return null
    let depth = 0
    for (let index = 0; index < inner.length; index += 1) {
        if (inner[index] === '<') depth += 1
        else if (inner[index] === '>') depth -= 1
        else if (inner[index] === ',' && depth === 0) {
            const keyType = inner.slice(0, index).trim()
            const itemType = inner.slice(index + 1).trim()
            return keyType && itemType ? [keyType, itemType] : null
        }
    }
    return null
}

/**
 * Browser mirror of core.vnext.program_validation.types_compatible.
 *
 * This function only controls which references the editor offers. The backend
 * remains authoritative and validates the selected value again before saving
 * or running a ProgramDocument.
 */
export function isProgramTypeCompatible(actual: string, expected: string): boolean {
    if (expected === 'any' || actual === expected) return true

    if (expected === 'message_value') {
        if (['null', 'bool', 'int64', 'float64', 'string', 'json', 'json_value', 'message_value'].includes(actual)) {
            return true
        }
        const listItem = genericInner(actual, 'list')
        if (listItem !== null) return isProgramTypeCompatible(listItem, 'message_value')
        const mapTypes = mapParts(actual)
        return mapTypes !== null
            && mapTypes[0] === 'string'
            && isProgramTypeCompatible(mapTypes[1], 'message_value')
    }

    if (expected.startsWith('enum<') && actual === 'string') return true
    if (expected === 'percentage' && ['int64', 'float64'].includes(actual)) return true
    if (['relative_path', 'url', 'timezone'].includes(expected) && actual === 'string') return true
    if (expected.startsWith('optional<')) {
        return actual === 'null' || isProgramTypeCompatible(actual, expected.slice(9, -1))
    }
    if (expected === 'asset_ref' && actual.startsWith('asset_ref<')) return true
    return expected === 'float64' && actual === 'int64'
}
