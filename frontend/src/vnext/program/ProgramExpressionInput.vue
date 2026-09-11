<template>
    <div ref="root" class="expression-composer" :class="{ 'is-editing': editing, 'has-error': Boolean(error) || (!editing && invalid) }" @focusout="handleFocusOut">
        <button
            v-if="!editing"
            type="button"
            class="expression-surface"
            :class="{ 'is-multiline': multiline }"
            data-control-surface
            :disabled="disabled"
            :aria-label="`${label}：${displaySummary}`"
            :aria-invalid="(!editing && invalid) || Boolean(error) ? 'true' : undefined"
            :aria-describedby="resolvedDescribedBy"
            @click="beginEditing"
        >
            <span class="expression-value" :title="displaySummary">
                <span v-if="value.kind === 'unset'" class="expression-placeholder">{{ placeholder }}</span>
                <span v-else-if="value.kind === 'literal' && value.value === null && effectiveDefaultLabel" class="expression-default">
                    {{ effectiveDefaultLabel }}
                </span>
                <span v-for="(segment, index) in segments" v-else :key="`${index}:${segment.text}`" class="expression-token" :data-tone="segment.tone">
                    {{ segment.text }}
                </span>
            </span>
            <span v-if="adornment" class="app-control-adornment">{{ adornment }}</span>
        </button>

        <template v-else>
            <textarea
                v-if="multiline"
                ref="input"
                v-model="draftText"
                class="expression-editor is-multiline"
                role="combobox"
                :aria-label="label"
                :aria-expanded="showCompletion"
                :aria-controls="`${value.value_id}-expression-completion`"
                :aria-invalid="Boolean(error) ? 'true' : undefined"
                :aria-describedby="resolvedDescribedBy"
                :placeholder="placeholder"
                autocomplete="off"
                spellcheck="false"
                aria-autocomplete="list"
                @input="handleInput"
                @click="syncCaret"
                @keyup="syncCaret"
                @compositionstart="composing = true"
                @compositionend="handleCompositionEnd"
                @keydown.ctrl.enter.exact="handleMultilineCommit"
                @keydown.meta.enter.exact="handleMultilineCommit"
                @keydown.esc.prevent="cancel"
                @keydown.down="focusFirstSuggestion"
                @keydown.ctrl.space.prevent="openDiscovery"
                @keydown.meta.space.prevent="openDiscovery"
            />
            <input
                v-else
                ref="input"
                v-model="draftText"
                class="expression-editor"
                type="text"
                role="combobox"
                :aria-label="label"
                :aria-expanded="showCompletion"
                :aria-controls="`${value.value_id}-expression-completion`"
                :aria-invalid="Boolean(error) ? 'true' : undefined"
                :aria-describedby="resolvedDescribedBy"
                :placeholder="placeholder"
                autocomplete="off"
                spellcheck="false"
                aria-autocomplete="list"
                @input="handleInput"
                @click="syncCaret"
                @keyup="syncCaret"
                @compositionstart="composing = true"
                @compositionend="handleCompositionEnd"
                @keydown.enter="handleSingleLineEnter"
                @keydown.esc.prevent="cancel"
                @keydown.down.prevent="focusFirstSuggestion"
                @keydown.ctrl.space.prevent="openDiscovery"
                @keydown.meta.space.prevent="openDiscovery"
            />
            <section v-if="showCompletion" :id="`${value.value_id}-expression-completion`" class="value-suggestions" role="listbox" aria-label="表达式补全">
                <template v-if="showValues">
                <template v-if="memberContext">
                <div class="suggestion-heading">
                    <strong>{{ memberHeading }}</strong>
                    <span>{{ memberSteps.length }} 项</span>
                </div>
                <p v-if="memberContext.guardRequired" class="member-guard-note" role="note">
                    “{{ memberContext.source.display_name }}”可能无结果。可以直接使用；若实际为空，本次运行会停在使用它的语句。若无结果是正常情况，再添加“有结果”判断。
                </p>
                <button
                    v-for="item in memberSteps"
                    :key="item.key"
                    type="button"
                    class="value-suggestion member-suggestion"
                    role="option"
                    :disabled="Boolean(item.disabledReason)"
                    :title="item.disabledReason || (item.canDrill ? `继续选择${item.displayName}的字段` : `插入${item.displayName}`)"
                    @mousedown.prevent
                    @click="insertMemberStep(item)"
                    @keydown="onSuggestionKeydown($event)"
                >
                    <span data-source="member">字段</span>
                    <strong>{{ item.displayName }}</strong>
                    <small>{{ programTypeDisplayName(item.valueType) }}<template v-if="item.canDrill"> · 可继续选择</template></small>
                </button>
                <p v-if="!memberSteps.length && !memberCatalogLoading">当前字段没有可继续选择的内容。</p>
                <p v-else-if="memberCatalogLoading">正在读取字段…</p>
                </template>
                <template v-else>
                <div class="suggestion-heading">
                    <strong>选择已有值</strong>
                    <span>{{ filteredValues.length }} 项</span>
                </div>
                <div v-for="group in suggestionGroups" :key="group.label" class="suggestion-group">
                    <small v-if="suggestionGroups.length > 1" class="suggestion-group-label">{{ group.label }}</small>
                    <button
                        v-for="item in group.items"
                        :key="`${item.source}:${item.id}`"
                        type="button"
                        class="value-suggestion"
                        role="option"
                        @mousedown.prevent
                        @click="insertValue(item)"
                        @keydown="onSuggestionKeydown($event)"
                    >
                        <span :data-source="item.source">{{ item.source === 'project' ? '项目' : '局部' }}</span>
                        <strong>{{ item.display_name }}</strong>
                        <small>{{ programTypeDisplayName(item.value_type) }}</small>
                    </button>
                </div>
                <p v-if="!filteredValues.length">当前作用域没有匹配的已有值。</p>
                </template>
                </template>
                <template v-else-if="showOperationDirectory">
                    <div class="suggestion-heading">
                        <strong>{{ operationHeading }}</strong>
                        <span>{{ directoryOperations.length }} 项</span>
                    </div>
                    <div v-for="group in operationGroups" :key="group.label" class="suggestion-group">
                        <small v-if="operationGroups.length > 1" class="suggestion-group-label">{{ group.label }}</small>
                        <button
                            v-for="item in group.items"
                            :key="item.key"
                            type="button"
                            class="operation-suggestion"
                            role="option"
                            :disabled="directoryOperationDisabled(item) || Boolean(operationInsertBusy)"
                            :title="directoryOperationTitle(item)"
                            @mousedown.prevent
                            @click="insertDirectoryOperation(item)"
                            @keydown="onSuggestionKeydown($event)"
                        >
                            <strong>{{ item.discovery.syntax_name }}</strong>
                            <span>{{ item.discovery.description }}</span>
                            <small v-if="operationInsertBusy === item.key">正在准备可用参数…</small>
                            <small v-else-if="item.candidate">{{ operationCandidateSignature(item.candidate) }}<template v-if="conditionIntermediateResult(item)"> · 继续输入比较符</template></small>
                            <small v-else-if="conditionIntermediateResult(item)">可先生成{{ resultTypeHint(item.discovery.result_type_hints) }}，再继续比较</small>
                            <small v-else>{{ item.disabledReason }}<template v-if="item.discovery.result_type_hints.length"> · 结果为 {{ resultTypeHint(item.discovery.result_type_hints) }}</template></small>
                        </button>
                    </div>
                    <p v-if="!directoryOperations.length">没有找到相关纯值操作。可以按 Ctrl+Space 查看全部写法。</p>
                </template>
                <template v-else>
                    <div class="suggestion-heading">
                        <strong>{{ operatorOnly ? '继续计算或判断' : (activeParameterLabel || `${typeLabel}可用写法`) }}</strong>
                        <span>Ctrl+Space</span>
                    </div>
                    <div v-if="!operatorOnly && currentParameterChoices.length" class="suggestion-group">
                        <small class="suggestion-group-label">固定选项</small>
                        <button v-for="choice in currentParameterChoices" :key="String(choice.value)" type="button" class="discovery-suggestion" role="option" @mousedown.prevent @click="insertLiteral(String(choice.label))" @keydown="onSuggestionKeydown($event)">
                            <strong>{{ choice.label }}</strong><span>当前参数允许的选项</span>
                        </button>
                    </div>
                    <div v-if="!operatorOnly && literalSuggestions.length" class="suggestion-group">
                        <small class="suggestion-group-label">直接填写</small>
                        <button v-for="item in literalSuggestions" :key="`${item.label}:${item.insert_text}`" type="button" class="discovery-suggestion" role="option" @mousedown.prevent @click="insertLiteral(item.insert_text)" @keydown="onSuggestionKeydown($event)">
                            <strong>{{ item.label }}</strong><span>{{ item.description }}</span><small v-if="item.insert_text">{{ item.insert_text }}</small>
                        </button>
                    </div>
                    <div v-if="!operatorOnly" class="suggestion-group">
                        <small class="suggestion-group-label">已有值</small>
                        <button type="button" class="discovery-suggestion" role="option" @mousedown.prevent @click="insertValueTrigger" @keydown="onSuggestionKeydown($event)">
                            <strong>@ 变量或结果</strong><span>先选值本体，之后输入 . 查看字段</span>
                        </button>
                    </div>
                    <div v-if="!operatorOnly && namespaceSuggestions.length" class="suggestion-group">
                        <small class="suggestion-group-label">纯值操作</small>
                        <button v-for="item in namespaceSuggestions" :key="item.name" type="button" class="discovery-suggestion namespace-suggestion" role="option" @mousedown.prevent @click="insertNamespace(item.name)" @keydown="onSuggestionKeydown($event)">
                            <strong>{{ item.name }}.</strong><span>{{ item.description }}</span><small>{{ item.compatible_count ? `${item.compatible_count} 项适用` : '当前字段仅可查看' }}</small>
                        </button>
                    </div>
                    <div v-if="operatorSuggestions.length" class="suggestion-group">
                        <small class="suggestion-group-label">运算与判断</small>
                        <button v-for="item in operatorSuggestions" :key="`${item.label}:${item.insert_text}`" type="button" class="discovery-suggestion" role="option" @mousedown.prevent @click="insertLiteral(item.insert_text)" @keydown="onSuggestionKeydown($event)">
                            <strong>{{ item.label }}</strong><span>{{ item.description }}</span><small>{{ item.insert_text.trim() }}</small>
                        </button>
                    </div>
                    <p v-if="!operatorOnly && catalogLoading">正在读取当前字段的可用写法…</p>
                    <p v-else-if="!operatorOnly && !currentCatalog?.discovery">当前仍可直接输入；语法目录暂时不可用，请稍后重试。</p>
                </template>
            </section>
        </template>
        <p v-if="activeParameterHint" class="parameter-hint" role="status">{{ activeParameterHint }}</p>
        <section v-if="helpOpen" class="expression-help" aria-label="表达式输入帮助">
            <header><strong>{{ typeLabel }}怎么填写</strong><button type="button" @click="emit('closeHelp')">关闭</button></header>
            <p>{{ helpText || helpInstruction }}</p>
            <button v-for="example in helpExamples" :key="example" type="button" @click="useExample(example)">{{ example }}</button>
            <small>这里只能组合不会等待或操作外部目标的纯值函数。普通函数仍作为流程语句插入。</small>
        </section>
        <p v-if="error" :id="localErrorId" class="expression-error" role="alert">{{ error }}</p>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { programTypeDisplayName } from './typePresentation'
import {
    expressionNamespaces,
    expressionHelpExamples,
    normalizeSyntaxKey,
    operationDirectorySuggestions,
    operationSignature,
    operationSuggestions,
    operationSyntaxAliases,
    type ExpressionOperationDirectorySuggestion,
    type ExpressionOperationSuggestion,
} from './operationSyntax'
import {
    expressionSegments,
    expressionText,
    isInlineExpressionEditable,
    parseExpressionDraft,
    preserveExpressionValueIds,
    selectorBindingsForType,
    selectorResultType,
} from './expressionComposer'
import type { ProgramValueCatalogDto, PureOperationCandidateDto } from './serverTypes'
import type { AvailableProgramValue, LocalSymbolDefinition, ProgramValueNode } from './types'
import { isProgramTypeCompatible } from './typeCompatibility'

const props = withDefaults(defineProps<{
    label: string
    value: ProgramValueNode
    expectedType: string
    availableValues?: AvailableProgramValue[]
    disabled?: boolean
    helpOpen?: boolean
    placeholder?: string
    helpText?: string
    effectiveDefaultLabel?: string
    adornment?: string
    invalid?: boolean
    describedBy?: string
    multiline?: boolean
    resolveCatalog?: ((expectedType: string, scopeBindings?: LocalSymbolDefinition[]) => Promise<ProgramValueCatalogDto>) | null
}>(), { availableValues: () => [], disabled: false, helpOpen: false, placeholder: '', helpText: '', effectiveDefaultLabel: '', adornment: '', invalid: false, describedBy: '', multiline: false, resolveCatalog: null })

const emit = defineEmits<{ replace: [value: ProgramValueNode]; closeHelp: []; editingChange: [editing: boolean] }>()
const root = ref<HTMLElement | null>(null)
const input = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)
const editing = ref(false)
const composing = ref(false)
const draftText = ref('')
const error = ref('')
const localErrorId = computed(() => `${props.value.value_id}-expression-error`)
const resolvedDescribedBy = computed(() => [props.describedBy, error.value ? localErrorId.value : ''].filter(Boolean).join(' ') || undefined)
const showValues = ref(false)
const completionDismissed = ref(false)
const manualCompletion = ref(false)
const catalogLoading = ref(false)
const operationInsertBusy = ref('')
const caretPosition = ref<number | null>(null)
const selectionEndPosition = ref<number | null>(null)
const catalogs = ref<ProgramValueCatalogDto[]>([])
type CatalogRequest = { type: string; bindings: LocalSymbolDefinition[] }
type CatalogSource = ProgramValueCatalogDto['sources'][number]
type RecordPathField = ProgramValueCatalogDto['members'][number]['path'][number]
interface RootCompletionContext { query: string; start: number; end: number }
interface MemberSyntaxContext {
    sourceKind: 'local' | 'project'
    sourceName: string
    completedNames: string[]
    query: string
    queryStart: number
    end: number
}
interface MemberCompletionContext extends MemberSyntaxContext {
    source: AvailableProgramValue
    sourceInfo: CatalogSource | null
    currentType: string
    currentRecord: ProgramValueCatalogDto['record']
    prefix: RecordPathField[]
    guardRequired: boolean
}
interface MemberStep {
    key: string
    displayName: string
    valueType: string
    fieldId: string
    canDrill: boolean
    disabledReason: string
}
const catalogRequests = new Map<string, Promise<void>>()
const memberCatalogLoading = ref(false)
let memberCatalogLoadRevision = 0
let activeCatalogLoads = 0

const segments = computed(() => expressionSegments(props.value))
const plainSummary = computed(() => expressionText(props.value))
const displaySummary = computed(() => {
    if (props.value.kind === 'literal' && props.value.value === null && props.effectiveDefaultLabel) {
        return props.effectiveDefaultLabel
    }
    return plainSummary.value
})
const typeLabel = computed(() => programTypeDisplayName(props.expectedType))
function editableText(value: ProgramValueNode): string {
    if (value.kind === 'unset') return ''
    if (value.kind === 'literal' && value.value === null && props.effectiveDefaultLabel) return ''
    return expressionText(value)
}
const helpInstruction = computed(() => {
    if (props.expectedType === 'duration') return '直接填写“500 毫秒”“2 秒”或“1 分钟”；输入 @ 可选择已有持续时间。'
    if (props.expectedType === 'bool') return '输入 @ 先选择变量或结果；选择结构化结果后输入 . 查看字段。多个条件可使用“且、或、非”。'
    if (['int64', 'float64', 'percentage'].includes(props.expectedType)) return '直接填写数字；输入 @ 先选择已有值，选择结构化结果后输入 . 查看字段；也可以进行加减或调用数值操作。'
    if (props.expectedType === 'string') return '直接填写文字；输入 @ 先选择变量或结果，选择后输入 . 查看它的字段；输入“文本.”可查找替换、提取等操作。'
    return '直接填写普通值；输入 @ 先选择变量或结果，选择后输入 . 查看它的字段；输入“类型.”查找兼容的纯值操作。'
})
const helpExamples = computed(() => {
    const matching = props.availableValues.filter((item) => isProgramTypeCompatible(item.value_type, props.expectedType))
    const token = (item: AvailableProgramValue) => `@${item.display_name}`
    if (props.expectedType === 'bool') {
        const booleans = props.availableValues.filter((item) => isProgramTypeCompatible(item.value_type, 'bool'))
        const numbers = props.availableValues.filter((item) => ['int64', 'float64', 'percentage'].includes(item.value_type))
        return [
            '开启',
            booleans[0] ? token(booleans[0]) : '18 大于等于 3',
            numbers[0] ? `${token(numbers[0])} 大于等于 ${numbers[1] ? token(numbers[1]) : '18'}` : '18 大于等于 3',
        ]
    }
    if (['int64', 'float64', 'percentage'].includes(props.expectedType)) {
        return ['18', matching[0] ? `${token(matching[0])} + 3` : '18 + 3', '数值.取较大值(18, 3)']
    }
    if (props.expectedType === 'duration') {
        return ['500 毫秒', '2 秒', matching[0] ? token(matching[0]) : '1 分钟']
    }
    if (props.expectedType === 'string') {
        return ['直接输入普通内容', ...(matching[0] ? [token(matching[0])] : []), '文本.替换("旧服公告", "旧服", "新服")']
    }
    return expressionHelpExamples(props.expectedType)
})
const placeholder = computed(() => props.placeholder || (props.expectedType === 'bool'
    ? '例如：[局部 · 当前体力] 大于等于 [项目 · 最低体力]'
    : `输入${typeLabel.value}，或按 @ 选择已有值`))
function optionalInner(valueType: string): string {
    return valueType.startsWith('optional<') && valueType.endsWith('>') ? valueType.slice(9, -1) : ''
}
function recordTypeId(valueType: string): string {
    const unwrapped = optionalInner(valueType) || valueType
    if (unwrapped.startsWith('record<') && unwrapped.endsWith('>')) return unwrapped.slice(7, -1)
    return unwrapped.startsWith('record.') ? unwrapped.slice(7) : unwrapped
}
function recordCatalog(valueType: string): ProgramValueCatalogDto['record'] {
    const typeId = recordTypeId(valueType)
    return catalogs.value.find((catalog) => catalog.record?.type_id === typeId)?.record || null
}
function caretBefore(): { text: string; end: number } {
    const end = caretPosition.value ?? input.value?.selectionStart ?? draftText.value.length
    return { text: draftText.value.slice(0, end), end }
}
const rootCompletion = computed<RootCompletionContext | null>(() => {
    const before = caretBefore()
    const match = /@([^@\s,，()（）\u005B\u005D]*)$/u.exec(before.text)
    if (!match) return null
    return { query: match[1].trim().toLocaleLowerCase('zh-CN'), start: match.index, end: before.end }
})
const memberSyntax = computed<MemberSyntaxContext | null>(() => {
    const before = caretBefore()
    const match = /\[(局部|项目)\s*[·.]\s*([^\]]+)\]((?:[。.][\p{L}\p{N}_]*)+)$/u.exec(before.text)
    if (!match) return null
    const parts = match[3].slice(1).split(/[。.]/u)
    const query = parts.pop() || ''
    return {
        sourceKind: match[1] === '项目' ? 'project' : 'local',
        sourceName: match[2].trim(),
        completedNames: parts,
        query: normalizeSyntaxKey(query),
        queryStart: before.end - query.length,
        end: before.end,
    }
})
const operationQuery = computed(() => {
    const position = caretPosition.value ?? input.value?.selectionStart ?? draftText.value.length
    const before = draftText.value.slice(0, position)
    const match = /(?:^|[,（(]\s*)([\p{L}\p{N}_。．.]+)$/u.exec(before)
    if (!match || !/[。．.]/.test(match[1])) return ''
    const tokenStart = before.lastIndexOf(match[1])
    if (tokenStart > 0 && before[tokenStart - 1] === '@') return ''
    return match[1]
})
const namespaceQuery = computed(() => {
    if (operationQuery.value || rootCompletion.value || memberSyntax.value) return ''
    const position = caretPosition.value ?? input.value?.selectionStart ?? draftText.value.length
    const before = draftText.value.slice(0, position)
    const match = /(?:^|[,，(（]\s*)([\p{L}\p{N}_]{1,8})$/u.exec(before)
    if (!match) return ''
    return match[1]
})
function activeCallAtCaret(before: string): { name: string; argumentIndex: number } | null {
    const opens: number[] = []
    let quote = ''
    for (let index = 0; index < before.length; index += 1) {
        const char = before[index]
        if (!quote && (char === '"' || char === "'" || char === '“')) { quote = char === '“' ? '”' : char; continue }
        if (quote && char === quote) { quote = ''; continue }
        if (quote) continue
        if (char === '(' || char === '（') opens.push(index)
        else if (char === ')' || char === '）') opens.pop()
    }
    const open = opens.at(-1)
    if (open === undefined) return null
    const name = /([\p{L}\p{N}_。．.]+)\s*$/u.exec(before.slice(0, open))?.[1]
    if (!name) return null
    let depth = 0
    let argumentIndex = 0
    quote = ''
    for (const char of before.slice(open + 1)) {
        if (!quote && (char === '"' || char === "'" || char === '“')) { quote = char === '“' ? '”' : char; continue }
        if (quote && char === quote) { quote = ''; continue }
        if (quote) continue
        if (char === '(' || char === '（' || char === '[') depth += 1
        else if (char === ')' || char === '）' || char === ']') depth -= 1
        else if ((char === ',' || char === '，') && depth === 0) argumentIndex += 1
    }
    return { name, argumentIndex }
}
const activeCallContext = computed(() => {
    if (!editing.value) return null
    const position = caretPosition.value ?? input.value?.selectionStart ?? draftText.value.length
    const before = draftText.value.slice(0, position)
    const active = activeCallAtCaret(before)
    if (!active) return null
    const name = normalizeSyntaxKey(active.name)
    const suggestion = operationSuggestions(catalogs.value).find((item) => operationSyntaxAliases(item.candidate).includes(name))
    if (!suggestion) return null
    return { suggestion, argumentIndex: active.argumentIndex }
})
const completionExpectedType = computed(() => activeCallContext.value?.suggestion.candidate.inputs[activeCallContext.value.argumentIndex]?.value_type || props.expectedType)
const currentCatalog = computed(() => [...catalogs.value].reverse().find((catalog) => catalog.expected_type === completionExpectedType.value) || null)
const currentParameter = computed(() => {
    const context = activeCallContext.value
    return context?.suggestion.candidate.inputs[context.argumentIndex] || null
})
const activeParameterLabel = computed(() => currentParameter.value
    ? `${activeCallContext.value?.suggestion.syntaxName} · ${currentParameter.value.display_name}`
    : '')
const selectorCompletionValues = computed<AvailableProgramValue[]>(() => selectorBindingsForType(completionExpectedType.value).map((binding) => ({
    source: 'local', id: binding.symbol_id, display_name: binding.display_name, value_type: binding.value_type,
})))
const completionValues = computed(() => [...selectorCompletionValues.value, ...props.availableValues])
const directoryOperations = computed(() => operationDirectorySuggestions(
    currentCatalog.value,
    operationQuery.value,
    props.expectedType === 'bool' ? catalogs.value : [],
))
const operationGroups = computed(() => {
    const groups = new Map<string, ExpressionOperationDirectorySuggestion[]>()
    for (const item of directoryOperations.value) {
        const label = item.discovery.group || '其他操作'
        groups.set(label, [...(groups.get(label) || []), item])
    }
    return [...groups].map(([label, items]) => ({ label, items }))
})
const operationHeading = computed(() => {
    const namespace = operationQuery.value.split(/[。.]/u)[0]
    return namespace ? `${namespace}操作` : '纯值操作'
})
const namespaceSuggestions = computed(() => {
    const query = manualCompletion.value ? '' : normalizeSyntaxKey(namespaceQuery.value)
    return expressionNamespaces(currentCatalog.value).filter((item) => !query || normalizeSyntaxKey([
        item.name, item.description, ...item.keywords,
    ].join(' ')).includes(query))
})
const literalSuggestions = computed(() => currentCatalog.value?.discovery?.literals || [])
const operatorSuggestions = computed(() => currentCatalog.value?.discovery?.operators || [])
const currentParameterChoices = computed(() => currentParameter.value?.choices || [])
const parameterCompletion = computed(() => {
    if (!activeCallContext.value) return false
    const position = caretPosition.value ?? input.value?.selectionStart ?? draftText.value.length
    return /(?:[(（,，])\s*$/u.test(draftText.value.slice(0, position))
})
const operatorOnly = computed(() => {
    if (manualCompletion.value || parameterCompletion.value || operationQuery.value || rootCompletion.value || memberSyntax.value) return false
    if (!['bool', 'int64', 'float64', 'percentage'].includes(completionExpectedType.value)) return false
    if (caretPosition.value !== selectionEndPosition.value) return false
    const position = caretPosition.value ?? input.value?.selectionStart ?? draftText.value.length
    const before = draftText.value.slice(0, position).trimEnd()
    return /(?:\]|\)|\d|开启|关闭|真|假|true|false)$/iu.test(before)
        && !/(?:\+|-|\*|\/|%|等于|不等于|大于|大于等于|小于|小于等于|且|或|非)\s*$/u.test(before)
})
const showOperationDirectory = computed(() => Boolean(operationQuery.value))
const showCompletion = computed(() => editing.value && !completionDismissed.value && (
    showValues.value
    || showOperationDirectory.value
    || manualCompletion.value
    || Boolean(namespaceQuery.value && namespaceSuggestions.value.length)
    || parameterCompletion.value
    || operatorOnly.value
))
const activeParameterHint = computed(() => {
    const context = activeCallContext.value
    if (!context) return ''
    const parameter = context.suggestion.candidate.inputs[context.argumentIndex]
    const selectorResult = parameter ? selectorResultType(parameter.value_type) : null
    return parameter
        ? selectorResult
            ? `${context.suggestion.syntaxName} · ${parameter.display_name}：填写“每项 => 表达式”，可用 @当前项${parameter.value_type.startsWith('list_selector<') ? '、@当前序号' : '、@当前键、@当前值'}。`
            : `${context.suggestion.syntaxName} · ${parameter.display_name}（${programTypeDisplayName(parameter.value_type)}）`
        : context.suggestion.signature
})
function operationCandidateSignature(candidate: PureOperationCandidateDto): string {
    return operationSignature(candidate)
}
function resultTypeHint(types: string[]): string {
    return types.slice(0, 3).map(programTypeDisplayName).join('、')
}
function conditionIntermediateResult(item: ExpressionOperationDirectorySuggestion): boolean {
    const resultType = item.candidate?.result_type || item.discovery.result_type_hints[0] || ''
    return props.expectedType === 'bool' && Boolean(resultType) && !isProgramTypeCompatible(resultType, 'bool')
}
function directoryOperationDisabled(item: ExpressionOperationDirectorySuggestion): boolean {
    return !item.candidate && !conditionIntermediateResult(item)
}
function directoryOperationTitle(item: ExpressionOperationDirectorySuggestion): string {
    if (conditionIntermediateResult(item)) {
        return `${item.discovery.example}；插入中间值后继续输入 ==、!=、>、< 等比较符`
    }
    return item.disabledReason || item.discovery.example
}
function catalogSource(item: AvailableProgramValue): CatalogSource | null {
    return catalogs.value.flatMap((catalog) => catalog.sources)
        .find((source) => source.source === item.source && source.source_id === item.id) || null
}
function hasCompatibleMember(item: AvailableProgramValue): boolean {
    return catalogs.value.some((catalog) => catalog.expected_type === completionExpectedType.value
        && catalog.members.some((member) => member.source === item.source && member.source_id === item.id))
}
function canHaveMembers(valueType: string): boolean {
    const type = optionalInner(valueType) || valueType
    if (recordCatalog(type)) return true
    if (/^(?:null|bool|int64|float64|percentage|string|date|datetime|time|time_of_day|duration|point|rect|path|json|json_value|message_value|url|timezone|relative_path)$/.test(type)) return false
    if (/^(?:list|map|set|asset_ref|target_ref|entity_ref|file_ref|directory_ref|ref)</.test(type)) return false
    return !type.startsWith('enum<')
}
const filteredValues = computed(() => completionValues.value.filter((item) => {
    const useful = completionExpectedType.value === 'bool'
        || isProgramTypeCompatible(item.value_type, completionExpectedType.value)
        || hasCompatibleMember(item)
        || canHaveMembers(item.value_type)
    if (!useful) return false
    const query = rootCompletion.value?.query || ''
    return !query || `${item.display_name} ${item.value_type} ${item.source === 'project' ? '项目' : '局部'}`.toLocaleLowerCase('zh-CN').includes(query)
}))
const memberContext = computed<MemberCompletionContext | null>(() => {
    const syntax = memberSyntax.value
    if (!syntax) return null
    const source = completionValues.value.find((item) => item.source === syntax.sourceKind && item.display_name === syntax.sourceName)
    if (!source) return null
    const sourceInfo = catalogSource(source)
    let currentType = sourceInfo?.narrowed_type || optionalInner(source.value_type) || source.value_type
    let guardRequired = Boolean(optionalInner(source.value_type) && !sourceInfo?.narrowed_type)
    const prefix: RecordPathField[] = []
    for (const name of syntax.completedNames) {
        const record = recordCatalog(currentType)
        const field = record?.fields.find((item) => normalizeSyntaxKey(item.display_name) === normalizeSyntaxKey(name))
        if (!field) return { ...syntax, source, sourceInfo, currentType, currentRecord: record, prefix, guardRequired }
        prefix.push({ field_id: field.field_id, display_name: field.display_name, result_type: field.value_type })
        if (optionalInner(field.value_type)) guardRequired = true
        currentType = optionalInner(field.value_type) || field.value_type
    }
    return { ...syntax, source, sourceInfo, currentType, currentRecord: recordCatalog(currentType), prefix, guardRequired }
})
const memberSteps = computed<MemberStep[]>(() => {
    const context = memberContext.value
    if (!context?.currentRecord) return []
    const allowed = catalogs.value
        .filter((catalog) => catalog.expected_type === completionExpectedType.value)
        .flatMap((catalog) => catalog.members)
        .filter((candidate) => candidate.source === context.source.source && candidate.source_id === context.source.id)
    return context.currentRecord.fields.map((field) => {
        const pathIds = [...context.prefix.map((item) => item.field_id), field.field_id]
        const matching = allowed.filter((candidate) => pathIds.every((fieldId, index) => candidate.path[index]?.field_id === fieldId))
        const selectable = matching.some((candidate) => candidate.path.length === pathIds.length)
        const canDrill = matching.some((candidate) => candidate.path.length > pathIds.length)
            || Boolean(recordCatalog(field.value_type))
        let disabledReason = ''
        if (!selectable && !canDrill) disabledReason = `${programTypeDisplayName(field.value_type)}不能用于当前需要的${programTypeDisplayName(completionExpectedType.value)}`
        return {
            key: `${context.source.source}:${context.source.id}:${pathIds.join('.')}`,
            displayName: field.display_name,
            valueType: field.value_type,
            fieldId: field.field_id,
            canDrill,
            disabledReason,
        }
    }).filter((item) => !context.query || normalizeSyntaxKey(item.displayName).includes(context.query))
})
const memberHeading = computed(() => {
    const context = memberContext.value
    const owner = context?.completedNames.at(-1) || context?.source.display_name || '当前值'
    return `${owner}的字段`
})
const suggestionGroups = computed(() => {
    if (completionExpectedType.value !== 'bool') return [{ label: '可用值', items: filteredValues.value }]
    const direct = filteredValues.value.filter((item) => isProgramTypeCompatible(item.value_type, 'bool'))
    const comparable = filteredValues.value.filter((item) => !isProgramTypeCompatible(item.value_type, 'bool'))
    return [
        ...(direct.length ? [{ label: '可直接判断', items: direct }] : []),
        ...(comparable.length ? [{ label: '用于比较', items: comparable }] : []),
    ]
})

watch(activeCallContext, (context) => {
    const parameter = context?.suggestion.candidate.inputs[context.argumentIndex]
    if (!parameter) return
    const selectorType = selectorResultType(parameter.value_type)
    if (selectorType) {
        void ensureCatalogs([{ type: selectorType, bindings: selectorCatalogBindings(parameter.value_type) }])
    } else {
        void ensureCatalogs([{ type: parameter.value_type, bindings: [] }])
    }
})

watch(memberSyntax, (syntax) => {
    if (syntax) void ensureMemberCatalogs(syntax)
}, { deep: true })

watch(() => props.value, () => {
    if (!editing.value) draftText.value = editableText(props.value)
}, { deep: true })

watch(() => props.value.value_id, () => {
    if (editing.value) emit('editingChange', false)
    editing.value = false
    composing.value = false
    showValues.value = false
    completionDismissed.value = false
    error.value = ''
    draftText.value = editableText(props.value)
})

async function beginEditing(): Promise<void> {
    if (props.disabled) return
    if (!isInlineExpressionEditable(props.value) && props.value.kind !== 'unset') {
        error.value = '这个值包含尚未支持直接改写的逐项表达式；可以先在流程中提取为赋值。'
        return
    }
    commitRevision += 1
    editing.value = true
    emit('editingChange', true)
    error.value = ''
    completionDismissed.value = false
    manualCompletion.value = false
    draftText.value = editableText(props.value)
    void loadCatalogs()
    await nextTick()
    input.value?.focus()
    input.value?.select()
    caretPosition.value = input.value?.selectionStart ?? draftText.value.length
    selectionEndPosition.value = input.value?.selectionEnd ?? caretPosition.value
}

async function loadCatalogs(): Promise<void> {
    if (!props.resolveCatalog) return
    await ensureCatalogs([{ type: props.expectedType, bindings: [] }])
}

function catalogRequestKey(item: CatalogRequest): string {
    return JSON.stringify([item.type, item.bindings.map((binding) => [binding.display_name, binding.value_type])])
}

function selectorCatalogBindings(selectorType: string): LocalSymbolDefinition[] {
    return selectorBindingsForType(selectorType).map((binding) => ({
        ...binding,
        symbol_id: `expression_${binding.role}_${selectorType.replace(/[^a-z0-9]+/gi, '_')}`,
    }))
}

async function ensureCatalogs(requests: CatalogRequest[]): Promise<void> {
    if (!props.resolveCatalog) return
    const unique = requests.filter((item, index) => requests.findIndex((other) => catalogRequestKey(other) === catalogRequestKey(item)) === index)
    await Promise.all(unique.map((item) => {
        const key = catalogRequestKey(item)
        const existing = catalogRequests.get(key)
        if (existing) return existing
        activeCatalogLoads += 1
        catalogLoading.value = true
        const pending = (props.resolveCatalog as NonNullable<typeof props.resolveCatalog>)(item.type, item.bindings)
            .then((catalog) => {
                if (!catalogs.value.some((current) => current === catalog)) catalogs.value = [...catalogs.value, catalog]
            })
            .catch(() => {
                catalogRequests.delete(key)
            })
            .finally(() => {
                activeCatalogLoads = Math.max(0, activeCatalogLoads - 1)
                catalogLoading.value = activeCatalogLoads > 0
            })
        catalogRequests.set(key, pending)
        return pending
    }))
}

async function ensureMemberCatalogs(syntax: MemberSyntaxContext): Promise<void> {
    const revision = ++memberCatalogLoadRevision
    memberCatalogLoading.value = true
    try {
        await loadCatalogs()
        const source = completionValues.value.find((item) => item.source === syntax.sourceKind && item.display_name === syntax.sourceName)
        if (!source) return
        const sourceInfo = catalogSource(source)
        let currentType = sourceInfo?.narrowed_type || optionalInner(source.value_type) || source.value_type
        for (const name of syntax.completedNames) {
            await ensureCatalogs([{ type: recordTypeId(currentType), bindings: [] }])
            const field = recordCatalog(currentType)?.fields
                .find((item) => normalizeSyntaxKey(item.display_name) === normalizeSyntaxKey(name))
            if (!field) return
            currentType = optionalInner(field.value_type) || field.value_type
        }
        await ensureCatalogs([{ type: recordTypeId(currentType), bindings: [] }])
    } finally {
        if (revision === memberCatalogLoadRevision) memberCatalogLoading.value = false
    }
}

function functionNamesInDraft(): string[] {
    const names = [...draftText.value.matchAll(/([\p{L}\p{N}_。．.]+)\s*[（(]/gu)].map((match) => normalizeSyntaxKey(match[1]))
    return [...new Set(names)]
}

async function loadDraftCatalogs(): Promise<void> {
    await loadCatalogs()
    const names = functionNamesInDraft()
    const discoveredResultTypes = catalogs.value
        .flatMap((catalog) => catalog.discovery?.operations || [])
        .filter((operation) => [
            operation.syntax_name,
            `${operation.namespace}.${operation.display_name}`,
            operation.display_name,
            ...operation.aliases,
        ].map(normalizeSyntaxKey).some((alias) => names.includes(alias)))
        .flatMap((operation) => operation.result_type_hints)
    await ensureCatalogs([...new Set(discoveredResultTypes)].map((type) => ({ type, bindings: [] })))
    for (let pass = 0; pass < 5; pass += 1) {
        const candidates = operationSuggestions(catalogs.value)
            .filter((item) => operationSyntaxAliases(item.candidate).some((alias) => names.includes(alias)))
        const requests = candidates.flatMap((item): CatalogRequest[] => item.candidate.inputs.map((parameter) => {
            const selectorType = selectorResultType(parameter.value_type)
            return selectorType
                ? { type: selectorType, bindings: selectorCatalogBindings(parameter.value_type) }
                : { type: parameter.value_type, bindings: [] }
        }))
        const before = catalogRequests.size
        await ensureCatalogs(requests)
        if (catalogRequests.size === before) break
    }

    if (/[+*/%]|\s-\s/.test(draftText.value)) {
        const inferredLiteralType = /\d+\.\d+/.test(draftText.value) ? 'float64' : 'int64'
        const numericTypes = [inferredLiteralType, props.expectedType, ...props.availableValues.map((item) => item.value_type)]
            .filter((type) => ['int64', 'float64', 'percentage'].includes(type))
        await ensureCatalogs([...new Set(numericTypes)].map((type) => ({ type, bindings: [] })))
    }
}

function handleInput(): void {
    commitRevision += 1
    error.value = ''
    completionDismissed.value = false
    manualCompletion.value = false
    syncCaret()
    showValues.value = Boolean(rootCompletion.value || memberSyntax.value)
}

function handleCompositionEnd(): void {
    composing.value = false
    handleInput()
}

function handleSingleLineEnter(event: KeyboardEvent): void {
    if (composing.value || event.isComposing) return
    event.preventDefault()
    commit()
}

function handleMultilineCommit(event: KeyboardEvent): void {
    if (composing.value || event.isComposing) return
    event.preventDefault()
    commit()
}

function syncCaret(): void {
    caretPosition.value = input.value?.selectionStart ?? draftText.value.length
    selectionEndPosition.value = input.value?.selectionEnd ?? caretPosition.value
}

let commitRevision = 0

function commit(): void {
    if (draftText.value.trim() === editableText(props.value).trim()) {
        editing.value = false
        emit('editingChange', false)
        showValues.value = false
        error.value = ''
        return
    }
    if (!draftText.value.trim() && optionalInner(props.expectedType)) {
        emit('replace', {
            value_id: props.value.value_id,
            kind: 'literal',
            value_type: props.expectedType,
            value: null,
        })
        editing.value = false
        emit('editingChange', false)
        showValues.value = false
        error.value = ''
        return
    }
    // Most edits (literals, references and ordinary comparisons) can be parsed
    // from the values already in scope. Commit those synchronously so Enter
    // followed immediately by Save/Escape cannot race a needless microtask.
    if (finishCommit()) return
    if (!props.resolveCatalog) return

    const revision = ++commitRevision
    error.value = ''
    void loadDraftCatalogs().then(() => {
        if (revision !== commitRevision || !editing.value) return
        finishCommit()
    })
}

function finishCommit(): boolean {
    const result = parseExpressionDraft(draftText.value, props.expectedType, props.value.value_id, props.availableValues, catalogs.value)
    if (!result.value) {
        error.value = result.error
        input.value?.focus()
        return false
    }
    emit('replace', preserveExpressionValueIds(props.value, result.value))
    editing.value = false
    emit('editingChange', false)
    showValues.value = false
    error.value = ''
    return true
}

function cancel(): void {
    commitRevision += 1
    editing.value = false
    emit('editingChange', false)
    composing.value = false
    showValues.value = false
    manualCompletion.value = false
    error.value = ''
    draftText.value = editableText(props.value)
}

function insertValue(item: AvailableProgramValue): void {
    const token = `[${item.source === 'project' ? '项目' : '局部'} · ${item.display_name}]`
    const completion = rootCompletion.value
    if (completion) {
        draftText.value = `${draftText.value.slice(0, completion.start)}${token}${draftText.value.slice(completion.end)}`
        const position = completion.start + token.length
        void nextTick(() => {
            input.value?.focus()
            input.value?.setSelectionRange(position, position)
            caretPosition.value = position
            selectionEndPosition.value = position
        })
    } else insertText(token)
    showValues.value = false
}

function insertMemberStep(item: MemberStep): void {
    const context = memberContext.value
    if (!context || item.disabledReason) return
    const suffix = item.canDrill ? `${item.displayName}.` : item.displayName
    draftText.value = `${draftText.value.slice(0, context.queryStart)}${suffix}${draftText.value.slice(context.end)}`
    const position = context.queryStart + suffix.length
    showValues.value = item.canDrill
    void nextTick(() => {
        input.value?.focus()
        input.value?.setSelectionRange(position, position)
        caretPosition.value = position
        selectionEndPosition.value = position
        if (item.canDrill && memberSyntax.value) void ensureMemberCatalogs(memberSyntax.value)
    })
}

function insertOperation(item: ExpressionOperationSuggestion): void {
    const element = input.value
    if (!element) return
    const position = element.selectionStart ?? draftText.value.length
    const before = draftText.value.slice(0, position)
    const match = /[\p{L}\p{N}_。．.]+$/u.exec(before)
    const start = match?.index ?? position
    const inserted = `${item.syntaxName}()`
    draftText.value = `${draftText.value.slice(0, start)}${inserted}${draftText.value.slice(position)}`
    showValues.value = false
    void nextTick(() => {
        const caret = start + inserted.length - 1
        element.focus()
        element.setSelectionRange(caret, caret)
        caretPosition.value = caret
        selectionEndPosition.value = caret
    })
}

async function insertDirectoryOperation(item: ExpressionOperationDirectorySuggestion): Promise<void> {
    let resolved = item
    if (!resolved.candidate && conditionIntermediateResult(resolved)) {
        operationInsertBusy.value = item.key
        error.value = ''
        try {
            await ensureCatalogs(item.discovery.result_type_hints.map((type) => ({ type, bindings: [] })))
            resolved = operationDirectorySuggestions(
                currentCatalog.value,
                operationQuery.value,
                props.expectedType === 'bool' ? catalogs.value : [],
            ).find((candidate) => candidate.key === item.key) || item
        } finally {
            operationInsertBusy.value = ''
        }
    }
    if (!resolved.candidate) {
        error.value = resolved.disabledReason || '当前作用域无法为这个操作提供合法参数。'
        input.value?.focus()
        return
    }
    insertOperation({
        key: resolved.key,
        candidate: resolved.candidate,
        syntaxName: resolved.discovery.syntax_name,
        signature: operationSignature(resolved.candidate),
    })
}

function insertNamespace(name: string): void {
    const element = input.value
    if (!element) return
    const selectionStart = element.selectionStart ?? draftText.value.length
    const selectionEnd = element.selectionEnd ?? selectionStart
    const before = draftText.value.slice(0, selectionStart)
    const token = namespaceQuery.value
    const tokenStart = token ? before.lastIndexOf(token) : selectionStart
    const start = selectionStart === selectionEnd && tokenStart >= 0 ? tokenStart : selectionStart
    const inserted = `${name}.`
    draftText.value = `${draftText.value.slice(0, start)}${inserted}${draftText.value.slice(selectionEnd)}`
    manualCompletion.value = false
    void nextTick(() => {
        const caret = start + inserted.length
        element.focus()
        element.setSelectionRange(caret, caret)
        caretPosition.value = caret
        selectionEndPosition.value = caret
    })
}

function insertLiteral(text: string): void {
    if (!text) {
        input.value?.focus()
        return
    }
    insertText(text)
    manualCompletion.value = false
}

function insertValueTrigger(): void {
    insertText('@')
    manualCompletion.value = false
    showValues.value = true
}

function openDiscovery(): void {
    completionDismissed.value = false
    manualCompletion.value = true
    showValues.value = false
    void loadCatalogs()
}

async function useExample(example: string): Promise<void> {
    emit('closeHelp')
    if (!editing.value) await beginEditing()
    draftText.value = example === '直接输入普通内容' ? '' : example
    await nextTick()
    input.value?.focus()
    input.value?.setSelectionRange(draftText.value.length, draftText.value.length)
    caretPosition.value = draftText.value.length
    selectionEndPosition.value = draftText.value.length
}

function insertText(text: string): void {
    const element = input.value
    if (!element) { draftText.value += text; return }
    const start = element.selectionStart ?? draftText.value.length
    const end = element.selectionEnd ?? start
    draftText.value = `${draftText.value.slice(0, start)}${text}${draftText.value.slice(end)}`
    void nextTick(() => {
        const position = start + text.length
        element.focus()
        element.setSelectionRange(position, position)
        caretPosition.value = position
        selectionEndPosition.value = position
    })
}

function focusFirstSuggestion(): void {
    completionDismissed.value = false
    if (!showCompletion.value) showValues.value = true
    void nextTick(() => root.value?.querySelector<HTMLButtonElement>('.value-suggestion:not(:disabled), .operation-suggestion:not(:disabled), .discovery-suggestion:not(:disabled)')?.focus())
}

function suggestionButtons(): HTMLButtonElement[] {
    return [...(root.value?.querySelectorAll<HTMLButtonElement>('.value-suggestion:not(:disabled), .operation-suggestion:not(:disabled), .discovery-suggestion:not(:disabled)') || [])]
}

function onSuggestionKeydown(event: KeyboardEvent): void {
    const buttons = suggestionButtons()
    const current = buttons.indexOf(event.currentTarget as HTMLButtonElement)
    if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && buttons.length) {
        event.preventDefault()
        const direction = event.key === 'ArrowDown' ? 1 : -1
        buttons[(current + direction + buttons.length) % buttons.length]?.focus()
        return
    }
    if ((event.key === 'Home' || event.key === 'End') && buttons.length) {
        event.preventDefault()
        buttons[event.key === 'Home' ? 0 : buttons.length - 1]?.focus()
        return
    }
    if (event.key === 'Escape') {
        event.preventDefault()
        showValues.value = false
        manualCompletion.value = false
        completionDismissed.value = true
        input.value?.focus()
    }
}

async function handleFocusOut(): Promise<void> {
    // The read-only surface is replaced by the input on the same click. Browsers
    // emit focusout for the removed button before Vue has focused the new input,
    // so decide only after the DOM/focus transition has settled.
    await nextTick()
    if (root.value?.contains(document.activeElement)) return
    if (editing.value && !error.value) void commit()
}
</script>

<style scoped>
.expression-composer { position: relative; min-width: 0; }
.expression-surface { width: 100%; min-height: var(--app-control-default); display: flex; align-items: center; gap: 5px; padding: 3px 8px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); background: var(--app-bg-input); color: var(--app-text-primary); text-align: left; cursor: text; }
.expression-surface:hover { border-color: var(--app-border-strong); background: var(--app-bg-raised); }
.expression-surface:focus-visible { outline: 0; border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.expression-surface:disabled { opacity: .55; cursor: not-allowed; }
.expression-surface.is-multiline { min-height: 72px; align-items: flex-start; }
.expression-value { min-width: 0; display: flex; flex: 1; align-items: center; gap: 5px; overflow: hidden; white-space: nowrap; }
.expression-surface.is-multiline .expression-value { flex-wrap: wrap; overflow: visible; white-space: normal; }
.expression-token { display: inline-flex; min-height: 24px; flex: 0 0 auto; align-items: center; border-radius: var(--app-radius-sm); color: var(--app-text-regular); font-size: var(--app-font-xs); line-height: 1.25; }
.expression-value > .expression-token:only-child { min-width: 0; flex: 1 1 auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.expression-token[data-tone='local'], .expression-token[data-tone='project'] { position: relative; padding: 0 6px; border-radius: 0; color: #c8d9f6; }
.expression-token[data-tone='project'] { color: #f0d4a2; }
.expression-token[data-tone='local']::before, .expression-token[data-tone='project']::before,
.expression-token[data-tone='local']::after, .expression-token[data-tone='project']::after { position: absolute; width: 4px; height: 55%; border-color: currentColor; opacity: .68; content: ''; pointer-events: none; }
.expression-token[data-tone='local']::before, .expression-token[data-tone='project']::before { inset-block-start: 2px; inset-inline-start: 0; border-block-start: 1px solid; border-inline-start: 1px solid; }
.expression-token[data-tone='local']::after, .expression-token[data-tone='project']::after { inset-inline-end: 0; inset-block-end: 2px; border-inline-end: 1px solid; border-block-end: 1px solid; }
.expression-token[data-tone='operator'] { color: var(--app-color-primary-hover); font-weight: 600; }
.expression-token[data-tone='punctuation'] { color: var(--app-text-placeholder); }
.expression-token[data-tone='summary'] { color: var(--app-text-secondary); }
.expression-placeholder, .expression-default { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.expression-placeholder { color: var(--app-text-placeholder); font-size: var(--app-font-xs); }
.expression-default { color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.expression-editor { width: 100%; min-width: 0; min-height: var(--app-control-default); padding: 3px 8px; border: 1px solid var(--app-color-primary); border-radius: var(--app-radius-sm); outline: 0; background: var(--app-bg-input); color: var(--app-text-primary); box-shadow: var(--focus-ring); caret-color: var(--app-color-primary-hover); font: inherit; font-size: var(--app-font-xs); }
.expression-editor::placeholder { color: var(--app-text-placeholder); }
.expression-editor.is-multiline { min-height: 76px; resize: vertical; line-height: 1.55; }
.value-suggestions { position: absolute; z-index: 8; top: calc(100% + 6px); left: 0; right: 0; max-height: 260px; overflow: auto; padding: 6px; border: 1px solid var(--app-overlay-border); border-radius: var(--app-radius-md); background: var(--app-overlay-bg); box-shadow: 0 12px 28px rgba(0, 0, 0, .36); }
.suggestion-heading { display: flex; align-items: center; justify-content: space-between; padding: 5px 7px 7px; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.suggestion-heading span { color: var(--app-text-placeholder); }
.suggestion-group + .suggestion-group { margin-top: 4px; padding-top: 4px; border-top: 1px solid var(--app-border-subtle); }
.suggestion-group-label { display: block; padding: 4px 7px 3px; color: var(--app-text-placeholder); font-size: var(--app-font-caption); }
.value-suggestion { width: 100%; min-height: var(--app-control-default); display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 4px 7px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-regular); text-align: left; cursor: pointer; }
.value-suggestion:hover, .value-suggestion:focus-visible { outline: 0; background: var(--app-bg-hover); box-shadow: none; }
.value-suggestion:disabled { cursor: not-allowed; opacity: .56; }
.member-suggestion:disabled { opacity: .72; }
.value-suggestion:disabled:hover { background: transparent; }
.value-suggestion > span { min-width: 34px; padding: 2px 5px; border-radius: var(--app-radius-sm); background: rgba(92, 131, 199, .13); color: #c8d9f6; font-size: var(--app-font-caption); text-align: center; }
.value-suggestion > span[data-source='project'] { background: rgba(216, 154, 50, .12); color: #f0d4a2; }
.value-suggestion > span[data-source='member'] { background: var(--app-bg-raised); color: var(--app-text-secondary); }
.value-suggestion strong { overflow: hidden; font-size: var(--app-font-xs); font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.value-suggestion small { color: var(--app-text-placeholder); font-size: var(--app-font-caption); }
.operation-suggestion { width: 100%; display: grid; grid-template-columns: minmax(110px, .7fr) minmax(0, 1fr); gap: 2px 10px; padding: 7px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-regular); text-align: left; cursor: pointer; }
.operation-suggestion:hover, .operation-suggestion:focus-visible { outline: 0; background: var(--app-bg-hover); }
.operation-suggestion:disabled { cursor: not-allowed; opacity: .58; }
.operation-suggestion:disabled:hover { background: transparent; }
.operation-suggestion strong { color: var(--app-text-primary); font-size: var(--app-font-xs); font-weight: 600; }
.operation-suggestion span { overflow: hidden; color: var(--app-text-secondary); font-size: var(--app-font-xs); text-overflow: ellipsis; white-space: nowrap; }
.operation-suggestion small { grid-column: 1 / -1; color: var(--app-text-placeholder); font-size: var(--app-font-caption); }
.discovery-suggestion { width: 100%; min-height: var(--app-control-default); display: grid; grid-template-columns: minmax(88px, auto) minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 5px 7px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-regular); text-align: left; cursor: pointer; }
.discovery-suggestion:hover, .discovery-suggestion:focus-visible { outline: 0; background: var(--app-bg-hover); }
.discovery-suggestion strong { color: var(--app-text-primary); font-size: var(--app-font-xs); font-weight: 600; }
.discovery-suggestion span { overflow: hidden; color: var(--app-text-secondary); font-size: var(--app-font-xs); text-overflow: ellipsis; white-space: nowrap; }
.discovery-suggestion small { color: var(--app-text-placeholder); font-size: var(--app-font-caption); white-space: nowrap; }
.namespace-suggestion strong { color: var(--app-color-primary-hover); }
.value-suggestions > p, .expression-error, .parameter-hint { margin: 6px 0 0; font-size: var(--app-font-xs); line-height: 1.5; }
.value-suggestions > p, .parameter-hint { color: var(--app-text-placeholder); }
.value-suggestions > .member-guard-note { margin: 0 7px 5px; padding: 6px 7px; border-radius: var(--app-radius-sm); background: var(--app-color-warning-soft); color: var(--app-text-secondary); }
.expression-help { position: absolute; z-index: 9; top: calc(100% + 6px); left: 0; right: 0; display: grid; gap: 5px; padding: 9px; border: 1px solid var(--app-overlay-border); border-radius: var(--app-radius-md); background: var(--app-overlay-bg); box-shadow: 0 12px 28px rgba(0, 0, 0, .36); }
.expression-help header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.expression-help header strong { color: var(--app-text-primary); font-size: var(--app-font-xs); }
.expression-help header button { border: 0; background: transparent; color: var(--app-text-secondary); font: inherit; font-size: var(--app-font-xs); cursor: pointer; }
.expression-help > p, .expression-help > small { margin: 0; color: var(--app-text-secondary); font-size: var(--app-font-xs); line-height: 1.5; }
.expression-help > button { min-height: var(--app-control-compact); padding: 4px 7px; border: 0; border-radius: var(--app-radius-sm); background: var(--app-bg-input); color: var(--app-text-regular); font: inherit; font-size: var(--app-font-xs); text-align: left; cursor: pointer; }
.expression-help > button:hover, .expression-help > button:focus-visible { outline: 0; background: var(--app-bg-hover); box-shadow: var(--focus-ring); }
.expression-error { color: var(--app-color-danger); }
.has-error .expression-editor { border-color: var(--app-color-danger); box-shadow: 0 0 0 3px var(--app-color-danger-soft); }
</style>
