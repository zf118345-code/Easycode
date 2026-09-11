import { computed, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'
import type { ExecutionPlatformId, WorkspaceIdentity } from '../types'
import {
    availableFunctionsToUiContracts,
    projectFunctionsToUiContracts,
    ProgramProjectionError,
    programSnapshotToUiDocument,
    uiDraftToServerValue,
    uiProgramValueToServerValue,
    uiStructureCommandToServerCommand,
    uiValueUpdateToServerCommand,
} from './adapter'
import { ProgramApiError, programApi } from './api'
import type {
    AvailableProgramValue,
    ProgramCommand,
    ProgramCommandEnvelope,
    ProgramDocument,
    ProgramFunctionContract,
    ProgramInsertionTarget,
    ProgramAssignmentTarget,
    ProgramStatement,
    ProgramStatementState,
    ProgramValueDraft,
} from './types'
import type {
    AvailableFunctionContractDto,
    ProgramCompileResponse,
    ProgramDeleteResponseDto,
    ProgramHistoryDto,
    ProgramRunRequest,
    ProgramRunResponse,
    ProgramServerCommand,
    ProgramSnapshotDto,
    ProgramStatementLocationDto,
    ProgramSummaryDto,
    ServerProgramStatement,
} from './serverTypes'
import type { ProgramStructureKind } from './functionLibraryTypes'
import { defaultProgramValue } from './valueFactories'

export type ProgramStoreStatus = 'idle' | 'loading' | 'ready' | 'error' | 'conflict'

export interface ProgramRevisionConflict {
    function_id: string
    expected_revision: string
    actual_revision: string
    message: string
}

export interface ProgramLifecycleBlocker {
    function_id: string
    code: 'program_referenced' | 'program_entry_delete_forbidden'
    message: string
    references: Array<Record<string, unknown>>
}

export interface ProgramStructureInsertOptions {
    target_id?: string
    handler_function_id?: string
    assignment_target?: ProgramAssignmentTarget
}

interface StatementContainer {
    parent_statement_id: string | null
    block: ProgramStatementLocationDto['block']
    clause_id?: string | null
    statements: ServerProgramStatement[]
    index: number
}

interface ProgramOperationScope {
    connection_token: number
    workspace_id: string
    workspace_generation: number
    document_id?: string
    function_id?: string
}

interface ProgramStatementClipboard {
    mode: 'copy' | 'cut'
    workspace_id: string
    workspace_generation: number
    document_id: string
    source_function_id: string
    statement_ids: string[]
    statements: ServerProgramStatement[]
}

export class ProgramStoreError extends Error {
    constructor(message: string) {
        super(message)
        this.name = 'ProgramStoreError'
    }
}

class ProgramContextChangedError extends ProgramStoreError {
    constructor() {
        super('项目或函数已经切换，旧操作结果未应用到当前界面')
        this.name = 'ProgramContextChangedError'
    }
}

interface ServerChildBlock {
    block: ProgramStatementLocationDto['block']
    clause_id?: string
    statements: ServerProgramStatement[]
}

function serverChildBlocks(statement: ServerProgramStatement): ServerChildBlock[] {
    if (statement.kind === 'if') return [
        { block: 'then', statements: statement.then_statements },
        ...statement.additional_branches.map((branch) => ({
            block: 'additional_branch' as const,
            clause_id: branch.branch_id,
            statements: branch.statements,
        })),
        { block: 'otherwise', statements: statement.otherwise_statements },
    ]
    if (statement.kind === 'loop' || statement.kind === 'target_scope') {
        return [{ block: 'body', statements: statement.body }]
    }
    if (statement.kind === 'try') return [
        { block: 'body', statements: statement.body },
        ...statement.catches.map((clause) => ({
            block: 'catch' as const,
            clause_id: clause.catch_id,
            statements: clause.statements,
        })),
        { block: 'finally', statements: statement.finally_statements },
    ]
    return []
}

function statementIds(statements: ServerProgramStatement[]): string[] {
    return statements.flatMap((statement) => [
        statement.statement_id,
        ...serverChildBlocks(statement).flatMap((child) => statementIds(child.statements)),
    ])
}

function findStatementContainer(
    statements: ServerProgramStatement[],
    statementId: string,
    parentStatementId: string | null = null,
    block: StatementContainer['block'] = 'root',
    clauseId?: string | null,
): StatementContainer | null {
    const index = statements.findIndex((statement) => statement.statement_id === statementId)
    if (index >= 0) return { parent_statement_id: parentStatementId, block, clause_id: clauseId, statements, index }
    for (const statement of statements) {
        for (const child of serverChildBlocks(statement)) {
            const found = findStatementContainer(
                child.statements,
                statementId,
                statement.statement_id,
                child.block,
                child.clause_id,
            )
            if (found) return found
        }
    }
    return null
}

function findServerStatement(statements: ServerProgramStatement[], statementId: string): ServerProgramStatement | null {
    for (const statement of statements) {
        if (statement.statement_id === statementId) return statement
        for (const child of serverChildBlocks(statement)) {
            const found = findServerStatement(child.statements, statementId)
            if (found) return found
        }
    }
    return null
}

function locationInContainer(
    container: StatementContainer,
    beforeStatementId: string | null,
): ProgramStatementLocationDto {
    return {
        parent_statement_id: container.parent_statement_id,
        block: container.block,
        ...(container.clause_id ? { clause_id: container.clause_id } : {}),
        before_statement_id: beforeStatementId,
    }
}

function resolvedInsertionTarget(
    statements: ServerProgramStatement[],
    target: ProgramInsertionTarget,
): ProgramStatementLocationDto | null {
    const owner = findServerStatement(statements, target.parent_statement_id)
    if (!owner) return null
    const block = serverChildBlocks(owner).find((candidate) => (
        candidate.block === target.block && (candidate.clause_id || '') === (target.clause_id || '')
    ))
    if (!block) return null
    return {
        parent_statement_id: target.parent_statement_id,
        block: target.block,
        ...(target.clause_id ? { clause_id: target.clause_id } : {}),
        before_statement_id: null,
    }
}

function locationIsInsideLoop(
    statements: ServerProgramStatement[],
    location: ProgramStatementLocationDto,
): boolean {
    let parentId = location.parent_statement_id
    while (parentId) {
        const parent = findServerStatement(statements, parentId)
        if (parent?.kind === 'loop') return true
        const container = findStatementContainer(statements, parentId)
        parentId = container?.parent_statement_id || null
    }
    return false
}

function diagnosticCountByStatement(statements: ProgramStatement[], counts: Record<string, number>): void {
    for (const statement of statements) {
        counts[statement.statement_id] ||= 0
        if (statement.kind === 'if') {
            diagnosticCountByStatement(statement.then_body, counts)
            for (const branch of statement.additional_branches) diagnosticCountByStatement(branch.statements, counts)
            diagnosticCountByStatement(statement.else_body, counts)
        } else if (statement.kind === 'loop' || statement.kind === 'target_scope') {
            diagnosticCountByStatement(statement.body, counts)
        } else if (statement.kind === 'try') {
            diagnosticCountByStatement(statement.body, counts)
            for (const clause of statement.catches) diagnosticCountByStatement(clause.statements, counts)
            diagnosticCountByStatement(statement.finally_body, counts)
        }
    }
}

function newClientStableId(prefix: string): string {
    const uuid = globalThis.crypto?.randomUUID?.().replaceAll('-', '')
    if (uuid) return `${prefix}_${uuid}`
    return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 12)}`
}

function draftWithoutStableIds(draft: ProgramValueDraft): ProgramValueDraft {
    function visit(value: unknown): unknown {
        if (Array.isArray(value)) return value.map(visit)
        if (!value || typeof value !== 'object') return value
        return Object.fromEntries(Object.entries(value as Record<string, unknown>)
            .filter(([key]) => key !== 'value_id')
            .map(([key, child]) => [key, visit(child)]))
    }
    return visit(draft) as ProgramValueDraft
}

export const useProgramStore = defineStore('vnext-program', () => {
    const workspace = ref<WorkspaceIdentity | null>(null)
    const programs = shallowRef<ProgramSummaryDto[]>([])
    const availableFunctions = shallowRef<AvailableFunctionContractDto[]>([])
    const serverSnapshot = shallowRef<ProgramSnapshotDto | null>(null)
    const document = shallowRef<ProgramDocument | null>(null)
    const selectedStatementIds = ref<string[]>([])
    const insertionTarget = ref<ProgramInsertionTarget | null>(null)
    const collapsedStatementIds = ref<string[]>([])
    const status = ref<ProgramStoreStatus>('idle')
    const operationError = ref('')
    const conflict = ref<ProgramRevisionConflict | null>(null)
    const lifecycleBlocker = ref<ProgramLifecycleBlocker | null>(null)
    const projectVariableNames = ref<Record<string, string>>({})
    const pendingCount = ref(0)
    const lastCompile = ref<ProgramCompileResponse | null>(null)
    const lastRun = ref<ProgramRunResponse | null>(null)
    const history = shallowRef<ProgramHistoryDto | null>(null)
    const statementClipboard = shallowRef<ProgramStatementClipboard | null>(null)
    let connectionToken = 0
    let mutationTail: Promise<void> = Promise.resolve()

    const busy = computed(() => pendingCount.value > 0)
    const activeFunctionId = computed(() => serverSnapshot.value?.document.function.function_id || '')
    const functionContracts = computed<Record<string, ProgramFunctionContract>>(() => ({
        ...projectFunctionsToUiContracts(programs.value),
        ...availableFunctionsToUiContracts(availableFunctions.value),
    }))
    const availableFunctionIds = computed(() => new Set([
        ...availableFunctions.value.map((item) => item.function_id),
        ...programs.value.map((item) => item.function_id),
    ]))
    const canUndo = computed(() => Boolean(serverSnapshot.value?.can_undo))
    const canRedo = computed(() => Boolean(serverSnapshot.value?.can_redo))
    const readOnly = computed(() => Boolean(workspace.value?.read_only))
    const pendingCutStatementIds = computed(() => (
        statementClipboard.value?.mode === 'cut' ? statementClipboard.value.statement_ids : []
    ))
    const statementClipboardCount = computed(() => statementClipboard.value?.statement_ids.length || 0)
    const canPasteStatements = computed(() => {
        const clipboard = statementClipboard.value
        const currentWorkspace = workspace.value
        const currentDocumentId = serverSnapshot.value?.document.document_id
        if (!clipboard || !currentWorkspace || !currentDocumentId || readOnly.value) return false
        const sameWorkspace = clipboard.workspace_id === currentWorkspace.workspace_id
            && clipboard.workspace_generation === currentWorkspace.generation
        return sameWorkspace && (clipboard.mode === 'copy' || clipboard.document_id === currentDocumentId)
    })
    const effectiveDiagnostics = computed(() => (
        lastCompile.value?.diagnostics || serverSnapshot.value?.diagnostics || []
    ))
    const diagnosticsByValueId = computed<Record<string, string[]>>(() => {
        const result: Record<string, string[]> = {}
        for (const diagnostic of effectiveDiagnostics.value) {
            if (!diagnostic.value_id) continue
            ;(result[diagnostic.value_id] ||= []).push(diagnostic.message)
        }
        return result
    })
    const statementStates = computed<Record<string, ProgramStatementState>>(() => {
        const counts: Record<string, number> = {}
        if (document.value) diagnosticCountByStatement(document.value.function.statements, counts)
        for (const diagnostic of effectiveDiagnostics.value) {
            if (diagnostic.statement_id) counts[diagnostic.statement_id] = (counts[diagnostic.statement_id] || 0) + 1
        }
        return Object.fromEntries(
            Object.entries(counts)
                .filter(([, count]) => count > 0)
                .map(([statementId, count]) => [statementId, { diagnostic_count: count }]),
        )
    })

    function requireWorkspace(): WorkspaceIdentity {
        if (!workspace.value) throw new ProgramStoreError('请先打开项目')
        return workspace.value
    }

    function requireSnapshot(): ProgramSnapshotDto {
        if (!serverSnapshot.value) throw new ProgramStoreError('请先打开项目函数')
        return serverSnapshot.value
    }

    function ensureWritable(): void {
        if (workspace.value?.read_only) throw new ProgramStoreError('当前项目为只读，不能修改函数')
    }

    function captureScope(requireProgram = true): ProgramOperationScope {
        const currentWorkspace = requireWorkspace()
        const current = requireProgram ? requireSnapshot() : null
        return {
            connection_token: connectionToken,
            workspace_id: currentWorkspace.workspace_id,
            workspace_generation: currentWorkspace.generation,
            document_id: current?.document.document_id,
            function_id: current?.document.function.function_id,
        }
    }

    function assertScope(scope: ProgramOperationScope): void {
        if (
            scope.connection_token !== connectionToken
            || workspace.value?.workspace_id !== scope.workspace_id
            || workspace.value?.generation !== scope.workspace_generation
            || (scope.document_id && serverSnapshot.value?.document.document_id !== scope.document_id)
            || (scope.function_id && activeFunctionId.value !== scope.function_id)
        ) {
            throw new ProgramContextChangedError()
        }
    }

    function updateProgramSummary(snapshot: ProgramSnapshotDto): void {
        const current = snapshot.document.function
        const existing = programs.value.find((item) => item.function_id === current.function_id)
        const summary: ProgramSummaryDto = {
            document_id: snapshot.document.document_id,
            function_id: current.function_id,
            display_name: current.display_name,
            statement_count: countServerStatements(current.statements),
            revision: snapshot.revision,
            parameters: current.parameters,
            return_type: current.return_type,
            contract_version: existing?.contract_version || '1.0.0',
            contract_fingerprint: existing?.contract_fingerprint || '',
        }
        const index = programs.value.findIndex((item) => item.function_id === current.function_id)
        if (index < 0) programs.value = [...programs.value, summary]
        else programs.value = programs.value.map((item, itemIndex) => itemIndex === index ? summary : item)
    }

    function countServerStatements(statements: ServerProgramStatement[]): number {
        return statements.reduce((total, statement) => {
            if (statement.kind === 'if') {
                return total + 1
                    + countServerStatements(statement.then_statements)
                    + statement.additional_branches.reduce((sum, branch) => sum + countServerStatements(branch.statements), 0)
                    + countServerStatements(statement.otherwise_statements)
            }
            if (statement.kind === 'loop' || statement.kind === 'target_scope') {
                return total + 1 + countServerStatements(statement.body)
            }
            if (statement.kind === 'try') {
                return total + 1
                    + countServerStatements(statement.body)
                    + statement.catches.reduce((sum, clause) => sum + countServerStatements(clause.statements), 0)
                    + countServerStatements(statement.finally_statements)
            }
            return total + 1
        }, 0)
    }

    function adoptSnapshot(snapshot: ProgramSnapshotDto): void {
        const projected = programSnapshotToUiDocument(snapshot, availableFunctions.value, {
            projectVariableNames: projectVariableNames.value,
            functionNames: Object.fromEntries(programs.value.map((item) => [item.function_id, item.display_name])),
        })
        lastCompile.value = null
        serverSnapshot.value = snapshot
        document.value = projected
        updateProgramSummary(snapshot)
        const validIds = new Set(statementIds(snapshot.document.function.statements))
        if (Object.prototype.hasOwnProperty.call(snapshot, 'selected_statement_id')) {
            selectedStatementIds.value = snapshot.selected_statement_id && validIds.has(snapshot.selected_statement_id)
                ? [snapshot.selected_statement_id]
                : []
            if (selectedStatementIds.value.length) insertionTarget.value = null
        } else {
            selectedStatementIds.value = selectedStatementIds.value.filter((id) => validIds.has(id))
        }
        collapsedStatementIds.value = collapsedStatementIds.value.filter((id) => validIds.has(id))
        if (insertionTarget.value && !resolvedInsertionTarget(snapshot.document.function.statements, insertionTarget.value)) {
            insertionTarget.value = null
        }
        operationError.value = ''
        conflict.value = null
        lifecycleBlocker.value = null
        status.value = 'ready'
    }

    function clearActiveProgram(): void {
        serverSnapshot.value = null
        document.value = null
        selectedStatementIds.value = []
        insertionTarget.value = null
        collapsedStatementIds.value = []
        conflict.value = null
        lastCompile.value = null
        lastRun.value = null
        history.value = null
        statementClipboard.value = null
    }

    function rememberError(error: unknown): void {
        operationError.value = error instanceof Error ? error.message : '操作未完成'
        if (error instanceof ProgramApiError && (
            error.code === 'program_referenced' || error.code === 'program_entry_delete_forbidden'
        ) && !lifecycleBlocker.value) {
            lifecycleBlocker.value = {
                function_id: activeFunctionId.value,
                code: error.code,
                message: error.message,
                references: error.diagnostics,
            }
        }
        if (error instanceof ProgramApiError && error.code === 'program_revision_conflict' && !conflict.value) {
            const details = (error.diagnostics[0] || {}) as Record<string, unknown>
            conflict.value = {
                function_id: String(details.function_id || activeFunctionId.value),
                expected_revision: String(details.expected_revision || serverSnapshot.value?.revision || ''),
                actual_revision: String(details.actual_revision || ''),
                message: error.message,
            }
            status.value = 'conflict'
        } else {
            status.value = document.value ? 'ready' : 'error'
        }
    }

    async function withActivity<T>(operation: () => Promise<T>): Promise<T> {
        pendingCount.value += 1
        try {
            return await operation()
        } finally {
            pendingCount.value = Math.max(0, pendingCount.value - 1)
        }
    }

    function enqueueMutation<T>(operation: () => Promise<T>): Promise<T> {
        let resolveResult: (value: T | PromiseLike<T>) => void = () => undefined
        let rejectResult: (reason?: unknown) => void = () => undefined
        const result = new Promise<T>((resolve, reject) => {
            resolveResult = resolve
            rejectResult = reject
        })
        mutationTail = mutationTail
            .catch(() => undefined)
            .then(async () => {
                try {
                    resolveResult(await withActivity(operation))
                } catch (error) {
                    if (!(error instanceof ProgramContextChangedError)) rememberError(error)
                    rejectResult(error)
                }
            })
        return result
    }

    async function connect(nextWorkspace: WorkspaceIdentity, preferredFunctionId = ''): Promise<void> {
        const token = ++connectionToken
        status.value = 'loading'
        operationError.value = ''
        conflict.value = null
        workspace.value = nextWorkspace
        clearActiveProgram()
        try {
            const [functionsResult, programsResult] = await withActivity(() => Promise.all([
                programApi.listAvailableFunctions(),
                programApi.listPrograms(nextWorkspace),
            ]))
            if (token !== connectionToken) return
            availableFunctions.value = functionsResult
            programs.value = programsResult
            const functionId = preferredFunctionId || programsResult[0]?.function_id || ''
            if (functionId) {
                const snapshot = await withActivity(() => programApi.getProgram(nextWorkspace, functionId))
                if (token !== connectionToken) return
                adoptSnapshot(snapshot)
            } else {
                status.value = 'ready'
            }
        } catch (error) {
            if (token !== connectionToken) return
            rememberError(error)
            throw error
        }
    }

    async function loadProgram(functionId: string): Promise<void> {
        const currentWorkspace = requireWorkspace()
        const token = ++connectionToken
        status.value = 'loading'
        operationError.value = ''
        try {
            const snapshot = await withActivity(() => programApi.getProgram(currentWorkspace, functionId))
            if (token !== connectionToken) return
            if (statementClipboard.value?.mode === 'cut'
                && statementClipboard.value.document_id !== snapshot.document.document_id) {
                statementClipboard.value = null
            }
            adoptSnapshot(snapshot)
        } catch (error) {
            if (token !== connectionToken) return
            rememberError(error)
            throw error
        }
    }

    async function createProgram(displayName: string): Promise<ProgramSnapshotDto> {
        const name = displayName.trim()
        if (!name) throw new ProgramStoreError('请输入函数名称')
        ensureWritable()
        const currentWorkspace = requireWorkspace()
        const scope = captureScope(false)
        return enqueueMutation(async () => {
            const snapshot = await programApi.createProgram(currentWorkspace, name)
            assertScope(scope)
            if (statementClipboard.value?.mode === 'cut') statementClipboard.value = null
            adoptSnapshot(snapshot)
            return snapshot
        })
    }

    function renameProgram(functionId: string, displayName: string): Promise<ProgramSnapshotDto> {
        const name = displayName.trim()
        if (!name) return Promise.reject(new ProgramStoreError('请输入函数名称'))
        ensureWritable()
        const currentScope = captureScope(false)
        return enqueueMutation(async () => {
            lifecycleBlocker.value = null
            conflict.value = null
            const summary = programs.value.find((item) => item.function_id === functionId)
            if (!summary) throw new ProgramStoreError('项目函数已经不存在')
            let snapshot: ProgramSnapshotDto
            try {
                snapshot = await programApi.renameProgram(requireWorkspace(), functionId, summary.revision, name)
            } catch (error) {
                if (error instanceof ProgramApiError && error.code === 'program_revision_conflict') {
                    const details = error.diagnostics[0] || {}
                    conflict.value = {
                        function_id: functionId,
                        expected_revision: String(details.expected_revision || summary.revision),
                        actual_revision: String(details.actual_revision || ''),
                        message: error.message,
                    }
                }
                throw error
            }
            assertScope(currentScope)
            lifecycleBlocker.value = null
            if (functionId === activeFunctionId.value) adoptSnapshot(snapshot)
            else updateProgramSummary(snapshot)
            return snapshot
        })
    }

    function deleteProgram(functionId: string): Promise<void> {
        ensureWritable()
        const currentScope = captureScope(false)
        return enqueueMutation(async () => {
            lifecycleBlocker.value = null
            conflict.value = null
            const summary = programs.value.find((item) => item.function_id === functionId)
            if (!summary) throw new ProgramStoreError('项目函数已经不存在')
            let response: ProgramDeleteResponseDto
            try {
                response = await programApi.deleteProgram(requireWorkspace(), functionId, summary.revision)
            } catch (error) {
                if (error instanceof ProgramApiError && (
                    error.code === 'program_referenced' || error.code === 'program_entry_delete_forbidden'
                )) {
                    lifecycleBlocker.value = {
                        function_id: functionId,
                        code: error.code,
                        message: error.message,
                        references: error.diagnostics,
                    }
                }
                if (error instanceof ProgramApiError && error.code === 'program_revision_conflict') {
                    const details = error.diagnostics[0] || {}
                    conflict.value = {
                        function_id: functionId,
                        expected_revision: String(details.expected_revision || summary.revision),
                        actual_revision: String(details.actual_revision || ''),
                        message: error.message,
                    }
                }
                throw error
            }
            assertScope(currentScope)
            programs.value = response.programs
            lifecycleBlocker.value = null
            if (functionId !== activeFunctionId.value) return
            clearActiveProgram()
            const next = response.programs[0]
            if (!next) {
                status.value = 'ready'
                return
            }
            const snapshot = await programApi.getProgram(requireWorkspace(), next.function_id)
            assertScope(currentScope)
            adoptSnapshot(snapshot)
        })
    }

    function setProjectVariableCatalog(values: AvailableProgramValue[]): void {
        projectVariableNames.value = Object.fromEntries(values
            .filter((item) => item.source === 'project')
            .map((item) => [item.id, item.display_name]))
        if (serverSnapshot.value) {
            document.value = programSnapshotToUiDocument(serverSnapshot.value, availableFunctions.value, {
                projectVariableNames: projectVariableNames.value,
            })
        }
    }

    function clearLifecycleBlocker(): void { lifecycleBlocker.value = null }

    async function applyOne(command: ProgramServerCommand, scope: ProgramOperationScope): Promise<ProgramSnapshotDto> {
        assertScope(scope)
        ensureWritable()
        const currentWorkspace = requireWorkspace()
        const current = requireSnapshot()
        const snapshot = await programApi.applyCommand(
            currentWorkspace,
            current.document.function.function_id,
            current.revision,
            command,
        )
        assertScope(scope)
        adoptSnapshot(snapshot)
        return snapshot
    }

    async function applyMany(commands: ProgramServerCommand[], scope: ProgramOperationScope): Promise<ProgramSnapshotDto> {
        assertScope(scope)
        ensureWritable()
        if (!commands.length) throw new ProgramStoreError('批量操作没有可执行内容')
        const currentWorkspace = requireWorkspace()
        const current = requireSnapshot()
        const snapshot = await programApi.applyCommands(
            currentWorkspace,
            current.document.function.function_id,
            current.revision,
            commands,
        )
        assertScope(scope)
        adoptSnapshot(snapshot)
        return snapshot
    }

    function insertionLocation(): ProgramStatementLocationDto {
        const current = requireSnapshot()
        const selectedTarget = insertionTarget.value
        if (selectedTarget) {
            const location = resolvedInsertionTarget(current.document.function.statements, selectedTarget)
            if (location) return location
        }
        const selected = selectedStatementIds.value.at(-1)
        if (!selected) return { parent_statement_id: null, block: 'root', before_statement_id: null }
        const container = findStatementContainer(current.document.function.statements, selected)
        if (!container) return { parent_statement_id: null, block: 'root', before_statement_id: null }
        return locationInContainer(container, container.statements[container.index + 1]?.statement_id || null)
    }

    function insertFunction(functionId: string): Promise<ProgramSnapshotDto> {
        if (!availableFunctionIds.value.has(functionId)) {
            return Promise.reject(new ProgramStoreError('该函数尚未由后端确认可运行，不能插入'))
        }
        if (functionId === activeFunctionId.value) {
            return Promise.reject(new ProgramStoreError('项目函数不能直接调用自身'))
        }
        const scope = captureScope()
        return enqueueMutation(() => applyOne({
            kind: 'insert_call',
            function_id: functionId,
            location: insertionLocation(),
        }, scope))
    }

    function insertStructure(kind: ProgramStructureKind, options: ProgramStructureInsertOptions = {}): Promise<ProgramSnapshotDto> {
        const scope = captureScope()
        const location = insertionLocation()
        let command: ProgramServerCommand
        if (kind === 'assignment') {
            const assignmentTarget = options.assignment_target
            command = {
                kind: 'insert_assignment',
                target: assignmentTarget || {
                    kind: 'local',
                    symbol_id: newClientStableId('symbol'),
                    display_name: '新变量',
                    value_type: 'null',
                    declare: true,
                },
                value: assignmentTarget
                    ? uiProgramValueToServerValue(defaultProgramValue(
                        assignmentTarget.value_type,
                        newClientStableId('value'),
                    ))
                    : { value_id: newClientStableId('value'), kind: 'null' },
                location,
            }
        } else if (kind === 'if') {
            command = {
                kind: 'insert_if',
                condition: { value_id: newClientStableId('value'), kind: 'bool', value: true },
                location,
            }
        } else if (kind === 'loop') {
            command = {
                kind: 'insert_loop',
                mode: 'repeat',
                source: { value_id: newClientStableId('value'), kind: 'int64', value: 1 },
                location,
            }
        } else if (kind === 'break' || kind === 'continue') {
            const current = requireSnapshot()
            if (!locationIsInsideLoop(current.document.function.statements, location)) {
                return Promise.reject(new ProgramStoreError(
                    `${kind === 'break' ? '跳出循环' : '跳过本轮'}只能插入到循环体内`,
                ))
            }
            command = { kind: kind === 'break' ? 'insert_break' : 'insert_continue', location }
        } else if (kind === 'fail') {
            command = {
                kind: 'insert_fail',
                error_id: 'project.explicit_failure',
                message: { value_id: newClientStableId('value'), kind: 'string', value: '任务未满足继续执行条件' },
                details: null,
                location,
            }
        } else if (kind === 'try') {
            command = { kind: 'insert_try', location }
        } else if (kind === 'target_scope') {
            command = {
                kind: 'insert_target_scope',
                target: options.target_id
                    ? { value_id: newClientStableId('value'), kind: 'target_ref', target_id: options.target_id }
                    : { value_id: newClientStableId('value'), kind: 'unset', expected_type: 'target_ref' },
                location,
            }
        } else if (kind === 'listen') {
            const handlerFunctionId = options.handler_function_id
                || programs.value.find((item) => item.function_id !== activeFunctionId.value)?.function_id
            if (!handlerFunctionId) {
                return Promise.reject(new ProgramStoreError('请先创建另一个项目函数，用来处理收到的消息'))
            }
            command = {
                kind: 'insert_listen',
                event_source: {
                    kind: 'message',
                    name: { value_id: newClientStableId('value'), kind: 'string', value: '消息' },
                    sender: null,
                },
                receive_binding: {
                    symbol_id: newClientStableId('symbol'),
                    display_name: '收到的消息',
                    value_type: 'message',
                },
                handler_function_id: handlerFunctionId,
                condition: null,
                handler_arguments: {},
                location,
            }
        } else {
            command = { kind: 'insert_return', value: null, location }
        }
        return enqueueMutation(() => applyOne(command, scope))
    }

    async function moveStatements(
        statementIdsToMove: string[],
        direction: 'up' | 'down',
        scope: ProgramOperationScope,
    ): Promise<void> {
        const current = requireSnapshot()
        const containers = statementIdsToMove.map((statementId) => (
            findStatementContainer(current.document.function.statements, statementId)
        ))
        if (!containers.length || containers.some((item) => !item)) {
            throw new ProgramStoreError('所选语句已经变化，请重新选择')
        }
        const first = containers[0] as StatementContainer
        if (containers.some((item) => item?.statements !== first.statements)) {
            throw new ProgramStoreError('只能同时移动同一个语句块中的语句')
        }
        const indexes = (containers as StatementContainer[]).map((item) => item.index).sort((left, right) => left - right)
        if (indexes.some((index, offset) => index !== indexes[0] + offset)) {
            throw new ProgramStoreError('只能同时移动连续语句')
        }
        if (direction === 'up' && indexes[0] === 0) return
        if (direction === 'down' && indexes.at(-1) === first.statements.length - 1) return
        const before = direction === 'up'
            ? first.statements[indexes[0] - 1]?.statement_id || null
            : first.statements[(indexes.at(-1) as number) + 2]?.statement_id || null
        await applyOne({
            kind: 'move_statements',
            statement_ids: statementIdsToMove,
            location: locationInContainer(first, before),
        }, scope)
        setSelectedStatementIds(statementIdsToMove)
    }

    async function changeStatementNesting(
        statementIdsToMove: string[],
        direction: 'in' | 'out',
        scope: ProgramOperationScope,
    ): Promise<void> {
        const current = requireSnapshot()
        const containers = statementIdsToMove.map((statementId) => (
            findStatementContainer(current.document.function.statements, statementId)
        ))
        if (!containers.length || containers.some((item) => !item)) {
            throw new ProgramStoreError('所选语句已经变化，请重新选择')
        }
        const first = containers[0] as StatementContainer
        if (containers.some((item) => item?.statements !== first.statements)) {
            throw new ProgramStoreError('只能同时调整同一个语句块中的语句')
        }
        const indexes = (containers as StatementContainer[]).map((item) => item.index).sort((left, right) => left - right)
        if (indexes.some((index, offset) => index !== indexes[0] + offset)) {
            throw new ProgramStoreError('只能同时调整连续语句的层级')
        }

        let location: ProgramStatementLocationDto
        if (direction === 'in') {
            const previous = first.statements[indexes[0] - 1]
            if (!previous || statementIdsToMove.includes(previous.statement_id)) {
                throw new ProgramStoreError('前面没有可以容纳这些语句的语句块')
            }
            const child = serverChildBlocks(previous)[0]
            if (!child) throw new ProgramStoreError('上一条不是语句块，不能移入')
            location = {
                parent_statement_id: previous.statement_id,
                block: child.block,
                clause_id: child.clause_id || null,
                before_statement_id: null,
            }
        } else {
            if (!first.parent_statement_id) throw new ProgramStoreError('这些语句已经位于函数最外层')
            const parentContainer = findStatementContainer(
                current.document.function.statements,
                first.parent_statement_id,
            )
            if (!parentContainer) throw new ProgramStoreError('父级语句块已经变化，请重新选择')
            location = locationInContainer(
                parentContainer,
                parentContainer.statements[parentContainer.index + 1]?.statement_id || null,
            )
        }

        await applyOne({ kind: 'move_statements', statement_ids: statementIdsToMove, location }, scope)
        setSelectedStatementIds(statementIdsToMove)
    }

    function clipboardSelection(statementIdsToCopy: string[]): { ids: string[]; statements: ServerProgramStatement[] } {
        const current = requireSnapshot()
        const containers = [...new Set(statementIdsToCopy)].map((statementId) => (
            findStatementContainer(current.document.function.statements, statementId)
        ))
        if (!containers.length || containers.some((item) => !item)) {
            throw new ProgramStoreError('所选语句已经变化，请重新选择')
        }
        const first = containers[0] as StatementContainer
        if (containers.some((item) => item?.statements !== first.statements)) {
            throw new ProgramStoreError('复制或剪切时请选择同一个语句块中的语句')
        }
        const ordered = (containers as StatementContainer[]).sort((left, right) => left.index - right.index)
        return {
            ids: ordered.map((item) => item.statements[item.index].statement_id),
            statements: ordered.map((item) => structuredClone(item.statements[item.index])),
        }
    }

    function copyStatements(statementIdsToCopy: string[]): void {
        const currentWorkspace = requireWorkspace()
        const current = requireSnapshot()
        const selection = clipboardSelection(statementIdsToCopy)
        statementClipboard.value = {
            mode: 'copy',
            workspace_id: currentWorkspace.workspace_id,
            workspace_generation: currentWorkspace.generation,
            document_id: current.document.document_id,
            source_function_id: current.document.function.function_id,
            statement_ids: selection.ids,
            statements: selection.statements,
        }
        operationError.value = ''
    }

    function cutStatements(statementIdsToCut: string[]): void {
        ensureWritable()
        const currentWorkspace = requireWorkspace()
        const current = requireSnapshot()
        const selection = clipboardSelection(statementIdsToCut)
        statementClipboard.value = {
            mode: 'cut',
            workspace_id: currentWorkspace.workspace_id,
            workspace_generation: currentWorkspace.generation,
            document_id: current.document.document_id,
            source_function_id: current.document.function.function_id,
            statement_ids: selection.ids,
            statements: selection.statements,
        }
        operationError.value = ''
    }

    function cancelStatementClipboard(): void {
        statementClipboard.value = null
    }

    async function duplicateStatements(statementIdsToCopy: string[], scope: ProgramOperationScope): Promise<void> {
        const current = requireSnapshot()
        const selection = clipboardSelection(statementIdsToCopy)
        const last = selection.ids.at(-1) as string
        const container = findStatementContainer(current.document.function.statements, last)
        if (!container) throw new ProgramStoreError('所选语句已经变化，请重新选择')
        const beforeIds = new Set(statementIds(current.document.function.statements))
        const result = await applyOne({
            kind: 'paste_statements',
            statements: selection.statements,
            location: locationInContainer(container, container.statements[container.index + 1]?.statement_id || null),
        }, scope)
        const createdStatementIds = statementIds(result.document.function.statements).filter((id) => !beforeIds.has(id))
        setSelectedStatementIds(createdStatementIds)
    }

    async function pasteStatements(scope: ProgramOperationScope): Promise<void> {
        const clipboard = statementClipboard.value
        const currentWorkspace = requireWorkspace()
        const current = requireSnapshot()
        const sameWorkspace = clipboard
            && clipboard.workspace_id === currentWorkspace.workspace_id
            && clipboard.workspace_generation === currentWorkspace.generation
        if (!clipboard || !sameWorkspace
            || (clipboard.mode === 'cut' && clipboard.document_id !== current.document.document_id)) {
            throw new ProgramStoreError('当前函数没有可粘贴的语句')
        }
        const location = insertionLocation()
        if (clipboard.mode === 'copy') {
            const beforeIds = new Set(statementIds(current.document.function.statements))
            let result: ProgramSnapshotDto
            try {
                result = await applyOne({
                    kind: 'paste_statements',
                    statements: clipboard.statements.map((statement) => structuredClone(statement)),
                    location,
                }, scope)
            } catch (error) {
                const crossingFunctions = clipboard.source_function_id !== current.document.function.function_id
                if (crossingFunctions && error instanceof ProgramApiError && error.code === 'program_command_invalid') {
                    throw new ProgramStoreError(
                        `无法粘贴到当前函数：${error.message}。请同时复制所依赖的局部语句，或在目标函数中重新选择兼容的变量。`,
                    )
                }
                throw error
            }
            const createdStatementIds = statementIds(result.document.function.statements).filter((id) => !beforeIds.has(id))
            setSelectedStatementIds(createdStatementIds)
            return
        }
        const existingIds = new Set(statementIds(current.document.function.statements))
        if (clipboard.statement_ids.some((id) => !existingIds.has(id))) {
            statementClipboard.value = null
            throw new ProgramStoreError('待剪切语句已经变化，请重新剪切')
        }
        const anchor = selectedStatementIds.value.at(-1)
        if ((anchor && clipboard.statement_ids.includes(anchor))
            || (location.before_statement_id && clipboard.statement_ids.includes(location.before_statement_id))) {
            statementClipboard.value = null
            setSelectedStatementIds(clipboard.statement_ids)
            return
        }
        await applyOne({
            kind: 'move_statements',
            statement_ids: clipboard.statement_ids,
            location,
        }, scope)
        statementClipboard.value = null
        setSelectedStatementIds(clipboard.statement_ids)
    }

    async function deleteStatements(statementIdsToDelete: string[], scope: ProgramOperationScope): Promise<void> {
        await applyOne({ kind: 'delete_statements', statement_ids: statementIdsToDelete }, scope)
        if (statementClipboard.value?.mode === 'cut'
            && statementClipboard.value.statement_ids.some((id) => statementIdsToDelete.includes(id))) {
            statementClipboard.value = null
        }
    }

    async function batchUpdateValues(
        statementIdsToUpdate: string[],
        parameterId: string,
        next: ProgramValueDraft,
        scope: ProgramOperationScope,
    ): Promise<void> {
        const current = requireSnapshot()
        const calls = statementIdsToUpdate.map((statementId) => (
            findServerStatement(current.document.function.statements, statementId)
        ))
        if (!calls.length || calls.some((statement) => statement?.kind !== 'call')) {
            throw new ProgramStoreError('批量参数编辑只支持同一函数的调用语句')
        }
        const functionId = calls[0]?.kind === 'call' ? calls[0].function_id : ''
        if (calls.some((statement) => statement?.kind !== 'call' || statement.function_id !== functionId)) {
            throw new ProgramStoreError('请选择同一个函数的调用语句再批量编辑')
        }
        const sanitized = draftWithoutStableIds(next)
        const commands: ProgramServerCommand[] = calls.map((statement) => {
            if (!statement || statement.kind !== 'call') throw new ProgramStoreError('所选语句已经变化，请重新选择')
            const currentValue = statement.arguments[parameterId]
            if (!currentValue) throw new ProgramStoreError('所选语句缺少这个公共参数')
            return {
                kind: 'update_argument',
                statement_id: statement.statement_id,
                parameter_id: parameterId,
                value: uiDraftToServerValue(currentValue.value_id, sanitized),
            }
        })
        await applyMany(commands, scope)
        setSelectedStatementIds(statementIdsToUpdate)
    }

    function applyUiCommand(envelope: ProgramCommandEnvelope): Promise<void> {
        const current = requireSnapshot()
        if (envelope.document_id !== current.document.document_id || envelope.base_revision !== current.revision) {
            return Promise.reject(new ProgramStoreError('编辑视图已过期，请重新选择当前语句后再试'))
        }
        const scope = captureScope()
        return enqueueMutation(async () => {
            const command: ProgramCommand = envelope.command
            if (command.kind === 'repair_missing_arguments') {
                await applyOne({
                    kind: 'repair_missing_arguments',
                    statement_id: command.statement_id,
                }, scope)
                return
            }
            if (command.kind === 'update_value') {
                await applyOne(uiValueUpdateToServerCommand(command), scope)
                return
            }
            if (command.kind === 'move_statements') {
                await moveStatements(command.statement_ids, command.direction, scope)
                return
            }
            if (command.kind === 'change_statement_nesting') {
                await changeStatementNesting(command.statement_ids, command.direction, scope)
                return
            }
            if (command.kind === 'copy_statements') {
                copyStatements(command.statement_ids)
                return
            }
            if (command.kind === 'cut_statements') {
                cutStatements(command.statement_ids)
                return
            }
            if (command.kind === 'duplicate_statements') {
                await duplicateStatements(command.statement_ids, scope)
                return
            }
            if (command.kind === 'paste_statements') {
                await pasteStatements(scope)
                return
            }
            if (command.kind === 'cancel_statement_clipboard') {
                cancelStatementClipboard()
                return
            }
            if (command.kind === 'batch_update_values') {
                await batchUpdateValues(command.statement_ids, command.parameter_id, command.next, scope)
                return
            }
            if (command.kind === 'delete_statements') {
                await deleteStatements(command.statement_ids, scope)
                return
            }
            if (command.kind === 'set_result_binding') {
                const statement = findServerStatement(requireSnapshot().document.function.statements, command.statement_id)
                if (!statement || statement.kind !== 'call') throw new ProgramStoreError('只有函数调用可以保存返回结果')
                const contract = availableFunctions.value.find((item) => item.function_id === statement.function_id)
                if (!contract || contract.return_type === 'unit') throw new ProgramStoreError('该函数没有可保存的返回结果')
                const target = command.target
                const displayName = target?.display_name.trim() || ''
                await applyOne({
                    kind: 'set_result_binding',
                    statement_id: command.statement_id,
                    binding: target && displayName ? {
                        symbol_id: target.kind === 'existing_local'
                            ? target.symbol_id
                            : statement.result_binding?.declare
                                ? statement.result_binding.symbol_id
                                : newClientStableId('symbol'),
                        display_name: displayName,
                        value_type: target.kind === 'existing_local' ? target.value_type : contract.return_type,
                        declare: target.kind === 'new_local',
                    } : null,
                }, scope)
                return
            }
            if (command.kind === 'insert_if_from_call_result') {
                await applyOne({
                    kind: 'insert_if_from_call_result',
                    statement_id: command.statement_id,
                }, scope)
                return
            }
            if (command.kind === 'set_step_label') {
                await applyOne({
                    kind: 'set_step_label',
                    statement_id: command.statement_id,
                    label: command.step_label,
                }, scope)
                return
            }
            const structureCommand = uiStructureCommandToServerCommand(command)
            if (structureCommand) {
                await applyOne(structureCommand, scope)
                return
            }
            throw new ProgramStoreError('该编辑能力尚未进入 Program Service，界面不会伪造保存结果')
        })
    }

    function extractStatements(statementIdsToExtract: string[], displayName: string): Promise<void> {
        const name = displayName.trim()
        if (!name) return Promise.reject(new ProgramStoreError('请输入提取后的函数名称'))
        const scope = captureScope()
        return enqueueMutation(async () => {
            assertScope(scope)
            ensureWritable()
            const currentWorkspace = requireWorkspace()
            const current = requireSnapshot()
            const response = await programApi.extractStatements(
                currentWorkspace,
                current.document.function.function_id,
                current.revision,
                statementIdsToExtract,
                name,
            )
            assertScope(scope)
            const index = programs.value.findIndex((item) => item.function_id === response.extracted_program.function_id)
            programs.value = index < 0
                ? [...programs.value, response.extracted_program]
                : programs.value.map((item, itemIndex) => itemIndex === index ? response.extracted_program : item)
            adoptSnapshot(response)
        })
    }

    function undo(): Promise<void> {
        const scope = captureScope()
        return enqueueMutation(async () => {
            assertScope(scope)
            ensureWritable()
            const currentWorkspace = requireWorkspace()
            const current = requireSnapshot()
            if (!current.can_undo) throw new ProgramStoreError('当前没有可撤销的操作')
            const snapshot = await programApi.undo(
                currentWorkspace,
                current.document.function.function_id,
                current.revision,
            )
            assertScope(scope)
            if (snapshot.programs) programs.value = snapshot.programs
            adoptSnapshot(snapshot)
        })
    }

    function redo(): Promise<void> {
        const scope = captureScope()
        return enqueueMutation(async () => {
            assertScope(scope)
            ensureWritable()
            const currentWorkspace = requireWorkspace()
            const current = requireSnapshot()
            if (!current.can_redo) throw new ProgramStoreError('当前没有可重做的操作')
            const snapshot = await programApi.redo(
                currentWorkspace,
                current.document.function.function_id,
                current.revision,
            )
            assertScope(scope)
            if (snapshot.programs) programs.value = snapshot.programs
            adoptSnapshot(snapshot)
        })
    }

    async function reloadConflict(): Promise<void> {
        const currentWorkspace = requireWorkspace()
        const functionId = conflict.value?.function_id || activeFunctionId.value
        if (!functionId) throw new ProgramStoreError('没有可重新加载的函数')
        try {
            const snapshot = await withActivity(() => programApi.getProgram(currentWorkspace, functionId))
            adoptSnapshot(snapshot)
        } catch (error) {
            rememberError(error)
            throw error
        }
    }

    async function loadHistory(): Promise<ProgramHistoryDto> {
        const currentWorkspace = requireWorkspace()
        const current = requireSnapshot()
        const scope = captureScope()
        const result = await withActivity(() => programApi.getProgramHistory(
            currentWorkspace,
            current.document.function.function_id,
        ))
        assertScope(scope)
        history.value = result
        return result
    }

    function restoreHistory(historyId: string): Promise<void> {
        const scope = captureScope()
        return enqueueMutation(async () => {
            assertScope(scope)
            ensureWritable()
            const current = requireSnapshot()
            const snapshot = await programApi.restoreProgramHistory(
                requireWorkspace(),
                current.document.function.function_id,
                current.revision,
                historyId,
            )
            assertScope(scope)
            adoptSnapshot(snapshot)
            history.value = null
        })
    }

    async function compile(targetPlatform?: ExecutionPlatformId): Promise<ProgramCompileResponse> {
        const currentWorkspace = requireWorkspace()
        const current = requireSnapshot()
        try {
            const result = await withActivity(() => programApi.compile(
                currentWorkspace,
                current.document.function.function_id,
                targetPlatform,
            ))
            lastCompile.value = result
            operationError.value = ''
            return result
        } catch (error) {
            rememberError(error)
            throw error
        }
    }

    async function run(payload: ProgramRunRequest = {}): Promise<ProgramRunResponse> {
        const currentWorkspace = requireWorkspace()
        const current = requireSnapshot()
        try {
            const result = await withActivity(() => programApi.run(
                currentWorkspace,
                current.document.function.function_id,
                payload,
            ))
            lastRun.value = result
            operationError.value = ''
            return result
        } catch (error) {
            rememberError(error)
            throw error
        }
    }

    function setSelectedStatementIds(statementIdsToSelect: string[]): void {
        const valid = new Set(statementIds(serverSnapshot.value?.document.function.statements || []))
        selectedStatementIds.value = [...new Set(statementIdsToSelect)].filter((id) => valid.has(id))
        if (selectedStatementIds.value.length) insertionTarget.value = null
    }

    function setInsertionTarget(target: ProgramInsertionTarget | null): void {
        if (!target) {
            insertionTarget.value = null
            return
        }
        const current = requireSnapshot()
        if (!resolvedInsertionTarget(current.document.function.statements, target)) {
            throw new ProgramStoreError('所选插入位置已经失效，请重新选择')
        }
        insertionTarget.value = { ...target }
        selectedStatementIds.value = []
    }

    function setCollapsedStatementIds(statementIdsToCollapse: string[]): void {
        const valid = new Set(statementIds(serverSnapshot.value?.document.function.statements || []))
        collapsedStatementIds.value = [...new Set(statementIdsToCollapse)].filter((id) => valid.has(id))
    }

    function reset(): void {
        connectionToken += 1
        workspace.value = null
        programs.value = []
        availableFunctions.value = []
        clearActiveProgram()
        status.value = 'idle'
        operationError.value = ''
        lifecycleBlocker.value = null
        projectVariableNames.value = {}
        pendingCount.value = 0
        mutationTail = Promise.resolve()
    }

    return {
        workspace,
        programs,
        availableFunctions,
        serverSnapshot,
        document,
        selectedStatementIds,
        insertionTarget,
        collapsedStatementIds,
        status,
        operationError,
        conflict,
        lifecycleBlocker,
        lastCompile,
        lastRun,
        history,
        busy,
        activeFunctionId,
        functionContracts,
        availableFunctionIds,
        canUndo,
        canRedo,
        readOnly,
        pendingCutStatementIds,
        statementClipboardCount,
        canPasteStatements,
        effectiveDiagnostics,
        diagnosticsByValueId,
        statementStates,
        connect,
        loadProgram,
        createProgram,
        renameProgram,
        deleteProgram,
        insertFunction,
        insertStructure,
        applyUiCommand,
        extractStatements,
        undo,
        redo,
        reloadConflict,
        loadHistory,
        restoreHistory,
        compile,
        run,
        adoptSnapshot,
        setSelectedStatementIds,
        setInsertionTarget,
        setCollapsedStatementIds,
        setProjectVariableCatalog,
        clearLifecycleBlocker,
        reset,
    }
})

export { ProgramApiError, ProgramProjectionError }
