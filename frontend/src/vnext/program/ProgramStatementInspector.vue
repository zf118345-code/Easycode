<template>
    <aside class="statement-inspector" aria-label="语句检查器">
        <VNextWorkspaceState v-if="!statement" class="inspector-empty" compact kind="selection" title="选择流程中的一步" description="参数和结果会显示在这里。"><template #icon><MousePointer2 :size="22" /></template></VNextWorkspaceState>

        <template v-else>
            <VNextPaneHeader class="inspector-header" role="inspector" :title="inspectorTitle" :meta="inspectorMeta">
                <template #actions><div class="inspector-header-actions">
                    <VNextIconButton
                        label="在 Player 中查找可发布参数"
                        title="在 Player 中查找可发布参数"
                        @click="emit('locatePlayer', statement.statement_id)"
                    >
                        <LayoutTemplate aria-hidden="true" />
                    </VNextIconButton>
                    <VNextIconButton
                        :label="`复制语句 ID：${statement.statement_id}`"
                        :title="`复制语句 ID：${statement.statement_id}`"
                        @click="copyStatementId"
                    >
                        <Check v-if="copyState === 'copied'" aria-hidden="true" />
                        <Copy v-else aria-hidden="true" />
                    </VNextIconButton>
                </div></template>
            </VNextPaneHeader>
            <p class="sr-only" aria-live="polite">{{ copyMessage }}</p>

            <div v-if="showTargetContext" class="target-context" role="note" :title="platformLabel">
                <span>语句目标</span>
                <strong>{{ targetContextLabel }}</strong>
                <p v-if="targetContextDetail">{{ targetContextDetail }}</p>
            </div>

            <div class="inspector-body app-inspector-body">
                <div v-if="statement.kind === 'call' && !functionContract" class="contract-error" role="alert">
                    函数契约不可用，暂时无法编辑参数。
                </div>

                <VNextInspectorSection v-if="fields.length" title="参数" title-id="parameter-heading">
                    <template v-if="visionPreviewSupported" #actions>
                        <VNextButton
                            class="app-inline-action vision-preview-action"
                            appearance="ghost"
                            size="compact"
                            :disabled="busy || visionPreviewBusy || Boolean(visionPreviewBlockedReason)"
                            :loading="visionPreviewBusy"
                            :title="visionPreviewBlockedReason || '截取当前画面并用实际运行参数测试，不执行点击或等待'"
                            :aria-label="visionPreviewBlockedReason || '测试当前画面'"
                            @click="runVisionPreview"
                        >
                            <template v-if="!visionPreviewBusy" #icon><ScanSearch aria-hidden="true" /></template>
                            {{ visionPreviewBusy ? '测试中' : '测试' }}
                        </VNextButton>
                    </template>
                    <div v-if="missingFields.length" class="parameter-recovery" role="alert">
                        <span>此步骤缺少 {{ missingFields.length }} 个参数节点，已有内容不会改变。</span>
                        <VNextButton
                            appearance="outline"
                            size="compact"
                            :disabled="busy || !supports('repair_missing_arguments')"
                            title="按当前函数契约补齐默认参数"
                            @click="repairMissingArguments"
                        >
                            <template #icon><Wrench aria-hidden="true" /></template>
                            补齐参数
                        </VNextButton>
                    </div>
                    <template v-for="field in primaryFields" :key="`${statement.statement_id}:${field.parameter.parameter_id}`">
                        <ProgramParameterControl
                            v-if="field.value"
                            :statement-id="statement.statement_id"
                            :parameter="field.parameter"
                            :value="field.value"
                            :available-values="availableValues"
                            :assets="assets"
                            :diagnostics="diagnosticsByValueId[field.value.value_id] || []"
                            :platform="platform"
                            :disabled="busy"
                            :value-editor-available="true"
                            @update="updateValue"
                            @capture="emit('capture', $event)"
                            @open-value-editor="emit('openValueEditor', $event)"
                        />
                    </template>
                    <details v-if="advancedFields.length" class="advanced-parameters app-inspector-disclosure" :open="advancedOpen || advancedHasErrors" @toggle="syncAdvancedOpen">
                        <summary><span>高级参数</span><small v-if="advancedHasErrors">需要处理</small></summary>
                        <template v-for="field in advancedFields" :key="`${statement.statement_id}:advanced:${field.parameter.parameter_id}`">
                            <ProgramParameterControl
                                v-if="field.value"
                                :statement-id="statement.statement_id"
                                :parameter="field.parameter"
                                :value="field.value"
                                :available-values="availableValues"
                                :assets="assets"
                                :diagnostics="diagnosticsByValueId[field.value.value_id] || []"
                                :platform="platform"
                                :disabled="busy"
                                :value-editor-available="true"
                                @update="updateValue"
                                @capture="emit('capture', $event)"
                                @open-value-editor="emit('openValueEditor', $event)"
                            />
                        </template>
                    </details>
                    <div v-if="visionPreviewSupported && (visionPreviewBlockedReason || visionPreviewError || visionPreviewResult)" class="vision-preview-feedback">
                        <p v-if="visionPreviewBlockedReason" class="app-inspector-feedback">{{ visionPreviewBlockedReason }}</p>
                        <p v-if="visionPreviewError" class="app-inspector-feedback" data-tone="danger" role="alert">{{ visionPreviewError }}</p>
                        <figure v-if="visionPreviewResult" class="vision-preview-result">
                            <img v-if="visionPreviewResult.preview_data_url" :src="visionPreviewResult.preview_data_url" alt="本次实际分析区域预览" />
                            <div v-else class="vision-preview-empty" role="img" aria-label="区域与当前画面无交集">
                                <ScanSearch aria-hidden="true" />
                                <span>无有效区域</span>
                            </div>
                            <figcaption>
                                <strong :title="visionPreviewResult.text || visionPreviewSummary">{{ visionPreviewSummary }}</strong>
                                <span :title="visionPreviewDetail">{{ visionPreviewDetail }}</span>
                            </figcaption>
                        </figure>
                    </div>
                </VNextInspectorSection>

                <section v-if="dangerReviewRequired" class="danger-review" role="alert">
                    <strong>递归删除不可回滚</strong>
                    <p>请确认此调用的目录绑定与危险权限。参数、授权或函数契约变化后需要重新审核；实际运行仍会要求终端确认授权根。</p>
                    <button type="button" class="app-inline-action" :disabled="busy" @click="reviewDangerousCall"><Check :size="14" aria-hidden="true" /><span>审核此危险调用</span></button>
                </section>

                <VNextInspectorSection v-if="showsResultBinding" class="result-section" title="结果" title-id="result-heading">
                    <div class="result-control-row">
                        <span class="result-control-label">保存结果为</span>
                        <ProgramResultBindingInput
                            :statement-id="statement.statement_id"
                            :binding="statement.kind === 'call' ? statement.result_binding : null"
                            :compatible-locals="compatibleResultLocals"
                            :disabled="busy"
                            @commit="commitResultBinding"
                        />
                        <div v-if="canCreateResultCondition" class="result-condition-action">
                            <button
                                type="button"
                                class="app-field-action"
                                :disabled="busy"
                                :title="resultConditionHint"
                                :aria-label="resultConditionHint"
                                @click="createResultCondition"
                            >
                                <GitBranchPlus :size="14" aria-hidden="true" />
                                <span class="sr-only">根据结果添加条件</span>
                            </button>
                        </div>
                    </div>
                </VNextInspectorSection>

                <ProgramStructureInspector
                    v-if="statement.kind !== 'call' && structureEditorAvailable"
                    :statement="statement"
                    :function-return-type="functionReturnType"
                    :function-contracts="functionContracts"
                    :project-function-ids="projectFunctionIds"
                    :available-values="availableValues"
                    :diagnostics-by-value-id="diagnosticsByValueId"
                    :review-retry-required="retryReviewRequired"
                    :target-options="targetOptions"
                    :busy="busy"
                    :can-add-if-branch="supports('add_if_branch')"
                    :can-remove-if-branch="supports('remove_if_branch')"
                    @command="emit('command', $event)"
                    @open-value-editor="emit('openValueEditor', $event)"
                />

                <div v-else-if="statement.kind !== 'call' && !showsNoConfiguration" class="structure-editor-notice" role="note">
                    <strong>此结构已完整保存</strong>
                    <span>当前服务尚未开放此结构的字段命令，因此这里不会显示无法保存的表单。</span>
                </div>

                <p v-if="showsNoConfiguration" class="no-configuration">此语句无需配置参数。</p>

                <details v-if="supports('set_step_label')" class="secondary-settings app-inspector-disclosure">
                    <summary>步骤备注</summary>
                    <label>
                        <span class="sr-only">步骤备注</span>
                        <input
                            type="text"
                            :value="statement.step_label || ''"
                            :disabled="busy"
                            placeholder="仅在需要解释时填写"
                            @change="commitStepLabel"
                        />
                    </label>
                </details>
            </div>
        </template>
    </aside>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Check, Copy, GitBranchPlus, LayoutTemplate, MousePointer2, ScanSearch, Wrench } from 'lucide-vue-next'
import { vnextApi } from '../api'
import ProgramParameterControl from './ProgramParameterControl.vue'
import ProgramResultBindingInput from './ProgramResultBindingInput.vue'
import ProgramStructureInspector from './ProgramStructureInspector.vue'
import { statementSummary } from './projection'
import { isProgramTypeCompatible } from './typeCompatibility'
import type {
    AvailableProgramValue,
    ProgramAsset,
    ProgramCaptureRequest,
    ProgramCommand,
    ProgramFunctionContract,
    ProgramNamedOption,
    ProgramParameterContract,
    ProgramStatement,
    ProgramStatementKind,
    ProgramValueEditorRequest,
    ProgramValueNode,
    ProgramValueUpdate,
} from './types'
import type { ExecutionPlatformId, WorkspaceIdentity } from '../types'
import type { ProgramDiagnosticDto } from './serverTypes'
import VNextPaneHeader from '../components/ui/VNextPaneHeader.vue'
import VNextInspectorSection from '../components/ui/VNextInspectorSection.vue'
import VNextWorkspaceState from '../components/ui/VNextWorkspaceState.vue'
import VNextButton from '../components/ui/VNextButton.vue'
import VNextIconButton from '../components/ui/VNextIconButton.vue'

interface InspectorField {
    parameter: ProgramParameterContract
    value: ProgramValueNode | null
}

type VisionFunctionId =
    | 'official.image.find'
    | 'official.image.find_all'
    | 'official.image.wait_visible'
    | 'official.image.wait_hidden'
    | 'official.image.click_once'
    | 'official.image.click_until_hidden'
    | 'official.image.click_position_until_visible'
    | 'official.image.click_position_until_hidden'
    | 'official.text.recognize'
    | 'official.text.match'
    | 'official.text.wait_visible'

interface VisionPreviewResult {
    kind: 'image' | 'ocr'
    preview_data_url: string
    matched: boolean | null
    similarity: number | null
    threshold: number | null
    text: string
    line_count: number
    target_id: string
    captured_at: string
    requested_region: number[]
    actual_region: number[]
    region_clipped: boolean
    region_empty: boolean
}

const props = withDefaults(defineProps<{
    statement: ProgramStatement | null
    functionContract?: ProgramFunctionContract | null
    functionReturnType?: string
    functionContracts?: Record<string, ProgramFunctionContract>
    projectFunctionIds?: string[]
    availableValues?: AvailableProgramValue[]
    assets?: ProgramAsset[]
    diagnosticsByValueId?: Record<string, string[]>
    diagnostics?: ProgramDiagnosticDto[]
    targetOptions?: ProgramNamedOption[]
    platform?: ExecutionPlatformId
    targetContextLabel?: string
    targetContextDetail?: string
    workspace?: WorkspaceIdentity | null
    targetId?: string
    busy?: boolean
    supportedCommands?: ProgramCommand['kind'][]
    editableValueStatementKinds?: ProgramStatementKind[]
}>(), {
    functionContract: null,
    functionReturnType: 'void',
    functionContracts: () => ({}),
    projectFunctionIds: () => [],
    availableValues: () => [],
    assets: () => [],
    diagnosticsByValueId: () => ({}),
    diagnostics: () => [],
    targetOptions: () => [],
    platform: 'windows',
    targetContextLabel: '默认运行目标',
    targetContextDetail: '',
    workspace: null,
    targetId: '',
    busy: false,
    supportedCommands: () => [
        'repair_missing_arguments', 'update_value', 'update_assignment_value', 'update_assignment_target', 'update_if_condition', 'add_if_branch', 'remove_if_branch',
        'update_loop', 'update_return_value', 'update_fail', 'update_try_retry_policy', 'update_catch_clause',
        'update_target_scope', 'update_listen', 'review_retry_risk', 'review_dangerous_call', 'set_result_binding', 'insert_if_from_call_result', 'set_step_label',
    ],
    editableValueStatementKinds: () => ['call'],
})

const emit = defineEmits<{
    command: [command: ProgramCommand]
    capture: [request: ProgramCaptureRequest]
    openValueEditor: [request: ProgramValueEditorRequest]
    locatePlayer: [statementId: string]
}>()

const copyState = ref<'idle' | 'copied' | 'failed'>('idle')
const advancedOpen = ref(false)
const visionPreviewBusy = ref(false)
const visionPreviewError = ref('')
const visionPreviewResult = ref<VisionPreviewResult | null>(null)
const copyMessage = computed(() => {
    if (copyState.value === 'copied') return '已复制语句 ID'
    if (copyState.value === 'failed') return '无法访问剪贴板，语句 ID 未复制'
    return ''
})
let copyResetTimer: ReturnType<typeof setTimeout> | null = null

watch(() => props.statement?.statement_id, () => {
    copyState.value = 'idle'
    advancedOpen.value = false
    if (copyResetTimer) clearTimeout(copyResetTimer)
    copyResetTimer = null
    resetVisionPreview()
})

watch(() => [props.targetId, props.statement?.kind === 'call' ? props.statement.arguments : null], resetVisionPreview, { deep: true })

onBeforeUnmount(() => {
    if (copyResetTimer) clearTimeout(copyResetTimer)
})

const retryReviewRequired = computed(() => Boolean(
    props.statement?.kind === 'try'
    && props.diagnostics.some((item) => item.code === 'PGM-TRY-003' && item.statement_id === props.statement?.statement_id),
))
const dangerReviewRequired = computed(() => Boolean(
    props.statement?.kind === 'call'
    && props.functionContract?.dangerous
    && props.diagnostics.some((item) => item.code === 'PGM-DANGER-001' && item.statement_id === props.statement?.statement_id),
))

const summary = computed(() => props.statement ? statementSummary(props.statement) : '')
const inspectorTitle = computed(() => {
    if (!props.statement) return ''
    if (props.statement.kind === 'call') return props.functionContract?.display_name || props.statement.display_name || '不可用函数'
    return summary.value
})
const inspectorMeta = computed(() => {
    if (props.statement?.kind !== 'call' || !props.statement.result_binding) return ''
    return `→ ${props.statement.result_binding.display_name}`
})
const platformLabel = computed(() => ({
    windows: 'Windows 控件',
    android_adb: 'ADB 控件',
    android_local: 'Android 无障碍',
    no_target: '无操作目标',
}[props.platform]))
const showTargetContext = computed(() => Boolean(
    props.statement?.kind === 'call'
    && props.targetContextDetail
    && props.targetContextDetail !== '继承项目默认目标',
))
const allFields = computed<InspectorField[]>(() => {
    const statement = props.statement
    if (!statement) return []
    if (!supports('update_value') || !props.editableValueStatementKinds.includes(statement.kind)) return []
    if (statement.kind === 'call') {
        return (props.functionContract?.parameters || []).map((parameter) => ({
            parameter,
            value: statement.arguments[parameter.parameter_id] || null,
        }))
    }
    return []
})

function conditionValue(parameterId: string): unknown {
    if (props.statement?.kind !== 'call') return undefined
    const value = props.statement.arguments[parameterId]
    return value?.kind === 'literal' ? value.value : undefined
}

function parameterIsVisible(parameter: ProgramParameterContract): boolean {
    if (parameter.ui?.importance === 'internal') return false
    const rule = parameter.ui?.visible_when
    if (!rule) return true
    if (!rule.parameter_id) return true
    const actual = conditionValue(rule.parameter_id)
    if (rule.operator === 'not_equals') return actual !== rule.value
    if (rule.operator === 'greater_than') return typeof actual === 'number' && actual > Number(rule.value)
    if (rule.operator === 'truthy') return Boolean(actual)
    return actual === rule.value
}

const fields = computed(() => allFields.value.filter((field) => parameterIsVisible(field.parameter)))
const missingFields = computed(() => fields.value.filter((field) => !field.value))
const primaryFields = computed(() => fields.value.filter((field) => field.parameter.ui?.importance !== 'advanced'))
const advancedFields = computed(() => fields.value.filter((field) => field.parameter.ui?.importance === 'advanced'))
const advancedHasErrors = computed(() => advancedFields.value.some((field) => Boolean(
    field.value && props.diagnosticsByValueId[field.value.value_id]?.length,
)))

const showsResultBinding = computed(() => {
    return supports('set_result_binding')
        && props.statement?.kind === 'call'
        && Boolean(props.functionContract && props.functionContract.return_type !== 'void')
})
const compatibleResultLocals = computed(() => {
    const returnType = props.functionContract?.return_type || ''
    const locals = props.availableValues.filter((item) => item.source === 'local'
        && isProgramTypeCompatible(returnType, item.value_type))
    const binding = props.statement?.kind === 'call' ? props.statement.result_binding : null
    if (binding && !binding.declare && !locals.some((item) => item.id === binding.symbol_id)) {
        return [...locals, { source: 'local' as const, id: binding.symbol_id, display_name: binding.display_name, value_type: binding.value_type }]
    }
    return locals
})
const canCreateResultCondition = computed(() => {
    const returnType = props.functionContract?.return_type || ''
    return supports('insert_if_from_call_result')
        && props.statement?.kind === 'call'
        && (returnType === 'bool' || /^optional<.+>$/.test(returnType))
})
const resultConditionHint = computed(() => props.functionContract?.return_type === 'bool'
    ? '在下一行添加“如果结果成立”'
    : '在下一行添加“如果有结果”')

const visionFunctionIds = new Set<VisionFunctionId>([
    'official.image.find', 'official.image.find_all', 'official.image.wait_visible',
    'official.image.wait_hidden', 'official.image.click_once', 'official.image.click_until_hidden',
    'official.image.click_position_until_visible', 'official.image.click_position_until_hidden',
    'official.text.recognize', 'official.text.match', 'official.text.wait_visible',
])
const visionFunctionId = computed<VisionFunctionId | null>(() => {
    if (props.statement?.kind !== 'call') return null
    return visionFunctionIds.has(props.statement.function_id as VisionFunctionId)
        ? props.statement.function_id as VisionFunctionId
        : null
})
const visionPreviewSupported = computed(() => Boolean(visionFunctionId.value))

interface FixedValue { fixed: boolean; value: unknown }

function fixedValue(value: ProgramValueNode | null | undefined): FixedValue {
    if (!value || value.kind === 'unset') return { fixed: true, value: null }
    if (value.kind === 'literal') return { fixed: true, value: value.value }
    if (value.kind === 'asset_ref') return { fixed: true, value: value.asset_id }
    if (value.kind === 'json') return { fixed: true, value: value.payload }
    if (value.kind === 'list') {
        const items = value.items.map(fixedValue)
        return items.every((item) => item.fixed)
            ? { fixed: true, value: items.map((item) => item.value) }
            : { fixed: false, value: null }
    }
    if (value.kind === 'record') {
        const entries = Object.entries(value.fields).map(([key, child]) => [key, fixedValue(child)] as const)
        return entries.every(([, child]) => child.fixed)
            ? { fixed: true, value: Object.fromEntries(entries.map(([key, child]) => [key, child.value])) }
            : { fixed: false, value: null }
    }
    return { fixed: false, value: null }
}

function argumentValue(parameterId: string): FixedValue {
    if (props.statement?.kind !== 'call') return { fixed: false, value: null }
    const direct = props.statement.arguments[parameterId]
    if (direct) return fixedValue(direct)
    const stableSuffix = `.parameter.${parameterId}`
    const entry = Object.entries(props.statement.arguments).find(([id]) => id.endsWith(stableSuffix))
    return fixedValue(entry?.[1])
}

function regionValue(value: unknown): number[] | null {
    if (value === null || value === undefined || value === '') return null
    if (Array.isArray(value) && value.length === 4) return value.map(Number)
    if (typeof value === 'object') {
        const record = value as Record<string, unknown>
        const tuple = record.kind === 'rect'
            ? [record.x, record.y, record.width, record.height]
            : [record['rect.field.x'], record['rect.field.y'], record['rect.field.width'], record['rect.field.height']]
        if (tuple.every((item) => Number.isFinite(Number(item)))) return tuple.map(Number)
    }
    return null
}

const visionPreviewBlockedReason = computed(() => {
    if (!props.workspace) return '请先打开项目'
    if (!props.targetId) return '请先选择运行目标'
    if (props.platform === 'android_local') return 'Android 本机画面请在 Player 中测试'
    if (props.statement?.kind !== 'call') return ''
    const relevant = visionFunctionId.value?.startsWith('official.image.')
        ? ['image', 'similarity', 'region']
        : ['region', 'language', 'preprocess', 'text', 'mode']
    if (relevant.some((id) => !argumentValue(id).fixed)) return '当前参数含运行时变量，请运行流程验证'
    if (visionFunctionId.value?.startsWith('official.image.') && !String(argumentValue('image').value || '')) {
        return '请先选择图片资源'
    }
    return ''
})

const visionPreviewSummary = computed(() => {
    const result = visionPreviewResult.value
    if (!result) return ''
    if (result.region_empty) return result.kind === 'ocr' ? '区域与当前画面无交集' : '未匹配 · 区域无有效像素'
    if (result.kind === 'ocr') return result.text ? `识别到：${result.text}` : '当前区域未识别到文字'
    const score = result.similarity === null ? '不可用' : `${Math.round(Number(result.similarity) * 100)}%`
    return result.matched ? `已匹配 · 相似度 ${score}` : `未匹配 · 最高相似度 ${score}`
})

const visionPreviewDetail = computed(() => {
    const result = visionPreviewResult.value
    if (!result) return ''
    const [x = 0, y = 0, width = 0, height = 0] = result.actual_region || []
    const details = result.region_empty
        ? ['实际区域无可分析像素']
        : [`实际区域 (${x}, ${y}) ${width}×${height}`]
    if (result.region_clipped) details.push('已按当前画面裁剪')
    if (result.kind === 'image') {
        details.push(`当前阈值 ${Math.round(Number(result.threshold || 0) * 100)}%`)
        return details.join(' · ')
    }
    details.push(`${result.line_count} 行文字`)
    if (result.threshold !== null) details.push(`二值化阈值 ${result.threshold}`)
    if (result.matched !== null) details.push(result.matched ? '符合文字条件' : '不符合文字条件')
    return details.join(' · ')
})
const structureCommandByKind: Partial<Record<Exclude<ProgramStatementKind, 'call'>, ProgramCommand['kind']>> = {
    assignment: 'update_assignment_value',
    if: 'update_if_condition',
    loop: 'update_loop',
    return: 'update_return_value',
    fail: 'update_fail',
    try: 'update_try_retry_policy',
    target_scope: 'update_target_scope',
    listen: 'update_listen',
}
const structureEditorAvailable = computed(() => {
    const statement = props.statement
    if (!statement || statement.kind === 'call') return false
    const command = structureCommandByKind[statement.kind]
    return Boolean(command && supports(command))
})
const showsNoConfiguration = computed(() => {
    if (!props.statement || props.statement.kind === 'call' && !props.functionContract) return false
    if (props.statement.kind === 'break' || props.statement.kind === 'continue') return true
    return props.statement.kind === 'call' && fields.value.length === 0 && !showsResultBinding.value
})

function supports(command: ProgramCommand['kind']): boolean {
    return props.supportedCommands.includes(command)
}

function syncAdvancedOpen(event: Event): void {
    advancedOpen.value = (event.currentTarget as HTMLDetailsElement).open
}

function updateValue(update: ProgramValueUpdate): void {
    emit('command', {
        kind: 'update_value',
        statement_id: update.statement_id,
        parameter_id: update.parameter_id,
        value_id: update.value_id,
        next: update.next,
    })
}

function repairMissingArguments(): void {
    if (!props.statement || props.statement.kind !== 'call' || !missingFields.value.length) return
    emit('command', {
        kind: 'repair_missing_arguments',
        statement_id: props.statement.statement_id,
    })
}

function commitResultBinding(target: Extract<ProgramCommand, { kind: 'set_result_binding' }>['target']): void {
    if (!props.statement) return
    emit('command', {
        kind: 'set_result_binding',
        statement_id: props.statement.statement_id,
        target,
    })
}

function createResultCondition(): void {
    if (!props.statement || props.statement.kind !== 'call') return
    emit('command', {
        kind: 'insert_if_from_call_result',
        statement_id: props.statement.statement_id,
    })
}

function commitStepLabel(event: Event): void {
    if (!props.statement) return
    const stepLabel = (event.target as HTMLInputElement).value.trim()
    emit('command', {
        kind: 'set_step_label',
        statement_id: props.statement.statement_id,
        step_label: stepLabel || null,
    })
}

function reviewDangerousCall(): void {
    if (!props.statement || props.statement.kind !== 'call') return
    emit('command', {
        kind: 'review_dangerous_call',
        statement_id: props.statement.statement_id,
    })
}

function resetVisionPreview(): void {
    visionPreviewError.value = ''
    visionPreviewResult.value = null
}

async function runVisionPreview(): Promise<void> {
    const functionId = visionFunctionId.value
    const statement = props.statement
    if (!functionId || statement?.kind !== 'call' || !props.workspace || !props.targetId || visionPreviewBlockedReason.value) return
    visionPreviewBusy.value = true
    visionPreviewError.value = ''
    visionPreviewResult.value = null
    try {
        const region = argumentValue('region')
        const image = argumentValue('image')
        const similarity = argumentValue('similarity')
        const language = argumentValue('language')
        const preprocess = argumentValue('preprocess')
        const text = argumentValue('text')
        const mode = argumentValue('mode')
        visionPreviewResult.value = await vnextApi.previewVision(props.workspace, {
            target_id: props.targetId,
            function_id: functionId,
            region: regionValue(region.value),
            image_asset_id: String(image.value || ''),
            similarity: typeof similarity.value === 'number' ? similarity.value : 0.85,
            language: String(language.value || 'auto'),
            preprocess: preprocess.value && typeof preprocess.value === 'object'
                ? preprocess.value as Record<string, unknown>
                : {},
            expected_text: String(text.value || ''),
            match_mode: String(mode.value || 'contains'),
        })
    } catch (error) {
        visionPreviewError.value = error instanceof Error ? error.message : '当前画面测试失败'
    } finally {
        visionPreviewBusy.value = false
    }
}

async function copyStatementId(): Promise<void> {
    const statementId = props.statement?.statement_id
    if (!statementId) return
    try {
        if (!navigator.clipboard?.writeText) throw new Error('clipboard unavailable')
        await navigator.clipboard.writeText(statementId)
        copyState.value = 'copied'
    } catch {
        copyState.value = 'failed'
    }
    if (copyResetTimer) clearTimeout(copyResetTimer)
    copyResetTimer = setTimeout(() => { copyState.value = 'idle' }, 1800)
}

</script>

<style scoped>
.statement-inspector {
    display: flex;
    min-width: 0;
    height: 100%;
    flex-direction: column;
    overflow: hidden;
    border-inline-start: 1px solid var(--app-border-subtle);
    background: var(--app-bg-panel);
    color: var(--app-text-regular);
    container-type: inline-size;
}

.inspector-header {
    display: flex;
    min-height: var(--app-height-pane-header);
    flex: 0 0 auto;
    align-items: center;
    justify-content: space-between;
    gap: var(--app-spacing-xs);
    padding: 0 var(--app-pane-inline-padding);
    border-bottom: 1px solid var(--app-border-subtle);
    background: var(--app-bg-sidebar);
}

.inspector-heading {
    display: flex;
    min-width: 0;
    flex: 1;
    align-items: center;
}

.inspector-header-actions {
    display: flex;
    flex: 0 0 auto;
    gap: var(--app-spacing-xs);
}

.inspector-header-actions button {
    width: 28px;
    height: var(--app-control-compact);
    display: grid;
    place-items: center;
    border: 0;
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-muted);
    cursor: pointer;
}

.inspector-header-actions button:hover { background: var(--app-bg-hover); color: var(--app-text-primary); }
.inspector-header-actions button:focus-visible { outline: 0; box-shadow: var(--focus-ring); }

.inspector-header strong {
    overflow: hidden;
    color: var(--app-text-primary);
    font-size: var(--app-font-sm);
    font-weight: 600;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.target-context {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: var(--app-spacing-xs);
    align-items: center;
    margin: 0 var(--app-spacing-md);
    padding: var(--app-spacing-xs) var(--app-spacing-sm);
    border: 1px solid color-mix(in srgb, var(--app-border-default) 72%, transparent);
    border-radius: var(--app-radius-sm);
    background: var(--app-bg-input);
    color: var(--app-text-secondary);
    font-size: var(--app-font-xs);
}

.target-context strong {
    overflow: hidden;
    color: var(--app-text-primary);
    font-weight: 600;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.target-context p {
    grid-column: 2;
    margin: -2px 0 0;
    color: var(--app-text-tertiary);
    line-height: 1.45;
}

.inspector-body {
    flex: 1;
}

.advanced-parameters {
    margin: var(--app-form-field-gap) 0 0;
}

.advanced-parameters > summary {
    border-top: 1px solid var(--app-border-subtle);
}

.advanced-parameters > summary:hover { color: var(--app-text-primary); }
.advanced-parameters > summary small { color: var(--app-color-danger); font-size: var(--app-font-caption); }
.advanced-parameters[open] > summary { margin-bottom: var(--app-form-heading-field-gap); }

.secondary-settings label {
    display: flex;
    flex-direction: column;
    gap: var(--app-form-label-control-gap);
    margin-top: 0;
    color: var(--app-text-regular);
    font-size: var(--app-font-sm);
    font-weight: 500;
}

.secondary-settings input {
    width: 100%;
    min-height: var(--app-control-default);
    padding: 0 var(--app-spacing-sm);
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    outline: 0;
    background: var(--app-bg-input);
    color: var(--app-text-primary);
    font: inherit;
}

.secondary-settings input:hover { border-color: var(--app-border-strong); }

.secondary-settings input:focus-visible {
    border-color: var(--app-color-primary);
    box-shadow: var(--focus-ring);
}

.result-control-row {
    display: grid;
    grid-template-columns: minmax(72px, .34fr) minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--app-spacing-xs);
    min-width: 0;
}

.result-control-label {
    min-width: 0;
    overflow: hidden;
    color: var(--app-text-regular);
    font-size: var(--app-font-sm);
    font-weight: 500;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.result-condition-action {
    display: grid;
    place-items: center;
}

.result-condition-action .app-field-action {
    width: var(--app-control-default);
    height: var(--app-control-default);
}

.no-configuration {
    margin: var(--app-spacing-sm) 0 0;
    color: var(--app-text-secondary);
    font-size: var(--app-font-xs);
    line-height: 1.6;
}

.danger-review {
    margin-top: var(--app-spacing-md);
    padding: var(--app-spacing-md);
    border: 1px solid color-mix(in srgb, var(--app-color-warning) 55%, var(--app-border-default));
    border-radius: var(--app-radius-sm);
    background: var(--app-bg-sidebar);
}
.danger-review strong { color: var(--app-text-primary); font-size: var(--app-font-sm); }
.danger-review p { margin: var(--app-spacing-xs) 0 var(--app-spacing-sm); color: var(--app-text-secondary); font-size: var(--app-font-xs); line-height: 1.55; }
.danger-review .app-inline-action { color: var(--app-text-primary); }

.vision-preview-action { margin-inline-end: -7px; }
.vision-preview-feedback { margin-top: var(--app-form-field-gap); }
.vision-preview-feedback > p { margin: 0; }

.vision-preview-result {
    width: 100%;
    display: grid;
    grid-template-columns: 88px minmax(0, 1fr);
    align-items: center;
    gap: var(--app-spacing-sm);
    margin: var(--app-spacing-xs) 0 0;
    padding: var(--app-spacing-xs);
    border: 1px solid var(--app-border-subtle);
    border-radius: var(--app-radius-sm);
    background: var(--app-bg-input);
}

.vision-preview-result img {
    width: 88px;
    height: 56px;
    display: block;
    object-fit: contain;
    border-radius: calc(var(--app-radius-sm) - 2px);
    background: var(--app-bg-canvas);
}

.vision-preview-empty {
    width: 88px;
    height: 56px;
    display: grid;
    place-items: center;
    align-content: center;
    gap: 2px;
    border-radius: calc(var(--app-radius-sm) - 2px);
    background: var(--app-bg-canvas);
    color: var(--app-text-tertiary);
    font-size: var(--app-font-caption);
}

.vision-preview-empty svg { width: 16px; height: 16px; }

.vision-preview-result figcaption { min-width: 0; display: grid; gap: 2px; }
.vision-preview-result strong,
.vision-preview-result span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vision-preview-result strong { color: var(--app-text-primary); font-size: var(--app-font-xs); font-weight: 600; }
.vision-preview-result span { color: var(--app-text-secondary); font-size: var(--app-font-caption); }
.is-spinning { animation: vision-preview-spin 800ms linear infinite; }
@keyframes vision-preview-spin { to { transform: rotate(360deg); } }

.structure-editor-notice {
    display: flex;
    flex-direction: column;
    gap: var(--app-spacing-xs);
    margin-top: var(--app-spacing-md);
    padding: var(--app-spacing-md);
    border: 1px solid var(--app-border-subtle);
    border-radius: var(--app-radius-sm);
    background: var(--app-bg-sidebar);
    color: var(--app-text-secondary);
    font-size: var(--app-font-xs);
    line-height: 1.6;
}

.structure-editor-notice strong { color: var(--app-text-primary); font-weight: 600; }

.no-configuration { padding: var(--app-spacing-lg) 0; }

.contract-error {
    margin-top: var(--app-spacing-md);
    padding: var(--app-spacing-sm);
    border: 1px solid var(--app-color-danger);
    border-radius: var(--app-radius-sm);
    background: var(--app-color-danger-soft);
    color: var(--app-text-regular);
    font-size: var(--app-font-xs);
    line-height: 1.6;
}

.parameter-recovery {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--app-spacing-xs);
    margin-bottom: var(--app-form-field-gap);
    padding: var(--app-spacing-xs) var(--app-spacing-sm);
    border: 1px solid color-mix(in srgb, var(--app-color-warning) 45%, var(--app-border-default));
    border-radius: var(--app-radius-sm);
    background: var(--app-bg-input);
    color: var(--app-text-secondary);
    font-size: var(--app-font-xs);
    line-height: 1.45;
}

.parameter-recovery span { min-width: 0; }
.parameter-recovery button { flex: 0 0 auto; }

.secondary-settings {
    margin: 0;
    padding: var(--app-spacing-xs) 0 var(--app-form-section-padding);
    border-bottom: 1px solid var(--app-border-subtle);
}

.secondary-settings summary {
    font-weight: 600;
}
.secondary-settings[open] summary { margin-bottom: var(--app-form-label-control-gap); }

.inspector-empty {
    display: flex;
    min-height: 220px;
    flex: 1;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--app-spacing-sm);
    padding: var(--app-spacing-xl);
    color: var(--app-text-secondary);
    text-align: center;
}

.inspector-empty strong {
    color: var(--app-text-primary);
    font-size: var(--app-font-sm);
    font-weight: 600;
}

.inspector-empty p {
    max-width: 30ch;
    margin: 0;
    font-size: var(--app-font-xs);
    line-height: 1.6;
}

@container (max-width: 244px) {
    .result-control-row {
        grid-template-columns: minmax(0, 1fr) auto;
    }

    .result-control-label {
        grid-column: 1 / -1;
    }
}

</style>
