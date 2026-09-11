import type { ExecutionPlatformId, ParameterControlType, PlatformId } from '../types'
import type {
    AvailableProgramValue,
    ProgramParameterContract,
    ProgramValueDraft,
    ProgramValueNode,
    ProgramValueSource,
} from './types'
import { isProgramTypeCompatible } from './typeCompatibility'
import { colorRecordFields } from '../colorValue'

const TYPE_CONTROLS: Record<string, ParameterControlType> = {
    string: 'text',
    relative_path: 'text',
    url: 'text',
    timezone: 'text',
    int64: 'number',
    float64: 'number',
    bool: 'toggle',
    duration: 'duration',
    date: 'time',
    datetime: 'time',
    time: 'time',
    color: 'color',
    point: 'coordinate',
    rect: 'region',
    path: 'gesture-path',
    asset_ref: 'resource',
    control_ref: 'control-selector',
    list: 'list',
    map: 'key-value',
    record: 'key-value',
    json: 'key-value',
}

function normalizedType(typeId: string): string {
    if (typeId.startsWith('optional<') && typeId.endsWith('>')) return normalizedType(typeId.slice(9, -1))
    if (typeId.startsWith('list<')) return 'list'
    if (typeId.startsWith('map<')) return 'map'
    if (typeId.startsWith('asset_ref')) return 'asset_ref'
    if (typeId === 'gesture_path') return 'path'
    if (typeId === 'json_value') return 'json'
    return typeId
}

export function controlForParameter(parameter: ProgramParameterContract): ParameterControlType {
    if (parameter.constraints?.choices?.length) return 'select'
    return parameter.ui?.control || TYPE_CONTROLS[normalizedType(parameter.value_type)] || 'expression'
}

export function sourcesForParameter(parameter: ProgramParameterContract): ProgramValueSource[] {
    const sources: ProgramValueSource[] = parameter.allowed_sources?.length ? parameter.allowed_sources : ['fixed']
    return [...new Set(sources)]
}

export function sourceForValue(value: ProgramValueNode): ProgramValueSource {
    if (value.kind === 'symbol_ref' || value.kind === 'project_variable_ref') return 'reference'
    if (value.kind === 'computed' || value.kind === 'selector' || value.kind === 'member_access' || value.kind === 'compare'
        || value.kind === 'condition_group' || value.kind === 'not') return 'computed'
    return 'fixed'
}

export function valueModel(value: ProgramValueNode): unknown {
    if (value.kind === 'unset') return null
    if (value.kind === 'literal') return value.value
    if (value.kind === 'asset_ref') return value.asset_id
    if (value.kind === 'target_ref') return value.target_id
    if (value.kind === 'entity_ref') return value.reference_id
    if (value.kind === 'symbol_ref') return value.symbol_id
    if (value.kind === 'project_variable_ref') return value.variable_id
    if (value.kind === 'json') return value.payload
    if (value.kind === 'list') return value.items.map((item) => valueModel(item))
    if (value.kind === 'map') return Object.fromEntries(value.entries.map((entry) => [
        String(valueModel(entry.key) ?? ''),
        valueModel(entry.value),
    ]))
    if (value.kind === 'record') return Object.fromEntries(Object.entries(value.fields).map(([fieldId, child]) => [fieldId, valueModel(child)]))
    if (value.kind === 'computed') return value.summary || value.operation_name
    if (value.kind === 'selector') return value.summary || '逐项处理'
    return value.summary || null
}

function assetKind(valueType: string): string {
    const match = /^asset_ref<(.+)>$/.exec(valueType)
    return match?.[1] || 'image'
}

function draftFromPlainValue(value: unknown): ProgramValueDraft {
    if (value === null || value === undefined) return { kind: 'literal', value_type: 'json_value', value: null }
    if (typeof value === 'boolean' || typeof value === 'number' || typeof value === 'string') {
        return { kind: 'literal', value_type: 'json_value', value }
    }
    if (Array.isArray(value) || (typeof value === 'object' && value !== null)) {
        return { kind: 'json', value_type: 'json_value', payload: value as never }
    }
    return { kind: 'literal', value_type: 'json_value', value: String(value) }
}

function recordDraftFromPlainObject(valueType: string, modelValue: unknown): ProgramValueDraft {
    const entries = modelValue && typeof modelValue === 'object' && !Array.isArray(modelValue)
        ? Object.entries(modelValue as Record<string, unknown>)
        : []
    return {
        kind: 'record',
        value_type: valueType,
        record_type: '字典',
        fields: Object.fromEntries(entries.map(([fieldId, child]) => [fieldId, draftFromPlainValue(child)])),
    }
}

export function valueDraftFromModel(
    parameter: ProgramParameterContract,
    control: ParameterControlType,
    modelValue: unknown,
): ProgramValueDraft {
    const valueType = parameter.value_type
    if (control === 'color' || normalizedType(valueType) === 'color') {
        if (modelValue === null || modelValue === undefined || modelValue === '') {
            return { kind: 'unset', value_type: valueType }
        }
        return {
            kind: 'record',
            value_type: valueType,
            record_type: 'color',
            record_name: '颜色',
            field_names: {
                'color.field.red': '红',
                'color.field.green': '绿',
                'color.field.blue': '蓝',
                'color.field.alpha': '透明度',
            },
            fields: colorRecordFields(modelValue),
        }
    }
    if (control === 'control-selector' || normalizedType(valueType) === 'control_selector') {
        if (modelValue === null || modelValue === undefined || modelValue === '') {
            return { kind: 'unset', value_type: valueType }
        }
        if (typeof modelValue === 'object') {
            return recordDraftFromPlainObject(valueType, modelValue)
        }
        return {
            kind: 'record',
            value_type: valueType,
            record_type: '字典',
            fields: {
                selector: {
                    kind: 'literal',
                    value_type: 'json_value',
                    value: String(modelValue),
                },
            },
        }
    }
    if ((control === 'resource' || normalizedType(valueType) === 'asset_ref') && !modelValue) {
        return { kind: 'unset', value_type: valueType }
    }
    if (control === 'resource' || normalizedType(valueType) === 'asset_ref') {
        return { kind: 'asset_ref', value_type: valueType, asset_id: String(modelValue), asset_kind: assetKind(valueType) }
    }
    if (normalizedType(valueType) === 'target_ref') {
        if (!modelValue) return { kind: 'unset', value_type: valueType }
        return { kind: 'target_ref', value_type: valueType, target_id: String(modelValue) }
    }
    return { kind: 'literal', value_type: valueType, value: modelValue as never }
}

export function referenceDraft(
    value: AvailableProgramValue,
    targetType: string,
): ProgramValueDraft {
    if (value.source === 'project') {
        return {
            kind: 'project_variable_ref',
            value_type: targetType,
            variable_id: value.id,
            display_name: value.display_name,
        }
    }
    return {
        kind: 'symbol_ref',
        value_type: targetType,
        symbol_id: value.id,
        display_name: value.display_name,
    }
}

export function compatibleAvailableValues(
    values: AvailableProgramValue[],
    valueType: string,
): AvailableProgramValue[] {
    return values.filter((value) => isProgramTypeCompatible(value.value_type, valueType))
}

export function choiceOptions(
    parameter: ProgramParameterContract,
    platform?: ExecutionPlatformId,
    currentValue?: unknown,
): Array<{ label: string; value: unknown; disabled?: boolean }> {
    return (parameter.constraints?.choices || []).flatMap((choice) => {
        if (choice && typeof choice === 'object' && 'value' in choice) {
            const record = choice as { label?: unknown; value: unknown; platforms?: PlatformId[] }
            const supported = !platform || !record.platforms?.length
                || (platform !== 'no_target' && record.platforms.includes(platform))
            if (supported) return [{ label: String(record.label ?? record.value), value: record.value }]
            if (String(record.value) === String(currentValue)) {
                return [{ label: `${String(record.label ?? record.value)}（当前目标不可用）`, value: record.value, disabled: true }]
            }
            return []
        }
        return [{ label: String(choice), value: choice }]
    })
}
