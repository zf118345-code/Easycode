import type { ProgramValueCatalogDto, PureOperationCandidateDto } from './serverTypes'
import type { AvailableProgramValue, ProgramLiteral, ProgramValueNode, SelectorBindingDefinition } from './types'
import { programTypeDisplayName } from './typePresentation'
import { isProgramTypeCompatible } from './typeCompatibility'
import { newProgramValueId, referenceProgramValue } from './valueFactories'
import { COLOR_FIELD_IDS, formatRgbaHex, normalizeRgbaColor, parseRgbaHex } from '../colorValue'
import {
    normalizeExpressionPunctuation,
    normalizeSyntaxKey,
    operationSyntaxAliases,
    operationSyntaxName,
    splitFunctionArguments,
} from './operationSyntax'

export interface ExpressionSegment {
    text: string
    tone: 'literal' | 'local' | 'project' | 'operator' | 'punctuation' | 'summary'
}

export interface ExpressionParseResult {
    value: ProgramValueNode | null
    error: string
}

interface ParseContext {
    expectedType: string
    availableValues: AvailableProgramValue[]
    catalogs: ProgramValueCatalogDto[]
}

const BINARY_OPERATION_IDS: Record<string, string> = {
    '+': 'core.number_add.v1',
    '-': 'core.number_subtract.v1',
    '*': 'core.number_multiply.v1',
    '/': 'core.number_divide.v1',
    '%': 'core.number_modulo.v1',
}

const OPERATION_SYMBOLS: Record<string, string> = Object.fromEntries(
    Object.entries(BINARY_OPERATION_IDS).map(([symbol, operationId]) => [operationId, symbol]),
)

const DURATION_OPERATION_UNITS: Record<string, string> = {
    'core.duration_from_milliseconds.v1': '毫秒',
    'core.duration_from_seconds.v1': '秒',
    'core.duration_from_minutes.v1': '分钟',
}

const COMPARE_OPERATORS = [
    ['大于等于', 'gte'], ['小于等于', 'lte'], ['不等于', 'ne'], ['等于', 'eq'],
    ['大于', 'gt'], ['小于', 'lt'],
    ['>=', 'gte'], ['<=', 'lte'], ['!=', 'ne'], ['==', 'eq'], ['>', 'gt'], ['<', 'lt'],
] as const

const COMPARE_LABELS = { eq: '等于', ne: '不等于', lt: '小于', lte: '小于等于', gt: '大于', gte: '大于等于' } as const

const INLINE_SCALAR_TYPES = new Set([
    'string', 'relative_path', 'url', 'timezone', 'int64', 'float64', 'percentage',
    'bool', 'duration', 'date', 'datetime', 'time', 'any', 'message_value',
    'point', 'rect', 'path', 'gesture_path', 'control_selector', 'color',
])

function optionalInner(typeId: string): string | null {
    return typeId.startsWith('optional<') && typeId.endsWith('>') ? typeId.slice(9, -1) : null
}

export function isConditionShorthandType(typeId: string): boolean {
    return typeId === 'bool'
        || Boolean(optionalInner(typeId))
        || ['int64', 'float64', 'percentage', 'string'].includes(typeId)
        || Boolean(genericParts(typeId, 'list'))
        || Boolean(genericParts(typeId, 'map'))
}

export function isInlineExpressionValueType(typeId: string): boolean {
    let normalized = typeId
    while (optionalInner(normalized)) normalized = optionalInner(normalized) as string
    // Stable image resources are selected or captured through their dedicated
    // Control.  Treating them as free-form expressions makes a basic choice
    // look like syntax the author has to learn.
    if (normalized === 'asset_ref' || normalized.startsWith('asset_ref<')) return false
    return INLINE_SCALAR_TYPES.has(normalized)
        || /^[a-z][a-z0-9_]*_ref(?:<.*>)?$/.test(normalized)
}

function durationText(value: ProgramLiteral): string | null {
    const milliseconds = typeof value === 'number'
        ? value
        : value && typeof value === 'object' && !Array.isArray(value) && 'milliseconds' in value
            ? Number(value.milliseconds)
            : Number.NaN
    if (!Number.isFinite(milliseconds) || milliseconds < 0) return null
    if (milliseconds >= 60_000 && milliseconds % 60_000 === 0) return `${milliseconds / 60_000} 分钟`
    if (milliseconds >= 1_000 && milliseconds % 1_000 === 0) return `${milliseconds / 1_000} 秒`
    return `${milliseconds} 毫秒`
}

function literalDisplay(value: ProgramLiteral, standalone = false, valueType = ''): string {
    if (value === null) return '无结果'
    if (valueType === 'duration' || optionalInner(valueType) === 'duration') return durationText(value) || JSON.stringify(value)
    if (typeof value === 'boolean') return value ? '开启' : '关闭'
    if (typeof value === 'string') return standalone ? value : `“${value.replaceAll('”', '\\”')}”`
    if (typeof value === 'number') return String(value)
    if (valueType === 'point' && Array.isArray(value) && value.length === 2) return `坐标(${value.join(', ')})`
    if (valueType === 'rect' && Array.isArray(value) && value.length === 4) return `区域(${value.join(', ')})`
    if (['path', 'gesture_path'].includes(valueType) && Array.isArray(value)) return `路径(${value.length} 个点)`
    return JSON.stringify(value)
}

function referenceDisplay(value: ProgramValueNode): string {
    if (value.kind === 'project_variable_ref') return `[项目 · ${value.display_name}]`
    if (value.kind === 'symbol_ref') return `[局部 · ${value.display_name}]`
    return value.summary || programTypeDisplayName(value.value_type)
}

function textTemplateText(value: ProgramValueNode): string | null {
    if (value.kind === 'literal' && value.value_type === 'string' && typeof value.value === 'string') return value.value
    if (value.kind === 'symbol_ref' || value.kind === 'project_variable_ref') return referenceDisplay(value)
    if (value.kind === 'computed' && value.operation_id === 'core.value_to_text.v1') {
        const input = Object.values(value.inputs)[0]
        return input ? expressionText(input, false) : null
    }
    if (value.kind === 'computed' && value.operation_id === 'core.text_concat.v1') {
        const inputs = Object.values(value.inputs)
        if (inputs.length !== 2) return null
        const left = textTemplateText(inputs[0])
        const right = textTemplateText(inputs[1])
        return left === null || right === null ? null : `${left}${right}`
    }
    return null
}

function computedExpressionText(value: Extract<ProgramValueNode, { kind: 'computed' }>): string {
    const candidate: Pick<PureOperationCandidateDto, 'operation_id' | 'display_name' | 'category'> = {
        operation_id: value.operation_id,
        display_name: value.operation_name,
        category: '',
    }
    return `${operationSyntaxName(candidate)}(${Object.values(value.inputs).map((input) => expressionText(input, false)).join(', ')})`
}

function controlSelectorText(value: Extract<ProgramValueNode, { kind: 'record' }>): string {
    const text = (fieldId: string): string => {
        const field = value.fields[fieldId]
        return field?.kind === 'literal' && typeof field.value === 'string' ? field.value : ''
    }
    const name = text('control_selector.field.name') || '已捕获控件'
    const detail = text('control_selector.field.resource_id')
        || text('control_selector.field.automation_id')
        || text('control_selector.field.content_description')
        || text('control_selector.field.class_name')
    return detail ? `${name} · ${detail}` : name
}

function colorRecordModel(value: Extract<ProgramValueNode, { kind: 'record' }>): Record<string, unknown> {
    return Object.fromEntries(Object.entries(value.fields).flatMap(([fieldId, child]) => (
        child.kind === 'literal' ? [[fieldId, child.value]] : []
    )))
}

export function expressionText(value: ProgramValueNode, standalone = true): string {
    if (value.kind === 'literal') return literalDisplay(value.value, standalone, value.value_type)
    if (value.kind === 'symbol_ref' || value.kind === 'project_variable_ref') return referenceDisplay(value)
    if (value.kind === 'asset_ref') return `${value.asset_kind === 'image' ? '图片' : '资源'}「${value.display_name || value.asset_id}」`
    if (value.kind === 'target_ref') return `目标「${value.display_name || value.target_id}」`
    if (value.kind === 'entity_ref') return `${programTypeDisplayName(value.value_type)}「${value.display_name || value.reference_id}」`
    if (value.kind === 'record' && value.value_type === 'control_selector') return value.summary || controlSelectorText(value)
    if (value.kind === 'record' && value.value_type === 'color') {
        const color = normalizeRgbaColor(colorRecordModel(value))
        return formatRgbaHex(color, color.alpha !== 255)
    }
    if (value.kind === 'list') return `[${value.items.map((item) => expressionText(item, false)).join(', ')}]`
    if (value.kind === 'map') return `{${value.entries.map((entry) => `${expressionText(entry.key, false)}: ${expressionText(entry.value, false)}`).join(', ')}}`
    if (value.kind === 'json') return JSON.stringify(value.payload)
    if (value.kind === 'record') return value.summary || `${value.record_name || programTypeDisplayName(value.value_type)}（${Object.keys(value.fields).length} 个字段）`
    if (value.kind === 'compare') {
        return `${expressionText(value.left, false)} ${COMPARE_LABELS[value.operator]} ${expressionText(value.right, false)}`
    }
    if (value.kind === 'condition_group') {
        const separator = value.operator === 'all' ? ' 且 ' : ' 或 '
        return value.conditions.map((item) => expressionText(item, false)).join(separator)
    }
    if (value.kind === 'not') return `非 (${expressionText(value.condition, false)})`
    if (value.kind === 'computed' && DURATION_OPERATION_UNITS[value.operation_id]) {
        const input = Object.values(value.inputs)[0]
        return input ? `${expressionText(input, false)} ${DURATION_OPERATION_UNITS[value.operation_id]}` : computedExpressionText(value)
    }
    if (value.kind === 'computed' && ['core.text_concat.v1', 'core.value_to_text.v1'].includes(value.operation_id)) {
        const template = textTemplateText(value)
        if (template !== null) return template
    }
    if (value.kind === 'computed' && OPERATION_SYMBOLS[value.operation_id]) {
        const inputs = Object.values(value.inputs)
        if (inputs.length === 2) {
            return `(${expressionText(inputs[0], false)} ${OPERATION_SYMBOLS[value.operation_id]} ${expressionText(inputs[1], false)})`
        }
    }
    if (value.kind === 'computed') return computedExpressionText(value)
    if (value.kind === 'selector') return `每项 => ${expressionText(value.expression, false)}`
    if (value.kind === 'member_access') return `${expressionText(value.source, false)}.${value.field_name}`
    return value.summary || programTypeDisplayName(value.value_type)
}

export function expressionSegments(value: ProgramValueNode): ExpressionSegment[] {
    if (value.kind === 'literal') return [{ text: literalDisplay(value.value, true, value.value_type), tone: 'literal' }]
    if (value.kind === 'symbol_ref') return [{ text: `局部 · ${value.display_name}`, tone: 'local' }]
    if (value.kind === 'project_variable_ref') return [{ text: `项目 · ${value.display_name}`, tone: 'project' }]
    if (value.kind === 'asset_ref' || value.kind === 'target_ref' || value.kind === 'entity_ref'
        || (value.kind === 'record' && value.value_type === 'control_selector')) {
        return [{ text: expressionText(value), tone: 'summary' }]
    }
    if (value.kind === 'list' || value.kind === 'map' || value.kind === 'json' || value.kind === 'record') {
        return [{ text: expressionText(value), tone: 'summary' }]
    }
    if (value.kind === 'compare') return [
        ...expressionSegments(value.left),
        { text: COMPARE_LABELS[value.operator], tone: 'operator' },
        ...expressionSegments(value.right),
    ]
    if (value.kind === 'condition_group') {
        return value.conditions.flatMap((condition, index) => [
            ...(index ? [{ text: value.operator === 'all' ? '且' : '或', tone: 'operator' as const }] : []),
            ...expressionSegments(condition),
        ])
    }
    if (value.kind === 'not') return [
        { text: '非', tone: 'operator' },
        { text: '(', tone: 'punctuation' },
        ...expressionSegments(value.condition),
        { text: ')', tone: 'punctuation' },
    ]
    if (value.kind === 'computed' && DURATION_OPERATION_UNITS[value.operation_id]) {
        const input = Object.values(value.inputs)[0]
        return input ? [
            ...expressionSegments(input),
            { text: DURATION_OPERATION_UNITS[value.operation_id], tone: 'literal' },
        ] : [{ text: computedExpressionText(value), tone: 'summary' }]
    }
    if (value.kind === 'computed' && value.operation_id === 'core.text_concat.v1') {
        return Object.values(value.inputs).flatMap(expressionSegments)
    }
    if (value.kind === 'computed' && value.operation_id === 'core.value_to_text.v1') {
        const input = Object.values(value.inputs)[0]
        return input ? expressionSegments(input) : []
    }
    if (value.kind === 'computed' && OPERATION_SYMBOLS[value.operation_id]) {
        const inputs = Object.values(value.inputs)
        if (inputs.length === 2) return [
            { text: '(', tone: 'punctuation' },
            ...expressionSegments(inputs[0]),
            { text: OPERATION_SYMBOLS[value.operation_id], tone: 'operator' },
            ...expressionSegments(inputs[1]),
            { text: ')', tone: 'punctuation' },
        ]
    }
    if (value.kind === 'computed') {
        const candidate: Pick<PureOperationCandidateDto, 'operation_id' | 'display_name' | 'category'> = {
            operation_id: value.operation_id,
            display_name: value.operation_name,
            category: '',
        }
        return [
            { text: operationSyntaxName(candidate), tone: 'operator' },
            { text: '(', tone: 'punctuation' },
            ...Object.values(value.inputs).flatMap((input, index) => [
                ...(index ? [{ text: ',', tone: 'punctuation' as const }] : []),
                ...expressionSegments(input),
            ]),
            { text: ')', tone: 'punctuation' },
        ]
    }
    if (value.kind === 'selector') return [
        { text: '每项 =>', tone: 'operator' },
        ...expressionSegments(value.expression),
    ]
    if (value.kind === 'member_access') return [
        ...expressionSegments(value.source),
        { text: `.${value.field_name}`, tone: 'operator' },
    ]
    return [{ text: value.summary || programTypeDisplayName(value.value_type), tone: 'summary' }]
}

export function isInlineExpressionEditable(value: ProgramValueNode): boolean {
    if (['literal', 'symbol_ref', 'project_variable_ref', 'asset_ref', 'target_ref', 'entity_ref', 'compare', 'condition_group', 'not'].includes(value.kind)) return true
    if (value.kind === 'record' && value.value_type === 'control_selector') return true
    if (value.kind === 'list') return value.items.every(isInlineExpressionEditable)
    if (value.kind === 'map') return value.entries.every((entry) => isInlineExpressionEditable(entry.key) && isInlineExpressionEditable(entry.value))
    if (value.kind === 'record') return Object.values(value.fields).every(isInlineExpressionEditable)
    if (value.kind === 'json') return true
    if (value.kind === 'computed') return Object.values(value.inputs).every(isInlineExpressionEditable)
    if (value.kind === 'selector') return isInlineExpressionEditable(value.expression)
    if (value.kind === 'member_access') return isInlineExpressionEditable(value.source)
    return false
}

function remapSymbolReferences(value: ProgramValueNode, mapping: Map<string, string>): ProgramValueNode {
    if (value.kind === 'symbol_ref' && mapping.has(value.symbol_id)) return { ...value, symbol_id: mapping.get(value.symbol_id) as string }
    if (value.kind === 'computed') return {
        ...value,
        inputs: Object.fromEntries(Object.entries(value.inputs).map(([key, child]) => [key, remapSymbolReferences(child, mapping)])),
    }
    if (value.kind === 'selector') return { ...value, expression: remapSymbolReferences(value.expression, mapping) }
    if (value.kind === 'member_access') return { ...value, source: remapSymbolReferences(value.source, mapping) }
    if (value.kind === 'list') return { ...value, items: value.items.map((child) => remapSymbolReferences(child, mapping)) }
    if (value.kind === 'map') return {
        ...value,
        entries: value.entries.map((entry) => ({
            key: remapSymbolReferences(entry.key, mapping),
            value: remapSymbolReferences(entry.value, mapping),
        })),
    }
    if (value.kind === 'record') return {
        ...value,
        fields: Object.fromEntries(Object.entries(value.fields).map(([key, child]) => [key, remapSymbolReferences(child, mapping)])),
    }
    if (value.kind === 'compare') return {
        ...value,
        left: remapSymbolReferences(value.left, mapping),
        right: remapSymbolReferences(value.right, mapping),
    }
    if (value.kind === 'condition_group') return { ...value, conditions: value.conditions.map((child) => remapSymbolReferences(child, mapping)) }
    if (value.kind === 'not') return { ...value, condition: remapSymbolReferences(value.condition, mapping) }
    return value
}

/**
 * The expression field is only a projection of ProgramDocument. Re-parsing the
 * projection must not manufacture a completely new value tree: Player fields
 * and diagnostics can bind to nested value IDs. Keep the ID of every existing
 * structural slot, while allowing genuinely inserted descendants to retain the
 * fresh IDs produced by the parser.
 */
export function preserveExpressionValueIds(previous: ProgramValueNode, next: ProgramValueNode): ProgramValueNode {
    const result = { ...next, value_id: previous.value_id } as ProgramValueNode
    if (previous.kind !== next.kind) return result

    if (previous.kind === 'computed' && next.kind === 'computed') {
        const inputs = Object.fromEntries(Object.entries(next.inputs).map(([inputId, input]) => [
            inputId,
            previous.inputs[inputId] ? preserveExpressionValueIds(previous.inputs[inputId], input) : input,
        ]))
        return { ...next, value_id: previous.value_id, inputs }
    }
    if (previous.kind === 'compare' && next.kind === 'compare') {
        return {
            ...next,
            value_id: previous.value_id,
            left: preserveExpressionValueIds(previous.left, next.left),
            right: preserveExpressionValueIds(previous.right, next.right),
        }
    }
    if (previous.kind === 'condition_group' && next.kind === 'condition_group') {
        return {
            ...next,
            value_id: previous.value_id,
            conditions: next.conditions.map((condition, index) => (
                previous.conditions[index]
                    ? preserveExpressionValueIds(previous.conditions[index], condition)
                    : condition
            )),
        }
    }
    if (previous.kind === 'not' && next.kind === 'not') {
        return {
            ...next,
            value_id: previous.value_id,
            condition: preserveExpressionValueIds(previous.condition, next.condition),
        }
    }
    if (previous.kind === 'member_access' && next.kind === 'member_access') {
        return {
            ...next,
            value_id: previous.value_id,
            source: preserveExpressionValueIds(previous.source, next.source),
        }
    }
    if (previous.kind === 'selector' && next.kind === 'selector') {
        const symbolMapping = new Map(next.bindings.map((binding, index) => [
            binding.symbol_id,
            previous.bindings[index]?.symbol_id || binding.symbol_id,
        ]))
        const expression = remapSymbolReferences(next.expression, symbolMapping)
        return {
            ...next,
            value_id: previous.value_id,
            bindings: next.bindings.map((binding, index) => previous.bindings[index]
                ? { ...binding, symbol_id: previous.bindings[index].symbol_id }
                : binding),
            expression: preserveExpressionValueIds(previous.expression, expression),
        }
    }
    if (previous.kind === 'record' && next.kind === 'record') {
        return {
            ...next,
            value_id: previous.value_id,
            fields: Object.fromEntries(Object.entries(next.fields).map(([fieldId, child]) => [
                fieldId,
                previous.fields[fieldId] ? preserveExpressionValueIds(previous.fields[fieldId], child) : child,
            ])),
        }
    }
    return result
}

function isWrapped(text: string): boolean {
    if (!text.startsWith('(') || !text.endsWith(')')) return false
    let depth = 0
    for (let index = 0; index < text.length; index += 1) {
        if (text[index] === '(') depth += 1
        else if (text[index] === ')') depth -= 1
        if (depth === 0 && index < text.length - 1) return false
    }
    return depth === 0
}

function stripOuterParentheses(text: string): string {
    let result = text.trim()
    while (isWrapped(result)) result = result.slice(1, -1).trim()
    return result
}

function splitTopLevel(text: string, operators: readonly string[], word = false): { left: string; operator: string; right: string } | null {
    let roundDepth = 0
    let squareDepth = 0
    let quote = ''
    for (let index = text.length - 1; index >= 0; index -= 1) {
        const char = text[index]
        if ((char === '“' || char === '”' || char === '"' || char === "'") && (!quote || quote === char || (quote === '”' && char === '“'))) {
            quote = quote ? '' : (char === '“' ? '”' : char)
            continue
        }
        if (quote) continue
        if (char === ')') roundDepth += 1
        else if (char === '(') roundDepth -= 1
        else if (char === ']') squareDepth += 1
        else if (char === '[') squareDepth -= 1
        if (roundDepth || squareDepth) continue
        for (const operator of operators) {
            const start = index - operator.length + 1
            if (start < 0 || text.slice(start, index + 1) !== operator) continue
            if (word) {
                const before = text[start - 1] || ' '
                const after = text[index + 1] || ' '
                if (!/\s|\)|\]/.test(before) || !/\s|\(|\[/.test(after)) continue
            }
            const left = text.slice(0, start).trim()
            const right = text.slice(index + 1).trim()
            if (!left || !right) continue
            if ((operator === '+' || operator === '-') && /[+\-*/%(]$/.test(left)) continue
            return { left, operator, right }
        }
    }
    return null
}

interface OptionalParseResult extends ExpressionParseResult { handled: boolean }

function genericParts(typeId: string, prefix: string): string[] | null {
    if (!typeId.startsWith(`${prefix}<`) || !typeId.endsWith('>')) return null
    const inner = typeId.slice(prefix.length + 1, -1)
    return splitFunctionArguments(inner).arguments
}

function parseListLiteral(text: string, expectedType: string, context: ParseContext, valueId: string): OptionalParseResult {
    const parts = genericParts(expectedType, 'list')
    const trimmed = text.trim()
    if (!parts || !trimmed.startsWith('[') || !trimmed.endsWith(']')) return { handled: false, value: null, error: '' }
    const split = splitFunctionArguments(trimmed.slice(1, -1))
    if (split.error) return { handled: true, value: null, error: split.error }
    const items: ProgramValueNode[] = []
    for (const item of split.arguments) {
        const parsed = parseExpressionForType(item, parts[0], context, newProgramValueId('value_item'))
        if (!parsed.value) return { handled: true, ...parsed }
        items.push(parsed.value)
    }
    return {
        handled: true,
        value: { value_id: valueId, kind: 'list', value_type: expectedType, item_type: parts[0], items },
        error: '',
    }
}

function memberSyntaxAliases(candidate: ProgramValueCatalogDto['members'][number]): string[] {
    const path = candidate.path.map((field) => field.display_name).join('.')
    const source = candidate.source === 'project' ? '项目' : '局部'
    return [
        `@${candidate.source_display_name}.${path}`,
        `[${source} · ${candidate.source_display_name}].${path}`,
        `[${source}.${candidate.source_display_name}].${path}`,
        `${source}.${candidate.source_display_name}.${path}`,
    ].map(normalizeSyntaxKey)
}

function parseMemberAccess(text: string, context: ParseContext, valueId: string): OptionalParseResult {
    const normalized = normalizeSyntaxKey(text)
    const matches = context.catalogs.flatMap((catalog) => catalog.members)
        .filter((candidate) => memberSyntaxAliases(candidate).includes(normalized))
    if (!matches.length) return { handled: false, value: null, error: '' }
    const resolved = matches.map((candidate) => ({
        candidate,
        available: context.availableValues.find((item) => item.source === candidate.source && item.id === candidate.source_id)
            || context.availableValues.find((item) => item.source === candidate.source
                && item.display_name === candidate.source_display_name
                && item.value_type === candidate.source_value_type),
    })).filter((item) => item.available)
    const unique = resolved.filter((item, index) => resolved.findIndex((other) => (
        other.available?.id === item.available?.id
        && other.candidate.path.map((part) => part.field_id).join('.') === item.candidate.path.map((part) => part.field_id).join('.')
    )) === index)
    if (unique.length > 1) return { handled: true, value: null, error: '这个字段路径对应多个值，请输入 @ 后从候选中选择。' }
    const candidate = unique[0]?.candidate || matches[0]
    const available = unique[0]?.available
    if (!available) return { handled: true, value: null, error: '字段来源已经离开当前作用域，请重新选择。' }
    let source = referenceProgramValue(available, newProgramValueId('value_source'), candidate.source_value_type)
    candidate.path.forEach((field, index) => {
        source = {
            value_id: index === candidate.path.length - 1 ? valueId : newProgramValueId('value_member'),
            kind: 'member_access',
            value_type: field.result_type,
            source,
            field_id: field.field_id,
            field_name: field.display_name,
        }
    })
    return { handled: true, value: source, error: '' }
}

export function selectorBindingsForType(valueType: string): SelectorBindingDefinition[] {
    const list = genericParts(valueType, 'list_selector')
    if (list?.length === 2) return [
        { symbol_id: newProgramValueId('symbol_selector_item'), role: 'item', display_name: '当前项', value_type: list[0] },
        { symbol_id: newProgramValueId('symbol_selector_index'), role: 'index', display_name: '当前序号', value_type: 'int64' },
    ]
    const map = genericParts(valueType, 'map_selector')
    if (map?.length === 3) return [
        { symbol_id: newProgramValueId('symbol_selector_key'), role: 'key', display_name: '当前键', value_type: map[0] },
        { symbol_id: newProgramValueId('symbol_selector_value'), role: 'value', display_name: '当前值', value_type: map[1] },
    ]
    return []
}

export function selectorResultType(valueType: string): string | null {
    const list = genericParts(valueType, 'list_selector')
    if (list?.length === 2) return list[1]
    const map = genericParts(valueType, 'map_selector')
    return map?.length === 3 ? map[2] : null
}

function parseSelector(text: string, expectedType: string, context: ParseContext, valueId: string): OptionalParseResult {
    const resultType = selectorResultType(expectedType)
    if (!resultType) return { handled: false, value: null, error: '' }
    const match = /^(?:每项|逐项)\s*(?:=>|→)\s*(.+)$/s.exec(text.trim())
    if (!match) return {
        handled: true,
        value: null,
        error: '逐项处理请填写“每项 => 表达式”，表达式中可使用 @当前项、@当前序号、@当前键或 @当前值。',
    }
    const bindings = selectorBindingsForType(expectedType)
    const selectorValues: AvailableProgramValue[] = bindings.map((binding) => ({
        source: 'local', id: binding.symbol_id, display_name: binding.display_name, value_type: binding.value_type,
    }))
    const parsed = parseExpressionForType(match[1], resultType, {
        ...context,
        expectedType: resultType,
        availableValues: [...selectorValues, ...context.availableValues],
    }, newProgramValueId('value_selector_expression'))
    if (!parsed.value) return { handled: true, ...parsed }
    return {
        handled: true,
        value: { value_id: valueId, kind: 'selector', value_type: expectedType, bindings, result_type: resultType, expression: parsed.value },
        error: '',
    }
}

function functionCallParts(text: string): { name: string; body: string } | null {
    const normalized = normalizeExpressionPunctuation(text).trim()
    const open = normalized.indexOf('(')
    if (open <= 0 || !normalized.endsWith(')')) return null
    let depth = 0
    let quote = ''
    for (let index = open; index < normalized.length; index += 1) {
        const char = normalized[index]
        if (!quote && (char === '"' || char === "'")) { quote = char; continue }
        if (quote && char === quote) { quote = ''; continue }
        if (quote) continue
        if (char === '(') depth += 1
        else if (char === ')') depth -= 1
        if (depth === 0 && index !== normalized.length - 1) return null
    }
    if (depth !== 0 || quote) return null
    return { name: normalized.slice(0, open).trim(), body: normalized.slice(open + 1, -1) }
}

function parseFunctionCall(text: string, expectedType: string, context: ParseContext, valueId: string): OptionalParseResult {
    const call = functionCallParts(text)
    if (!call) return { handled: false, value: null, error: '' }
    const allCandidates = context.catalogs.flatMap((catalog) => catalog.operations)
    const name = normalizeSyntaxKey(call.name)
    const named = allCandidates.filter((candidate) => operationSyntaxAliases(candidate).includes(name))
    if (!named.length) return { handled: false, value: null, error: '' }
    const compatible = named.filter((candidate) => ['any', 'message_value'].includes(expectedType)
        || isProgramTypeCompatible(candidate.result_type, expectedType))
    if (!compatible.length) {
        return { handled: true, value: null, error: `“${call.name}”的结果不能用于当前${programTypeDisplayName(expectedType)}字段。` }
    }
    const args = splitFunctionArguments(call.body)
    if (args.error) return { handled: true, value: null, error: args.error }
    const correctArity = compatible.filter((candidate) => candidate.inputs.length === args.arguments.length)
    if (!correctArity.length) {
        const counts = [...new Set(compatible.map((candidate) => candidate.inputs.length))].join(' 或 ')
        return { handled: true, value: null, error: `“${call.name}”需要 ${counts} 个参数，目前填写了 ${args.arguments.length} 个。` }
    }
    const failures: string[] = []
    for (const candidate of correctArity) {
        const inputs: Record<string, ProgramValueNode> = {}
        let failed = false
        for (let index = 0; index < candidate.inputs.length; index += 1) {
            const input = candidate.inputs[index]
            const inputValueId = newProgramValueId('value_input')
            const selector = parseSelector(args.arguments[index], input.value_type, context, inputValueId)
            const parsed = selector.handled ? selector : parseExpressionForType(args.arguments[index], input.value_type, context, inputValueId)
            if (!parsed.value) {
                failures.push(`${input.display_name}：${parsed.error}`)
                failed = true
                break
            }
            inputs[input.input_id] = parsed.value
        }
        if (!failed) {
            return {
                handled: true,
                value: {
                    value_id: valueId,
                    kind: 'computed',
                    value_type: candidate.result_type,
                    operation_id: candidate.operation_id,
                    operation_name: operationSyntaxName(candidate),
                    operation_input_names: Object.fromEntries(candidate.inputs.map((input) => [input.input_id, input.display_name])),
                    inputs,
                },
                error: '',
            }
        }
    }
    return { handled: true, value: null, error: failures[0] || `“${call.name}”的参数类型不匹配。` }
}

function resolveReference(text: string, values: AvailableProgramValue[]): { value: AvailableProgramValue | null; error: string } {
    const trimmed = text.trim()
    const bracket = /^(?:\[|【)(项目|项目变量|局部|局部变量)\s*[·.]\s*(.+?)(?:]|】)$/.exec(trimmed)
    const qualified = /^(项目|项目变量|局部|局部变量)[·.]([^]+)$/.exec(trimmed)
    const mention = /^@(.+)$/.exec(trimmed)
    const sourceLabel = bracket?.[1] || qualified?.[1] || ''
    const name = (bracket?.[2] || qualified?.[2] || mention?.[1] || '').trim()
    if (!name) return { value: null, error: '' }
    const expectedSource = sourceLabel.startsWith('项目') ? 'project' : sourceLabel.startsWith('局部') ? 'local' : ''
    const matches = values.filter((item) => item.display_name === name && (!expectedSource || item.source === expectedSource))
    if (matches.length === 1) return { value: matches[0], error: '' }
    if (matches.length > 1) return { value: null, error: `“${name}”存在多个同名值，请从候选中选择具体来源。` }
    return { value: null, error: `当前作用域中没有“${name}”。` }
}

const TEXT_TEMPLATE_TOKEN = /(?:\[(?:项目|项目变量|局部|局部变量)\s*[·.]\s*[^\]]+]|【(?:项目|项目变量|局部|局部变量)\s*[·.]\s*[^】]+】)(?:\s*[.·]\s*[^.·\s,，()（）[\]【】]+)*/g

function isTextConvertibleType(valueType: string): boolean {
    return ['string', 'int64', 'float64', 'percentage', 'bool', 'date', 'datetime', 'time', 'time_of_day', 'duration'].includes(valueType)
        || valueType.startsWith('enum<')
}

function textOperation(
    operationId: 'core.text_concat.v1' | 'core.value_to_text.v1',
    inputs: Record<string, ProgramValueNode>,
    valueId = newProgramValueId('value_text'),
): ProgramValueNode {
    return {
        value_id: valueId,
        kind: 'computed',
        value_type: 'string',
        operation_id: operationId,
        operation_name: operationId === 'core.text_concat.v1' ? '文本.拼接' : '类型.转为文本',
        operation_input_names: operationId === 'core.text_concat.v1'
            ? { 'core.text_concat.v1.input.left': '左侧', 'core.text_concat.v1.input.right': '右侧' }
            : { 'core.value_to_text.v1.input.value': '值' },
        inputs,
    }
}

function parseTextTemplate(text: string, expectedType: string, context: ParseContext, valueId: string): OptionalParseResult {
    const matches = [...text.matchAll(TEXT_TEMPLATE_TOKEN)]
    if (!matches.length) return { handled: false, value: null, error: '' }
    if (matches.length === 1 && matches[0].index === 0 && matches[0][0].length === text.length
        && ['any', 'message_value'].includes(expectedType)) {
        return { handled: false, value: null, error: '' }
    }
    const parts: ProgramValueNode[] = []
    let cursor = 0
    for (const match of matches) {
        const index = match.index || 0
        if (index > cursor) parts.push(literalNode(text.slice(cursor, index), 'string', newProgramValueId('value_text')))
        const member = parseMemberAccess(match[0], context, newProgramValueId('value_member'))
        const resolved = member.handled ? null : resolveReference(match[0], context.availableValues)
        if (member.handled && (!member.value || member.error)) {
            return { handled: true, value: null, error: member.error || '字段引用无效。' }
        }
        if (!member.handled && (resolved?.error || !resolved?.value)) {
            return { handled: true, value: null, error: resolved?.error || '变量引用无效。' }
        }
        let node = member.handled
            ? member.value as ProgramValueNode
            : referenceProgramValue(resolved!.value!, newProgramValueId('value_ref'), resolved!.value!.value_type)
        if (node.value_type !== 'string') {
            if (!isTextConvertibleType(node.value_type)) {
                const displayName = resolved?.value?.display_name || match[0]
                return {
                    handled: true,
                    value: null,
                    error: `“${displayName}”是结构化结果，不能整项嵌入文字；输入 @${displayName} 后请选择具体字段。`,
                }
            }
            node = textOperation('core.value_to_text.v1', { 'core.value_to_text.v1.input.value': node })
        }
        parts.push(node)
        cursor = index + match[0].length
    }
    if (cursor < text.length) parts.push(literalNode(text.slice(cursor), 'string', newProgramValueId('value_text')))
    if (parts.length === 1) return { handled: true, value: { ...parts[0], value_id: valueId }, error: '' }
    let combined = parts[0]
    for (let index = 1; index < parts.length; index += 1) {
        combined = textOperation('core.text_concat.v1', {
            'core.text_concat.v1.input.left': combined,
            'core.text_concat.v1.input.right': parts[index],
        }, index === parts.length - 1 ? valueId : newProgramValueId('value_text'))
    }
    return { handled: true, value: combined, error: '' }
}

function literalNode(value: ProgramLiteral, valueType: string, valueId: string): ProgramValueNode {
    return { value_id: valueId, kind: 'literal', value_type: valueType, value }
}

function colorRecordNode(value: ReturnType<typeof normalizeRgbaColor>, valueId: string): ProgramValueNode {
    return {
        value_id: valueId,
        kind: 'record',
        value_type: 'color',
        record_type: 'color',
        record_name: '颜色',
        field_names: {
            [COLOR_FIELD_IDS.red]: '红',
            [COLOR_FIELD_IDS.green]: '绿',
            [COLOR_FIELD_IDS.blue]: '蓝',
            [COLOR_FIELD_IDS.alpha]: '透明度',
        },
        fields: Object.fromEntries(Object.entries(COLOR_FIELD_IDS).map(([name, fieldId]) => [
            fieldId,
            literalNode(value[name as keyof typeof value], 'int64', newProgramValueId('value_color_channel')),
        ])),
    }
}

function parsePrimitive(text: string, expectedType: string, context: ParseContext, valueId: string): ExpressionParseResult {
    const member = parseMemberAccess(text, context, valueId)
    if (member.handled) return member
    const reference = resolveReference(text, context.availableValues)
    if (reference.error) return { value: null, error: reference.error }
    if (reference.value) {
        if (!isProgramTypeCompatible(reference.value.value_type, expectedType)) {
            return { value: null, error: `“${reference.value.display_name}”是${programTypeDisplayName(reference.value.value_type)}，当前需要${programTypeDisplayName(expectedType)}。` }
        }
        const referenceType = ['any', 'message_value'].includes(expectedType)
            ? reference.value.value_type
            : expectedType
        return { value: referenceProgramValue(reference.value, valueId, referenceType), error: '' }
    }
    const trimmed = text.trim()
    const innerOptionalType = optionalInner(expectedType)
    if (innerOptionalType) {
        if (['无结果', '空', 'null'].includes(trimmed.toLowerCase())) {
            return { value: literalNode(null, expectedType, valueId), error: '' }
        }
        const inner = parsePrimitive(trimmed, innerOptionalType, context, valueId)
        return inner.value?.kind === 'literal'
            ? { value: { ...inner.value, value_type: expectedType }, error: '' }
            : inner
    }
    if (expectedType === 'color') {
        const color = parseRgbaHex(trimmed)
        if (!color) return { value: null, error: '颜色请填写 #RGB、#RRGGBB 或 #RRGGBBAA，也可以输入 @ 选择已有颜色。' }
        return { value: colorRecordNode(color, valueId), error: '' }
    }
    if (expectedType === 'point' || expectedType === 'rect') {
        const label = expectedType === 'point' ? '坐标' : '区域'
        const count = expectedType === 'point' ? 2 : 4
        const constructor = new RegExp(`^(?:${label})?\\s*\\((.*)\\)$`).exec(trimmed)
        const bracket = /^\[(.*)]$/.exec(trimmed)
        const body = constructor?.[1] ?? bracket?.[1]
        if (body === undefined) {
            return { value: null, error: `${label}请填写“${label}(${expectedType === 'point' ? 'X, Y' : 'X, Y, 宽, 高'})”，或输入 @ 选择已有值。` }
        }
        const parts = splitFunctionArguments(body)
        if (parts.error || parts.arguments.length !== count) return { value: null, error: `${label}需要 ${count} 个数值。` }
        const values = parts.arguments.map((part) => Number(part.trim()))
        if (values.some((value) => !Number.isFinite(value))) {
            return { value: null, error: `${label}的每一项都必须是有限数值；需要变量或偏移时可使用 @ 或“坐标.操作(...)”。` }
        }
        return { value: literalNode(values, expectedType, valueId), error: '' }
    }
    if (expectedType === 'bool') {
        if (['开启', '是', '真', 'true'].includes(trimmed.toLowerCase())) return { value: literalNode(true, 'bool', valueId), error: '' }
        if (['关闭', '否', '假', 'false'].includes(trimmed.toLowerCase())) return { value: literalNode(false, 'bool', valueId), error: '' }
        return { value: null, error: '这里需要一个条件。请输入“开启/关闭”、布尔变量或比较表达式。' }
    }
    if (expectedType === 'int64') {
        if (!/^[+-]?\d+$/.test(trimmed)) return { value: null, error: '这里需要整数、整数变量或能得到整数的表达式。' }
        const value = Number(trimmed)
        if (!Number.isSafeInteger(value)) return { value: null, error: '整数超出当前输入器可安全处理的范围。' }
        return { value: literalNode(value, expectedType, valueId), error: '' }
    }
    if (expectedType === 'float64' || expectedType === 'percentage') {
        if (!/^[+-]?(?:\d+\.?\d*|\.\d+)$/.test(trimmed)) return { value: null, error: '这里需要小数、数值变量或能得到数值的表达式。' }
        const value = Number(trimmed)
        if (!Number.isFinite(value)) return { value: null, error: '数值必须是有限小数。' }
        return { value: literalNode(value, expectedType, valueId), error: '' }
    }
    if (expectedType === 'duration') {
        const match = /^(.+?)\s*(毫秒|ms|秒|s|分钟|min)$/i.exec(trimmed)
        if (!match) return { value: null, error: '持续时间请填写例如“500 毫秒”“2 秒”或“1 分钟”。' }
        const amountText = match[1].trim()
        const unit = match[2]?.toLowerCase()
        if (/^[+]?(?:\d+\.?\d*|\.\d+)$/.test(amountText)) {
            const amount = Number(amountText)
            const milliseconds = amount * (unit === '秒' || unit === 's' ? 1_000 : unit === '分钟' || unit === 'min' ? 60_000 : 1)
            if (!Number.isFinite(milliseconds) || milliseconds < 0) return { value: null, error: '持续时间必须是大于等于 0 的有限数值。' }
            return { value: literalNode(milliseconds, expectedType, valueId), error: '' }
        }
        const amountType = numericTypeFor(amountText, context.availableValues)
        const amount = parseArithmetic(amountText, amountType, context, newProgramValueId('value_duration_amount'))
        if (!amount.value) return amount
        const operationId = unit === '秒' || unit === 's'
            ? 'core.duration_from_seconds.v1'
            : unit === '分钟' || unit === 'min'
                ? 'core.duration_from_minutes.v1'
                : 'core.duration_from_milliseconds.v1'
        return {
            value: {
                value_id: valueId, kind: 'computed', value_type: 'duration',
                operation_id: operationId,
                operation_name: unit === '秒' || unit === 's' ? '时间.秒数转持续时间' : unit === '分钟' || unit === 'min' ? '时间.分钟数转持续时间' : '时间.毫秒数转持续时间',
                operation_input_names: { [`${operationId}.input.amount`]: '数值' },
                inputs: { [`${operationId}.input.amount`]: amount.value },
            },
            error: '',
        }
    }
    if (expectedType === 'date') {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(trimmed) || Number.isNaN(Date.parse(`${trimmed}T00:00:00`))) {
            return { value: null, error: '日期请使用 YYYY-MM-DD，例如 2026-09-02。' }
        }
        return { value: literalNode(trimmed, expectedType, valueId), error: '' }
    }
    if (expectedType === 'datetime') {
        const normalized = trimmed.replace(' ', 'T')
        if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/.test(normalized) || Number.isNaN(Date.parse(normalized))) {
            return { value: null, error: '日期时间请使用 YYYY-MM-DD HH:mm，例如 2026-09-02 18:30。' }
        }
        return { value: literalNode(normalized, expectedType, valueId), error: '' }
    }
    if (expectedType === 'time') {
        if (!/^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$/.test(trimmed)) {
            return { value: null, error: '时间请使用 HH:mm，例如 18:30。' }
        }
        return { value: literalNode(trimmed, expectedType, valueId), error: '' }
    }
    if (expectedType.startsWith('enum<')) {
        const unquoted = (/^[“"'].*[”"']$/.test(trimmed)) ? trimmed.slice(1, -1) : trimmed
        return { value: literalNode(unquoted, expectedType, valueId), error: '' }
    }
    if (expectedType === 'any' || expectedType === 'message_value') {
        if (['空', 'null'].includes(trimmed.toLowerCase())) return { value: literalNode(null, 'null', valueId), error: '' }
        if (['开启', '是', '真', 'true'].includes(trimmed.toLowerCase())) return { value: literalNode(true, 'bool', valueId), error: '' }
        if (['关闭', '否', '假', 'false'].includes(trimmed.toLowerCase())) return { value: literalNode(false, 'bool', valueId), error: '' }
        if (/^[+-]?\d+$/.test(trimmed) && Number.isSafeInteger(Number(trimmed))) {
            return { value: literalNode(Number(trimmed), 'int64', valueId), error: '' }
        }
        if (/^[+-]?(?:\d+\.\d*|\.\d+)$/.test(trimmed) && Number.isFinite(Number(trimmed))) {
            return { value: literalNode(Number(trimmed), 'float64', valueId), error: '' }
        }
        const unquoted = (/^[“"'].*[”"']$/.test(trimmed)) ? trimmed.slice(1, -1) : trimmed
        return { value: literalNode(unquoted, 'string', valueId), error: '' }
    }
    if (expectedType === 'string' || expectedType === 'relative_path' || expectedType === 'url' || expectedType === 'timezone') {
        const unquoted = (/^[“"'].*[”"']$/.test(trimmed)) ? trimmed.slice(1, -1) : trimmed
        return { value: literalNode(unquoted, expectedType, valueId), error: '' }
    }
    return { value: null, error: `当前${programTypeDisplayName(expectedType)}不能直接填写；请输入 @ 选择已有值，或输入“类型.操作(参数)”。` }
}

function numericTypeFor(text: string, values: AvailableProgramValue[]): string {
    const names = [...text.matchAll(/(?:\[|【)(?:项目|项目变量|局部|局部变量)\s*[·.]\s*([^\]】]+)(?:]|】)/g)].map((item) => item[1].trim())
    const references = values.filter((item) => names.includes(item.display_name) && ['int64', 'float64', 'percentage'].includes(item.value_type))
    if (references.some((item) => item.value_type !== 'int64') || /\d\.\d/.test(text)) return 'float64'
    return 'int64'
}

function looksLikeNumericExpression(text: string, values: AvailableProgramValue[]): boolean {
    let normalized = text
    normalized = normalized.replace(/(?:\[|【)(项目|项目变量|局部|局部变量)\s*[·.]\s*([^\]】]+)(?:]|】)/g, (token, sourceLabel: string, name: string) => {
        const expectedSource = sourceLabel.startsWith('项目') ? 'project' : 'local'
        const matches = values.filter((item) => item.source === expectedSource
            && item.display_name === String(name).trim()
            && ['int64', 'float64', 'percentage'].includes(item.value_type))
        return matches.length === 1 ? '1' : token
    })
    return /[+*/%]|\s-\s/.test(normalized)
        && /^[\d\s.+\-*/%()]+$/.test(normalized)
}

function operationCandidate(operationId: string, resultType: string, catalogs: ProgramValueCatalogDto[]): PureOperationCandidateDto | null {
    return catalogs.flatMap((catalog) => catalog.operations).find((candidate) => (
        candidate.operation_id === operationId && isProgramTypeCompatible(candidate.result_type, resultType)
    )) || null
}

function parseArithmetic(text: string, expectedType: string, context: ParseContext, valueId: string): ExpressionParseResult {
    const normalized = stripOuterParentheses(text)
    const additive = splitTopLevel(normalized, ['+', '-'])
    const multiplicative = additive ? null : splitTopLevel(normalized, ['*', '/', '%'])
    const split = additive || multiplicative
    if (!split) {
        const call = parseFunctionCall(normalized, expectedType, context, valueId)
        return call.handled ? call : parsePrimitive(normalized, expectedType, context, valueId)
    }
    if (!['int64', 'float64', 'percentage'].includes(expectedType)) {
        return { value: null, error: '四则运算只能用于数值；文本等类型请使用“类型.操作(参数)”。' }
    }
    const operationId = BINARY_OPERATION_IDS[split.operator]
    const candidate = operationCandidate(operationId, expectedType, context.catalogs)
    if (!candidate || candidate.inputs.length !== 2) {
        return { value: null, error: '当前数值运算目录尚未就绪，请稍后重试。' }
    }
    const left = parseArithmetic(split.left, candidate.inputs[0].value_type, context, newProgramValueId('value_input'))
    if (!left.value) return left
    const right = parseArithmetic(split.right, candidate.inputs[1].value_type, context, newProgramValueId('value_input'))
    if (!right.value) return right
    return {
        value: {
            value_id: valueId,
            kind: 'computed',
            value_type: candidate.result_type,
            operation_id: candidate.operation_id,
            operation_name: operationSyntaxName(candidate),
            operation_input_names: Object.fromEntries(candidate.inputs.map((input) => [input.input_id, input.display_name])),
            inputs: {
                [candidate.inputs[0].input_id]: left.value,
                [candidate.inputs[1].input_id]: right.value,
            },
        },
        error: '',
    }
}

function parseComparable(text: string, context: ParseContext, valueId: string): ExpressionParseResult {
    const expectedType = numericTypeFor(text, context.availableValues)
    if (/^[+-]?(?:\d+\.?\d*|\.\d+)$/.test(stripOuterParentheses(text))) {
        return parsePrimitive(stripOuterParentheses(text), expectedType, context, valueId)
    }
    const call = parseFunctionCall(stripOuterParentheses(text), 'any', context, valueId)
    if (call.handled) return call
    const member = parseMemberAccess(stripOuterParentheses(text), context, valueId)
    if (member.handled) return member
    const reference = resolveReference(stripOuterParentheses(text), context.availableValues)
    if (reference.value) return { value: referenceProgramValue(reference.value, valueId, reference.value.value_type), error: '' }
    if (reference.error && /^(?:\[|@|(?:项目变量|项目|局部变量|局部)[·.])/.test(text.trim())) return { value: null, error: reference.error }
    if (/[+*/%]/.test(text) || /\s-\s/.test(text)) return parseArithmetic(text, expectedType, context, valueId)
    const trimmed = text.trim()
    if (/^[“"'].*[”"']$/.test(trimmed)) return { value: literalNode(trimmed.slice(1, -1), 'string', valueId), error: '' }
    return { value: literalNode(trimmed, 'string', valueId), error: '' }
}

function withValueId(value: ProgramValueNode, valueId: string): ProgramValueNode {
    return { ...value, value_id: valueId }
}

function conditionFromValue(value: ProgramValueNode, valueId: string): ExpressionParseResult {
    const valueType = value.value_type
    if (valueType === 'bool') return { value: withValueId(value, valueId), error: '' }
    const operand = withValueId(value, newProgramValueId('value_condition_operand'))
    if (optionalInner(valueType)) {
        const operationId = 'core.optional_has_value.v1'
        return {
            value: {
                value_id: valueId, kind: 'computed', value_type: 'bool', operation_id: operationId,
                operation_name: '结果.有结果', operation_input_names: { [`${operationId}.input.value`]: '值' },
                inputs: { [`${operationId}.input.value`]: operand },
            },
            error: '',
        }
    }
    if (['int64', 'float64', 'percentage'].includes(valueType)) {
        return {
            value: {
                value_id: valueId, kind: 'compare', value_type: 'bool', operator: 'ne', left: operand,
                right: literalNode(0, valueType, newProgramValueId('value_condition_zero')),
            },
            error: '',
        }
    }
    if (valueType === 'string') {
        return {
            value: {
                value_id: valueId, kind: 'compare', value_type: 'bool', operator: 'ne', left: operand,
                right: literalNode('', 'string', newProgramValueId('value_condition_empty_text')),
            },
            error: '',
        }
    }
    if (genericParts(valueType, 'list')) {
        const operationId = 'core.list_is_empty.v1'
        return {
            value: {
                value_id: valueId, kind: 'not', value_type: 'bool',
                condition: {
                    value_id: newProgramValueId('value_condition_empty'), kind: 'computed', value_type: 'bool',
                    operation_id: operationId, operation_name: '列表.是否为空',
                    operation_input_names: { [`${operationId}.input.list`]: '列表' },
                    inputs: { [`${operationId}.input.list`]: operand },
                },
            },
            error: '',
        }
    }
    const mapTypes = genericParts(valueType, 'map')
    if (mapTypes?.length === 2) {
        const keysOperationId = 'core.map_keys.v1'
        const emptyOperationId = 'core.list_is_empty.v1'
        return {
            value: {
                value_id: valueId, kind: 'not', value_type: 'bool',
                condition: {
                    value_id: newProgramValueId('value_condition_empty'), kind: 'computed', value_type: 'bool',
                    operation_id: emptyOperationId, operation_name: '列表.是否为空',
                    operation_input_names: { [`${emptyOperationId}.input.list`]: '列表' },
                    inputs: {
                        [`${emptyOperationId}.input.list`]: {
                            value_id: newProgramValueId('value_condition_keys'), kind: 'computed',
                            value_type: `list<${mapTypes[0]}>`, operation_id: keysOperationId,
                            operation_name: '字典.所有键', operation_input_names: { [`${keysOperationId}.input.map`]: '字典' },
                            inputs: { [`${keysOperationId}.input.map`]: operand },
                        },
                    },
                },
            },
            error: '',
        }
    }
    return {
        value: null,
        error: `${programTypeDisplayName(valueType)}没有默认的条件含义；请选择它的具体字段或使用明确的判断操作。`,
    }
}

function parseConditionShorthand(text: string, context: ParseContext, valueId: string): OptionalParseResult {
    const normalized = stripOuterParentheses(text)
    const member = parseMemberAccess(normalized, context, newProgramValueId('value_condition_source'))
    if (member.handled) return member.value
        ? { handled: true, ...conditionFromValue(member.value, valueId) }
        : member
    const reference = resolveReference(normalized, context.availableValues)
    if (reference.value) {
        return {
            handled: true,
            ...conditionFromValue(referenceProgramValue(
                reference.value,
                newProgramValueId('value_condition_source'),
                reference.value.value_type,
            ), valueId),
        }
    }
    if (reference.error && /^(?:\[|@|(?:项目变量|项目|局部变量|局部)[·.])/.test(normalized)) {
        return { handled: true, value: null, error: reference.error }
    }
    const call = parseFunctionCall(normalized, 'any', context, newProgramValueId('value_condition_source'))
    if (call.handled) return call.value
        ? { handled: true, ...conditionFromValue(call.value, valueId) }
        : call
    if (/^[+-]?\d+$/.test(normalized)) {
        const parsed = parsePrimitive(normalized, 'int64', context, newProgramValueId('value_condition_source'))
        return parsed.value ? { handled: true, ...conditionFromValue(parsed.value, valueId) } : { handled: true, ...parsed }
    }
    if (/^[+-]?(?:\d+\.\d*|\.\d+)$/.test(normalized)) {
        const parsed = parsePrimitive(normalized, 'float64', context, newProgramValueId('value_condition_source'))
        return parsed.value ? { handled: true, ...conditionFromValue(parsed.value, valueId) } : { handled: true, ...parsed }
    }
    if (/^[“"'].*[”"']$/.test(normalized)) {
        const parsed = parsePrimitive(normalized, 'string', context, newProgramValueId('value_condition_source'))
        return parsed.value ? { handled: true, ...conditionFromValue(parsed.value, valueId) } : { handled: true, ...parsed }
    }
    return { handled: false, value: null, error: '' }
}

function parseCondition(text: string, context: ParseContext, valueId: string): ExpressionParseResult {
    const normalized = stripOuterParentheses(text)
    const orSplit = splitTopLevel(normalized, ['||', '或'], true)
    const andSplit = orSplit ? null : splitTopLevel(normalized, ['&&', '且'], true)
    const logical = orSplit || andSplit
    if (logical) {
        const left = parseCondition(logical.left, context, newProgramValueId('value_condition'))
        if (!left.value) return left
        const right = parseCondition(logical.right, context, newProgramValueId('value_condition'))
        if (!right.value) return right
        const operator = logical.operator === '且' || logical.operator === '&&' ? 'all' : 'any'
        const leftConditions = left.value.kind === 'condition_group' && left.value.operator === operator ? left.value.conditions : [left.value]
        const rightConditions = right.value.kind === 'condition_group' && right.value.operator === operator ? right.value.conditions : [right.value]
        return { value: { value_id: valueId, kind: 'condition_group', value_type: 'bool', operator, conditions: [...leftConditions, ...rightConditions] }, error: '' }
    }
    if (/^(非|!)\s*/.test(normalized)) {
        const childText = normalized.replace(/^(非|!)\s*/, '')
        const child = parseCondition(childText, context, newProgramValueId('value_condition'))
        return child.value
            ? { value: { value_id: valueId, kind: 'not', value_type: 'bool', condition: child.value }, error: '' }
            : child
    }
    for (const [token, operator] of COMPARE_OPERATORS) {
        const split = splitTopLevel(normalized, [token])
        if (!split) continue
        const left = parseComparable(split.left, context, newProgramValueId('value_left'))
        if (!left.value) return left
        const right = parseComparable(split.right, context, newProgramValueId('value_right'))
        if (!right.value) return right
        let leftValue = left.value
        let rightValue = right.value
        if (leftValue.kind === 'literal' && rightValue.kind !== 'literal') {
            const reparsed = parsePrimitive(split.left, rightValue.value_type, context, leftValue.value_id)
            if (!reparsed.value) return reparsed
            leftValue = reparsed.value
        }
        if (rightValue.kind === 'literal' && leftValue.kind !== 'literal') {
            const reparsed = parsePrimitive(split.right, leftValue.value_type, context, rightValue.value_id)
            if (!reparsed.value) return reparsed
            rightValue = reparsed.value
        }
        if (!isProgramTypeCompatible(leftValue.value_type, rightValue.value_type)
            && !isProgramTypeCompatible(rightValue.value_type, leftValue.value_type)) {
            return { value: null, error: `不能比较${programTypeDisplayName(leftValue.value_type)}和${programTypeDisplayName(rightValue.value_type)}。` }
        }
        if (['lt', 'lte', 'gt', 'gte'].includes(operator)
            && !['int64', 'float64', 'percentage', 'duration', 'date', 'datetime', 'time'].includes(leftValue.value_type)) {
            return { value: null, error: '大于、小于比较只适用于数值、持续时间或时间类型。' }
        }
        return { value: { value_id: valueId, kind: 'compare', value_type: 'bool', operator, left: leftValue, right: rightValue }, error: '' }
    }
    const shorthand = parseConditionShorthand(normalized, context, valueId)
    return shorthand.handled ? shorthand : parsePrimitive(normalized, 'bool', context, valueId)
}

function parseExpressionForType(
    text: string,
    expectedType: string,
    context: ParseContext,
    valueId: string,
): ExpressionParseResult {
    const rawTrimmed = text.trim()
    const openValueExpression = ['any', 'message_value'].includes(expectedType)
    const templateMayBeNumeric = openValueExpression && looksLikeNumericExpression(rawTrimmed, context.availableValues)
    const templateMayBeCondition = openValueExpression && (
        COMPARE_OPERATORS.some(([token]) => rawTrimmed.includes(token))
        || /(?:^|\s)(?:且|或|&&|\|\|)(?:\s|$)/.test(rawTrimmed)
        || /^(?:非|!)\s*/.test(rawTrimmed)
    )
    if (['string', 'any', 'message_value'].includes(expectedType) && !templateMayBeNumeric && !templateMayBeCondition) {
        const template = parseTextTemplate(rawTrimmed, expectedType, context, valueId)
        if (template.handled) return template
    }
    const trimmed = normalizeExpressionPunctuation(rawTrimmed).trim()
    if (!trimmed) return { value: null, error: '请输入内容，或从候选中选择一个值。' }
    const call = parseFunctionCall(trimmed, expectedType === 'bool' ? 'any' : expectedType, context, valueId)
    if (call.handled) {
        if (expectedType === 'bool' && call.value) return conditionFromValue(call.value, valueId)
        return call
    }
    const list = parseListLiteral(trimmed, expectedType, context, valueId)
    if (list.handled) return list
    const innerOptionalType = optionalInner(expectedType)
    if (innerOptionalType) return parsePrimitive(trimmed, expectedType, context, valueId)
    if (expectedType === 'bool') return parseCondition(trimmed, context, valueId)
    if (['int64', 'float64', 'percentage'].includes(expectedType)) {
        return parseArithmetic(trimmed, expectedType, context, valueId)
    }
    if (['any', 'message_value'].includes(expectedType)) {
        const looksLikeCondition = COMPARE_OPERATORS.some(([token]) => trimmed.includes(token))
            || /(?:^|\s)(?:且|或|&&|\|\|)(?:\s|$)/.test(trimmed)
            || /^(?:非|!)\s*/.test(trimmed)
        if (looksLikeCondition) return parseCondition(trimmed, context, valueId)
        const looksLikeArithmetic = looksLikeNumericExpression(trimmed, context.availableValues)
        if (looksLikeArithmetic) return parseArithmetic(trimmed, numericTypeFor(trimmed, context.availableValues), context, valueId)
    }
    return parsePrimitive(trimmed, expectedType, context, valueId)
}

export function parseExpressionDraft(
    text: string,
    expectedType: string,
    valueId: string,
    availableValues: AvailableProgramValue[],
    catalogs: ProgramValueCatalogDto[] = [],
): ExpressionParseResult {
    return parseExpressionForType(text, expectedType, { expectedType, availableValues, catalogs }, valueId)
}
