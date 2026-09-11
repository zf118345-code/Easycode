<template>
    <section class="value-tree-field" :class="{ 'is-root': root, 'is-inline-leaf': inlineLeaf }" :data-value-id="value.value_id" :data-value-kind="value.kind">
        <header v-if="showsFieldHeader">
            <div><strong :title="label">{{ label }}<b v-if="required && ui" aria-label="必填">*</b></strong><small v-if="!inlineLeaf">{{ kindLabel }}</small><button v-if="showsUnifiedComposer || showsWholeValueComposer || ui?.help || description" type="button" class="expression-help-trigger" :aria-label="`${label}的填写帮助`" :aria-expanded="expressionHelpOpen" :aria-controls="!showsUnifiedComposer && (ui?.help || description) ? fieldHelpId : undefined" @click="expressionHelpOpen = !expressionHelpOpen"><CircleHelp :size="13" aria-hidden="true" /></button></div>
        </header>

        <div v-if="showsWholeValueComposer" class="value-mode-bar">
            <span>{{ wholeValueMode ? '使用已有值或计算' : collectionSummary }}</span>
            <button type="button" class="app-inline-action" @click="wholeValueMode = !wholeValueMode">
                <PencilLine :size="13" aria-hidden="true" />
                <span>{{ wholeValueMode ? '按项填写' : '使用已有值或计算' }}</span>
            </button>
        </div>

        <ProgramExpressionInput
            v-if="showsUnifiedComposer"
            :label="label"
            :value="value"
            :expected-type="value.value_type"
            :available-values="availableValues"
            :resolve-catalog="resolveCatalog"
            :help-open="expressionHelpOpen"
            :placeholder="ui?.placeholder"
            :help-text="ui?.help || description"
            :effective-default-label="ui?.effective_default_label"
            :adornment="ui?.unit"
            @replace="replace"
            @close-help="expressionHelpOpen = false"
        />

        <ProgramExpressionInput
            v-else-if="showsWholeValueComposer && wholeValueMode"
            class="whole-value-composer"
            :label="`${label}整体`"
            :value="value"
            :expected-type="value.value_type"
            :available-values="availableValues"
            :resolve-catalog="resolveCatalog"
            :help-open="expressionHelpOpen"
            @replace="replaceWholeValue"
            @close-help="expressionHelpOpen = false"
        />

        <div v-if="catalogMode" class="catalog-picker" aria-live="polite">
            <div class="catalog-heading">
                <strong>{{ catalogMode === 'computed' ? `选择${expectedTypeLabel}的处理方式` : catalogMode === 'member' ? '选择对象字段' : '填写结构化内容' }}</strong>
                <button type="button" class="app-inline-action" @click="catalogMode = ''"><X :size="13" aria-hidden="true" /><span>取消</span></button>
            </div>
            <p v-if="catalogLoading">正在读取当前作用域可用项…</p>
            <div v-else-if="catalogError" class="catalog-error" role="alert">
                <span>{{ catalogError }}</span><button type="button" class="app-inline-action" @click="loadCatalog"><RotateCcw :size="13" aria-hidden="true" /><span>重试</span></button>
            </div>
            <template v-else>
                <p v-if="catalogMode === 'computed'" class="catalog-intro">只显示能得到{{ expectedTypeLabel }}的操作；选择后，它的输入仍使用统一输入器。</p>
                <label v-if="catalogMode !== 'record'">
                    <span>{{ catalogMode === 'computed' ? '处理方式' : '字段' }}</span>
                    <select v-model="selectedCandidateId">
                        <option value="" disabled>请选择</option>
                        <template v-if="catalogMode === 'computed'">
                            <optgroup v-for="group in operationGroups" :key="group.category" :label="group.category">
                                <option v-for="item in group.items" :key="item.candidate_id" :value="`operation:${item.candidate_id}`">{{ item.display_name }}{{ operationTypeSuffix(item) }}</option>
                            </optgroup>
                            <optgroup v-if="catalog?.members.length" label="读取已有值的字段">
                                <option v-for="item in catalog.members" :key="item.candidate_id" :value="`member:${item.candidate_id}`">{{ memberCandidateLabel(item) }}</option>
                            </optgroup>
                        </template>
                        <option v-for="item in catalog?.members || []" v-else :key="item.candidate_id" :value="item.candidate_id">{{ memberCandidateLabel(item) }}</option>
                    </select>
                </label>
                <p v-if="catalogMode === 'record' && !catalog?.record" class="empty-note">此类型没有可填写的字段定义。</p>
                <p v-else-if="catalogMode === 'record' && !canConstructCatalogRecord" class="empty-note">此类型只能通过{{ catalog?.record?.authoring_mode === 'capture_only' ? '宿主捕获' : '已有值引用' }}获得，不能手动创建。</p>
                <p v-else-if="catalogMode !== 'record' && !activeCandidates.length" class="empty-note">当前类型与作用域中没有已闭环的可用项。</p>
                <p v-else-if="selectedCandidateDescription" class="candidate-description">{{ selectedCandidateDescription }}</p>
                <button v-if="catalogMode === 'record' ? canConstructCatalogRecord : Boolean(activeCandidates.length)" type="button" class="app-inline-action use-candidate" :disabled="catalogMode !== 'record' && !selectedCandidateId" @click="applyCandidate"><Check :size="13" aria-hidden="true" /><span>{{ catalogMode === 'record' ? '开始填写' : '使用此项' }}</span></button>
            </template>
        </div>

        <label v-if="conditionBuilder && !catalogMode && (!showsUnifiedComposer || advancedOpen)" class="condition-kind-field">
            <span>条件表达方式</span>
            <select :value="conditionKind" :aria-label="`${label}的条件表达方式`" @change="changeConditionKind">
                <option value="single">单个布尔值</option>
                <option value="compare">比较两个值</option>
                <option value="all">全部条件满足</option>
                <option value="any">任一条件满足</option>
                <option value="not">条件取反</option>
            </select>
        </label>

        <div v-if="pendingTypeChange" class="type-change-confirm" role="alert">
            <span>{{ pendingTypeChange.kind === 'condition' ? '切换表达方式会替换当前条件。' : '切换值类型会清空左右两侧。' }}</span>
            <div><button type="button" class="app-inline-action" @click="pendingTypeChange = null">保留当前内容</button><button type="button" class="app-inline-action danger-inline-action" @click="confirmTypeChange">仍要切换</button></div>
        </div>

        <div v-if="showsLegacyEditor && !catalogMode && !wholeValueMode && depth >= 3 && !expanded" class="collapsed-value">
            <span>{{ collapsedSummary }}</span>
            <button type="button" class="app-inline-action" @click="expanded = true"><Maximize2 :size="13" aria-hidden="true" /><span>展开此层</span></button>
        </div>

        <template v-else-if="showsLegacyEditor && !catalogMode && !wholeValueMode">
        <div v-if="value.kind === 'unset' && !hasEnumeratedChoices" class="unset-value">
            <span>尚未配置</span>
            <button v-if="canMaterializeCurrent" type="button" class="app-inline-action" @click="replace(defaultProgramValue(value.value_type, value.value_id))"><PencilLine :size="13" aria-hidden="true" /><span>填写内容</span></button>
            <button v-else-if="resolveCatalog" type="button" class="app-inline-action" @click="openRecordCatalog"><Plus :size="13" aria-hidden="true" /><span>选择填写方式</span></button>
            <small v-else>请选择一个类型兼容的已有值</small>
        </div>

        <VNextValueControl
            v-else-if="value.kind === 'literal' || (value.kind === 'unset' && hasEnumeratedChoices)"
            :control-type="literalControl"
            :label="label"
            :value-type="value.value_type"
            :model-value="valueModel(value)"
            :required="required"
            :options="literalOptions"
            :constraints="constraints"
            :ui="ui"
            :placeholder="ui?.placeholder || ''"
            :described-by="!showsUnifiedComposer && expressionHelpOpen && (ui?.help || description) ? fieldHelpId : ''"
            :toggle-labels="conditionBuilder ? { trueLabel: '满足', falseLabel: '不满足' } : undefined"
            @update:model-value="replaceLiteral"
        />

        <p v-else-if="value.kind === 'symbol_ref' || value.kind === 'project_variable_ref'" class="reference-note">
            引用“{{ value.display_name }}” · {{ programTypeDisplayName(value.value_type) }}
        </p>

        <div v-else-if="value.kind === 'list'" class="children-list">
            <section v-for="(item, index) in visibleListItems" :key="item.value_id" class="list-entry">
                <ProgramValueTreeField
                    :label="`第 ${index + 1} 项`"
                    :value="item"
                    :available-values="availableValues"
                    :depth="depth + 1"
                    :resolve-catalog="resolveCatalog"
                    @replace="replaceListItem(index, $event)"
                />
                <div class="row-actions" :aria-label="`第 ${index + 1} 项操作`">
                    <button type="button" class="app-inline-action" :disabled="index === 0" @click="moveListItem(index, -1)"><ChevronUp :size="13" aria-hidden="true" /><span>上移</span></button>
                    <button type="button" class="app-inline-action" :disabled="index === value.items.length - 1" @click="moveListItem(index, 1)"><ChevronDown :size="13" aria-hidden="true" /><span>下移</span></button>
                    <button type="button" class="app-inline-action danger-inline-action" @click="removeListItem(index)"><Trash2 :size="13" aria-hidden="true" /><span>删除</span></button>
                </div>
            </section>
            <div class="collection-actions">
                <button type="button" class="app-inline-action" :disabled="!canAddListItem" @click="addListItem"><Plus :size="13" aria-hidden="true" /><span>添加一项</span></button>
                <span v-if="!canAddListItem">缺少可创建的类型结构或可引用值</span>
                <span v-else-if="!value.items.length">列表目前为空</span>
                <button v-else-if="remainingListItems" type="button" class="app-inline-action" @click="collectionLimit += COLLECTION_PAGE_SIZE"><ChevronDown :size="13" aria-hidden="true" /><span>再显示 {{ Math.min(COLLECTION_PAGE_SIZE, remainingListItems) }} 项</span></button>
            </div>
        </div>

        <div v-else-if="value.kind === 'map'" class="children-list">
            <section v-for="(entry, index) in visibleMapEntries" :key="`${entry.key.value_id}:${entry.value.value_id}`" class="map-entry">
                <header><strong>第 {{ index + 1 }} 项</strong><span><button type="button" class="app-inline-action" :disabled="index === 0" @click="moveMapEntry(index, -1)"><ChevronUp :size="13" aria-hidden="true" /><span>上移</span></button><button type="button" class="app-inline-action" :disabled="index === value.entries.length - 1" @click="moveMapEntry(index, 1)"><ChevronDown :size="13" aria-hidden="true" /><span>下移</span></button><button type="button" class="app-inline-action danger-inline-action" @click="removeMapEntry(index)"><Trash2 :size="13" aria-hidden="true" /><span>删除</span></button></span></header>
                <ProgramValueTreeField label="键" :value="entry.key" :available-values="availableValues" :depth="depth + 1" :resolve-catalog="resolveCatalog" @replace="replaceMapPart(index, 'key', $event)" />
                <ProgramValueTreeField label="值" :value="entry.value" :available-values="availableValues" :depth="depth + 1" :resolve-catalog="resolveCatalog" @replace="replaceMapPart(index, 'value', $event)" />
            </section>
            <div class="collection-actions"><button type="button" class="app-inline-action" :disabled="!canAddMapEntry" @click="addMapEntry"><Plus :size="13" aria-hidden="true" /><span>添加一项</span></button><span v-if="!canAddMapEntry">缺少可创建的键/值类型结构或可引用值</span><span v-else-if="!value.entries.length">字典目前为空</span><button v-else-if="remainingMapEntries" type="button" class="app-inline-action" @click="collectionLimit += COLLECTION_PAGE_SIZE"><ChevronDown :size="13" aria-hidden="true" /><span>再显示 {{ Math.min(COLLECTION_PAGE_SIZE, remainingMapEntries) }} 项</span></button></div>
        </div>

        <div v-else-if="value.kind === 'record'" class="record-editor">
            <p v-if="catalogLoading" class="record-state" role="status">正在读取字段…</p>
            <div v-else-if="recordMetadataError" class="record-state is-error" role="alert">
                <span>{{ recordMetadataError }}</span>
                <button v-if="resolveCatalog" type="button" class="app-inline-action" @click="loadCatalog"><RotateCcw :size="13" aria-hidden="true" /><span>重试</span></button>
            </div>
            <template v-else>
                <div class="children-list record-fields">
                    <ProgramValueTreeField
                        v-for="field in visiblePrimaryRecordFields"
                        :key="field.field_id"
                        :label="field.display_name"
                        :value="recordFieldValue(field)"
                        :available-values="availableValues"
                        :depth="depth + 1"
                        :resolve-catalog="resolveCatalog"
                        :constraints="recordFieldConstraints(field)"
                        :ui="field.ui"
                        :required="Boolean(field.required)"
                        :description="field.description"
                        @replace="replaceRecordField(field.field_id, $event)"
                    />
                </div>
                <details v-if="visibleAdvancedRecordFields.length" class="record-advanced">
                    <summary>更多条件</summary>
                    <div class="children-list record-fields">
                        <ProgramValueTreeField
                            v-for="field in visibleAdvancedRecordFields"
                            :key="field.field_id"
                            :label="field.display_name"
                            :value="recordFieldValue(field)"
                            :available-values="availableValues"
                            :depth="depth + 1"
                            :resolve-catalog="resolveCatalog"
                            :constraints="recordFieldConstraints(field)"
                            :ui="field.ui"
                            :required="Boolean(field.required)"
                            :description="field.description"
                            @replace="replaceRecordField(field.field_id, $event)"
                        />
                    </div>
                </details>
            </template>
        </div>

        <ProgramJsonValueField v-else-if="value.kind === 'json'" :model-value="value.payload" @update:model-value="updateJsonValue" />

        <div v-else-if="value.kind === 'computed'" class="complex-block">
            <div class="readonly-contract"><span>处理方式</span><strong>{{ value.operation_name }}</strong></div>
            <ProgramValueTreeField
                v-for="(input, inputId) in value.inputs"
                :key="input.value_id"
                :label="operationInputLabel(inputId)"
                :value="input"
                :available-values="availableValues"
                :depth="depth + 1"
                :resolve-catalog="resolveCatalog"
                :constraints="operationInputConstraints(inputId)"
                @replace="replaceOperationInput(inputId, $event)"
            />
        </div>

        <div v-else-if="value.kind === 'selector'" class="complex-block selector-block">
            <div class="selector-summary">
                <strong>{{ selectorTitle }}</strong>
                <span>{{ value.bindings.map((binding) => `${binding.display_name} · ${programTypeDisplayName(binding.value_type)}`).join('，') }}</span>
            </div>
            <ProgramValueTreeField
                label="逐项处理结果"
                :value="value.expression"
                :available-values="selectorAvailableValues"
                :depth="depth + 1"
                :resolve-catalog="resolveSelectorCatalog"
                :condition-builder="value.result_type === 'bool'"
                @replace="replaceSelectorExpression"
            />
        </div>

        <div v-else-if="value.kind === 'member_access'" class="complex-block">
            <div class="readonly-contract"><span>读取字段</span><strong>{{ value.field_name }}</strong></div>
            <ProgramValueTreeField label="来源" :value="value.source" :available-values="availableValues" :depth="depth + 1" :resolve-catalog="resolveCatalog" @replace="replaceMemberSource" />
        </div>

        <div v-else-if="value.kind === 'compare'" class="complex-block">
            <label class="operator-field">
                <span>比较值类型</span>
                <select :value="compareValueType" @change="replaceCompareValueType">
                    <option v-for="option in compareTypeOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select>
            </label>
            <label class="operator-field"><span>比较方式</span><select :value="value.operator" @change="replaceCompareOperator"><option value="eq">等于</option><option value="ne">不等于</option><option value="lt">小于</option><option value="lte">小于等于</option><option value="gt">大于</option><option value="gte">大于等于</option></select></label>
            <ProgramValueTreeField label="左侧" :value="value.left" :available-values="availableValues" :depth="depth + 1" :resolve-catalog="resolveCatalog" @replace="replaceCompareSide('left', $event)" />
            <ProgramValueTreeField label="右侧" :value="value.right" :available-values="availableValues" :depth="depth + 1" :resolve-catalog="resolveCatalog" @replace="replaceCompareSide('right', $event)" />
        </div>

        <div v-else-if="value.kind === 'condition_group'" class="complex-block">
            <label class="operator-field"><span>组合方式</span><select :value="value.operator" @change="replaceConditionOperator"><option value="all">全部满足</option><option value="any">任意满足</option></select></label>
            <section v-for="(condition, index) in value.conditions" :key="condition.value_id" class="condition-row">
                <ProgramValueTreeField :label="`条件 ${index + 1}`" :value="condition" :available-values="availableValues" :depth="depth + 1" :resolve-catalog="resolveCatalog" condition-builder @replace="replaceCondition(index, $event)" />
                <button type="button" class="app-inline-action danger-inline-action remove-condition" :disabled="value.conditions.length <= 1" @click="removeCondition(index)"><Trash2 :size="13" aria-hidden="true" /><span>删除条件</span></button>
            </section>
            <div class="collection-actions"><button type="button" class="app-inline-action" @click="addCondition"><Plus :size="13" aria-hidden="true" /><span>添加条件</span></button><span v-if="!value.conditions.length">至少添加一个条件</span></div>
        </div>

        <ProgramValueTreeField
            v-else-if="value.kind === 'not'"
            label="需要取反的条件"
            :value="value.condition"
            :available-values="availableValues"
            :depth="depth + 1"
            :resolve-catalog="resolveCatalog"
            condition-builder
            @replace="replaceNotCondition"
        />

        <p v-else class="readonly-value">此引用由专用 Control 维护，当前聚焦编辑器只读展示。</p>
        <p v-if="!showsUnifiedComposer && expressionHelpOpen && (ui?.help || description)" :id="fieldHelpId" class="field-help" role="note">{{ ui?.help || description }}</p>
        </template>
    </section>
</template>

<script setup lang="ts">
import { Check, ChevronDown, ChevronUp, CircleHelp, Maximize2, PencilLine, Plus, RotateCcw, Trash2, X } from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'
import VNextValueControl from '../components/VNextValueControl.vue'
import ProgramJsonValueField from './ProgramJsonValueField.vue'
import ProgramExpressionInput from './ProgramExpressionInput.vue'
import { isInlineExpressionEditable, isInlineExpressionValueType } from './expressionComposer'
import { operationSyntaxName } from './operationSyntax'
import { programTypeDisplayName } from './typePresentation'
import { choiceOptions, controlForParameter, valueDraftFromModel, valueModel } from './controlContract'
import {
    canMaterializeProgramValue,
    compatibleProgramValues,
    defaultProgramValue,
    newProgramValueId,
    referenceProgramValue,
} from './valueFactories'
import type { ProgramValueCatalogDto, PureOperationCandidateDto, RecordMemberCandidateDto } from './serverTypes'
import type { ParameterUiContract } from '../types'
import type { AvailableProgramValue, LocalSymbolDefinition, ProgramLiteral, ProgramParameterContract, ProgramValueNode } from './types'

defineOptions({ name: 'ProgramValueTreeField' })
const props = withDefaults(defineProps<{
    label: string
    value: ProgramValueNode
    availableValues?: AvailableProgramValue[]
    depth?: number
    conditionBuilder?: boolean
    hideSourcePicker?: boolean
    root?: boolean
    required?: boolean
    description?: string
    ui?: ParameterUiContract
    initialCatalogMode?: '' | 'computed' | 'member'
    resolveCatalog?: ((expectedType: string, scopeBindings?: LocalSymbolDefinition[]) => Promise<ProgramValueCatalogDto>) | null
    constraints?: ProgramParameterContract['constraints']
}>(), { availableValues: () => [], depth: 0, conditionBuilder: false, hideSourcePicker: false, root: false, required: true, description: '', ui: undefined, initialCatalogMode: '', resolveCatalog: null, constraints: () => ({}) })
const emit = defineEmits<{ replace: [value: ProgramValueNode] }>()

const parameter = computed<ProgramParameterContract>(() => ({
    parameter_id: props.value.value_id,
    display_name: props.label,
    value_type: props.value.value_type,
    required: props.required,
    allowed_sources: ['fixed'],
    constraints: props.constraints,
    ui: props.ui,
}))
const literalControl = computed(() => controlForParameter(parameter.value))
const literalOptions = computed(() => choiceOptions(parameter.value, undefined, valueModel(props.value)))
const canMaterializeCurrent = computed(() => canMaterializeProgramValue(props.value.value_type))
const canAddListItem = computed(() => props.value.kind === 'list' && canCreateChild(props.value.item_type))
const canAddMapEntry = computed(() => props.value.kind === 'map' && canCreateChild(props.value.key_type) && canCreateChild(props.value.entry_value_type))
const hasEnumeratedChoices = computed(() => /^(?:optional<)?enum</.test(props.value.value_type) || Boolean(props.constraints?.choices?.length))
const usesDirectMetadataControl = computed(() => ['toggle', 'select', 'slider-number'].includes(props.ui?.control || ''))
const showsUnifiedComposer = computed(() => !usesDirectMetadataControl.value && !hasEnumeratedChoices.value && isInlineExpressionValueType(props.value.value_type))
const showsWholeValueComposer = computed(() => !hasEnumeratedChoices.value && !showsUnifiedComposer.value && (
    ['list', 'map', 'record', 'json'].includes(props.value.kind)
    || (['computed', 'member_access', 'symbol_ref', 'project_variable_ref'].includes(props.value.kind)
        && /^(?:list<|map<|record<|json|json_value)/.test(props.value.value_type))
))
const wholeValueMode = ref(false)
const showsFieldHeader = computed(() => !props.root || showsUnifiedComposer.value || !['list', 'map', 'record', 'json'].includes(props.value.kind))
const inlineLeaf = computed(() => !props.root && (
    showsUnifiedComposer.value
    || props.value.kind === 'literal'
    || (props.value.kind === 'unset' && hasEnumeratedChoices.value)
))
const fieldHelpId = computed(() => `${props.value.value_id.replace(/[^a-zA-Z0-9_-]/g, '-')}-field-help`)
const collectionSummary = computed(() => {
    if (props.value.kind === 'list') return `${props.value.items.length} 项`
    if (props.value.kind === 'map') return `${props.value.entries.length} 项`
    if (props.value.kind === 'record') return props.root ? '按字段填写' : (props.value.record_name || '按字段填写')
    if (props.value.kind === 'json') {
        if (Array.isArray(props.value.payload)) return `${props.value.payload.length} 项`
        if (props.value.payload && typeof props.value.payload === 'object') return `${Object.keys(props.value.payload).length} 个字段`
    }
    return kindLabel.value
})
const advancedOpen = ref(false)
const expressionHelpOpen = ref(false)
const showsLegacyEditor = computed(() => !showsUnifiedComposer.value && (!showsWholeValueComposer.value
    || ['list', 'map', 'record', 'json'].includes(props.value.kind)) || advancedOpen.value)
const catalogMode = ref<'' | 'computed' | 'member' | 'record'>(props.initialCatalogMode)
const kindLabel = computed(() => ({
    unset: `待配置 · ${programTypeDisplayName(props.value.value_type)}`, literal: programTypeDisplayName(props.value.value_type), symbol_ref: '局部变量', project_variable_ref: '项目变量',
    list: '列表', map: '字典', record: '结构化对象', json: 'JSON', computed: '处理结果',
    selector: '逐项处理',
    member_access: '对象字段', compare: '比较条件', condition_group: '条件组合', not: '条件取反',
    asset_ref: '资源引用', target_ref: '目标引用', entity_ref: '实体引用',
}[props.value.kind]))
const conditionKind = computed(() => {
    if (props.value.kind === 'compare') return 'compare'
    if (props.value.kind === 'condition_group') return props.value.operator
    if (props.value.kind === 'not') return 'not'
    return 'single'
})
const compareValueType = computed(() => props.value.kind === 'compare' ? props.value.left.value_type : 'string')
const selectorTitle = computed(() => props.value.kind === 'selector'
    ? (props.value.result_type === 'bool' ? '对每一项判断条件' : '对每一项生成一个值') : '')
const selectorAvailableValues = computed<AvailableProgramValue[]>(() => {
    if (props.value.kind !== 'selector') return props.availableValues
    return [
        ...props.value.bindings.map((binding) => ({
            source: 'local' as const,
            id: binding.symbol_id,
            display_name: binding.display_name,
            value_type: binding.value_type,
        })),
        ...props.availableValues,
    ]
})
const compareTypeOptions = computed(() => {
    const base = [
        { value: 'string', label: '文本' },
        { value: 'int64', label: '整数' },
        { value: 'float64', label: '小数' },
        { value: 'bool', label: '布尔值' },
        { value: 'duration', label: '持续时间' },
    ]
    for (const item of props.availableValues) {
        if (!base.some((option) => option.value === item.value_type)) {
            base.push({ value: item.value_type, label: `${programTypeDisplayName(item.value_type)}（可引用变量）` })
        }
    }
    return base
})
const expanded = ref(props.depth < 3)
const COLLECTION_PAGE_SIZE = 40
const collectionLimit = ref(COLLECTION_PAGE_SIZE)
type PendingTypeChange = { kind: 'condition'; next: string } | { kind: 'compare'; next: string }
const pendingTypeChange = ref<PendingTypeChange | null>(null)
const visibleListItems = computed(() => props.value.kind === 'list' ? props.value.items.slice(0, collectionLimit.value) : [])
const visibleMapEntries = computed(() => props.value.kind === 'map' ? props.value.entries.slice(0, collectionLimit.value) : [])
const remainingListItems = computed(() => props.value.kind === 'list' ? Math.max(0, props.value.items.length - collectionLimit.value) : 0)
const remainingMapEntries = computed(() => props.value.kind === 'map' ? Math.max(0, props.value.entries.length - collectionLimit.value) : 0)
const collapsedSummary = computed(() => `${kindLabel.value} · ${props.value.summary || programTypeDisplayName(props.value.value_type)}`)
const catalog = ref<ProgramValueCatalogDto | null>(null)
const catalogLoading = ref(false)
const catalogError = ref('')
const selectedCandidateId = ref('')
let catalogRequest = 0
const operationGroups = computed(() => {
    const groups = new Map<string, PureOperationCandidateDto[]>()
    for (const item of catalog.value?.operations || []) {
        groups.set(item.category, [...(groups.get(item.category) || []), item])
    }
    const order = ['数值', '文本', '时间', '条件', '几何', '列表', '字典', '类型', 'JSON']
    return [...groups.entries()]
        .sort(([left], [right]) => {
            const leftRank = order.indexOf(left)
            const rightRank = order.indexOf(right)
            return (leftRank < 0 ? order.length : leftRank) - (rightRank < 0 ? order.length : rightRank)
                || left.localeCompare(right, 'zh-CN')
        })
        .map(([category, items]) => ({ category, items }))
})
const expectedTypeLabel = computed(() => programTypeDisplayName(props.value.value_type))
const activeCandidates = computed(() => catalogMode.value === 'computed'
    ? [...(catalog.value?.operations || []), ...(catalog.value?.members || [])] : catalog.value?.members || [])
const selectedCandidateDescription = computed(() => {
    if (catalogMode.value !== 'computed') return ''
    if (!selectedCandidateId.value.startsWith('operation:')) return ''
    const candidateId = selectedCandidateId.value.slice('operation:'.length)
    return catalog.value?.operations.find((item) => item.candidate_id === candidateId)?.description || ''
})
type CatalogRecord = NonNullable<ProgramValueCatalogDto['record']>
type CatalogRecordField = CatalogRecord['fields'][number]
const canConstructCatalogRecord = computed(() => Boolean(catalog.value?.record)
    && !['reference_only', 'capture_only'].includes(catalog.value?.record?.authoring_mode || 'constructible'))
const snapshotRecordFields = computed<CatalogRecordField[]>(() => {
    if (props.value.kind !== 'record') return []
    return Object.entries(props.value.fields).flatMap(([fieldId, child]) => {
        const displayName = props.value.kind === 'record' ? props.value.field_names?.[fieldId] : undefined
        if (!displayName) return []
        return [{ field_id: fieldId, display_name: displayName, value_type: child.value_type, description: '', choices: [] }]
    })
})
const catalogRecordFieldsComplete = computed(() => Boolean(catalog.value?.record?.fields?.length)
    && catalog.value!.record!.fields.every((field) => Boolean(field.display_name?.trim())))
const recordFields = computed(() => catalogRecordFieldsComplete.value ? catalog.value!.record!.fields : snapshotRecordFields.value)
const recordMetadataError = computed(() => {
    if (props.value.kind !== 'record' || catalogLoading.value) return ''
    if (catalogRecordFieldsComplete.value) return ''
    const recordValue = props.value
    const missingNames = Object.keys(recordValue.fields).filter((fieldId) => !recordValue.field_names?.[fieldId])
    const catalogMissingNames = Boolean(catalog.value?.record?.fields?.some((field) => !field.display_name?.trim()))
    if (catalogError.value || catalogMissingNames || missingNames.length || !recordFields.value.length) return '字段定义暂不可用，已保留原值。'
    return ''
})
function recordRuleValue(fieldId: string): unknown {
    if (props.value.kind !== 'record') return undefined
    const child = props.value.fields[fieldId]
    if (child) return valueModel(child)
    const contract = recordFields.value.find((field) => field.field_id === fieldId)
    return contract?.has_default ? contract.default : undefined
}
function recordFieldIsVisible(field: CatalogRecordField): boolean {
    const rule = field.ui?.visible_when
    if (!rule) return true
    const dependencyId = rule.field_id || rule.parameter_id
    if (!dependencyId) return true
    const actual = recordRuleValue(dependencyId)
    if (rule.operator === 'not_equals') return actual !== rule.value
    if (rule.operator === 'greater_than') return typeof actual === 'number' && actual > Number(rule.value)
    if (rule.operator === 'truthy') return Boolean(actual)
    return actual === rule.value
}
const visibleRecordFields = computed(() => recordFields.value.filter(recordFieldIsVisible))
const visiblePrimaryRecordFields = computed(() => visibleRecordFields.value.filter((field) => field.ui?.importance !== 'advanced'))
const visibleAdvancedRecordFields = computed(() => visibleRecordFields.value.filter((field) => field.ui?.importance === 'advanced'))
onMounted(() => {
    if (props.resolveCatalog && (catalogMode.value || ['computed', 'record'].includes(props.value.kind))) void loadCatalog()
})
// A source/operation replacement deliberately preserves value_id. Keep the
// expanded editor open across that replacement; only reset when the user
// actually selects a different value node.
watch(() => props.value.value_id, () => {
    if (isInlineExpressionEditable(props.value)) advancedOpen.value = false
    wholeValueMode.value = false
    collectionLimit.value = COLLECTION_PAGE_SIZE
})

function replace(value: ProgramValueNode): void { emit('replace', value) }
function replaceWholeValue(value: ProgramValueNode): void {
    wholeValueMode.value = !['list', 'map', 'record', 'json'].includes(value.kind)
    replace(value)
}
function resolveSelectorCatalog(expectedType: string, scopeBindings: LocalSymbolDefinition[] = []): Promise<ProgramValueCatalogDto> {
    if (!props.resolveCatalog || props.value.kind !== 'selector') return Promise.reject(new Error('逐项作用域目录不可用。'))
    return props.resolveCatalog(expectedType, [...props.value.bindings, ...scopeBindings])
}
function canCreateChild(valueType: string): boolean {
    return canMaterializeProgramValue(valueType) || compatibleProgramValues(props.availableValues, valueType).length > 0
}
function newChildValue(valueType: string, valueId = newProgramValueId()): ProgramValueNode {
    if (canMaterializeProgramValue(valueType)) return defaultProgramValue(valueType, valueId)
    const available = compatibleProgramValues(props.availableValues, valueType)[0]
    return available
        ? referenceProgramValue(available, valueId, valueType)
        : { value_id: valueId, kind: 'unset', value_type: valueType }
}
function materialize(next: ReturnType<typeof valueDraftFromModel>): ProgramValueNode {
    return { ...next, value_id: props.value.value_id } as ProgramValueNode
}
function replaceLiteral(model: unknown): void { replace(materialize(valueDraftFromModel(parameter.value, literalControl.value, model))) }
function openRecordCatalog(): void {
    catalogMode.value = 'record'
    selectedCandidateId.value = ''
    void loadCatalog()
}
async function loadCatalog(): Promise<void> {
    if (!props.resolveCatalog) return
    const request = ++catalogRequest
    catalogLoading.value = true
    catalogError.value = ''
    try {
        const result = await props.resolveCatalog(props.value.value_type)
        if (request !== catalogRequest) return
        catalog.value = result
        selectedCandidateId.value = ''
    } catch (error) {
        if (request !== catalogRequest) return
        catalogError.value = error instanceof Error ? error.message : '目录读取失败，请重试。'
    } finally {
        if (request === catalogRequest) catalogLoading.value = false
    }
}
function operationTypeSuffix(candidate: PureOperationCandidateDto): string {
    const variants = catalog.value?.operations.filter((item) => item.operation_id === candidate.operation_id) || []
    if (variants.length <= 1) return ''
    return ` · ${candidate.inputs.map((item) => programTypeDisplayName(item.value_type)).join(' / ')}`
}
function memberCandidateLabel(candidate: RecordMemberCandidateDto): string {
    return `${candidate.source_display_name} · ${candidate.path.map((item) => item.display_name).join(' · ')}`
}
function applyCandidate(): void {
    if (catalogMode.value === 'record') {
        const schema = catalog.value?.record
        if (!schema || ['reference_only', 'capture_only'].includes(schema.authoring_mode || 'constructible')) return
        replace({
            value_id: props.value.value_id,
            kind: 'record',
            value_type: props.value.value_type,
            record_type: props.value.value_type,
            record_name: schema.display_name,
            field_names: Object.fromEntries(schema.fields.map((field) => [field.field_id, field.display_name])),
            fields: Object.fromEntries(schema.fields.map((field) => [
                field.field_id,
                catalogFieldValue(field),
            ])),
        })
    } else if (catalogMode.value === 'computed') {
        if (selectedCandidateId.value.startsWith('member:')) {
            applyMemberCandidate(selectedCandidateId.value.slice('member:'.length))
            catalogMode.value = ''
            return
        }
        const candidateId = selectedCandidateId.value.startsWith('operation:')
            ? selectedCandidateId.value.slice('operation:'.length)
            : selectedCandidateId.value
        const candidate = catalog.value?.operations.find((item) => item.candidate_id === candidateId)
        if (!candidate) return
        replace({
            value_id: props.value.value_id,
            kind: 'computed',
            value_type: candidate.result_type,
            operation_id: candidate.operation_id,
            operation_name: operationSyntaxName(candidate),
            operation_input_names: Object.fromEntries(candidate.inputs.map((input) => [input.input_id, input.display_name])),
            inputs: Object.fromEntries(candidate.inputs.map((input) => [
                input.input_id,
                canMaterializeProgramValue(input.value_type)
                    ? defaultProgramValue(input.value_type, newProgramValueId('value_input'))
                    : {
                        value_id: newProgramValueId('value_input'),
                        kind: 'unset',
                        value_type: input.value_type,
                    },
            ])),
        })
    } else {
        applyMemberCandidate(selectedCandidateId.value)
    }
    catalogMode.value = ''
    advancedOpen.value = true
}
function applyMemberCandidate(candidateId: string): void {
    const candidate = catalog.value?.members.find((item) => item.candidate_id === candidateId)
    if (!candidate) return
    const available = props.availableValues.find((item) => item.source === candidate.source && item.id === candidate.source_id)
    if (!available) { catalogError.value = '来源值已离开当前作用域，请重新打开编辑器。'; return }
    let source = referenceProgramValue(available, newProgramValueId('value_source'), candidate.source_value_type)
    candidate.path.forEach((field, index) => {
        source = {
            value_id: index === candidate.path.length - 1 ? props.value.value_id : newProgramValueId('value_member'),
            kind: 'member_access',
            value_type: field.result_type,
            source,
            field_id: field.field_id,
            field_name: field.display_name,
        }
    })
    replace(source)
}
function catalogFieldValue(field: CatalogRecordField): ProgramValueNode {
    const valueId = newProgramValueId('value_field')
    if (field.has_default) {
        return { value_id: valueId, kind: 'literal', value_type: field.value_type, value: field.default as ProgramLiteral }
    }
    return { value_id: valueId, kind: 'unset', value_type: field.value_type }
}
function matchingOperationCandidate(): PureOperationCandidateDto | null {
    if (props.value.kind !== 'computed') return null
    const computedValue = props.value
    return catalog.value?.operations.find((item) => item.operation_id === computedValue.operation_id
        && item.result_type === computedValue.value_type
        && item.inputs.every((input) => computedValue.inputs[input.input_id]?.value_type === input.value_type)) || null
}
function operationInputContract(inputId: string) { return matchingOperationCandidate()?.inputs.find((item) => item.input_id === inputId) }
function operationInputLabel(inputId: string): string {
    if (props.value.kind !== 'computed') return '参数'
    return operationInputContract(inputId)?.display_name
        || props.value.operation_input_names?.[inputId]
        || `参数 ${Math.max(1, Object.keys(props.value.inputs).indexOf(inputId) + 1)}`
}
function operationInputConstraints(inputId: string): ProgramParameterContract['constraints'] {
    const choices = operationInputContract(inputId)?.choices || []
    return choices.length ? { choices } : {}
}
function recordFieldValue(field: CatalogRecordField): ProgramValueNode {
    if (props.value.kind !== 'record') return { value_id: newProgramValueId('value_field'), kind: 'unset', value_type: field.value_type }
    const current = props.value.fields[field.field_id]
    if (current) return current
    const valueId = `${props.value.value_id}.${field.field_id}`
    if (field.has_default) return { value_id: valueId, kind: 'literal', value_type: field.value_type, value: field.default as ProgramLiteral }
    return { value_id: valueId, kind: 'unset', value_type: field.value_type }
}
function recordFieldConstraints(field: CatalogRecordField): ProgramParameterContract['constraints'] {
    return { ...(field.constraints || {}), ...(field.choices?.length ? { choices: field.choices } : {}) }
}
function changeConditionKind(event: Event): void {
    const select = event.target as HTMLSelectElement
    const kind = select.value
    select.value = conditionKind.value
    if (kind === conditionKind.value) return
    if (hasMeaningfulProgramValue(props.value)) {
        pendingTypeChange.value = { kind: 'condition', next: kind }
        return
    }
    applyConditionKind(kind)
}
function applyConditionKind(kind: string): void {
    const rootId = props.value.value_id
    if (kind === 'single') { replace(defaultProgramValue('bool', rootId)); return }
    if (kind === 'compare') {
        replace({
            value_id: rootId,
            kind: 'compare',
            value_type: 'bool',
            operator: 'eq',
            left: defaultProgramValue('string', newProgramValueId('value_left')),
            right: defaultProgramValue('string', newProgramValueId('value_right')),
        })
        return
    }
    if (kind === 'not') {
        replace({ value_id: rootId, kind: 'not', value_type: 'bool', condition: defaultProgramValue('bool') })
        return
    }
    replace({
        value_id: rootId,
        kind: 'condition_group',
        value_type: 'bool',
        operator: kind as 'all' | 'any',
        conditions: [defaultProgramValue('bool')],
    })
}
function updateJsonValue(payload: ProgramLiteral): void { if (props.value.kind === 'json') replace({ ...props.value, payload }) }
function replaceListItem(index: number, child: ProgramValueNode): void {
    if (props.value.kind !== 'list') return
    const items = [...props.value.items]; items[index] = child; replace({ ...props.value, items })
}
function addListItem(): void {
    if (props.value.kind !== 'list' || !canAddListItem.value) return
    replace({ ...props.value, items: [...props.value.items, newChildValue(props.value.item_type)] })
}
function removeListItem(index: number): void { if (props.value.kind === 'list') replace({ ...props.value, items: props.value.items.filter((_, current) => current !== index) }) }
function moveListItem(index: number, offset: -1 | 1): void {
    if (props.value.kind !== 'list') return
    const target = index + offset
    if (target < 0 || target >= props.value.items.length) return
    const items = [...props.value.items]; [items[index], items[target]] = [items[target], items[index]]; replace({ ...props.value, items })
}
function replaceMapPart(index: number, part: 'key' | 'value', child: ProgramValueNode): void {
    if (props.value.kind !== 'map') return
    const entries = props.value.entries.map((entry, current) => current === index ? { ...entry, [part]: child } : entry)
    replace({ ...props.value, entries })
}
function addMapEntry(): void {
    if (props.value.kind !== 'map' || !canAddMapEntry.value) return
    replace({ ...props.value, entries: [...props.value.entries, {
        key: newChildValue(props.value.key_type, newProgramValueId('value_key')),
        value: newChildValue(props.value.entry_value_type, newProgramValueId('value_entry')),
    }] })
}
function removeMapEntry(index: number): void {
    if (props.value.kind === 'map') replace({ ...props.value, entries: props.value.entries.filter((_, current) => current !== index) })
}
function moveMapEntry(index: number, offset: -1 | 1): void {
    if (props.value.kind !== 'map') return
    const target = index + offset
    if (target < 0 || target >= props.value.entries.length) return
    const entries = [...props.value.entries]; [entries[index], entries[target]] = [entries[target], entries[index]]; replace({ ...props.value, entries })
}
function replaceRecordField(fieldId: string, child: ProgramValueNode): void {
    if (props.value.kind === 'record') replace({ ...props.value, fields: { ...props.value.fields, [fieldId]: child } })
}
function replaceOperationInput(inputId: string, child: ProgramValueNode): void {
    if (props.value.kind === 'computed') replace({ ...props.value, inputs: { ...props.value.inputs, [inputId]: child } })
}
function replaceSelectorExpression(expression: ProgramValueNode): void {
    if (props.value.kind === 'selector') replace({ ...props.value, expression })
}
function replaceMemberSource(source: ProgramValueNode): void { if (props.value.kind === 'member_access') replace({ ...props.value, source }) }
function replaceCompareOperator(event: Event): void { if (props.value.kind === 'compare') replace({ ...props.value, operator: (event.target as HTMLSelectElement).value as typeof props.value.operator }) }
function replaceCompareValueType(event: Event): void {
    if (props.value.kind !== 'compare') return
    const select = event.target as HTMLSelectElement
    const valueType = select.value
    select.value = compareValueType.value
    if (valueType === compareValueType.value) return
    if (hasMeaningfulProgramValue(props.value.left) || hasMeaningfulProgramValue(props.value.right)) {
        pendingTypeChange.value = { kind: 'compare', next: valueType }
        return
    }
    applyCompareValueType(valueType)
}
function applyCompareValueType(valueType: string): void {
    if (props.value.kind !== 'compare') return
    replace({
        ...props.value,
        left: newChildValue(valueType, props.value.left.value_id),
        right: newChildValue(valueType, props.value.right.value_id),
    })
}
function confirmTypeChange(): void {
    const pending = pendingTypeChange.value
    pendingTypeChange.value = null
    if (!pending) return
    if (pending.kind === 'condition') applyConditionKind(pending.next)
    else applyCompareValueType(pending.next)
}
function hasMeaningfulProgramValue(value: ProgramValueNode): boolean {
    if (value.kind === 'unset') return false
    if (value.kind === 'literal') return value.value !== null && value.value !== ''
    if (value.kind === 'json') {
        const payload = value.payload
        if (payload === null || payload === '') return false
        if (Array.isArray(payload)) return payload.length > 0
        return typeof payload !== 'object' || Object.keys(payload).length > 0
    }
    if (value.kind === 'list') return value.items.some(hasMeaningfulProgramValue)
    if (value.kind === 'map') return value.entries.some((entry) => hasMeaningfulProgramValue(entry.key) || hasMeaningfulProgramValue(entry.value))
    if (value.kind === 'record') return Object.values(value.fields).some(hasMeaningfulProgramValue)
    if (value.kind === 'compare') return hasMeaningfulProgramValue(value.left) || hasMeaningfulProgramValue(value.right)
    if (value.kind === 'condition_group') return value.conditions.some(hasMeaningfulProgramValue)
    if (value.kind === 'not') return hasMeaningfulProgramValue(value.condition)
    return true
}
function replaceCompareSide(side: 'left' | 'right', child: ProgramValueNode): void { if (props.value.kind === 'compare') replace({ ...props.value, [side]: child }) }
function replaceConditionOperator(event: Event): void { if (props.value.kind === 'condition_group') replace({ ...props.value, operator: (event.target as HTMLSelectElement).value as 'all' | 'any' }) }
function replaceCondition(index: number, child: ProgramValueNode): void {
    if (props.value.kind !== 'condition_group') return
    const conditions = [...props.value.conditions]; conditions[index] = child; replace({ ...props.value, conditions })
}
function addCondition(): void {
    if (props.value.kind === 'condition_group') replace({ ...props.value, conditions: [...props.value.conditions, defaultProgramValue('bool')] })
}
function removeCondition(index: number): void { if (props.value.kind === 'condition_group') replace({ ...props.value, conditions: props.value.conditions.filter((_, current) => current !== index) }) }
function replaceNotCondition(condition: ProgramValueNode): void { if (props.value.kind === 'not') replace({ ...props.value, condition }) }
</script>

<style scoped>
.value-tree-field { min-width: 0; }
.value-tree-field > header { display: flex; align-items: center; justify-content: space-between; gap: var(--app-spacing-sm); margin-bottom: var(--app-form-label-control-gap); }
.value-tree-field > header > div { min-width: 0; display: flex; align-items: baseline; gap: 6px; }
.value-tree-field > header strong { overflow: hidden; color: var(--app-text-primary); font-size: var(--app-font-xs); font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.value-tree-field > header strong b { margin-inline-start: 3px; color: var(--app-color-danger); font-weight: 600; }
.value-tree-field > header small { color: var(--app-text-placeholder); font-size: var(--app-font-caption); }
.is-inline-leaf { display: grid; grid-template-columns: minmax(108px, .38fr) minmax(0, 1fr); align-items: start; column-gap: 12px; }
.is-inline-leaf > header { min-width: 0; min-height: var(--app-control-default); margin: 0; }
.is-inline-leaf > header > div { width: 100%; display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 5px; }
.is-inline-leaf > header strong { min-width: 0; }
.is-inline-leaf > header small { white-space: nowrap; }
.is-inline-leaf > .field-help { grid-column: 2; }
.field-help { margin: 6px 0 0; color: var(--app-text-secondary); font-size: var(--app-font-caption); line-height: 1.5; }
.expression-help-trigger { width: 18px; height: 18px; display: grid; flex: 0 0 18px; align-self: center; place-items: center; padding: 0; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-placeholder); cursor: help; }
.expression-help-trigger:hover, .expression-help-trigger:focus-visible { outline: 0; background: var(--app-bg-hover); color: var(--app-text-primary); box-shadow: var(--focus-ring); }
select { font: inherit; }
select { min-width: 0; min-height: var(--app-control-default); border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); outline: 0; background: var(--app-bg-base); color: var(--app-text-primary); }
select { padding: 0 8px; }
select:focus-visible { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.value-mode-bar { min-height: var(--app-control-compact); display: flex; align-items: center; justify-content: space-between; gap: var(--app-spacing-sm); margin-bottom: var(--app-spacing-sm); color: var(--app-text-placeholder); font-size: var(--app-font-xs); }
.value-mode-bar > span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.catalog-picker { display: flex; flex-direction: column; gap: 8px; margin-bottom: var(--app-spacing-sm); }
.catalog-heading, .catalog-error { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.catalog-heading strong { color: var(--app-text-primary); font-size: var(--app-font-xs); }
.catalog-picker > label { display: grid; grid-template-columns: minmax(88px, .36fr) minmax(0, 1fr); align-items: center; gap: 8px; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.catalog-picker p { margin: 0; color: var(--app-text-placeholder); font-size: var(--app-font-xs); line-height: 1.5; }
.catalog-error span { color: var(--app-color-danger); font-size: var(--app-font-xs); }
.use-candidate { align-self: flex-end; }
.children-list, .complex-block { container-type: inline-size; display: flex; flex-direction: column; gap: var(--app-form-field-gap); }
.list-entry, .map-entry, .condition-row { padding: 0 0 var(--app-spacing-md); border-bottom: 1px solid var(--app-border-subtle); }
.list-entry:last-of-type, .map-entry:last-of-type, .condition-row:last-of-type { padding-bottom: 0; border-bottom: 0; }
.map-entry > header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.map-entry > header > span { display: flex; gap: 4px; }
.map-entry > .value-tree-field + .value-tree-field { margin-top: 8px; }
.danger-inline-action:hover:not(:disabled) { color: var(--app-color-danger); }
.row-actions { display: flex; justify-content: flex-end; gap: 4px; margin-top: -5px; }
.collection-actions { display: flex; align-items: center; gap: 9px; color: var(--app-text-placeholder); font-size: var(--app-font-xs); }
.record-editor { min-width: 0; }
.record-state { min-height: var(--app-control-default); display: flex; align-items: center; justify-content: space-between; gap: var(--app-spacing-sm); margin: 0; color: var(--app-text-placeholder); font-size: var(--app-font-xs); }
.record-state.is-error { color: var(--app-color-danger); }
.record-advanced { margin-top: var(--app-form-field-gap); border-top: 1px solid var(--app-border-subtle); }
.record-advanced > summary { min-height: var(--app-form-disclosure-height); display: flex; align-items: center; color: var(--app-text-secondary); font-size: var(--app-font-compact); cursor: pointer; }
.record-advanced[open] > summary { margin-bottom: var(--app-form-heading-field-gap); }
.readonly-contract { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 3px 8px; padding-bottom: var(--app-spacing-sm); border-bottom: 1px solid var(--app-border-subtle); }
.readonly-contract span { color: var(--app-text-placeholder); font-size: var(--app-font-caption); }
.readonly-contract strong { color: var(--app-text-primary); font-size: var(--app-font-xs); }
.selector-summary { display: flex; flex-direction: column; gap: 3px; padding-bottom: var(--app-spacing-sm); border-bottom: 1px solid var(--app-border-subtle); }
.selector-summary strong { color: var(--app-text-primary); font-size: var(--app-font-xs); }
.selector-summary span { color: var(--app-text-secondary); font-size: var(--app-font-caption); line-height: 1.45; }
.operator-field { display: grid; grid-template-columns: minmax(80px, .45fr) minmax(0, 1fr); align-items: center; gap: 8px; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.condition-kind-field { display: grid; grid-template-columns: minmax(96px, .45fr) minmax(0, 1fr); align-items: center; gap: 8px; margin-bottom: 8px; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.type-change-confirm { display: flex; flex-direction: column; gap: var(--app-spacing-xs); margin-bottom: var(--app-spacing-sm); padding: var(--app-spacing-sm); border: 1px solid var(--app-color-warning); border-radius: var(--app-radius-sm); color: var(--app-text-regular); font-size: var(--app-font-xs); }
.type-change-confirm > div { display: flex; align-items: center; flex-wrap: wrap; gap: var(--app-spacing-xs); }
.reference-note, .readonly-value, .empty-note, .unset-value { margin: 0; color: var(--app-text-secondary); font-size: var(--app-font-xs); line-height: 1.55; }
.unset-value { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.collapsed-value { display: flex; align-items: center; justify-content: space-between; gap: 8px; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.condition-row > .remove-condition { width: 100%; margin-top: 6px; }
@container (max-width: 350px) {
    .is-inline-leaf { grid-template-columns: minmax(0, 1fr); row-gap: var(--app-form-label-control-gap); }
    .is-inline-leaf > header { min-height: auto; }
    .is-inline-leaf > .field-help { grid-column: 1; }
}
@media (max-width: 620px) { .value-tree-field > header { align-items: stretch; flex-direction: column; } .catalog-picker > label { grid-template-columns: 1fr; } }
@media (max-width: 420px) { .is-inline-leaf { grid-template-columns: minmax(0, 1fr); row-gap: var(--app-form-label-control-gap); } .is-inline-leaf > header { min-height: auto; } .is-inline-leaf > .field-help { grid-column: 1; } }
</style>
