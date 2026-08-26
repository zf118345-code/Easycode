<template>
    <section class="function-panel" @click="closeMenus">
        <header class="panel-toolbar">
            <label><Search :size="13" /><input v-model="query" placeholder="搜索函数" /></label>
            <button type="button" title="新建函数文件夹" aria-label="新建函数文件夹" @click="createFolder"><FolderPlus :size="15" /></button>
            <button class="primary" type="button" title="新建函数" aria-label="新建函数" @click="createFunction"><Plus :size="15" /></button>
            <el-dropdown trigger="click" @command="libraryAction">
                <button type="button" title="函数库操作" aria-label="函数库操作"><MoreHorizontal :size="15" /></button>
                <template #dropdown><el-dropdown-menu><el-dropdown-item command="import"><FileInput :size="14" />导入 .ecf</el-dropdown-item></el-dropdown-menu></template>
            </el-dropdown>
        </header>

        <div class="function-tree">
            <div v-for="folder in folders" :key="folder.folder_id" class="function-folder">
                <button class="folder-row" type="button" @click="toggleFolder(folder.folder_id)" @dblclick.stop="renameFolder(folder)" @contextmenu.prevent="openFolderMenu($event, folder)">
                    <ChevronRight :class="{ expanded: !collapsed.has(folder.folder_id) }" :size="13" /><FolderCode :size="14" /><span>{{ folder.name }}</span><small>{{ functionsFor(folder.folder_id).length }}</small>
                </button>
                <FunctionRow v-for="fn in collapsed.has(folder.folder_id) ? [] : functionsFor(folder.folder_id)" :key="fn.function_id" :item="fn" :active="selectedId === fn.function_id" nested @select="selectFunction" @open="openFunction" @menu="openFunctionMenu" />
            </div>
            <div v-if="unfiledFunctions.length" class="unfiled">
                <div class="section-label"><Braces :size="12" /><span>函数</span><small>{{ unfiledFunctions.length }}</small></div>
                <FunctionRow v-for="fn in unfiledFunctions" :key="fn.function_id" :item="fn" :active="selectedId === fn.function_id" @select="selectFunction" @open="openFunction" @menu="openFunctionMenu" />
            </div>
            <div v-if="!visibleFunctionCount" class="empty-state"><Braces :size="24" /><strong>{{ query ? '没有匹配函数' : '还没有函数' }}</strong><span>函数拥有独立画布、形参、局部变量和显式返回。</span><button v-if="!query" type="button" @click="createFunction"><Plus :size="13" />新建函数</button></div>
        </div>

        <div v-if="selected" class="contract-card">
            <div class="contract-heading">
                <div><strong>{{ selected.name }}</strong><small>{{ selected.function_id }}</small></div>
                <button type="button" title="直接测试函数" aria-label="直接测试函数" @click="openFunctionTest(selected)"><Play :size="15" /></button>
                <button type="button" title="打开函数画布" aria-label="打开函数画布" @click="openFunction(selected)"><PanelTopOpen :size="15" /></button>
            </div>
            <label class="field-label">函数说明<textarea v-model="selected.description" rows="2" placeholder="说明职责、约束和副作用" @change="saveSelected" /></label>
            <ContractSection title="形参" prefix="$param." id-field="parameter_id" :items="selected.parameters" @add="addContractItem('parameters', 'parameter')" @remove="removeContractItem('parameters', $event)" @rename="renameContractItem('parameters', $event)" @change="saveSelected" />
            <ContractSection title="局部变量" prefix="$local." id-field="local_id" :items="selected.local_variables" @add="addContractItem('local_variables', 'local')" @remove="removeContractItem('local_variables', $event)" @rename="renameContractItem('local_variables', $event)" @change="saveSelected" />
            <ContractSection title="输出" prefix="" id-field="output_id" :items="selected.outputs" @add="addContractItem('outputs', 'output')" @remove="removeContractItem('outputs', $event)" @rename="renameContractItem('outputs', $event)" @change="saveSelected" />
            <section class="contract-section">
                <header><span>结果出口</span><button type="button" title="新增结果出口" aria-label="新增结果出口" @click="addOutcome"><Plus :size="13" /></button></header>
                <div v-for="outcome in selected.outcomes" :key="outcome.outcome_id" class="outcome-row">
                    <i :class="outcome.color || 'success'" /><input v-model="outcome.name" :disabled="outcome.immutable" @change="saveSelected" /><button v-if="!outcome.immutable" type="button" title="删除结果出口" :aria-label="`删除结果出口 ${outcome.name}`" @click="removeOutcome(outcome)"><Trash2 :size="12" /></button><LockKeyhole v-else :size="11" />
                </div>
            </section>
            <section class="contract-section">
                <header><span>测试用例</span><button type="button" title="新增并运行测试" aria-label="新增并运行函数测试" @click="openFunctionTest(selected)"><Plus :size="13" /></button></header>
                <div v-for="testCase in selected.test_cases || []" :key="testCase.test_id" class="test-row">
                    <button class="test-name" type="button" @click="openFunctionTest(selected, testCase)"><Play :size="11" /><span>{{ testCase.name }}</span></button>
                    <button type="button" title="删除测试用例" @click="removeTestCase(testCase)"><Trash2 :size="11" /></button>
                </div>
                <div v-if="!(selected.test_cases || []).length" class="empty-contract">暂无测试用例</div>
            </section>
        </div>
        <div v-else class="contract-empty"><MousePointer2 :size="22" /><span>选择一个函数查看并编辑契约</span></div>

        <div v-if="context.visible" class="function-menu" :style="{ left: `${context.x}px`, top: `${context.y}px` }" @click.stop>
            <button @click="openFunction(context.target)"><PanelTopOpen :size="14" />打开画布</button>
            <button @click="renameFunction(context.target)"><Pencil :size="14" />重命名</button>
            <button @click="duplicateFunction(context.target)"><CopyPlus :size="14" />创建副本</button>
            <button @click="moveFunction(context.target)"><FolderInput :size="14" />移动到文件夹…</button>
            <button @click="exportFunction(context.target)"><FileOutput :size="14" />导出 .ecf</button>
            <button class="danger" @click="deleteFunction(context.target)"><Trash2 :size="14" />删除函数</button>
        </div>
        <div v-if="folderContext.visible" class="function-menu" :style="{ left: `${folderContext.x}px`, top: `${folderContext.y}px` }" @click.stop>
            <button @click="renameFolder(folderContext.target)"><Pencil :size="14" />重命名文件夹</button>
            <button class="danger" @click="deleteFolder(folderContext.target)"><Trash2 :size="14" />删除文件夹</button>
        </div>

        <el-dialog v-model="testDialog.visible" title="函数测试" width="520px" append-to-body :close-on-click-modal="false">
            <div v-if="testDialog.function" class="function-test-form">
                <label><span>用例名称</span><input v-model="testDialog.name" placeholder="例如：默认参数" /></label>
                <label v-for="parameter in testDialog.function.parameters || []" :key="parameter.parameter_id">
                    <span>{{ parameter.name }} <small>{{ parameter.type || 'any' }}</small></span>
                    <input v-model="testDialog.inputs[parameter.parameter_id]" :placeholder="parameter.required ? '必填' : '留空使用默认值'" />
                </label>
                <label><span>预期结果</span><select v-model="testDialog.expectedOutcomeId"><option value="">不校验</option><option v-for="outcome in testDialog.function.outcomes || []" :key="outcome.outcome_id" :value="outcome.outcome_id">{{ outcome.name }}</option></select></label>
                <p>测试会用临时主流程调用该函数，不修改正式画布；结果、输出与异常会显示在运行日志中。</p>
            </div>
            <template #footer><el-button @click="testDialog.visible = false">取消</el-button><el-button type="primary" :disabled="store.isRunning || store.isPaused" @click="runFunctionTest"><Play :size="13" /> 保存并运行</el-button></template>
        </el-dialog>
    </section>
</template>

<script setup>
import { computed, defineComponent, h, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Braces, ChevronRight, CopyPlus, FileInput, FileOutput, FolderCode, FolderInput, FolderPlus, LockKeyhole, MoreHorizontal, MousePointer2, PanelTopOpen, Pencil, Play, Plus, Search, Trash2 } from 'lucide-vue-next'
import { useIdeStore } from '@/stores'
import { blueprintApi } from '@/api/blueprintApi'
import { projectWorkspaceApi } from '@/api/projectWorkspaceApi'
import { downloadBlob, safeDownloadName } from '@/utils/download'
import { collectFunctionReferences, createStableId } from '@/utils/flowModel'
import { containsScopedReference, formatScopedReference, rewriteScopedReferences } from '@/utils/functionContract'

const FunctionRow = defineComponent({
    props: {
        item: { type: Object, default: () => ({}) },
        active: { type: Boolean, default: false },
        nested: { type: Boolean, default: false }
    },
    emits: ['select', 'open', 'menu'],
    setup(props, { emit }) { return () => h('button', { class: ['function-row', { active: props.active, nested: props.nested }], type: 'button', onClick: () => emit('select', props.item), onDblclick: () => emit('open', props.item), onContextmenu: event => { event.preventDefault(); emit('menu', event, props.item) } }, [h(Braces, { size: 14 }), h('span', props.item.name), h('small', `${props.item.graph?.nodes?.length || 0}`)]) }
})

const ContractSection = defineComponent({
    props: {
        title: { type: String, default: '' },
        prefix: { type: String, default: '' },
        idField: { type: String, default: '' },
        items: { type: Array, default: () => [] }
    },
    emits: ['add', 'remove', 'rename', 'change'],
    setup(props, { emit }) {
        const types = ['any', 'string', 'number', 'boolean', 'list', 'dict', 'point', 'region']
        const scope = () => String(props.prefix || '').match(/^\$([a-z]+)/)?.[1] || ''
        const reference = item => scope() ? formatScopedReference(scope(), item.name) : item.name
        const copy = async item => { try { await navigator.clipboard.writeText(reference(item)); ElMessage.success('变量引用已复制') } catch { ElMessage.error('复制失败') } }
        return () => h('section', { class: 'contract-section' }, [
            h('header', [h('span', props.title), h('button', { type: 'button', title: `新增${props.title}`, 'aria-label': `新增${props.title}`, onClick: () => emit('add') }, [h(Plus, { size: 13 })])]),
            ...(props.items || []).map((item, index) => h('div', { class: 'contract-item', key: item[props.idField] }, [
                h('div', { class: 'contract-row' }, [
                    h('input', { value: item.name, title: reference(item), onChange: event => { const previousName = item.name; item.name = event.target.value.trim(); emit('rename', { item, index, previousName, nextName: item.name }) } }),
                    h('select', { value: item.type || 'any', onChange: event => { item.type = event.target.value; emit('change') } }, types.map(type => h('option', { value: type }, type))),
                    props.prefix ? h('button', { type: 'button', title: `复制 ${reference(item)}`, 'aria-label': `复制 ${reference(item)}`, onClick: () => copy(item) }, [h(CopyPlus, { size: 11 })]) : null,
                    h('button', { type: 'button', title: `删除${props.title} ${item.name || index + 1}`, 'aria-label': `删除${props.title} ${item.name || index + 1}`, onClick: () => emit('remove', index) }, [h(Trash2, { size: 11 })])
                ]),
                h('div', { class: 'contract-meta' }, [
                    props.idField !== 'output_id' ? h('input', { value: item.default_value ?? '', placeholder: '默认值', title: '默认值', onChange: event => { item.default_value = event.target.value === '' ? null : event.target.value; emit('change') } }) : null,
                    props.idField === 'parameter_id' ? h('label', { title: '调用方必须传入该参数' }, [h('input', { type: 'checkbox', checked: Boolean(item.required), onChange: event => { item.required = event.target.checked; emit('change') } }), '必填']) : null,
                    h('input', { value: item.description || '', placeholder: '说明', title: '契约说明', onChange: event => { item.description = event.target.value; emit('change') } })
                ])
            ])),
            !(props.items || []).length ? h('div', { class: 'empty-contract' }, '无') : null
        ])
    }
})

const store = useIdeStore()
const query = ref('')
const selectedId = ref('')
const collapsed = ref(new Set())
const context = reactive({ visible: false, x: 0, y: 0, target: null })
const folderContext = reactive({ visible: false, x: 0, y: 0, target: null })
const testDialog = reactive({ visible: false, function: null, testId: '', name: '', inputs: {}, expectedOutcomeId: '' })
const selected = computed(() => (store.blueprint?.functions || []).find(item => item.function_id === selectedId.value) || null)
const matches = item => !query.value.trim() || `${item.name} ${item.description || ''}`.toLowerCase().includes(query.value.trim().toLowerCase())
const folders = computed(() => store.blueprint?.function_folders || [])
const functionsFor = folderId => (store.blueprint?.functions || []).filter(item => item.folder_id === folderId && matches(item))
const unfiledFunctions = computed(() => (store.blueprint?.functions || []).filter(item => !item.folder_id && matches(item)))
const visibleFunctionCount = computed(() => folders.value.reduce((count, folder) => count + functionsFor(folder.folder_id).length, 0) + unfiledFunctions.value.length)

watch(
    () => [store.canvasMode, store.currentTaskId, store.blueprint?.functions?.length],
    ([mode, taskId]) => {
        if (mode === 'function' && (store.blueprint?.functions || []).some(item => item.function_id === taskId)) selectedId.value = taskId
        else if (selectedId.value && !(store.blueprint?.functions || []).some(item => item.function_id === selectedId.value)) selectedId.value = ''
    },
    { immediate: true }
)

function closeMenus() { context.visible = false; folderContext.visible = false }
function uniqueFunctionName(raw, excludedId = '') {
    const used = new Set((store.blueprint?.functions || []).filter(item => item.function_id !== excludedId).map(item => item.name))
    const base = String(raw || '新建函数').trim() || '新建函数'
    if (!used.has(base)) return base
    let suffix = 1
    while (used.has(`${base}${suffix}`)) suffix += 1
    return `${base}${suffix}`
}

function toggleFolder(id) { const next = new Set(collapsed.value); next.has(id) ? next.delete(id) : next.add(id); collapsed.value = next }
function selectFunction(item) { selectedId.value = item.function_id; context.visible = false }
async function openFunction(item) { await store.loadTaskData(item.function_id); await store.setCanvasMode('function'); store.setFocusTarget({ type: 'graph', id: item.function_id, timestamp: Date.now() }); selectedId.value = item.function_id; context.visible = false }

async function createFunction() {
    try {
        const result = await ElMessageBox.prompt('函数会创建独立画布，并包含固定入口和显式返回节点。', '新建函数', { inputValue: '新建函数', inputPattern: /\S+/, inputErrorMessage: '名称不能为空', confirmButtonText: '创建', cancelButtonText: '取消' })
        const created = await store.createFunction(result.value.trim())
        selectedId.value = created.function_id
        await openFunction(created)
    } catch { /* cancel */ }
}

async function createFolder() {
    try {
        const result = await ElMessageBox.prompt('文件夹只整理函数库，不改变执行语义。', '新建函数文件夹', { inputValue: '新建文件夹', inputPattern: /\S+/, inputErrorMessage: '名称不能为空', confirmButtonText: '创建', cancelButtonText: '取消' })
        const names = new Set(folders.value.map(item => item.name)); let name = result.value.trim(), suffix = 1; const base = name
        while (names.has(name)) name = `${base}${suffix++}`
        store.blueprint.function_folders.push({ folder_id: createStableId('folder'), name })
        await store.saveWorkflowImmediately()
    } catch { /* cancel */ }
}

async function renameFolder(folder) {
    folderContext.visible = false
    try {
        const result = await ElMessageBox.prompt('', '重命名函数文件夹', { inputValue: folder.name, inputPattern: /\S+/, inputErrorMessage: '名称不能为空' })
        const used = new Set(folders.value.filter(item => item.folder_id !== folder.folder_id).map(item => item.name)); let name = result.value.trim(), suffix = 1; const base = name
        while (used.has(name)) name = `${base}${suffix++}`
        folder.name = name
        await store.saveWorkflowImmediately()
    } catch { /* cancel */ }
}

function openFolderMenu(event, folder) { context.visible = false; Object.assign(folderContext, { visible: true, x: event.clientX, y: event.clientY, target: folder }) }
async function deleteFolder(folder) {
    folderContext.visible = false
    if (!folder) return
    const count = (store.blueprint?.functions || []).filter(item => item.folder_id === folder.folder_id).length
    try {
        await ElMessageBox.confirm(count ? `删除文件夹“${folder.name}”？其中 ${count} 个函数会移到未分类，函数本身不会删除。` : `删除空文件夹“${folder.name}”？`, '删除函数文件夹', { type: 'warning', confirmButtonText: '删除文件夹', cancelButtonText: '取消' })
        for (const fn of store.blueprint.functions || []) if (fn.folder_id === folder.folder_id) fn.folder_id = null
        store.blueprint.function_folders = folders.value.filter(item => item.folder_id !== folder.folder_id)
        await store.saveWorkflowImmediately()
    } catch { /* cancel */ }
}

async function saveSelected() {
    if (!selected.value) return
    const duplicate = section => new Set((selected.value[section] || []).map(item => item.name.trim())).size !== (selected.value[section] || []).length
    if (['parameters', 'local_variables', 'outputs'].some(duplicate)) return ElMessage.warning('同一契约分区内名称不能重复')
    try { await store.saveFunctionData(selected.value) } catch (error) { ElMessage.error(error.message || '函数保存失败') }
}

function addContractItem(section, prefix) {
    const items = selected.value[section] || (selected.value[section] = [])
    const used = new Set(items.map(item => item.name)); let name = section === 'parameters' ? '参数' : section === 'local_variables' ? '局部变量' : '输出', index = 1, value = name
    while (used.has(value)) value = `${name}${index++}`
    const idField = section === 'parameters' ? 'parameter_id' : section === 'local_variables' ? 'local_id' : 'output_id'
    items.push({ [idField]: createStableId(prefix), name: value, type: 'any', required: false, default_value: null, description: '' })
    saveSelected()
}
async function renameContractItem(section, { item, previousName, nextName }) {
    if (!selected.value || previousName === nextName) return saveSelected()
    const names = (selected.value[section] || []).filter(candidate => candidate !== item).map(candidate => candidate.name)
    if (!nextName || names.includes(nextName)) {
        item.name = previousName
        ElMessage.warning(nextName ? '同一契约分区内名称不能重复' : '契约名称不能为空')
        return
    }
    const scope = section === 'parameters' ? 'param' : section === 'local_variables' ? 'local' : ''
    if (scope) {
        for (const node of selected.value.graph?.nodes || []) {
            node.params = rewriteScopedReferences(node.params || {}, scope, previousName, nextName)
        }
    }
    await store.saveWorkflowImmediately()
}

async function removeContractItem(section, index) {
    if (!selected.value) return
    const item = selected.value[section]?.[index]
    if (!item) return
    const scope = section === 'parameters' ? 'param' : section === 'local_variables' ? 'local' : ''
    if (scope && containsScopedReference(selected.value.graph?.nodes || [], scope, item.name)) {
        return ElMessage.warning(`函数体仍在使用 ${formatScopedReference(scope, item.name)}，请先调整引用`)
    }
    try {
        await ElMessageBox.confirm(`删除${section === 'parameters' ? '形参' : section === 'local_variables' ? '局部变量' : '输出'}“${item.name}”？相关稳定 ID 绑定会同步清理。`, '删除函数契约项', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    } catch { return }

    const idField = section === 'parameters' ? 'parameter_id' : section === 'local_variables' ? 'local_id' : 'output_id'
    const stableId = item[idField]
    const graphs = [store.blueprint?.main_graph, ...(store.blueprint?.functions || []).map(fn => fn.graph)].filter(Boolean)
    for (const graph of graphs) {
        for (const node of graph.nodes || []) {
            if (node.node_type !== 'call_function' || node.params?.function_id !== selected.value.function_id) continue
            if (section === 'parameters') node.params.input_bindings = (node.params.input_bindings || []).filter(binding => binding.parameter_id !== stableId)
            if (section === 'outputs') node.params.output_bindings = (node.params.output_bindings || []).filter(binding => binding.output_id !== stableId)
        }
    }
    if (section === 'parameters') {
        for (const testCase of selected.value.test_cases || []) if (testCase.inputs) delete testCase.inputs[stableId]
    }
    if (section === 'outputs') {
        for (const node of selected.value.graph?.nodes || []) {
            if (node.node_type === 'function_return') node.params.output_bindings = (node.params.output_bindings || []).filter(binding => binding.output_id !== stableId)
        }
    }
    selected.value[section].splice(index, 1)
    await store.saveWorkflowImmediately()
}
function addOutcome() { const used = new Set(selected.value.outcomes.map(item => item.name)); let name = '结果', i = 1; while (used.has(name)) name = `结果${i++}`; selected.value.outcomes.push({ outcome_id: createStableId('outcome'), name, color: 'success' }); saveSelected() }
async function removeOutcome(outcome) {
    const usedByReturns = (selected.value.graph?.nodes || []).some(node => node.node_type === 'function_return' && node.params?.outcome_id === outcome.outcome_id)
    if (usedByReturns) return ElMessage.warning('该结果仍被函数返回节点使用，请先调整返回节点')
    selected.value.outcomes = selected.value.outcomes.filter(item => item.outcome_id !== outcome.outcome_id); await saveSelected()
}

function openFunctionMenu(event, item) { context.visible = true; context.x = event.clientX; context.y = event.clientY; context.target = item; selectedId.value = item.function_id }
async function renameFunction(item) { context.visible = false; try { const result = await ElMessageBox.prompt('', '重命名函数', { inputValue: item.name, inputPattern: /\S+/, inputErrorMessage: '名称不能为空' }); item.name = uniqueFunctionName(result.value, item.function_id); await store.saveFunctionData(item) } catch { /* cancel */ } }
async function duplicateFunction(item) { context.visible = false; try { const copy = await store.projectStore.duplicateFunction(item.function_id); selectedId.value = copy.function_id; ElMessage.success('函数副本已创建') } catch (error) { ElMessage.error(error.message || '复制失败') } }
async function moveFunction(item) { context.visible = false; const options = [{ value: '', label: '不放入文件夹' }, ...folders.value.map(folder => ({ value: folder.folder_id, label: folder.name }))]; try { const result = await ElMessageBox.prompt(`可用文件夹：${options.map(option => option.label).join('、')}`, '移动函数', { inputValue: options.find(option => option.value === item.folder_id)?.label || '不放入文件夹' }); const target = options.find(option => option.label === result.value.trim()); if (!target) return ElMessage.warning('请输入现有文件夹名称'); item.folder_id = target.value || null; await store.saveFunctionData(item) } catch { /* cancel */ } }
async function exportFunction(item) { context.visible = false; try { const blob = await blueprintApi.exportFunction(item.function_id, store.currentProjectPath); downloadBlob(blob, `${safeDownloadName(item.name, 'function')}.ecf`) } catch (error) { ElMessage.error(error.message || '导出失败') } }
async function deleteFunction(item) { context.visible = false; const refs = collectFunctionReferences(store.blueprint, item.function_id); if (refs.length) return ElMessage.warning(`该函数仍被 ${refs.length} 个调用节点使用`); try { await ElMessageBox.confirm(`删除函数“${item.name}”？此操作不可通过画布撤销。`, '删除函数', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }); await store.deleteFunction(item.function_id); if (selectedId.value === item.function_id) selectedId.value = '' } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(error.message || '删除失败') } }
async function libraryAction(command) { if (command !== 'import') return; try { const picked = await projectWorkspaceApi.chooseFile('选择 EasyCode 函数包', ['.ecf']); if (!picked?.path) return; const result = await blueprintApi.importFunction(store.currentProjectPath, picked.path); await store.loadProjectData(); selectedId.value = result.root_function_id || ''; ElMessage.success(`已导入 ${result.imported || 1} 个函数，所有 ID 已重新生成`) } catch (error) { ElMessage.error(error.message || '导入失败') } }

function openFunctionTest(item, testCase = null) {
    const inputs = {}
    for (const parameter of item.parameters || []) inputs[parameter.parameter_id] = testCase?.inputs?.[parameter.parameter_id] ?? ''
    Object.assign(testDialog, {
        visible: true,
        function: item,
        testId: testCase?.test_id || '',
        name: testCase?.name || `测试 ${(item.test_cases || []).length + 1}`,
        inputs,
        expectedOutcomeId: testCase?.expected_outcome_id || ''
    })
}

function parseTestValue(raw, type) {
    if (raw === '') return undefined
    if (type === 'number') { const value = Number(raw); if (!Number.isFinite(value)) throw new Error(`无法转换为数字：${raw}`); return value }
    if (type === 'boolean') return ['true', '1', 'yes', '是'].includes(String(raw).trim().toLowerCase())
    if (['list', 'dict', 'point', 'region'].includes(type)) return JSON.parse(raw)
    return raw
}

async function runFunctionTest() {
    const fn = testDialog.function
    if (!fn || store.isRunning || store.isPaused) return
    try {
        const inputs = {}
        for (const parameter of fn.parameters || []) {
            const value = parseTestValue(testDialog.inputs[parameter.parameter_id] ?? '', parameter.type || 'any')
            if (value !== undefined) inputs[parameter.parameter_id] = value
            else if (parameter.required && parameter.default == null && parameter.default_value == null) throw new Error(`请填写必填参数：${parameter.name}`)
        }
        const testCase = {
            test_id: testDialog.testId || createStableId('test'),
            name: testDialog.name.trim() || `测试 ${(fn.test_cases || []).length + 1}`,
            inputs,
            expected_outcome_id: testDialog.expectedOutcomeId || ''
        }
        fn.test_cases ||= []
        const existing = fn.test_cases.findIndex(item => item.test_id === testCase.test_id)
        existing >= 0 ? fn.test_cases.splice(existing, 1, testCase) : fn.test_cases.push(testCase)
        await saveSelected()

        const callId = createStableId('function_test_call')
        const nodes = [{
            node_id: callId,
            node_name: `测试 ${fn.name}`,
            node_type: 'call_function',
            params: {
                function_id: fn.function_id,
                input_bindings: Object.entries(inputs).map(([parameter_id, value]) => ({ parameter_id, value })),
                output_bindings: (fn.outputs || []).map(output => ({ output_id: output.output_id, target: `$var.__function_test_${output.output_id}` }))
            },
            delay_before: 0, loop_count: 1, enabled: true, position: { x: 80, y: 120 }, size: { w: 180, h: 92 }
        }]
        const edges = []
        ;(fn.outcomes || []).forEach((outcome, index) => {
            const logId = createStableId('function_test_result')
            const expected = !testCase.expected_outcome_id || testCase.expected_outcome_id === outcome.outcome_id
            nodes.push({ node_id: logId, node_name: expected ? '测试结果符合预期' : '测试结果不符合预期', node_type: 'log', params: { message: `${expected ? '[函数测试通过]' : '[函数测试未通过]'} 实际结果：${outcome.name}` }, delay_before: 0, loop_count: 1, enabled: true, position: { x: 360, y: 70 + index * 115 }, size: { w: 180, h: 84 } })
            edges.push({ edge_id: createStableId('edge'), source_node: callId, target_node: logId, source_port: `outcome_${index}`, source_port_id: outcome.outcome_id, canvas: 'workflow' })
        })
        const runtimeBlueprint = JSON.parse(JSON.stringify(store.blueprint))
        runtimeBlueprint.main_graph = { graph_id: 'main', nodes, edges, blocks: [] }
        testDialog.visible = false
        await store.executionStore.runTask('main', callId, { blueprintData: runtimeBlueprint, skipSave: true, breakpoints: [] })
    } catch (error) { ElMessage.error(error.message || '函数测试启动失败') }
}

async function removeTestCase(testCase) {
    if (!selected.value) return
    selected.value.test_cases = (selected.value.test_cases || []).filter(item => item.test_id !== testCase.test_id)
    await saveSelected()
}
</script>

<style scoped>
.function-panel{height:100%;min-width:0;display:grid;grid-template-rows:42px minmax(150px,42%) minmax(0,1fr);background:var(--app-sidebar-bg);color:var(--app-text-primary);font-size:11px}.panel-toolbar{display:flex;align-items:center;gap:4px;padding:0 7px;border-bottom:1px solid var(--app-separator)}.panel-toolbar label{min-width:0;flex:1;height:29px;display:flex;align-items:center;gap:6px;padding:0 7px;border:1px solid var(--app-border-subtle);border-radius:6px;background:var(--app-input-bg)}.panel-toolbar input{min-width:0;flex:1;border:0;outline:0;background:transparent;color:inherit;font:inherit}.panel-toolbar button,.contract-heading button,.contract-section button{width:28px;height:28px;display:grid;place-items:center;padding:0;border:0;border-radius:6px;background:transparent;color:var(--app-text-secondary);cursor:pointer}.panel-toolbar button:hover,.contract-heading button:hover,.contract-section button:hover{background:var(--el-fill-color-light);color:var(--app-text-primary)}.panel-toolbar button.primary{background:var(--el-color-primary);color:#fff}.function-tree{min-height:0;overflow:auto;padding:6px;border-bottom:1px solid var(--app-separator)}.folder-row,.function-row{width:100%;height:29px;display:flex;align-items:center;gap:7px;padding:0 7px;border:0;border-radius:5px;background:transparent;color:var(--app-text-secondary);text-align:left;cursor:pointer}.folder-row:hover,.function-row:hover,.function-row.active{background:var(--el-fill-color-light);color:var(--app-text-primary)}.function-row.active{box-shadow:inset 2px 0 var(--el-color-primary)}.folder-row>svg:first-child{transition:transform .12s}.folder-row>svg.expanded{transform:rotate(90deg)}.folder-row span,.function-row span{min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.folder-row small,.function-row small,.section-label small{color:var(--app-text-placeholder);font-size:10px}.function-row.nested{padding-left:27px}.section-label{height:27px;display:flex;align-items:center;gap:6px;padding:0 8px;color:var(--app-text-placeholder);text-transform:uppercase;letter-spacing:.05em}.section-label span{flex:1}.empty-state,.contract-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;padding:20px;color:var(--app-text-placeholder);text-align:center}.empty-state strong{color:var(--app-text-secondary)}.empty-state span{max-width:220px;line-height:1.5}.empty-state button{display:flex;align-items:center;gap:5px;margin-top:4px;padding:6px 9px;border:0;border-radius:6px;background:var(--app-color-primary-dim);color:var(--el-color-primary);cursor:pointer}.contract-card{min-height:0;overflow:auto;padding:10px}.contract-heading{display:flex;align-items:center;margin-bottom:9px}.contract-heading>div{min-width:0;flex:1;display:flex;flex-direction:column;gap:2px}.contract-heading strong{font-size:12px}.contract-heading small{overflow:hidden;text-overflow:ellipsis;color:var(--app-text-placeholder);font-size:10px}.field-label{display:flex;flex-direction:column;gap:5px;color:var(--app-text-secondary);font-size:10px}.field-label textarea,.contract-row input,.outcome-row input,.contract-meta input{box-sizing:border-box;border:1px solid var(--app-border-subtle);border-radius:5px;outline:0;background:var(--app-input-bg);color:var(--app-text-primary);font:inherit}.field-label textarea{width:100%;padding:6px;resize:vertical}.contract-section{margin-top:10px}.contract-section>header{height:25px;display:flex;align-items:center;border-bottom:1px solid var(--app-separator);font-weight:650}.contract-section>header span{flex:1}.contract-section>header button{width:23px;height:23px}.contract-item{padding:3px 0;border-bottom:1px solid color-mix(in srgb,var(--app-separator) 55%,transparent)}.contract-row,.outcome-row,.test-row{height:29px;display:flex;align-items:center;gap:4px}.contract-row input,.outcome-row input{min-width:0;flex:1;height:24px;padding:0 5px}.contract-row select{width:67px;height:24px;border:1px solid var(--app-border-subtle);border-radius:5px;background:var(--app-input-bg);color:var(--app-text-secondary);font-size:10px}.contract-row button,.outcome-row button,.test-row>button{width:22px;height:22px}.contract-meta{display:flex;align-items:center;gap:4px;padding:0 2px 3px}.contract-meta>input{min-width:0;flex:1;height:22px;padding:0 5px;font-size:10px}.contract-meta label{display:flex;align-items:center;gap:2px;color:var(--app-text-secondary);font-size:10px;white-space:nowrap}.contract-meta label input{accent-color:var(--el-color-primary)}.test-row .test-name{min-width:0;flex:1;width:auto;display:flex;grid-auto-flow:column;justify-content:flex-start;gap:5px;padding:0 5px}.test-name span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.empty-contract{height:26px;display:flex;align-items:center;color:var(--app-text-placeholder)}.outcome-row>i{width:7px;height:7px;border-radius:50%;background:#54a875}.outcome-row>i.danger{background:#dc655f}.outcome-row>svg{margin:0 5px;color:var(--app-text-placeholder)}.function-menu{position:fixed;z-index:6500;min-width:185px;padding:5px;border:1px solid var(--app-overlay-border);border-radius:8px;background:var(--app-overlay-bg);box-shadow:var(--app-shadow-lg)}.function-menu button{width:100%;height:30px;display:flex;align-items:center;gap:8px;padding:0 8px;border:0;border-radius:5px;background:transparent;color:var(--app-text-primary);font-size:11px;text-align:left;cursor:pointer}.function-menu button:hover{background:var(--el-fill-color-light)}.function-menu button.danger{color:var(--el-color-danger)}.function-test-form{display:grid;gap:10px}.function-test-form label{display:grid;grid-template-columns:130px 1fr;align-items:center;gap:10px;font-size:12px}.function-test-form label>span{display:flex;align-items:center;gap:6px;color:var(--app-text-secondary)}.function-test-form small{color:var(--app-text-placeholder)}.function-test-form input,.function-test-form select{height:31px;box-sizing:border-box;padding:0 8px;border:1px solid var(--app-border-subtle);border-radius:6px;background:var(--app-input-bg);color:var(--app-text-primary)}.function-test-form p{margin:3px 0 0;color:var(--app-text-placeholder);font-size:11px;line-height:1.55}
</style>
