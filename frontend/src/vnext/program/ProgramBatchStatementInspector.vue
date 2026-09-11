<template>
    <aside class="statement-inspector batch-statement-inspector" aria-label="批量语句检查器">
        <VNextPaneHeader
            class="inspector-header"
            role="inspector"
            :title="contract ? `批量编辑 · ${contract.display_name}` : '批量选择'"
            :meta="`${statements.length} 条语句`"
        />
        <div class="inspector-body app-inspector-body">
            <template v-if="contract && callStatements.length === statements.length">
                <p class="batch-scope-note" role="note">只修改这些语句的公共参数；步骤备注和返回结果保持不变。</p>
                <VNextInspectorSection v-if="primaryFields.length" title="公共参数" title-id="batch-parameter-heading">
                    <ProgramParameterControl
                        v-for="field in primaryFields"
                        :key="field.parameter.parameter_id"
                        :statement-id="callStatements[0].statement_id"
                        :parameter="batchParameter(field.parameter, field.mixed)"
                        :value="field.displayValue"
                        :mixed="field.mixed"
                        :available-values="availableValues"
                        :assets="assets"
                        :platform="platform"
                        :disabled="busy"
                        :value-editor-available="true"
                        @update="commitField(field.parameter.parameter_id, $event)"
                        @open-value-editor="openBatchValueEditor"
                    />
                </VNextInspectorSection>
                <details v-if="advancedFields.length" class="advanced-parameters app-inspector-disclosure">
                    <summary><span>高级参数</span></summary>
                    <ProgramParameterControl
                        v-for="field in advancedFields"
                        :key="field.parameter.parameter_id"
                        :statement-id="callStatements[0].statement_id"
                        :parameter="batchParameter(field.parameter, field.mixed)"
                        :value="field.displayValue"
                        :mixed="field.mixed"
                        :available-values="availableValues"
                        :assets="assets"
                        :platform="platform"
                        :disabled="busy"
                        :value-editor-available="true"
                        @update="commitField(field.parameter.parameter_id, $event)"
                        @open-value-editor="openBatchValueEditor"
                    />
                </details>
                <VNextWorkspaceState
                    v-if="!fields.length"
                    compact
                    kind="empty"
                    title="这些语句没有可批量修改的参数"
                    description="仍可在中央流程中复制、剪切、移动或删除当前选择。"
                />
            </template>
            <VNextWorkspaceState
                v-else
                compact
                kind="selection"
                title="所选语句类型不同"
                description="选择至少两条相同函数调用后，可以在这里统一修改公共参数。当前选择仍可批量复制、剪切、移动或删除。"
            />
        </div>
        <p class="sr-only" aria-live="polite">已选择 {{ statements.length }} 条语句</p>
    </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import ProgramParameterControl from './ProgramParameterControl.vue'
import VNextInspectorSection from '../components/ui/VNextInspectorSection.vue'
import VNextPaneHeader from '../components/ui/VNextPaneHeader.vue'
import VNextWorkspaceState from '../components/ui/VNextWorkspaceState.vue'
import type {
    AvailableProgramValue,
    CallStatement,
    ProgramAsset,
    ProgramCommand,
    ProgramFunctionContract,
    ProgramParameterContract,
    ProgramStatement,
    ProgramValueNode,
    ProgramValueUpdate,
    ProgramValueEditorRequest,
} from './types'
import type { ExecutionPlatformId } from '../types'

interface BatchField {
    parameter: ProgramParameterContract
    displayValue: ProgramValueNode
    mixed: boolean
}

const props = withDefaults(defineProps<{
    statements: ProgramStatement[]
    contract?: ProgramFunctionContract | null
    availableValues?: AvailableProgramValue[]
    assets?: ProgramAsset[]
    platform?: ExecutionPlatformId
    busy?: boolean
}>(), {
    contract: null,
    availableValues: () => [],
    assets: () => [],
    platform: 'windows',
    busy: false,
})

const emit = defineEmits<{
    command: [command: ProgramCommand]
    openValueEditor: [request: ProgramValueEditorRequest]
}>()
const callStatements = computed(() => props.statements.filter((statement): statement is CallStatement => statement.kind === 'call'))

function comparableValue(value: ProgramValueNode): string {
    function visit(current: unknown): unknown {
        if (Array.isArray(current)) return current.map(visit)
        if (!current || typeof current !== 'object') return current
        return Object.fromEntries(Object.entries(current as Record<string, unknown>)
            .filter(([key]) => !['value_id', 'summary'].includes(key))
            .map(([key, child]) => [key, visit(child)]))
    }
    return JSON.stringify(visit(value))
}

function conditionValue(statement: CallStatement, parameterId: string): unknown {
    const value = statement.arguments[parameterId]
    return value?.kind === 'literal' ? value.value : undefined
}

function visibleForEveryCall(parameter: ProgramParameterContract): boolean {
    if (parameter.ui?.importance === 'internal') return false
    const rule = parameter.ui?.visible_when
    if (!rule?.parameter_id) return true
    return callStatements.value.every((statement) => {
        const actual = conditionValue(statement, rule.parameter_id || '')
        if (rule.operator === 'not_equals') return actual !== rule.value
        if (rule.operator === 'greater_than') return typeof actual === 'number' && actual > Number(rule.value)
        if (rule.operator === 'truthy') return Boolean(actual)
        return actual === rule.value
    })
}

const fields = computed<BatchField[]>(() => {
    if (!props.contract || callStatements.value.length !== props.statements.length) return []
    return props.contract.parameters.filter(visibleForEveryCall).flatMap((parameter) => {
        const values = callStatements.value.map((statement) => statement.arguments[parameter.parameter_id]).filter(Boolean)
        if (values.length !== callStatements.value.length || !values[0]) return []
        const mixed = values.slice(1).some((value) => comparableValue(value) !== comparableValue(values[0]))
        const displayValue: ProgramValueNode = mixed
            ? { value_id: values[0].value_id, value_type: parameter.value_type, kind: 'unset' }
            : values[0]
        return [{ parameter, displayValue, mixed }]
    })
})
const primaryFields = computed(() => fields.value.filter((field) => field.parameter.ui?.importance !== 'advanced'))
const advancedFields = computed(() => fields.value.filter((field) => field.parameter.ui?.importance === 'advanced'))

function batchParameter(parameter: ProgramParameterContract, mixed: boolean): ProgramParameterContract {
    return {
        ...parameter,
        required: mixed ? false : parameter.required,
        ui: {
            control: parameter.ui?.control || 'expression',
            ...(parameter.ui || {}),
            actions: [],
            ...(mixed ? { placeholder: '多个值，输入后应用到全部' } : {}),
        },
    }
}

function commitField(parameterId: string, update: ProgramValueUpdate): void {
    emit('command', {
        kind: 'batch_update_values',
        statement_ids: callStatements.value.map((statement) => statement.statement_id),
        parameter_id: parameterId,
        next: update.next,
    })
}

function openBatchValueEditor(request: ProgramValueEditorRequest): void {
    emit('openValueEditor', {
        ...request,
        batch_statement_ids: callStatements.value.map((statement) => statement.statement_id),
    })
}
</script>

<style scoped>
.batch-scope-note {
    margin: 0;
    padding: var(--app-spacing-sm) 0;
    border-bottom: 1px solid var(--app-border-subtle);
    color: var(--app-text-secondary);
    font-size: var(--app-font-interface);
    line-height: var(--app-line-height-regular);
}
</style>
