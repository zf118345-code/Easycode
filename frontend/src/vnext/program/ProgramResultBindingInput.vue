<template>
    <div ref="root" class="result-binding-input" @focusout="handleFocusOut">
        <input
            ref="input"
            v-model="draft"
            type="text"
            role="combobox"
            aria-label="保存结果为"
            :aria-expanded="showSuggestions"
            :aria-controls="`${statementId}-result-bindings`"
            :disabled="disabled"
            placeholder="留空不保存；输入名称新建；输入 @ 选择已有变量"
            autocomplete="off"
            spellcheck="false"
            @focus="focused = true"
            @input="handleInput"
            @keydown.enter.prevent="commitDraft"
            @keydown.down.prevent="focusFirstSuggestion"
            @keydown.esc.prevent="resetDraft"
        />
        <section
            v-if="showSuggestions"
            :id="`${statementId}-result-bindings`"
            class="result-binding-suggestions"
            aria-label="可保存结果的已有局部变量"
        >
            <header><strong>使用已有局部变量</strong><span>{{ filteredLocals.length }} 项</span></header>
            <button
                v-for="item in filteredLocals"
                :key="item.id"
                type="button"
                @mousedown.prevent="selectExisting(item)"
                @click="selectExisting(item)"
                @keydown="handleSuggestionKeydown"
            >
                <span>局部</span>
                <strong>{{ item.display_name }}</strong>
                <small>{{ programTypeDisplayName(item.value_type) }}</small>
            </button>
            <p v-if="!filteredLocals.length">当前步骤之前没有类型兼容的局部变量。</p>
        </section>
        <p v-if="error" class="result-binding-error" role="alert">{{ error }}</p>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { programTypeDisplayName } from './typePresentation'
import type { AvailableProgramValue, ProgramCommand, ProgramResultBinding } from './types'

type ResultBindingTarget = Extract<ProgramCommand, { kind: 'set_result_binding' }>['target']

const props = withDefaults(defineProps<{
    statementId: string
    binding?: ProgramResultBinding | null
    compatibleLocals?: AvailableProgramValue[]
    disabled?: boolean
}>(), { binding: null, compatibleLocals: () => [], disabled: false })

const emit = defineEmits<{ commit: [target: ResultBindingTarget] }>()
const root = ref<HTMLElement | null>(null)
const input = ref<HTMLInputElement | null>(null)
const draft = ref('')
const focused = ref(false)
const error = ref('')

function bindingText(binding: ProgramResultBinding | null | undefined): string {
    if (!binding) return ''
    return binding.declare ? binding.display_name : `[局部 · ${binding.display_name}]`
}

const suggestionQuery = computed(() => {
    const value = draft.value.trim()
    if (value.startsWith('@')) return value.slice(1).trim().toLocaleLowerCase('zh-CN')
    if (value.startsWith('[')) return value.slice(1).replace(/^局部\s*[·.]?\s*/u, '').replace(/\]$/u, '').trim().toLocaleLowerCase('zh-CN')
    return ''
})
const hasReferenceTrigger = computed(() => /^\s*(?:@|\[)/u.test(draft.value))
const filteredLocals = computed(() => props.compatibleLocals.filter((item) => (
    !suggestionQuery.value
    || `${item.display_name} ${programTypeDisplayName(item.value_type)}`.toLocaleLowerCase('zh-CN').includes(suggestionQuery.value)
)))
const showSuggestions = computed(() => focused.value && hasReferenceTrigger.value)

watch(() => props.binding, (binding) => {
    if (!focused.value) draft.value = bindingText(binding)
}, { deep: true, immediate: true })

function handleInput(): void { error.value = '' }

function selectExisting(item: AvailableProgramValue): void {
    draft.value = `[局部 · ${item.display_name}]`
    error.value = ''
    emit('commit', { kind: 'existing_local', symbol_id: item.id, display_name: item.display_name, value_type: item.value_type })
    focused.value = false
}

function referencedLocal(value: string): AvailableProgramValue | undefined {
    const normalized = value.trim().replace(/^@/u, '').replace(/^\[/u, '').replace(/\]$/u, '').replace(/^局部\s*[·.]?\s*/u, '').trim()
    return props.compatibleLocals.find((item) => item.display_name === normalized)
}

function commitDraft(): void {
    const value = draft.value.trim()
    if (!value) {
        error.value = ''
        emit('commit', null)
        focused.value = false
        return
    }
    if (hasReferenceTrigger.value) {
        const existing = referencedLocal(value)
        if (!existing) {
            error.value = '请从列表选择一个已有局部变量，或去掉 @ 后输入新变量名称。'
            return
        }
        selectExisting(existing)
        return
    }
    error.value = ''
    emit('commit', { kind: 'new_local', display_name: value })
    focused.value = false
}

function resetDraft(): void {
    draft.value = bindingText(props.binding)
    error.value = ''
    focused.value = false
    input.value?.blur()
}

function suggestionButtons(): HTMLButtonElement[] {
    return [...(root.value?.querySelectorAll<HTMLButtonElement>('.result-binding-suggestions button') || [])]
}

function focusFirstSuggestion(): void {
    if (!showSuggestions.value) return
    void nextTick(() => suggestionButtons()[0]?.focus())
}

function handleSuggestionKeydown(event: KeyboardEvent): void {
    const buttons = suggestionButtons()
    const index = buttons.indexOf(event.currentTarget as HTMLButtonElement)
    if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && buttons.length) {
        event.preventDefault()
        const direction = event.key === 'ArrowDown' ? 1 : -1
        buttons[(index + direction + buttons.length) % buttons.length]?.focus()
    } else if (event.key === 'Escape') {
        event.preventDefault()
        input.value?.focus()
    }
}

async function handleFocusOut(): Promise<void> {
    if (!focused.value) return
    await nextTick()
    if (root.value?.contains(document.activeElement)) return
    focused.value = false
    if (!error.value) commitDraft()
}
</script>

<style scoped>
.result-binding-input { position: relative; min-width: 0; }
.result-binding-input > input { width: 100%; min-height: var(--app-control-default); padding: 0 var(--app-spacing-sm); border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); outline: 0; background: var(--app-bg-input); color: var(--app-text-primary); font: inherit; }
.result-binding-input > input:hover { border-color: var(--app-border-strong); }
.result-binding-input > input:focus-visible { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.result-binding-input > input::placeholder { color: var(--app-text-placeholder); }
.result-binding-suggestions { position: absolute; z-index: 12; inset: calc(100% + 6px) 0 auto; max-height: 250px; overflow: auto; padding: 6px; border: 1px solid var(--app-overlay-border); border-radius: var(--app-radius-md); background: var(--app-overlay-bg); box-shadow: var(--app-shadow-lg); }
.result-binding-suggestions header { display: flex; align-items: center; justify-content: space-between; padding: 5px 7px 7px; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.result-binding-suggestions header span { color: var(--app-text-placeholder); }
.result-binding-suggestions button { width: 100%; min-height: var(--app-control-default); display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 4px 7px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-regular); text-align: left; cursor: pointer; }
.result-binding-suggestions button:hover, .result-binding-suggestions button:focus-visible { outline: 0; background: var(--app-bg-hover); box-shadow: none; }
.result-binding-suggestions button > span { padding: 2px 5px; background: rgba(92, 131, 199, .13); color: #c8d9f6; font-size: var(--app-font-caption); }
.result-binding-suggestions button strong { overflow: hidden; font-size: var(--app-font-xs); font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.result-binding-suggestions button small { color: var(--app-text-placeholder); font-size: var(--app-font-caption); }
.result-binding-suggestions > p, .result-binding-error { margin: 6px 0 0; font-size: var(--app-font-xs); line-height: 1.5; }
.result-binding-suggestions > p { padding: 5px 7px; color: var(--app-text-placeholder); }
.result-binding-error { color: var(--app-color-danger); }
</style>
