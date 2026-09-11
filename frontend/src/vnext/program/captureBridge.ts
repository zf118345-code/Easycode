import type {
    AssetCategoryId,
    AssetDefinition,
    ParameterUiAction,
    PlatformId,
    TargetDefinition,
    WorkspaceIdentity,
} from '../types'
import type { ProgramSnapshotDto, ServerProgramStatement, ServerProgramValueNode } from './serverTypes'
import type {
    ProgramCaptureEnvelope,
    ProgramCommandEnvelope,
    ProgramFunctionContract,
    ProgramValueDraft,
} from './types'
import { colorRecordFields } from '../colorValue'

const STABLE_ID = /^[A-Za-z][A-Za-z0-9_.-]{0,159}$/
const CAPTURE_ACTION_IDS = new Set([
    'choose-resource',
    'capture-image',
    'pick-point',
    'pick-region',
    'pick-color',
    'capture-control',
    'capture-path',
])

export interface ProgramCaptureContext {
    workspace: WorkspaceIdentity
    snapshot: ProgramSnapshotDto
    functionContracts: Record<string, ProgramFunctionContract>
    platform: PlatformId
    target: TargetDefinition | null
}

export interface ProgramCaptureDestination {
    request_id: string
    workspace_id: string
    workspace_generation: number
    project_id: string
    function_id: string
    document_id: string
    base_revision: string
    statement_id: string
    parameter_id: string
    parameter_display_name: string
    value_id: string
    expected_value_type: string
    action: ParameterUiAction
    platform: PlatformId
    target_id: string | null
}

export class ProgramCaptureBridgeError extends Error {
    constructor(message: string) {
        super(message)
        this.name = 'ProgramCaptureBridgeError'
    }
}

function childStatements(statement: ServerProgramStatement): ServerProgramStatement[][] {
    if (statement.kind === 'if') return [
        statement.then_statements,
        ...statement.additional_branches.map((branch) => branch.statements),
        statement.otherwise_statements,
    ]
    if (statement.kind === 'loop' || statement.kind === 'target_scope') return [statement.body]
    if (statement.kind === 'try') return [
        statement.body,
        ...statement.catches.map((clause) => clause.statements),
        statement.finally_statements,
    ]
    return []
}

function findStatement(statements: ServerProgramStatement[], statementId: string): ServerProgramStatement | null {
    for (const statement of statements) {
        if (statement.statement_id === statementId) return statement
        for (const children of childStatements(statement)) {
            const found = findStatement(children, statementId)
            if (found) return found
        }
    }
    return null
}

interface StatementTargetResolution {
    found: boolean
    targetId: string | null
}

function targetReferenceId(value: ServerProgramValueNode): string | null {
    return value.kind === 'target_ref' && value.target_id.trim() ? value.target_id : null
}

function resolveTargetInStatements(
    statements: ServerProgramStatement[],
    statementId: string,
    inheritedTargetId: string | null,
): StatementTargetResolution {
    for (const statement of statements) {
        const statementTargetId = statement.kind === 'target_scope'
            ? targetReferenceId(statement.target)
            : inheritedTargetId
        if (statement.statement_id === statementId) return { found: true, targetId: statementTargetId }
        for (const children of childStatements(statement)) {
            const resolved = resolveTargetInStatements(children, statementId, statementTargetId)
            if (resolved.found) return resolved
        }
    }
    return { found: false, targetId: null }
}

/** Resolve the target that is active at a statement, including the nearest target-scope ancestor. */
export function resolveStatementTargetId(
    snapshot: ProgramSnapshotDto,
    statementId: string,
    defaultTargetId: string | null,
): string | null {
    const resolved = resolveTargetInStatements(
        snapshot.document.function.statements,
        statementId,
        defaultTargetId,
    )
    return resolved.found ? resolved.targetId : null
}

function unwrapOptional(valueType: string): string {
    let current = valueType.trim()
    while (current.startsWith('optional<') && current.endsWith('>')) current = current.slice(9, -1).trim()
    return current
}

function actionValueKind(action: ParameterUiAction): 'asset' | 'point' | 'rect' | 'color' | 'control' | 'path' {
    if (action.id === 'choose-resource' || action.id === 'capture-image') return 'asset'
    if (action.id === 'pick-point' && action.capture_kind === 'point') return 'point'
    if (action.id === 'pick-region' && action.capture_kind === 'region') return 'rect'
    if (action.id === 'pick-color' && action.capture_kind === 'color') return 'color'
    if (action.id === 'capture-control' && action.capture_kind === 'control') return 'control'
    if (action.id === 'capture-path' && action.capture_kind === 'path') return 'path'
    throw new ProgramCaptureBridgeError('函数契约中的捕获动作不完整，当前操作未执行')
}

function assertCompatibleType(action: ParameterUiAction, valueType: string): void {
    const normalized = unwrapOptional(valueType)
    const expected = actionValueKind(action)
    const compatibleByKind: Record<typeof expected, boolean> = {
        asset: normalized === 'asset_ref' || normalized.startsWith('asset_ref<'),
        point: normalized === 'point',
        rect: normalized === 'rect',
        color: normalized === 'color',
        control: normalized === 'control_selector',
        path: normalized === 'path' || normalized === 'gesture_path',
    }
    const compatible = compatibleByKind[expected]
    if (!compatible) throw new ProgramCaptureBridgeError('捕获动作与当前参数类型不匹配，当前值没有修改')
}

function argumentForDestination(
    context: ProgramCaptureContext,
    statementId: string,
    parameterId: string,
): { statement: Extract<ServerProgramStatement, { kind: 'call' }>; value: ServerProgramValueNode; contract: ProgramFunctionContract } {
    const statement = findStatement(context.snapshot.document.function.statements, statementId)
    if (!statement || statement.kind !== 'call') throw new ProgramCaptureBridgeError('原函数调用已经不存在，请重新选择参数')
    const contract = context.functionContracts[statement.function_id]
    if (!contract) throw new ProgramCaptureBridgeError('原函数契约已经不可用，请重新选择参数')
    const value = statement.arguments[parameterId]
    if (!value) throw new ProgramCaptureBridgeError('原参数已经不存在，请重新选择参数')
    return { statement, value, contract }
}

function contractAction(
    contract: ProgramFunctionContract,
    parameterId: string,
    requested: ParameterUiAction,
): { action: ParameterUiAction; valueType: string; displayName: string } {
    const parameter = contract.parameters.find((item) => item.parameter_id === parameterId)
    if (!parameter) throw new ProgramCaptureBridgeError('原参数契约已经不存在，请重新选择参数')
    if (!CAPTURE_ACTION_IDS.has(requested.id)) throw new ProgramCaptureBridgeError('当前动作不属于已接通的捕获协议')
    const action = parameter.ui?.actions?.find((item) => item.id === requested.id)
    if (!action || action.capture_kind !== requested.capture_kind) {
        throw new ProgramCaptureBridgeError('该参数没有开放此捕获动作')
    }
    assertCompatibleType(action, parameter.value_type)
    return { action: { ...action }, valueType: parameter.value_type, displayName: parameter.display_name }
}

function requestId(): string {
    const uuid = globalThis.crypto?.randomUUID?.().replaceAll('-', '')
    return `program_capture_${uuid || `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`}`
}

export function createProgramCaptureDestination(
    envelope: ProgramCaptureEnvelope,
    context: ProgramCaptureContext,
): ProgramCaptureDestination {
    if (envelope.document_id !== context.snapshot.document.document_id || envelope.base_revision !== context.snapshot.revision) {
        throw new ProgramCaptureBridgeError('参数检查器已经过期，请重新选择当前语句')
    }
    const { value, contract } = argumentForDestination(
        context,
        envelope.request.statement_id,
        envelope.request.parameter_id,
    )
    if (value.value_id !== envelope.request.value_id) {
        throw new ProgramCaptureBridgeError('参数值已经变化，请重新发起捕获')
    }
    const resolved = contractAction(contract, envelope.request.parameter_id, envelope.request.action)
    if (resolved.action.platforms?.length && !resolved.action.platforms.includes(context.platform)) {
        throw new ProgramCaptureBridgeError('当前平台没有开放此捕获动作')
    }
    if (resolved.action.id !== 'choose-resource' && !context.target) {
        throw new ProgramCaptureBridgeError('请先配置运行目标')
    }
    return {
        request_id: requestId(),
        workspace_id: context.workspace.workspace_id,
        workspace_generation: context.workspace.generation,
        project_id: context.workspace.project_id,
        function_id: context.snapshot.document.function.function_id,
        document_id: context.snapshot.document.document_id,
        base_revision: context.snapshot.revision,
        statement_id: envelope.request.statement_id,
        parameter_id: envelope.request.parameter_id,
        parameter_display_name: resolved.displayName,
        value_id: envelope.request.value_id,
        expected_value_type: resolved.valueType,
        action: resolved.action,
        platform: context.platform,
        target_id: context.target?.target_id || null,
    }
}

export function validateProgramCaptureDestination(
    destination: ProgramCaptureDestination,
    context: ProgramCaptureContext,
): void {
    if (
        destination.workspace_id !== context.workspace.workspace_id
        || destination.workspace_generation !== context.workspace.generation
        || destination.project_id !== context.workspace.project_id
    ) throw new ProgramCaptureBridgeError('项目已经切换，旧捕获结果已拒绝')
    if (
        destination.function_id !== context.snapshot.document.function.function_id
        || destination.document_id !== context.snapshot.document.document_id
        || destination.base_revision !== context.snapshot.revision
    ) throw new ProgramCaptureBridgeError('项目函数已经变化，旧捕获结果已拒绝')
    if (destination.platform !== context.platform) throw new ProgramCaptureBridgeError('运行平台已经变化，旧捕获结果已拒绝')
    if (destination.action.id !== 'choose-resource' && destination.target_id !== (context.target?.target_id || null)) {
        throw new ProgramCaptureBridgeError('运行目标已经变化，旧捕获结果已拒绝')
    }
    const { value, contract } = argumentForDestination(context, destination.statement_id, destination.parameter_id)
    if (value.value_id !== destination.value_id) throw new ProgramCaptureBridgeError('参数已经被替换，旧捕获结果已拒绝')
    const resolved = contractAction(contract, destination.parameter_id, destination.action)
    if (resolved.valueType !== destination.expected_value_type) {
        throw new ProgramCaptureBridgeError('参数类型已经变化，旧捕获结果已拒绝')
    }
}

function assetKind(valueType: string): string {
    const normalized = unwrapOptional(valueType)
    const match = /^asset_ref<([^>]+)>$/.exec(normalized)
    return match?.[1] || 'image'
}

export function valueDraftForAsset(
    destination: ProgramCaptureDestination,
    asset: AssetDefinition,
): ProgramValueDraft {
    if (actionValueKind(destination.action) !== 'asset') {
        throw new ProgramCaptureBridgeError('当前参数不接受资源引用')
    }
    if (!STABLE_ID.test(asset.asset_id)) throw new ProgramCaptureBridgeError('资源 ID 无效，当前值没有修改')
    return {
        kind: 'asset_ref',
        value_type: destination.expected_value_type,
        asset_id: asset.asset_id,
        asset_kind: assetKind(destination.expected_value_type),
        display_name: asset.display_name,
    }
}

function finiteTuple(value: unknown, count: number, label: string): number[] {
    if (!Array.isArray(value) || value.length < count) throw new ProgramCaptureBridgeError(`${label}捕获结果不完整`)
    const result = value.slice(0, count).map(Number)
    if (result.some((item) => !Number.isFinite(item))) throw new ProgramCaptureBridgeError(`${label}捕获结果包含无效数字`)
    return result
}

function captureAssetId(payload: Record<string, unknown>): string {
    const ids = Array.isArray(payload.asset_ids) ? payload.asset_ids : []
    const refs = Array.isArray(payload.asset_refs) ? payload.asset_refs : []
    const assetId = String(ids[0] || refs[0] || '').replace(/^asset:\/\//, '')
    if (!STABLE_ID.test(assetId)) throw new ProgramCaptureBridgeError('图片已保存，但捕获宿主没有返回有效资源 ID')
    return assetId
}

function sampledPath(points: number[][], maximum: number | undefined): number[][] {
    if (!maximum || points.length <= maximum) return points
    return Array.from({ length: maximum }, (_, index) => {
        const source = Math.round(index * (points.length - 1) / (maximum - 1))
        return points[source]
    })
}

function controlSelectorDraft(payload: Record<string, unknown>, expectedType: string): ProgramValueDraft {
    const raw = payload.selector
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
        throw new ProgramCaptureBridgeError('控件宿主没有返回强类型选择器，当前值没有修改')
    }
    const selector = raw as Record<string, unknown>
    const prefix = 'control_selector.field.'
    const fields: Record<string, ProgramValueDraft> = {}
    const stringFields = [
        'provider', 'target_id', 'package_name', 'resource_id', 'name', 'text',
        'content_description', 'automation_id', 'class_name', 'control_type',
        'selector_id', 'primary_strategy_id', 'captured_space_version',
    ]
    for (const name of stringFields) {
        const value = selector[`${prefix}${name}`]
        if (typeof value === 'string') fields[`${prefix}${name}`] = { kind: 'literal', value_type: 'string', value }
    }
    for (const name of ['schema_version', 'index']) {
        const value = Number(selector[`${prefix}${name}`])
        if (Number.isSafeInteger(value) && value >= 0) fields[`${prefix}${name}`] = { kind: 'literal', value_type: 'int64', value }
    }
    const rect = selector[`${prefix}rect`]
    if (rect && typeof rect === 'object' && !Array.isArray(rect)) {
        const value = rect as Record<string, unknown>
        const tuple = [value.x, value.y, value.width, value.height].map(Number)
        if (tuple.every(Number.isFinite) && tuple[2] >= 0 && tuple[3] >= 0) {
            fields[`${prefix}rect`] = { kind: 'literal', value_type: 'rect', value: tuple }
        }
    }
    const path = selector[`${prefix}path`]
    if (Array.isArray(path) && path.every((item) => Number.isSafeInteger(Number(item)) && Number(item) >= 0)) {
        fields[`${prefix}path`] = {
            kind: 'list', value_type: 'list<int64>', item_type: 'int64',
            items: path.map((item) => ({ kind: 'literal', value_type: 'int64', value: Number(item) })),
        }
    }
    const ancestors = selector[`${prefix}ancestor_path`]
    if (ancestors !== undefined) {
        fields[`${prefix}ancestor_path`] = { kind: 'json', value_type: 'json_value', payload: ancestors as never }
    }
    const strategies = selector[`${prefix}strategies`]
    if (strategies !== undefined) {
        fields[`${prefix}strategies`] = { kind: 'json', value_type: 'json_value', payload: strategies as never }
    }
    const stable = ['resource_id', 'automation_id', 'name', 'text', 'content_description', 'class_name']
        .some((name) => String(selector[`${prefix}${name}`] || '').trim())
        || (Array.isArray(path) && path.length > 0)
        || (Array.isArray(strategies) && strategies.length > 0)
    if (!stable) throw new ProgramCaptureBridgeError('控件选择器缺少可重新定位的稳定字段，当前值没有修改')
    return { kind: 'record', value_type: expectedType, record_type: 'control_selector', fields }
}

export function valueDraftForCaptureResult(
    destination: ProgramCaptureDestination,
    payload: Record<string, unknown>,
    assets: AssetDefinition[] = [],
): ProgramValueDraft {
    const kind = actionValueKind(destination.action)
    if (kind === 'asset') {
        const assetId = captureAssetId(payload)
        const asset = assets.find((item) => item.asset_id === assetId)
        if (!asset) throw new ProgramCaptureBridgeError('图片已保存，但资源注册表尚未确认该资源')
        return valueDraftForAsset(destination, asset)
    }
    if (kind === 'point') {
        const point = finiteTuple(payload.point, 2, '坐标')
        return { kind: 'literal', value_type: destination.expected_value_type, value: point }
    }
    if (kind === 'rect') {
        const rects = Array.isArray(payload.rects) ? payload.rects : []
        const rect = finiteTuple(rects[0], 4, '区域')
        if (rect[2] < 0 || rect[3] < 0) throw new ProgramCaptureBridgeError('区域宽高不能为负数')
        return { kind: 'literal', value_type: destination.expected_value_type, value: rect }
    }
    if (kind === 'color') {
        const raw = payload.color
        if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
            throw new ProgramCaptureBridgeError('取色结果不完整，当前值没有修改')
        }
        const source = raw as Record<string, unknown>
        const color = {
            red: Number(source.red), green: Number(source.green), blue: Number(source.blue),
            alpha: source.alpha === undefined ? 255 : Number(source.alpha),
        }
        if (Object.values(color).some((value) => !Number.isInteger(value) || value < 0 || value > 255)) {
            throw new ProgramCaptureBridgeError('取色结果包含无效通道，当前值没有修改')
        }
        return {
            kind: 'record', value_type: destination.expected_value_type,
            record_type: 'color', record_name: '颜色',
            field_names: {
                'color.field.red': '红', 'color.field.green': '绿',
                'color.field.blue': '蓝', 'color.field.alpha': '透明度',
            },
            fields: colorRecordFields(color),
        }
    }
    if (kind === 'path') {
        if (!Array.isArray(payload.path)) throw new ProgramCaptureBridgeError('路径捕获结果不完整')
        const points = payload.path.map((point) => finiteTuple(point, 2, '路径点'))
        const minimum = Math.max(2, destination.action.min_points || 2)
        if (points.length < minimum) throw new ProgramCaptureBridgeError(`拖拽路径至少需要 ${minimum} 个点`)
        const maximum = destination.action.max_points && destination.action.max_points >= minimum
            ? Math.floor(destination.action.max_points) : undefined
        return {
            kind: 'literal',
            value_type: destination.expected_value_type,
            value: sampledPath(points, maximum),
        }
    }
    const expectedReferenceType = destination.action.result_reference_type || unwrapOptional(destination.expected_value_type)
    if (expectedReferenceType !== 'control_selector') throw new ProgramCaptureBridgeError('控件捕获结果类型与参数契约不匹配')
    return controlSelectorDraft(payload, destination.expected_value_type)
}

export function captureCommandEnvelope(
    destination: ProgramCaptureDestination,
    next: ProgramValueDraft,
): ProgramCommandEnvelope {
    return {
        document_id: destination.document_id,
        base_revision: destination.base_revision,
        command: {
            kind: 'update_value',
            statement_id: destination.statement_id,
            parameter_id: destination.parameter_id,
            value_id: destination.value_id,
            next,
        },
    }
}

export function captureDefaultCategory(destination: ProgramCaptureDestination): AssetCategoryId {
    return destination.action.default_category || 'image'
}

export function focusProgramCaptureOrigin(
    destination: ProgramCaptureDestination,
    root: ParentNode = document,
): boolean {
    const field = root.querySelector<HTMLElement>(`[data-value-id="${destination.value_id}"]`)
    const action = field?.querySelector<HTMLButtonElement>(`[data-parameter-action-id="${destination.action.id}"]`)
    const target = action || field?.querySelector<HTMLElement>('input,select,textarea,button')
    target?.focus()
    return Boolean(target)
}
