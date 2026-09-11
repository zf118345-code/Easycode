<template>
    <VNextControlField
        class="program-parameter"
        :class="{ 'is-disabled': disabled, 'is-inline-record': usesInlineRecord, 'is-multiline': parameter.constraints?.multiline === true }"
        :data-value-id="value.value_id"
        :label="parameter.display_name"
        :title-id="parameterTitleId"
        :help-id="parameterHelpId"
        :error-id="parameterErrorId"
        :required="parameter.required"
        :disabled="disabled"
        :stacked="shouldStackField"
        :help-available="usesUnifiedComposer || Boolean(parameter.ui?.help || parameter.description)"
        :help-text="usesUnifiedComposer ? '' : (parameter.ui?.help || parameter.description || '')"
        :help-open="expressionHelpOpen"
        :error="fieldErrors.join('；')"
        @toggle-help="expressionHelpOpen = !expressionHelpOpen"
    >
        <div v-if="usesColorControl" class="program-color-row">
            <VNextValueControl
                control-type="color"
                :label="parameter.display_name"
                :value-type="parameter.value_type"
                :model-value="controlModelValue"
                :required="parameter.required"
                :ui="parameter.ui"
                :actions="actions"
                :disabled="disabled"
                :mixed="mixed"
                :invalid="Boolean(fieldErrors.length)"
                :described-by="parameterDescribedBy"
                @update:model-value="commitFixedValue"
                @action="emitCapture"
            />
            <button type="button" class="app-field-action" :disabled="disabled" title="引用已有颜色或使用颜色操作" aria-label="引用已有颜色或使用颜色操作" @click="colorComposerOpen = true">
                <AtSign :size="14" aria-hidden="true" />
            </button>
        </div>

        <ProgramRecordInlineEditor
            v-else-if="usesInlineRecord"
            :label="parameter.display_name"
            :value="value as RecordValueNode"
            :available-values="availableValues"
            :disabled="disabled"
            :resolve-catalog="catalogResolver"
            @replace="commitExpression"
        />

        <div v-else-if="usesUnifiedComposer" class="unified-value-row" :class="{ 'has-actions': hasUnifiedActions }">
            <ProgramExpressionInput
                :label="parameter.display_name"
                :value="value"
                :expected-type="parameter.value_type"
                :available-values="availableValues"
                :disabled="disabled"
                :help-open="expressionHelpOpen"
                :placeholder="placeholder"
                :help-text="parameter.ui?.help || parameter.description"
                :effective-default-label="parameter.ui?.effective_default_label"
                :adornment="parameter.ui?.unit"
                :invalid="Boolean(fieldErrors.length)"
                :described-by="parameterDescribedBy"
                :multiline="parameter.constraints?.multiline === true"
                :resolve-catalog="catalogResolver"
                @replace="commitExpression"
                @close-help="expressionHelpOpen = false"
                @editing-change="expressionEditing = $event"
            />
            <div v-if="hasUnifiedActions" class="unified-value-actions">
                <VNextValueControl
                    v-if="actions.length"
                    actions-only
                    :control-type="control"
                    :label="parameter.display_name"
                    :value-type="parameter.value_type"
                    :model-value="controlModelValue"
                    :ui="parameter.ui"
                    :actions="actions"
                    :disabled="disabled"
                    :mixed="mixed"
                    @action="emitCapture"
                />
            </div>
        </div>

        <ProgramStructuredSummaryControl
            v-else-if="requiresStructuredEditor && draftSource === 'fixed'"
            :summary="structuredSummary"
            :empty="value.kind === 'unset'"
            :disabled="disabled || !valueEditorAvailable"
            :invalid="Boolean(fieldErrors.length)"
            :described-by="parameterDescribedBy"
            :action-label="`编辑${parameter.display_name}`"
            @edit="openComputedEditor"
        />

        <VNextValueControl
            v-else-if="draftSource === 'fixed'"
            :control-type="control"
            :label="parameter.display_name"
            :value-type="parameter.value_type"
            :model-value="controlModelValue"
            :required="parameter.required"
            :options="options"
            :constraints="parameter.constraints"
            :ui="parameter.ui"
            :assets="assets"
            :actions="actions"
            :placeholder="placeholder"
            :disabled="disabled"
            :mixed="mixed"
            :invalid="Boolean(fieldErrors.length)"
            :described-by="parameterDescribedBy"
            @update:model-value="commitFixedValue"
            @action="emitCapture"
        />

        <ProgramValueReferencePicker
            v-else-if="draftSource === 'reference'"
            :values="compatibleValues"
            :current-key="currentReferenceKey"
            :disabled="disabled"
            :empty-label="compatibleValues.length ? '选择已有值' : '当前没有类型兼容的值'"
            @select="commitReference"
        />

        <ProgramStructuredSummaryControl
            v-else
            :summary="computedSummary"
            :empty="computedSummary === '尚未配置'"
            :disabled="disabled || !valueEditorAvailable"
            :invalid="Boolean(fieldErrors.length)"
            :described-by="parameterDescribedBy"
            :action-label="`编辑${parameter.display_name}`"
            @edit="openComputedEditor"
        />

    </VNextControlField>
</template>

<script setup lang="ts">
import { computed, inject, ref, watch } from 'vue'
import { AtSign } from 'lucide-vue-next'
import VNextValueControl from '../components/VNextValueControl.vue'
import VNextControlField from '../components/ui/VNextControlField.vue'
import ProgramExpressionInput from './ProgramExpressionInput.vue'
import ProgramRecordInlineEditor from './ProgramRecordInlineEditor.vue'
import ProgramStructuredSummaryControl from './ProgramStructuredSummaryControl.vue'
import ProgramValueReferencePicker from './ProgramValueReferencePicker.vue'
import { expressionText, isInlineExpressionValueType } from './expressionComposer'
import {
    choiceOptions,
    compatibleAvailableValues,
    controlForParameter,
    referenceDraft,
    sourceForValue,
    valueDraftFromModel,
    valueModel,
} from './controlContract'
import { valueSummary } from './projection'
import { isFocusedValueEditorSupported, programValueToDraft } from './valueFactories'
import type { ProgramValueCatalogDto } from './serverTypes'
import { programValueCatalogResolverKey } from './valueCatalogContext'
import type {
    AvailableProgramValue,
    LocalSymbolDefinition,
    ProgramAsset,
    ProgramCaptureRequest,
    ProgramParameterContract,
    ProgramValueEditorRequest,
    ProgramValueNode,
    RecordValueNode,
    ProgramValueSource,
    ProgramValueUpdate,
} from './types'
import type { ExecutionPlatformId } from '../types'

const props = withDefaults(defineProps<{
    statementId: string
    parameter: ProgramParameterContract
    value: ProgramValueNode
    availableValues?: AvailableProgramValue[]
    assets?: ProgramAsset[]
    diagnostics?: string[]
    platform?: ExecutionPlatformId
    disabled?: boolean
    valueEditorAvailable?: boolean
    mixed?: boolean
    resolveCatalog?: ((expectedType: string, scopeBindings?: LocalSymbolDefinition[]) => Promise<ProgramValueCatalogDto>) | null
}>(), {
    availableValues: () => [],
    assets: () => [],
    diagnostics: () => [],
    platform: 'windows',
    disabled: false,
    valueEditorAvailable: false,
    mixed: false,
    resolveCatalog: null,
})

const emit = defineEmits<{
    update: [update: ProgramValueUpdate]
    capture: [request: ProgramCaptureRequest]
    openValueEditor: [request: ProgramValueEditorRequest]
}>()

const inheritedCatalogResolver = inject(programValueCatalogResolverKey, null)
const IDE_AUTHOR_ACTION_IDS = new Set([
    'choose-resource', 'capture-image', 'pick-point', 'pick-region', 'pick-color', 'capture-control', 'capture-path',
])
const parameterTitleId = computed(() => `parameter-${props.value.value_id.replace(/[^a-zA-Z0-9_-]/g, '-')}-title`)
const parameterHelpId = computed(() => `${parameterTitleId.value}-help`)
const parameterErrorId = computed(() => `${parameterTitleId.value}-error`)
const parameterDescribedBy = computed(() => [
    !usesUnifiedComposer.value && expressionHelpOpen.value && (props.parameter.ui?.help || props.parameter.description) ? parameterHelpId.value : '',
    fieldErrors.value.length ? parameterErrorId.value : '',
].filter(Boolean).join(' ') || undefined)
const catalogResolver = computed(() => props.resolveCatalog || (inheritedCatalogResolver
    ? (expectedType: string, scopeBindings: LocalSymbolDefinition[] = []) => inheritedCatalogResolver(props.statementId, expectedType, scopeBindings)
    : null))

const control = computed(() => controlForParameter(props.parameter))
const draftSource = ref<ProgramValueSource>(sourceForValue(props.value))
const expressionHelpOpen = ref(false)
const expressionEditing = ref(false)
const colorComposerOpen = ref(false)
const modelValue = computed(() => draftSource.value === sourceForValue(props.value) ? valueModel(props.value) : null)
const controlModelValue = computed(() => {
    if (props.value.kind === 'entity_ref') return {
        reference_id: props.value.reference_id,
        display_name: props.value.display_name || props.value.reference_id,
        reference_type: props.value.reference_type,
    }
    if (props.value.kind === 'target_ref' && control.value === 'select') return props.value.target_id
    if (props.value.kind === 'target_ref') return {
        reference_id: props.value.target_id,
        display_name: props.value.display_name || props.value.target_id,
        reference_type: props.value.value_type,
    }
    return modelValue.value
})
const options = computed(() => choiceOptions(props.parameter, props.platform, modelValue.value))
const hasEnumeratedChoices = computed(() => /^(?:optional<)?enum</.test(props.parameter.value_type) || options.value.length > 0)
const compatibleValues = computed(() => compatibleAvailableValues(props.availableValues, props.parameter.value_type))
const actions = computed(() => (props.parameter.ui?.actions || []).filter((action) => {
    if (!IDE_AUTHOR_ACTION_IDS.has(action.id)) return false
    if (props.platform === 'no_target') return false
    return !action.platforms?.length || action.platforms.includes(props.platform)
}))
const currentReferenceKey = computed(() => {
    if (props.value.kind === 'symbol_ref') return `local:${props.value.symbol_id}`
    if (props.value.kind === 'project_variable_ref') return `project:${props.value.variable_id}`
    return ''
})
const computedSummary = computed(() => {
    if (props.value.kind === 'computed') return props.value.summary || expressionText(props.value)
    if (props.value.kind === 'selector') return props.value.summary || '逐项处理'
    return '尚未配置'
})
const editorStrategy = computed(() => props.parameter.ui?.editor_strategy)
const usesInlineRecord = computed(() => editorStrategy.value === 'inline_record' && props.value.kind === 'record')
const usesColorControl = computed(() => control.value === 'color'
    && !colorComposerOpen.value
    && ['unset', 'literal', 'record'].includes(props.value.kind))
// Only controls whose own width is deliberately compact stay beside the label.
// Every other value keeps the full inspector width so labels, values and actions
// never compete for the same narrow row.
const shouldStackField = computed(() => (
    control.value !== 'toggle'
    || usesInlineRecord.value
    || usesColorControl.value
    || props.parameter.constraints?.multiline === true
))
const requiresStructuredEditor = computed(() => (
    ['focused', 'row_list'].includes(editorStrategy.value || '')
    || (!editorStrategy.value && !isInlineExpressionValueType(props.parameter.value_type) && (
        (control.value !== 'control-selector' && isFocusedValueEditorSupported(props.value, props.parameter.value_type))
        || (props.value.kind === 'unset' && props.valueEditorAvailable && control.value === 'expression')
    ))
))
const isAuthorReferenceControl = computed(() => [
    'file', 'directory', 'control-reference', 'instance', 'target', 'application', 'instance-multi-select',
].includes(control.value))
const usesUnifiedComposer = computed(() => control.value !== 'resource' && !usesColorControl.value && !usesInlineRecord.value && !requiresStructuredEditor.value && !hasEnumeratedChoices.value && (
    editorStrategy.value === 'reference'
    || (editorStrategy.value === 'inline_record' && props.value.kind !== 'record')
    || isAuthorReferenceControl.value
    || isInlineExpressionValueType(props.parameter.value_type)
))
const hasUnifiedActions = computed(() => actions.value.length > 0)
const structuredSummary = computed(() => valueSummary(props.value))
const placeholder = computed(() => {
    if (props.mixed) return '多个值，输入后应用到全部'
    if (props.parameter.ui?.placeholder) return props.parameter.ui.placeholder
    if (props.value.kind === 'unset') return props.parameter.required
        ? `填写${props.parameter.display_name}`
        : `可填写${props.parameter.display_name}`
    return `填写${props.parameter.display_name}`
})
const visibleErrors = computed(() => {
    const errors = [...props.diagnostics]
    if (props.parameter.required && props.value.kind === 'unset') errors.unshift('请完成必填项')
    return [...new Set(errors)]
})
const fieldErrors = computed(() => usesUnifiedComposer.value && expressionEditing.value ? [] : visibleErrors.value)

watch(() => [props.value.value_id, props.value.kind] as const, () => {
    draftSource.value = sourceForValue(props.value)
    if (!['unset', 'literal', 'record'].includes(props.value.kind)) colorComposerOpen.value = true
})

function emitUpdate(next: ProgramValueUpdate['next']): void {
    emit('update', {
        statement_id: props.statementId,
        parameter_id: props.parameter.parameter_id,
        value_id: props.value.value_id,
        next,
    })
}

function commitFixedValue(nextValue: unknown): void {
    emitUpdate(valueDraftFromModel(props.parameter, control.value, nextValue))
}

function commitReference(selected: AvailableProgramValue): void {
    emitUpdate(referenceDraft(selected, props.parameter.value_type))
}

function commitExpression(next: ProgramValueNode): void {
    emitUpdate(programValueToDraft(next))
    colorComposerOpen.value = false
}

function emitCapture(action: ProgramCaptureRequest['action']): void {
    emit('capture', {
        statement_id: props.statementId,
        parameter_id: props.parameter.parameter_id,
        value_id: props.value.value_id,
        action,
    })
}

function openComputedEditor(): void {
    if (!props.valueEditorAvailable) return
    emit('openValueEditor', {
        statement_id: props.statementId,
        parameter_id: props.parameter.parameter_id,
        value_id: props.value.value_id,
        ...(draftSource.value === 'computed'
            && sourceForValue(props.value) !== 'computed'
            ? { preferred_source: 'computed' as const }
            : {}),
    })
}

</script>

<style scoped>
.program-parameter {
    min-width: 0;
    margin: 0;
    padding: 0;
    border: 0;
}

.program-parameter + .program-parameter { margin-top: var(--app-form-field-gap); }

.unified-value-row { min-width: 0; }
.unified-value-row.has-actions { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: start; gap: var(--app-spacing-xs); }
.unified-value-actions { display: flex; align-items: flex-start; gap: var(--app-spacing-xs); }
.program-color-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: start; gap: var(--app-spacing-xs); }

</style>
