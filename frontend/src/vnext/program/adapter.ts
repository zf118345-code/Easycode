import type { ParameterControlType, PlatformId } from '../types'
import type {
    LocalSymbolDefinition,
    ProgramAssignmentTarget,
    ProgramCommand,
    ProgramDocument,
    ProgramFunctionContract,
    ProgramLiteral,
    ProgramParameterContract,
    ProgramStatement,
    ProgramSummaryPart,
    ProgramValueDraft,
    ProgramValueNode,
    ProgramValueUpdate,
} from './types'
import { valueSummary } from './projection'
import type {
    AvailableFunctionContractDto,
    AvailableFunctionParameterDto,
    ProgramServerCommand,
    ProgramSnapshotDto,
    ProgramSummaryDto,
    ServerAssignmentTarget,
    ServerProgramStatement,
    ServerProgramValueNode,
} from './serverTypes'

export class ProgramProjectionError extends Error {
    constructor(message: string) { super(message); this.name = 'ProgramProjectionError' }
}

export interface ProgramProjectionLookups {
    symbolNames?: Record<string, string>
    projectVariableNames?: Record<string, string>
    assetNames?: Record<string, string>
    targetNames?: Record<string, string>
    entityNames?: Record<string, string>
    fieldNames?: Record<string, string>
    recordTypeNames?: Record<string, string>
    operationNames?: Record<string, string>
    operationSyntaxNames?: Record<string, string>
    operationInputNames?: Record<string, Record<string, string>>
    functionNames?: Record<string, string>
}

const SUPPORTED_CONTROLS = new Set<ParameterControlType>([
    'text', 'number', 'toggle', 'select', 'slider-number', 'duration', 'time', 'color', 'coordinate', 'region',
    'resource', 'control-selector', 'gesture-path', 'file', 'directory', 'control-reference',
    'instance', 'target', 'application', 'instance-multi-select', 'key-chord', 'json',
    'list', 'key-value', 'expression',
])

function normalizedType(valueType: string): string {
    if (valueType.startsWith('optional<') && valueType.endsWith('>')) return normalizedType(valueType.slice(9, -1))
    if (valueType.startsWith('enum<')) return 'enum'
    if (valueType.startsWith('list<')) return 'list'
    if (valueType.startsWith('map<')) return 'map'
    if (valueType.startsWith('asset_ref')) return 'asset_ref'
    if (valueType === 'gesture_path') return 'path'
    if (valueType === 'json_value') return 'json'
    return valueType
}

function inferredControl(parameter: AvailableFunctionParameterDto): ParameterControlType {
    const requested = parameter.ui?.control || parameter.control
    if (requested !== 'auto' && SUPPORTED_CONTROLS.has(requested as ParameterControlType)) {
        if (requested === 'select' && !Array.isArray(parameter.constraints?.choices)) return 'text'
        return requested as ParameterControlType
    }
    return inferredControlForType(parameter.value_type)
}

function inferredControlForType(typeId: string): ParameterControlType {
    const valueType = normalizedType(typeId)
    if (valueType === 'bool') return 'toggle'
    if (valueType === 'int64' || valueType === 'float64') return 'number'
    if (valueType === 'duration') return 'duration'
    if (valueType === 'datetime' || valueType === 'date' || valueType === 'time') return 'time'
    if (valueType === 'color') return 'color'
    if (valueType === 'point') return 'coordinate'
    if (valueType === 'rect') return 'region'
    if (valueType === 'path') return 'gesture-path'
    if (valueType === 'asset_ref') return 'resource'
    if (valueType === 'list') return 'list'
    if (valueType === 'map' || valueType === 'record' || valueType === 'json') return 'key-value'
    return 'text'
}

function defaultLiteral(parameter: AvailableFunctionParameterDto): ProgramLiteral | undefined {
    if (!parameter.has_default) return undefined
    const value = parameter.default
    if (parameter.value_type === 'duration') {
        if (value && typeof value === 'object' && 'milliseconds' in value) {
            return { milliseconds: Number((value as { milliseconds: unknown }).milliseconds) || 0 }
        }
        return { milliseconds: Number(value) || 0 }
    }
    if (value === null || ['string', 'number', 'boolean'].includes(typeof value)) return value as ProgramLiteral
    if (Array.isArray(value)) return value as ProgramLiteral
    if (value && typeof value === 'object') return value as ProgramLiteral
    return undefined
}

function platformsFor(contract: AvailableFunctionContractDto): PlatformId[] {
    const requested = contract.target_kinds.length ? contract.target_kinds : contract.host_requirements
    const result = new Set<PlatformId>()
    for (const platform of requested) {
        if (platform === 'windows') result.add('windows')
        if (platform === 'android' || platform === 'android_adb') result.add('android_adb')
        if (platform === 'android' || platform === 'android_local') result.add('android_local')
    }
    return [...result]
}

export function availableFunctionToUiContract(contract: AvailableFunctionContractDto): ProgramFunctionContract {
    const parameters: ProgramParameterContract[] = contract.parameters.map((parameter) => {
        const actions = parameter.ui?.actions
        return {
            parameter_id: parameter.parameter_id,
            display_name: parameter.display_name,
            value_type: parameter.value_type,
            required: parameter.required,
            default_value: defaultLiteral(parameter),
            description: parameter.description || undefined,
            constraints: { ...parameter.constraints },
            ui: {
                ...(parameter.ui || {}),
                control: inferredControl(parameter),
                ...(actions?.length ? { actions } : {}),
            },
            // Contract choices are fixed author decisions, so select Controls
            // never expose variable/calculation source modes. Other values use
            // one unified expression surface backed by the server catalog.
            allowed_sources: Array.isArray(parameter.constraints?.choices) && parameter.constraints.choices.length
                ? ['fixed']
                : ['fixed', 'reference', 'computed'],
        }
    })
    return {
        function_id: contract.function_id,
        display_name: contract.qualified_name || `${contract.namespace}.${contract.name}`,
        description: contract.summary,
        parameters,
        return_type: contract.return_type === 'unit' ? 'void' : contract.return_type,
        platforms: platformsFor(contract),
        dangerous: contract.dangerous,
    }
}

export function availableFunctionsToUiContracts(functions: AvailableFunctionContractDto[]): Record<string, ProgramFunctionContract> {
    return Object.fromEntries(functions.filter((item) => item.implementation_state === 'available').map((item) => {
        const contract = availableFunctionToUiContract(item)
        return [contract.function_id, contract]
    }))
}

export function projectFunctionToUiContract(summary: ProgramSummaryDto): ProgramFunctionContract {
    return {
        function_id: summary.function_id,
        display_name: summary.display_name,
        description: '当前项目中的可复用函数',
        parameters: summary.parameters.map((parameter) => {
            const defaultValue = parameter.default_value ? serverValueToUiValue(parameter.default_value) : null
            const literalDefault = defaultValue?.kind === 'literal' ? defaultValue.value
                : defaultValue?.kind === 'json' ? defaultValue.payload : undefined
            return {
                parameter_id: parameter.parameter_id,
                display_name: parameter.display_name,
                value_type: parameter.value_type,
                required: parameter.required,
                default_value: literalDefault,
                ui: { control: inferredControlForType(parameter.value_type) },
                allowed_sources: parameter.value_type.startsWith('enum<')
                    ? ['fixed']
                    : ['fixed', 'reference', 'computed'],
            }
        }),
        return_type: summary.return_type === 'unit' ? 'void' : summary.return_type,
    }
}

export function projectFunctionsToUiContracts(programs: ProgramSummaryDto[]): Record<string, ProgramFunctionContract> {
    return Object.fromEntries(programs.map((program) => [program.function_id, projectFunctionToUiContract(program)]))
}

function jsonLiteral(value: unknown): ProgramLiteral {
    if (value === null || typeof value === 'string' || typeof value === 'boolean') return value
    if (typeof value === 'number' && Number.isFinite(value)) return value
    if (Array.isArray(value)) return value.map(jsonLiteral)
    if (value && typeof value === 'object') {
        return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, jsonLiteral(child)]))
    }
    throw new ProgramProjectionError('服务端返回了无法展示的 JSON 值')
}

export function serverValueToUiValue(value: ServerProgramValueNode, lookups: ProgramProjectionLookups = {}): ProgramValueNode {
    if (value.kind === 'unset') return { value_id: value.value_id, kind: 'unset', value_type: value.expected_type }
    if (value.kind === 'null') return { value_id: value.value_id, kind: 'literal', value_type: 'null', value: null }
    if (value.kind === 'string' || value.kind === 'int64' || value.kind === 'float64' || value.kind === 'bool'
        || value.kind === 'date' || value.kind === 'datetime' || value.kind === 'time') {
        return { value_id: value.value_id, kind: 'literal', value_type: value.kind, value: value.value }
    }
    if (value.kind === 'duration') return { value_id: value.value_id, kind: 'literal', value_type: 'duration', value: { milliseconds: value.milliseconds } }
    if (value.kind === 'point') return { value_id: value.value_id, kind: 'literal', value_type: 'point', value: [value.x, value.y] }
    if (value.kind === 'rect') return { value_id: value.value_id, kind: 'literal', value_type: 'rect', value: [value.x, value.y, value.width, value.height] }
    if (value.kind === 'path') return { value_id: value.value_id, kind: 'literal', value_type: 'path', value: value.points.map((point) => [point.x, point.y]) }
    if (value.kind === 'symbol_ref') return {
        value_id: value.value_id, kind: 'symbol_ref', value_type: value.value_type, symbol_id: value.symbol_id,
        display_name: lookups.symbolNames?.[value.symbol_id] || '局部值',
    }
    if (value.kind === 'project_variable_ref') return {
        value_id: value.value_id, kind: 'project_variable_ref', value_type: value.value_type, variable_id: value.variable_id,
        display_name: lookups.projectVariableNames?.[value.variable_id] || '项目变量',
    }
    if (value.kind === 'asset_ref') return {
        value_id: value.value_id, kind: 'asset_ref', value_type: `asset_ref<${value.asset_kind}>`, asset_id: value.asset_id,
        asset_kind: value.asset_kind, display_name: lookups.assetNames?.[value.asset_id],
    }
    if (value.kind === 'target_ref') return {
        value_id: value.value_id, kind: 'target_ref', value_type: 'target_ref', target_id: value.target_id,
        display_name: lookups.targetNames?.[value.target_id],
    }
    if (value.kind === 'entity_ref') return {
        value_id: value.value_id, kind: 'entity_ref', value_type: value.reference_type, reference_id: value.reference_id,
        reference_type: value.reference_type, display_name: lookups.entityNames?.[value.reference_id],
    }
    if (value.kind === 'member_access') return {
        value_id: value.value_id, kind: 'member_access', value_type: value.result_type,
        source: serverValueToUiValue(value.source, lookups), field_id: value.field_id,
        field_name: lookups.fieldNames?.[value.field_id] || '不可用字段',
    }
    if (value.kind === 'list') return {
        value_id: value.value_id, kind: 'list', value_type: `list<${value.item_type}>`, item_type: value.item_type,
        items: value.items.map((item) => serverValueToUiValue(item, lookups)),
    }
    if (value.kind === 'map') return {
        value_id: value.value_id, kind: 'map', value_type: `map<${value.key_type},${value.entry_value_type}>`,
        key_type: value.key_type, entry_value_type: value.entry_value_type, duplicate_policy: value.duplicate_policy,
        entries: value.entries.map((entry) => ({ key: serverValueToUiValue(entry.key, lookups), value: serverValueToUiValue(entry.value, lookups) })),
    }
    if (value.kind === 'record') return {
        value_id: value.value_id, kind: 'record', value_type: value.record_type, record_type: value.record_type,
        record_name: lookups.recordTypeNames?.[value.record_type],
        field_names: lookups.fieldNames,
        fields: Object.fromEntries(Object.entries(value.fields).map(([fieldId, child]) => [fieldId, serverValueToUiValue(child, lookups)])),
    }
    if (value.kind === 'json') return { value_id: value.value_id, kind: 'json', value_type: 'json_value', payload: jsonLiteral(value.payload) }
    if (value.kind === 'operation') return {
        value_id: value.value_id, kind: 'computed', value_type: value.result_type, operation_id: value.operation_id,
        operation_name: lookups.operationSyntaxNames?.[value.operation_id]
            || lookups.operationNames?.[value.operation_id]
            || '不可用操作',
        operation_input_names: lookups.operationInputNames?.[value.operation_id],
        inputs: Object.fromEntries(Object.entries(value.inputs).map(([inputId, child]) => [inputId, serverValueToUiValue(child, lookups)])),
    }
    if (value.kind === 'selector') {
        const byRole = Object.fromEntries(value.bindings.map((binding) => [binding.role, binding.value_type]))
        const valueType = byRole.item
            ? `list_selector<${byRole.item},${value.result_type}>`
            : `map_selector<${byRole.key},${byRole.value},${value.result_type}>`
        return {
            value_id: value.value_id, kind: 'selector', value_type: valueType,
            result_type: value.result_type, bindings: value.bindings,
            expression: serverValueToUiValue(value.expression, lookups),
        }
    }
    if (value.kind === 'compare') return {
        value_id: value.value_id, kind: 'compare', value_type: 'bool', operator: value.operator,
        left: serverValueToUiValue(value.left, lookups), right: serverValueToUiValue(value.right, lookups),
    }
    if (value.kind === 'condition_group') return {
        value_id: value.value_id, kind: 'condition_group', value_type: 'bool', operator: value.operator,
        conditions: value.conditions.map((condition) => serverValueToUiValue(condition, lookups)),
    }
    return { value_id: value.value_id, kind: 'not', value_type: 'bool', condition: serverValueToUiValue(value.condition, lookups) }
}

function parameterByName(contract: AvailableFunctionContractDto | undefined, name: string): AvailableFunctionParameterDto | undefined {
    return contract?.parameters.find((parameter) => parameter.name === name || parameter.parameter_id === name)
}
function callArgumentSummary(value: ProgramValueNode | undefined, parameter?: AvailableFunctionParameterDto): string {
    if (!value || value.kind === 'unset') return '待配置'
    if (value.kind === 'literal' && parameter?.value_type.startsWith('enum<')) {
        const choice = Array.isArray(parameter.constraints?.choices)
            ? parameter.constraints.choices.find((item) => item && typeof item === 'object' && (item as { value?: unknown }).value === value.value)
            : null
        const label = choice && typeof choice === 'object' ? (choice as { label?: unknown }).label : ''
        if (typeof label === 'string' && label) return label
    }
    return valueSummary(value).replace(
        /\[(项目|项目变量|局部|局部变量)\s*[·.]\s*([^\]]+)]/g,
        (_token, source: string, name: string) => `${source.replace('变量', '')} · ${name.trim()}`,
    )
}
function renderedCallSummaryParts(contract: AvailableFunctionContractDto | undefined, argumentsById: Record<string, ProgramValueNode>) {
    if (!contract?.summary) return undefined
    if (contract.statement_summary?.schema_version === 1) {
        return contract.statement_summary.parts.map((part) => {
            if (part.kind === 'text') return { text: part.text }
            const parameter = contract.parameters.find((item) => item.parameter_id === part.parameter_id)
            const value = argumentsById[part.parameter_id]
            return {
                text: callArgumentSummary(value, parameter),
                dynamic: true,
                value,
                parameter_id: part.parameter_id,
                role: part.role,
                presentation: part.presentation,
            }
        })
    }
    const parts: ProgramSummaryPart[] = []
    let cursor = 0
    for (const match of contract.summary.matchAll(/\{([^}]+)\}/g)) {
        const index = match.index ?? 0
        if (index > cursor) parts.push({ text: contract.summary.slice(cursor, index) })
        const parameter = parameterByName(contract, match[1])
        parts.push({
            text: parameter ? callArgumentSummary(argumentsById[parameter.parameter_id], parameter) : '待配置',
            dynamic: true,
            value: parameter ? argumentsById[parameter.parameter_id] : undefined,
            parameter_id: parameter?.parameter_id,
        })
        cursor = index + match[0].length
    }
    if (cursor < contract.summary.length) parts.push({ text: contract.summary.slice(cursor) })
    return parts
}

function assignmentTarget(target: ServerAssignmentTarget, lookups: ProgramProjectionLookups) {
    if (target.kind === 'local') return { ...target }
    return { ...target, display_name: lookups.projectVariableNames?.[target.variable_id] || '项目变量' }
}

function serverStatementToUiStatement(statement: ServerProgramStatement, contracts: Record<string, AvailableFunctionContractDto>, lookups: ProgramProjectionLookups): ProgramStatement {
    const step_label = statement.step_label || undefined
    if (statement.kind === 'call') {
        const contract = contracts[statement.function_id]
        const argumentsById = Object.fromEntries(Object.entries(statement.arguments).map(([parameterId, value]) => [parameterId, serverValueToUiValue(value, lookups)]))
        const summaryParts = renderedCallSummaryParts(contract, argumentsById)
        return {
            statement_id: statement.statement_id, kind: 'call', function_id: statement.function_id,
            display_name: contract?.qualified_name || lookups.functionNames?.[statement.function_id] || '不可用函数',
            summary: summaryParts?.map((part) => part.text).join(''), summary_parts: summaryParts, arguments: argumentsById,
            result_binding: statement.result_binding ? { ...statement.result_binding } : null,
            author_review_fingerprint: statement.author_review_fingerprint, step_label,
        }
    }
    if (statement.kind === 'assignment') return {
        statement_id: statement.statement_id, kind: 'assignment', target: assignmentTarget(statement.target, lookups),
        value: serverValueToUiValue(statement.value, lookups), step_label,
    }
    if (statement.kind === 'if') return {
        statement_id: statement.statement_id, kind: 'if', condition: serverValueToUiValue(statement.condition, lookups),
        then_body: statement.then_statements.map((child) => serverStatementToUiStatement(child, contracts, lookups)),
        additional_branches: statement.additional_branches.map((branch) => ({
            branch_id: branch.branch_id, condition: serverValueToUiValue(branch.condition, lookups),
            statements: branch.statements.map((child) => serverStatementToUiStatement(child, contracts, lookups)),
        })),
        else_body: statement.otherwise_statements.map((child) => serverStatementToUiStatement(child, contracts, lookups)), step_label,
    }
    if (statement.kind === 'loop') return {
        statement_id: statement.statement_id, kind: 'loop', mode: statement.mode, source: serverValueToUiValue(statement.source, lookups),
        body: statement.body.map((child) => serverStatementToUiStatement(child, contracts, lookups)),
        item_binding: statement.item_binding, index_binding: statement.index_binding,
        key_binding: statement.key_binding, value_binding: statement.value_binding, step_label,
    }
    if (statement.kind === 'break' || statement.kind === 'continue') return {
        statement_id: statement.statement_id, kind: statement.kind, step_label,
    }
    if (statement.kind === 'return') return {
        statement_id: statement.statement_id, kind: 'return', value: statement.value ? serverValueToUiValue(statement.value, lookups) : null, step_label,
    }
    if (statement.kind === 'fail') return {
        statement_id: statement.statement_id, kind: 'fail', error_id: statement.error_id,
        message: serverValueToUiValue(statement.message, lookups),
        details: statement.details ? serverValueToUiValue(statement.details, lookups) : null,
        step_label,
    }
    if (statement.kind === 'try') return {
        statement_id: statement.statement_id, kind: 'try', body: statement.body.map((child) => serverStatementToUiStatement(child, contracts, lookups)),
        retry_policy: statement.retry_policy ? {
            max_retries: serverValueToUiValue(statement.retry_policy.max_retries, lookups),
            interval: serverValueToUiValue(statement.retry_policy.interval, lookups), transient_only: true,
            author_review_fingerprint: statement.retry_policy.author_review_fingerprint,
        } : null,
        catches: statement.catches.map((clause) => ({
            catch_id: clause.catch_id, error_ids: [...clause.error_ids], error_binding: clause.error_binding,
            statements: clause.statements.map((child) => serverStatementToUiStatement(child, contracts, lookups)),
        })),
        finally_body: statement.finally_statements.map((child) => serverStatementToUiStatement(child, contracts, lookups)), step_label,
    }
    if (statement.kind === 'target_scope') return {
        statement_id: statement.statement_id, kind: 'target_scope', target: serverValueToUiValue(statement.target, lookups),
        body: statement.body.map((child) => serverStatementToUiStatement(child, contracts, lookups)), step_label,
    }
    return {
        statement_id: statement.statement_id, kind: 'listen',
        event_source: {
            kind: 'message', name: serverValueToUiValue(statement.event_source.name, lookups),
            sender: statement.event_source.sender ? serverValueToUiValue(statement.event_source.sender, lookups) : null,
        },
        receive_binding: statement.receive_binding,
        condition: statement.condition ? serverValueToUiValue(statement.condition, lookups) : null,
        handler_function_id: statement.handler_function_id,
        handler_display_name: lookups.functionNames?.[statement.handler_function_id] || '处理消息',
        handler_arguments: Object.fromEntries(Object.entries(statement.handler_arguments).map(([parameterId, value]) => [parameterId, serverValueToUiValue(value, lookups)])),
        step_label,
    }
}

function collectSymbolNames(statements: ServerProgramStatement[], result: Record<string, string>): void {
    for (const statement of statements) {
        if (statement.kind === 'call' && statement.result_binding) result[statement.result_binding.symbol_id] = statement.result_binding.display_name
        if (statement.kind === 'assignment' && statement.target.kind === 'local') result[statement.target.symbol_id] = statement.target.display_name
        if (statement.kind === 'loop') {
            for (const binding of [statement.item_binding, statement.index_binding, statement.key_binding, statement.value_binding]) {
                if (binding) result[binding.symbol_id] = binding.display_name
            }
            collectSymbolNames(statement.body, result)
        } else if (statement.kind === 'if') {
            collectSymbolNames(statement.then_statements, result)
            for (const branch of statement.additional_branches) collectSymbolNames(branch.statements, result)
            collectSymbolNames(statement.otherwise_statements, result)
        } else if (statement.kind === 'try') {
            collectSymbolNames(statement.body, result)
            for (const clause of statement.catches) {
                if (clause.error_binding) result[clause.error_binding.symbol_id] = clause.error_binding.display_name
                collectSymbolNames(clause.statements, result)
            }
            collectSymbolNames(statement.finally_statements, result)
        } else if (statement.kind === 'target_scope') collectSymbolNames(statement.body, result)
        if (statement.kind === 'listen') result[statement.receive_binding.symbol_id] = statement.receive_binding.display_name
    }
}

export function programSnapshotToUiDocument(snapshot: ProgramSnapshotDto, functions: AvailableFunctionContractDto[], lookups: ProgramProjectionLookups = {}): ProgramDocument {
    const contracts = Object.fromEntries(functions.map((contract) => [contract.function_id, contract]))
    const symbolNames = { ...(lookups.symbolNames || {}) }
    for (const parameter of snapshot.document.function.parameters) symbolNames[parameter.symbol_id] = parameter.display_name
    collectSymbolNames(snapshot.document.function.statements, symbolNames)
    const resolvedLookups = {
        ...lookups,
        symbolNames,
        fieldNames: {
            ...(snapshot.presentations?.fields || {}),
            ...(lookups.fieldNames || {}),
        },
        recordTypeNames: {
            ...(snapshot.presentations?.record_types || {}),
            ...(lookups.recordTypeNames || {}),
        },
        operationNames: {
            ...Object.fromEntries(Object.entries(snapshot.presentations?.operations || {}).map(([id, item]) => [id, item.display_name])),
            ...(lookups.operationNames || {}),
        },
        operationSyntaxNames: {
            ...Object.fromEntries(Object.entries(snapshot.presentations?.operations || {}).map(([id, item]) => [id, item.syntax_name])),
            ...(lookups.operationSyntaxNames || {}),
        },
        operationInputNames: {
            ...Object.fromEntries(Object.entries(snapshot.presentations?.operations || {}).map(([id, item]) => [id, item.input_labels])),
            ...(lookups.operationInputNames || {}),
        },
        functionNames: {
            ...Object.fromEntries(functions.map((contract) => [contract.function_id, contract.qualified_name])),
            ...(lookups.functionNames || {}),
        },
    }
    return {
        schema_version: snapshot.document.schema_version, document_id: snapshot.document.document_id, revision: snapshot.revision,
        function: {
            function_id: snapshot.document.function.function_id, display_name: snapshot.document.function.display_name,
            parameters: snapshot.document.function.parameters.map((parameter) => ({ symbol_id: parameter.symbol_id, display_name: parameter.display_name, value_type: parameter.value_type })),
            return_type: snapshot.document.function.return_type,
            statements: snapshot.document.function.statements.map((statement) => serverStatementToUiStatement(statement, contracts, resolvedLookups)),
        },
    }
}

function ensureFiniteNumber(value: unknown, label: string): number {
    const number = Number(value)
    if (!Number.isFinite(number)) throw new ProgramProjectionError(`${label}必须是有效数字`)
    return number
}
function vector(value: ProgramLiteral, count: number, label: string): number[] {
    if (!Array.isArray(value) || value.length < count) throw new ProgramProjectionError(`${label}需要 ${count} 个数字`)
    return value.slice(0, count).map((item) => ensureFiniteNumber(item, label))
}

function literalToServerValue(valueId: string, valueType: string, value: ProgramLiteral): ServerProgramValueNode {
    const normalized = normalizedType(valueType)
    if (value === null) return { value_id: valueId, kind: 'null' }
    if (normalized === 'duration') {
        const milliseconds = value && typeof value === 'object' && !Array.isArray(value) && 'milliseconds' in value
            ? ensureFiniteNumber(value.milliseconds, '持续时间') : ensureFiniteNumber(value, '持续时间')
        return { value_id: valueId, kind: 'duration', milliseconds: Math.max(0, Math.round(milliseconds)) }
    }
    if (normalized === 'bool') return { value_id: valueId, kind: 'bool', value: Boolean(value) }
    if (normalized === 'int64') return { value_id: valueId, kind: 'int64', value: Math.trunc(ensureFiniteNumber(value, '整数')) }
    // `percentage` is a semantic authoring type whose wire representation is
    // the same finite float used by the Program Service (for example 0.9).
    // Treating it as an unknown textual type made valid image thresholds fail
    // client-side and snap back to the previous/default value.
    if (normalized === 'float64' || normalized === 'percentage') {
        return { value_id: valueId, kind: 'float64', value: ensureFiniteNumber(value, normalized === 'percentage' ? '百分比' : '小数') }
    }
    if (normalized === 'date' || normalized === 'datetime' || normalized === 'time') {
        if (typeof value !== 'string') throw new ProgramProjectionError(`${valueType} 必须是文本格式`)
        return { value_id: valueId, kind: normalized, value }
    }
    if (normalized === 'point') {
        const [x, y] = vector(value, 2, '坐标')
        return { value_id: valueId, kind: 'point', x, y }
    }
    if (normalized === 'rect') {
        const [x, y, width, height] = vector(value, 4, '区域')
        return { value_id: valueId, kind: 'rect', x, y, width: Math.max(0, width), height: Math.max(0, height) }
    }
    if (normalized === 'path') {
        if (!Array.isArray(value) || !value.length) throw new ProgramProjectionError('路径至少需要一个点')
        return { value_id: valueId, kind: 'path', points: value.map((point) => {
            const [x, y] = vector(point, 2, '路径点')
            return { x, y }
        }) }
    }
    if (normalized === 'json') return { value_id: valueId, kind: 'json', payload: value }
    if (normalized === 'any') {
        if (typeof value === 'boolean') return { value_id: valueId, kind: 'bool', value }
        if (typeof value === 'number') return Number.isInteger(value)
            ? { value_id: valueId, kind: 'int64', value } : { value_id: valueId, kind: 'float64', value }
        if (typeof value === 'string') return { value_id: valueId, kind: 'string', value }
        return { value_id: valueId, kind: 'json', payload: value }
    }
    if (typeof value !== 'string') throw new ProgramProjectionError(`${valueType} 当前只接受文本值`)
    return { value_id: valueId, kind: 'string', value }
}

export function uiDraftToServerValue(valueId: string, draft: ProgramValueDraft): ServerProgramValueNode {
    const stableValueId = draft.value_id || valueId
    if (draft.kind === 'unset') return { value_id: stableValueId, kind: 'unset', expected_type: draft.value_type }
    if (draft.kind === 'literal') return literalToServerValue(stableValueId, draft.value_type, draft.value)
    if (draft.kind === 'symbol_ref') return { value_id: stableValueId, kind: 'symbol_ref', symbol_id: draft.symbol_id, value_type: draft.value_type }
    if (draft.kind === 'project_variable_ref') return { value_id: stableValueId, kind: 'project_variable_ref', variable_id: draft.variable_id, value_type: draft.value_type }
    if (draft.kind === 'asset_ref') return { value_id: stableValueId, kind: 'asset_ref', asset_id: draft.asset_id, asset_kind: draft.asset_kind }
    if (draft.kind === 'target_ref') return { value_id: stableValueId, kind: 'target_ref', target_id: draft.target_id }
    if (draft.kind === 'entity_ref') return { value_id: stableValueId, kind: 'entity_ref', reference_id: draft.reference_id, reference_type: draft.reference_type }
    if (draft.kind === 'member_access') return {
        value_id: stableValueId,
        kind: 'member_access',
        source: uiDraftToServerValue(`${stableValueId}.source`, draft.source),
        field_id: draft.field_id,
        result_type: draft.value_type,
    }
    if (draft.kind === 'list') return { value_id: stableValueId, kind: 'list', item_type: draft.item_type, items: draft.items.map((item, index) => uiDraftToServerValue(`${stableValueId}.item${index}`, item)) }
    if (draft.kind === 'map') return {
        value_id: stableValueId, kind: 'map', key_type: draft.key_type, entry_value_type: draft.entry_value_type, duplicate_policy: 'error',
        entries: draft.entries.map((entry, index) => ({
            key: uiDraftToServerValue(`${stableValueId}.key${index}`, entry.key),
            value: uiDraftToServerValue(`${stableValueId}.value${index}`, entry.value),
        })),
    }
    if (draft.kind === 'record') return {
        value_id: stableValueId, kind: 'record', record_type: draft.record_type,
        fields: Object.fromEntries(Object.entries(draft.fields).map(([fieldId, child]) => [fieldId, uiDraftToServerValue(`${stableValueId}.${fieldId}`, child)])),
    }
    if (draft.kind === 'json') return { value_id: stableValueId, kind: 'json', payload: draft.payload }
    if (draft.kind === 'computed') return {
        value_id: stableValueId, kind: 'operation', operation_id: draft.operation_id, result_type: draft.value_type,
        inputs: Object.fromEntries(Object.entries(draft.inputs).map(([inputId, child]) => [inputId, uiDraftToServerValue(`${stableValueId}.${inputId}`, child)])),
    }
    if (draft.kind === 'selector') return {
        value_id: stableValueId, kind: 'selector', bindings: draft.bindings,
        result_type: draft.result_type,
        expression: uiDraftToServerValue(`${stableValueId}.expression`, draft.expression),
    }
    if (draft.kind === 'compare') return {
        value_id: stableValueId, kind: 'compare', operator: draft.operator,
        left: uiDraftToServerValue(`${stableValueId}.left`, draft.left), right: uiDraftToServerValue(`${stableValueId}.right`, draft.right),
    }
    if (draft.kind === 'condition_group') return {
        value_id: stableValueId, kind: 'condition_group', operator: draft.operator,
        conditions: draft.conditions.map((item, index) => uiDraftToServerValue(`${stableValueId}.condition${index}`, item)),
    }
    return { value_id: stableValueId, kind: 'not', condition: uiDraftToServerValue(`${stableValueId}.condition`, draft.condition) }
}

function uiNodeToServerValue(value: ProgramValueNode): ServerProgramValueNode {
    if (value.kind === 'unset') return { value_id: value.value_id, kind: 'unset', expected_type: value.value_type }
    if (value.kind === 'literal') return literalToServerValue(value.value_id, value.value_type, value.value)
    if (value.kind === 'symbol_ref') return { value_id: value.value_id, kind: 'symbol_ref', symbol_id: value.symbol_id, value_type: value.value_type }
    if (value.kind === 'project_variable_ref') return { value_id: value.value_id, kind: 'project_variable_ref', variable_id: value.variable_id, value_type: value.value_type }
    if (value.kind === 'asset_ref') return { value_id: value.value_id, kind: 'asset_ref', asset_id: value.asset_id, asset_kind: value.asset_kind }
    if (value.kind === 'target_ref') return { value_id: value.value_id, kind: 'target_ref', target_id: value.target_id }
    if (value.kind === 'entity_ref') return { value_id: value.value_id, kind: 'entity_ref', reference_id: value.reference_id, reference_type: value.reference_type }
    if (value.kind === 'member_access') return {
        value_id: value.value_id, kind: 'member_access', source: uiNodeToServerValue(value.source),
        field_id: value.field_id, result_type: value.value_type,
    }
    if (value.kind === 'list') return {
        value_id: value.value_id, kind: 'list', item_type: value.item_type,
        items: value.items.map(uiNodeToServerValue),
    }
    if (value.kind === 'map') return {
        value_id: value.value_id, kind: 'map', key_type: value.key_type, entry_value_type: value.entry_value_type,
        duplicate_policy: 'error', entries: value.entries.map((entry) => ({
            key: uiNodeToServerValue(entry.key), value: uiNodeToServerValue(entry.value),
        })),
    }
    if (value.kind === 'record') return {
        value_id: value.value_id, kind: 'record', record_type: value.record_type,
        fields: Object.fromEntries(Object.entries(value.fields).map(([fieldId, child]) => [fieldId, uiNodeToServerValue(child)])),
    }
    if (value.kind === 'json') return { value_id: value.value_id, kind: 'json', payload: value.payload }
    if (value.kind === 'computed') return {
        value_id: value.value_id, kind: 'operation', operation_id: value.operation_id, result_type: value.value_type,
        inputs: Object.fromEntries(Object.entries(value.inputs).map(([inputId, child]) => [inputId, uiNodeToServerValue(child)])),
    }
    if (value.kind === 'selector') return {
        value_id: value.value_id, kind: 'selector', bindings: value.bindings,
        result_type: value.result_type, expression: uiNodeToServerValue(value.expression),
    }
    if (value.kind === 'compare') return {
        value_id: value.value_id, kind: 'compare', operator: value.operator,
        left: uiNodeToServerValue(value.left), right: uiNodeToServerValue(value.right),
    }
    if (value.kind === 'condition_group') return {
        value_id: value.value_id, kind: 'condition_group', operator: value.operator,
        conditions: value.conditions.map(uiNodeToServerValue),
    }
    return { value_id: value.value_id, kind: 'not', condition: uiNodeToServerValue(value.condition) }
}

/** Convert an already materialized UI value without changing its stable root identity. */
export function uiProgramValueToServerValue(value: ProgramValueNode): ServerProgramValueNode {
    return uiNodeToServerValue(value)
}

function uiBindingToServer(binding: LocalSymbolDefinition | null | undefined) {
    return binding ? {
        symbol_id: binding.symbol_id,
        display_name: binding.display_name,
        value_type: binding.value_type,
    } : null
}

function uiAssignmentTargetToServer(target: ProgramAssignmentTarget): ServerAssignmentTarget {
    if (target.kind === 'local') return {
        kind: 'local',
        symbol_id: target.symbol_id,
        display_name: target.display_name,
        value_type: target.value_type,
        declare: target.declare,
    }
    return {
        kind: 'project_variable',
        variable_id: target.variable_id,
        value_type: target.value_type,
    }
}

export function uiValueUpdateToServerCommand(update: ProgramValueUpdate): ProgramServerCommand {
    return {
        kind: 'update_argument', statement_id: update.statement_id, parameter_id: update.parameter_id,
        value: uiDraftToServerValue(update.value_id, update.next),
    }
}

/**
 * Field-specific structure commands are deliberately converted here rather than emitted as
 * arbitrary JSON patches. The server remains responsible for preserving root value/symbol IDs.
 */
export function uiStructureCommandToServerCommand(command: ProgramCommand): ProgramServerCommand | null {
    if (command.kind === 'add_if_branch') return {
        kind: command.kind,
        statement_id: command.statement_id,
        condition: uiNodeToServerValue(command.condition),
    }
    if (command.kind === 'remove_if_branch') return {
        kind: command.kind,
        statement_id: command.statement_id,
        branch_id: command.branch_id,
    }
    if (command.kind === 'update_assignment_value') return {
        kind: command.kind,
        statement_id: command.statement_id,
        value: uiNodeToServerValue(command.value),
    }
    if (command.kind === 'update_assignment_target') return {
        kind: command.kind,
        statement_id: command.statement_id,
        target: uiAssignmentTargetToServer(command.target),
        ...(command.value ? { value: uiNodeToServerValue(command.value) } : {}),
    }
    if (command.kind === 'update_if_condition') return {
        kind: command.kind,
        statement_id: command.statement_id,
        branch_id: command.branch_id ?? null,
        condition: uiNodeToServerValue(command.condition),
    }
    if (command.kind === 'update_loop') return {
        kind: command.kind,
        statement_id: command.statement_id,
        mode: command.mode,
        source: uiNodeToServerValue(command.source),
        item_binding: uiBindingToServer(command.item_binding),
        index_binding: uiBindingToServer(command.index_binding),
        key_binding: uiBindingToServer(command.key_binding),
        value_binding: uiBindingToServer(command.value_binding),
    }
    if (command.kind === 'update_return_value') return {
        kind: command.kind,
        statement_id: command.statement_id,
        value: command.value ? uiNodeToServerValue(command.value) : null,
    }
    if (command.kind === 'update_fail') return {
        kind: command.kind,
        statement_id: command.statement_id,
        error_id: command.error_id,
        message: uiNodeToServerValue(command.message),
        details: command.details ? uiNodeToServerValue(command.details) : null,
    }
    if (command.kind === 'update_try_retry_policy') return {
        kind: command.kind,
        statement_id: command.statement_id,
        retry_policy: command.retry_policy ? {
            max_retries: uiNodeToServerValue(command.retry_policy.max_retries),
            interval: uiNodeToServerValue(command.retry_policy.interval),
            transient_only: true,
            author_review_fingerprint: command.retry_policy.author_review_fingerprint ?? null,
        } : null,
    }
    if (command.kind === 'review_retry_risk') return {
        kind: command.kind,
        statement_id: command.statement_id,
    }
    if (command.kind === 'review_dangerous_call') return {
        kind: command.kind,
        statement_id: command.statement_id,
    }
    if (command.kind === 'update_catch_clause') return {
        kind: command.kind,
        statement_id: command.statement_id,
        catch_id: command.catch_id,
        error_ids: command.error_ids,
        error_binding: uiBindingToServer(command.error_binding),
    }
    if (command.kind === 'update_target_scope') return {
        kind: command.kind,
        statement_id: command.statement_id,
        target: uiNodeToServerValue(command.target),
    }
    if (command.kind === 'update_listen') return {
        kind: command.kind,
        statement_id: command.statement_id,
        event_source: {
            kind: 'message',
            name: uiNodeToServerValue(command.event_source.name),
            sender: command.event_source.sender ? uiNodeToServerValue(command.event_source.sender) : null,
        },
        receive_binding: uiBindingToServer(command.receive_binding)!,
        handler_function_id: command.handler_function_id,
        condition: command.condition ? uiNodeToServerValue(command.condition) : null,
        handler_arguments: Object.fromEntries(Object.entries(command.handler_arguments).map(([parameterId, value]) => [
            parameterId,
            uiNodeToServerValue(value),
        ])),
    }
    return null
}
