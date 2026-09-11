import type {
    AvailableProgramValue,
    ProgramLiteral,
    ProgramValueDraft,
    ProgramValueNode,
} from './types'
import { isProgramTypeCompatible } from './typeCompatibility'

export function newProgramValueId(prefix = 'value'): string {
    const suffix = globalThis.crypto?.randomUUID?.().replaceAll('-', '')
        || `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`
    return `${prefix}_${suffix}`
}

function genericInner(typeId: string, prefix: string): string | null {
    return typeId.startsWith(`${prefix}<`) && typeId.endsWith('>')
        ? typeId.slice(prefix.length + 1, -1)
        : null
}

function genericParts(typeId: string, prefix: string): string[] | null {
    const inner = genericInner(typeId, prefix)
    if (inner === null) return null
    const result: string[] = []
    let depth = 0
    let start = 0
    for (let index = 0; index < inner.length; index += 1) {
        if (inner[index] === '<') depth += 1
        else if (inner[index] === '>') depth -= 1
        else if (inner[index] === ',' && depth === 0) {
            result.push(inner.slice(start, index).trim())
            start = index + 1
        }
    }
    result.push(inner.slice(start).trim())
    return result.every(Boolean) ? result : null
}

export function splitMapType(typeId: string): [string, string] {
    const inner = genericInner(typeId, 'map') || 'string,string'
    let depth = 0
    for (let index = 0; index < inner.length; index += 1) {
        if (inner[index] === '<') depth += 1
        else if (inner[index] === '>') depth -= 1
        else if (inner[index] === ',' && depth === 0) {
            return [inner.slice(0, index).trim(), inner.slice(index + 1).trim()]
        }
    }
    return ['string', 'string']
}

function literal(valueId: string, valueType: string, value: ProgramLiteral): ProgramValueNode {
    return { value_id: valueId, kind: 'literal', value_type: valueType, value }
}

export function canMaterializeProgramValue(typeId: string): boolean {
    if (genericParts(typeId, 'list_selector')?.length === 2) return true
    if (genericParts(typeId, 'map_selector')?.length === 3) return true
    if (typeId.startsWith('optional<') && typeId.endsWith('>')) return true
    return ['string', 'relative_path', 'url', 'timezone'].includes(typeId)
        || typeId.startsWith('enum<')
        || ['int64', 'float64', 'percentage', 'bool', 'duration', 'date', 'datetime', 'time', 'point', 'rect', 'path', 'gesture_path', 'json', 'json_value'].includes(typeId)
        || typeId.startsWith('list<')
        || typeId.startsWith('map<')
}

export function defaultProgramValue(typeId: string, valueId = newProgramValueId()): ProgramValueNode {
    const listSelector = genericParts(typeId, 'list_selector')
    if (listSelector?.length === 2) {
        const [itemType, resultType] = listSelector
        return {
            value_id: valueId, kind: 'selector', value_type: typeId, result_type: resultType,
            bindings: [
                { symbol_id: newProgramValueId('symbol_item'), role: 'item', display_name: '当前项', value_type: itemType },
                { symbol_id: newProgramValueId('symbol_index'), role: 'index', display_name: '当前序号', value_type: 'int64' },
            ],
            expression: defaultProgramValue(resultType, newProgramValueId('value_selector_result')),
        }
    }
    const mapSelector = genericParts(typeId, 'map_selector')
    if (mapSelector?.length === 3) {
        const [keyType, entryType, resultType] = mapSelector
        return {
            value_id: valueId, kind: 'selector', value_type: typeId, result_type: resultType,
            bindings: [
                { symbol_id: newProgramValueId('symbol_key'), role: 'key', display_name: '当前键', value_type: keyType },
                { symbol_id: newProgramValueId('symbol_value'), role: 'value', display_name: '当前值', value_type: entryType },
            ],
            expression: defaultProgramValue(resultType, newProgramValueId('value_selector_result')),
        }
    }
    if (typeId.startsWith('optional<') && typeId.endsWith('>')) return literal(valueId, typeId, null)
    if (['string', 'relative_path', 'url', 'timezone'].includes(typeId) || typeId.startsWith('enum<')) return literal(valueId, typeId, '')
    if (typeId === 'int64' || typeId === 'float64' || typeId === 'percentage') return literal(valueId, typeId, 0)
    if (typeId === 'bool') return literal(valueId, typeId, false)
    if (typeId === 'duration') return literal(valueId, typeId, { milliseconds: 1000 })
    const now = new Date()
    const localIso = new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString()
    if (typeId === 'date') return literal(valueId, typeId, localIso.slice(0, 10))
    if (typeId === 'datetime') return literal(valueId, typeId, localIso.slice(0, 19))
    if (typeId === 'time') return literal(valueId, typeId, localIso.slice(11, 19))
    if (typeId === 'point') return literal(valueId, typeId, [0, 0])
    if (typeId === 'rect') return literal(valueId, typeId, [0, 0, 0, 0])
    if (typeId === 'path' || typeId === 'gesture_path') return literal(valueId, typeId, [[0, 0], [1, 1]])
    const itemType = genericInner(typeId, 'list')
    if (itemType) return { value_id: valueId, kind: 'list', value_type: typeId, item_type: itemType, items: [] }
    if (typeId.startsWith('map<')) {
        const [keyType, entryType] = splitMapType(typeId)
        return {
            value_id: valueId,
            kind: 'map',
            value_type: typeId,
            key_type: keyType,
            entry_value_type: entryType,
            entries: [],
            duplicate_policy: 'error',
        }
    }
    if (typeId === 'json' || typeId === 'json_value') {
        return { value_id: valueId, kind: 'json', value_type: 'json_value', payload: {} }
    }
    return { value_id: valueId, kind: 'record', value_type: typeId, record_type: typeId, fields: {} }
}

export function cloneProgramValue<T extends ProgramValueNode>(value: T): T {
    return JSON.parse(JSON.stringify(value)) as T
}

export function compatibleProgramValues(values: AvailableProgramValue[], valueType: string): AvailableProgramValue[] {
    return values.filter((item) => isProgramTypeCompatible(item.value_type, valueType))
}

export function referenceProgramValue(value: AvailableProgramValue, valueId: string, valueType: string): ProgramValueNode {
    if (value.source === 'project') {
        return {
            value_id: valueId,
            kind: 'project_variable_ref',
            value_type: valueType,
            variable_id: value.id,
            display_name: value.display_name,
        }
    }
    return {
        value_id: valueId,
        kind: 'symbol_ref',
        value_type: valueType,
        symbol_id: value.id,
        display_name: value.display_name,
    }
}

export function isFocusedValueEditorSupported(value: ProgramValueNode, valueType = value.value_type): boolean {
    if (['list', 'map', 'record', 'json', 'computed', 'selector', 'member_access', 'compare', 'condition_group', 'not'].includes(value.kind)) {
        return true
    }
    return value.kind === 'unset' && (
        valueType.startsWith('list<') || valueType.startsWith('map<') || ['json', 'json_value'].includes(valueType)
    )
}

/**
 * Convert the transient editor tree into the existing update command shape. Stable IDs are kept
 * as non-domain transport hints; adapter.ts consumes them while labels and summaries stay UI-only.
 */
export function programValueToDraft(value: ProgramValueNode): ProgramValueDraft {
    const identity = { value_id: value.value_id }
    if (value.kind === 'unset') return { ...identity, kind: 'unset', value_type: value.value_type } as ProgramValueDraft
    if (value.kind === 'literal') return { ...identity, kind: 'literal', value_type: value.value_type, value: value.value } as ProgramValueDraft
    if (value.kind === 'symbol_ref') return { ...identity, kind: value.kind, value_type: value.value_type, symbol_id: value.symbol_id, display_name: value.display_name } as ProgramValueDraft
    if (value.kind === 'project_variable_ref') return { ...identity, kind: value.kind, value_type: value.value_type, variable_id: value.variable_id, display_name: value.display_name } as ProgramValueDraft
    if (value.kind === 'asset_ref') return { ...identity, kind: value.kind, value_type: value.value_type, asset_id: value.asset_id, asset_kind: value.asset_kind, display_name: value.display_name } as ProgramValueDraft
    if (value.kind === 'target_ref') return { ...identity, kind: value.kind, value_type: value.value_type, target_id: value.target_id, display_name: value.display_name } as ProgramValueDraft
    if (value.kind === 'entity_ref') return { ...identity, kind: value.kind, value_type: value.value_type, reference_id: value.reference_id, reference_type: value.reference_type, display_name: value.display_name } as ProgramValueDraft
    if (value.kind === 'member_access') return {
        ...identity, kind: value.kind, value_type: value.value_type, field_id: value.field_id,
        field_name: value.field_name, source: programValueToDraft(value.source),
    } as ProgramValueDraft
    if (value.kind === 'list') return {
        ...identity, kind: value.kind, value_type: value.value_type, item_type: value.item_type,
        items: value.items.map(programValueToDraft),
    } as ProgramValueDraft
    if (value.kind === 'map') return {
        ...identity, kind: value.kind, value_type: value.value_type, key_type: value.key_type,
        entry_value_type: value.entry_value_type, duplicate_policy: 'error',
        entries: value.entries.map((entry) => ({ key: programValueToDraft(entry.key), value: programValueToDraft(entry.value) })),
    } as ProgramValueDraft
    if (value.kind === 'record') return {
        ...identity, kind: value.kind, value_type: value.value_type, record_type: value.record_type,
        record_name: value.record_name, field_names: value.field_names,
        fields: Object.fromEntries(Object.entries(value.fields).map(([fieldId, child]) => [fieldId, programValueToDraft(child)])),
    } as ProgramValueDraft
    if (value.kind === 'json') return { ...identity, kind: value.kind, value_type: value.value_type, payload: value.payload } as ProgramValueDraft
    if (value.kind === 'computed') return {
        ...identity, kind: value.kind, value_type: value.value_type, operation_id: value.operation_id,
        operation_name: value.operation_name,
        operation_input_names: value.operation_input_names,
        inputs: Object.fromEntries(Object.entries(value.inputs).map(([inputId, child]) => [inputId, programValueToDraft(child)])),
    } as ProgramValueDraft
    if (value.kind === 'selector') return {
        ...identity, kind: value.kind, value_type: value.value_type,
        result_type: value.result_type, bindings: value.bindings,
        expression: programValueToDraft(value.expression),
    } as ProgramValueDraft
    if (value.kind === 'compare') return {
        ...identity, kind: value.kind, value_type: value.value_type, operator: value.operator,
        left: programValueToDraft(value.left), right: programValueToDraft(value.right),
    } as ProgramValueDraft
    if (value.kind === 'condition_group') return {
        ...identity, kind: value.kind, value_type: value.value_type, operator: value.operator,
        conditions: value.conditions.map(programValueToDraft),
    } as ProgramValueDraft
    return { ...identity, kind: 'not', value_type: value.value_type, condition: programValueToDraft(value.condition) } as ProgramValueDraft
}
