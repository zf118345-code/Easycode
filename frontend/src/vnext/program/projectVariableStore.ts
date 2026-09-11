import { computed, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'
import type { WorkspaceIdentity } from '../types'
import { serverValueToUiValue, uiProgramValueToServerValue } from './adapter'
import { ProgramApiError, programApi } from './api'
import type {
    AvailableProgramValue,
    ProgramValueNode,
    ProjectVariableDefinition,
} from './types'
import type {
    ProjectVariableReferenceDto,
    ProjectVariableSnapshotDto,
    ServerProgramValueNode,
} from './serverTypes'

export type ProjectVariableStoreStatus = 'idle' | 'loading' | 'ready' | 'error' | 'conflict'

export interface ProjectVariableRevisionConflict {
    expected_revision: string
    actual_revision: string
    message: string
}

export interface ProjectVariableMutation {
    display_name?: string
    value_type?: string
    default_value?: ProgramValueNode
    description?: string
    constraints?: Record<string, unknown>
}

interface OperationScope {
    token: number
    workspace_id: string
    generation: number
}

export class ProjectVariableStoreError extends Error {
    constructor(message: string) {
        super(message)
        this.name = 'ProjectVariableStoreError'
    }
}

function projectSnapshot(snapshot: ProjectVariableSnapshotDto): ProjectVariableDefinition[] {
    return snapshot.variables.map((variable) => ({
        variable_id: variable.variable_id,
        display_name: variable.display_name,
        value_type: variable.value_type,
        default_value: serverValueToUiValue(variable.default_value),
        description: variable.description,
        constraints: { ...variable.constraints },
    }))
}

function referenceDiagnostics(diagnostics: Array<Record<string, unknown>>): ProjectVariableReferenceDto[] {
    return diagnostics.flatMap((item) => typeof item.kind === 'string' ? [{
        kind: item.kind,
        ...(typeof item.function_id === 'string' ? { function_id: item.function_id } : {}),
        ...(typeof item.function_name === 'string' ? { function_name: item.function_name } : {}),
        ...(typeof item.statement_id === 'string' ? { statement_id: item.statement_id } : {}),
        ...(typeof item.value_id === 'string' ? { value_id: item.value_id } : {}),
        ...(typeof item.field === 'string' ? { field: item.field } : {}),
        ...(typeof item.path === 'string' ? { path: item.path } : {}),
        ...(typeof item.location === 'string' ? { location: item.location } : {}),
    }] : [])
}

export const useProjectVariableStore = defineStore('vnext-project-variables', () => {
    const workspace = ref<WorkspaceIdentity | null>(null)
    const serverSnapshot = shallowRef<ProjectVariableSnapshotDto | null>(null)
    const variables = shallowRef<ProjectVariableDefinition[]>([])
    const selectedVariableId = ref('')
    const status = ref<ProjectVariableStoreStatus>('idle')
    const operationError = ref('')
    const conflict = ref<ProjectVariableRevisionConflict | null>(null)
    const blockedReferences = shallowRef<ProjectVariableReferenceDto[]>([])
    const pendingCount = ref(0)
    let connectionToken = 0
    let mutationTail: Promise<void> = Promise.resolve()

    const busy = computed(() => pendingCount.value > 0)
    const revision = computed(() => serverSnapshot.value?.revision || '')
    const selectedVariable = computed(() => variables.value.find((item) => item.variable_id === selectedVariableId.value) || null)
    const availableValues = computed<AvailableProgramValue[]>(() => variables.value.map((item) => ({
        source: 'project', id: item.variable_id, display_name: item.display_name, value_type: item.value_type,
    })))

    function requireWorkspace(): WorkspaceIdentity {
        if (!workspace.value) throw new ProjectVariableStoreError('请先打开项目')
        return workspace.value
    }

    function requireSnapshot(): ProjectVariableSnapshotDto {
        if (!serverSnapshot.value) throw new ProjectVariableStoreError('项目变量尚未载入')
        return serverSnapshot.value
    }

    function ensureWritable(): void {
        if (workspace.value?.read_only) throw new ProjectVariableStoreError('当前项目为只读，不能修改项目变量')
    }

    function scope(): OperationScope {
        const current = requireWorkspace()
        return { token: connectionToken, workspace_id: current.workspace_id, generation: current.generation }
    }

    function assertScope(current: OperationScope): void {
        if (
            current.token !== connectionToken
            || workspace.value?.workspace_id !== current.workspace_id
            || workspace.value?.generation !== current.generation
        ) throw new ProjectVariableStoreError('项目已经切换，旧变量操作未应用')
    }

    function adoptSnapshot(snapshot: ProjectVariableSnapshotDto): void {
        serverSnapshot.value = snapshot
        variables.value = projectSnapshot(snapshot)
        const preferred = snapshot.selected_variable_id || selectedVariableId.value
        selectedVariableId.value = variables.value.some((item) => item.variable_id === preferred)
            ? preferred
            : variables.value[0]?.variable_id || ''
        status.value = 'ready'
        operationError.value = ''
        conflict.value = null
        blockedReferences.value = []
    }

    function rememberError(error: unknown): void {
        operationError.value = error instanceof Error ? error.message : '项目变量操作未完成'
        if (error instanceof ProgramApiError && error.code === 'project_variable_revision_conflict') {
            const details = error.diagnostics[0] || {}
            conflict.value = {
                expected_revision: String(details.expected_revision || revision.value),
                actual_revision: String(details.actual_revision || ''),
                message: error.message,
            }
            status.value = 'conflict'
            return
        }
        if (error instanceof ProgramApiError && error.code === 'project_variable_referenced') {
            blockedReferences.value = referenceDiagnostics(error.diagnostics)
        }
        status.value = serverSnapshot.value ? 'ready' : 'error'
    }

    async function withActivity<T>(operation: () => Promise<T>): Promise<T> {
        pendingCount.value += 1
        try { return await operation() } finally { pendingCount.value = Math.max(0, pendingCount.value - 1) }
    }

    function enqueue<T>(operation: () => Promise<T>): Promise<T> {
        let resolveResult: (value: T | PromiseLike<T>) => void = () => undefined
        let rejectResult: (reason?: unknown) => void = () => undefined
        const result = new Promise<T>((resolve, reject) => { resolveResult = resolve; rejectResult = reject })
        mutationTail = mutationTail.catch(() => undefined).then(async () => {
            try { resolveResult(await withActivity(operation)) } catch (error) { rememberError(error); rejectResult(error) }
        })
        return result
    }

    async function connect(nextWorkspace: WorkspaceIdentity): Promise<void> {
        const token = ++connectionToken
        workspace.value = nextWorkspace
        // A workspace switch must never project the previous project's variables
        // while the new snapshot is loading (or when loading fails).
        serverSnapshot.value = null
        variables.value = []
        selectedVariableId.value = ''
        status.value = 'loading'
        operationError.value = ''
        conflict.value = null
        blockedReferences.value = []
        try {
            const snapshot = await withActivity(() => programApi.getProjectVariables(nextWorkspace))
            if (token !== connectionToken) return
            adoptSnapshot(snapshot)
        } catch (error) {
            if (token !== connectionToken) return
            rememberError(error)
            throw error
        }
    }

    function reload(): Promise<void> {
        const currentWorkspace = requireWorkspace()
        const currentScope = scope()
        return withActivity(async () => {
            const snapshot = await programApi.getProjectVariables(currentWorkspace)
            assertScope(currentScope)
            adoptSnapshot(snapshot)
        })
    }

    function createVariable(payload: {
        display_name: string; value_type: string; default_value: ProgramValueNode
        description?: string; constraints?: Record<string, unknown>
    }): Promise<ProjectVariableDefinition> {
        ensureWritable()
        const currentScope = scope()
        return enqueue(async () => {
            const current = requireSnapshot()
            const snapshot = await programApi.createProjectVariable(requireWorkspace(), current.revision, {
                display_name: payload.display_name.trim(),
                value_type: payload.value_type.trim(),
                default_value: uiProgramValueToServerValue(payload.default_value),
                description: payload.description || '',
                constraints: payload.constraints || {},
            })
            assertScope(currentScope)
            adoptSnapshot(snapshot)
            const created = variables.value.find((item) => item.variable_id === snapshot.selected_variable_id)
            if (!created) throw new ProjectVariableStoreError('服务已创建变量，但没有返回新变量标识')
            return created
        })
    }

    function updateVariable(variableId: string, changes: ProjectVariableMutation): Promise<ProjectVariableDefinition> {
        ensureWritable()
        const currentScope = scope()
        return enqueue(async () => {
            const current = requireSnapshot()
            const payload: {
                display_name?: string
                value_type?: string
                default_value?: ServerProgramValueNode
                description?: string
                constraints?: Record<string, unknown>
            } = {}
            if (changes.display_name !== undefined) payload.display_name = changes.display_name.trim()
            if (changes.value_type !== undefined) payload.value_type = changes.value_type.trim()
            if (changes.default_value !== undefined) payload.default_value = uiProgramValueToServerValue(changes.default_value)
            if (changes.description !== undefined) payload.description = changes.description
            if (changes.constraints !== undefined) payload.constraints = changes.constraints
            const snapshot = await programApi.updateProjectVariable(requireWorkspace(), variableId, current.revision, payload)
            assertScope(currentScope)
            adoptSnapshot(snapshot)
            const updated = variables.value.find((item) => item.variable_id === variableId)
            if (!updated) throw new ProjectVariableStoreError('服务已保存变量，但返回快照缺少该变量')
            return updated
        })
    }

    function deleteVariable(variableId: string): Promise<void> {
        ensureWritable()
        const currentScope = scope()
        return enqueue(async () => {
            const current = requireSnapshot()
            const snapshot = await programApi.deleteProjectVariable(requireWorkspace(), variableId, current.revision)
            assertScope(currentScope)
            adoptSnapshot(snapshot)
        })
    }

    function loadReferences(variableId: string): Promise<ProjectVariableReferenceDto[]> {
        const currentScope = scope()
        return withActivity(async () => {
            const result = await programApi.getProjectVariableReferences(requireWorkspace(), variableId)
            assertScope(currentScope)
            blockedReferences.value = result
            return result
        })
    }

    function reset(): void {
        connectionToken += 1
        workspace.value = null
        serverSnapshot.value = null
        variables.value = []
        selectedVariableId.value = ''
        status.value = 'idle'
        operationError.value = ''
        conflict.value = null
        blockedReferences.value = []
        pendingCount.value = 0
        mutationTail = Promise.resolve()
    }

    return {
        workspace, serverSnapshot, variables, selectedVariableId, selectedVariable, availableValues,
        status, operationError, conflict, blockedReferences, busy, revision,
        connect, reload, createVariable, updateVariable, deleteVariable, loadReferences, reset,
    }
})
