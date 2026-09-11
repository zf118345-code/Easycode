<template>
    <div class="reference-picker" :class="{ 'is-open': open }" @keydown.esc.stop.prevent="close">
        <button
            type="button"
            class="reference-trigger"
            :disabled="disabled || !values.length"
            aria-haspopup="listbox"
            :aria-expanded="open"
            @click="toggle"
        >
            <span v-if="current" class="source-badge" :class="`source-${current.source}`">{{ sourceLabel(current.source) }}</span>
            <span class="reference-name">{{ current?.display_name || emptyLabel }}</span>
            <small v-if="current">{{ programTypeDisplayName(current.value_type) }}</small>
            <ChevronDown :size="14" aria-hidden="true" />
        </button>

        <section v-if="open" class="reference-panel" aria-label="选择已有值">
            <label class="search-field">
                <Search :size="14" aria-hidden="true" />
                <input
                    ref="searchInput"
                    v-model="query"
                    type="search"
                    placeholder="搜索名称或类型"
                    aria-label="搜索局部变量或项目变量"
                />
            </label>
            <div class="reference-options" role="listbox">
                <template v-for="group in groups" :key="group.source">
                    <div v-if="group.items.length" class="reference-group">
                        <strong>{{ sourceLabel(group.source) }}</strong>
                        <button
                            v-for="item in group.items"
                            :key="`${item.source}:${item.id}`"
                            type="button"
                            role="option"
                            :aria-selected="keyOf(item) === currentKey"
                            @click="select(item)"
                        >
                            <span>{{ item.display_name }}</span>
                            <small>{{ programTypeDisplayName(item.value_type) }}</small>
                        </button>
                    </div>
                </template>
                <p v-if="!filteredValues.length" class="reference-empty">没有匹配的已有值</p>
            </div>
        </section>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { ChevronDown, Search } from 'lucide-vue-next'
import type { AvailableProgramValue } from './types'
import { programTypeDisplayName } from './typePresentation'

const props = withDefaults(defineProps<{
    values: AvailableProgramValue[]
    currentKey?: string
    disabled?: boolean
    emptyLabel?: string
}>(), { currentKey: '', disabled: false, emptyLabel: '选择已有值' })

const emit = defineEmits<{ select: [value: AvailableProgramValue] }>()
const open = ref(false)
const query = ref('')
const searchInput = ref<HTMLInputElement | null>(null)

const current = computed(() => props.values.find((item) => keyOf(item) === props.currentKey) || null)
const filteredValues = computed(() => {
    const needle = query.value.trim().toLocaleLowerCase()
    if (!needle) return props.values
    return props.values.filter((item) => `${item.display_name} ${item.value_type} ${programTypeDisplayName(item.value_type)}`.toLocaleLowerCase().includes(needle))
})
const groups = computed(() => (['local', 'project'] as const).map((source) => ({
    source,
    items: filteredValues.value.filter((item) => item.source === source),
})))

watch(() => props.currentKey, () => { open.value = false; query.value = '' })

function keyOf(value: AvailableProgramValue): string { return `${value.source}:${value.id}` }
function sourceLabel(source: AvailableProgramValue['source']): string { return source === 'local' ? '局部' : '项目' }
function close(): void { open.value = false; query.value = '' }
async function toggle(): Promise<void> {
    if (props.disabled || !props.values.length) return
    open.value = !open.value
    if (open.value) { await nextTick(); searchInput.value?.focus() }
    else query.value = ''
}
function select(value: AvailableProgramValue): void { emit('select', value); close() }
</script>

<style scoped>
.reference-picker { position: relative; min-width: 0; }
.reference-trigger { width: 100%; min-height: var(--app-control-default); display: grid; grid-template-columns: auto minmax(0, 1fr) auto auto; align-items: center; gap: var(--app-spacing-xs); padding: 0 var(--app-spacing-sm); border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); background: var(--app-bg-input); color: var(--app-text-primary); font: inherit; text-align: left; cursor: pointer; }
.reference-trigger:hover { border-color: var(--app-border-strong); }
.reference-trigger:focus-visible { outline: 0; border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.reference-trigger:disabled { cursor: not-allowed; opacity: .62; }
.reference-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.reference-trigger small { color: var(--app-text-placeholder); font-size: var(--app-font-xs); white-space: nowrap; }
.source-badge { min-width: 30px; padding: 2px 5px; border-radius: 999px; background: var(--app-bg-active); color: var(--app-text-secondary); font-size: var(--app-font-caption); text-align: center; }
.source-project { background: var(--app-color-primary-dim); color: var(--app-text-primary); }
.reference-panel { margin-top: var(--app-spacing-xs); overflow: hidden; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); background: var(--app-bg-sidebar); box-shadow: var(--app-shadow-md); }
.search-field { min-height: var(--app-control-default); display: flex; align-items: center; gap: var(--app-spacing-xs); padding: 0 var(--app-spacing-sm); border-bottom: 1px solid var(--app-border-subtle); color: var(--app-text-secondary); }
.search-field input { min-width: 0; flex: 1; border: 0; outline: 0; background: transparent; color: var(--app-text-primary); font: inherit; }
.reference-options { max-height: 240px; overflow: auto; padding: var(--app-spacing-xs); }
.reference-group > strong { display: block; padding: var(--app-spacing-xs) var(--app-spacing-sm); color: var(--app-text-placeholder); font-size: var(--app-font-caption); font-weight: 600; }
.reference-group button { width: 100%; min-height: var(--app-control-default); display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: var(--app-spacing-sm); padding: 0 var(--app-spacing-sm); border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-regular); font: inherit; text-align: left; cursor: pointer; }
.reference-group button:hover, .reference-group button[aria-selected="true"] { background: var(--app-bg-hover); color: var(--app-text-primary); }
.reference-group button span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.reference-group button small { color: var(--app-text-placeholder); font-size: var(--app-font-xs); }
.reference-empty { margin: 0; padding: var(--app-spacing-md); color: var(--app-text-secondary); font-size: var(--app-font-xs); text-align: center; }
</style>
