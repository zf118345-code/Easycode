import { programValueToDraft } from './valueFactories'
import { statementSummary } from './projection'
import type {
    ProgramCommand,
    ProgramFunctionContract,
    ProgramStatement,
    ProgramValueNode,
    RetryPolicyDefinition,
} from './types'

function directValues(statement: ProgramStatement): Array<{ parameter_id: string; value: ProgramValueNode }> {
    if (statement.kind === 'call') return Object.entries(statement.arguments).map(([parameter_id, value]) => ({ parameter_id, value }))
    if (statement.kind === 'assignment') return [{ parameter_id: 'assignment.value', value: statement.value }]
    if (statement.kind === 'if') return [
        { parameter_id: 'if.condition', value: statement.condition },
        ...statement.additional_branches.map((branch) => ({ parameter_id: `if.branch.${branch.branch_id}`, value: branch.condition })),
    ]
    if (statement.kind === 'loop') return [{ parameter_id: 'loop.source', value: statement.source }]
    if (statement.kind === 'return') return statement.value ? [{ parameter_id: 'return.value', value: statement.value }] : []
    if (statement.kind === 'fail') return [
        { parameter_id: 'fail.message', value: statement.message },
        ...(statement.details ? [{ parameter_id: 'fail.details', value: statement.details }] : []),
    ]
    if (statement.kind === 'try') return statement.retry_policy ? [
        { parameter_id: 'try.max_retries', value: statement.retry_policy.max_retries },
        { parameter_id: 'try.interval', value: statement.retry_policy.interval },
    ] : []
    if (statement.kind === 'target_scope') return [{ parameter_id: 'target_scope.target', value: statement.target }]
    if (statement.kind === 'break' || statement.kind === 'continue') return []
    return [
        { parameter_id: 'listen.message_name', value: statement.event_source.name },
        ...(statement.event_source.sender ? [{ parameter_id: 'listen.sender', value: statement.event_source.sender }] : []),
        ...(statement.condition ? [{ parameter_id: 'listen.condition', value: statement.condition }] : []),
        ...Object.entries(statement.handler_arguments).map(([parameter_id, value]) => ({ parameter_id, value })),
    ]
}

export function directProgramValue(
    statement: ProgramStatement,
    parameterId: string,
    valueId: string,
): ProgramValueNode | null {
    const match = directValues(statement).find((item) => item.parameter_id === parameterId && item.value.value_id === valueId)
    return match?.value || null
}

export function programValueEditorTitle(
    statement: ProgramStatement,
    parameterId: string,
    contracts: Record<string, ProgramFunctionContract>,
): string {
    const context = statementSummary(statement)
    if (statement.kind === 'call') {
        const field = contracts[statement.function_id]?.parameters.find((item) => item.parameter_id === parameterId)?.display_name || '参数'
        return `${context} · ${field}`
    }
    if (parameterId === 'assignment.value') return `${context} · 赋予的值`
    if (parameterId === 'if.condition') return `${context} · 条件`
    if (parameterId.startsWith('if.branch.') && statement.kind === 'if') {
        const branchId = parameterId.slice('if.branch.'.length)
        const index = statement.additional_branches.findIndex((branch) => branch.branch_id === branchId)
        return `${context} · 否则如果 ${index >= 0 ? index + 1 : ''}`.trim()
    }
    if (parameterId === 'loop.source') return `${context} · 循环条件或集合`
    if (parameterId === 'return.value') return `${context} · 返回值`
    if (parameterId === 'fail.message') return `${context} · 给用户的消息`
    if (parameterId === 'fail.details') return `${context} · 诊断详情`
    if (parameterId === 'try.max_retries') return `${context} · 最多重试`
    if (parameterId === 'try.interval') return `${context} · 重试间隔`
    if (parameterId === 'target_scope.target') return `${context} · 运行目标`
    if (parameterId === 'listen.message_name') return `${context} · 消息名称`
    if (parameterId === 'listen.condition') return `${context} · 处理条件`
    const handler = statement.kind === 'listen' ? contracts[statement.handler_function_id] : null
    const field = handler?.parameters.find((item) => item.parameter_id === parameterId)?.display_name || '处理函数参数'
    return `${context} · ${field}`
}

export function programValueEditorConstraints(
    statement: ProgramStatement,
    parameterId: string,
    contracts: Record<string, ProgramFunctionContract>,
): Record<string, unknown> {
    if (statement.kind !== 'call') return {}
    return contracts[statement.function_id]?.parameters.find((item) => item.parameter_id === parameterId)?.constraints || {}
}

export function isConditionValueDestination(statement: ProgramStatement, parameterId: string): boolean {
    if (statement.kind === 'if') return parameterId === 'if.condition' || parameterId.startsWith('if.branch.')
    if (statement.kind === 'loop') return statement.mode === 'while' && parameterId === 'loop.source'
    return statement.kind === 'listen' && parameterId === 'listen.condition'
}

function updatedRetryPolicy(
    policy: RetryPolicyDefinition,
    valueId: string,
    next: ProgramValueNode,
): RetryPolicyDefinition {
    if (policy.max_retries.value_id === valueId) return { ...policy, max_retries: next }
    return { ...policy, interval: next }
}

export function replaceDirectProgramValue(
    statement: ProgramStatement,
    parameterId: string,
    valueId: string,
    next: ProgramValueNode,
): ProgramCommand | null {
    if (next.value_id !== valueId || !directProgramValue(statement, parameterId, valueId)) return null
    if (statement.kind === 'call') return {
        kind: 'update_value', statement_id: statement.statement_id, parameter_id: parameterId,
        value_id: valueId, next: programValueToDraft(next),
    }
    if (statement.kind === 'assignment') return { kind: 'update_assignment_value', statement_id: statement.statement_id, value: next }
    if (statement.kind === 'if') return {
        kind: 'update_if_condition', statement_id: statement.statement_id,
        branch_id: parameterId === 'if.condition' ? null : parameterId.slice('if.branch.'.length), condition: next,
    }
    if (statement.kind === 'loop') return {
        kind: 'update_loop', statement_id: statement.statement_id, mode: statement.mode, source: next,
        item_binding: statement.item_binding, index_binding: statement.index_binding,
        key_binding: statement.key_binding, value_binding: statement.value_binding,
    }
    if (statement.kind === 'return') return { kind: 'update_return_value', statement_id: statement.statement_id, value: next }
    if (statement.kind === 'fail') return {
        kind: 'update_fail', statement_id: statement.statement_id, error_id: statement.error_id,
        message: parameterId === 'fail.message' ? next : statement.message,
        details: parameterId === 'fail.details' ? next : statement.details,
    }
    if (statement.kind === 'try' && statement.retry_policy) return {
        kind: 'update_try_retry_policy', statement_id: statement.statement_id,
        retry_policy: updatedRetryPolicy(statement.retry_policy, valueId, next),
    }
    if (statement.kind === 'target_scope') return { kind: 'update_target_scope', statement_id: statement.statement_id, target: next }
    if (statement.kind !== 'listen') return null
    if (statement.event_source.name.value_id === valueId) return {
        kind: 'update_listen', statement_id: statement.statement_id,
        event_source: { ...statement.event_source, name: next }, receive_binding: statement.receive_binding,
        handler_function_id: statement.handler_function_id, condition: statement.condition,
        handler_arguments: statement.handler_arguments,
    }
    if (statement.event_source.sender?.value_id === valueId) return {
        kind: 'update_listen', statement_id: statement.statement_id,
        event_source: { ...statement.event_source, sender: next }, receive_binding: statement.receive_binding,
        handler_function_id: statement.handler_function_id, condition: statement.condition,
        handler_arguments: statement.handler_arguments,
    }
    if (statement.condition?.value_id === valueId) return {
        kind: 'update_listen', statement_id: statement.statement_id,
        event_source: statement.event_source, receive_binding: statement.receive_binding,
        handler_function_id: statement.handler_function_id, condition: next,
        handler_arguments: statement.handler_arguments,
    }
    return {
        kind: 'update_listen', statement_id: statement.statement_id,
        event_source: statement.event_source, receive_binding: statement.receive_binding,
        handler_function_id: statement.handler_function_id, condition: statement.condition,
        handler_arguments: { ...statement.handler_arguments, [parameterId]: next },
    }
}
