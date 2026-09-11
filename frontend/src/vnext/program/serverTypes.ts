import type { ExecutionPlatformId, ParameterUiContract, PlatformId, RuntimeSession } from '../types'

/** Exact format-6 Program Service wire contract. */
export interface ServerPointLiteral { x: number; y: number }
export interface ServerMapEntry { key: ServerProgramValueNode; value: ServerProgramValueNode }
export interface ServerSelectorBinding { symbol_id: string; role: 'item' | 'index' | 'key' | 'value'; display_name: string; value_type: string }

export type ServerProgramValueNode =
    | { value_id: string; kind: 'unset'; expected_type: string }
    | { value_id: string; kind: 'null' }
    | { value_id: string; kind: 'string'; value: string }
    | { value_id: string; kind: 'int64'; value: number }
    | { value_id: string; kind: 'float64'; value: number }
    | { value_id: string; kind: 'bool'; value: boolean }
    | { value_id: string; kind: 'date'; value: string }
    | { value_id: string; kind: 'datetime'; value: string }
    | { value_id: string; kind: 'time'; value: string }
    | { value_id: string; kind: 'duration'; milliseconds: number }
    | { value_id: string; kind: 'point'; x: number; y: number }
    | { value_id: string; kind: 'rect'; x: number; y: number; width: number; height: number }
    | { value_id: string; kind: 'path'; points: ServerPointLiteral[] }
    | { value_id: string; kind: 'symbol_ref'; symbol_id: string; value_type: string }
    | { value_id: string; kind: 'project_variable_ref'; variable_id: string; value_type: string }
    | { value_id: string; kind: 'asset_ref'; asset_id: string; asset_kind: string }
    | { value_id: string; kind: 'target_ref'; target_id: string }
    | { value_id: string; kind: 'entity_ref'; reference_id: string; reference_type: string }
    | { value_id: string; kind: 'member_access'; source: ServerProgramValueNode; field_id: string; result_type: string }
    | { value_id: string; kind: 'list'; item_type: string; items: ServerProgramValueNode[] }
    | { value_id: string; kind: 'map'; key_type: string; entry_value_type: string; entries: ServerMapEntry[]; duplicate_policy: 'error' }
    | { value_id: string; kind: 'record'; record_type: string; fields: Record<string, ServerProgramValueNode> }
    | { value_id: string; kind: 'json'; payload: unknown }
    | { value_id: string; kind: 'operation'; operation_id: string; result_type: string; inputs: Record<string, ServerProgramValueNode> }
    | { value_id: string; kind: 'selector'; bindings: ServerSelectorBinding[]; result_type: string; expression: ServerProgramValueNode }
    | { value_id: string; kind: 'compare'; operator: 'eq' | 'ne' | 'lt' | 'lte' | 'gt' | 'gte'; left: ServerProgramValueNode; right: ServerProgramValueNode }
    | { value_id: string; kind: 'condition_group'; operator: 'all' | 'any'; conditions: ServerProgramValueNode[] }
    | { value_id: string; kind: 'not'; condition: ServerProgramValueNode }

export interface ServerProgramParameter {
    parameter_id: string
    symbol_id: string
    display_name: string
    value_type: string
    required: boolean
    default_value: ServerProgramValueNode | null
}

export interface ProgramSignatureParameterInput {
    parameter_id?: string | null
    display_name: string
    value_type: string
    required: boolean
    default_value: ServerProgramValueNode | null
}

export interface ServerProgramResultBinding { symbol_id: string; display_name: string; value_type: string; declare: boolean }
export interface ServerLoopBinding { symbol_id: string; display_name: string; value_type: string }
export type ServerAssignmentTarget =
    | { kind: 'local'; symbol_id: string; display_name: string; value_type: string; declare: boolean }
    | { kind: 'project_variable'; variable_id: string; value_type: string }

interface ServerStatementBase { statement_id: string; step_label: string | null }
export interface ServerCallStatement extends ServerStatementBase {
    kind: 'call'; function_id: string; arguments: Record<string, ServerProgramValueNode>; result_binding: ServerProgramResultBinding | null
    author_review_fingerprint?: string | null
}
export interface ServerAssignmentStatement extends ServerStatementBase { kind: 'assignment'; target: ServerAssignmentTarget; value: ServerProgramValueNode }
export interface ServerConditionalBranch { branch_id: string; condition: ServerProgramValueNode; statements: ServerProgramStatement[] }
export interface ServerIfStatement extends ServerStatementBase {
    kind: 'if'; condition: ServerProgramValueNode; then_statements: ServerProgramStatement[]
    additional_branches: ServerConditionalBranch[]; otherwise_statements: ServerProgramStatement[]
}
export interface ServerLoopStatement extends ServerStatementBase {
    kind: 'loop'; mode: 'repeat' | 'while' | 'for_each' | 'for_each_map'; source: ServerProgramValueNode
    body: ServerProgramStatement[]; item_binding: ServerLoopBinding | null; index_binding: ServerLoopBinding | null
    key_binding: ServerLoopBinding | null; value_binding: ServerLoopBinding | null
}
export interface ServerBreakStatement extends ServerStatementBase { kind: 'break' }
export interface ServerContinueStatement extends ServerStatementBase { kind: 'continue' }
export interface ServerReturnStatement extends ServerStatementBase { kind: 'return'; value: ServerProgramValueNode | null }
export interface ServerFailStatement extends ServerStatementBase {
    kind: 'fail'; error_id: string; message: ServerProgramValueNode; details: ServerProgramValueNode | null
}
export interface ServerRetryPolicy {
    max_retries: ServerProgramValueNode; interval: ServerProgramValueNode; transient_only: true; author_review_fingerprint: string | null
}
export interface ServerCatchClause {
    catch_id: string; error_ids: string[]; error_binding: ServerLoopBinding | null; statements: ServerProgramStatement[]
}
export interface ServerTryStatement extends ServerStatementBase {
    kind: 'try'; body: ServerProgramStatement[]; retry_policy: ServerRetryPolicy | null
    catches: ServerCatchClause[]; finally_statements: ServerProgramStatement[]
}
export interface ServerTargetScopeStatement extends ServerStatementBase { kind: 'target_scope'; target: ServerProgramValueNode; body: ServerProgramStatement[] }
export interface ServerMessageEventSource { kind: 'message'; name: ServerProgramValueNode; sender: ServerProgramValueNode | null }
export interface ServerListenStatement extends ServerStatementBase {
    kind: 'listen'; event_source: ServerMessageEventSource; receive_binding: ServerLoopBinding
    condition: ServerProgramValueNode | null; handler_function_id: string; handler_arguments: Record<string, ServerProgramValueNode>
}
export type ServerProgramStatement = ServerCallStatement | ServerAssignmentStatement | ServerIfStatement | ServerLoopStatement
    | ServerBreakStatement | ServerContinueStatement | ServerReturnStatement | ServerFailStatement
    | ServerTryStatement | ServerTargetScopeStatement | ServerListenStatement

export interface ServerProgramDocument {
    schema_version: number
    document_id: string
    function: { function_id: string; display_name: string; parameters: ServerProgramParameter[]; return_type: string; statements: ServerProgramStatement[] }
}

export interface ProgramDiagnosticDto {
    code: string; severity: 'error' | 'warning' | 'info' | string; message: string
    function_id?: string; statement_id?: string; value_id?: string; field_path?: string; [key: string]: unknown
}
export interface ProgramOperationPresentationDto {
    display_name: string
    syntax_name: string
    input_labels: Record<string, string>
}
export interface ProgramSnapshotDto {
    document: ServerProgramDocument; revision: string; diagnostics: ProgramDiagnosticDto[]
    presentations?: {
        operations: Record<string, ProgramOperationPresentationDto>
        fields?: Record<string, string>
        record_types?: Record<string, string>
    }
    selected_statement_id?: string; created_ids?: string[]; can_undo?: boolean; can_redo?: boolean
    programs?: ProgramSummaryDto[]
}
export interface ProgramSummaryDto {
    document_id: string; function_id: string; display_name: string; statement_count: number; revision: string
    parameters: ServerProgramParameter[]; return_type: string; contract_version: string; contract_fingerprint: string
}
export interface ProgramExtractResponseDto extends ProgramSnapshotDto {
    extracted_program: ProgramSummaryDto
}
export interface ProgramHistoryItemDto {
    history_id: string; revision: string; created_at: string; reason: string
    display_name: string; statement_count: number
}
export interface ProgramHistoryDto {
    function_id: string; current_revision: string; items: ProgramHistoryItemDto[]
}

export interface PureOperationCandidateInputDto {
    input_id: string; display_name: string; value_type: string
    choices: Array<{ label: string; value: unknown; platforms?: PlatformId[] }>
}
export interface PureOperationCandidateDto {
    candidate_id: string; operation_id: string; display_name: string; category: string
    description: string; syntax_name?: string; result_type: string; inputs: PureOperationCandidateInputDto[]
}
export interface ExpressionNamespaceDto {
    name: string; description: string; keywords: string[]; operation_count: number; compatible_count: number
}
export interface ExpressionOperationDiscoveryDto {
    operation_id: string; display_name: string; namespace: string; group: string; description: string
    syntax_name: string; aliases: string[]; keywords: string[]; input_labels: string[]; example: string
    result_type_hints: string[]; compatible: boolean; disabled_reason: string
}
export interface ExpressionLiteralSuggestionDto { label: string; insert_text: string; description: string }
export interface ExpressionOperatorSuggestionDto { label: string; insert_text: string; description: string }
export interface ExpressionDiscoveryDto {
    namespaces: ExpressionNamespaceDto[]
    operations: ExpressionOperationDiscoveryDto[]
    literals: ExpressionLiteralSuggestionDto[]
    operators: ExpressionOperatorSuggestionDto[]
    triggers: Array<{ keys: string; description: string }>
}
export interface RecordMemberPathItemDto { field_id: string; display_name: string; result_type: string }
export interface RecordMemberCandidateDto {
    candidate_id: string; source: 'local' | 'project'; source_id: string; source_display_name: string
    source_value_type: string; result_type: string; path: RecordMemberPathItemDto[]
}
export interface ProgramValueCatalogDto {
    schema_version: number; registry_version: number; registry_hash: string; revision: string; expected_type: string
    operations: PureOperationCandidateDto[]; members: RecordMemberCandidateDto[]
    discovery?: ExpressionDiscoveryDto
    sources: Array<{
        source: 'local' | 'project'; source_id: string; display_name: string
        value_type: string; narrowed_type: string
    }>
    record: null | {
        type_id: string; display_name: string
        authoring_mode?: 'constructible' | 'reference_only' | 'capture_only'
        editor_strategy?: 'inline_record' | 'row_list' | 'focused' | 'reference' | 'capture'
        summary_fields?: string[]
        fields: Array<{
            field_id: string; display_name: string; value_type: string; description: string
            choices: Array<{ label: string; value: unknown; platforms?: PlatformId[] }>
            required?: boolean
            has_default?: boolean
            default?: unknown
            constraints?: Record<string, unknown>
            ui?: ParameterUiContract
        }>
    }
}

export interface ProjectVariableDefinitionDto {
    variable_id: string
    display_name: string
    value_type: string
    default_value: ServerProgramValueNode
    description: string
    constraints: Record<string, unknown>
}
export interface ProjectVariableSnapshotDto {
    schema_version: number
    variables: ProjectVariableDefinitionDto[]
    revision: string
    selected_variable_id?: string
}
export interface ProjectVariableReferenceDto {
    kind: string
    function_id?: string
    function_name?: string
    statement_id?: string
    value_id?: string
    field?: string
    path?: string
    location?: string
}
export interface ProgramDeleteResponseDto {
    deleted_function_id: string
    programs: ProgramSummaryDto[]
}

export interface AvailableFunctionParameterDto {
    parameter_id: string; name: string; display_name: string; value_type: string; required: boolean
    has_default: boolean; default: unknown; control: string; constraints: Record<string, unknown>; description: string
    /** Optional until the server publishes the shared Control contract. No client-side action inference. */
    ui?: ParameterUiContract
}
export type StatementSummaryContractPartDto =
    | { kind: 'text'; text: string }
    | {
        kind: 'parameter'; parameter_id: string; parameter_name: string
        role: 'object' | 'destination' | 'condition' | 'qualifier' | 'content' | string
        presentation: 'auto' | string
    }
export interface StatementSummaryContractDto {
    schema_version: 1
    parts: StatementSummaryContractPartDto[]
}
export interface AvailableFunctionContractDto {
    function_id: string; namespace: string; name: string; qualified_name: string; summary: string; layer: 'atomic' | 'standard' | string
    parameters: AvailableFunctionParameterDto[]; return_type: string; opcode: string; host_requirements: string[]; target_kinds: string[]
    target_capabilities: string[]; permissions: string[]; side_effects: string[]
    errors: Array<{ error_id: string; classification: string; description: string }>; normal_empty: boolean; network_level: string
    dangerous: boolean; implementation_state: 'available' | 'planned' | string; standard_definition_id: string
    contract_version: string; schema_version: number; contract_fingerprint: string
    statement_summary?: StatementSummaryContractDto
    source?: 'official' | 'extension' | string; package_id?: string
}

export interface ProgramStatementLocationDto {
    parent_statement_id: string | null
    block: 'root' | 'then' | 'otherwise' | 'additional_branch' | 'body' | 'catch' | 'finally'
    clause_id?: string | null
    before_statement_id: string | null
}
export type ProgramServerCommand =
    | { kind: 'insert_call'; function_id: string; arguments?: Record<string, ServerProgramValueNode>; location: ProgramStatementLocationDto }
    | { kind: 'insert_call_and_if'; function_id: string; arguments?: Record<string, ServerProgramValueNode>; display_name?: string | null; location: ProgramStatementLocationDto }
    | { kind: 'insert_execute_until'; condition_function_id: string; arguments?: Record<string, ServerProgramValueNode>; display_name?: string | null; max_attempts?: number; location: ProgramStatementLocationDto }
    | { kind: 'insert_assignment'; target: ServerAssignmentTarget; value: ServerProgramValueNode; location: ProgramStatementLocationDto }
    | { kind: 'insert_if'; condition: ServerProgramValueNode; location: ProgramStatementLocationDto }
    | { kind: 'insert_if_from_call_result'; statement_id: string; display_name?: string | null }
    | { kind: 'insert_loop'; mode: ServerLoopStatement['mode']; source: ServerProgramValueNode; item_binding?: ServerLoopBinding | null; index_binding?: ServerLoopBinding | null; key_binding?: ServerLoopBinding | null; value_binding?: ServerLoopBinding | null; location: ProgramStatementLocationDto }
    | { kind: 'insert_break'; location: ProgramStatementLocationDto }
    | { kind: 'insert_continue'; location: ProgramStatementLocationDto }
    | { kind: 'insert_return'; value?: ServerProgramValueNode | null; location: ProgramStatementLocationDto }
    | { kind: 'insert_fail'; error_id: string; message: ServerProgramValueNode; details?: ServerProgramValueNode | null; location: ProgramStatementLocationDto }
    | { kind: 'insert_try'; retry_policy?: ServerRetryPolicy | null; catches?: ServerCatchClause[]; location: ProgramStatementLocationDto }
    | { kind: 'insert_target_scope'; target: ServerProgramValueNode; location: ProgramStatementLocationDto }
    | { kind: 'insert_listen'; event_source: ServerMessageEventSource; receive_binding: ServerLoopBinding; handler_function_id: string; condition?: ServerProgramValueNode | null; handler_arguments?: Record<string, ServerProgramValueNode>; location: ProgramStatementLocationDto }
    | { kind: 'add_if_branch'; statement_id: string; condition: ServerProgramValueNode }
    | { kind: 'remove_if_branch'; statement_id: string; branch_id: string }
    | { kind: 'add_catch_clause'; statement_id: string; error_ids?: string[]; error_binding?: ServerLoopBinding | null }
    | { kind: 'repair_missing_arguments'; statement_id: string }
    | { kind: 'update_argument'; statement_id: string; parameter_id: string; value: ServerProgramValueNode }
    | { kind: 'update_assignment_value'; statement_id: string; value: ServerProgramValueNode }
    | { kind: 'update_assignment_target'; statement_id: string; target: ServerAssignmentTarget; value?: ServerProgramValueNode }
    | { kind: 'update_if_condition'; statement_id: string; branch_id?: string | null; condition: ServerProgramValueNode }
    | { kind: 'update_loop'; statement_id: string; mode: ServerLoopStatement['mode']; source: ServerProgramValueNode; item_binding?: ServerLoopBinding | null; index_binding?: ServerLoopBinding | null; key_binding?: ServerLoopBinding | null; value_binding?: ServerLoopBinding | null }
    | { kind: 'update_return_value'; statement_id: string; value: ServerProgramValueNode | null }
    | { kind: 'update_fail'; statement_id: string; error_id: string; message: ServerProgramValueNode; details?: ServerProgramValueNode | null }
    | { kind: 'update_try_retry_policy'; statement_id: string; retry_policy: ServerRetryPolicy | null }
    | { kind: 'review_retry_risk'; statement_id: string }
    | { kind: 'review_dangerous_call'; statement_id: string }
    | { kind: 'update_catch_clause'; statement_id: string; catch_id: string; error_ids: string[]; error_binding?: ServerLoopBinding | null }
    | { kind: 'update_target_scope'; statement_id: string; target: ServerProgramValueNode }
    | { kind: 'update_listen'; statement_id: string; event_source: ServerMessageEventSource; receive_binding: ServerLoopBinding; handler_function_id: string; condition?: ServerProgramValueNode | null; handler_arguments: Record<string, ServerProgramValueNode> }
    | { kind: 'set_result_binding'; statement_id: string; binding: ServerProgramResultBinding | null }
    | { kind: 'set_step_label'; statement_id: string; label: string | null }
    | { kind: 'move_statement'; statement_id: string; location: ProgramStatementLocationDto }
    | { kind: 'move_statements'; statement_ids: string[]; location: ProgramStatementLocationDto }
    | { kind: 'copy_statement'; statement_id: string; location: ProgramStatementLocationDto }
    | { kind: 'paste_statements'; statements: ServerProgramStatement[]; location: ProgramStatementLocationDto }
    | { kind: 'delete_statement'; statement_id: string }
    | { kind: 'delete_statements'; statement_ids: string[] }

export interface ProgramCompileResponse { valid: boolean; ecir: Record<string, unknown> | null; ecir_revision?: string; diagnostics: ProgramDiagnosticDto[] }
export interface ProgramRunRequest { target_platform?: ExecutionPlatformId; target_id?: string; debug?: Record<string, unknown> }
export type ProgramRunResponse = RuntimeSession
export interface ProgramApiErrorDetail {
    code?: string; message?: string; request_id?: string; fields?: Array<{ path: string; message: string; kind?: string }>
    recovery?: { retryable?: boolean; action?: string; message?: string }; diagnostics?: ProgramDiagnosticDto[]
}
