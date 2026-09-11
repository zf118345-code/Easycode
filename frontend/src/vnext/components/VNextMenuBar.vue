<template>
    <nav ref="root" class="app-menu-bar" aria-label="应用菜单">
        <button
            ref="compactTrigger"
            type="button"
            class="app-menu-compact-trigger"
            aria-label="打开应用菜单"
            :aria-expanded="compactOpen"
            aria-controls="app-menu-compact"
            @click="toggleCompact"
            @keydown="onCompactTriggerKeydown"
        >
            <Menu :size="16" aria-hidden="true" />
            <span>菜单</span>
        </button>
        <div v-if="compactOpen" id="app-menu-compact" class="app-menu-compact-popover" role="menu" aria-label="全部应用命令">
            <template v-for="group in groups" :key="group">
                <div class="app-menu-section-label" role="presentation">{{ group }}</div>
                <button
                    v-for="entry in compactEntriesByGroup[group]"
                    :key="entry.item.id"
                    :ref="element => setCompactItemRef(element, entry.flatIndex)"
                    type="button"
                    role="menuitem"
                    :disabled="!enabled(entry.item.id)"
                    :title="enabled(entry.item.id) ? entry.item.description : disabledReason(entry.item.id)"
                    @click="choose(entry.item.id)"
                    @keydown="onCompactItemKeydown($event, entry.flatIndex)"
                >
                    <span>{{ entry.item.label }}</span>
                    <kbd v-if="shortcuts[entry.item.id]">{{ shortcuts[entry.item.id] }}</kbd>
                </button>
            </template>
        </div>
        <div v-for="(group, groupIndex) in groups" :key="group" class="app-menu-root">
            <button
                :ref="element => setTriggerRef(element, groupIndex)"
                type="button"
                class="app-menu-trigger"
                :aria-expanded="openGroup === group"
                :aria-controls="`app-menu-${group}`"
                @click="toggle(group)"
                @keydown="onTriggerKeydown($event, groupIndex)"
            >{{ group }}</button>
            <div v-if="openGroup === group" :id="`app-menu-${group}`" class="app-menu-popover" role="menu">
                <button
                    v-for="(item, itemIndex) in commandsByGroup[group]"
                    :key="item.id"
                    :ref="element => setItemRef(element, itemIndex)"
                    type="button"
                    role="menuitem"
                    :disabled="!enabled(item.id)"
                    :title="enabled(item.id) ? item.description : disabledReason(item.id)"
                    @click="choose(item.id)"
                    @keydown="onItemKeydown($event, groupIndex, itemIndex)"
                >
                    <span>{{ item.label }}</span>
                    <kbd v-if="shortcuts[item.id]">{{ shortcuts[item.id] }}</kbd>
                </button>
            </div>
        </div>
    </nav>
</template>

<script setup lang="ts">
import { Menu } from 'lucide-vue-next'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, type ComponentPublicInstance } from 'vue'
import { IDE_COMMANDS, type IdeCommandGroup } from '../ideCommands'

const props = defineProps<{
    shortcuts: Record<string, string>
    enabled: (commandId: string) => boolean
    disabledReason: (commandId: string) => string
}>()
const emit = defineEmits<{ command: [commandId: string] }>()
const groups: IdeCommandGroup[] = ['项目', '编辑', '视图', '运行', '帮助']
const openGroup = ref<IdeCommandGroup | ''>('')
const compactOpen = ref(false)
const root = ref<HTMLElement | null>(null)
const compactTrigger = ref<HTMLButtonElement | null>(null)
const triggerRefs: HTMLButtonElement[] = []
const itemRefs: HTMLButtonElement[] = []
const compactItemRefs: HTMLButtonElement[] = []
const commandsByGroup = computed(() => Object.fromEntries(groups.map(group => [group, IDE_COMMANDS.filter(item => item.group === group)])) as Record<IdeCommandGroup, typeof IDE_COMMANDS>)
const compactEntries = computed(() => groups.flatMap(group => commandsByGroup.value[group]).map((item, flatIndex) => ({ item, flatIndex })))
const compactEntriesByGroup = computed(() => Object.fromEntries(groups.map(group => [group, compactEntries.value.filter(entry => entry.item.group === group)])) as Record<IdeCommandGroup, typeof compactEntries.value>)

function asButton(element: Element | ComponentPublicInstance | null): HTMLButtonElement | null {
    return element instanceof HTMLButtonElement ? element : null
}
function setTriggerRef(element: Element | ComponentPublicInstance | null, index: number) {
    const button = asButton(element)
    if (button) triggerRefs[index] = button
}
function setItemRef(element: Element | ComponentPublicInstance | null, index: number) {
    const button = asButton(element)
    if (button) itemRefs[index] = button
}
function setCompactItemRef(element: Element | ComponentPublicInstance | null, index: number) {
    const button = asButton(element)
    if (button) compactItemRefs[index] = button
}
function enabledItemIndexes(group: IdeCommandGroup): number[] {
    return commandsByGroup.value[group].flatMap((item, index) => props.enabled(item.id) ? [index] : [])
}
async function open(group: IdeCommandGroup, focus: 'none' | 'first' | 'last' = 'none') {
    itemRefs.length = 0
    openGroup.value = group
    if (focus === 'none') return
    await nextTick()
    const indexes = enabledItemIndexes(group)
    const index = focus === 'first' ? indexes[0] : indexes.at(-1)
    if (index !== undefined) itemRefs[index]?.focus()
}
function close() { openGroup.value = ''; compactOpen.value = false }
function toggle(group: IdeCommandGroup) { compactOpen.value = false; openGroup.value = openGroup.value === group ? '' : group }
async function openCompact(focus: 'none' | 'first' | 'last' = 'none') {
    openGroup.value = ''
    compactItemRefs.length = 0
    compactOpen.value = true
    if (focus === 'none') return
    await nextTick()
    const indexes = compactEntries.value.filter(entry => props.enabled(entry.item.id)).map(entry => entry.flatIndex)
    const index = focus === 'first' ? indexes[0] : indexes.at(-1)
    if (index !== undefined) compactItemRefs[index]?.focus()
}
function toggleCompact() { compactOpen.value ? close() : void openCompact() }
function onCompactTriggerKeydown(event: KeyboardEvent) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault()
        void openCompact(event.key === 'ArrowDown' ? 'first' : 'last')
    } else if (event.key === 'Escape' && compactOpen.value) {
        event.preventDefault()
        close()
        compactTrigger.value?.focus()
    }
}
function onCompactItemKeydown(event: KeyboardEvent, flatIndex: number) {
    const indexes = compactEntries.value.filter(entry => props.enabled(entry.item.id)).map(entry => entry.flatIndex)
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault()
        const current = indexes.indexOf(flatIndex)
        const direction = event.key === 'ArrowDown' ? 1 : -1
        const next = current < 0 ? 0 : (current + direction + indexes.length) % indexes.length
        compactItemRefs[indexes[next]]?.focus()
    } else if (event.key === 'Home' || event.key === 'End') {
        event.preventDefault()
        compactItemRefs[event.key === 'Home' ? indexes[0] : indexes.at(-1)!]?.focus()
    } else if (event.key === 'Escape') {
        event.preventDefault()
        close()
        void nextTick(() => compactTrigger.value?.focus())
    }
}
function adjacentGroupIndex(index: number, direction: -1 | 1): number {
    return (index + direction + groups.length) % groups.length
}
function onTriggerKeydown(event: KeyboardEvent, groupIndex: number) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault()
        void open(groups[groupIndex], event.key === 'ArrowDown' ? 'first' : 'last')
        return
    }
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault()
        const nextIndex = adjacentGroupIndex(groupIndex, event.key === 'ArrowLeft' ? -1 : 1)
        triggerRefs[nextIndex]?.focus()
        if (openGroup.value) void open(groups[nextIndex])
        return
    }
    if (event.key === 'Escape' && openGroup.value) {
        event.preventDefault()
        close()
        triggerRefs[groupIndex]?.focus()
    }
}
function focusEnabledItem(group: IdeCommandGroup, itemIndex: number, direction: -1 | 1) {
    const indexes = enabledItemIndexes(group)
    const current = indexes.indexOf(itemIndex)
    const next = current < 0 ? 0 : (current + direction + indexes.length) % indexes.length
    itemRefs[indexes[next]]?.focus()
}
function onItemKeydown(event: KeyboardEvent, groupIndex: number, itemIndex: number) {
    const group = groups[groupIndex]
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault()
        focusEnabledItem(group, itemIndex, event.key === 'ArrowDown' ? 1 : -1)
        return
    }
    if (event.key === 'Home' || event.key === 'End') {
        event.preventDefault()
        const indexes = enabledItemIndexes(group)
        itemRefs[event.key === 'Home' ? indexes[0] : indexes.at(-1)!]?.focus()
        return
    }
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault()
        const nextIndex = adjacentGroupIndex(groupIndex, event.key === 'ArrowLeft' ? -1 : 1)
        triggerRefs[nextIndex]?.focus()
        void open(groups[nextIndex], 'first')
        return
    }
    if (event.key === 'Escape') {
        event.preventDefault()
        close()
        void nextTick(() => triggerRefs[groupIndex]?.focus())
    }
}
function choose(commandId: string) {
    if (!props.enabled(commandId)) return
    close()
    emit('command', commandId)
}
function onDocumentPointerDown(event: PointerEvent) {
    if (root.value && !root.value.contains(event.target as Node)) close()
}
onMounted(() => document.addEventListener('pointerdown', onDocumentPointerDown))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onDocumentPointerDown))
</script>

<style scoped>
.app-menu-bar { display: flex; align-items: center; gap: 1px; }
.app-menu-compact-trigger { display: none; height: 26px; align-items: center; gap: 5px; padding: 0 7px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-secondary); font: inherit; font-size: var(--app-font-xs); cursor: pointer; }
.app-menu-compact-trigger:hover, .app-menu-compact-trigger[aria-expanded="true"] { background: var(--app-bg-hover); color: var(--app-text-primary); }
.app-menu-root { position: relative; }
.app-menu-trigger { height: 26px; padding: 0 7px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-secondary); font: inherit; font-size: var(--app-font-xs); cursor: pointer; }
.app-menu-trigger:hover, .app-menu-trigger[aria-expanded="true"] { background: var(--app-bg-hover); color: var(--app-text-primary); }
.app-menu-popover { position: absolute; z-index: 2300; top: 29px; left: 0; width: 244px; padding: 5px; border: 1px solid var(--app-overlay-border); border-radius: var(--app-radius-md); background: var(--app-bg-overlay); box-shadow: var(--app-shadow-lg); }
.app-menu-popover button { width: 100%; min-height: var(--app-control-compact); display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 0 8px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-regular); font: inherit; font-size: var(--app-font-xs); text-align: left; cursor: pointer; }
.app-menu-popover button:hover:not(:disabled), .app-menu-popover button:focus-visible { outline: 0; background: var(--app-bg-hover); color: var(--app-text-primary); }
.app-menu-popover button:disabled { color: var(--app-text-placeholder); cursor: default; }
.app-menu-popover kbd { color: var(--app-text-placeholder); font: inherit; font-size: var(--app-font-caption); white-space: nowrap; }
.app-menu-compact-popover { position: absolute; z-index: 2300; top: 32px; left: 0; width: min(280px, calc(100vw - 20px)); max-height: calc(100vh - 52px); overflow: auto; padding: 5px; border: 1px solid var(--app-overlay-border); border-radius: var(--app-radius-md); background: var(--app-bg-overlay); box-shadow: var(--app-shadow-lg); }
.app-menu-section-label { padding: 8px 8px 4px; color: var(--app-text-placeholder); font-size: var(--app-font-caption); font-weight: 600; }
.app-menu-compact-popover button { width: 100%; min-height: var(--app-control-compact); display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 0 8px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-regular); font: inherit; font-size: var(--app-font-xs); text-align: left; cursor: pointer; }
.app-menu-compact-popover button:hover:not(:disabled), .app-menu-compact-popover button:focus-visible { outline: 0; background: var(--app-bg-hover); color: var(--app-text-primary); }
.app-menu-compact-popover button:disabled { color: var(--app-text-placeholder); cursor: default; }
.app-menu-compact-popover kbd { color: var(--app-text-placeholder); font: inherit; font-size: var(--app-font-caption); white-space: nowrap; }
@media (max-width: 820px) {
    .app-menu-bar { position: relative; }
    .app-menu-root { display: none; }
    .app-menu-compact-trigger { display: inline-flex; }
}
</style>
