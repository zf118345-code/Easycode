<template>
    <section class="json-value-field" :data-json-kind="kind">
        <header :class="{ 'atomic-header': atomic && !pendingKind }">
            <label>
                <span class="sr-only">JSON 值类型</span>
                <select :value="kind" @change="changeKind">
                    <option value="object">对象</option>
                    <option value="array">列表</option>
                    <option value="string">文本</option>
                    <option value="number">数值</option>
                    <option value="boolean">开关</option>
                    <option value="null">空值</option>
                </select>
            </label>
            <input v-if="!pendingKind && kind === 'string'" :value="modelValue" type="text" aria-label="文本值" @input="updateString" />
            <input v-else-if="!pendingKind && kind === 'number'" :value="modelValue" type="number" step="any" aria-label="数值" @change="updateNumber" />
            <label v-else-if="!pendingKind && kind === 'boolean'" class="boolean-field">
                <input :checked="Boolean(modelValue)" type="checkbox" @change="updateBoolean" />
                <span>{{ modelValue ? '开启' : '关闭' }}</span>
            </label>
            <p v-else-if="!pendingKind && kind === 'null'" class="null-note">明确为空</p>
            <small v-else>{{ summary }}</small>
        </header>

        <div v-if="pendingKind" class="kind-change-confirm" role="alert">
            <span>切换类型会清空当前内容。</span>
            <div><button type="button" class="app-inline-action" @click="pendingKind = ''">保留当前内容</button><button type="button" class="app-inline-action danger-inline-action" @click="confirmKindChange">仍要切换</button></div>
        </div>

        <div v-if="!pendingKind && kind === 'array'" class="json-children">
            <section v-for="(item, index) in visibleArrayValue" :key="index" class="json-child">
                <div class="child-heading"><strong>第 {{ index + 1 }} 项</strong><button type="button" class="app-inline-action danger-inline-action" @click="removeArrayItem(index)"><Trash2 :size="13" aria-hidden="true" /><span>删除</span></button></div>
                <ProgramJsonValueField :model-value="item" :depth="depth + 1" @update:model-value="replaceArrayItem(index, $event)" />
            </section>
            <div class="json-actions"><button type="button" class="app-inline-action add-button" @click="addArrayItem"><Plus :size="13" aria-hidden="true" /><span>添加一项</span></button><button v-if="remainingItems" type="button" class="app-inline-action" @click="visibleLimit += JSON_PAGE_SIZE"><span>再显示 {{ Math.min(JSON_PAGE_SIZE, remainingItems) }} 项</span></button></div>
        </div>

        <div v-else-if="!pendingKind && kind === 'object'" class="json-children">
            <section v-for="entry in visibleObjectEntries" :key="entry.key" class="json-child">
                <div class="child-heading">
                    <input :value="entry.key" type="text" aria-label="字段名称" placeholder="字段名称" @change="renameObjectKey(entry.key, $event)" />
                    <button type="button" class="app-inline-action danger-inline-action" @click="removeObjectEntry(entry.key)"><Trash2 :size="13" aria-hidden="true" /><span>删除</span></button>
                </div>
                <ProgramJsonValueField :model-value="entry.value" :depth="depth + 1" @update:model-value="replaceObjectValue(entry.key, $event)" />
            </section>
            <div class="json-actions"><button type="button" class="app-inline-action add-button" @click="addObjectEntry"><Plus :size="13" aria-hidden="true" /><span>添加字段</span></button><button v-if="remainingItems" type="button" class="app-inline-action" @click="visibleLimit += JSON_PAGE_SIZE"><span>再显示 {{ Math.min(JSON_PAGE_SIZE, remainingItems) }} 项</span></button></div>
        </div>
    </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Plus, Trash2 } from 'lucide-vue-next'
import type { ProgramLiteral } from './types'

defineOptions({ name: 'ProgramJsonValueField' })
const props = withDefaults(defineProps<{ modelValue: ProgramLiteral; depth?: number }>(), { depth: 0 })
const emit = defineEmits<{ 'update:modelValue': [value: ProgramLiteral] }>()

type JsonKind = 'object' | 'array' | 'string' | 'number' | 'boolean' | 'null'
const kind = computed<JsonKind>(() => {
    if (props.modelValue === null) return 'null'
    if (Array.isArray(props.modelValue)) return 'array'
    if (typeof props.modelValue === 'object') return 'object'
    if (typeof props.modelValue === 'number') return 'number'
    if (typeof props.modelValue === 'boolean') return 'boolean'
    return 'string'
})
const atomic = computed(() => ['string', 'number', 'boolean', 'null'].includes(kind.value))
const arrayValue = computed(() => Array.isArray(props.modelValue) ? props.modelValue : [])
const objectValue = computed<Record<string, ProgramLiteral>>(() => (
    props.modelValue && typeof props.modelValue === 'object' && !Array.isArray(props.modelValue)
        ? props.modelValue : {}
))
const objectEntries = computed(() => Object.entries(objectValue.value).map(([key, value]) => ({ key, value })))
const JSON_PAGE_SIZE = 40
const visibleLimit = ref(JSON_PAGE_SIZE)
const pendingKind = ref<JsonKind | ''>('')
const visibleArrayValue = computed(() => arrayValue.value.slice(0, visibleLimit.value))
const visibleObjectEntries = computed(() => objectEntries.value.slice(0, visibleLimit.value))
const remainingItems = computed(() => Math.max(0, (kind.value === 'array' ? arrayValue.value.length : objectEntries.value.length) - visibleLimit.value))
const summary = computed(() => kind.value === 'array' ? `${arrayValue.value.length} 项`
    : kind.value === 'object' ? `${objectEntries.value.length} 个字段` : '')

function changeKind(event: Event): void {
    const next = (event.target as HTMLSelectElement).value as JsonKind
    ;(event.target as HTMLSelectElement).value = kind.value
    if (next === kind.value) return
    if (hasContent(props.modelValue)) {
        pendingKind.value = next
        return
    }
    applyKind(next)
}
function applyKind(next: JsonKind): void {
    const defaults: Record<JsonKind, ProgramLiteral> = {
        object: {},
        array: [],
        string: '',
        number: 0,
        boolean: false,
        null: null,
    }
    emit('update:modelValue', defaults[next])
}
function confirmKindChange(): void {
    if (!pendingKind.value) return
    const next = pendingKind.value
    pendingKind.value = ''
    applyKind(next)
}
function hasContent(value: ProgramLiteral): boolean {
    if (value === null || value === '') return false
    if (Array.isArray(value)) return value.length > 0
    if (typeof value === 'object') return Object.keys(value).length > 0
    return true
}
function updateString(event: Event): void { emit('update:modelValue', (event.target as HTMLInputElement).value) }
function updateNumber(event: Event): void {
    const input = event.target as HTMLInputElement
    if (input.value === '') {
        input.value = String(props.modelValue)
        return
    }
    const next = Number(input.value)
    if (Number.isFinite(next)) emit('update:modelValue', next)
    else input.value = String(props.modelValue)
}
function updateBoolean(event: Event): void { emit('update:modelValue', (event.target as HTMLInputElement).checked) }
function replaceArrayItem(index: number, value: ProgramLiteral): void {
    const next = [...arrayValue.value]; next[index] = value; emit('update:modelValue', next)
}
function addArrayItem(): void { emit('update:modelValue', [...arrayValue.value, '']) }
function removeArrayItem(index: number): void { emit('update:modelValue', arrayValue.value.filter((_, current) => current !== index)) }
function replaceObjectValue(key: string, value: ProgramLiteral): void { emit('update:modelValue', { ...objectValue.value, [key]: value }) }
function removeObjectEntry(key: string): void {
    emit('update:modelValue', Object.fromEntries(Object.entries(objectValue.value).filter(([name]) => name !== key)))
}
function addObjectEntry(): void {
    let index = objectEntries.value.length + 1
    let key = `字段${index}`
    while (Object.hasOwn(objectValue.value, key)) { index += 1; key = `字段${index}` }
    emit('update:modelValue', { ...objectValue.value, [key]: '' })
}
function renameObjectKey(previous: string, event: Event): void {
    const input = event.target as HTMLInputElement
    const next = input.value.trim()
    if (!next || next === previous || Object.hasOwn(objectValue.value, next)) {
        input.value = previous
        return
    }
    emit('update:modelValue', Object.fromEntries(Object.entries(objectValue.value).map(([key, value]) => [key === previous ? next : key, value])))
}
watch(kind, () => {
    visibleLimit.value = JSON_PAGE_SIZE
})
</script>

<style scoped>
.json-value-field { min-width: 0; display: flex; flex-direction: column; gap: 8px; container-type: inline-size; }
.json-value-field > header, .child-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.json-value-field > header.atomic-header { display: grid; grid-template-columns: minmax(88px, auto) minmax(0, 1fr); align-items: center; }
.json-value-field small, .null-note { margin: 0; color: var(--app-text-placeholder); font-size: var(--app-font-xs); }
select, input[type='text'], input[type='number'] { min-width: 0; min-height: var(--app-control-default); border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); outline: 0; background: var(--app-bg-base); color: var(--app-text-primary); font: inherit; }
select { padding-inline: 8px; }
input[type='text'], input[type='number'] { width: 100%; padding-inline: 9px; }
select:focus-visible, input:focus-visible, button:focus-visible { border-color: var(--app-color-primary); outline: 0; box-shadow: var(--focus-ring); }
.boolean-field { display: flex; align-items: center; gap: 8px; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.json-children { display: flex; flex-direction: column; gap: 8px; }
.json-child { min-width: 0; padding: 0 0 var(--app-spacing-md); border-bottom: 1px solid var(--app-border-subtle); }
.json-child:last-of-type { padding-bottom: 0; border-bottom: 0; }
.child-heading { margin-bottom: 8px; }
.child-heading strong { color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.danger-inline-action:hover:not(:disabled) { color: var(--app-color-danger); }
.add-button { align-self: flex-start; }
.json-actions, .kind-change-confirm > div { display: flex; align-items: center; flex-wrap: wrap; gap: var(--app-spacing-xs); }
.kind-change-confirm { display: flex; flex-direction: column; gap: var(--app-spacing-xs); padding: var(--app-spacing-sm); border: 1px solid var(--app-color-warning); border-radius: var(--app-radius-sm); color: var(--app-text-regular); font-size: var(--app-font-xs); }
@container (max-width: 320px) { .json-value-field > header.atomic-header { grid-template-columns: minmax(0, 1fr); } }
</style>
