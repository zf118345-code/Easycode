<template>
    <div class="structure-inspector">
        <template v-if="statement.kind === 'assignment'">
            <section class="structure-section">
                <h2>赋值目标</h2>
                <label v-if="projectVariables.length" class="field-label">
                    <span>保存位置</span>
                    <select :value="assignmentTargetChoice" :disabled="busy" @change="updateAssignmentTarget">
                        <option value="local">当前函数的局部变量</option>
                        <option v-for="variable in projectVariables" :key="variable.id" :value="`project:${variable.id}`">
                            项目变量 · {{ variable.display_name }}
                        </option>
                    </select>
                </label>
                <label v-if="statement.target.kind === 'local'" class="field-label">
                    <span>局部变量名称</span>
                    <input :value="statement.target.display_name" :disabled="busy" @change="updateAssignmentName" />
                </label>
                <label v-if="statement.target.kind === 'local'" class="field-label">
                    <span>变量类型</span>
                    <select :value="statement.target.value_type" :disabled="busy" @change="updateAssignmentType">
                        <option v-for="option in assignmentTypeOptions" :key="option.value" :value="option.value">
                            {{ option.label }}
                        </option>
                    </select>
                </label>
                <p v-else class="field-note field-note--aligned" title="项目变量的类型在变量工作区统一定义">
                    <span>{{ programTypeDisplayName(statement.target.value_type) }} · 由项目变量定义</span>
                </p>
            </section>
            <ValueField
                :statement-id="statement.statement_id"
                title="赋予的值"
                parameter-id="assignment.value"
                :value="statement.value"
                :required="true"
                :available-values="availableValues"
                :diagnostics="errors(statement.value)"
                :busy="busy"
                @open-value-editor="emit('openValueEditor', $event)"
                @update="updateAssignmentValue"
            />
        </template>

        <template v-else-if="statement.kind === 'if'">
            <ValueField
                :statement-id="statement.statement_id"
                title="判断条件"
                parameter-id="if.condition"
                value-type="bool"
                :value="statement.condition"
                :required="true"
                :available-values="availableValues"
                :diagnostics="errors(statement.condition)"
                :busy="busy"
                @open-value-editor="emit('openValueEditor', $event)"
                @update="updateIfCondition(null, $event)"
            />
            <div v-for="(branch, index) in statement.additional_branches" :key="branch.branch_id" class="if-branch-editor">
                <ValueField
                    :statement-id="statement.statement_id"
                    :title="`否则如果 ${index + 1} 的条件`"
                    :parameter-id="`if.branch.${branch.branch_id}`"
                    value-type="bool"
                    :value="branch.condition"
                    :required="true"
                    :available-values="availableValues"
                    :diagnostics="errors(branch.condition)"
                    :busy="busy"
                    @open-value-editor="emit('openValueEditor', $event)"
                    @update="updateIfCondition(branch.branch_id, $event)"
                />
                <button
                    v-if="canRemoveIfBranch"
                    type="button"
                    class="app-field-action danger-inline-action remove-branch-button"
                    :disabled="busy || branch.statements.length > 0"
                    :title="branch.statements.length ? '请先处理这个分支中的语句' : '移除这个否则如果分支'"
                    :aria-label="branch.statements.length ? '请先处理这个分支中的语句' : '移除这个否则如果分支'"
                    @click="removeIfBranch(branch.branch_id)"
                >
                    <Trash2 :size="14" aria-hidden="true" />
                    <span class="sr-only">移除分支</span>
                </button>
            </div>
            <section class="condition-branch-actions">
                <button v-if="canAddIfBranch" type="button" class="app-inline-action" :disabled="busy" title="按顺序判断，并只执行第一个满足条件的分支" @click="addIfBranch">
                    <GitBranchPlus :size="14" aria-hidden="true" />
                    <span>添加否则如果</span>
                </button>
            </section>
        </template>

        <template v-else-if="statement.kind === 'loop'">
            <section class="structure-section">
                <label class="field-label">
                    <span>重复方式</span>
                    <select :value="statement.mode" :disabled="busy" @change="updateLoopMode">
                        <option value="repeat">重复指定次数</option>
                        <option value="while">条件满足时重复</option>
                        <option value="for_each">逐项处理列表</option>
                        <option value="for_each_map">逐项处理字典</option>
                    </select>
                </label>
            </section>
            <ValueField
                :statement-id="statement.statement_id"
                :title="loopSourceLabel"
                parameter-id="loop.source"
                :value-type="loopSourceType"
                :value="statement.source"
                :required="true"
                :available-values="availableValues"
                :diagnostics="errors(statement.source)"
                :busy="busy"
                @open-value-editor="emit('openValueEditor', $event)"
                @update="updateLoopSource"
            />
            <section v-if="loopBindings.length" class="structure-section">
                <h2>循环内可用值</h2>
                <label v-for="loopBinding in loopBindings" :key="loopBinding.key" class="field-label">
                    <span>{{ loopBinding.label }}</span>
                    <input
                        :value="loopBinding.value?.display_name || ''"
                        :disabled="busy"
                        :placeholder="loopBinding.placeholder"
                        @change="updateLoopBinding(loopBinding.key, $event)"
                    />
                </label>
                <label v-if="statement.mode === 'for_each'" class="check-field">
                    <input type="checkbox" :checked="Boolean(statement.index_binding)" :disabled="busy" @change="toggleLoopIndex" />
                    <span>同时提供当前序号</span>
                </label>
            </section>
        </template>

        <template v-else-if="statement.kind === 'return'">
            <section v-if="hasVoidReturn" class="structure-section">
                <p class="compact-status">立即结束函数（无返回值）</p>
            </section>
            <ValueField
                v-else-if="statement.value"
                :statement-id="statement.statement_id"
                title="返回值"
                parameter-id="return.value"
                :value-type="functionReturnType"
                :value="statement.value"
                :required="true"
                :available-values="availableValues"
                :diagnostics="errors(statement.value)"
                :busy="busy"
                @open-value-editor="emit('openValueEditor', $event)"
                @update="updateReturnValue"
            />
            <section v-else class="structure-section">
                <div class="field-action-row">
                    <span>返回值</span>
                    <button type="button" class="app-inline-action" :disabled="busy" @click="createReturnValue"><Plus :size="14" aria-hidden="true" /><span>设置</span></button>
                </div>
            </section>
        </template>

        <template v-else-if="statement.kind === 'fail'">
            <section class="structure-section">
                <label class="field-label">
                    <span>错误 ID</span>
                    <input
                        :value="statement.error_id"
                        :disabled="busy"
                        placeholder="例如：project.login_failed"
                        title="用于按失败类型精确处理；建议使用 project. 开头的稳定英文标识"
                        @change="updateFailErrorId"
                    />
                </label>
            </section>
            <ValueField
                :statement-id="statement.statement_id"
                title="给用户的消息"
                parameter-id="fail.message"
                value-type="string"
                :value="statement.message"
                :required="true"
                :available-values="availableValues"
                :diagnostics="errors(statement.message)"
                :busy="busy"
                @open-value-editor="emit('openValueEditor', $event)"
                @update="updateFailValue('message', $event)"
            />
            <ValueField
                v-if="statement.details"
                :statement-id="statement.statement_id"
                title="诊断详情"
                parameter-id="fail.details"
                value-type="json_value"
                :value="statement.details"
                :required="false"
                :available-values="availableValues"
                :diagnostics="errors(statement.details)"
                :busy="busy"
                @open-value-editor="emit('openValueEditor', $event)"
                @update="updateFailValue('details', $event)"
            />
            <section class="structure-section structure-action-section">
                <button type="button" class="app-inline-action" :class="{ 'danger-inline-action': statement.details }" :disabled="busy" @click="toggleFailDetails">
                    <Trash2 v-if="statement.details" :size="14" aria-hidden="true" />
                    <Plus v-else :size="14" aria-hidden="true" />
                    <span>{{ statement.details ? '移除诊断详情' : '添加诊断详情' }}</span>
                </button>
            </section>
        </template>

        <template v-else-if="statement.kind === 'try'">
            <section class="structure-section">
                <label class="check-field" title="只处理运行错误；图片未找到等正常结果仍由条件语句判断">
                    <input type="checkbox" :checked="Boolean(statement.retry_policy)" :disabled="busy" @change="toggleRetry" />
                    <span>失败后重试</span>
                </label>
            </section>
            <template v-if="statement.retry_policy">
                <ValueField
                    :statement-id="statement.statement_id"
                    title="最多重试"
                    parameter-id="try.max_retries"
                    value-type="int64"
                    :value="statement.retry_policy.max_retries"
                    :required="true"
                    :constraints="{ min: 0, step: 1 }"
                    :available-values="availableValues"
                    :diagnostics="errors(statement.retry_policy.max_retries)"
                    :busy="busy"
                    @open-value-editor="emit('openValueEditor', $event)"
                    @update="updateRetryValue('max_retries', $event)"
                />
                <ValueField
                    :statement-id="statement.statement_id"
                    title="重试间隔"
                    parameter-id="try.interval"
                    value-type="duration"
                    :value="statement.retry_policy.interval"
                    :required="true"
                    :constraints="{ min: 0 }"
                    :available-values="availableValues"
                    :diagnostics="errors(statement.retry_policy.interval)"
                    :busy="busy"
                    @open-value-editor="emit('openValueEditor', $event)"
                    @update="updateRetryValue('interval', $event)"
                />
                <section v-if="reviewRetryRequired" class="retry-review" role="note">
                    <strong>重试可能重复执行外部操作</strong>
                    <p>确认里面的点击、输入或写入在失败后可以再次执行。后续修改这些语句时，系统会要求重新确认。</p>
                    <button type="button" class="app-inline-action" :disabled="busy" @click="emitCommand({ kind: 'review_retry_risk', statement_id: statement.statement_id })">
                        <ShieldCheck :size="14" aria-hidden="true" />
                        <span>已检查，允许重试</span>
                    </button>
                </section>
            </template>
            <section v-for="(clause, index) in statement.catches" :key="clause.catch_id" class="structure-section catch-section">
                <h2>失败处理 {{ index + 1 }}</h2>
                <label class="field-label">
                    <span>错误编号</span>
                    <input
                        :value="clause.error_ids.join(', ')"
                        :disabled="busy"
                        placeholder="留空表示处理全部错误"
                        @change="updateCatchErrors(clause.catch_id, $event)"
                    />
                </label>
                <label class="check-field">
                    <input type="checkbox" :checked="Boolean(clause.error_binding)" :disabled="busy" @change="toggleCatchBinding(clause.catch_id)" />
                    <span>保留错误详情</span>
                </label>
                <label v-if="clause.error_binding" class="field-label">
                    <span>错误变量名称</span>
                    <input :value="clause.error_binding.display_name" :disabled="busy" @change="updateCatchBindingName(clause.catch_id, $event)" />
                </label>
            </section>
        </template>

        <template v-else-if="statement.kind === 'target_scope'">
            <ValueField
                :statement-id="statement.statement_id"
                title="在此目标中执行"
                parameter-id="target_scope.target"
                value-type="target_ref"
                :value="statement.target"
                :required="true"
                :constraints="targetChoices"
                control="select"
                :available-values="availableValues"
                :diagnostics="errors(statement.target)"
                :busy="busy"
                @open-value-editor="emit('openValueEditor', $event)"
                @update="updateTarget"
            />
        </template>

        <template v-else-if="statement.kind === 'listen'">
            <ValueField
                :statement-id="statement.statement_id"
                title="消息名称"
                parameter-id="listen.message_name"
                value-type="string"
                :value="statement.event_source.name"
                :required="true"
                :available-values="availableValues"
                :diagnostics="errors(statement.event_source.name)"
                :busy="busy"
                @open-value-editor="emit('openValueEditor', $event)"
                @update="updateListenValue('name', $event)"
            />
            <section class="structure-section">
                <h2>收到消息后</h2>
                <label class="field-label">
                    <span>保存消息为</span>
                    <input :value="statement.receive_binding.display_name" :disabled="busy" @change="updateReceiveBinding" />
                </label>
                <label class="field-label">
                    <span>处理函数</span>
                    <select :value="statement.handler_function_id" :disabled="busy || !handlerOptions.length" @change="updateHandlerFunction">
                        <option v-for="option in handlerOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                    </select>
                </label>
                <label class="check-field">
                    <input type="checkbox" :checked="Boolean(statement.condition)" :disabled="busy" @change="toggleListenCondition" />
                    <span>满足条件后再处理</span>
                </label>
            </section>
            <ValueField
                v-if="statement.condition"
                :statement-id="statement.statement_id"
                title="处理条件"
                parameter-id="listen.condition"
                value-type="bool"
                :value="statement.condition"
                :required="true"
                :available-values="availableValues"
                :diagnostics="errors(statement.condition)"
                :busy="busy"
                @open-value-editor="emit('openValueEditor', $event)"
                @update="updateListenValue('condition', $event)"
            />
            <section v-if="handlerContract?.parameters.length" class="structure-section">
                <h2>传给处理函数</h2>
                <template v-for="parameter in handlerContract.parameters" :key="parameter.parameter_id">
                    <ProgramParameterControl
                        v-if="statement.handler_arguments[parameter.parameter_id]"
                        :statement-id="statement.statement_id"
                        :parameter="parameter"
                        :value="statement.handler_arguments[parameter.parameter_id]"
                        :available-values="listenAvailableValues"
                        :diagnostics="errors(statement.handler_arguments[parameter.parameter_id])"
                        :disabled="busy"
                        :value-editor-available="true"
                        @open-value-editor="emit('openValueEditor', $event)"
                        @update="updateHandlerArgument(parameter.parameter_id, $event)"
                    />
                    <button v-else type="button" class="app-inline-action missing-argument" :disabled="busy" @click="createHandlerArgument(parameter)">
                        <Settings2 :size="14" aria-hidden="true" />
                        <span>配置“{{ parameter.display_name }}”</span>
                    </button>
                </template>
            </section>
        </template>
    </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { GitBranchPlus, Plus, Settings2, ShieldCheck, Trash2 } from 'lucide-vue-next'
import ProgramParameterControl from './ProgramParameterControl.vue'
import ValueField from './ProgramStructureValueField.vue'
import { canMaterializeProgramValue, defaultProgramValue } from './valueFactories'
import { programTypeDisplayName } from './typePresentation'
import type {
    AvailableProgramValue,
    CatchClauseDefinition,
    ListenStatement,
    LocalSymbolDefinition,
    LoopStatement,
    ProgramCommand,
    ProgramFunctionContract,
    ProgramNamedOption,
    ProgramParameterContract,
    ProgramStatement,
    ProgramValueNode,
    ProgramValueEditorRequest,
    ProgramValueUpdate,
    RetryPolicyDefinition,
} from './types'

type StructureStatement = Exclude<ProgramStatement, { kind: 'call' }>
type LoopBindingKey = 'item_binding' | 'index_binding' | 'key_binding' | 'value_binding'

const props = withDefaults(defineProps<{
    statement: StructureStatement
    functionReturnType?: string
    functionContracts?: Record<string, ProgramFunctionContract>
    projectFunctionIds?: string[]
    availableValues?: AvailableProgramValue[]
    diagnosticsByValueId?: Record<string, string[]>
    targetOptions?: ProgramNamedOption[]
    busy?: boolean
    reviewRetryRequired?: boolean
    canAddIfBranch?: boolean
    canRemoveIfBranch?: boolean
}>(), {
    functionReturnType: 'void',
    functionContracts: () => ({}),
    projectFunctionIds: () => [],
    availableValues: () => [],
    diagnosticsByValueId: () => ({}),
    targetOptions: () => [],
    busy: false,
    reviewRetryRequired: false,
    canAddIfBranch: true,
    canRemoveIfBranch: true,
})

const emit = defineEmits<{ command: [command: ProgramCommand]; openValueEditor: [request: ProgramValueEditorRequest] }>()

function newStableId(prefix: 'value' | 'symbol'): string {
    const suffix = globalThis.crypto?.randomUUID?.().replaceAll('-', '')
        || `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`
    return `${prefix}_${suffix}`
}

function materialize(update: ProgramValueUpdate): ProgramValueNode {
    return { ...update.next, value_id: update.value_id } as ProgramValueNode
}

function literal(valueType: string, value: string | number | boolean | null | Record<string, number>): ProgramValueNode {
    return { value_id: newStableId('value'), kind: 'literal', value_type: valueType, value }
}

function unset(valueType: string): ProgramValueNode {
    return { value_id: newStableId('value'), kind: 'unset', value_type: valueType }
}

function binding(name: string, valueType: string): LocalSymbolDefinition {
    return { symbol_id: newStableId('symbol'), display_name: name, value_type: valueType }
}

function errors(value?: ProgramValueNode | null): string[] {
    return value ? props.diagnosticsByValueId[value.value_id] || [] : []
}

function emitCommand(command: ProgramCommand): void { emit('command', command) }

function updateAssignmentName(event: Event): void {
    if (props.statement.kind !== 'assignment' || props.statement.target.kind !== 'local') return
    const name = (event.target as HTMLInputElement).value.trim()
    if (!name || name === props.statement.target.display_name) return
    emitCommand({ kind: 'update_assignment_target', statement_id: props.statement.statement_id, target: { ...props.statement.target, display_name: name } })
}

function updateAssignmentValue(update: ProgramValueUpdate): void {
    if (props.statement.kind !== 'assignment') return
    const value = materialize(update)
    if (props.statement.target.kind === 'local' && props.statement.target.value_type !== value.value_type) {
        emitCommand({
            kind: 'update_assignment_target',
            statement_id: props.statement.statement_id,
            target: { ...props.statement.target, value_type: value.value_type },
            value,
        })
        return
    }
    emitCommand({ kind: 'update_assignment_value', statement_id: props.statement.statement_id, value })
}

function updateIfCondition(branchId: string | null, update: ProgramValueUpdate): void {
    if (props.statement.kind !== 'if') return
    emitCommand({ kind: 'update_if_condition', statement_id: props.statement.statement_id, branch_id: branchId, condition: materialize(update) })
}

function addIfBranch(): void {
    if (props.statement.kind !== 'if') return
    emitCommand({
        kind: 'add_if_branch',
        statement_id: props.statement.statement_id,
        condition: unset('bool'),
    })
}

function removeIfBranch(branchId: string): void {
    if (props.statement.kind !== 'if') return
    const branch = props.statement.additional_branches.find((item) => item.branch_id === branchId)
    if (!branch || branch.statements.length > 0) return
    emitCommand({ kind: 'remove_if_branch', statement_id: props.statement.statement_id, branch_id: branchId })
}

const loopSourceLabel = computed(() => {
    if (props.statement.kind !== 'loop') return ''
    return ({ repeat: '重复次数', while: '继续循环的条件', for_each: '要处理的列表', for_each_map: '要处理的字典' })[props.statement.mode]
})

const projectVariables = computed(() => props.availableValues.filter((item) => item.source === 'project'))
const commonAssignmentTypes = [
    'string', 'int64', 'float64', 'bool', 'duration', 'date', 'datetime', 'time',
    'point', 'rect', 'path',
    'list<string>', 'list<int64>', 'list<float64>', 'list<bool>', 'list<any>',
    'map<string,string>', 'map<string,int64>', 'map<string,float64>', 'map<string,bool>', 'map<string,any>',
    'json_value',
]
const assignmentTypeOptions = computed(() => {
    if (props.statement.kind !== 'assignment') return []
    const types = new Set(commonAssignmentTypes)
    types.add(props.statement.target.value_type)
    for (const item of props.availableValues) types.add(item.value_type)
    return [...types].map((value) => ({ value, label: programTypeDisplayName(value) }))
})
const assignmentTargetChoice = computed(() => {
    if (props.statement.kind !== 'assignment' || props.statement.target.kind === 'local') return 'local'
    return `project:${props.statement.target.variable_id}`
})

function assignmentValueForType(valueType: string): ProgramValueNode {
    if (props.statement.kind === 'assignment' && props.statement.value.value_type === valueType) return props.statement.value
    return canMaterializeProgramValue(valueType)
        ? defaultProgramValue(valueType, props.statement.kind === 'assignment' ? props.statement.value.value_id : newStableId('value'))
        : unset(valueType)
}

function updateAssignmentType(event: Event): void {
    if (props.statement.kind !== 'assignment' || props.statement.target.kind !== 'local') return
    const valueType = (event.target as HTMLSelectElement).value
    if (!valueType || valueType === props.statement.target.value_type) return
    emitCommand({
        kind: 'update_assignment_target',
        statement_id: props.statement.statement_id,
        target: { ...props.statement.target, value_type: valueType },
        value: assignmentValueForType(valueType),
    })
}

function updateAssignmentTarget(event: Event): void {
    if (props.statement.kind !== 'assignment') return
    const selected = (event.target as HTMLSelectElement).value
    if (selected === 'local') {
        const current = props.statement.target
        emitCommand({
            kind: 'update_assignment_target',
            statement_id: props.statement.statement_id,
            target: current.kind === 'local' ? current : {
                kind: 'local', ...binding('新变量', props.statement.value.value_type), declare: true,
            },
            ...(current.kind === 'local' ? {} : { value: assignmentValueForType(props.statement.value.value_type) }),
        })
        return
    }
    const variable = projectVariables.value.find((item) => `project:${item.id}` === selected)
    if (!variable) return
    emitCommand({
        kind: 'update_assignment_target',
        statement_id: props.statement.statement_id,
        target: {
            kind: 'project_variable', variable_id: variable.id,
            value_type: variable.value_type, display_name: variable.display_name,
        },
        value: assignmentValueForType(variable.value_type),
    })
}
const loopSourceType = computed(() => {
    if (props.statement.kind !== 'loop') return 'any'
    return ({ repeat: 'int64', while: 'bool', for_each: 'list<any>', for_each_map: 'map<string,any>' })[props.statement.mode]
})

const loopBindings = computed(() => {
    if (props.statement.kind !== 'loop') return []
    if (props.statement.mode === 'for_each') return [{ key: 'item_binding' as const, label: '当前项名称', placeholder: '例如：副本', value: props.statement.item_binding }]
    if (props.statement.mode === 'for_each_map') return [
        { key: 'key_binding' as const, label: '键名称', placeholder: '例如：副本名称', value: props.statement.key_binding },
        { key: 'value_binding' as const, label: '值名称', placeholder: '例如：副本配置', value: props.statement.value_binding },
    ]
    return []
})

function collectionSource(mode: LoopStatement['mode'], current: ProgramValueNode): ProgramValueNode {
    if (mode === 'repeat') return current.value_type === 'int64' ? current : { ...literal('int64', 1), value_id: current.value_id }
    if (mode === 'while') return current.value_type === 'bool' ? current : { ...literal('bool', true), value_id: current.value_id }
    if (mode === 'for_each') {
        if (current.value_type.startsWith('list<')) return current
        return { value_id: current.value_id, kind: 'list', value_type: 'list<any>', item_type: 'any', items: [] }
    }
    if (current.value_type.startsWith('map<')) return current
    return { value_id: current.value_id, kind: 'map', value_type: 'map<string,any>', key_type: 'string', entry_value_type: 'any', entries: [], duplicate_policy: 'error' }
}

function loopCommand(statement: LoopStatement, overrides: Partial<LoopStatement> = {}): ProgramCommand {
    const next = { ...statement, ...overrides }
    return {
        kind: 'update_loop', statement_id: statement.statement_id, mode: next.mode, source: next.source,
        item_binding: next.item_binding, index_binding: next.index_binding,
        key_binding: next.key_binding, value_binding: next.value_binding,
    }
}

function updateLoopMode(event: Event): void {
    if (props.statement.kind !== 'loop') return
    const mode = (event.target as HTMLSelectElement).value as LoopStatement['mode']
    const overrides: Partial<LoopStatement> = { mode, source: collectionSource(mode, props.statement.source) }
    if (mode === 'for_each') {
        overrides.item_binding = props.statement.item_binding || binding('当前项', 'any')
        overrides.index_binding = props.statement.index_binding
        overrides.key_binding = null
        overrides.value_binding = null
    } else if (mode === 'for_each_map') {
        overrides.item_binding = null
        overrides.index_binding = null
        overrides.key_binding = props.statement.key_binding || binding('当前键', 'string')
        overrides.value_binding = props.statement.value_binding || binding('当前值', 'any')
    } else {
        overrides.item_binding = null
        overrides.index_binding = null
        overrides.key_binding = null
        overrides.value_binding = null
    }
    emitCommand(loopCommand(props.statement, overrides))
}

function updateLoopSource(update: ProgramValueUpdate): void {
    if (props.statement.kind !== 'loop') return
    emitCommand(loopCommand(props.statement, { source: materialize(update) }))
}

function updateLoopBinding(key: LoopBindingKey, event: Event): void {
    if (props.statement.kind !== 'loop') return
    const name = (event.target as HTMLInputElement).value.trim()
    const current = props.statement[key]
    if (!name || !current || name === current.display_name) return
    emitCommand(loopCommand(props.statement, { [key]: { ...current, display_name: name } }))
}

function toggleLoopIndex(event: Event): void {
    if (props.statement.kind !== 'loop') return
    const enabled = (event.target as HTMLInputElement).checked
    emitCommand(loopCommand(props.statement, { index_binding: enabled ? props.statement.index_binding || binding('当前序号', 'int64') : null }))
}

const hasVoidReturn = computed(() => ['void', 'unit', 'null'].includes(props.functionReturnType))
function createReturnValue(): void {
    if (props.statement.kind !== 'return' || hasVoidReturn.value) return
    emitCommand({ kind: 'update_return_value', statement_id: props.statement.statement_id, value: unset(props.functionReturnType) })
}
function updateReturnValue(update: ProgramValueUpdate): void {
    if (props.statement.kind !== 'return') return
    emitCommand({ kind: 'update_return_value', statement_id: props.statement.statement_id, value: materialize(update) })
}

function failCommand(overrides: { error_id?: string; message?: ProgramValueNode; details?: ProgramValueNode | null }): ProgramCommand | null {
    if (props.statement.kind !== 'fail') return null
    return {
        kind: 'update_fail',
        statement_id: props.statement.statement_id,
        error_id: overrides.error_id ?? props.statement.error_id,
        message: overrides.message ?? props.statement.message,
        details: overrides.details === undefined ? props.statement.details : overrides.details,
    }
}
function updateFailErrorId(event: Event): void {
    const errorId = (event.target as HTMLInputElement).value.trim()
    if (!errorId) return
    const command = failCommand({ error_id: errorId })
    if (command) emitCommand(command)
}
function updateFailValue(field: 'message' | 'details', update: ProgramValueUpdate): void {
    const command = failCommand({ [field]: materialize(update) })
    if (command) emitCommand(command)
}
function toggleFailDetails(): void {
    if (props.statement.kind !== 'fail') return
    const details: ProgramValueNode | null = props.statement.details ? null : {
        value_id: newStableId('value'), kind: 'json', value_type: 'json_value', payload: {},
    }
    const command = failCommand({ details })
    if (command) emitCommand(command)
}

function toggleRetry(event: Event): void {
    if (props.statement.kind !== 'try') return
    const enabled = (event.target as HTMLInputElement).checked
    const retryPolicy: RetryPolicyDefinition | null = enabled ? {
        max_retries: literal('int64', 2),
        interval: literal('duration', { milliseconds: 500 }),
        transient_only: true,
        author_review_fingerprint: null,
    } : null
    emitCommand({ kind: 'update_try_retry_policy', statement_id: props.statement.statement_id, retry_policy: retryPolicy })
}

function updateRetryValue(field: 'max_retries' | 'interval', update: ProgramValueUpdate): void {
    if (props.statement.kind !== 'try' || !props.statement.retry_policy) return
    emitCommand({
        kind: 'update_try_retry_policy', statement_id: props.statement.statement_id,
        retry_policy: { ...props.statement.retry_policy, [field]: materialize(update) },
    })
}

function catchClause(catchId: string): CatchClauseDefinition | undefined {
    return props.statement.kind === 'try' ? props.statement.catches.find((item) => item.catch_id === catchId) : undefined
}
function updateCatch(clause: CatchClauseDefinition, overrides: Partial<CatchClauseDefinition>): void {
    if (props.statement.kind !== 'try') return
    const next = { ...clause, ...overrides }
    emitCommand({
        kind: 'update_catch_clause', statement_id: props.statement.statement_id, catch_id: clause.catch_id,
        error_ids: next.error_ids, error_binding: next.error_binding,
    })
}
function updateCatchErrors(catchId: string, event: Event): void {
    const clause = catchClause(catchId)
    if (!clause) return
    const errorIds = [...new Set((event.target as HTMLInputElement).value.split(',').map((item) => item.trim()).filter(Boolean))]
    updateCatch(clause, { error_ids: errorIds })
}
function toggleCatchBinding(catchId: string): void {
    const clause = catchClause(catchId)
    if (!clause) return
    updateCatch(clause, { error_binding: clause.error_binding ? null : binding('异常详情', 'error') })
}
function updateCatchBindingName(catchId: string, event: Event): void {
    const clause = catchClause(catchId)
    const name = (event.target as HTMLInputElement).value.trim()
    if (!clause?.error_binding || !name) return
    updateCatch(clause, { error_binding: { ...clause.error_binding, display_name: name } })
}

const targetChoices = computed(() => ({ choices: props.targetOptions }))
function updateTarget(update: ProgramValueUpdate): void {
    if (props.statement.kind !== 'target_scope') return
    emitCommand({ kind: 'update_target_scope', statement_id: props.statement.statement_id, target: materialize(update) })
}

const handlerOptions = computed(() => props.projectFunctionIds
    .filter((functionId) => props.functionContracts[functionId])
    .map((functionId) => ({ value: functionId, label: props.functionContracts[functionId].display_name })))
const handlerContract = computed(() => props.statement.kind === 'listen'
    ? props.functionContracts[props.statement.handler_function_id] || null
    : null)
const listenAvailableValues = computed<AvailableProgramValue[]>(() => {
    if (props.statement.kind !== 'listen') return props.availableValues
    return [...props.availableValues, {
        source: 'local', id: props.statement.receive_binding.symbol_id,
        display_name: props.statement.receive_binding.display_name,
        value_type: props.statement.receive_binding.value_type,
    }]
})

function listenCommand(statement: ListenStatement, overrides: Partial<ListenStatement> = {}): ProgramCommand {
    const next = { ...statement, ...overrides }
    return {
        kind: 'update_listen', statement_id: statement.statement_id, event_source: next.event_source,
        receive_binding: next.receive_binding, handler_function_id: next.handler_function_id,
        condition: next.condition, handler_arguments: next.handler_arguments,
    }
}

function updateListenValue(field: 'name' | 'condition', update: ProgramValueUpdate): void {
    if (props.statement.kind !== 'listen') return
    if (field === 'name') {
        emitCommand(listenCommand(props.statement, { event_source: { ...props.statement.event_source, name: materialize(update) } }))
    } else {
        emitCommand(listenCommand(props.statement, { condition: materialize(update) }))
    }
}
function updateReceiveBinding(event: Event): void {
    if (props.statement.kind !== 'listen') return
    const name = (event.target as HTMLInputElement).value.trim()
    if (!name) return
    emitCommand(listenCommand(props.statement, { receive_binding: { ...props.statement.receive_binding, display_name: name } }))
}
function updateHandlerFunction(event: Event): void {
    if (props.statement.kind !== 'listen') return
    const functionId = (event.target as HTMLSelectElement).value
    const contract = props.functionContracts[functionId]
    if (!contract) return
    const handlerArguments = Object.fromEntries(contract.parameters.map((parameter) => [
        parameter.parameter_id,
        parameter.default_value === undefined ? unset(parameter.value_type) : literal(parameter.value_type, parameter.default_value as never),
    ]))
    emitCommand(listenCommand(props.statement, { handler_function_id: functionId, handler_arguments: handlerArguments }))
}
function toggleListenCondition(event: Event): void {
    if (props.statement.kind !== 'listen') return
    emitCommand(listenCommand(props.statement, { condition: (event.target as HTMLInputElement).checked ? literal('bool', true) : null }))
}
function updateHandlerArgument(parameterId: string, update: ProgramValueUpdate): void {
    if (props.statement.kind !== 'listen') return
    emitCommand(listenCommand(props.statement, {
        handler_arguments: { ...props.statement.handler_arguments, [parameterId]: materialize(update) },
    }))
}
function createHandlerArgument(parameter: ProgramParameterContract): void {
    if (props.statement.kind !== 'listen') return
    const value = parameter.default_value === undefined ? unset(parameter.value_type) : literal(parameter.value_type, parameter.default_value as never)
    emitCommand(listenCommand(props.statement, { handler_arguments: { ...props.statement.handler_arguments, [parameter.parameter_id]: value } }))
}
</script>

<style scoped>
.structure-inspector {
    min-width: 0;
    container-type: inline-size;
}
.structure-section {
    padding: var(--app-form-section-padding) 0;
    border-bottom: 1px solid var(--app-border-subtle);
}
.structure-section h2 {
    margin: 0 0 var(--app-form-heading-field-gap);
    color: var(--app-text-primary);
    font-size: var(--app-font-sm);
    font-weight: 600;
}
.field-label {
    display: grid;
    grid-template-columns: minmax(72px, .34fr) minmax(0, 1fr);
    align-items: center;
    gap: var(--app-spacing-xs);
    min-width: 0;
    min-height: var(--app-control-default);
    margin-top: var(--app-spacing-xs);
    color: var(--app-text-regular);
    font-size: var(--app-font-compact);
}
.structure-section > h2 + .field-label,
.structure-section > .field-label:first-child { margin-top: 0; }
.field-label > span {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.field-label input,
.field-label select {
    width: 100%;
    min-width: 0;
    min-height: var(--app-control-default);
    padding: 0 var(--app-spacing-sm);
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    outline: 0;
    background: var(--app-bg-input);
    color: var(--app-text-primary);
    font: inherit;
}
.field-label input:hover,
.field-label select:hover { border-color: var(--app-border-strong); }
.field-label input:focus-visible,
.field-label select:focus-visible { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.check-field {
    display: flex;
    align-items: center;
    gap: var(--app-spacing-sm);
    min-height: var(--app-control-default);
    margin-top: var(--app-spacing-xs);
    color: var(--app-text-regular);
    font-size: var(--app-font-xs);
}
.check-field input { accent-color: var(--app-color-primary); }
.field-note {
    margin: var(--app-form-feedback-gap) 0 0;
    color: var(--app-text-secondary);
    font-size: var(--app-font-xs);
    line-height: 1.55;
}
.field-note--aligned {
    display: grid;
    grid-template-columns: minmax(72px, .34fr) minmax(0, 1fr);
    gap: var(--app-spacing-xs);
}
.field-note--aligned > span { grid-column: 2; }
.compact-status {
    min-height: var(--app-control-default);
    display: flex;
    align-items: center;
    margin: 0;
    color: var(--app-text-secondary);
    font-size: var(--app-font-compact);
}
.field-action-row {
    display: grid;
    grid-template-columns: minmax(72px, .34fr) minmax(0, 1fr);
    align-items: center;
    gap: var(--app-spacing-xs);
    min-height: var(--app-control-default);
    color: var(--app-text-regular);
    font-size: var(--app-font-compact);
}
.field-action-row .app-inline-action { justify-self: start; }
.retry-review { margin-top: var(--app-spacing-sm); padding: var(--app-spacing-sm); border: 1px solid color-mix(in srgb, var(--app-color-warning) 45%, var(--app-border-default)); border-radius: var(--app-radius-sm); background: var(--app-bg-sidebar); }
.retry-review strong { color: var(--app-text-primary); font-size: var(--app-font-xs); }
.retry-review p { margin: var(--app-spacing-xs) 0 var(--app-spacing-sm); color: var(--app-text-secondary); font-size: var(--app-font-xs); line-height: 1.55; }
.retry-review .app-inline-action { color: var(--app-text-primary); }
.missing-argument { width: 100%; justify-content: flex-start; margin: var(--app-spacing-xs) 0; }
.structure-action-section {
    display: grid;
    grid-template-columns: minmax(72px, .34fr) minmax(0, 1fr);
}
.structure-action-section .app-inline-action { grid-column: 2; justify-self: start; }
.catch-section + .catch-section { margin-top: 0; }
.if-branch-editor {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--app-spacing-xs);
    border-bottom: 1px solid var(--app-border-subtle);
}
.if-branch-editor :deep(.value-field) { min-width: 0; border-bottom: 0; }
.if-branch-editor :deep(.program-parameter) { border-bottom: 0; }
.remove-branch-button {
    width: var(--app-control-default);
    height: var(--app-control-default);
    margin: 0;
}
.danger-inline-action:hover:not(:disabled) { color: var(--app-color-danger); }
.condition-branch-actions {
    display: grid;
    grid-template-columns: minmax(72px, .34fr) minmax(0, 1fr);
    padding: var(--app-form-section-padding) 0;
    border-bottom: 1px solid var(--app-border-subtle);
}
.condition-branch-actions .app-inline-action { grid-column: 2; justify-self: start; }
.structure-inspector > :deep(.program-parameter) {
    padding: var(--app-form-section-padding) 0;
    border-bottom: 1px solid var(--app-border-subtle);
}
.structure-section :deep(.program-parameter:first-of-type) { margin-top: var(--app-form-heading-field-gap); }

@container (max-width: 244px) {
    .field-label,
    .field-action-row,
    .condition-branch-actions,
    .structure-action-section,
    .field-note--aligned {
        grid-template-columns: minmax(0, 1fr);
    }

    .field-label { align-items: stretch; gap: var(--app-form-label-control-gap); }
    .field-note--aligned > span,
    .condition-branch-actions .app-inline-action,
    .structure-action-section .app-inline-action { grid-column: 1; }
}
</style>
