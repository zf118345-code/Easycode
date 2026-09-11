<template>
    <VNextNavigationPane class="function-library" aria-label="函数库">
        <VNextPaneHeader title="函数库">
            <template v-if="activeTab === 'project'" #actions><VNextIconButton label="新建项目函数" :disabled="busy" @click="emit('createProject')"><Plus aria-hidden="true" /></VNextIconButton></template>
        </VNextPaneHeader>

        <div class="library-tabs" role="tablist" aria-label="函数来源">
            <button
                v-for="tab in visibleTabs"
                :id="`function-tab-${tab.id}`"
                :key="tab.id"
                type="button"
                role="tab"
                :aria-selected="activeTab === tab.id"
                :aria-controls="`function-panel-${tab.id}`"
                :tabindex="activeTab === tab.id ? 0 : -1"
                @click="activeTab = tab.id"
                @keydown="onTabKeydown(tab.id, $event)"
            >
                {{ tab.label }}
            </button>
        </div>

        <VNextListSearch ref="searchControl" class="library-search" :model-value="query" :placeholder="`搜索${activeTabLabel}`" :aria-label="`搜索${activeTabLabel}`" @update:model-value="query = $event.trim()" @keydown.down.prevent="focusFirstRow" />

        <div
            :id="`function-panel-${activeTab}`"
            ref="libraryPanel"
            class="library-panel app-navigation-list"
            role="tabpanel"
            :aria-labelledby="`function-tab-${activeTab}`"
            @scroll.passive="loadMoreProjectsOnScroll"
        >
            <template v-if="activeTab === 'official' && officialCatalogGroups.length">
                <section v-for="group in officialCatalogGroups" :key="group.namespace" class="function-group">
                    <button
                        type="button"
                        class="group-heading"
                        :aria-expanded="domainExpanded(group.namespace)"
                        @click="toggleDomain(group.namespace)"
                    >
                        <ChevronDown v-if="domainExpanded(group.namespace)" :size="14" aria-hidden="true" />
                        <ChevronRight v-else :size="14" aria-hidden="true" />
                        <span>{{ group.namespace }}</span>
                        <small>{{ group.items.length }}</small>
                    </button>
                    <ul v-if="domainExpanded(group.namespace)" class="function-list" role="listbox">
                        <li v-for="entry in group.items" :key="`${entry.source}:${entry.id}`">
                            <VNextNavigationItem
                                v-if="entry.source === 'structure'"
                                as="div"
                                class="function-row"
                                :selected="isSelected('structure', entry.item.id)"
                            >
                                <button
                                    type="button"
                                    class="function-main"
                                    role="option"
                                    :aria-selected="isSelected('structure', entry.item.id)"
                                    :aria-label="entry.item.label"
                                    :data-structure-kind="entry.item.kind"
                                    :data-structure-mode="entry.item.id"
                                    :disabled="busy"
                                    :title="entry.item.description"
                                    @click="selectFunction('structure', entry.item.id)"
                                    @dblclick="insertStructure(entry.item.id)"
                                    @keydown="onRowKeydown('structure', entry.item.id, $event)"
                                >
                                    <span class="semantic-function">
                                        <span
                                            v-for="(part, partIndex) in entry.item.parts"
                                            :key="`${partIndex}:${part.text}`"
                                            :class="{ 'semantic-function-value': part.dynamic }"
                                        >{{ part.text }}</span>
                                    </span>
                                </button>
                                <button
                                    type="button"
                                    class="row-action"
                                    :disabled="busy"
                                    :aria-label="`插入${entry.item.label}`"
                                    @click="insertStructure(entry.item.id)"
                                >插入</button>
                            </VNextNavigationItem>
                            <VNextNavigationItem
                                v-else
                                as="div"
                                class="function-row"
                                :selected="isSelected('official', entry.item.function_id)"
                            >
                                <button
                                    type="button"
                                    class="function-main"
                                    role="option"
                                    :aria-selected="isSelected('official', entry.item.function_id)"
                                    :aria-label="semanticFunctionLabel(entry.item)"
                                    :data-function-id="entry.item.function_id"
                                    :disabled="busy"
                                    @click="selectFunction('official', entry.item.function_id)"
                                    @dblclick="insertFunction('official', entry.item.function_id)"
                                    @keydown="onRowKeydown('official', entry.item.function_id, $event)"
                                >
                                    <span class="semantic-function" :title="entry.item.qualified_name">
                                        <span
                                            v-for="(part, partIndex) in semanticFunctionParts(entry.item)"
                                            :key="`${partIndex}:${part.text}`"
                                            :class="{ 'semantic-function-value': part.dynamic }"
                                        >{{ part.text }}</span>
                                    </span>
                                </button>
                                <button
                                    type="button"
                                    class="row-action"
                                    :disabled="busy"
                                    :aria-label="`插入${semanticFunctionLabel(entry.item)}`"
                                    @click="insertFunction('official', entry.item.function_id)"
                                >
                                    插入
                                </button>
                            </VNextNavigationItem>
                        </li>
                    </ul>
                </section>
            </template>

            <ul v-else-if="activeTab === 'project' && filteredProjects.length" class="function-list project-list" role="listbox">
                <li v-for="item in visibleProjects" :key="item.function_id">
                    <VNextNavigationItem
                        as="div"
                        class="function-row project-row"
                        :selected="isSelected('project', item.function_id)"
                        @contextmenu.prevent="showProjectMenu(item.function_id)"
                    >
                        <button
                            type="button"
                            class="function-main"
                            role="option"
                            :aria-selected="isSelected('project', item.function_id)"
                            :data-function-id="item.function_id"
                            :disabled="busy"
                            @click="openProject(item)"
                            @keydown="onRowKeydown('project', item.function_id, $event, item)"
                        >
                            <span :title="item.display_name">{{ item.display_name }}</span>
                            <small>{{ item.statement_count }} 条语句</small>
                        </button>
                        <button
                            type="button"
                            class="row-action"
                            :disabled="busy || Boolean(item.insert_disabled_reason)"
                            :title="item.insert_disabled_reason || undefined"
                            :aria-label="projectActionLabel(item)"
                            @click="activateProject(item)"
                        >
                            {{ item.insert_disabled_reason ? '当前' : item.insertable ? '插入' : '打开' }}
                        </button>
                        <div class="project-menu-root">
                            <button
                                type="button"
                                class="more-action"
                                :disabled="busy"
                                aria-haspopup="menu"
                                :aria-expanded="openProjectMenuId === item.function_id"
                                :aria-label="`${item.display_name}的更多操作`"
                                :data-project-menu-trigger="item.function_id"
                                @click.stop="toggleProjectMenu(item.function_id, $event)"
                                @keydown.down.prevent.stop="openProjectMenuFromKeyboard(item.function_id, $event)"
                                @keydown.up.prevent.stop="openProjectMenuFromKeyboard(item.function_id, $event, true)"
                            >
                                <MoreHorizontal :size="14" aria-hidden="true" />
                            </button>
                            <div
                                v-if="openProjectMenuId === item.function_id"
                                class="project-menu"
                                role="menu"
                                :aria-label="`${item.display_name}的操作`"
                                :data-project-menu="item.function_id"
                                @keydown="onProjectMenuKeydown(item.function_id, $event)"
                            >
                                <button type="button" role="menuitem" @click="openProjectFromMenu(item)">查看或编辑</button>
                                <button
                                    type="button"
                                    role="menuitem"
                                    :disabled="Boolean(item.insert_disabled_reason)"
                                    :title="item.insert_disabled_reason || undefined"
                                    @click="insertProjectFromMenu(item)"
                                >插入调用</button>
                                <button type="button" role="menuitem" @click="renameProjectFromMenu(item)">重命名</button>
                                <button type="button" role="menuitem" class="danger-menu-item" @click="deleteProjectFromMenu(item)">删除</button>
                            </div>
                        </div>
                    </VNextNavigationItem>
                </li>
                <li v-if="renderedProjectTotal < filteredProjects.length" class="library-load-state" role="status">
                    已显示 {{ renderedProjectTotal }} / {{ filteredProjects.length }}，继续向下滚动可查看更多
                </li>
            </ul>

            <template v-else-if="activeTab === 'extension' && extensionGroups.length">
                <section v-for="group in extensionGroups" :key="group.namespace" class="function-group">
                    <h2 class="extension-heading">{{ group.namespace }}</h2>
                    <ul class="function-list" role="listbox">
                        <li v-for="item in group.items" :key="item.function_id">
                            <VNextNavigationItem as="div" class="function-row" :selected="isSelected('extension', item.function_id)">
                                <button
                                    type="button"
                                    class="function-main"
                                    role="option"
                                    :aria-selected="isSelected('extension', item.function_id)"
                                    :data-function-id="item.function_id"
                                    :disabled="busy"
                                    @click="selectFunction('extension', item.function_id)"
                                    @dblclick="insertFunction('extension', item.function_id)"
                                    @keydown="onRowKeydown('extension', item.function_id, $event)"
                                >
                                    <span class="semantic-function" :title="item.qualified_name || item.display_name">
                                        <span
                                            v-for="(part, partIndex) in semanticExtensionParts(item)"
                                            :key="`${partIndex}:${part.text}`"
                                            :class="{ 'semantic-function-value': part.dynamic }"
                                        >{{ part.text }}</span>
                                    </span>
                                </button>
                                <button
                                    type="button"
                                    class="row-action"
                                    :disabled="busy"
                                    :aria-label="`插入${semanticExtensionLabel(item)}`"
                                    @click="insertFunction('extension', item.function_id)"
                                >
                                    插入
                                </button>
                            </VNextNavigationItem>
                        </li>
                    </ul>
                </section>
            </template>

            <VNextWorkspaceState v-else class="library-empty" compact :kind="query ? 'filtered' : 'empty'" :title="emptyTitle" :description="emptyDescription">
                <template v-if="activeTab === 'project' && !query" #actions><VNextButton size="compact" :disabled="busy" @click="emit('createProject')">新建项目函数</VNextButton></template>
            </VNextWorkspaceState>
        </div>

        <p class="sr-only" aria-live="polite">{{ liveMessage }}</p>
    </VNextNavigationPane>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ChevronDown, ChevronRight, MoreHorizontal, Plus } from 'lucide-vue-next'
import VNextWorkspaceState from '../components/ui/VNextWorkspaceState.vue'
import VNextPaneHeader from '../components/ui/VNextPaneHeader.vue'
import VNextListSearch from '../components/ui/VNextListSearch.vue'
import VNextNavigationPane from '../components/ui/VNextNavigationPane.vue'
import VNextNavigationItem from '../components/ui/VNextNavigationItem.vue'
import VNextButton from '../components/ui/VNextButton.vue'
import VNextIconButton from '../components/ui/VNextIconButton.vue'
import type { AvailableFunctionContractDto } from './serverTypes'
import type {
    ExtensionFunctionLibraryItem,
    FunctionLibrarySelection,
    FunctionLibrarySource,
    FunctionLibraryTab,
    ProjectFunctionLibraryItem,
} from './functionLibraryTypes'
import {
    buildFunctionCatalog,
    normalizeFunctionQuery,
    searchFunctionCatalog,
    semanticExtensionLabel,
    semanticExtensionParts,
    semanticFunctionLabel,
    semanticFunctionParts,
    structureItems,
    type StructureLibraryItem,
} from './functionCatalogSearch'

interface FunctionGroup<T> {
    namespace: string
    items: T[]
}

const props = withDefaults(defineProps<{
    officialFunctions?: AvailableFunctionContractDto[]
    projectFunctions?: ProjectFunctionLibraryItem[]
    extensionFunctions?: ExtensionFunctionLibraryItem[]
    selected?: FunctionLibrarySelection | null
    initialTab?: FunctionLibraryTab
    busy?: boolean
}>(), {
    officialFunctions: () => [],
    projectFunctions: () => [],
    extensionFunctions: () => [],
    selected: null,
    initialTab: 'project',
    busy: false,
})

const emit = defineEmits<{
    select: [selection: FunctionLibrarySelection]
    insert: [selection: FunctionLibrarySelection]
    openProject: [functionId: string]
    createProject: []
    renameProject: [item: ProjectFunctionLibraryItem]
    deleteProject: [item: ProjectFunctionLibraryItem]
}>()

const tabs: Array<{ id: FunctionLibraryTab; label: string }> = [
    { id: 'project', label: '项目' },
    { id: 'official', label: '官方' },
    { id: 'extension', label: '扩展' },
]
const activeTab = ref<FunctionLibraryTab>(props.initialTab)
const query = ref('')
const selected = ref<FunctionLibrarySelection | null>(props.selected)
const rememberedOfficialDomainKey = 'easycode:v6:function-library:official-domain'
const expandedDomain = ref(readRememberedDomain())
const libraryPanel = ref<HTMLElement | null>(null)
const searchControl = ref<InstanceType<typeof VNextListSearch> | null>(null)
const liveMessage = ref('')
const openProjectMenuId = ref('')
const projectMenuTrigger = ref<HTMLElement | null>(null)
const PROJECT_RENDER_BATCH_SIZE = 100
const renderedProjectCount = ref(PROJECT_RENDER_BATCH_SIZE)
type OfficialCatalogEntry =
    | { source: 'structure'; id: string; item: StructureLibraryItem }
    | { source: 'official'; id: string; item: AvailableFunctionContractDto }
interface OfficialCatalogGroup { namespace: string; items: OfficialCatalogEntry[] }

const availableOfficialFunctions = computed(() => props.officialFunctions.filter((item) => (
    item.implementation_state === 'available'
)))
const availableExtensionFunctions = computed(() => props.extensionFunctions.filter((item) => (
    item.implementation_state === 'available'
)))
const visibleTabs = computed(() => tabs.filter((tab) => tab.id !== 'extension' || availableExtensionFunctions.value.length > 0))
const activeTabLabel = computed(() => tabs.find((tab) => tab.id === activeTab.value)?.label || '函数')
const normalizedQuery = computed(() => normalizeFunctionQuery(query.value))
const catalogCandidates = computed(() => buildFunctionCatalog({
    officialFunctions: props.officialFunctions,
    projectFunctions: props.projectFunctions,
    extensionFunctions: props.extensionFunctions,
}))
const matchingCandidates = computed(() => searchFunctionCatalog(catalogCandidates.value, normalizedQuery.value))
const matchingKeys = computed(() => new Set(matchingCandidates.value.map((candidate) => candidate.key)))
const filteredOfficial = computed(() => availableOfficialFunctions.value.filter((item) => matchingKeys.value.has(`official:${item.function_id}`)))
const filteredStructures = computed(() => structureItems.filter((item) => matchingKeys.value.has(`structure:${item.id}`)))
const filteredProjects = computed(() => props.projectFunctions
    .filter((item) => matchingKeys.value.has(`project:${item.function_id}`))
    .sort((left, right) => left.display_name.localeCompare(right.display_name, 'zh-CN', {
        numeric: true,
        sensitivity: 'base',
    })))
const visibleProjects = computed(() => {
    const batch = filteredProjects.value.slice(0, renderedProjectCount.value)
    if (selected.value?.source !== 'project') return batch
    const current = filteredProjects.value.find((item) => item.function_id === selected.value?.function_id)
    if (!current || batch.some((item) => item.function_id === current.function_id)) return batch
    // Keep the current function reachable without rendering every preceding row in a large project.
    return [current, ...batch]
})
const renderedProjectTotal = computed(() => Math.min(renderedProjectCount.value, filteredProjects.value.length))
const filteredExtensions = computed(() => availableExtensionFunctions.value.filter((item) => matchingKeys.value.has(`extension:${item.function_id}`)))

function groupedByNamespace<T extends { namespace: string }>(items: T[]): FunctionGroup<T>[] {
    const groups = new Map<string, T[]>()
    for (const item of items) {
        const entries = groups.get(item.namespace) || []
        entries.push(item)
        groups.set(item.namespace, entries)
    }
    return [...groups.entries()].map(([namespace, entries]) => ({ namespace, items: entries }))
}

const officialCatalogGroups = computed<OfficialCatalogGroup[]>(() => {
    const groups = new Map<string, OfficialCatalogEntry[]>()
    const preferredOrder = ['流程控制', '变量', '消息']
    for (const item of filteredStructures.value) {
        const entries = groups.get(item.group) || []
        entries.push({ source: 'structure', id: item.id, item })
        groups.set(item.group, entries)
    }
    for (const item of filteredOfficial.value) {
        const entries = groups.get(item.namespace) || []
        entries.push({ source: 'official', id: item.function_id, item })
        groups.set(item.namespace, entries)
    }
    return [...groups.entries()]
        .sort(([left], [right]) => {
            const leftIndex = preferredOrder.indexOf(left)
            const rightIndex = preferredOrder.indexOf(right)
            if (leftIndex >= 0 || rightIndex >= 0) return (leftIndex < 0 ? preferredOrder.length : leftIndex) - (rightIndex < 0 ? preferredOrder.length : rightIndex)
            return left.localeCompare(right, 'zh-CN')
        })
        .map(([namespace, items]) => ({ namespace, items }))
})
const extensionGroups = computed(() => groupedByNamespace(filteredExtensions.value))
const emptyTitle = computed(() => {
    if (query.value) return '没有匹配的函数'
    if (activeTab.value === 'project') return '还没有项目函数'
    if (activeTab.value === 'official') return '当前没有可运行的官方函数'
    return '当前没有已启用的扩展函数'
})
const emptyDescription = computed(() => {
    if (query.value) return '尝试更短的名称或切换函数来源。'
    if (activeTab.value === 'project') return '项目函数用于组合并复用结构化语句。'
    if (activeTab.value === 'official') return '这里只展示后端已经实现并验证的函数。'
    return '启用扩展后，可运行函数会出现在这里。'
})

watch(() => props.selected, (value) => {
    selected.value = value
}, { deep: true, immediate: true })
watch(visibleTabs, (nextTabs) => {
    if (!nextTabs.some((tab) => tab.id === activeTab.value)) activeTab.value = nextTabs[0]?.id || 'project'
})
watch(activeTab, () => { query.value = ''; renderedProjectCount.value = PROJECT_RENDER_BATCH_SIZE })
watch(normalizedQuery, () => { renderedProjectCount.value = PROJECT_RENDER_BATCH_SIZE })

defineExpose({
    async focusSearch(value = '') {
        if (value && activeTab.value !== 'official') {
            activeTab.value = 'official'
            await nextTick()
        }
        if (value) query.value = value
        await nextTick()
        searchControl.value?.focus()
        searchControl.value?.select()
    },
})

function loadMoreProjectsOnScroll(event: Event): void {
    if (activeTab.value !== 'project' || visibleProjects.value.length >= filteredProjects.value.length) return
    const element = event.currentTarget as HTMLElement
    if (element.scrollTop + element.clientHeight < element.scrollHeight - 180) return
    renderedProjectCount.value = Math.min(
        renderedProjectCount.value + PROJECT_RENDER_BATCH_SIZE,
        filteredProjects.value.length,
    )
}

function readRememberedDomain(): string {
    try { return window.localStorage.getItem(rememberedOfficialDomainKey) || '' } catch { return '' }
}

function domainExpanded(namespace: string): boolean {
    return Boolean(normalizedQuery.value) || expandedDomain.value === namespace
}

function toggleDomain(namespace: string): void {
    expandedDomain.value = expandedDomain.value === namespace ? '' : namespace
    try {
        if (expandedDomain.value) window.localStorage.setItem(rememberedOfficialDomainKey, expandedDomain.value)
        else window.localStorage.removeItem(rememberedOfficialDomainKey)
    } catch { /* storage is optional; the in-memory accordion still works */ }
}

function closeProjectMenu(restoreFocus = false): void {
    openProjectMenuId.value = ''
    if (restoreFocus) void nextTick(() => projectMenuTrigger.value?.focus())
}
function projectMenuItems(functionId: string): HTMLButtonElement[] {
    return [...(libraryPanel.value?.querySelectorAll<HTMLButtonElement>(`[data-project-menu="${functionId}"] [role="menuitem"]:not(:disabled)`) || [])]
}
function focusProjectMenuEdge(functionId: string, last = false): void {
    void nextTick(() => {
        const items = projectMenuItems(functionId)
        items[last ? items.length - 1 : 0]?.focus()
    })
}
function toggleProjectMenu(functionId: string, event: MouseEvent): void {
    if (openProjectMenuId.value === functionId) {
        closeProjectMenu()
        return
    }
    projectMenuTrigger.value = event.currentTarget as HTMLElement
    openProjectMenuId.value = functionId
}
function openProjectMenuFromKeyboard(functionId: string, event: KeyboardEvent, last = false): void {
    projectMenuTrigger.value = event.currentTarget as HTMLElement
    openProjectMenuId.value = functionId
    focusProjectMenuEdge(functionId, last)
}
function showProjectMenu(functionId: string): void {
    if (!props.busy) openProjectMenuId.value = functionId
}
function onProjectMenuKeydown(functionId: string, event: KeyboardEvent): void {
    if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        closeProjectMenu(true)
        return
    }
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const items = projectMenuItems(functionId)
    const current = event.target as HTMLButtonElement
    const index = Math.max(0, items.indexOf(current))
    const nextIndex = event.key === 'Home'
        ? 0
        : event.key === 'End'
            ? items.length - 1
            : event.key === 'ArrowDown'
                ? (index + 1) % items.length
                : (index - 1 + items.length) % items.length
    items[nextIndex]?.focus()
}
function closeProjectMenuOutside(event: PointerEvent): void {
    const target = event.target
    if (target instanceof Element && target.closest('.project-menu-root')) return
    closeProjectMenu()
}
onMounted(() => document.addEventListener('pointerdown', closeProjectMenuOutside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', closeProjectMenuOutside))

function isSelected(source: FunctionLibrarySource, functionId: string): boolean {
    return selected.value?.source === source && selected.value.function_id === functionId
}

function selectFunction(source: FunctionLibrarySource, functionId: string): void {
    selected.value = { source, function_id: functionId }
    emit('select', selected.value)
    liveMessage.value = '已选择函数'
}

function insertFunction(source: 'official' | 'extension', functionId: string): void {
    if (props.busy) return
    selectFunction(source, functionId)
    emit('insert', { source, function_id: functionId })
    liveMessage.value = '已请求插入函数'
}

function insertStructure(id: string): void {
    if (props.busy) return
    selectFunction('structure', id)
    emit('insert', { source: 'structure', function_id: id })
    liveMessage.value = '已请求插入控制结构'
}

function activateProject(item: ProjectFunctionLibraryItem): void {
    if (props.busy) return
    selectFunction('project', item.function_id)
    if (item.insert_disabled_reason) {
        liveMessage.value = item.insert_disabled_reason
        return
    }
    if (item.insertable) {
        emit('insert', { source: 'project', function_id: item.function_id })
        liveMessage.value = '已请求插入项目函数'
    } else {
        emit('openProject', item.function_id)
        liveMessage.value = '已请求打开项目函数'
    }
}

function openProject(item: ProjectFunctionLibraryItem): void {
    if (props.busy) return
    selectFunction('project', item.function_id)
    emit('openProject', item.function_id)
    liveMessage.value = '已打开项目函数'
}

function projectActionLabel(item: ProjectFunctionLibraryItem): string {
    if (item.insert_disabled_reason) return item.insert_disabled_reason
    return item.insertable ? `插入${item.display_name}` : `打开${item.display_name}`
}

function openProjectFromMenu(item: ProjectFunctionLibraryItem): void {
    closeProjectMenu()
    selectFunction('project', item.function_id)
    emit('openProject', item.function_id)
}

function insertProjectFromMenu(item: ProjectFunctionLibraryItem): void {
    closeProjectMenu()
    if (item.insert_disabled_reason || !item.insertable) return
    selectFunction('project', item.function_id)
    emit('insert', { source: 'project', function_id: item.function_id })
}

function renameProjectFromMenu(item: ProjectFunctionLibraryItem): void {
    closeProjectMenu()
    emit('renameProject', item)
}

function deleteProjectFromMenu(item: ProjectFunctionLibraryItem): void {
    closeProjectMenu()
    emit('deleteProject', item)
}

function focusableRows(): HTMLButtonElement[] {
    return [...(libraryPanel.value?.querySelectorAll<HTMLButtonElement>('.function-main:not(:disabled)') || [])]
}

function focusFirstRow(): void {
    void nextTick(() => focusableRows()[0]?.focus())
}

function onRowKeydown(
    source: FunctionLibrarySource,
    functionId: string,
    event: KeyboardEvent,
    projectItem?: ProjectFunctionLibraryItem,
): void {
    const rows = focusableRows()
    const current = event.currentTarget as HTMLButtonElement
    const index = rows.indexOf(current)
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Home' || event.key === 'End') {
        event.preventDefault()
        const nextIndex = event.key === 'Home'
            ? 0
            : event.key === 'End'
                ? rows.length - 1
                : event.key === 'ArrowDown'
                    ? Math.min(rows.length - 1, index + 1)
                    : Math.max(0, index - 1)
        rows[nextIndex]?.focus()
        return
    }
    if (event.key === ' ') {
        event.preventDefault()
        selectFunction(source, functionId)
        return
    }
    if (event.key !== 'Enter') return
    event.preventDefault()
    if (source === 'project' && projectItem) openProject(projectItem)
    else if (source === 'structure') insertStructure(functionId)
    else insertFunction(source as 'official' | 'extension', functionId)
}

function onTabKeydown(currentTab: FunctionLibraryTab, event: KeyboardEvent): void {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const items = visibleTabs.value
    const index = items.findIndex((tab) => tab.id === currentTab)
    const nextIndex = event.key === 'Home'
        ? 0
        : event.key === 'End'
            ? items.length - 1
            : event.key === 'ArrowRight'
                ? (index + 1) % items.length
                : (index - 1 + items.length) % items.length
    activeTab.value = items[nextIndex].id
    void nextTick(() => document.getElementById(`function-tab-${activeTab.value}`)?.focus())
}
</script>

<style scoped>
.function-library {
    display: flex;
    width: 100%;
    min-width: 0;
    height: 100%;
    flex-direction: column;
    overflow: hidden;
    border-inline-end: 1px solid var(--app-border-subtle);
    background: var(--app-bg-sidebar);
    color: var(--app-text-regular);
}

.library-header {
    display: flex;
    min-height: var(--app-height-pane-header);
    flex: 0 0 auto;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--app-spacing-sm) 0 var(--app-spacing-md);
    border-bottom: 1px solid var(--app-border-subtle);
}

.library-header strong {
    min-width: 0;
    overflow: hidden;
    color: var(--app-text-primary);
    font-size: var(--app-font-sm);
    font-weight: 600;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.header-action,
.row-action,
.library-empty button {
    min-height: var(--app-control-compact);
    padding: 0 var(--app-spacing-sm);
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    background: var(--app-bg-raised);
    color: var(--app-text-regular);
    font: inherit;
    font-size: var(--app-font-xs);
    cursor: pointer;
}

.header-action:hover,
.row-action:hover,
.library-empty button:hover {
    border-color: var(--app-border-strong);
    background: var(--app-bg-hover);
    color: var(--app-text-primary);
}

.header-action:focus-visible,
.row-action:focus-visible,
.library-empty button:focus-visible { outline: 0; box-shadow: var(--focus-ring); }
.header-action { flex: none; }

.function-row .row-action {
    opacity: 0;
    transition: opacity var(--app-motion-fast);
}

.function-row:hover .row-action,
.function-row:focus-within .row-action,
.function-row.is-selected .row-action {
    opacity: 1;
}

button:disabled { cursor: not-allowed; opacity: 0.46; }

.library-tabs {
    display: grid;
    min-height: var(--app-control-default);
    flex: 0 0 auto;
    grid-auto-columns: 1fr;
    grid-auto-flow: column;
    padding: var(--app-spacing-xs) var(--app-spacing-sm) 0;
}

.library-tabs button {
    position: relative;
    min-height: var(--app-control-compact);
    border: 0;
    border-radius: var(--app-radius-sm) var(--app-radius-sm) 0 0;
    background: transparent;
    color: var(--app-text-secondary);
    font: inherit;
    font-size: var(--app-font-xs);
    cursor: pointer;
}

.library-tabs button:hover { color: var(--app-text-primary); }
.library-tabs button[aria-selected='true'] { color: var(--app-text-primary); }
.library-tabs button[aria-selected='true']::after {
    position: absolute;
    right: var(--app-spacing-sm);
    bottom: 0;
    left: var(--app-spacing-sm);
    height: 2px;
    border-radius: 2px 2px 0 0;
    background: var(--app-color-primary);
    content: '';
}
.library-tabs button:focus-visible { outline: 0; box-shadow: var(--focus-ring); }

.library-panel {
    min-height: 0;
    flex: 1;
    overflow: auto;
    padding-bottom: var(--app-spacing-lg);
}

.library-load-state {
    padding: 9px 8px;
    color: var(--app-text-placeholder);
    font-size: var(--app-font-xs);
    text-align: center;
}

.function-group { margin: 0; }

.group-heading {
    display: grid;
    width: 100%;
    min-height: var(--app-control-default);
    grid-template-columns: var(--app-control-compact) minmax(0, 1fr) auto;
    align-items: center;
    padding: 0 var(--app-spacing-sm) 0 var(--app-spacing-xs);
    border: 0;
    background: transparent;
    color: var(--app-text-regular);
    font: inherit;
    font-size: var(--app-font-sm);
    font-weight: 600;
    text-align: start;
    cursor: pointer;
}

.group-heading:hover { background: var(--app-bg-hover); color: var(--app-text-primary); }
.group-heading:focus-visible { outline: 0; box-shadow: var(--focus-ring); }
.group-heading small { color: var(--app-text-placeholder); font-size: var(--app-font-xs); font-weight: 400; }

.extension-heading {
    min-height: var(--app-control-default);
    margin: 0;
    padding: var(--app-spacing-sm) var(--app-spacing-md) var(--app-spacing-xs);
    color: var(--app-text-secondary);
    font-size: var(--app-font-xs);
    font-weight: 600;
}

.function-list {
    margin: 0;
    padding: 0;
    list-style: none;
}

.function-group > .function-list {
    padding-inline-start: calc(var(--app-control-compact) + var(--app-spacing-xs));
}

.function-group > .function-list .function-main {
    padding-inline-start: var(--app-spacing-xs);
    font-size: var(--app-font-xs);
}

.project-list { padding-top: var(--app-spacing-xs); }

.function-row {
    position: relative;
    display: grid;
    min-height: var(--app-list-row-compact);
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
}
.function-row.project-row { grid-template-columns: minmax(0, 1fr) auto auto; }

.function-row:hover { background: var(--app-bg-hover); }
.function-main {
    display: flex;
    min-width: 0;
    min-height: var(--app-list-row-compact);
    align-items: center;
    justify-content: space-between;
    gap: var(--app-spacing-sm);
    padding: 0 var(--app-spacing-sm) 0 var(--app-spacing-md);
    border: 0;
    outline: 0;
    background: transparent;
    color: var(--app-text-regular);
    font: inherit;
    font-size: var(--app-font-sm);
    text-align: start;
    cursor: default;
}

.function-main > span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.semantic-function { display: inline-flex; min-width: 0; align-items: baseline; }
.semantic-function-value { position: relative; display: inline-block; margin-inline: 2px; padding-inline: 6px; color: var(--app-text-primary); }
.semantic-function-value::before,
.semantic-function-value::after { position: absolute; width: 4px; height: 55%; border-color: var(--app-text-muted); content: ''; pointer-events: none; }
.semantic-function-value::before { inset-block-start: 2px; inset-inline-start: 0; border-block-start: 1px solid; border-inline-start: 1px solid; }
.semantic-function-value::after { inset-inline-end: 0; inset-block-end: 2px; border-inline-end: 1px solid; border-block-end: 1px solid; }

.function-main small {
    flex: 0 0 auto;
    color: var(--app-text-secondary);
    font-size: var(--app-font-xs);
}

.function-main:focus-visible { box-shadow: var(--focus-ring); }
.function-row.is-selected .function-main { color: var(--app-text-primary); }

.row-action {
    visibility: hidden;
    margin-inline-end: var(--app-spacing-sm);
    opacity: 0;
}

.function-row:hover .row-action,
.function-row:focus-within .row-action,
.function-row.is-selected .row-action {
    visibility: visible;
    opacity: 1;
}

.project-menu-root { position: relative; display: grid; place-items: center; margin-inline-end: var(--app-spacing-xs); }
.more-action {
    width: var(--app-control-compact);
    height: var(--app-control-compact);
    display: grid;
    visibility: hidden;
    place-items: center;
    padding: 0;
    border: 0;
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-secondary);
    cursor: pointer;
    opacity: 0;
}
.project-row:hover .more-action,
.project-row:focus-within .more-action,
.more-action[aria-expanded='true'] { visibility: visible; opacity: 1; }
.more-action:hover { background: var(--app-bg-raised); color: var(--app-text-primary); }
.more-action:focus-visible { outline: 0; box-shadow: var(--focus-ring); }
.project-menu {
    position: absolute;
    z-index: 20;
    top: calc(100% + var(--app-spacing-xs));
    right: 0;
    width: 154px;
    overflow: hidden;
    padding: var(--app-spacing-xs);
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-md);
    background: var(--app-bg-raised);
    box-shadow: var(--app-shadow-lg);
}
.project-menu button {
    width: 100%;
    min-height: var(--app-control-default);
    padding: 0 var(--app-spacing-sm);
    border: 0;
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-regular);
    font: inherit;
    font-size: var(--app-font-xs);
    text-align: start;
    cursor: pointer;
}
.project-menu button:hover:not(:disabled), .project-menu button:focus-visible { background: var(--app-bg-hover); color: var(--app-text-primary); outline: 0; }
.project-menu .danger-menu-item { color: var(--app-color-danger); }

.library-empty {
    display: flex;
    min-height: 190px;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--app-spacing-sm);
    padding: var(--app-spacing-lg);
    text-align: center;
}

.library-empty strong { color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 600; }
.library-empty p {
    max-width: 30ch;
    margin: 0;
    color: var(--app-text-secondary);
    font-size: var(--app-font-xs);
    line-height: 1.6;
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
</style>
