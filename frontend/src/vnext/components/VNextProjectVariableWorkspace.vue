<template>
    <div class="variable-workspace">
        <VNextNavigationPane class="variable-sidebar" aria-label="项目变量列表">
            <VNextPaneHeader title="项目变量" :meta="store.variables.length">
                <template #actions><VNextIconButton label="新建项目变量" :disabled="store.busy || readOnly" @click="openCreate"><Plus aria-hidden="true" /></VNextIconButton></template>
            </VNextPaneHeader>
            <VNextListSearch v-if="store.variables.length" :model-value="query" placeholder="搜索项目变量" aria-label="搜索项目变量" @update:model-value="query = $event.trim()" />
            <ul v-if="store.variables.length && filteredVariables.length" class="variable-list app-navigation-list">
                <li v-for="variable in filteredVariables" :key="variable.variable_id">
                    <VNextNavigationItem
                        :selected="store.selectedVariableId === variable.variable_id"
                        :title="variable.display_name"
                        @click="store.selectedVariableId = variable.variable_id"
                    >
                        <span>{{ variable.display_name }}</span><small>{{ typeLabel(variable.value_type) }}</small>
                    </VNextNavigationItem>
                </li>
            </ul>
            <VNextWorkspaceState
                v-else-if="store.variables.length"
                compact
                kind="filtered"
                title="没有匹配的变量"
                description="换一个关键词，或清空搜索。"
            ><template #actions><VNextButton size="compact" @click="query = ''">清空搜索</VNextButton></template></VNextWorkspaceState>
        </VNextNavigationPane>

        <main v-if="selected" class="variable-inspector">
            <VNextPaneHeader class="inspector-header" role="inspector" :title="selected.display_name">
                <template #actions><VNextButton class="danger-button" tone="danger" appearance="ghost" size="compact" :disabled="store.busy || readOnly" @click="requestDelete">删除</VNextButton></template>
            </VNextPaneHeader>

            <div class="inspector-scroll app-inspector-body app-inspector-form">
                <section class="form-section app-inspector-section">
                    <h2>基本信息</h2>
                    <label class="field app-form-row"><span class="app-form-label">名称</span><input class="app-form-control" :value="selected.display_name" :disabled="store.busy || readOnly" maxlength="160" @change="updateName" /></label>
                    <label class="field app-form-row"><span class="app-form-label">类型</span>
                        <select class="app-form-control" :value="selected.value_type" :disabled="store.busy || readOnly" @change="updateType">
                            <option v-for="option in selectedTypeOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                        </select>
                    </label>
                </section>

                <section class="form-section default-section app-inspector-section">
                    <h2 class="section-heading">
                        <span>每次运行的初始值</span>
                        <button
                            type="button"
                            class="section-help"
                            aria-label="初始值说明"
                            title="Player 运行方案可以覆盖这个初始值；脚本运行期间的修改不会写回项目。"
                        ><CircleHelp :size="13" aria-hidden="true" /></button>
                    </h2>
                    <ProgramParameterControl
                        :statement-id="`project-variable:${selected.variable_id}`"
                        :parameter="defaultParameter"
                        :value="selected.default_value"
                        :assets="assets"
                        :disabled="store.busy || readOnly"
                        :value-editor-available="isStructuredDefault"
                        @update="updateDefault"
                        @open-value-editor="structuredEditorOpen = true"
                    />
                </section>

                <details :key="selected.variable_id" class="advanced-variable-settings app-inspector-disclosure">
                    <summary><span>说明与限制</span><small>{{ advancedSettingsLabel }}</small></summary>
                    <section class="form-section app-inspector-section">
                        <label class="field app-form-row is-multiline"><span class="app-form-label">说明</span><textarea class="app-form-control" :value="selected.description" :disabled="store.busy || readOnly" maxlength="4000" placeholder="只在需要解释用途时填写" @change="updateDescription" /></label>
                    </section>
                    <section class="form-section constraints-section app-inspector-section">
                        <h2 title="留空表示不限制；设置后同时约束 IDE、Player 和运行。">取值限制</h2>
                        <div v-if="numericType" class="field-grid">
                            <ConstraintNumber label="最小值" field="minimum" :constraints="selected.constraints" :disabled="store.busy || readOnly" @change="updateConstraint" />
                            <ConstraintNumber label="最大值" field="maximum" :constraints="selected.constraints" :disabled="store.busy || readOnly" @change="updateConstraint" />
                            <ConstraintNumber label="步长" field="step" :constraints="selected.constraints" :disabled="store.busy || readOnly" @change="updateConstraint" />
                        </div>
                        <div v-else-if="textType" class="field-grid">
                            <ConstraintNumber label="最短长度" field="min_length" integer :constraints="selected.constraints" :disabled="store.busy || readOnly" @change="updateConstraint" />
                            <ConstraintNumber label="最长长度" field="max_length" integer :constraints="selected.constraints" :disabled="store.busy || readOnly" @change="updateConstraint" />
                        </div>
                        <div v-else-if="collectionType" class="field-grid">
                            <ConstraintNumber label="最少项目" field="min_items" integer :constraints="selected.constraints" :disabled="store.busy || readOnly" @change="updateConstraint" />
                            <ConstraintNumber label="最多项目" field="max_items" integer :constraints="selected.constraints" :disabled="store.busy || readOnly" @change="updateConstraint" />
                            <label v-if="selected.value_type.startsWith('list<')" class="check-field"><input type="checkbox" :checked="Boolean(selected.constraints.unique_items)" :disabled="store.busy || readOnly" @change="updateUniqueItems" /><span>列表内容不重复</span></label>
                        </div>
                        <label v-if="textType" class="field app-form-row"><span class="app-form-label" title="格式规则（正则表达式）">格式规则</span><input class="app-form-control" :value="String(selected.constraints.pattern || '')" :disabled="store.busy || readOnly" placeholder="例如：[A-Za-z0-9_]+" @change="updatePattern" /></label>
                        <label class="field app-form-row is-multiline"><span class="app-form-label">可选值</span><textarea class="app-form-control" :value="choiceText" :disabled="store.busy || readOnly" placeholder="每行一个；留空允许任意值" @change="updateChoices" /></label>
                    </section>
                </details>

                <VNextInlineNotice v-if="store.operationError" class="inline-error" tone="error" :message="store.operationError" />
            </div>
        </main>

        <VNextWorkspaceState v-else kind="empty" title="创建第一个项目变量" description="只把确实需要跨函数共享、或需要交给 Player 用户配置的值放在这里。">
            <template #actions><VNextButton size="compact" :disabled="store.busy || readOnly" @click="openCreate">新建项目变量</VNextButton></template>
        </VNextWorkspaceState>

        <ProjectVariableStructuredEditor
            v-if="structuredEditorOpen && selected"
            :title="selected.display_name"
            :value="selected.default_value"
            :available-values="store.availableValues"
            :constraints="selected.constraints"
            :busy="store.busy"
            @save="saveStructuredDefault"
            @cancel="structuredEditorOpen = false"
        />

        <div v-if="createOpen" class="dialog-backdrop" @mousedown.self="closeCreate">
            <section class="variable-dialog" role="dialog" aria-modal="true" aria-labelledby="create-variable-title" @keydown="trapDialogFocus" @keydown.esc="closeCreate">
                <header><div><h2 id="create-variable-title">新建项目变量</h2><p>变量仅在一次运行中共享，不会自动跨重启保存。</p></div><button type="button" aria-label="关闭" @click="closeCreate"><X :size="15" aria-hidden="true" /></button></header>
                <form @submit.prevent="createVariable">
                    <label class="field app-form-row"><span class="app-form-label">名称</span><input ref="createNameInput" v-model="createName" class="app-form-control" maxlength="160" autocomplete="off" placeholder="例如：启用的副本" /></label>
                    <label class="field app-form-row"><span class="app-form-label">类型</span><select v-model="createType" class="app-form-control" @change="resetCreateDefault"><option v-for="option in typeOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
                    <ProgramParameterControl
                        statement-id="project-variable:create"
                        :parameter="createDefaultParameter"
                        :value="createDefault"
                        :assets="assets"
                        :disabled="store.busy"
                        @update="updateCreateDefault"
                    />
                    <p v-if="createError" class="form-error" role="alert">{{ createError }}</p>
                    <footer><button type="button" class="secondary" @click="closeCreate">取消</button><button type="submit" class="primary" :disabled="store.busy || !createName.trim()">创建</button></footer>
                </form>
            </section>
        </div>

        <div v-if="deleteCandidate" class="dialog-backdrop">
            <section class="variable-dialog delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-variable-title" @keydown="trapDialogFocus">
                <header><div><h2 id="delete-variable-title">{{ deleteReferenceError ? '暂时无法检查引用' : deleteReferences.length ? '项目变量仍在使用' : '删除项目变量？' }}</h2><p>{{ deleteReferenceError || (deleteReferences.length ? '先处理下面的引用，才能安全删除。' : '删除后无法撤销，但不会清理或改写其他项目数据。') }}</p></div></header>
                <ul v-if="deleteReferences.length" class="reference-list">
                    <li v-for="(reference, index) in deleteReferences" :key="`${reference.kind}:${index}`">
                        <button v-if="reference.function_id" type="button" @click="openReference(reference)">
                            <span>{{ reference.function_name || '项目函数' }}</span><small>{{ referenceLabel(reference) }}</small>
                        </button>
                        <div v-else><span>{{ reference.path || reference.kind }}</span><small>{{ reference.location || '外部数据引用' }}</small></div>
                    </li>
                </ul>
                <footer><button type="button" class="secondary" @click="closeDelete">关闭</button><button v-if="deleteReferenceError" type="button" class="primary" :disabled="store.busy" @click="requestDelete">重新检查</button><button v-else-if="!deleteReferences.length" type="button" class="danger-confirm" :disabled="store.busy" @click="confirmDelete">确认删除</button></footer>
            </section>
        </div>

        <div v-if="store.conflict" class="dialog-backdrop">
            <section class="variable-dialog" role="alertdialog" aria-modal="true" aria-labelledby="variable-conflict-title" @keydown="trapDialogFocus">
                <header><div><h2 id="variable-conflict-title">项目变量已在磁盘变化</h2><p>当前操作没有覆盖外部内容。重新加载后再继续。</p></div></header>
                <footer><button type="button" class="primary" :disabled="store.busy" @click="reloadConflict">重新加载</button></footer>
            </section>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, shallowRef, watch } from 'vue'
import { CircleHelp, Plus, X } from 'lucide-vue-next'
import { trapDialogFocus } from '../dialogFocus'
import ProgramParameterControl from '../program/ProgramParameterControl.vue'
import ProjectVariableStructuredEditor from '../program/ProjectVariableStructuredEditor.vue'
import ConstraintNumber from '../program/ProjectVariableConstraintNumber.vue'
import VNextPaneHeader from './ui/VNextPaneHeader.vue'
import VNextListSearch from './ui/VNextListSearch.vue'
import VNextNavigationPane from './ui/VNextNavigationPane.vue'
import VNextNavigationItem from './ui/VNextNavigationItem.vue'
import VNextWorkspaceState from './ui/VNextWorkspaceState.vue'
import VNextInlineNotice from './ui/VNextInlineNotice.vue'
import VNextButton from './ui/VNextButton.vue'
import VNextIconButton from './ui/VNextIconButton.vue'
import { useProjectVariableStore } from '../program/projectVariableStore'
import type { AssetDefinition } from '../types'
import type {
    ProgramParameterContract,
    ProgramValueNode,
    ProgramValueUpdate,
    ProjectVariableDefinition,
} from '../program/types'
import { defaultProgramValue, newProgramValueId } from '../program/valueFactories'
import type { ProjectVariableReferenceDto } from '../program/serverTypes'

withDefaults(defineProps<{ assets?: AssetDefinition[]; readOnly?: boolean }>(), { assets: () => [], readOnly: false })
const emit = defineEmits<{ openReference: [reference: ProjectVariableReferenceDto] }>()
const store = useProjectVariableStore()
const query = ref('')
const createOpen = ref(false)
const createName = ref('')
const createType = ref('string')
const createDefault = shallowRef<ProgramValueNode>(defaultForType('string'))
const createError = ref('')
const createNameInput = ref<HTMLInputElement | null>(null)
const structuredEditorOpen = ref(false)
const deleteCandidate = ref<ProjectVariableDefinition | null>(null)
const deleteReferences = ref<ProjectVariableReferenceDto[]>([])
const deleteReferenceError = ref('')

const typeOptions = [
    { value: 'string', label: '文本' }, { value: 'int64', label: '整数' }, { value: 'float64', label: '小数' },
    { value: 'bool', label: '开关' }, { value: 'duration', label: '持续时间' }, { value: 'date', label: '日期' },
    { value: 'datetime', label: '日期和时间' }, { value: 'time', label: '时间点' }, { value: 'point', label: '坐标' },
    { value: 'rect', label: '区域' }, { value: 'path', label: '路径' }, { value: 'list<string>', label: '文本列表' },
    { value: 'map<string,string>', label: '文本字典' }, { value: 'json_value', label: 'JSON 数据' },
]

const filteredVariables = computed(() => {
    const normalized = query.value.toLocaleLowerCase()
    return store.variables.filter((item) => !normalized || item.display_name.toLocaleLowerCase().includes(normalized))
})
const selected = computed(() => store.selectedVariable)
const selectedTypeOptions = computed(() => {
    const current = selected.value?.value_type
    return current && !typeOptions.some((item) => item.value === current)
        ? [{ value: current, label: `${current}（扩展类型）` }, ...typeOptions]
        : typeOptions
})
const numericType = computed(() => Boolean(selected.value && ['int64', 'float64', 'percentage', 'duration'].includes(selected.value.value_type)))
const textType = computed(() => Boolean(selected.value && (selected.value.value_type === 'string' || selected.value.value_type.startsWith('enum<'))))
const collectionType = computed(() => Boolean(selected.value && (selected.value.value_type.startsWith('list<') || selected.value.value_type.startsWith('map<'))))
const isStructuredDefault = computed(() => Boolean(selected.value && ['list', 'map', 'record', 'json'].includes(selected.value.default_value.kind)))
const choiceText = computed(() => Array.isArray(selected.value?.constraints.choices) ? (selected.value?.constraints.choices as unknown[]).join('\n') : '')
const advancedSettingsLabel = computed(() => {
    if (selected.value?.description.trim()) return '已设置'
    const hasConstraint = Object.values(selected.value?.constraints || {}).some((value) => {
        if (Array.isArray(value)) return value.length > 0
        return value !== undefined && value !== null && value !== '' && value !== false
    })
    return hasConstraint ? '已设置' : '可选'
})
const defaultParameter = computed<ProgramParameterContract>(() => ({
    parameter_id: selected.value?.variable_id || 'project-variable', display_name: '初始值',
    value_type: selected.value?.value_type || 'string', required: true,
    constraints: selected.value?.constraints || {}, allowed_sources: ['fixed'],
}))
const createDefaultParameter = computed<ProgramParameterContract>(() => ({
    parameter_id: 'project-variable:create:default', display_name: '初始值', value_type: createType.value,
    required: true, allowed_sources: ['fixed'],
}))

watch(() => store.selectedVariableId, () => { structuredEditorOpen.value = false })

function typeLabel(typeId: string): string { return typeOptions.find((item) => item.value === typeId)?.label || typeId }
function defaultForType(typeId: string, valueId = newProgramValueId()): ProgramValueNode { return defaultProgramValue(typeId, valueId) }
function materialize(update: ProgramValueUpdate): ProgramValueNode { return { ...update.next, value_id: update.value_id } as ProgramValueNode }

async function updateName(event: Event): Promise<void> {
    if (!selected.value) return
    const name = (event.target as HTMLInputElement).value.trim()
    if (!name || name === selected.value.display_name) return
    await store.updateVariable(selected.value.variable_id, { display_name: name }).catch(() => undefined)
}
async function updateType(event: Event): Promise<void> {
    if (!selected.value) return
    const valueType = (event.target as HTMLInputElement).value.trim()
    if (!valueType || valueType === selected.value.value_type) return
    await store.updateVariable(selected.value.variable_id, {
        value_type: valueType,
        default_value: defaultForType(valueType, selected.value.default_value.value_id),
        constraints: {},
    }).catch(() => undefined)
}
async function updateDescription(event: Event): Promise<void> {
    if (!selected.value) return
    const description = (event.target as HTMLTextAreaElement).value.trim()
    if (description === selected.value.description) return
    await store.updateVariable(selected.value.variable_id, { description }).catch(() => undefined)
}
async function updateDefault(update: ProgramValueUpdate): Promise<void> {
    if (!selected.value) return
    await store.updateVariable(selected.value.variable_id, { default_value: materialize(update) }).catch(() => undefined)
}
async function saveStructuredDefault(value: ProgramValueNode): Promise<void> {
    if (!selected.value) return
    try { await store.updateVariable(selected.value.variable_id, { default_value: value }); structuredEditorOpen.value = false } catch { /* store owns error */ }
}
function nextConstraints(field: string, value: unknown): Record<string, unknown> {
    const next = { ...(selected.value?.constraints || {}) }
    if (value === undefined || value === null || value === '') delete next[field]
    else next[field] = value
    return next
}
async function updateConstraint(field: string, value: number | null): Promise<void> {
    if (!selected.value) return
    await store.updateVariable(selected.value.variable_id, { constraints: nextConstraints(field, value) }).catch(() => undefined)
}
async function updatePattern(event: Event): Promise<void> {
    if (!selected.value) return
    await store.updateVariable(selected.value.variable_id, { constraints: nextConstraints('pattern', (event.target as HTMLInputElement).value.trim()) }).catch(() => undefined)
}
async function updateUniqueItems(event: Event): Promise<void> {
    if (!selected.value) return
    await store.updateVariable(selected.value.variable_id, { constraints: nextConstraints('unique_items', (event.target as HTMLInputElement).checked || null) }).catch(() => undefined)
}
async function updateChoices(event: Event): Promise<void> {
    if (!selected.value) return
    const lines = (event.target as HTMLTextAreaElement).value.split('\n').map((item) => item.trim()).filter(Boolean)
    const choices = lines.map((item) => numericType.value ? Number(item) : item)
    await store.updateVariable(selected.value.variable_id, { constraints: nextConstraints('choices', choices.length ? choices : null) }).catch(() => undefined)
}

async function openCreate(): Promise<void> { createOpen.value = true; createName.value = ''; createType.value = 'string'; createDefault.value = defaultForType('string'); createError.value = ''; await nextTick(); createNameInput.value?.focus() }
function closeCreate(): void { if (!store.busy) createOpen.value = false }
function resetCreateDefault(): void { createDefault.value = defaultForType(createType.value) }
function updateCreateDefault(update: ProgramValueUpdate): void { createDefault.value = materialize(update) }
async function createVariable(): Promise<void> {
    createError.value = ''
    try {
        await store.createVariable({ display_name: createName.value, value_type: createType.value, default_value: createDefault.value })
        createOpen.value = false
    } catch (error) { createError.value = error instanceof Error ? error.message : '创建失败' }
}
async function requestDelete(): Promise<void> {
    if (!selected.value) return
    deleteCandidate.value = selected.value
    deleteReferences.value = []
    deleteReferenceError.value = ''
    try {
        deleteReferences.value = await store.loadReferences(selected.value.variable_id)
    } catch (error) {
        deleteReferenceError.value = error instanceof Error ? error.message : '无法读取变量引用，请重试。'
    }
}
function closeDelete(): void { if (!store.busy) { deleteCandidate.value = null; deleteReferences.value = []; deleteReferenceError.value = '' } }
async function confirmDelete(): Promise<void> {
    if (!deleteCandidate.value) return
    try { await store.deleteVariable(deleteCandidate.value.variable_id); closeDelete() } catch { deleteReferences.value = store.blockedReferences }
}
function openReference(reference: ProjectVariableReferenceDto): void { emit('openReference', reference); closeDelete() }
function referenceLabel(reference: ProjectVariableReferenceDto): string { return reference.kind === 'program_assignment' ? '赋值目标' : reference.kind === 'program_value' ? '参数引用' : reference.field || reference.kind }
async function reloadConflict(): Promise<void> { await store.reload().catch(() => undefined) }
</script>

<style scoped>
.variable-workspace { position: relative; display: grid; grid-template-columns: 270px minmax(0, 1fr); min-width: 0; height: 100%; overflow: hidden; background: var(--app-bg-base); color: var(--app-text-regular); }
.variable-sidebar { display: flex; min-width: 0; flex-direction: column; border-right: 1px solid var(--app-border-subtle); background: var(--app-bg-sidebar); }
.variable-sidebar header { min-height: var(--app-height-pane-header); display: flex; align-items: center; justify-content: space-between; padding: 0 12px; border-bottom: 1px solid var(--app-border-subtle); }
.variable-sidebar header strong { color: var(--app-text-primary); font-size: var(--app-font-sm); }
.variable-sidebar header button, .workspace-empty button { min-height: var(--app-control-compact); padding: 0 10px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); background: var(--app-bg-input); color: var(--app-text-regular); font: inherit; cursor: pointer; }
.variable-search { padding: 10px 10px 6px; }
.variable-search input { width: 100%; min-height: var(--app-control-default); padding: 0 10px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); outline: 0; background: var(--app-bg-input); color: var(--app-text-primary); }
.variable-search input:focus { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.variable-list { margin: 0; padding: 4px 6px 12px; overflow: auto; list-style: none; }
.variable-list button { width: 100%; min-height: var(--app-list-row-compact); display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 0 8px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-regular); text-align: left; cursor: pointer; }
.variable-list button:hover { background: var(--app-bg-hover); }
.variable-list span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.variable-list small { flex: 0 0 auto; color: var(--app-text-placeholder); font-size: var(--app-font-xs); }
.sidebar-empty, .workspace-empty { display: flex; flex: 1; flex-direction: column; align-items: center; justify-content: center; gap: 8px; padding: 28px; color: var(--app-text-secondary); text-align: center; }
.sidebar-empty strong, .workspace-empty strong { color: var(--app-text-primary); font-size: var(--app-font-sm); }
.sidebar-empty p, .workspace-empty p { max-width: 34ch; margin: 0; font-size: var(--app-font-xs); line-height: 1.6; }
.variable-inspector { min-width: 0; display: flex; flex-direction: column; overflow: hidden; }
.inspector-header { min-height: var(--app-height-pane-header); display: flex; align-items: center; justify-content: space-between; padding: 0 18px; border-bottom: 1px solid var(--app-border-subtle); background: var(--app-bg-panel); }
.inspector-header strong { color: var(--app-text-primary); font-size: var(--app-font-sm); }
.danger-button { min-height: var(--app-control-compact); padding: 0 10px; border: 1px solid var(--app-color-danger); border-radius: var(--app-radius-sm); background: transparent; color: var(--app-color-danger); cursor: pointer; }
.inspector-scroll { container-type: inline-size; width: min(720px, 100%); flex: 1; overflow: auto; padding: 0 24px 48px; }
.form-section { padding: var(--app-form-section-padding) 0; border-bottom: 1px solid var(--app-border-subtle); }
.form-section h2 { margin: 0 0 var(--app-form-heading-field-gap); color: var(--app-text-primary); font-size: var(--app-font-sm); }
.form-section > p { margin: -5px 0 12px; color: var(--app-text-secondary); font-size: var(--app-font-xs); line-height: 1.6; }
.section-heading { display: flex; align-items: center; gap: 4px; }
.section-help { width: 22px; height: 22px; display: grid; place-items: center; padding: 0; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-placeholder); cursor: help; }
.section-help:hover, .section-help:focus-visible { outline: 0; background: var(--app-bg-hover); color: var(--app-text-primary); box-shadow: var(--focus-ring); }
.default-section :deep(.program-parameter) { padding-top: 0; }
.advanced-variable-settings { border-bottom: 1px solid var(--app-border-subtle); }
.advanced-variable-settings > summary { min-height: var(--app-form-disclosure-height); display: flex; align-items: center; justify-content: space-between; gap: 12px; color: var(--app-text-regular); font-size: var(--app-font-sm); cursor: pointer; }
.advanced-variable-settings > summary:hover { color: var(--app-text-primary); }
.advanced-variable-settings > summary small { color: var(--app-text-placeholder); font-size: var(--app-font-xs); }
.advanced-variable-settings[open] > summary { border-bottom: 1px solid var(--app-border-subtle); }
.advanced-variable-settings .form-section:last-child { border-bottom: 0; }
.field { --app-form-row-label-min: 84px; --app-form-row-label-max: 104px; margin-top: var(--app-form-field-gap); color: var(--app-text-regular); font-size: var(--app-font-xs); }
.form-section > h2 + .field,
.form-section > .field:first-child { margin-top: 0; }
.field input, .field select, .field textarea { width: 100%; min-height: var(--app-control-default); padding: 0 10px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); outline: 0; background: var(--app-bg-input); color: var(--app-text-primary); font: inherit; }
.field textarea { min-height: 72px; padding: 9px 10px; resize: vertical; line-height: 1.5; }
.field input:focus, .field select:focus, .field textarea:focus { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.field-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.check-field { display: flex; align-items: center; gap: 8px; min-height: var(--app-control-default); margin-top: 0; font-size: var(--app-font-xs); }
.check-field input { accent-color: var(--app-color-primary); }
.inline-error { margin-top: 16px; padding: 10px 12px; border: 1px solid var(--app-color-danger); border-radius: var(--app-radius-sm); background: var(--app-color-danger-soft); color: var(--app-text-regular); font-size: var(--app-font-xs); }
.dialog-backdrop { position: fixed; inset: 0; z-index: 90; display: grid; place-items: center; padding: 24px; background: rgb(0 0 0 / 55%); }
.variable-dialog { container-type: inline-size; width: min(500px, 100%); overflow: hidden; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-lg); background: var(--app-bg-panel); box-shadow: var(--app-shadow-lg); }
.variable-dialog header { display: flex; justify-content: space-between; gap: 12px; padding: 16px 18px; border-bottom: 1px solid var(--app-border-subtle); }
.variable-dialog h2 { margin: 0; color: var(--app-text-primary); font-size: var(--app-font-md); }
.variable-dialog header p { margin: 4px 0 0; color: var(--app-text-secondary); font-size: var(--app-font-xs); line-height: 1.5; }
.variable-dialog header > button { border: 0; background: transparent; color: var(--app-text-secondary); cursor: pointer; }
.variable-dialog form { padding: 4px 18px 0; }
.variable-dialog form > .program-parameter { margin-top: var(--app-form-field-gap); }
.variable-dialog footer { display: flex; justify-content: flex-end; gap: 8px; padding: 14px 18px; border-top: 1px solid var(--app-border-subtle); }
.variable-dialog footer button { min-height: var(--app-control-default); padding: 0 14px; border-radius: var(--app-radius-sm); font: inherit; cursor: pointer; }
.secondary { border: 1px solid var(--app-border-default); background: var(--app-bg-input); color: var(--app-text-regular); }
.primary { border: 1px solid var(--app-color-primary); background: var(--app-color-primary); color: var(--app-text-on-primary); }
.danger-confirm { border: 1px solid var(--app-color-danger); background: var(--app-color-danger); color: var(--app-color-on-primary); }
.form-error { color: var(--app-color-danger); font-size: var(--app-font-xs); }
.reference-list { max-height: 320px; margin: 0; padding: 10px; overflow: auto; list-style: none; }
.reference-list li button, .reference-list li > div { width: 100%; min-height: var(--app-list-row-rich); display: flex; flex-direction: column; align-items: flex-start; justify-content: center; gap: 3px; padding: 5px 10px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-regular); text-align: left; }
.reference-list li button { cursor: pointer; }
.reference-list li button:hover { background: var(--app-bg-hover); }
.reference-list small { color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
@container (max-width: 300px) {
    .field.app-form-row { grid-template-columns: minmax(0, 1fr); row-gap: var(--app-form-label-control-gap); }
    .field.app-form-row > .app-form-help,
    .field.app-form-row > .app-form-error { grid-column: 1; }
    .field.app-form-row.is-multiline > .app-form-label { padding-top: 0; }
}
@container (max-width: 520px) {
    .field-grid { grid-template-columns: minmax(0, 1fr); gap: var(--app-spacing-sm); }
}
@media (max-width: 760px) { .variable-workspace { grid-template-columns: 220px minmax(0, 1fr); } .field-grid { grid-template-columns: 1fr; } }
@media (min-width: 701px) { .variable-workspace { grid-template-columns: var(--workspace-sidebar-width, 260px) minmax(0, 1fr); } }
</style>
