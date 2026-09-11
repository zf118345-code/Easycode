<template>
    <div class="inline-record" role="group" :aria-label="label" :aria-busy="loading || undefined">
        <template v-if="visiblePrimaryFields.length">
            <div v-for="field in visiblePrimaryFields" :key="field.field_id" class="record-field" :class="{ 'is-compact': isCompactField(field) }" :data-record-field-id="field.field_id">
                <div class="record-field-heading">
                    <span :title="field.display_name">{{ field.display_name }}<b v-if="field.required" aria-label="必填">*</b></span>
                    <span v-if="field.description" class="sr-only" :id="fieldHelpId(field.field_id)">{{ field.description }}</span>
                </div>
                <VNextValueControl
                    v-if="usesDirectControl(field)"
                    :control-type="fieldControl(field)"
                    :label="field.display_name"
                    :value-type="field.value_type"
                    :model-value="fieldModel(field)"
                    :required="Boolean(field.required)"
                    :constraints="field.constraints || {}"
                    :options="field.choices || []"
                    :ui="fieldUi(field)"
                    :placeholder="field.ui?.placeholder || ''"
                    :disabled="disabled"
                    :described-by="field.description ? fieldHelpId(field.field_id) : ''"
                    @update:model-value="replaceDirectField(field, $event)"
                />
                <ProgramExpressionInput
                    v-else
                    :label="field.display_name"
                    :value="fieldValue(field)"
                    :expected-type="field.value_type"
                    :available-values="availableValues"
                    :disabled="disabled"
                    :placeholder="field.ui?.placeholder || contextualPlaceholder(field)"
                    :help-text="field.ui?.help || field.description"
                    :effective-default-label="field.ui?.effective_default_label || effectiveDefault(field)"
                    :described-by="field.description ? fieldHelpId(field.field_id) : ''"
                    :resolve-catalog="resolveCatalog"
                    @replace="replaceField(field.field_id, $event)"
                />
            </div>
        </template>

        <details v-if="visibleAdvancedFields.length" class="record-advanced">
            <summary>更多条件</summary>
            <div v-for="field in visibleAdvancedFields" :key="field.field_id" class="record-field" :class="{ 'is-compact': isCompactField(field) }" :data-record-field-id="field.field_id">
                <div class="record-field-heading">
                    <span :title="field.display_name">{{ field.display_name }}<b v-if="field.required" aria-label="必填">*</b></span>
                    <span v-if="field.description" class="sr-only" :id="fieldHelpId(field.field_id)">{{ field.description }}</span>
                </div>
                <VNextValueControl
                    v-if="usesDirectControl(field)"
                    :control-type="fieldControl(field)"
                    :label="field.display_name"
                    :value-type="field.value_type"
                    :model-value="fieldModel(field)"
                    :required="Boolean(field.required)"
                    :constraints="field.constraints || {}"
                    :options="field.choices || []"
                    :ui="fieldUi(field)"
                    :placeholder="field.ui?.placeholder || ''"
                    :disabled="disabled"
                    :described-by="field.description ? fieldHelpId(field.field_id) : ''"
                    @update:model-value="replaceDirectField(field, $event)"
                />
                <ProgramExpressionInput
                    v-else
                    :label="field.display_name"
                    :value="fieldValue(field)"
                    :expected-type="field.value_type"
                    :available-values="availableValues"
                    :disabled="disabled"
                    :placeholder="field.ui?.placeholder || contextualPlaceholder(field)"
                    :help-text="field.ui?.help || field.description"
                    :effective-default-label="field.ui?.effective_default_label || effectiveDefault(field)"
                    :described-by="field.description ? fieldHelpId(field.field_id) : ''"
                    :resolve-catalog="resolveCatalog"
                    @replace="replaceField(field.field_id, $event)"
                />
            </div>
        </details>

        <div v-if="!visibleFields.length && loading" class="record-state" role="status">正在读取字段…</div>
        <div v-else-if="!visibleFields.length" class="record-state is-error" role="alert">
            <span>字段定义暂不可用，已保留原值。</span>
            <button v-if="resolveCatalog" type="button" class="app-inline-action" :disabled="disabled" @click="loadCatalog">重试</button>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import VNextValueControl from '../components/VNextValueControl.vue'
import ProgramExpressionInput from './ProgramExpressionInput.vue'
import { valueModel } from './controlContract'
import type { ProgramValueCatalogDto } from './serverTypes'
import type { ParameterControlType, ParameterUiContract } from '../types'
import type { AvailableProgramValue, LocalSymbolDefinition, ProgramValueNode, RecordValueNode } from './types'

type RecordSchema = NonNullable<ProgramValueCatalogDto['record']>
type RecordField = RecordSchema['fields'][number]

const props = withDefaults(defineProps<{
    label: string
    value: RecordValueNode
    availableValues?: AvailableProgramValue[]
    disabled?: boolean
    resolveCatalog?: ((expectedType: string, scopeBindings?: LocalSymbolDefinition[]) => Promise<ProgramValueCatalogDto>) | null
}>(), {
    availableValues: () => [],
    disabled: false,
    resolveCatalog: null,
})

const emit = defineEmits<{ replace: [value: RecordValueNode] }>()
const schema = ref<RecordSchema | null>(null)
const loading = ref(false)
let loadRevision = 0

function normalizedType(valueType: string): string {
    let value = valueType.trim()
    while (value.startsWith('optional<') && value.endsWith('>')) value = value.slice(9, -1).trim()
    return value
}

function fallbackFields(): RecordField[] {
    return Object.entries(props.value.fields).flatMap(([fieldId, child]) => {
        const displayName = props.value.field_names?.[fieldId]
        if (!displayName) return []
        return [{ field_id: fieldId, display_name: displayName, value_type: child.value_type, description: '', choices: [] }]
    })
}

const fields = computed(() => schema.value?.fields?.length ? schema.value.fields : fallbackFields())

function ruleValue(fieldId: string): unknown {
    const child = props.value.fields[fieldId]
    return child ? valueModel(child) : undefined
}

function fieldIsVisible(field: RecordField): boolean {
    const rule = field.ui?.visible_when
    if (!rule) return true
    const dependencyId = rule.field_id || rule.parameter_id
    if (!dependencyId) return true
    const actual = ruleValue(dependencyId)
    if (rule.operator === 'not_equals') return actual !== rule.value
    if (rule.operator === 'greater_than') return typeof actual === 'number' && actual > Number(rule.value)
    if (rule.operator === 'truthy') return Boolean(actual)
    return actual === rule.value
}

const visibleFields = computed(() => fields.value.filter(fieldIsVisible))
const visiblePrimaryFields = computed(() => visibleFields.value.filter((field) => field.ui?.importance !== 'advanced'))
const visibleAdvancedFields = computed(() => visibleFields.value.filter((field) => field.ui?.importance === 'advanced'))

async function loadCatalog(): Promise<void> {
    const resolver = props.resolveCatalog
    if (!resolver) return
    const revision = ++loadRevision
    loading.value = true
    try {
        const catalog = await resolver(props.value.record_type || props.value.value_type)
        if (revision !== loadRevision) return
        schema.value = catalog.record
    } catch {
        if (revision === loadRevision) schema.value = null
    } finally {
        if (revision === loadRevision) loading.value = false
    }
}

watch(() => [props.value.record_type, props.resolveCatalog] as const, () => { void loadCatalog() }, { immediate: true })

function fieldValue(field: RecordField): ProgramValueNode {
    const current = props.value.fields[field.field_id]
    if (current) return current
    const valueId = `${props.value.value_id}.${field.field_id}`
    if (field.has_default) return { value_id: valueId, kind: 'literal', value_type: field.value_type, value: field.default as never }
    return { value_id: valueId, kind: 'unset', value_type: field.value_type }
}

function fieldModel(field: RecordField): unknown { return valueModel(fieldValue(field)) }

function fieldControl(field: RecordField): ParameterControlType {
    if (field.ui?.control) return field.ui.control
    const type = normalizedType(field.value_type)
    if (type === 'bool') return 'toggle'
    if (type.startsWith('enum<') || field.choices?.length) return 'select'
    if (type === 'int64' || type === 'float64' || type === 'percentage') return 'number'
    if (['date', 'datetime', 'time'].includes(type)) return 'time'
    return 'expression'
}

function fieldUi(field: RecordField): ParameterUiContract {
    return { control: fieldControl(field), ...(field.ui || {}) }
}

function usesDirectControl(field: RecordField): boolean {
    return ['toggle', 'select', 'slider-number'].includes(fieldControl(field))
}

function isCompactField(field: RecordField): boolean {
    return fieldControl(field) === 'toggle'
}

function replaceField(fieldId: string, child: ProgramValueNode): void {
    emit('replace', { ...props.value, fields: { ...props.value.fields, [fieldId]: child } })
}

function replaceDirectField(field: RecordField, nextValue: unknown): void {
    const current = fieldValue(field)
    replaceField(field.field_id, {
        value_id: current.value_id,
        kind: 'literal',
        value_type: field.value_type,
        value: nextValue as never,
    })
}

function contextualPlaceholder(field: RecordField): string {
    if (normalizedType(field.value_type) === 'int64') return `填写${field.display_name}`
    return field.required ? `填写${field.display_name}` : `可填写${field.display_name}`
}

function effectiveDefault(field: RecordField): string {
    if (!field.has_default) return ''
    if (typeof field.default === 'boolean') return field.default ? '开启' : '关闭'
    return field.default == null ? '留空' : String(field.default)
}

function fieldHelpId(fieldId: string): string {
    return `${props.value.value_id}-${fieldId.replace(/[^a-zA-Z0-9_-]/g, '-')}-help`
}
</script>

<style scoped>
.inline-record { container-type: inline-size; min-width: 0; }
.record-field { min-width: 0; display: grid; grid-template-columns: minmax(0, 1fr); align-items: start; row-gap: var(--app-form-label-control-gap); }
.record-field.is-compact { grid-template-columns: minmax(76px, 96px) minmax(0, 1fr); align-items: center; column-gap: var(--app-spacing-sm); row-gap: 0; }
.record-field + .record-field { margin-top: var(--app-spacing-sm); }
.record-field-heading { min-width: 0; min-height: 18px; display: flex; align-items: center; color: var(--app-text-regular); font-size: var(--app-font-xs); font-weight: 500; }
.record-field.is-compact .record-field-heading { min-height: var(--app-control-default); }
.record-field-heading > span:first-child { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.record-field-heading b { margin-inline-start: 3px; color: var(--app-color-danger); font-weight: 600; }
.record-advanced { margin-top: var(--app-form-field-gap); border-top: 1px solid var(--app-border-subtle); }
.record-advanced > summary { min-height: var(--app-form-disclosure-height); display: flex; align-items: center; color: var(--app-text-secondary); font-size: var(--app-font-compact); cursor: pointer; }
.record-advanced[open] > summary { margin-bottom: var(--app-form-heading-field-gap); }
.record-state { min-height: var(--app-control-default); display: flex; align-items: center; justify-content: space-between; gap: var(--app-spacing-sm); color: var(--app-text-placeholder); font-size: var(--app-font-xs); }
.record-state.is-error { color: var(--app-color-danger); }

@container (max-width: 220px) {
    .record-field.is-compact { grid-template-columns: minmax(0, 1fr); row-gap: var(--app-form-label-control-gap); }
    .record-field.is-compact .record-field-heading { min-height: 18px; }
}
</style>
