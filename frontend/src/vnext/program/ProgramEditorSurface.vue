<template>
    <div
        ref="surfaceElement"
        class="program-editor-surface"
        :class="{ 'without-inspector': !effectiveInspectorVisible || compactInspector }"
        :style="{ '--program-inspector-width': `${inspectorWidth}px` }"
    >
        <div class="surface-main-header">
            <slot name="header"></slot>
        </div>
        <ProgramStatementList
            class="surface-statement-list"
            :statements="document.function.statements"
            :selected-statement-ids="localSelection"
            :collapsed-statement-ids="collapsedStatementIds"
            :selected-insertion-target-key="insertionTarget?.key || ''"
            :pending-cut-statement-ids="pendingCutStatementIds"
            :can-paste="canPaste"
            :statement-states="statementStates"
            :assets="assets"
            :target-options="targetOptions"
            :load-asset-preview="loadAssetPreview"
            :busy="busy"
            :quick-insert-candidates="quickInsertCandidates"
            :recent-quick-insert-keys="recentQuickInsertKeys"
            :insert-quick-function="insertQuickFunction"
            @update:selected-statement-ids="updateSelection"
            @update:collapsed-statement-ids="emit('update:collapsedStatementIds', $event)"
            @update:insertion-target="emit('update:insertionTarget', $event)"
            @action="handleListAction"
            @toggle-breakpoint="emit('toggleBreakpoint', $event)"
            @request-function-library="emit('requestFunctionLibrary', $event)"
        />

        <button
            v-if="showInspectorToggle && showInspector && compactInspector && !effectiveInspectorVisible"
            ref="inspectorDrawerToggle"
            type="button"
            class="inspector-drawer-toggle"
            aria-label="打开语句检查器"
            title="打开语句检查器"
            @click="openInspectorDrawer"
        ><PanelRightOpen :size="15" aria-hidden="true" /></button>
        <div v-if="effectiveInspectorVisible && compactInspector" class="inspector-drawer-scrim" aria-hidden="true" @click="closeInspectorDrawer"></div>
        <button
            v-if="effectiveInspectorVisible && compactInspector && showInspectorToggle"
            ref="inspectorDrawerClose"
            type="button"
            class="inspector-drawer-close"
            aria-label="关闭语句检查器"
            title="关闭语句检查器"
            @click="closeInspectorDrawer"
        ><PanelRightClose :size="15" aria-hidden="true" /></button>
        <VNextPaneResizer
            v-if="effectiveInspectorVisible && !compactInspector"
            v-model="localInspectorWidth"
            orientation="vertical"
            :reverse="true"
            :min="280"
            :max="560"
            :default-value="340"
            label="调整语句检查器宽度"
            @commit="emit('commitInspectorWidth', $event)"
        />
        <ProgramBatchStatementInspector
            v-if="effectiveInspectorVisible && localSelection.length > 1"
            :class="{ 'is-drawer': compactInspector }"
            :statements="selectedStatements"
            :contract="batchContract"
            :available-values="batchAvailableValues"
            :assets="assets"
            :platform="platform"
            :busy="busy"
            @command="dispatchCommand"
            @open-value-editor="dispatchValueEditor"
        />
        <ProgramStatementInspector
            v-else-if="effectiveInspectorVisible"
            :class="{ 'is-drawer': compactInspector }"
            :statement="selectedStatement"
            :function-contract="selectedContract"
            :function-return-type="document.function.return_type"
            :function-contracts="functionContracts"
            :project-function-ids="projectFunctionIds"
            :available-values="visibleAvailableValues"
            :assets="assets"
            :diagnostics-by-value-id="diagnosticsByValueId"
            :diagnostics="diagnostics"
            :target-options="targetOptions"
            :platform="platform"
            :target-context-label="targetContextLabel"
            :target-context-detail="targetContextDetail"
            :workspace="workspace"
            :target-id="targetId"
            :busy="busy"
            :supported-commands="supportedInspectorCommands"
            :editable-value-statement-kinds="editableValueStatementKinds"
            @command="dispatchCommand"
            @capture="dispatchCapture"
            @open-value-editor="dispatchValueEditor"
            @locate-player="emit('locatePlayer', $event)"
        />
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import { PanelRightClose, PanelRightOpen } from 'lucide-vue-next'
import VNextPaneResizer from '../components/VNextPaneResizer.vue'
import ProgramStatementInspector from './ProgramStatementInspector.vue'
import ProgramBatchStatementInspector from './ProgramBatchStatementInspector.vue'
import ProgramStatementList from './ProgramStatementList.vue'
import { availableValuesAtStatement, findStatement } from './projection'
import type {
    AvailableProgramValue,
    ProgramAsset,
    ProgramCaptureEnvelope,
    ProgramCaptureRequest,
    ProgramCommand,
    ProgramCommandEnvelope,
    ProgramDocument,
    ProgramFunctionContract,
    ProgramInsertionTarget,
    ProgramNamedOption,
    ProgramStatementState,
    ProgramStatement,
    ProgramStatementKind,
    ProgramValueEditorEnvelope,
    ProgramValueEditorRequest,
    StatementListAction,
} from './types'
import type { ExecutionPlatformId } from '../types'
import type { WorkspaceIdentity } from '../types'
import type { ProgramDiagnosticDto } from './serverTypes'
import type { FunctionCatalogCandidate } from './functionCatalogSearch'
import type { FunctionLibrarySelection } from './functionLibraryTypes'
import { programValueCatalogResolverKey, type ProgramValueCatalogResolver } from './valueCatalogContext'

const props = withDefaults(defineProps<{
    document: ProgramDocument
    functionContracts?: Record<string, ProgramFunctionContract>
    projectFunctionIds?: string[]
    selectedStatementIds?: string[]
    collapsedStatementIds?: string[]
    insertionTarget?: ProgramInsertionTarget | null
    pendingCutStatementIds?: string[]
    canPaste?: boolean
    statementStates?: Record<string, ProgramStatementState>
    availableValues?: AvailableProgramValue[]
    assets?: ProgramAsset[]
    loadAssetPreview?: ((assetId: string) => Promise<string>) | null
    diagnosticsByValueId?: Record<string, string[]>
    diagnostics?: ProgramDiagnosticDto[]
    targetOptions?: ProgramNamedOption[]
    platform?: ExecutionPlatformId
    targetContextLabel?: string
    targetContextDetail?: string
    workspace?: WorkspaceIdentity | null
    targetId?: string
    showInspector?: boolean
    inspectorOpen?: boolean
    showInspectorToggle?: boolean
    busy?: boolean
    supportedInspectorCommands?: ProgramCommand['kind'][]
    editableValueStatementKinds?: ProgramStatementKind[]
    resolveValueCatalog?: ProgramValueCatalogResolver | null
    inspectorWidth?: number
    quickInsertCandidates?: FunctionCatalogCandidate[]
    recentQuickInsertKeys?: string[]
    insertQuickFunction?: ((selection: FunctionLibrarySelection) => Promise<void>) | null
}>(), {
    functionContracts: () => ({}),
    projectFunctionIds: () => [],
    selectedStatementIds: () => [],
    collapsedStatementIds: () => [],
    insertionTarget: null,
    pendingCutStatementIds: () => [],
    canPaste: false,
    statementStates: () => ({}),
    availableValues: () => [],
    assets: () => [],
    loadAssetPreview: null,
    diagnosticsByValueId: () => ({}),
    diagnostics: () => [],
    targetOptions: () => [],
    platform: 'windows',
    targetContextLabel: '默认运行目标',
    targetContextDetail: '',
    workspace: null,
    targetId: '',
    showInspector: true,
    inspectorOpen: true,
    showInspectorToggle: true,
    busy: false,
    supportedInspectorCommands: () => [
        'repair_missing_arguments', 'update_value', 'update_assignment_value', 'update_assignment_target', 'update_if_condition', 'add_if_branch', 'remove_if_branch',
        'update_loop', 'update_return_value', 'update_fail', 'update_try_retry_policy', 'update_catch_clause',
        'update_target_scope', 'update_listen', 'review_retry_risk', 'review_dangerous_call', 'set_result_binding', 'insert_if_from_call_result', 'set_step_label',
    ],
    editableValueStatementKinds: () => ['call'],
    resolveValueCatalog: null,
    inspectorWidth: 340,
    quickInsertCandidates: () => [],
    recentQuickInsertKeys: () => [],
    insertQuickFunction: null,
})

if (props.resolveValueCatalog) provide(programValueCatalogResolverKey, props.resolveValueCatalog)

const emit = defineEmits<{
    'update:selectedStatementIds': [statementIds: string[]]
    'update:collapsedStatementIds': [statementIds: string[]]
    'update:insertionTarget': [target: ProgramInsertionTarget | null]
    command: [envelope: ProgramCommandEnvelope]
    capture: [envelope: ProgramCaptureEnvelope]
    openValueEditor: [envelope: ProgramValueEditorEnvelope]
    locatePlayer: [statementId: string]
    requestFunctionLibrary: [query?: string]
    toggleBreakpoint: [statementId: string]
    extractStatements: [statementIds: string[]]
    'update:inspectorWidth': [width: number]
    'update:inspectorOpen': [open: boolean]
    commitInspectorWidth: [width: number]
}>()

const localSelection = ref<string[]>([...props.selectedStatementIds])
const localInspectorWidth = computed({
    get: () => props.inspectorWidth,
    set: (width: number) => emit('update:inspectorWidth', width),
})
const compactInspector = ref(false)
const inspectorDrawerOpen = ref(false)
const surfaceElement = ref<HTMLElement | null>(null)
const inspectorDrawerToggle = ref<HTMLButtonElement | null>(null)
const inspectorDrawerClose = ref<HTMLButtonElement | null>(null)
let compactInspectorMedia: MediaQueryList | null = null
const effectiveInspectorVisible = computed(() => props.showInspector && (
    compactInspector.value && props.showInspectorToggle ? inspectorDrawerOpen.value : props.inspectorOpen
))
function drawerFocusableElements(): HTMLElement[] {
    const inspector = surfaceElement.value?.querySelector<HTMLElement>('.statement-inspector.is-drawer')
    const candidates = [
        inspectorDrawerClose.value,
        ...Array.from(inspector?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])') || []),
    ]
    return candidates.filter((element): element is HTMLElement => Boolean(element && element.getClientRects().length))
}
function handleDrawerKeydown(event: KeyboardEvent): void {
    if (!effectiveInspectorVisible.value || !compactInspector.value) return
    if (event.key === 'Escape') {
        event.preventDefault()
        closeInspectorDrawer()
        return
    }
    if (event.key !== 'Tab') return
    const focusable = drawerFocusableElements()
    if (!focusable.length) return
    const first = focusable[0]
    const last = focusable.at(-1) as HTMLElement
    if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
    }
}
function closeInspectorDrawer(): void {
    if (!effectiveInspectorVisible.value) return
    if (props.showInspectorToggle) inspectorDrawerOpen.value = false
    else emit('update:inspectorOpen', false)
    window.removeEventListener('keydown', handleDrawerKeydown)
    if (props.showInspectorToggle) void nextTick(() => inspectorDrawerToggle.value?.focus())
}
function openInspectorDrawer(): void {
    inspectorDrawerOpen.value = true
    window.addEventListener('keydown', handleDrawerKeydown)
    void nextTick(() => inspectorDrawerClose.value?.focus())
}
function syncCompactInspector(event?: MediaQueryListEvent): void {
    compactInspector.value = event?.matches ?? compactInspectorMedia?.matches ?? false
    if (compactInspector.value && effectiveInspectorVisible.value) {
        window.addEventListener('keydown', handleDrawerKeydown)
        void nextTick(() => inspectorDrawerClose.value?.focus())
    } else {
        window.removeEventListener('keydown', handleDrawerKeydown)
    }
}
onMounted(() => {
    compactInspectorMedia = window.matchMedia?.('(max-width: 1099px)') || null
    syncCompactInspector()
    compactInspectorMedia?.addEventListener?.('change', syncCompactInspector)
})
onBeforeUnmount(() => {
    compactInspectorMedia?.removeEventListener?.('change', syncCompactInspector)
    window.removeEventListener('keydown', handleDrawerKeydown)
})
watch(() => props.selectedStatementIds, (statementIds) => {
    localSelection.value = [...statementIds]
}, { deep: true })
watch(effectiveInspectorVisible, (visible) => {
    if (compactInspector.value && visible) {
        window.addEventListener('keydown', handleDrawerKeydown)
        void nextTick(() => inspectorDrawerClose.value?.focus())
    } else {
        window.removeEventListener('keydown', handleDrawerKeydown)
    }
})

const selectedStatement = computed(() => {
    const statementId = localSelection.value.at(-1)
    return statementId ? findStatement(props.document.function.statements, statementId) : null
})
const selectedStatements = computed(() => localSelection.value
    .map((statementId) => findStatement(props.document.function.statements, statementId))
    .filter((statement): statement is ProgramStatement => Boolean(statement)))
const batchContract = computed(() => {
    if (selectedStatements.value.length < 2 || selectedStatements.value.some((statement) => statement.kind !== 'call')) return null
    const calls = selectedStatements.value.filter((statement) => statement.kind === 'call')
    const functionId = calls[0]?.function_id || ''
    if (!functionId || calls.some((statement) => statement.function_id !== functionId)) return null
    return props.functionContracts[functionId] || null
})
const selectedContract = computed(() => {
    const statement = selectedStatement.value
    return statement?.kind === 'call' ? props.functionContracts[statement.function_id] || null : null
})
const visibleAvailableValues = computed<AvailableProgramValue[]>(() => {
    const statementId = localSelection.value.at(-1)
    const localValues = statementId ? availableValuesAtStatement(props.document, statementId) : []
    const seen = new Set<string>()
    return [...localValues, ...props.availableValues].filter((item) => {
        const key = `${item.source}:${item.id}`
        if (seen.has(key)) return false
        seen.add(key)
        return true
    })
})
const batchAvailableValues = computed<AvailableProgramValue[]>(() => {
    if (selectedStatements.value.length < 2) return visibleAvailableValues.value
    const catalogs = selectedStatements.value.map((statement) => {
        const combined = [...availableValuesAtStatement(props.document, statement.statement_id), ...props.availableValues]
        return new Map(combined.map((item) => [`${item.source}:${item.id}`, item]))
    })
    const first = catalogs[0]
    if (!first) return []
    return [...first.entries()]
        .filter(([key]) => catalogs.slice(1).every((catalog) => catalog.has(key)))
        .map(([, item]) => item)
})

function updateSelection(statementIds: string[]): void {
    localSelection.value = [...statementIds]
    emit('update:selectedStatementIds', statementIds)
}

function dispatchCommand(command: ProgramCommand): void {
    emit('command', {
        document_id: props.document.document_id,
        base_revision: props.document.revision,
        command,
    })
}

function handleListAction(action: StatementListAction): void {
    if (action.kind === 'move') {
        dispatchCommand({
            kind: 'move_statements',
            statement_ids: action.statement_ids,
            direction: action.direction,
        })
        return
    }
    if (action.kind === 'nest') {
        dispatchCommand({
            kind: 'change_statement_nesting',
            statement_ids: action.statement_ids,
            direction: action.direction,
        })
        return
    }
    if (action.kind === 'copy') {
        dispatchCommand({ kind: 'copy_statements', statement_ids: action.statement_ids })
        return
    }
    if (action.kind === 'cut') {
        dispatchCommand({ kind: 'cut_statements', statement_ids: action.statement_ids })
        return
    }
    if (action.kind === 'paste') {
        dispatchCommand({ kind: 'paste_statements' })
        return
    }
    if (action.kind === 'duplicate') {
        dispatchCommand({ kind: 'duplicate_statements', statement_ids: action.statement_ids })
        return
    }
    if (action.kind === 'cancel-clipboard') {
        dispatchCommand({ kind: 'cancel_statement_clipboard' })
        return
    }
    if (action.kind === 'extract') {
        emit('extractStatements', action.statement_ids)
        return
    }
    updateSelection(action.fallback_statement_id ? [action.fallback_statement_id] : [])
    dispatchCommand({ kind: 'delete_statements', statement_ids: action.statement_ids })
}

function dispatchCapture(request: ProgramCaptureRequest): void {
    emit('capture', {
        document_id: props.document.document_id,
        base_revision: props.document.revision,
        request,
    })
}

function dispatchValueEditor(request: ProgramValueEditorRequest): void {
    emit('openValueEditor', {
        document_id: props.document.document_id,
        base_revision: props.document.revision,
        request,
    })
}
</script>

<style scoped>
.program-editor-surface {
    position: relative;
    display: grid;
    grid-template-columns: minmax(0, 1fr) 5px minmax(280px, var(--program-inspector-width, 340px));
    grid-template-rows: 38px minmax(0, 1fr);
    min-width: 0;
    height: 100%;
    overflow: hidden;
    background: var(--app-bg-base);
}

.program-editor-surface.without-inspector { grid-template-columns: minmax(0, 1fr); }
.surface-main-header { min-width: 0; grid-column: 1; grid-row: 1; }
.surface-statement-list { min-width: 0; min-height: 0; grid-column: 1; grid-row: 2; }
.program-editor-surface > :deep(.pane-resizer) { grid-column: 2; grid-row: 1 / -1; }
.program-editor-surface > :deep(.statement-inspector) {
    min-width: 0;
    min-height: 0;
    display: flex;
    grid-column: 3;
    grid-row: 1 / -1;
    flex-direction: column;
    overflow: hidden;
    border-inline-start: 1px solid var(--app-border-subtle);
    background: var(--app-bg-panel);
    color: var(--app-text-regular);
    container-type: inline-size;
}
.statement-inspector.is-drawer {
    position: absolute;
    z-index: 22;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(360px, calc(100% - 44px));
    box-shadow: var(--app-shadow-lg);
}
.inspector-drawer-scrim { position: absolute; z-index: 20; inset: 0; background: rgba(0, 0, 0, .34); }
.inspector-drawer-toggle,.inspector-drawer-close {
    position: absolute;
    z-index: 24;
    top: 7px;
    right: 8px;
    width: 28px;
    height: var(--app-control-compact);
    display: grid;
    place-items: center;
    padding: 0;
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    background: var(--app-bg-raised);
    color: var(--app-text-secondary);
    cursor: pointer;
    box-shadow: var(--app-shadow-sm);
}
.inspector-drawer-toggle:hover,.inspector-drawer-close:hover { background: var(--app-bg-hover); color: var(--app-text-primary); }
.inspector-drawer-toggle:focus-visible,.inspector-drawer-close:focus-visible { outline: 0; box-shadow: var(--focus-ring); }
</style>
