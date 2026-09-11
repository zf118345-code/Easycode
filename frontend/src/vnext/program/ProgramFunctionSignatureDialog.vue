<template>
    <VNextDialog
        :open="open"
        title="参数与返回值"
        description="让同一个项目函数在不同调用位置接收不同输入，并把一个结果交还给调用方。"
        size="large"
        :dismissible="!busy"
        :dismiss-on-backdrop="!busy"
        @close="emit('close')"
    >
        <form id="program-signature-form" class="signature-form" @submit.prevent="submit">
            <section class="signature-section">
                <header class="section-heading">
                    <div><h3>输入参数</h3><p>调用这个函数时填写；参数顺序也是调用处的展示顺序。</p></div>
                    <VNextButton size="compact" :disabled="busy" @click="addParameter">
                        <template #icon><Plus aria-hidden="true" /></template>添加参数
                    </VNextButton>
                </header>

                <div v-if="draftParameters.length" class="parameter-list">
                    <article v-for="(parameter, index) in draftParameters" :key="parameter.clientId" class="parameter-card">
                        <div class="parameter-main-row">
                            <span class="parameter-index" aria-hidden="true">{{ index + 1 }}</span>
                            <label><span>名称</span><VNextTextField v-model="parameter.display_name" maxlength="80" autocomplete="off" placeholder="例如：最大战斗次数" :disabled="busy" /></label>
                            <label><span>类型</span><VNextSelect v-model="parameter.value_type" :disabled="busy" @update:model-value="changeType(parameter, $event)"><option v-for="option in typeOptionsFor(parameter.value_type)" :key="option.value" :value="option.value">{{ option.label }}</option></VNextSelect></label>
                            <label class="optional-toggle" title="关闭后，调用方可以省略这个参数并使用默认值"><VNextSwitch v-model="parameter.required" label="参数必填" :disabled="busy" @update:model-value="changeRequired(parameter, $event)" /><span>必填</span></label>
                            <div class="row-actions">
                                <VNextIconButton label="上移参数" :disabled="busy || index === 0" @click="moveParameter(index, -1)"><ChevronUp /></VNextIconButton>
                                <VNextIconButton label="下移参数" :disabled="busy || index === draftParameters.length - 1" @click="moveParameter(index, 1)"><ChevronDown /></VNextIconButton>
                                <VNextIconButton label="删除参数" tone="danger" :disabled="busy" @click="removeParameter(index)"><Trash2 /></VNextIconButton>
                            </div>
                        </div>
                        <div v-if="!parameter.required && parameter.default_value" class="parameter-default">
                            <ProgramParameterControl
                                :statement-id="`function-signature:${program?.function_id || 'unknown'}:${parameter.clientId}`"
                                :parameter="defaultContract(parameter)"
                                :value="parameter.default_value"
                                :disabled="busy"
                                @update="updateDefault(parameter, $event)"
                            />
                        </div>
                    </article>
                </div>
                <div v-else class="empty-parameters"><span>当前没有参数</span><small>函数仍可直接调用；需要复用不同数值时再添加。</small></div>
            </section>

            <section class="signature-section return-section">
                <header class="section-heading"><div><h3>返回值</h3><p>函数结束后交给调用处的一个结果；不需要结果就选“无返回值”。</p></div></header>
                <label class="return-type"><span>返回类型</span><VNextSelect v-model="draftReturnType" :disabled="busy"><option v-for="option in returnTypeOptions" :key="option.value" :value="option.value">{{ option.label }}</option></VNextSelect></label>
            </section>

            <VNextInlineNotice v-if="error || validationError" tone="error" :message="error || validationError" />
        </form>
        <template #footer>
            <VNextButton :disabled="busy" @click="emit('close')">取消</VNextButton>
            <VNextButton type="submit" form="program-signature-form" tone="primary" appearance="solid" :loading="busy">保存参数</VNextButton>
        </template>
    </VNextDialog>
</template>

<script setup lang="ts">
import { ref, shallowRef, watch } from 'vue'
import { ChevronDown, ChevronUp, Plus, Trash2 } from 'lucide-vue-next'
import VNextButton from '../components/ui/VNextButton.vue'
import VNextDialog from '../components/ui/VNextDialog.vue'
import VNextIconButton from '../components/ui/VNextIconButton.vue'
import VNextInlineNotice from '../components/ui/VNextInlineNotice.vue'
import VNextSelect from '../components/ui/VNextSelect.vue'
import VNextSwitch from '../components/ui/VNextSwitch.vue'
import VNextTextField from '../components/ui/VNextTextField.vue'
import ProgramParameterControl from './ProgramParameterControl.vue'
import { serverValueToUiValue } from './adapter'
import type { ProgramSummaryDto } from './serverTypes'
import type { ProgramParameterContract, ProgramValueNode, ProgramValueUpdate } from './types'
import { defaultProgramValue, newProgramValueId } from './valueFactories'

interface DraftParameter {
    clientId: string
    parameter_id?: string | null
    display_name: string
    value_type: string
    required: boolean
    default_value: ProgramValueNode | null
}

const props = withDefaults(defineProps<{
    open: boolean
    program: ProgramSummaryDto | null
    busy?: boolean
    error?: string
}>(), { busy: false, error: '' })

const emit = defineEmits<{
    close: []
    save: [payload: { parameters: Array<Omit<DraftParameter, 'clientId'>>; returnType: string }]
}>()

const typeOptions = [
    { value: 'string', label: '文本' }, { value: 'int64', label: '整数' }, { value: 'float64', label: '小数' },
    { value: 'bool', label: '开关' }, { value: 'duration', label: '持续时间' }, { value: 'date', label: '日期' },
    { value: 'datetime', label: '日期和时间' }, { value: 'time', label: '时间点' }, { value: 'point', label: '坐标' },
    { value: 'rect', label: '区域' }, { value: 'path', label: '路径' }, { value: 'list<string>', label: '文本列表' },
    { value: 'list<int64>', label: '整数列表' }, { value: 'map<string,string>', label: '文本字典' },
    { value: 'map<string,bool>', label: '开关字典' }, { value: 'json_value', label: 'JSON 数据' },
]
const returnTypeOptions = [{ value: 'null', label: '无返回值' }, ...typeOptions]
const draftParameters = shallowRef<DraftParameter[]>([])
const draftReturnType = ref('null')
const validationError = ref('')

watch(() => [props.open, props.program] as const, ([open, program]) => {
    if (!open || !program) return
    draftParameters.value = program.parameters.map((parameter) => ({
        clientId: parameter.parameter_id,
        parameter_id: parameter.parameter_id,
        display_name: parameter.display_name,
        value_type: parameter.value_type,
        required: parameter.required,
        default_value: parameter.default_value ? serverValueToUiValue(parameter.default_value) : null,
    }))
    draftReturnType.value = program.return_type || 'null'
    validationError.value = ''
}, { immediate: true })

function typeOptionsFor(current: string) {
    return typeOptions.some((option) => option.value === current)
        ? typeOptions
        : [{ value: current, label: `${current}（扩展类型）` }, ...typeOptions]
}
function addParameter(): void {
    const index = draftParameters.value.length + 1
    draftParameters.value = [...draftParameters.value, {
        clientId: newProgramValueId('parameter_draft'),
        parameter_id: null,
        display_name: `参数${index}`,
        value_type: 'string',
        required: true,
        default_value: null,
    }]
    validationError.value = ''
}
function moveParameter(index: number, offset: -1 | 1): void {
    const target = index + offset
    if (target < 0 || target >= draftParameters.value.length) return
    const next = [...draftParameters.value]
    const [parameter] = next.splice(index, 1)
    next.splice(target, 0, parameter)
    draftParameters.value = next
}
function removeParameter(index: number): void { draftParameters.value = draftParameters.value.filter((_parameter, parameterIndex) => parameterIndex !== index) }
function changeType(parameter: DraftParameter, nextType: string): void {
    parameter.value_type = nextType
    if (!parameter.required) parameter.default_value = defaultProgramValue(parameter.value_type, parameter.default_value?.value_id)
    draftParameters.value = [...draftParameters.value]
}
function changeRequired(parameter: DraftParameter, required: boolean): void {
    parameter.required = required
    parameter.default_value = parameter.required ? null : defaultProgramValue(parameter.value_type, parameter.default_value?.value_id)
    draftParameters.value = [...draftParameters.value]
}
function defaultContract(parameter: DraftParameter): ProgramParameterContract {
    return {
        parameter_id: parameter.parameter_id || parameter.clientId,
        display_name: '省略时使用',
        value_type: parameter.value_type,
        required: true,
        allowed_sources: ['fixed'],
    }
}
function updateDefault(parameter: DraftParameter, update: ProgramValueUpdate): void {
    parameter.default_value = { ...update.next, value_id: update.value_id } as ProgramValueNode
    draftParameters.value = [...draftParameters.value]
}
function submit(): void {
    const normalized: DraftParameter[] = draftParameters.value.map((parameter): DraftParameter => ({
        clientId: parameter.clientId,
        parameter_id: parameter.parameter_id,
        display_name: parameter.display_name.trim(),
        value_type: parameter.value_type,
        required: parameter.required,
        default_value: parameter.default_value,
    }))
    if (normalized.some((parameter) => !parameter.display_name)) {
        validationError.value = '每个参数都需要名称。'
        return
    }
    const names: string[] = normalized.map((parameter) => parameter.display_name)
    if (new Set<string>(names).size !== names.length) {
        validationError.value = '参数名称不能重复。'
        return
    }
    validationError.value = ''
    emit('save', {
        parameters: normalized.map(({ clientId: _clientId, ...parameter }) => parameter),
        returnType: draftReturnType.value,
    })
}
</script>

<style scoped>
.signature-form { display: grid; gap: var(--app-spacing-lg); }
.signature-section { display: grid; gap: var(--app-spacing-md); }
.section-heading { min-height: var(--app-control-default); display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.section-heading h3 { margin: 0; color: var(--app-text-primary); font-size: var(--app-font-interface); font-weight: 650; }
.section-heading p { margin: 3px 0 0; color: var(--app-text-secondary); font-size: var(--app-font-xs); line-height: var(--app-line-height-body); }
.parameter-list { display: grid; gap: 8px; }
.parameter-card { overflow: hidden; border: 1px solid var(--app-border-subtle); border-radius: var(--app-radius-md); background: var(--app-bg-input); }
.parameter-main-row { min-height: 58px; display: grid; grid-template-columns: 24px minmax(150px, 1.25fr) minmax(140px, .9fr) auto auto; align-items: end; gap: 8px; padding: 9px 10px; }
.parameter-index { align-self: center; color: var(--app-text-secondary); font-size: var(--app-font-xs); text-align: center; }
.parameter-main-row label, .return-type { min-width: 0; display: grid; gap: 5px; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.optional-toggle { height: var(--app-control-default); display: inline-flex !important; grid-auto-flow: column; align-items: center; gap: 6px !important; padding: 0 6px; color: var(--app-text-regular) !important; white-space: nowrap; }
.row-actions { height: var(--app-control-default); display: flex; align-items: center; }
.parameter-default { padding: 0 10px 10px 42px; border-top: 1px solid var(--app-border-subtle); }
.parameter-default :deep(.program-parameter) { padding-top: 9px; }
.empty-parameters { min-height: 84px; display: grid; place-items: center; align-content: center; gap: 4px; border: 1px dashed var(--app-border-default); border-radius: var(--app-radius-md); color: var(--app-text-regular); }
.empty-parameters small { color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.return-section { padding-top: var(--app-spacing-md); border-top: 1px solid var(--app-border-subtle); }
.return-type { grid-template-columns: minmax(0, 110px) minmax(180px, 320px); align-items: center; color: var(--app-text-regular); font-size: var(--app-font-interface); }
@media (max-width: 720px) {
    .parameter-main-row { grid-template-columns: 24px minmax(0, 1fr) auto; align-items: end; }
    .parameter-main-row > label:not(.optional-toggle) { grid-column: 2 / -1; }
    .optional-toggle { grid-column: 2; }
    .row-actions { grid-column: 3; }
    .parameter-default { padding-left: 10px; }
}
</style>
