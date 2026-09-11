<template>
    <section class="statement-editor" aria-label="结构化语句">
        <div v-if="statementRows.length === 0" class="statement-empty">
            <ProgramInlineQuickInsert
                v-if="quickInsertAnchor?.kind === 'empty'"
                class="quick-insert-empty"
                :candidates="quickInsertCandidates"
                :recent-keys="recentQuickInsertKeys"
                :busy="busy"
                :insert="requireQuickInsert"
                placeholder="搜索第一项操作，例如“控件、文字、等待”"
                @cancel="closeQuickInsert"
                @complete="completeQuickInsert"
                @request-library="requestFullLibrary"
            />
            <VNextWorkspaceState v-else kind="empty" title="这个函数还没有语句" description="直接搜索要执行的操作，或前往完整函数目录浏览。">
                <template #icon><Braces :size="24" /></template>
                <template #actions>
                    <VNextButton size="compact" :disabled="busy" @click="openEmptyQuickInsert">快速添加第一条语句</VNextButton>
                    <VNextButton size="compact" appearance="ghost" @click="emit('requestFunctionLibrary', '')">浏览函数目录</VNextButton>
                </template>
            </VNextWorkspaceState>
        </div>

        <div v-else ref="treeRoot" class="statement-tree" role="tree" aria-multiselectable="true" @scroll.passive="updateVirtualWindow">
            <div v-if="topSpacerHeight" class="statement-virtual-spacer" :style="{ height: `${topSpacerHeight}px` }" aria-hidden="true"></div>
            <template v-for="row in renderedRows" :key="row.key">
                <ProgramInlineQuickInsert
                    v-if="row.row_kind === 'quick_insert'"
                    :candidates="quickInsertCandidates"
                    :depth="row.depth"
                    :recent-keys="recentQuickInsertKeys"
                    :busy="busy"
                    :insert="requireQuickInsert"
                    @cancel="closeQuickInsert"
                    @complete="completeQuickInsert"
                    @request-library="requestFullLibrary"
                />
                <div
                    v-else-if="row.row_kind === 'branch'"
                    class="branch-row"
                    :class="branchClasses(row)"
                    :style="rowStyle(row.depth)"
                    role="treeitem"
                    tabindex="0"
                    :aria-level="row.depth"
                    :aria-selected="selectedInsertionTargetKey === row.key"
                    :data-branch-key="row.key"
                    :aria-label="row.action ? `${row.label}，选择为插入位置` : `${row.label}${row.empty ? '，暂无语句' : ''}，选择为插入位置`"
                    @click="selectBranch(row)"
                    @dblclick="openQuickInsertForBranch(row)"
                    @keydown.enter.prevent="onBranchEnter(row)"
                >
                    <span class="branch-label">{{ row.label }}</span>
                    <em v-if="row.empty">暂无语句</em>
                    <span v-if="!row.action" class="branch-rule" aria-hidden="true"></span>
                    <button
                        type="button"
                        class="branch-insert-action"
                        :disabled="busy || !insertQuickFunction"
                        :aria-label="branchInsertLabel(row)"
                        :title="branchInsertLabel(row)"
                        @click.stop="openQuickInsertForBranch(row)"
                        @dblclick.stop
                        @keydown.enter.stop
                    ><Plus :size="14" aria-hidden="true" /></button>
                </div>

                <div
                    v-else
                    class="statement-row"
                    :class="rowClasses(row.statement, row.depth)"
                    :style="rowStyle(row.depth)"
                    :data-statement-id="row.statement.statement_id"
                    role="treeitem"
                    :aria-level="row.depth"
                    :aria-selected="selectedSet.has(row.statement.statement_id)"
                    :aria-expanded="row.has_children ? !collapsedSet.has(row.statement.statement_id) : undefined"
                    :aria-label="accessibleLabel(row.statement.statement_id, displaySummary(row.statement, row.summary_parts))"
                    :tabindex="rowTabIndex(row.statement.statement_id)"
                    @click="selectRow(row.statement.statement_id, $event)"
                    @contextmenu.prevent="openStatementContextMenu(row.statement.statement_id)"
                    @focus="lastFocusedId = row.statement.statement_id"
                    @keydown="onRowKeydown(row.statement.statement_id, $event)"
                >
                    <button
                        v-if="row.has_children"
                        type="button"
                        class="collapse-button"
                        :aria-label="collapsedSet.has(row.statement.statement_id) ? '展开语句块' : '折叠语句块'"
                        :title="collapsedSet.has(row.statement.statement_id) ? '展开语句块' : '折叠语句块'"
                        @click.stop="toggleCollapse(row.statement.statement_id)"
                    >
                        <ChevronRight v-if="collapsedSet.has(row.statement.statement_id)" :size="14" aria-hidden="true" />
                        <ChevronDown v-else :size="14" aria-hidden="true" />
                    </button>
                    <span v-else class="collapse-placeholder" aria-hidden="true"></span>

                    <span class="statement-content">
                        <ProgramStatementSummary
                            :parts="displaySummaryParts(row.statement, row.summary_parts)"
                            :assets="assets"
                            :load-asset-preview="loadSummaryAssetPreview"
                        />
                        <span v-if="row.statement.step_label" class="step-label" :title="row.statement.step_label">{{ row.statement.step_label }}</span>
                    </span>

                    <span v-if="stateFor(row.statement.statement_id).runtime && stateFor(row.statement.statement_id).runtime !== 'idle'" class="runtime-state">
                        {{ runtimeLabel(stateFor(row.statement.statement_id).runtime) }}
                    </span>
                    <span v-if="stateFor(row.statement.statement_id).diagnostic_count" class="diagnostic-count">
                        {{ stateFor(row.statement.statement_id).diagnostic_count }} 个问题
                    </span>

                    <span
                        v-if="isPrimary(row.statement.statement_id)"
                        class="statement-actions"
                        :aria-label="`${actionObjectLabel(row.statement.statement_id)}操作`"
                    >
                        <button type="button" class="quick-insert-action" :disabled="busy" title="在此语句后插入（Ctrl+Enter）" aria-label="在此语句后插入" @click.stop="openQuickInsertAfter(row.statement.statement_id)">
                            <Plus :size="14" aria-hidden="true" />
                        </button>
                        <button
                            type="button"
                            class="breakpoint-action"
                            :class="{ active: stateFor(row.statement.statement_id).breakpoint }"
                            :disabled="busy"
                            :title="stateFor(row.statement.statement_id).breakpoint ? '移除断点（F9）' : '添加断点（F9）'"
                            :aria-label="stateFor(row.statement.statement_id).breakpoint ? '移除断点' : '添加断点'"
                            @click.stop="emit('toggleBreakpoint', row.statement.statement_id)"
                        ><span aria-hidden="true"></span></button>
                        <button type="button" :disabled="busy" :title="`上移${actionObjectLabel(row.statement.statement_id)}`" :aria-label="`上移${actionObjectLabel(row.statement.statement_id)}`" @click.stop="performAction('move', row.statement.statement_id, 'up')">
                            <ArrowUp :size="14" aria-hidden="true" />
                        </button>
                        <button type="button" :disabled="busy" :title="`下移${actionObjectLabel(row.statement.statement_id)}`" :aria-label="`下移${actionObjectLabel(row.statement.statement_id)}`" @click.stop="performAction('move', row.statement.statement_id, 'down')">
                            <ArrowDown :size="14" aria-hidden="true" />
                        </button>
                        <span class="statement-more" @focusout="closeMoreOnFocusOut">
                            <button
                                type="button"
                                :disabled="busy"
                                title="更多语句操作"
                                aria-label="更多语句操作"
                                :aria-expanded="openActionsId === row.statement.statement_id"
                                aria-haspopup="menu"
                                @click.stop="toggleMoreActions(row.statement.statement_id)"
                                @keydown.down.stop.prevent="openMoreActions(row.statement.statement_id, $event)"
                                @keydown.escape="openActionsId = null"
                            ><MoreHorizontal :size="15" aria-hidden="true" /></button>
                            <span v-if="openActionsId === row.statement.statement_id" class="statement-more-menu" role="menu" aria-label="更多语句操作" @keydown="onMoreMenuKeydown">
                                <button type="button" role="menuitem" :disabled="busy || !canNest(row.statement.statement_id, 'in')" @click.stop="performMoreAction(row.statement.statement_id, 'nest-in')"><IndentIncrease :size="14" aria-hidden="true" />移入上一个语句块 <kbd>Tab</kbd></button>
                                <button type="button" role="menuitem" :disabled="busy || !canNest(row.statement.statement_id, 'out')" @click.stop="performMoreAction(row.statement.statement_id, 'nest-out')"><IndentDecrease :size="14" aria-hidden="true" />移出当前语句块 <kbd>Shift+Tab</kbd></button>
                                <button type="button" role="menuitem" :disabled="busy" @click.stop="performMoreAction(row.statement.statement_id, 'copy')"><Copy :size="14" aria-hidden="true" />{{ batchActionLabel('copy', row.statement.statement_id) }} <kbd>Ctrl+C</kbd></button>
                                <button type="button" role="menuitem" :disabled="busy" @click.stop="performMoreAction(row.statement.statement_id, 'cut')"><Scissors :size="14" aria-hidden="true" />{{ batchActionLabel('cut', row.statement.statement_id) }} <kbd>Ctrl+X</kbd></button>
                                <button type="button" role="menuitem" :disabled="busy || !canPaste" @click.stop="performMoreAction(row.statement.statement_id, 'paste')"><ClipboardPaste :size="14" aria-hidden="true" />在此语句后粘贴 <kbd>Ctrl+V</kbd></button>
                                <button type="button" role="menuitem" :disabled="busy" @click.stop="performMoreAction(row.statement.statement_id, 'duplicate')"><CopyPlus :size="14" aria-hidden="true" />{{ batchActionLabel('duplicate', row.statement.statement_id) }} <kbd>Ctrl+D</kbd></button>
                                <button type="button" role="menuitem" :disabled="busy" @click.stop="performMoreAction(row.statement.statement_id, 'extract')"><PackagePlus :size="14" aria-hidden="true" />{{ batchActionLabel('extract', row.statement.statement_id) }}</button>
                                <button type="button" role="menuitem" class="danger-action" :disabled="busy" @click.stop="performMoreAction(row.statement.statement_id, 'delete')"><Trash2 :size="14" aria-hidden="true" />{{ batchActionLabel('delete', row.statement.statement_id) }} <kbd>Delete</kbd></button>
                            </span>
                        </span>
                    </span>
                </div>
            </template>
            <div v-if="bottomSpacerHeight" class="statement-virtual-spacer" :style="{ height: `${bottomSpacerHeight}px` }" aria-hidden="true"></div>
            <p v-if="rows.length > renderedRows.length" class="sr-only" role="status">当前仅渲染视口附近语句，共 {{ statementRows.length }} 条</p>
        </div>

        <p class="sr-only" aria-live="polite">{{ liveMessage }}</p>
    </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
    ArrowDown,
    ArrowUp,
    Braces,
    ChevronDown,
    ChevronRight,
    Copy,
    CopyPlus,
    ClipboardPaste,
    IndentDecrease,
    IndentIncrease,
    MoreHorizontal,
    PackagePlus,
    Plus,
    Scissors,
    Trash2,
} from 'lucide-vue-next'
import { projectStatements, statementHasChildren, visibleStatementRows } from './projection'
import type { ProjectedBranchRow, ProjectedProgramRow } from './projection'
import VNextButton from '../components/ui/VNextButton.vue'
import VNextWorkspaceState from '../components/ui/VNextWorkspaceState.vue'
import ProgramInlineQuickInsert from './ProgramInlineQuickInsert.vue'
import ProgramStatementSummary from './ProgramStatementSummary.vue'
import { readableImageName, summaryPartText } from './summaryPresentation'
import type { FunctionCatalogCandidate } from './functionCatalogSearch'
import type { FunctionLibrarySelection } from './functionLibraryTypes'
import type {
    ProgramAsset,
    ProgramInsertionTarget,
    ProgramNamedOption,
    ProgramRuntimeState,
    ProgramStatement,
    ProgramStatementState,
    ProgramSummaryPart,
    ProgramValueNode,
    StatementListAction,
} from './types'

const props = withDefaults(defineProps<{
    statements: ProgramStatement[]
    selectedStatementIds?: string[]
    collapsedStatementIds?: string[]
    statementStates?: Record<string, ProgramStatementState>
    assets?: ProgramAsset[]
    targetOptions?: ProgramNamedOption[]
    loadAssetPreview?: ((assetId: string) => Promise<string>) | null
    selectedInsertionTargetKey?: string
    pendingCutStatementIds?: string[]
    canPaste?: boolean
    busy?: boolean
    quickInsertCandidates?: FunctionCatalogCandidate[]
    recentQuickInsertKeys?: string[]
    insertQuickFunction?: ((selection: FunctionLibrarySelection) => Promise<void>) | null
}>(), {
    selectedStatementIds: () => [],
    collapsedStatementIds: () => [],
    statementStates: () => ({}),
    assets: () => [],
    targetOptions: () => [],
    loadAssetPreview: null,
    selectedInsertionTargetKey: '',
    pendingCutStatementIds: () => [],
    canPaste: false,
    busy: false,
    quickInsertCandidates: () => [],
    recentQuickInsertKeys: () => [],
    insertQuickFunction: null,
})

const emit = defineEmits<{
    'update:selectedStatementIds': [statementIds: string[]]
    'update:collapsedStatementIds': [statementIds: string[]]
    'update:insertionTarget': [target: ProgramInsertionTarget | null]
    action: [action: StatementListAction]
    toggleBreakpoint: [statementId: string]
    requestFunctionLibrary: [query?: string]
}>()

const treeRoot = ref<HTMLElement | null>(null)
const localSelection = ref<string[]>([...props.selectedStatementIds])
const localCollapsed = ref<string[]>([...props.collapsedStatementIds])
const selectionAnchorId = ref<string | null>(props.selectedStatementIds.at(-1) || null)
const lastFocusedId = ref<string | null>(props.selectedStatementIds.at(-1) || null)
const liveMessage = ref('')
const openActionsId = ref<string | null>(null)
type QuickInsertAnchor =
    | { kind: 'empty'; key: 'empty'; depth: 1 }
    | { kind: 'statement'; key: string; depth: number; statementId: string }
    | { kind: 'branch'; key: string; depth: number; target: ProgramInsertionTarget }
type QuickInsertProjectedRow = { row_kind: 'quick_insert'; key: string; depth: number }
const quickInsertAnchor = ref<QuickInsertAnchor | null>(null)
const STATEMENT_ROW_HEIGHT = 34
const BRANCH_ROW_HEIGHT = 26
const QUICK_INSERT_ROW_HEIGHT = 38
const ROW_OVERSCAN = 16
const virtualScrollTop = ref(0)
const virtualViewportHeight = ref(720)
let treeResizeObserver: ResizeObserver | null = null
const summaryPreviewUrls = new Map<string, string>()
const summaryPreviewRequests = new Map<string, Promise<string>>()
let summaryPreviewGeneration = 0

const collapsedSet = computed(() => new Set(localCollapsed.value))
const selectedSet = computed(() => new Set(localSelection.value))
const rows = computed(() => projectStatements(props.statements, collapsedSet.value))
const displayRows = computed<Array<ProjectedProgramRow | QuickInsertProjectedRow>>(() => {
    const anchor = quickInsertAnchor.value
    if (!anchor || anchor.kind === 'empty') return rows.value
    const anchorIndex = rows.value.findIndex((row) => row.key === anchor.key)
    if (anchorIndex < 0) return rows.value
    let insertionIndex = anchorIndex + 1
    if (anchor.kind === 'branch') {
        while (insertionIndex < rows.value.length) {
            const candidate = rows.value[insertionIndex]!
            if (candidate.depth < anchor.depth || (candidate.row_kind === 'branch' && candidate.depth === anchor.depth)) break
            insertionIndex += 1
        }
    } else {
        while (insertionIndex < rows.value.length && rows.value[insertionIndex]!.depth > anchor.depth) insertionIndex += 1
    }
    const next: Array<ProjectedProgramRow | QuickInsertProjectedRow> = [...rows.value]
    next.splice(insertionIndex, 0, { row_kind: 'quick_insert', key: `quick:${anchor.kind}:${anchor.key}`, depth: anchor.depth })
    return next
})
const rowOffsets = computed(() => {
    const offsets = [0]
    for (const row of displayRows.value) {
        const height = row.row_kind === 'quick_insert' ? QUICK_INSERT_ROW_HEIGHT : row.row_kind === 'branch' ? BRANCH_ROW_HEIGHT : STATEMENT_ROW_HEIGHT
        offsets.push(offsets[offsets.length - 1]! + height)
    }
    return offsets
})

function rowIndexAtOffset(offset: number): number {
    const offsets = rowOffsets.value
    let low = 0
    let high = Math.max(0, offsets.length - 1)
    while (low < high) {
        const middle = Math.ceil((low + high) / 2)
        if ((offsets[middle] || 0) <= offset) low = middle
        else high = middle - 1
    }
    return Math.min(displayRows.value.length, low)
}

const virtualStart = computed(() => Math.max(0, rowIndexAtOffset(virtualScrollTop.value) - ROW_OVERSCAN))
const virtualEnd = computed(() => Math.min(
    displayRows.value.length,
    rowIndexAtOffset(virtualScrollTop.value + virtualViewportHeight.value) + ROW_OVERSCAN + 1,
))
const renderedRows = computed(() => displayRows.value.slice(virtualStart.value, virtualEnd.value))
const topSpacerHeight = computed(() => rowOffsets.value[virtualStart.value] || 0)
const bottomSpacerHeight = computed(() => Math.max(0, (rowOffsets.value.at(-1) || 0) - (rowOffsets.value[virtualEnd.value] || 0)))
const statementRows = computed(() => visibleStatementRows(rows.value))
const visibleIds = computed(() => statementRows.value.map((row) => row.statement.statement_id))
const primaryId = computed(() => localSelection.value.at(-1) || lastFocusedId.value || visibleIds.value[0] || null)

watch(rows, () => {
    const anchor = quickInsertAnchor.value
    if (!anchor || anchor.kind === 'empty') return
    if (!rows.value.some((row) => row.key === anchor.key)) {
        quickInsertAnchor.value = null
        liveMessage.value = '原插入位置已经失效，请重新选择'
    }
})

watch(() => props.selectedStatementIds, (statementIds) => {
    localSelection.value = [...statementIds]
    if (statementIds.length) selectionAnchorId.value = statementIds.at(-1) || null
    const selectedId = statementIds.at(-1)
    if (!selectedId) return
    const index = rows.value.findIndex((row) => row.row_kind === 'statement' && row.statement.statement_id === selectedId)
    if (index >= 0 && (index < virtualStart.value || index >= virtualEnd.value)) scrollToVirtualIndex(index)
}, { deep: true, immediate: true })

watch(() => props.collapsedStatementIds, (statementIds) => {
    localCollapsed.value = [...statementIds]
}, { deep: true })

function updateVirtualWindow(event: Event): void {
    const element = event.currentTarget as HTMLElement
    virtualScrollTop.value = element.scrollTop
    virtualViewportHeight.value = Math.max(1, element.clientHeight || virtualViewportHeight.value)
}

function scrollToVirtualIndex(index: number): void {
    const maximumTop = Math.max(0, (rowOffsets.value.at(-1) || 0) - virtualViewportHeight.value)
    const targetTop = Math.min(maximumTop, Math.max(0, (rowOffsets.value[index] || 0) - Math.floor(virtualViewportHeight.value / 3)))
    virtualScrollTop.value = targetTop
    void nextTick(() => {
        if (treeRoot.value) treeRoot.value.scrollTop = targetTop
    })
}

onMounted(() => {
    if (!treeRoot.value) return
    virtualViewportHeight.value = Math.max(1, treeRoot.value.clientHeight || virtualViewportHeight.value)
    treeResizeObserver = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(([entry]) => {
        virtualViewportHeight.value = Math.max(1, entry?.contentRect.height || treeRoot.value?.clientHeight || 1)
    })
    treeResizeObserver?.observe(treeRoot.value)
})
function releaseSummaryPreviews(): void {
    summaryPreviewGeneration += 1
    for (const url of summaryPreviewUrls.values()) {
        if (url.startsWith('blob:') && typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(url)
    }
    summaryPreviewUrls.clear()
    summaryPreviewRequests.clear()
}

async function loadSummaryAssetPreview(assetId: string): Promise<string> {
    const cached = summaryPreviewUrls.get(assetId)
    if (cached) return cached
    const pending = summaryPreviewRequests.get(assetId)
    if (pending) return pending
    if (!props.loadAssetPreview) return ''
    const requestGeneration = summaryPreviewGeneration
    const request = props.loadAssetPreview(assetId).then((url) => {
        if (requestGeneration !== summaryPreviewGeneration) {
            if (url.startsWith('blob:') && typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(url)
            return ''
        }
        summaryPreviewUrls.set(assetId, url)
        summaryPreviewRequests.delete(assetId)
        return url
    }, (error) => {
        summaryPreviewRequests.delete(assetId)
        throw error
    })
    summaryPreviewRequests.set(assetId, request)
    return request
}

watch(
    () => [props.loadAssetPreview, ...props.assets.map((asset) => `${asset.asset_id}:${asset.updated_at}`)],
    releaseSummaryPreviews,
)

onBeforeUnmount(() => {
    treeResizeObserver?.disconnect()
    releaseSummaryPreviews()
})

function firstValueAsset(value: ProgramValueNode | null | undefined): Extract<ProgramValueNode, { kind: 'asset_ref' }> | null {
    if (!value) return null
    if (value.kind === 'asset_ref') return value
    if (value.kind === 'member_access') return firstValueAsset(value.source)
    if (value.kind === 'list') return value.items.map(firstValueAsset).find(Boolean) || null
    if (value.kind === 'map') {
        for (const entry of value.entries) {
            const asset = firstValueAsset(entry.key) || firstValueAsset(entry.value)
            if (asset) return asset
        }
        return null
    }
    if (value.kind === 'record') return Object.values(value.fields).map(firstValueAsset).find(Boolean) || null
    if (value.kind === 'computed') return Object.values(value.inputs).map(firstValueAsset).find(Boolean) || null
    if (value.kind === 'selector') return firstValueAsset(value.expression)
    if (value.kind === 'compare') return firstValueAsset(value.left) || firstValueAsset(value.right)
    if (value.kind === 'condition_group') return value.conditions.map(firstValueAsset).find(Boolean) || null
    if (value.kind === 'not') return firstValueAsset(value.condition)
    return null
}

function firstStatementAsset(statement: ProgramStatement): Extract<ProgramValueNode, { kind: 'asset_ref' }> | null {
    if (statement.kind === 'call') return Object.values(statement.arguments).map(firstValueAsset).find(Boolean) || null
    if (statement.kind === 'assignment') return firstValueAsset(statement.value)
    if (statement.kind === 'if') return firstValueAsset(statement.condition)
    if (statement.kind === 'loop') return firstValueAsset(statement.source)
    if (statement.kind === 'return') return firstValueAsset(statement.value)
    if (statement.kind === 'fail') return firstValueAsset(statement.message) || firstValueAsset(statement.details)
    if (statement.kind === 'target_scope') return firstValueAsset(statement.target)
    if (statement.kind === 'listen') return firstValueAsset(statement.event_source.name) || firstValueAsset(statement.event_source.sender)
    return null
}

function displaySummary(statement: ProgramStatement, parts: ProgramSummaryPart[]): string {
    return displaySummaryParts(statement, parts).map((part) => summaryPartText(part, props.assets)).join('')
}

function displaySummaryParts(statement: ProgramStatement, parts: ProgramSummaryPart[]): ProgramSummaryPart[] {
    const targetValue = statement.kind === 'target_scope' ? statement.target : null
    if (targetValue?.kind === 'target_ref') {
        const target = props.targetOptions.find((item) => String(item.value) === targetValue.target_id)
        if (target) return [{ text: '在' }, { text: target.label, dynamic: true }, { text: '中执行' }]
    }
    const assetValue = firstStatementAsset(statement)
    if (!assetValue || parts.some((part) => part.value?.kind === 'asset_ref')) return parts
    const asset = props.assets.find((item) => item.asset_id === assetValue.asset_id)
    const assetName = asset?.display_name || assetValue.display_name || ''
    let attached = false
    const result = parts.flatMap((part) => {
        const tokens = [
            `图片「${assetValue.asset_id}」`,
            ...(assetName ? [`图片「${assetName}」`, assetName] : []),
            assetValue.asset_id,
        ]
        const token = tokens.find((candidate) => candidate && part.text.includes(candidate))
        if (!token) return [part]
        attached = true
        const index = part.text.indexOf(token)
        return [
            ...(index ? [{ text: part.text.slice(0, index) }] : []),
            { ...part, text: assetName || '图片资源', dynamic: true, value: assetValue },
            ...(index + token.length < part.text.length ? [{ text: part.text.slice(index + token.length) }] : []),
        ]
    })
    if (!attached) {
        result.push(
            { text: ' · ' },
            { text: readableImageName(assetName), dynamic: true, value: assetValue, role: 'object', presentation: 'auto' },
        )
    }
    return result
}

function rowStyle(depth: number): Record<string, string> {
    return { '--statement-depth': String(depth) }
}

function isPrimary(statementId: string): boolean {
    return primaryId.value === statementId
}

function stateFor(statementId: string): ProgramStatementState {
    return props.statementStates[statementId] || {}
}

function runtimeLabel(runtime: ProgramRuntimeState | undefined): string {
    if (runtime === 'running') return '执行中'
    if (runtime === 'completed') return '已完成'
    if (runtime === 'waiting') return '等待中'
    if (runtime === 'paused') return '已暂停'
    if (runtime === 'failed') return '失败'
    return ''
}

function accessibleLabel(statementId: string, summary: string): string {
    const state = stateFor(statementId)
    const parts = [summary]
    if (state.breakpoint) parts.push('设有断点')
    if (state.runtime && state.runtime !== 'idle') parts.push(runtimeLabel(state.runtime))
    if (state.diagnostic_count) parts.push(`${state.diagnostic_count} 个问题`)
    if (props.pendingCutStatementIds.includes(statementId)) parts.push('已剪切，等待粘贴')
    return parts.filter(Boolean).join('，')
}

function rowClasses(statement: ProgramStatement, depth: number): Record<string, boolean> {
    const statementId = statement.statement_id
    const state = stateFor(statementId)
    const structureKinds: ProgramStatement['kind'][] = ['if', 'loop', 'try', 'target_scope', 'listen']
    return {
        [`kind-${statement.kind}`]: true,
        'is-structure': structureKinds.includes(statement.kind),
        'is-nested': depth > 1,
        'is-selected': selectedSet.value.has(statementId),
        'is-cut-pending': props.pendingCutStatementIds.includes(statementId),
        'is-primary': isPrimary(statementId),
        'has-breakpoint': Boolean(state.breakpoint),
        'is-running': state.runtime === 'running',
        'is-failed': state.runtime === 'failed',
    }
}

function branchClasses(row: ProjectedBranchRow): Record<string, boolean> {
    return {
        [`branch-${row.block}`]: true,
        'is-nested': row.depth > 1,
        'is-insertion-target': props.selectedInsertionTargetKey === row.key,
        'is-optional-action': Boolean(row.action),
        'is-empty': row.empty,
    }
}

function branchInsertLabel(row: ProjectedBranchRow): string {
    if (row.action && row.block === 'otherwise') return '添加“否则”分支并插入语句'
    if (row.action && row.block === 'finally') return '添加“最后”分支并插入语句'
    return `在“${row.label}”中插入语句`
}

function branchInsertStatus(row: ProjectedBranchRow): string {
    if (row.action && row.block === 'otherwise') return '正在为“否则”分支选择第一条语句'
    if (row.action && row.block === 'finally') return '正在为“最后”分支选择第一条语句'
    return `正在为“${row.label}”选择要插入的操作`
}

function rowTabIndex(statementId: string): 0 | -1 {
    return primaryId.value === statementId ? 0 : -1
}

function setSelection(statementIds: string[], primary: string | null): void {
    const ordered = visibleIds.value.filter((id) => statementIds.includes(id))
    localSelection.value = ordered
    if (primary) {
        selectionAnchorId.value = primary
        lastFocusedId.value = primary
    }
    emit('update:selectedStatementIds', ordered)
    emit('update:insertionTarget', null)
}

function selectBranch(row: ProjectedBranchRow): void {
    openActionsId.value = null
    emit('update:selectedStatementIds', [])
    emit('update:insertionTarget', {
        key: row.key,
        parent_statement_id: row.owner_statement_id,
        block: row.block,
        ...(row.clause_id ? { clause_id: row.clause_id } : {}),
        label: row.label,
    })
    liveMessage.value = `插入位置已切换到${row.label}`
}

function branchTarget(row: ProjectedBranchRow): ProgramInsertionTarget {
    return {
        key: row.key,
        parent_statement_id: row.owner_statement_id,
        block: row.block,
        ...(row.clause_id ? { clause_id: row.clause_id } : {}),
        label: row.label,
    }
}

function openEmptyQuickInsert(): void {
    if (props.busy) return
    if (!props.insertQuickFunction) {
        emit('requestFunctionLibrary', '')
        return
    }
    emit('update:selectedStatementIds', [])
    emit('update:insertionTarget', null)
    quickInsertAnchor.value = { kind: 'empty', key: 'empty', depth: 1 }
}

function openQuickInsertAfter(statementId: string): void {
    if (props.busy || !props.insertQuickFunction) return
    const row = rows.value.find((candidate) => candidate.row_kind === 'statement' && candidate.statement.statement_id === statementId)
    if (!row || row.row_kind !== 'statement') return
    setSelection([statementId], statementId)
    quickInsertAnchor.value = { kind: 'statement', key: row.key, depth: row.depth, statementId }
    liveMessage.value = `正在${displaySummary(row.statement, row.summary_parts)}之后选择要插入的操作`
}

function openQuickInsertForBranch(row: ProjectedBranchRow): void {
    if (props.busy || !props.insertQuickFunction) return
    const target = branchTarget(row)
    selectBranch(row)
    quickInsertAnchor.value = { kind: 'branch', key: row.key, depth: row.depth, target }
    liveMessage.value = branchInsertStatus(row)
}

function onBranchEnter(row: ProjectedBranchRow): void {
    if (props.selectedInsertionTargetKey === row.key) openQuickInsertForBranch(row)
    else selectBranch(row)
}

function closeQuickInsert(): void {
    const anchor = quickInsertAnchor.value
    quickInsertAnchor.value = null
    liveMessage.value = '已取消快速插入'
    if (anchor?.kind === 'statement') focusStatement(anchor.statementId)
    else if (anchor?.kind === 'branch') void nextTick(() => {
        const branch = Array.from(treeRoot.value?.querySelectorAll<HTMLElement>('[data-branch-key]') || [])
            .find((element) => element.dataset.branchKey === anchor.key)
        branch?.focus()
    })
}

function completeQuickInsert(selection: FunctionLibrarySelection): void {
    quickInsertAnchor.value = null
    if (selection.source === 'structure' && selection.function_id === 'assignment.existing') {
        liveMessage.value = '请选择要修改的变量'
        return
    }
    liveMessage.value = selection.source === 'structure' ? '控制结构已插入并保存' : '函数已插入并保存'
    void nextTick(() => {
        const insertedId = props.selectedStatementIds.at(-1)
        if (insertedId) focusStatement(insertedId)
    })
}

function requestFullLibrary(query: string): void {
    quickInsertAnchor.value = null
    emit('requestFunctionLibrary', query)
}

function requireQuickInsert(selection: FunctionLibrarySelection): Promise<void> {
    if (!props.insertQuickFunction) return Promise.reject(new Error('快速插入当前不可用'))
    return props.insertQuickFunction(selection)
}

function selectRow(statementId: string, event: MouseEvent): void {
    openActionsId.value = null
    if (event.shiftKey && selectionAnchorId.value) {
        const anchorIndex = visibleIds.value.indexOf(selectionAnchorId.value)
        const currentIndex = visibleIds.value.indexOf(statementId)
        if (anchorIndex >= 0 && currentIndex >= 0) {
            const [start, end] = anchorIndex <= currentIndex ? [anchorIndex, currentIndex] : [currentIndex, anchorIndex]
            const range = visibleIds.value.slice(start, end + 1)
            const next = event.ctrlKey || event.metaKey ? [...new Set([...localSelection.value, ...range])] : range
            setSelection(next, statementId)
            return
        }
    }
    if (event.ctrlKey || event.metaKey) {
        const next = selectedSet.value.has(statementId)
            ? localSelection.value.filter((id) => id !== statementId)
            : [...localSelection.value, statementId]
        setSelection(next, next.at(-1) || null)
        return
    }
    setSelection([statementId], statementId)
}

function focusStatement(statementId: string): void {
    lastFocusedId.value = statementId
    const index = rows.value.findIndex((row) => row.row_kind === 'statement' && row.statement.statement_id === statementId)
    if (index >= 0 && (index < virtualStart.value || index >= virtualEnd.value)) scrollToVirtualIndex(index)
    void nextTick(() => {
        const element = [...(treeRoot.value?.querySelectorAll<HTMLElement>('[data-statement-id]') || [])]
            .find((row) => row.dataset.statementId === statementId)
        element?.focus()
    })
}

function selectByKeyboard(statementId: string, direction: 'previous' | 'next', extend: boolean): void {
    const index = visibleIds.value.indexOf(statementId)
    const nextIndex = direction === 'previous' ? Math.max(0, index - 1) : Math.min(visibleIds.value.length - 1, index + 1)
    const nextId = visibleIds.value[nextIndex]
    if (!nextId || nextId === statementId) return
    if (extend && selectionAnchorId.value) {
        const anchorIndex = visibleIds.value.indexOf(selectionAnchorId.value)
        const [start, end] = anchorIndex <= nextIndex ? [anchorIndex, nextIndex] : [nextIndex, anchorIndex]
        setSelection(visibleIds.value.slice(start, end + 1), nextId)
    } else {
        setSelection([nextId], nextId)
    }
    focusStatement(nextId)
}

function onRowKeydown(statementId: string, event: KeyboardEvent): void {
    const modifier = event.ctrlKey || event.metaKey
    if (modifier && event.key === 'Enter') {
        event.preventDefault()
        openQuickInsertAfter(statementId)
        return
    }
    if (modifier && event.key.toLowerCase() === 'a') {
        event.preventDefault()
        setSelection(visibleIds.value, statementId)
        liveMessage.value = `已选择当前函数的 ${visibleIds.value.length} 条可见语句`
        return
    }
    if (event.key === 'Tab') {
        event.preventDefault()
        performNesting(statementId, event.shiftKey ? 'out' : 'in')
        return
    }
    if (modifier && (event.key === 'ArrowUp' || event.key === 'ArrowDown')) {
        event.preventDefault()
        performAction('move', statementId, event.key === 'ArrowUp' ? 'up' : 'down')
        return
    }
    if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
        event.preventDefault()
        selectByKeyboard(statementId, event.key === 'ArrowUp' ? 'previous' : 'next', event.shiftKey)
        return
    }
    if (event.key === 'ArrowRight') {
        const row = statementRows.value.find((item) => item.statement.statement_id === statementId)
        if (!row?.has_children) return
        event.preventDefault()
        if (collapsedSet.value.has(statementId)) {
            toggleCollapse(statementId)
            return
        }
        const index = statementRows.value.indexOf(row)
        const child = statementRows.value[index + 1]
        if (child && child.depth > row.depth) {
            const childId = child.statement.statement_id
            setSelection([childId], childId)
            focusStatement(childId)
        }
        return
    }
    if (event.key === 'ArrowLeft') {
        const row = statementRows.value.find((item) => item.statement.statement_id === statementId)
        if (!row) return
        event.preventDefault()
        if (row.has_children && !collapsedSet.value.has(statementId)) {
            toggleCollapse(statementId)
            return
        }
        const index = statementRows.value.indexOf(row)
        for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
            const candidate = statementRows.value[cursor]
            if (candidate && candidate.depth < row.depth) {
                const parentId = candidate.statement.statement_id
                setSelection([parentId], parentId)
                focusStatement(parentId)
                break
            }
        }
        return
    }
    if (event.key === 'Home' || event.key === 'End') {
        event.preventDefault()
        const target = event.key === 'Home' ? visibleIds.value[0] : visibleIds.value.at(-1)
        if (target) {
            setSelection([target], target)
            focusStatement(target)
        }
        return
    }
    if (modifier && event.key.toLowerCase() === 'c') {
        event.preventDefault()
        performAction('copy', statementId)
        return
    }
    if (modifier && event.key.toLowerCase() === 'x') {
        event.preventDefault()
        performAction('cut', statementId)
        return
    }
    if (modifier && event.key.toLowerCase() === 'v') {
        event.preventDefault()
        if (props.canPaste) performAction('paste', statementId)
        else liveMessage.value = '当前函数没有可粘贴的语句'
        return
    }
    if (modifier && event.key.toLowerCase() === 'd') {
        event.preventDefault()
        performAction('duplicate', statementId)
        return
    }
    if (event.key === 'Escape' && props.pendingCutStatementIds.length) {
        event.preventDefault()
        performAction('cancel-clipboard', statementId)
        return
    }
    if (event.key === 'Delete' || event.key === 'Backspace') {
        event.preventDefault()
        performAction('delete', statementId)
        return
    }
    if (event.key === 'Enter') {
        event.preventDefault()
        if (selectedSet.value.has(statementId)) openQuickInsertAfter(statementId)
        else setSelection([statementId], statementId)
        return
    }
    if (event.key === ' ') {
        event.preventDefault()
        setSelection([statementId], statementId)
    }
}

function performNesting(statementId: string, direction: 'in' | 'out'): void {
    if (props.busy) return
    if (!canNest(statementId, direction)) {
        liveMessage.value = direction === 'in' ? '上一条语句不是可以容纳内容的语句块' : '当前语句已经位于函数最外层'
        return
    }
    const statementIds = actionStatementIds(statementId)
    emit('action', { kind: 'nest', statement_ids: statementIds, direction })
    liveMessage.value = `已请求${direction === 'in' ? '移入上一个语句块' : '移出当前语句块'}`
}

function toggleMoreActions(statementId: string): void {
    openActionsId.value = openActionsId.value === statementId ? null : statementId
}

function openStatementContextMenu(statementId: string): void {
    if (props.busy) return
    if (!selectedSet.value.has(statementId)) setSelection([statementId], statementId)
    openActionsId.value = statementId
}

function openMoreActions(statementId: string, event: KeyboardEvent): void {
    openActionsId.value = statementId
    const trigger = event.currentTarget as HTMLElement
    void nextTick(() => trigger.parentElement?.querySelector<HTMLElement>('[role="menuitem"]:not(:disabled)')?.focus())
}

function closeMoreActions(event: KeyboardEvent): void {
    const menu = event.currentTarget as HTMLElement
    const trigger = menu.parentElement?.querySelector<HTMLElement>(':scope > button') || null
    openActionsId.value = null
    void nextTick(() => trigger?.focus())
}

function onMoreMenuKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
        event.stopPropagation()
        event.preventDefault()
        closeMoreActions(event)
        return
    }
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
    const menu = event.currentTarget as HTMLElement
    const items = [...menu.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not(:disabled)')]
    if (!items.length) return
    event.preventDefault()
    const current = items.indexOf(document.activeElement as HTMLButtonElement)
    const next = event.key === 'Home' ? 0
        : event.key === 'End' ? items.length - 1
            : event.key === 'ArrowDown' ? (current + 1 + items.length) % items.length
                : (current - 1 + items.length) % items.length
    items[next]?.focus()
}

function closeMoreOnFocusOut(event: FocusEvent): void {
    const current = event.currentTarget as HTMLElement
    if (event.relatedTarget instanceof Node && current.contains(event.relatedTarget)) return
    openActionsId.value = null
}

function performMoreAction(statementId: string, action: 'nest-in' | 'nest-out' | 'copy' | 'cut' | 'paste' | 'duplicate' | 'extract' | 'delete'): void {
    openActionsId.value = null
    if (action === 'nest-in' || action === 'nest-out') {
        performNesting(statementId, action === 'nest-in' ? 'in' : 'out')
        return
    }
    performAction(action, statementId)
}

interface UiStatementContainer {
    parent: ProgramStatement | null
    statements: ProgramStatement[]
    index: number
}

function childStatementLists(statement: ProgramStatement): ProgramStatement[][] {
    if (statement.kind === 'if') return [
        statement.then_body,
        ...statement.additional_branches.map((branch) => branch.statements),
        statement.else_body,
    ]
    if (statement.kind === 'loop' || statement.kind === 'target_scope') return [statement.body]
    if (statement.kind === 'try') return [
        statement.body,
        ...statement.catches.map((clause) => clause.statements),
        statement.finally_body,
    ]
    return []
}

function findUiContainer(statements: ProgramStatement[], statementId: string, parent: ProgramStatement | null = null): UiStatementContainer | null {
    const index = statements.findIndex((statement) => statement.statement_id === statementId)
    if (index >= 0) return { parent, statements, index }
    for (const statement of statements) {
        for (const children of childStatementLists(statement)) {
            const found = findUiContainer(children, statementId, statement)
            if (found) return found
        }
    }
    return null
}

function canNest(statementId: string, direction: 'in' | 'out'): boolean {
    const statementIds = actionStatementIds(statementId)
    const containers = statementIds.map((id) => findUiContainer(props.statements, id))
    if (!containers.length || containers.some((container) => !container)) return false
    const first = containers[0] as UiStatementContainer
    if (containers.some((container) => container?.statements !== first.statements)) return false
    const indexes = (containers as UiStatementContainer[]).map((container) => container.index).sort((left, right) => left - right)
    if (indexes.some((index, offset) => index !== indexes[0] + offset)) return false
    if (direction === 'out') return Boolean(first.parent)
    const previous = first.statements[indexes[0] - 1]
    return Boolean(previous && statementHasChildren(previous))
}

function actionStatementIds(statementId: string): string[] {
    return selectedSet.value.has(statementId) && localSelection.value.length ? [...localSelection.value] : [statementId]
}

function actionObjectLabel(statementId: string): string {
    const count = actionStatementIds(statementId).length
    return count > 1 ? `${count} 条选中语句` : '语句'
}

function batchActionLabel(action: 'copy' | 'cut' | 'duplicate' | 'extract' | 'delete', statementId: string): string {
    const count = actionStatementIds(statementId).length
    const single = action === 'copy' ? '复制语句' : action === 'cut' ? '剪切语句' : action === 'duplicate' ? '创建语句副本' : action === 'extract' ? '提取为项目函数' : '删除语句'
    if (count === 1) return single
    if (action === 'copy') return `复制 ${count} 条语句`
    if (action === 'cut') return `剪切 ${count} 条语句`
    if (action === 'duplicate') return `创建 ${count} 条语句副本`
    return action === 'extract' ? `将 ${count} 条语句提取为项目函数` : `删除 ${count} 条语句`
}

function deleteFallback(statementIds: string[]): string | null {
    const indexes = statementIds.map((id) => visibleIds.value.indexOf(id)).filter((index) => index >= 0)
    if (!indexes.length) return null
    const after = visibleIds.value[Math.max(...indexes) + 1]
    if (after && !statementIds.includes(after)) return after
    const before = visibleIds.value[Math.min(...indexes) - 1]
    return before && !statementIds.includes(before) ? before : null
}

function performAction(kind: Exclude<StatementListAction['kind'], 'nest'>, statementId: string, direction?: 'up' | 'down'): void {
    if (props.busy) return
    const statementIds = actionStatementIds(statementId)
    if (!selectedSet.value.has(statementId)) setSelection(statementIds, statementId)
    if (kind === 'move') {
        const moveDirection = direction || 'down'
        emit('action', { kind, statement_ids: statementIds, direction: moveDirection })
        liveMessage.value = `已请求${moveDirection === 'up' ? '上移' : '下移'} ${statementIds.length} 条语句`
        return
    }
    if (kind === 'copy') {
        emit('action', { kind, statement_ids: statementIds })
        liveMessage.value = `已复制 ${statementIds.length} 条语句，可在当前项目的其他函数中粘贴`
        return
    }
    if (kind === 'cut') {
        emit('action', { kind, statement_ids: statementIds })
        liveMessage.value = `已剪切 ${statementIds.length} 条语句，选择位置后粘贴`
        return
    }
    if (kind === 'paste') {
        emit('action', { kind, statement_ids: statementIds })
        liveMessage.value = '正在粘贴语句'
        return
    }
    if (kind === 'duplicate') {
        emit('action', { kind, statement_ids: statementIds })
        liveMessage.value = `正在创建 ${statementIds.length} 条语句副本`
        return
    }
    if (kind === 'cancel-clipboard') {
        emit('action', { kind, statement_ids: statementIds })
        liveMessage.value = '已取消剪切'
        return
    }
    if (kind === 'extract') {
        emit('action', { kind, statement_ids: statementIds })
        liveMessage.value = `准备提取 ${statementIds.length} 条语句`
        return
    }
    const fallback = deleteFallback(statementIds)
    emit('action', { kind, statement_ids: statementIds, fallback_statement_id: fallback })
    liveMessage.value = `已请求删除 ${statementIds.length} 条语句`
}

function toggleCollapse(statementId: string): void {
    const next = new Set(localCollapsed.value)
    if (next.has(statementId)) next.delete(statementId)
    else next.add(statementId)
    localCollapsed.value = [...next]
    emit('update:collapsedStatementIds', localCollapsed.value)
    liveMessage.value = next.has(statementId) ? '语句块已折叠' : '语句块已展开'
}
</script>

<style scoped>
.statement-editor {
    min-width: 0;
    height: 100%;
    overflow: hidden;
    background: var(--app-bg-base);
    color: var(--app-text-regular);
}

.statement-tree {
    height: 100%;
    overflow: auto;
    padding: var(--app-spacing-sm) 0 var(--app-spacing-lg);
}

.statement-virtual-spacer { width: 1px; pointer-events: none; }

.statement-row,
.branch-row {
    --indent: calc((var(--statement-depth) - 1) * var(--app-spacing-md));
    padding-inline-start: calc(var(--app-spacing-sm) + var(--indent));
}

.statement-row {
    position: relative;
    display: grid;
    grid-template-columns: var(--app-control-compact) minmax(0, 1fr) auto auto auto;
    align-items: center;
    height: var(--app-control-default);
    padding-inline-end: var(--app-spacing-sm);
    border: 0;
    outline: 0;
    color: var(--app-text-regular);
    cursor: default;
    transition: background-color var(--app-transition-fast), color var(--app-transition-fast), box-shadow var(--app-transition-fast);
}

.statement-row.is-nested::before,
.branch-row.is-nested::before {
    position: absolute;
    inset-block: 0;
    inset-inline-start: calc(var(--app-spacing-sm) + var(--indent) - var(--app-spacing-sm));
    width: 1px;
    background: color-mix(in srgb, var(--app-text-primary) 7%, transparent);
    content: '';
}

.breakpoint-action span {
    display: block;
    width: 9px;
    height: 9px;
    border: 1px solid var(--app-text-muted);
    border-radius: 50%;
}

.breakpoint-action.active span {
    border-color: var(--app-color-error);
    background: var(--app-color-error);
}

.statement-row:hover { background: color-mix(in srgb, var(--app-bg-hover) 82%, transparent); }

.statement-row.is-structure {
    height: var(--app-control-default);
}

.statement-row.is-structure:not(.is-selected) {
    background: color-mix(in srgb, var(--app-bg-sidebar) 46%, transparent);
}

.statement-row.is-structure .statement-summary {
    color: var(--app-text-primary);
    font-weight: 600;
}

.statement-row.kind-target_scope .statement-summary {
    color: color-mix(in srgb, var(--app-color-primary-hover) 68%, var(--app-text-primary));
}

.statement-row.is-selected {
    background: color-mix(in srgb, var(--app-color-primary) 10%, transparent);
    color: var(--app-text-primary);
}

.statement-row.is-cut-pending .statement-content { opacity: .58; }
.statement-row.is-cut-pending .statement-content::after {
    content: '待移动';
    margin-inline-start: var(--app-spacing-xs);
    color: var(--app-text-secondary);
    font-size: var(--app-font-xs);
    white-space: nowrap;
}

.statement-row.is-primary { box-shadow: inset 1px 0 var(--app-color-primary-hover); }
.statement-row.is-running { box-shadow: inset 1px 0 var(--app-color-success); }
.statement-row.is-failed { box-shadow: inset 1px 0 var(--app-color-danger); }
.statement-row:focus-visible { box-shadow: var(--focus-ring); }

.collapse-button,
.statement-actions button {
    display: grid;
    place-items: center;
    width: var(--app-control-compact);
    height: var(--app-control-compact);
    padding: 0;
    border: 0;
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-secondary);
    cursor: pointer;
}

.collapse-button:hover,
.statement-actions button:hover {
    background: var(--app-bg-active);
    color: var(--app-text-primary);
}

.collapse-placeholder { width: var(--app-control-compact); }

.statement-content {
    display: flex;
    min-width: 0;
    align-items: baseline;
    gap: var(--app-spacing-xs);
    line-height: var(--app-line-height-compact);
}

.step-label {
    overflow: hidden;
    color: var(--app-text-placeholder);
    font-size: var(--app-font-xs);
    line-height: inherit;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.statement-row:hover .step-label,
.statement-row.is-selected .step-label { color: var(--app-text-secondary); }

.runtime-state,
.diagnostic-count {
    margin-inline-start: var(--app-spacing-sm);
    color: var(--app-text-secondary);
    font-size: var(--app-font-xs);
    white-space: nowrap;
}

.is-running .runtime-state { color: var(--app-color-success); }
.is-failed .runtime-state,
.diagnostic-count { color: var(--app-color-danger); }

.statement-actions {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: var(--app-spacing-xs);
    margin-inline-start: var(--app-spacing-sm);
}

.statement-more { position: relative; display: inline-flex; }
.statement-more-menu {
    position: absolute;
    z-index: 30;
    top: calc(100% + 3px);
    right: 0;
    width: 218px;
    padding: var(--app-spacing-xs);
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-md);
    background: var(--app-bg-raised);
    box-shadow: var(--app-shadow-lg);
}
.statement-actions .statement-more-menu button {
    width: 100%;
    height: var(--app-control-compact);
    display: grid;
    grid-template-columns: 18px minmax(0, 1fr) auto;
    justify-items: start;
    padding: 0 var(--app-spacing-sm);
    color: var(--app-text-regular);
    font-family: var(--app-font-sans);
    font-size: var(--app-font-xs);
    text-align: start;
    white-space: nowrap;
}
.statement-more-menu kbd { color: var(--app-text-placeholder); font-family: var(--app-font-sans); font-size: var(--app-font-caption); }

.statement-actions button:disabled { cursor: not-allowed; opacity: 0.46; }
.statement-actions .danger-action:hover { color: var(--app-color-danger); }

.branch-row {
    position: relative;
    display: flex;
    width: 100%;
    align-items: center;
    height: 26px;
    padding-block: 0;
    padding-inline-end: var(--app-spacing-sm);
    border: 0;
    outline: 0;
    background: transparent;
    color: var(--app-text-secondary);
    font-family: inherit;
    font-size: var(--app-font-xs);
    font-weight: 550;
    text-align: start;
    cursor: pointer;
}

.branch-row:hover { background: color-mix(in srgb, var(--app-bg-hover) 58%, transparent); color: var(--app-text-primary); }
.branch-row:focus-visible { box-shadow: var(--focus-ring); }
.branch-row.is-insertion-target { background: var(--app-color-primary-dim); color: var(--app-text-primary); }
.branch-row.is-optional-action {
    color: var(--app-text-placeholder);
    font-weight: 400;
}
.branch-row.is-optional-action:hover,
.branch-row.is-optional-action.is-insertion-target { color: var(--app-text-primary); }

.branch-insert-action {
    display: grid;
    width: var(--app-control-compact);
    height: var(--app-control-compact);
    flex: 0 0 var(--app-control-compact);
    margin-inline-start: auto;
    place-items: center;
    padding: 0;
    border: 0;
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-secondary);
    cursor: pointer;
}

.branch-insert-action:hover { background: var(--app-bg-active); color: var(--app-text-primary); }
.branch-insert-action:focus-visible { outline: 0; box-shadow: var(--focus-ring); }
.branch-insert-action:active { background: color-mix(in srgb, var(--app-bg-active) 76%, var(--app-color-primary-dim)); }
.branch-insert-action:disabled { cursor: not-allowed; opacity: 0.46; }

.branch-label {
    flex: 0 0 auto;
    padding-inline: var(--app-spacing-md) var(--app-spacing-sm);
}

.branch-rule {
    height: 1px;
    min-width: var(--app-spacing-lg);
    flex: 1 1 auto;
    margin-inline-end: var(--app-spacing-sm);
    background: color-mix(in srgb, var(--app-border-default) 62%, transparent);
}

.branch-row em {
    color: var(--app-text-placeholder);
    font-size: var(--app-font-xs);
    font-style: normal;
    font-weight: 400;
}

.statement-empty {
    display: flex;
    height: 100%;
    min-height: 220px;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--app-spacing-sm);
    padding: var(--app-spacing-xl);
    color: var(--app-text-secondary);
    text-align: center;
}

.quick-insert-empty {
    width: min(620px, 100%);
    flex: 0 0 auto;
    padding-inline: 0;
    text-align: start;
}

.quick-insert-empty :deep(.quick-insert__results) { left: 0; right: 0; }

.statement-empty strong {
    color: var(--app-text-primary);
    font-size: var(--app-font-sm);
    font-weight: 600;
}

.statement-empty p {
    max-width: 34ch;
    margin: 0;
    color: var(--app-text-secondary);
    font-size: var(--app-font-xs);
    line-height: 1.6;
}

.statement-empty button {
    min-height: var(--app-control-compact);
    margin-top: var(--app-spacing-xs);
    padding: 0 var(--app-spacing-md);
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    background: var(--app-bg-raised);
    color: var(--app-text-regular);
    cursor: pointer;
}

.statement-empty button:hover {
    border-color: var(--app-border-strong);
    background: var(--app-bg-hover);
    color: var(--app-text-primary);
}

.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
}

@media (prefers-reduced-motion: reduce) {
    .statement-row { transition: none; }
}
</style>
