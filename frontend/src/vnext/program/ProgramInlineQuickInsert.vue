<template>
    <div class="quick-insert" :style="{ '--quick-insert-depth': depth }" @click.stop>
        <div class="quick-insert__field" :class="{ 'has-error': error }">
            <Search :size="14" aria-hidden="true" />
            <input
                ref="inputElement"
                v-model="query"
                type="search"
                role="combobox"
                aria-label="快速插入函数"
                aria-autocomplete="list"
                :aria-controls="listboxId"
                :aria-expanded="true"
                :aria-activedescendant="activeCandidate ? optionId(activeCandidate.key) : undefined"
                :placeholder="placeholder"
                autocomplete="off"
                spellcheck="false"
                @compositionstart="composing = true"
                @compositionend="composing = false"
                @keydown="onInputKeydown"
            />
            <span v-if="pending || busy" class="quick-insert__status">{{ pending ? '正在插入' : '正在保存' }}</span>
            <kbd v-else>Esc</kbd>
        </div>

        <div :id="listboxId" class="quick-insert__results" role="listbox" aria-label="可插入的函数">
            <p v-if="error" class="quick-insert__message is-error" role="alert">{{ error }}</p>
            <template v-if="results.length">
                <button
                    v-for="(candidate, index) in results"
                    :id="optionId(candidate.key)"
                    :key="candidate.key"
                    type="button"
                    role="option"
                    class="quick-insert__option"
                    :class="{ 'is-active': index === activeIndex }"
                    :aria-selected="index === activeIndex"
                    :aria-disabled="candidate.disabledReason ? 'true' : undefined"
                    :disabled="pending"
                    :title="candidate.disabledReason || candidate.description"
                    @mouseenter="activeIndex = index"
                    @mousedown.prevent
                    @click="commit(candidate)"
                >
                    <span class="quick-insert__label" :aria-label="candidate.label">
                        <span
                            v-for="(part, partIndex) in candidate.parts"
                            :key="`${partIndex}:${part.text}`"
                            :class="{ 'quick-insert__value': part.dynamic }"
                        >{{ part.text }}</span>
                    </span>
                    <span class="quick-insert__meta">{{ candidate.namespace }} · {{ candidate.sourceLabel }}</span>
                    <span v-if="candidate.disabledReason" class="quick-insert__reason">{{ candidate.disabledReason }}</span>
                </button>
            </template>
            <div v-else class="quick-insert__empty">
                <span>{{ query.trim() ? `没有找到“${query.trim()}”` : '当前没有可插入的函数' }}</span>
                <button type="button" @mousedown.prevent @click="openLibrary">在完整函数库中搜索</button>
            </div>
            <footer v-if="results.length">
                <span><kbd>↑</kbd><kbd>↓</kbd> 选择</span>
                <span><kbd>Enter</kbd> 插入</span>
            </footer>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { Search } from 'lucide-vue-next'
import type { FunctionCatalogCandidate } from './functionCatalogSearch'
import { searchFunctionCatalog } from './functionCatalogSearch'
import type { FunctionLibrarySelection } from './functionLibraryTypes'

let quickInsertSequence = 0

const props = withDefaults(defineProps<{
    candidates: FunctionCatalogCandidate[]
    depth?: number
    recentKeys?: string[]
    busy?: boolean
    placeholder?: string
    insert: (selection: FunctionLibrarySelection) => Promise<void>
}>(), {
    depth: 1,
    recentKeys: () => [],
    busy: false,
    placeholder: '搜索要执行的操作，例如“控件、文字、等待”',
})

const emit = defineEmits<{
    cancel: []
    complete: [selection: FunctionLibrarySelection]
    requestLibrary: [query: string]
}>()

const query = ref('')
const activeIndex = ref(0)
const composing = ref(false)
const pending = ref(false)
const error = ref('')
const inputElement = ref<HTMLInputElement | null>(null)
const instanceId = `quick-insert-${++quickInsertSequence}`
const listboxId = `${instanceId}-listbox`
const results = computed(() => searchFunctionCatalog(props.candidates, query.value, {
    limit: 10,
    recentKeys: props.recentKeys,
}))
const activeCandidate = computed(() => results.value[activeIndex.value] || null)

watch(results, (next) => {
    if (!next.length) activeIndex.value = 0
    else if (activeIndex.value >= next.length || next[activeIndex.value]?.disabledReason) {
        activeIndex.value = Math.max(0, next.findIndex((candidate) => !candidate.disabledReason))
    }
}, { immediate: true })

onMounted(() => void nextTick(() => inputElement.value?.focus()))

function optionId(key: string): string {
    return `${instanceId}-${key.replace(/[^a-zA-Z0-9_-]/g, '-')}`
}

function moveActive(direction: 1 | -1): void {
    if (!results.value.length) return
    let index = activeIndex.value
    for (let attempts = 0; attempts < results.value.length; attempts += 1) {
        index = (index + direction + results.value.length) % results.value.length
        if (!results.value[index]?.disabledReason) {
            activeIndex.value = index
            document.getElementById(optionId(results.value[index]!.key))?.scrollIntoView({ block: 'nearest' })
            return
        }
    }
}

function onInputKeydown(event: KeyboardEvent): void {
    if (composing.value || event.isComposing) return
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault()
        moveActive(event.key === 'ArrowDown' ? 1 : -1)
        return
    }
    if (event.key === 'Enter') {
        event.preventDefault()
        if (activeCandidate.value) void commit(activeCandidate.value)
        return
    }
    if (event.key === 'Escape') {
        event.preventDefault()
        emit('cancel')
    }
}

async function commit(candidate: FunctionCatalogCandidate): Promise<void> {
    if (pending.value) return
    if (props.busy) {
        error.value = '正在完成上一项操作，请稍候'
        return
    }
    if (candidate.disabledReason) {
        error.value = candidate.disabledReason
        return
    }
    pending.value = true
    error.value = ''
    try {
        await props.insert(candidate.selection)
        emit('complete', candidate.selection)
    } catch (reason) {
        error.value = reason instanceof Error ? reason.message : '插入失败，请重试'
        await nextTick()
        inputElement.value?.focus()
    } finally {
        pending.value = false
    }
}

function openLibrary(): void {
    emit('requestLibrary', query.value.trim())
}
</script>

<style scoped>
.quick-insert {
    position: relative;
    z-index: 12;
    height: var(--app-control-default);
    padding-inline: calc(var(--app-spacing-sm) + (var(--quick-insert-depth) - 1) * var(--app-spacing-md) + var(--app-control-compact)) var(--app-spacing-sm);
}

.quick-insert__field {
    display: flex;
    min-width: 0;
    height: var(--app-control-default);
    align-items: center;
    gap: var(--app-spacing-sm);
    padding-inline: var(--app-spacing-sm);
    border: 1px solid var(--app-color-primary);
    border-radius: var(--app-radius-sm);
    background: var(--app-bg-input);
    color: var(--app-text-secondary);
    box-shadow: var(--focus-ring);
}

.quick-insert__field.has-error { border-color: var(--app-color-danger); }
.quick-insert__field input { min-width: 0; height: 100%; flex: 1; padding: 0; border: 0; outline: 0; background: transparent; color: var(--app-text-primary); font: inherit; }
.quick-insert__field input::placeholder { color: var(--app-text-placeholder); }
.quick-insert__field > kbd,
.quick-insert__status { flex: none; color: var(--app-text-placeholder); font: inherit; font-size: var(--app-font-caption); }

.quick-insert__results {
    position: absolute;
    z-index: 30;
    top: calc(100% + var(--app-spacing-xs));
    right: var(--app-spacing-sm);
    left: calc(var(--app-spacing-sm) + (var(--quick-insert-depth) - 1) * var(--app-spacing-md) + var(--app-control-compact));
    max-height: min(340px, calc(100vh - 170px));
    padding: var(--app-spacing-xs);
    overflow: auto;
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-md);
    background: var(--app-bg-raised);
    box-shadow: var(--app-shadow-lg);
}

.quick-insert__option {
    position: relative;
    display: grid;
    width: 100%;
    min-height: var(--app-control-default);
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--app-spacing-md);
    padding: 0 var(--app-spacing-sm);
    border: 0;
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-regular);
    font: inherit;
    text-align: start;
    cursor: pointer;
}

.quick-insert__option:hover,
.quick-insert__option.is-active { background: var(--app-bg-hover); color: var(--app-text-primary); }
.quick-insert__option[aria-disabled='true'] { color: var(--app-text-disabled); cursor: not-allowed; }
.quick-insert__label { display: inline-flex; min-width: 0; align-items: baseline; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.quick-insert__value { position: relative; display: inline-block; margin-inline: 2px; padding-inline: 6px; color: inherit; }
.quick-insert__value::before,
.quick-insert__value::after { position: absolute; width: 4px; height: 55%; border-color: var(--app-text-placeholder); content: ''; pointer-events: none; }
.quick-insert__value::before { inset-block-start: 2px; inset-inline-start: 0; border-block-start: 1px solid; border-inline-start: 1px solid; }
.quick-insert__value::after { inset-inline-end: 0; inset-block-end: 2px; border-inline-end: 1px solid; border-block-end: 1px solid; }
.quick-insert__meta { color: var(--app-text-placeholder); white-space: nowrap; }
.quick-insert__reason { grid-column: 1 / -1; margin-top: -5px; padding-bottom: 5px; color: var(--app-text-placeholder); font-size: var(--app-font-caption); }

.quick-insert__message,
.quick-insert__empty { margin: 0; padding: var(--app-spacing-sm); color: var(--app-text-secondary); }
.quick-insert__message.is-error { color: var(--app-color-danger); }
.quick-insert__empty { display: flex; align-items: center; justify-content: space-between; gap: var(--app-spacing-md); }
.quick-insert__empty button { flex: none; padding: 0; border: 0; background: transparent; color: var(--app-text-secondary); font: inherit; cursor: pointer; }
.quick-insert__empty button:hover,
.quick-insert__empty button:focus-visible { color: var(--app-text-primary); outline: 0; text-decoration: underline; text-underline-offset: 3px; }

.quick-insert__results footer { display: flex; justify-content: flex-end; gap: var(--app-spacing-lg); padding: var(--app-spacing-xs) var(--app-spacing-sm) 2px; border-top: 1px solid var(--app-border-subtle); color: var(--app-text-placeholder); font-size: var(--app-font-caption); }
.quick-insert__results footer span { display: inline-flex; align-items: center; gap: 3px; }
.quick-insert__results kbd { font: inherit; }

@media (max-width: 620px) {
    .quick-insert,
    .quick-insert__results { padding-inline-start: var(--app-spacing-sm); }
    .quick-insert__results { left: var(--app-spacing-sm); }
    .quick-insert__meta { display: none; }
}
</style>
