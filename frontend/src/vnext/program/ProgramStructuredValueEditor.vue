<template>
    <div class="structured-editor-backdrop" @mousedown.self="requestCancel">
        <section
            ref="dialogElement"
            class="structured-dialog"
            :class="`is-${resolvedSize}`"
            :data-editor-size="resolvedSize"
            role="dialog"
            aria-modal="true"
            aria-labelledby="program-value-editor-title"
            :aria-describedby="editorHelp ? 'program-value-editor-help' : undefined"
            :aria-hidden="discardPrompt ? 'true' : undefined"
            :inert="discardPrompt"
            tabindex="-1"
            @keydown="trapDialogFocus"
            @keydown.esc="requestCancel"
        >
            <header>
                <div><h2 id="program-value-editor-title">{{ title }}</h2><p v-if="editorHelp" id="program-value-editor-help">{{ editorHelp }}</p></div>
                <button type="button" aria-label="关闭" :disabled="busy" @click="requestCancel"><X :size="15" aria-hidden="true" /></button>
            </header>
            <form ref="formElement" @submit.prevent="save">
                <div class="editor-scroll">
                    <ProgramValueTreeField
                        :label="allowConditionBuilder ? '条件' : title"
                        :value="draft"
                        :available-values="availableValues"
                        :condition-builder="allowConditionBuilder"
                        :initial-catalog-mode="initialSource === 'computed' ? 'computed' : ''"
                        :hide-source-picker="!allowConditionBuilder"
                        :resolve-catalog="catalogResolver"
                        root
                        @replace="draft = $event"
                    />
                </div>
                <p v-if="error" class="form-error" role="alert">{{ error }}</p>
                <footer>
                    <button type="button" class="secondary" :disabled="busy" @click="requestCancel">取消</button>
                    <button type="submit" class="primary" :disabled="busy">{{ busy ? '正在保存' : '保存内容' }}</button>
                </footer>
            </form>
        </section>

        <section
            v-if="discardPrompt"
            ref="discardDialogElement"
            class="discard-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="discard-value-title"
            aria-describedby="discard-value-description"
            tabindex="-1"
            @keydown="trapDialogFocus"
            @keydown.esc.stop="closeDiscardPrompt"
        >
            <h2 id="discard-value-title">放弃未保存修改？</h2>
            <p id="discard-value-description">尚未保存的内容会丢失。</p>
            <footer><button type="button" data-dialog-initial-focus @click="closeDiscardPrompt">继续编辑</button><button type="button" class="danger" @click="discardChanges">放弃修改</button></footer>
        </section>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { X } from 'lucide-vue-next'
import { trapDialogFocus } from '../dialogFocus'
import type { WorkspaceIdentity } from '../types'
import { programApi } from './api'
import ProgramValueTreeField from './ProgramValueTreeField.vue'
import { canMaterializeProgramValue, cloneProgramValue, defaultProgramValue } from './valueFactories'
import type { ProgramValueCatalogDto } from './serverTypes'
import type { AvailableProgramValue, LocalSymbolDefinition, ProgramValueNode } from './types'

const props = withDefaults(defineProps<{
    title: string
    value: ProgramValueNode
    availableValues?: AvailableProgramValue[]
    busy?: boolean
    allowConditionBuilder?: boolean
    initialSource?: 'computed'
    constraints?: Record<string, unknown>
    workspace?: WorkspaceIdentity | null
    functionId?: string
    statementId?: string
    baseRevision?: string
    size?: 'auto' | 'compact' | 'default' | 'wide'
}>(), {
    availableValues: () => [], busy: false, allowConditionBuilder: false, initialSource: undefined, constraints: () => ({}),
    workspace: null, functionId: '', statementId: '', baseRevision: '', size: 'auto',
})
const emit = defineEmits<{ save: [value: ProgramValueNode]; cancel: [] }>()
const initial = cloneProgramValue(
    props.value.kind === 'unset' && canMaterializeProgramValue(props.value.value_type)
        ? defaultProgramValue(props.value.value_type, props.value.value_id)
        : props.value,
)
const draft = shallowRef<ProgramValueNode>(initial)
const initialFingerprint = JSON.stringify(initial)
const formElement = ref<HTMLFormElement | null>(null)
const dialogElement = ref<HTMLElement | null>(null)
const discardDialogElement = ref<HTMLElement | null>(null)
const error = ref('')
const discardPrompt = ref(false)
const returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
let focusBeforeDiscard: HTMLElement | null = null
const dirty = computed(() => JSON.stringify(draft.value) !== initialFingerprint)
const editorHelp = computed(() => props.allowConditionBuilder
    ? '输入判断，或用 @ 引用已有值。'
    : ['list', 'map', 'json'].includes(draft.value.kind)
        ? '按项填写，也可以改用已有值或计算结果。'
        : '')
const resolvedSize = computed<'compact' | 'default' | 'wide'>(() => {
    if (props.size !== 'auto') return props.size
    const shape = valueShape(draft.value)
    if (shape.collectionSize > 8 || shape.nodes > 16 || shape.depth > 3) return 'wide'
    if (draft.value.kind === 'record' && shape.nodes <= 7 && shape.depth <= 2) return 'compact'
    if (['literal', 'symbol_ref', 'project_variable_ref', 'member_access'].includes(draft.value.kind)) return 'compact'
    return 'default'
})
const catalogCache = new Map<string, ProgramValueCatalogDto>()
const catalogResolver = props.workspace && props.functionId && props.statementId && props.baseRevision
    ? resolveCatalog : null

async function resolveCatalog(expectedType: string, scopeBindings: LocalSymbolDefinition[] = []): Promise<ProgramValueCatalogDto> {
    const cacheKey = JSON.stringify([expectedType, scopeBindings.map((item) => [item.symbol_id, item.value_type])])
    const cached = catalogCache.get(cacheKey)
    if (cached) return cached
    if (!props.workspace || !props.functionId || !props.statementId) throw new Error('当前值没有可用的作用域目录。')
    const value = await programApi.getValueCatalog(props.workspace, props.functionId, props.statementId, expectedType, scopeBindings)
    if (value.revision !== props.baseRevision) throw new Error('项目函数已变化，请关闭后重新打开此编辑器。')
    catalogCache.set(cacheKey, value)
    return value
}

function requestCancel(): void {
    if (props.busy) return
    if (dirty.value) {
        focusBeforeDiscard = document.activeElement instanceof HTMLElement ? document.activeElement : null
        discardPrompt.value = true
        return
    }
    emit('cancel')
}
function closeDiscardPrompt(): void {
    discardPrompt.value = false
}
function discardChanges(): void {
    discardPrompt.value = false
    emit('cancel')
}
function save(): void {
    error.value = ''
    if (!formElement.value?.checkValidity()) {
        formElement.value?.reportValidity()
        error.value = '请先修复标出的结构化值'
        return
    }
    const structuralError = validateStructure(draft.value, true)
    if (structuralError) { error.value = structuralError; return }
    emit('save', cloneProgramValue(draft.value))
}

function canonicalLiteral(value: ProgramValueNode): string | null {
    if (value.kind !== 'literal' && value.kind !== 'json') return null
    return JSON.stringify(value.kind === 'literal' ? value.value : value.payload)
}
function finiteConstraint(name: string): number | null {
    const value = props.constraints[name]
    return typeof value === 'number' && Number.isFinite(value) ? value : null
}
function validateStructure(value: ProgramValueNode, root = false): string {
    if (value.kind === 'condition_group' && !value.conditions.length) return '条件组至少需要一个条件'
    if (root && (value.kind === 'list' || value.kind === 'map')) {
        const count = value.kind === 'list' ? value.items.length : value.entries.length
        const minItems = finiteConstraint('min_items')
        const maxItems = finiteConstraint('max_items')
        if (minItems !== null && count < minItems) return `至少需要 ${minItems} 项`
        if (maxItems !== null && count > maxItems) return `最多允许 ${maxItems} 项`
        if (value.kind === 'list' && props.constraints.unique_items === true) {
            const fixedItems = value.items.map(canonicalLiteral).filter((item): item is string => item !== null)
            if (new Set(fixedItems).size !== fixedItems.length) return '列表中存在重复的固定值'
        }
    }
    if (value.kind === 'map') {
        const fixedKeys = value.entries.map((entry) => canonicalLiteral(entry.key)).filter((item): item is string => item !== null)
        if (new Set(fixedKeys).size !== fixedKeys.length) return '字典中存在重复的固定键'
    }
    const children: ProgramValueNode[] = value.kind === 'list' ? value.items
        : value.kind === 'map' ? value.entries.flatMap((entry) => [entry.key, entry.value])
            : value.kind === 'record' ? Object.values(value.fields)
                : value.kind === 'computed' ? Object.values(value.inputs)
                    : value.kind === 'selector' ? [value.expression]
                    : value.kind === 'member_access' ? [value.source]
                        : value.kind === 'compare' ? [value.left, value.right]
                            : value.kind === 'condition_group' ? value.conditions
                                : value.kind === 'not' ? [value.condition] : []
    for (const child of children) {
        const childError = validateStructure(child)
        if (childError) return childError
    }
    return ''
}

function valueShape(value: ProgramValueNode, depth = 1): { nodes: number; depth: number; collectionSize: number } {
    const children: ProgramValueNode[] = value.kind === 'list' ? value.items
        : value.kind === 'map' ? value.entries.flatMap((entry) => [entry.key, entry.value])
            : value.kind === 'record' ? Object.values(value.fields)
                : value.kind === 'computed' ? Object.values(value.inputs)
                    : value.kind === 'selector' ? [value.expression]
                        : value.kind === 'member_access' ? [value.source]
                            : value.kind === 'compare' ? [value.left, value.right]
                                : value.kind === 'condition_group' ? value.conditions
                                    : value.kind === 'not' ? [value.condition] : []
    const collectionSize = value.kind === 'list' ? value.items.length
        : value.kind === 'map' ? value.entries.length
            : value.kind === 'record' ? Object.keys(value.fields).length
                : value.kind === 'json' && value.payload && typeof value.payload === 'object'
                    ? Object.keys(value.payload).length : 0
    return children.reduce((shape, child) => {
        const childShape = valueShape(child, depth + 1)
        return {
            nodes: shape.nodes + childShape.nodes,
            depth: Math.max(shape.depth, childShape.depth),
            collectionSize: Math.max(shape.collectionSize, childShape.collectionSize),
        }
    }, { nodes: 1, depth, collectionSize })
}

function focusFirst(dialog: HTMLElement | null): void {
    if (!dialog) return
    const initial = dialog.querySelector<HTMLElement>('[data-dialog-initial-focus]')
        || dialog.querySelector<HTMLElement>('.expression-surface:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])')
        || dialog.querySelector<HTMLElement>('button:not([disabled])')
        || dialog
    initial.focus()
}

onMounted(async () => {
    await nextTick()
    focusFirst(dialogElement.value)
})
watch(discardPrompt, async (open) => {
    await nextTick()
    if (open) focusFirst(discardDialogElement.value)
    else if (focusBeforeDiscard?.isConnected) focusBeforeDiscard.focus()
    else focusFirst(dialogElement.value)
})
onBeforeUnmount(() => {
    if (returnFocus?.isConnected) returnFocus.focus()
})
</script>

<style scoped>
.structured-editor-backdrop { position: fixed; inset: 0; z-index: 2400; display: grid; place-items: center; padding: 24px; background: rgb(0 0 0 / 58%); }
.structured-dialog { width: min(var(--structured-editor-width), 100%); max-height: min(780px, calc(100dvh - 48px)); display: flex; flex-direction: column; overflow: hidden; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-lg); background: var(--app-bg-panel); box-shadow: var(--app-shadow-lg); }
.structured-dialog.is-compact { --structured-editor-width: 440px; }
.structured-dialog.is-default { --structured-editor-width: 560px; }
.structured-dialog.is-wide { --structured-editor-width: 720px; }
.structured-dialog > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 16px 18px; border-bottom: 1px solid var(--app-border-subtle); }
.structured-dialog h2, .discard-dialog h2 { margin: 0; color: var(--app-text-primary); font-size: var(--app-font-md); }
.structured-dialog header p, .discard-dialog p { margin: 4px 0 0; color: var(--app-text-secondary); font-size: var(--app-font-xs); line-height: 1.55; }
.structured-dialog header button { width: 28px; height: var(--app-control-compact); border: 0; background: transparent; color: var(--app-text-secondary); cursor: pointer; }
.structured-dialog form { min-height: 0; display: flex; flex: 1; flex-direction: column; }
.editor-scroll { overflow: auto; padding: 16px 18px; }
.structured-dialog footer, .discard-dialog footer { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 18px; border-top: 1px solid var(--app-border-subtle); }
.structured-dialog footer button, .discard-dialog footer button { min-height: var(--app-control-default); padding: 0 14px; border-radius: var(--app-radius-sm); font: inherit; cursor: pointer; }
.secondary, .discard-dialog button { border: 1px solid var(--app-border-default); background: var(--app-bg-input); color: var(--app-text-regular); }
.primary { border: 1px solid var(--app-color-primary); background: var(--app-color-primary); color: var(--app-color-on-primary); }
.danger { border-color: var(--app-color-danger) !important; background: var(--app-color-danger) !important; color: var(--app-color-on-primary) !important; }
.form-error { margin: 0; padding: 0 18px 10px; color: var(--app-color-danger); font-size: var(--app-font-xs); }
.discard-dialog { position: absolute; z-index: 1; width: min(420px, calc(100% - 32px)); padding-top: 16px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-lg); background: var(--app-bg-panel); box-shadow: var(--app-shadow-lg); }
.discard-dialog > h2, .discard-dialog > p { padding-inline: 18px; }
@media (max-width: 620px) { .structured-editor-backdrop { padding: 0; } .structured-dialog { box-sizing: border-box; width: 100vw; max-width: none; max-height: 100dvh; border-inline: 0; border-radius: 0; } }
</style>
