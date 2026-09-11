import type {
    AvailableProgramValue,
    ProgramAssignmentTarget,
    ProgramDocument,
    ProgramInsertionTarget,
    ProgramLiteral,
    ProgramStatement,
    ProgramSummaryPart,
    ProgramValueNode,
} from './types'
import { expressionText } from './expressionComposer'

export interface ProjectedStatementRow {
    row_kind: 'statement'; key: string; depth: number; statement: ProgramStatement; summary: string; summary_parts: ProgramSummaryPart[]; has_children: boolean
}
export interface ProjectedBranchRow {
    row_kind: 'branch'; key: string; depth: number; owner_statement_id: string
    block: 'then' | 'additional_branch' | 'otherwise' | 'body' | 'catch' | 'finally'; clause_id?: string; label: string; empty: boolean; action?: boolean
}
export type ProjectedProgramRow = ProjectedStatementRow | ProjectedBranchRow

const MAX_SUMMARY_LENGTH = 88
const COMPARE_LABELS = { eq: '等于', ne: '不等于', lt: '小于', lte: '小于等于', gt: '大于', gte: '大于等于' } as const

function truncate(value: string, maximum = MAX_SUMMARY_LENGTH): string {
    return value.length <= maximum ? value : `${value.slice(0, Math.max(0, maximum - 1))}…`
}

function durationSummary(value: ProgramLiteral): string | null {
    if (!value || Array.isArray(value) || typeof value !== 'object') return null
    const milliseconds = Number(value.milliseconds)
    if (!Number.isFinite(milliseconds) || milliseconds < 0) return null
    if (milliseconds >= 60_000 && milliseconds % 60_000 === 0) return `${milliseconds / 60_000} 分钟`
    if (milliseconds >= 1_000 && milliseconds % 1_000 === 0) return `${milliseconds / 1_000} 秒`
    return `${milliseconds} 毫秒`
}

function vectorSummary(value: ProgramLiteral, type: string): string | null {
    if (!Array.isArray(value)) return null
    if (type === 'point' && value.length >= 2) return `坐标 (${value[0]}, ${value[1]})`
    if (type === 'rect' && value.length >= 4) return `区域 (${value[0]}, ${value[1]}, ${value[2]} × ${value[3]})`
    if (type === 'path' || type === 'gesture_path') return `路径 · ${value.length} 个点`
    return null
}

function literalSummary(value: ProgramLiteral, valueType = ''): string {
    const duration = durationSummary(value)
    if (duration) return duration
    const vector = vectorSummary(value, valueType)
    if (vector) return vector
    if (value === null) return '空'
    if (typeof value === 'string') return `「${truncate(value, 40)}」`
    if (typeof value === 'boolean') return value ? '开启' : '关闭'
    if (typeof value === 'number') return valueType === 'percentage' ? `${Number((value * 100).toFixed(2))}%` : String(value)
    if (Array.isArray(value)) return `列表 · ${value.length} 项`
    return `对象 · ${Object.keys(value).length} 项`
}

export function valueSummary(value: ProgramValueNode | null | undefined): string {
    if (!value || value.kind === 'unset') return '待配置'
    if (value.summary) return truncate(value.summary)
    if (value.kind === 'literal') return literalSummary(value.value, value.value_type)
    if (value.kind === 'symbol_ref') return `局部 · ${value.display_name}`
    if (value.kind === 'project_variable_ref') return `项目 · ${value.display_name}`
    if (value.kind === 'asset_ref') return value.display_name ? `图片「${value.display_name}」` : '图片资源'
    if (value.kind === 'target_ref') return value.display_name || '运行目标'
    if (value.kind === 'entity_ref') return value.display_name || '引用'
    if (value.kind === 'member_access') return `${valueSummary(value.source)}.${value.field_name}`
    if (value.kind === 'list') return `列表 · ${value.items.length} 项`
    if (value.kind === 'map') return `字典 · ${value.entries.length} 项`
    if (value.kind === 'record') {
        const textField = (name: string): string => {
            const field = value.fields[name]
            return field?.kind === 'literal' && typeof field.value === 'string' ? field.value : ''
        }
        const numberField = (name: string): number | null => {
            const field = value.fields[name]
            return field?.kind === 'literal' && typeof field.value === 'number' ? field.value : null
        }
        if (value.record_type === 'color') {
            const red = numberField('color.field.red')
            const green = numberField('color.field.green')
            const blue = numberField('color.field.blue')
            return red === null || green === null || blue === null ? '颜色待配置' : `RGB (${red}, ${green}, ${blue})`
        }
        if (value.record_type === 'size') {
            const width = numberField('width')
            const height = numberField('height')
            return width === null || height === null ? '尺寸待配置' : `尺寸 ${width} × ${height}`
        }
        if (value.record_type === 'application_ref') {
            const platform = textField('application_ref.field.platform')
            const packageName = textField('application_ref.field.package')
            const activity = textField('application_ref.field.activity')
            if (platform === 'android_adb') return `Android 应用「${packageName}${activity ? `/${activity}` : ''}」`
            return 'Windows 应用'
        }
        if (value.record_type === 'control_selector') {
            const name = textField('control_selector.field.name')
                || textField('control_selector.field.resource_id')
                || textField('control_selector.field.control_type')
            return name ? `控件「${name}」` : '控件'
        }
        if (value.record_type === 'window_selector') {
            const title = textField('window_selector.field.title')
            const mode = textField('window_selector.field.match_mode')
            const relation = mode === 'exact' ? '标题等于' : mode === 'regex' ? '标题匹配' : '标题包含'
            return title ? `${relation}「${title}」` : '窗口条件'
        }
        return `${value.record_name || '结构化对象'} · ${Object.keys(value.fields).length} 个字段`
    }
    if (value.kind === 'json') return literalSummary(value.payload, 'json')
    if (value.kind === 'computed') return expressionText(value)
    if (value.kind === 'selector') return `逐项处理 → ${valueSummary(value.expression)}`
    if (value.kind === 'compare') return `${valueSummary(value.left)} ${COMPARE_LABELS[value.operator]} ${valueSummary(value.right)}`
    if (value.kind === 'condition_group') return `${value.operator === 'all' ? '同时满足' : '满足任一'} ${value.conditions.length} 个条件`
    return `不满足 ${valueSummary(value.condition)}`
}

export function conditionSummary(value: ProgramValueNode | null | undefined): string {
    if (value?.kind === 'literal' && value.value_type === 'bool' && typeof value.value === 'boolean') {
        return value.value ? '始终满足' : '永不满足'
    }
    return valueSummary(value)
}

function targetSummary(target: ProgramAssignmentTarget): string {
    return target.kind === 'local' ? target.display_name : target.display_name || '项目变量'
}

function configurableValueSummary(value: ProgramValueNode | null | undefined): string {
    if (!value || value.kind === 'unset') return '待配置'
    if (value.kind === 'literal' && typeof value.value === 'string') return truncate(value.value, 40)
    if (value.kind === 'computed') return expressionText(value)
    return valueSummary(value)
}

function fixed(text: string): ProgramSummaryPart { return { text } }
function dynamic(text: string): ProgramSummaryPart { return { text, dynamic: true } }
function truncateParts(parts: ProgramSummaryPart[], maximum = MAX_SUMMARY_LENGTH): ProgramSummaryPart[] {
    let remaining = maximum
    const result: ProgramSummaryPart[] = []
    for (const part of parts) {
        if (remaining <= 0) break
        if (part.text.length <= remaining) {
            result.push(part)
            remaining -= part.text.length
            continue
        }
        result.push({ ...part, text: `${part.text.slice(0, Math.max(0, remaining - 1))}…` })
        remaining = 0
    }
    return result
}

export function statementSummaryParts(statement: ProgramStatement): ProgramSummaryPart[] {
    if (statement.kind === 'call') {
        const parts = statement.summary_parts?.length
            ? statement.summary_parts.map((part) => ({ ...part }))
            : [fixed(statement.summary || statement.display_name)]
        if (statement.result_binding) parts.push(fixed(' → '), dynamic(`局部 · ${statement.result_binding.display_name}`))
        return truncateParts(parts)
    }
    if (statement.kind === 'assignment') {
        return truncateParts([fixed('设置'), dynamic(targetSummary(statement.target)), fixed('为 '), dynamic(configurableValueSummary(statement.value))])
    }
    if (statement.kind === 'if') return truncateParts([fixed('如果 '), dynamic(conditionSummary(statement.condition))])
    if (statement.kind === 'loop') {
        if (statement.mode === 'repeat') return truncateParts([fixed('重复 '), dynamic(valueSummary(statement.source)), fixed(' 次')])
        if (statement.mode === 'while') return truncateParts([fixed('当 '), dynamic(conditionSummary(statement.source)), fixed(' 时重复')])
        if (statement.mode === 'for_each_map') {
            const bindings = [statement.key_binding?.display_name, statement.value_binding?.display_name].filter(Boolean).join('、')
            return truncateParts([fixed('逐项处理 '), dynamic(valueSummary(statement.source)), fixed(' → '), dynamic(bindings || '键和值')])
        }
        return truncateParts([fixed('逐项处理 '), dynamic(valueSummary(statement.source)), fixed(' → '), dynamic(statement.item_binding?.display_name || '当前项')])
    }
    if (statement.kind === 'break') return [fixed('跳出循环')]
    if (statement.kind === 'continue') return [fixed('跳过本轮')]
    if (statement.kind === 'return') return statement.value ? truncateParts([fixed('返回 '), dynamic(configurableValueSummary(statement.value))]) : [fixed('返回')]
    if (statement.kind === 'fail') return truncateParts([fixed('结束为失败：'), dynamic(configurableValueSummary(statement.message))])
    if (statement.kind === 'try') {
        if (!statement.retry_policy) return [fixed('尝试')]
        return truncateParts([
            fixed('尝试（失败后重试 '), dynamic(valueSummary(statement.retry_policy.max_retries)), fixed(' 次，每隔 '),
            dynamic(valueSummary(statement.retry_policy.interval)), fixed('）'),
        ])
    }
    if (statement.kind === 'target_scope') return truncateParts([fixed('在'), dynamic(valueSummary(statement.target)), fixed('中执行')])
    const parts: ProgramSummaryPart[] = [fixed('收到')]
    if (statement.event_source.sender) parts.push(dynamic(configurableValueSummary(statement.event_source.sender)), fixed('发来的'))
    parts.push(dynamic(configurableValueSummary(statement.event_source.name)), fixed('时'))
    const always = statement.condition?.kind === 'literal'
        && statement.condition.value_type === 'bool'
        && statement.condition.value === true
    if (statement.condition && !always) parts.push(fixed('，且 '), dynamic(conditionSummary(statement.condition)))
    parts.push(fixed('，'), dynamic(statement.handler_display_name))
    return truncateParts(parts)
}

export function statementSummary(statement: ProgramStatement): string {
    return statementSummaryParts(statement).map((part) => part.text).join('')
}

export function statementHasChildren(statement: ProgramStatement): boolean {
    // Block owners remain expandable even while empty, because their empty
    // block rows are valid, keyboard-accessible insertion targets.
    if (statement.kind === 'if' || statement.kind === 'loop' || statement.kind === 'try' || statement.kind === 'target_scope') return true
    return false
}

function branchRow(
    result: ProjectedProgramRow[], owner: string, key: string, depth: number,
    block: ProjectedBranchRow['block'], label: string, empty: boolean, clauseId?: string, action = false,
): void {
    result.push({ row_kind: 'branch', key, depth, owner_statement_id: owner, block, clause_id: clauseId, label, empty, action })
}

function appendStatements(result: ProjectedProgramRow[], statements: ProgramStatement[], collapsed: ReadonlySet<string>, depth: number): void {
    for (const statement of statements) {
        const hasChildren = statementHasChildren(statement)
        const summaryParts = statementSummaryParts(statement)
        result.push({ row_kind: 'statement', key: statement.statement_id, depth, statement, summary: summaryParts.map((part) => part.text).join(''), summary_parts: summaryParts, has_children: hasChildren })
        if (!hasChildren || collapsed.has(statement.statement_id)) continue

        if (statement.kind === 'if') {
            branchRow(
                result,
                statement.statement_id,
                `${statement.statement_id}:then`,
                depth + 1,
                'then',
                '那么',
                statement.then_body.length === 0,
                undefined,
                false,
            )
            appendStatements(result, statement.then_body, collapsed, depth + 1)
            for (const branch of statement.additional_branches) {
                branchRow(result, statement.statement_id, branch.branch_id, depth + 1, 'additional_branch', `否则如果 ${conditionSummary(branch.condition)}`, branch.statements.length === 0, branch.branch_id)
                appendStatements(result, branch.statements, collapsed, depth + 1)
            }
            if (statement.else_body.length) {
                branchRow(result, statement.statement_id, `${statement.statement_id}:otherwise`, depth + 1, 'otherwise', '否则', false)
                appendStatements(result, statement.else_body, collapsed, depth + 1)
            } else {
                branchRow(result, statement.statement_id, `${statement.statement_id}:otherwise`, depth + 1, 'otherwise', '添加“否则”分支', false, undefined, true)
            }
        } else if (statement.kind === 'try') {
            if (!statement.body.length) {
                branchRow(result, statement.statement_id, `${statement.statement_id}:body`, depth + 1, 'body', '添加语句', false, undefined, true)
            }
            appendStatements(result, statement.body, collapsed, depth + 1)
            for (const clause of statement.catches) {
                const label = clause.error_ids.length ? `${clause.error_ids.join('、')}时` : '失败时'
                branchRow(result, statement.statement_id, clause.catch_id, depth + 1, 'catch', label, clause.statements.length === 0, clause.catch_id)
                appendStatements(result, clause.statements, collapsed, depth + 1)
            }
            if (statement.finally_body.length) {
                branchRow(result, statement.statement_id, `${statement.statement_id}:finally`, depth + 1, 'finally', '最后', false)
            } else {
                branchRow(result, statement.statement_id, `${statement.statement_id}:finally`, depth + 1, 'finally', '添加“最后”分支', false, undefined, true)
            }
            appendStatements(result, statement.finally_body, collapsed, depth + 1)
        } else if (statement.kind === 'loop' || statement.kind === 'target_scope') {
            if (!statement.body.length) {
                branchRow(result, statement.statement_id, `${statement.statement_id}:body`, depth + 1, 'body', '添加语句', true, undefined, true)
            }
            appendStatements(result, statement.body, collapsed, depth + 1)
        }
    }
}

export function projectStatements(statements: ProgramStatement[], collapsed: ReadonlySet<string> = new Set<string>()): ProjectedProgramRow[] {
    const result: ProjectedProgramRow[] = []
    appendStatements(result, statements, collapsed, 1)
    return result
}
export function visibleStatementRows(rows: ProjectedProgramRow[]): ProjectedStatementRow[] {
    return rows.filter((row): row is ProjectedStatementRow => row.row_kind === 'statement')
}

export function statementChildBlocks(statement: ProgramStatement): ProgramStatement[][] {
    if (statement.kind === 'if') return [statement.then_body, ...statement.additional_branches.map((branch) => branch.statements), statement.else_body]
    if (statement.kind === 'loop' || statement.kind === 'target_scope') return [statement.body]
    if (statement.kind === 'try') return [statement.body, ...statement.catches.map((clause) => clause.statements), statement.finally_body]
    return []
}

export function findStatement(statements: ProgramStatement[], statementId: string): ProgramStatement | null {
    for (const statement of statements) {
        if (statement.statement_id === statementId) return statement
        for (const block of statementChildBlocks(statement)) {
            const match = findStatement(block, statementId)
            if (match) return match
        }
    }
    return null
}

function withLocal(
    values: AvailableProgramValue[],
    symbol: { symbol_id: string; display_name: string; value_type: string } | null | undefined,
): AvailableProgramValue[] {
    if (!symbol || values.some((item) => item.source === 'local' && item.id === symbol.symbol_id)) return values
    return [...values, {
        source: 'local', id: symbol.symbol_id, display_name: symbol.display_name, value_type: symbol.value_type,
    }]
}

function valuesInsideStatement(statement: ProgramStatement, values: AvailableProgramValue[]): Array<{
    statements: ProgramStatement[]; values: AvailableProgramValue[]
}> {
    if (statement.kind === 'if') return [
        { statements: statement.then_body, values },
        ...statement.additional_branches.map((branch) => ({ statements: branch.statements, values })),
        { statements: statement.else_body, values },
    ]
    if (statement.kind === 'loop') {
        let loopValues = values
        for (const item of [statement.item_binding, statement.index_binding, statement.key_binding, statement.value_binding]) {
            loopValues = withLocal(loopValues, item)
        }
        return [{ statements: statement.body, values: loopValues }]
    }
    if (statement.kind === 'target_scope') return [{ statements: statement.body, values }]
    if (statement.kind === 'try') return [
        { statements: statement.body, values },
        ...statement.catches.map((clause) => ({ statements: clause.statements, values: withLocal(values, clause.error_binding) })),
        { statements: statement.finally_body, values },
    ]
    return []
}

function valuesAtStatement(
    statements: ProgramStatement[],
    statementId: string,
    initial: AvailableProgramValue[],
): AvailableProgramValue[] | null {
    let visible = initial
    for (const statement of statements) {
        if (statement.statement_id === statementId) return visible
        for (const child of valuesInsideStatement(statement, visible)) {
            const found = valuesAtStatement(child.statements, statementId, child.values)
            if (found) return found
        }
        if (statement.kind === 'call') visible = withLocal(visible, statement.result_binding)
        if (statement.kind === 'assignment' && statement.target.kind === 'local') visible = withLocal(visible, statement.target)
    }
    return null
}

/** Values visible before the selected statement, respecting block order and lexical scope. */
export function availableValuesAtStatement(document: ProgramDocument, statementId: string): AvailableProgramValue[] {
    const parameters = document.function.parameters.map((parameter) => ({
        source: 'local' as const,
        id: parameter.symbol_id,
        display_name: parameter.display_name,
        value_type: parameter.value_type,
    }))
    return valuesAtStatement(document.function.statements, statementId, parameters) || parameters
}

function valuesAfterOwnBinding(
    statement: ProgramStatement | null,
    values: AvailableProgramValue[],
): AvailableProgramValue[] {
    if (statement?.kind === 'call') return withLocal(values, statement.result_binding)
    if (statement?.kind === 'assignment' && statement.target.kind === 'local') {
        return withLocal(values, statement.target)
    }
    return values
}

/** Values visible where the next statement will be inserted. */
export function availableValuesAtInsertion(
    document: ProgramDocument,
    selectedStatementId?: string,
    insertionTarget?: ProgramInsertionTarget | null,
): AvailableProgramValue[] {
    const parameters = document.function.parameters.map((parameter) => ({
        source: 'local' as const,
        id: parameter.symbol_id,
        display_name: parameter.display_name,
        value_type: parameter.value_type,
    }))
    if (insertionTarget) {
        const parent = findStatement(document.function.statements, insertionTarget.parent_statement_id)
        let values = valuesAtStatement(document.function.statements, insertionTarget.parent_statement_id, parameters)
            || parameters
        if (parent?.kind === 'loop' && insertionTarget.block === 'body') {
            for (const item of [parent.item_binding, parent.index_binding, parent.key_binding, parent.value_binding]) {
                values = withLocal(values, item)
            }
        }
        if (parent?.kind === 'try' && insertionTarget.block === 'catch') {
            values = withLocal(values, parent.catches.find((clause) => clause.catch_id === insertionTarget.clause_id)?.error_binding)
        }
        return values
    }
    if (selectedStatementId) {
        return valuesAfterOwnBinding(
            findStatement(document.function.statements, selectedStatementId),
            availableValuesAtStatement(document, selectedStatementId),
        )
    }
    return document.function.statements.reduce<AvailableProgramValue[]>(
        (values, statement) => valuesAfterOwnBinding(statement, values),
        parameters,
    )
}
