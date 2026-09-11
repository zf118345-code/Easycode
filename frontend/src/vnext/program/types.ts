import type {
    AssetDefinition,
    ParameterControlType,
    ParameterUiAction,
    ParameterUiContract,
    PlatformId,
} from '../types'

export type ProgramRevision = string
export type ProgramLiteral = null | string | number | boolean | ProgramLiteral[] | { [key: string]: ProgramLiteral }
export type ProgramCompareOperator = 'eq' | 'ne' | 'lt' | 'lte' | 'gt' | 'gte'

interface ProgramValueBase { value_id: string; value_type: string; summary?: string }
export interface UnsetValueNode extends ProgramValueBase { kind: 'unset' }
export interface LiteralValueNode extends ProgramValueBase { kind: 'literal'; value: ProgramLiteral }
export interface SymbolReferenceValueNode extends ProgramValueBase { kind: 'symbol_ref'; symbol_id: string; display_name: string }
export interface ProjectVariableReferenceValueNode extends ProgramValueBase { kind: 'project_variable_ref'; variable_id: string; display_name: string }
export interface AssetReferenceValueNode extends ProgramValueBase { kind: 'asset_ref'; asset_id: string; asset_kind: string; display_name?: string }
export interface TargetReferenceValueNode extends ProgramValueBase { kind: 'target_ref'; target_id: string; display_name?: string }
export interface EntityReferenceValueNode extends ProgramValueBase { kind: 'entity_ref'; reference_id: string; reference_type: string; display_name?: string }
export interface MemberAccessValueNode extends ProgramValueBase {
    kind: 'member_access'; source: ProgramValueNode; field_id: string; field_name: string
}
export interface ListValueNode extends ProgramValueBase { kind: 'list'; item_type: string; items: ProgramValueNode[] }
export interface MapValueEntry { key: ProgramValueNode; value: ProgramValueNode }
export interface MapValueNode extends ProgramValueBase {
    kind: 'map'; key_type: string; entry_value_type: string; entries: MapValueEntry[]; duplicate_policy: 'error'
}
export interface RecordValueNode extends ProgramValueBase {
    kind: 'record'; record_type: string; record_name?: string
    field_names?: Record<string, string>; fields: Record<string, ProgramValueNode>
}
export interface JsonValueNode extends ProgramValueBase { kind: 'json'; payload: ProgramLiteral }
export interface ComputedValueNode extends ProgramValueBase {
    kind: 'computed'; operation_id: string; operation_name: string
    operation_input_names?: Record<string, string>; inputs: Record<string, ProgramValueNode>
}
export interface SelectorBindingDefinition extends LocalSymbolDefinition { role: 'item' | 'index' | 'key' | 'value' }
export interface SelectorValueNode extends ProgramValueBase {
    kind: 'selector'; bindings: SelectorBindingDefinition[]; result_type: string; expression: ProgramValueNode
}
export interface CompareValueNode extends ProgramValueBase {
    kind: 'compare'; operator: ProgramCompareOperator; left: ProgramValueNode; right: ProgramValueNode
}
export interface ConditionGroupValueNode extends ProgramValueBase {
    kind: 'condition_group'; operator: 'all' | 'any'; conditions: ProgramValueNode[]
}
export interface NotValueNode extends ProgramValueBase { kind: 'not'; condition: ProgramValueNode }

export type ProgramValueNode = UnsetValueNode | LiteralValueNode | SymbolReferenceValueNode
    | ProjectVariableReferenceValueNode | AssetReferenceValueNode | TargetReferenceValueNode
    | EntityReferenceValueNode | MemberAccessValueNode | ListValueNode | MapValueNode
    | RecordValueNode | JsonValueNode | ComputedValueNode | SelectorValueNode | CompareValueNode
    | ConditionGroupValueNode | NotValueNode

/** Root identity is preserved by update commands; nested typed nodes are recursively shaped as drafts. */
type ProgramValueDraftIdentity = { value_id?: string }
export type ProgramValueDraft =
    | (Omit<UnsetValueNode, 'value_id' | 'summary'> & ProgramValueDraftIdentity)
    | (Omit<LiteralValueNode, 'value_id' | 'summary'> & ProgramValueDraftIdentity)
    | (Omit<SymbolReferenceValueNode, 'value_id' | 'summary'> & ProgramValueDraftIdentity)
    | (Omit<ProjectVariableReferenceValueNode, 'value_id' | 'summary'> & ProgramValueDraftIdentity)
    | (Omit<AssetReferenceValueNode, 'value_id' | 'summary'> & ProgramValueDraftIdentity)
    | (Omit<TargetReferenceValueNode, 'value_id' | 'summary'> & ProgramValueDraftIdentity)
    | (Omit<EntityReferenceValueNode, 'value_id' | 'summary'> & ProgramValueDraftIdentity)
    | (Omit<MemberAccessValueNode, 'value_id' | 'summary' | 'source'> & ProgramValueDraftIdentity & { source: ProgramValueDraft })
    | (Omit<ListValueNode, 'value_id' | 'summary' | 'items'> & ProgramValueDraftIdentity & { items: ProgramValueDraft[] })
    | (Omit<MapValueNode, 'value_id' | 'summary' | 'entries'> & {
        value_id?: string
        entries: Array<{ key: ProgramValueDraft; value: ProgramValueDraft }>
    })
    | (Omit<RecordValueNode, 'value_id' | 'summary' | 'fields'> & {
        value_id?: string
        fields: Record<string, ProgramValueDraft>
    })
    | (Omit<JsonValueNode, 'value_id' | 'summary'> & ProgramValueDraftIdentity)
    | (Omit<ComputedValueNode, 'value_id' | 'summary' | 'inputs'> & {
        value_id?: string
        inputs: Record<string, ProgramValueDraft>
    })
    | (Omit<SelectorValueNode, 'value_id' | 'summary' | 'expression'> & {
        value_id?: string
        expression: ProgramValueDraft
    })
    | (Omit<CompareValueNode, 'value_id' | 'summary' | 'left' | 'right'> & {
        value_id?: string
        left: ProgramValueDraft
        right: ProgramValueDraft
    })
    | (Omit<ConditionGroupValueNode, 'value_id' | 'summary' | 'conditions'> & {
        value_id?: string
        conditions: ProgramValueDraft[]
    })
    | (Omit<NotValueNode, 'value_id' | 'summary' | 'condition'> & {
        value_id?: string
        condition: ProgramValueDraft
    })

export interface LocalSymbolDefinition { symbol_id: string; display_name: string; value_type: string }
export interface ProgramResultBinding extends LocalSymbolDefinition { declare: boolean }
export type ProgramAssignmentTarget =
    | (LocalSymbolDefinition & { kind: 'local'; declare: boolean })
    | { kind: 'project_variable'; variable_id: string; value_type: string; display_name: string }

export type ProgramStatementKind = 'call' | 'assignment' | 'if' | 'loop' | 'break' | 'continue' | 'return' | 'fail' | 'try' | 'target_scope' | 'listen'
interface ProgramStatementBase { statement_id: string; kind: ProgramStatementKind; step_label?: string }
export interface ProgramSummaryPart {
    text: string
    dynamic?: boolean
    value?: ProgramValueNode
    parameter_id?: string
    role?: string
    presentation?: string
}
export interface CallStatement extends Omit<ProgramStatementBase, 'kind'> {
    kind: 'call'; function_id: string; display_name: string; summary?: string; summary_parts?: ProgramSummaryPart[]
    arguments: Record<string, ProgramValueNode>; result_binding?: ProgramResultBinding | null
    author_review_fingerprint?: string | null
}
export interface AssignmentStatement extends Omit<ProgramStatementBase, 'kind'> {
    kind: 'assignment'; target: ProgramAssignmentTarget; value: ProgramValueNode
}
export interface ConditionalBranch {
    branch_id: string; condition: ProgramValueNode; statements: ProgramStatement[]
}
export interface IfStatement extends Omit<ProgramStatementBase, 'kind'> {
    kind: 'if'; condition: ProgramValueNode; then_body: ProgramStatement[]
    additional_branches: ConditionalBranch[]; else_body: ProgramStatement[]
}
export interface LoopStatement extends Omit<ProgramStatementBase, 'kind'> {
    kind: 'loop'; mode: 'repeat' | 'while' | 'for_each' | 'for_each_map'; source: ProgramValueNode
    body: ProgramStatement[]; item_binding?: LocalSymbolDefinition | null; index_binding?: LocalSymbolDefinition | null
    key_binding?: LocalSymbolDefinition | null; value_binding?: LocalSymbolDefinition | null
}
export interface BreakStatement extends Omit<ProgramStatementBase, 'kind'> { kind: 'break' }
export interface ContinueStatement extends Omit<ProgramStatementBase, 'kind'> { kind: 'continue' }
export interface ReturnStatement extends Omit<ProgramStatementBase, 'kind'> { kind: 'return'; value?: ProgramValueNode | null }
export interface FailStatement extends Omit<ProgramStatementBase, 'kind'> {
    kind: 'fail'; error_id: string; message: ProgramValueNode; details?: ProgramValueNode | null
}
export interface RetryPolicyDefinition {
    max_retries: ProgramValueNode; interval: ProgramValueNode; transient_only: true; author_review_fingerprint?: string | null
}
export interface CatchClauseDefinition {
    catch_id: string; error_ids: string[]; error_binding?: LocalSymbolDefinition | null; statements: ProgramStatement[]
}
export interface TryStatement extends Omit<ProgramStatementBase, 'kind'> {
    kind: 'try'; body: ProgramStatement[]; catches: CatchClauseDefinition[]
    finally_body: ProgramStatement[]; retry_policy?: RetryPolicyDefinition | null
}
export interface TargetScopeStatement extends Omit<ProgramStatementBase, 'kind'> {
    kind: 'target_scope'; target: ProgramValueNode; body: ProgramStatement[]
}
export interface MessageEventSourceDefinition {
    kind: 'message'; name: ProgramValueNode; sender?: ProgramValueNode | null
}
export interface ListenStatement extends Omit<ProgramStatementBase, 'kind'> {
    kind: 'listen'; event_source: MessageEventSourceDefinition; receive_binding: LocalSymbolDefinition
    condition?: ProgramValueNode | null; handler_function_id: string; handler_display_name: string
    handler_arguments: Record<string, ProgramValueNode>
}
export type ProgramStatement = CallStatement | AssignmentStatement | IfStatement | LoopStatement
    | BreakStatement | ContinueStatement | ReturnStatement | FailStatement
    | TryStatement | TargetScopeStatement | ListenStatement

export interface ProgramFunctionDefinition {
    function_id: string; display_name: string; parameters: LocalSymbolDefinition[]; return_type: string; statements: ProgramStatement[]
}
export interface ProgramDocument {
    schema_version: number; document_id: string; revision: ProgramRevision; function: ProgramFunctionDefinition
}

export type ProgramValueSource = 'fixed' | 'reference' | 'computed'
export interface ProgramParameterContract {
    parameter_id: string; display_name: string; value_type: string; required: boolean; default_value?: ProgramLiteral; description?: string
    constraints?: {
        min?: number; max?: number; step?: number
        choices?: Array<unknown | { label: string; value: unknown; platforms?: PlatformId[] }>
        [key: string]: unknown
    }
    ui?: ParameterUiContract; allowed_sources?: ProgramValueSource[]
}
export interface ProgramFunctionContract {
    function_id: string; display_name: string; description?: string; parameters: ProgramParameterContract[]; return_type: string; platforms?: PlatformId[]
    dangerous?: boolean
}
export interface AvailableProgramValue { source: 'local' | 'project'; id: string; display_name: string; value_type: string; summary?: string }
export interface ProgramNamedOption { label: string; value: string }
export interface ProjectVariableDefinition {
    variable_id: string
    display_name: string
    value_type: string
    default_value: ProgramValueNode
    description: string
    constraints: Record<string, unknown>
}
export type ProgramRuntimeState = 'idle' | 'running' | 'completed' | 'waiting' | 'paused' | 'failed'
export interface ProgramStatementState { runtime?: ProgramRuntimeState; diagnostic_count?: number; breakpoint?: boolean }

export interface ProgramInsertionTarget {
    key: string
    parent_statement_id: string
    block: 'then' | 'otherwise' | 'additional_branch' | 'body' | 'catch' | 'finally'
    clause_id?: string
    label: string
}

export type StatementListAction =
    | { kind: 'move'; statement_ids: string[]; direction: 'up' | 'down' }
    | { kind: 'nest'; statement_ids: string[]; direction: 'in' | 'out' }
    | { kind: 'copy'; statement_ids: string[] }
    | { kind: 'cut'; statement_ids: string[] }
    | { kind: 'paste'; statement_ids: string[] }
    | { kind: 'duplicate'; statement_ids: string[] }
    | { kind: 'cancel-clipboard'; statement_ids: string[] }
    | { kind: 'extract'; statement_ids: string[] }
    | { kind: 'delete'; statement_ids: string[]; fallback_statement_id: string | null }
export type ProgramCommand =
    | { kind: 'move_statements'; statement_ids: string[]; direction: 'up' | 'down' }
    | { kind: 'change_statement_nesting'; statement_ids: string[]; direction: 'in' | 'out' }
    | { kind: 'copy_statements'; statement_ids: string[] }
    | { kind: 'duplicate_statements'; statement_ids: string[] }
    | { kind: 'cut_statements'; statement_ids: string[] }
    | { kind: 'paste_statements' }
    | { kind: 'cancel_statement_clipboard' }
    | { kind: 'batch_update_values'; statement_ids: string[]; parameter_id: string; next: ProgramValueDraft }
    | { kind: 'delete_statements'; statement_ids: string[] }
    | { kind: 'repair_missing_arguments'; statement_id: string }
    | { kind: 'update_value'; statement_id: string; parameter_id: string; value_id: string; next: ProgramValueDraft }
    | { kind: 'update_assignment_value'; statement_id: string; value: ProgramValueNode }
    | { kind: 'update_assignment_target'; statement_id: string; target: ProgramAssignmentTarget; value?: ProgramValueNode }
    | { kind: 'update_if_condition'; statement_id: string; branch_id?: string | null; condition: ProgramValueNode }
    | { kind: 'add_if_branch'; statement_id: string; condition: ProgramValueNode }
    | { kind: 'remove_if_branch'; statement_id: string; branch_id: string }
    | {
        kind: 'update_loop'; statement_id: string; mode: LoopStatement['mode']; source: ProgramValueNode
        item_binding?: LocalSymbolDefinition | null; index_binding?: LocalSymbolDefinition | null
        key_binding?: LocalSymbolDefinition | null; value_binding?: LocalSymbolDefinition | null
    }
    | { kind: 'update_return_value'; statement_id: string; value: ProgramValueNode | null }
    | { kind: 'update_fail'; statement_id: string; error_id: string; message: ProgramValueNode; details?: ProgramValueNode | null }
    | { kind: 'update_try_retry_policy'; statement_id: string; retry_policy: RetryPolicyDefinition | null }
    | { kind: 'review_retry_risk'; statement_id: string }
    | { kind: 'review_dangerous_call'; statement_id: string }
    | {
        kind: 'update_catch_clause'; statement_id: string; catch_id: string; error_ids: string[]
        error_binding?: LocalSymbolDefinition | null
    }
    | { kind: 'update_target_scope'; statement_id: string; target: ProgramValueNode }
    | {
        kind: 'update_listen'; statement_id: string; event_source: MessageEventSourceDefinition
        receive_binding: LocalSymbolDefinition; handler_function_id: string
        condition?: ProgramValueNode | null; handler_arguments: Record<string, ProgramValueNode>
    }
    | {
        kind: 'set_result_binding'; statement_id: string
        target:
            | { kind: 'new_local'; display_name: string }
            | { kind: 'existing_local'; symbol_id: string; display_name: string; value_type: string }
            | null
    }
    | { kind: 'insert_if_from_call_result'; statement_id: string }
    | { kind: 'set_step_label'; statement_id: string; step_label: string | null }
export interface ProgramCommandEnvelope { document_id: string; base_revision: ProgramRevision; command: ProgramCommand }
export interface ProgramValueUpdate { statement_id: string; parameter_id: string; value_id: string; next: ProgramValueDraft }
export interface ProgramCaptureRequest { statement_id: string; parameter_id: string; value_id: string; action: ParameterUiAction }
export interface ProgramCaptureEnvelope { document_id: string; base_revision: ProgramRevision; request: ProgramCaptureRequest }
export interface ProgramValueEditorRequest {
    statement_id: string
    parameter_id: string
    value_id: string
    preferred_source?: Extract<ProgramValueSource, 'computed'>
    batch_statement_ids?: string[]
}
export interface ProgramValueEditorEnvelope { document_id: string; base_revision: ProgramRevision; request: ProgramValueEditorRequest }

export type ProgramControlType = ParameterControlType
export type ProgramControlAction = ParameterUiAction
export type ProgramAsset = AssetDefinition
