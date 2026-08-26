<template>
    <section v-if="currentFunction" class="function-inspector">
        <header class="inspector-heading">
            <div class="heading-copy">
                <Braces :size="16" />
                <div><strong>{{ currentFunction.name }}</strong><small>{{ referenceCount }} 处调用</small></div>
            </div>
            <button type="button" title="测试函数" aria-label="测试函数" @click="openFunctionTest(currentFunction)"><Play :size="15" /></button>
        </header>

        <div class="inspector-scroll">
            <label class="field-label">函数名称<input v-model="currentFunction.name" @change="saveSelected" /></label>
            <label class="field-label">函数说明<textarea v-model="currentFunction.description" rows="3" placeholder="说明职责、约束和副作用" @change="saveSelected" /></label>

            <ContractSection title="形参" prefix="$param." id-field="parameter_id" :items="currentFunction.parameters" @add="addContractItem('parameters', 'parameter')" @remove="removeContractItem('parameters', $event)" @rename="renameContractItem('parameters', $event)" @change="saveSelected" />
            <ContractSection title="局部变量" prefix="$local." id-field="local_id" :items="currentFunction.local_variables" @add="addContractItem('local_variables', 'local')" @remove="removeContractItem('local_variables', $event)" @rename="renameContractItem('local_variables', $event)" @change="saveSelected" />
            <ContractSection title="输出" prefix="" id-field="output_id" :items="currentFunction.outputs" @add="addContractItem('outputs', 'output')" @remove="removeContractItem('outputs', $event)" @rename="renameContractItem('outputs', $event)" @change="saveSelected" />

            <section class="contract-section">
                <header><span>结果出口</span><button type="button" title="新增结果出口" aria-label="新增结果出口" @click="addOutcome"><Plus :size="13" /></button></header>
                <div v-for="outcome in currentFunction.outcomes" :key="outcome.outcome_id" class="outcome-row">
                    <i :class="outcome.color || 'success'" />
                    <input v-model="outcome.name" :disabled="outcome.immutable" @change="saveSelected" />
                    <button v-if="!outcome.immutable" type="button" title="删除结果出口" :aria-label="`删除结果出口 ${outcome.name}`" @click="removeOutcome(outcome)"><Trash2 :size="12" /></button>
                    <LockKeyhole v-else :size="11" />
                </div>
            </section>

            <section class="contract-section">
                <header><span>测试用例</span><button type="button" title="新增并运行测试" aria-label="新增并运行函数测试" @click="openFunctionTest(currentFunction)"><Plus :size="13" /></button></header>
                <div v-for="testCase in currentFunction.test_cases || []" :key="testCase.test_id" class="test-row">
                    <button class="test-name" type="button" @click="openFunctionTest(currentFunction, testCase)"><Play :size="11" /><span>{{ testCase.name }}</span></button>
                    <button type="button" title="删除测试用例" :aria-label="`删除测试用例 ${testCase.name}`" @click="removeTestCase(testCase)"><Trash2 :size="11" /></button>
                </div>
                <div v-if="!(currentFunction.test_cases || []).length" class="empty-contract">暂无测试用例</div>
            </section>
        </div>

        <el-dialog v-model="testDialog.visible" title="函数测试" width="520px" append-to-body :close-on-click-modal="false">
            <div v-if="testDialog.function" class="function-test-form">
                <label><span>用例名称</span><input v-model="testDialog.name" placeholder="例如：默认参数" /></label>
                <label v-for="parameter in testDialog.function.parameters || []" :key="parameter.parameter_id">
                    <span>{{ parameter.name }} <small>{{ parameter.type || 'any' }}</small></span>
                    <input v-model="testDialog.inputs[parameter.parameter_id]" :placeholder="parameter.required ? '必填' : '留空使用默认值'" />
                </label>
                <label><span>预期结果</span><select v-model="testDialog.expectedOutcomeId"><option value="">不校验</option><option v-for="outcome in testDialog.function.outcomes || []" :key="outcome.outcome_id" :value="outcome.outcome_id">{{ outcome.name }}</option></select></label>
                <p>测试使用隔离的临时主流程，不修改正式画布；结果、输出与异常会显示在运行日志中。</p>
            </div>
            <template #footer><el-button @click="testDialog.visible = false">取消</el-button><el-button type="primary" :disabled="store.isRunning || store.isPaused" @click="runFunctionTest"><Play :size="13" />保存并运行</el-button></template>
        </el-dialog>
    </section>
</template>

<script setup>
import { computed, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Braces, LockKeyhole, Play, Plus, Trash2 } from 'lucide-vue-next'
import ContractSection from './FunctionContractSection.vue'
import { useIdeStore } from '@/stores'
import { collectFunctionReferences, createStableId } from '@/utils/flowModel'
import { containsScopedReference, formatScopedReference, rewriteScopedReferences } from '@/utils/functionContract'

const store = useIdeStore()
const currentFunction = computed(() => {
    if (store.canvasMode !== 'function' || store.functionWorkspaceEmpty) return null
    return (store.blueprint?.functions || []).find(item => item.function_id === store.currentTaskId) || null
})
const referenceCount = computed(() => currentFunction.value ? collectFunctionReferences(store.blueprint, currentFunction.value.function_id).length : 0)
const testDialog = reactive({ visible: false, function: null, testId: '', name: '', inputs: {}, expectedOutcomeId: '' })

async function saveSelected() {
    const selected = currentFunction.value
    if (!selected) return
    const duplicate = section => new Set((selected[section] || []).map(item => item.name.trim())).size !== (selected[section] || []).length
    if (['parameters', 'local_variables', 'outputs'].some(duplicate)) return ElMessage.warning('同一契约分区内名称不能重复')
    try { await store.saveFunctionData(selected) } catch (error) { ElMessage.error(error.message || '函数保存失败') }
}

function addContractItem(section, prefix) {
    const selected = currentFunction.value
    if (!selected) return
    const items = selected[section] || (selected[section] = [])
    const used = new Set(items.map(item => item.name))
    const base = section === 'parameters' ? '参数' : section === 'local_variables' ? '局部变量' : '输出'
    let name = base, index = 1
    while (used.has(name)) name = `${base}${index++}`
    const idField = section === 'parameters' ? 'parameter_id' : section === 'local_variables' ? 'local_id' : 'output_id'
    items.push({ [idField]: createStableId(prefix), name, type: 'any', required: false, default_value: null, description: '' })
    saveSelected()
}

async function renameContractItem(section, { item, previousName, nextName }) {
    const selected = currentFunction.value
    if (!selected || previousName === nextName) return saveSelected()
    const names = (selected[section] || []).filter(candidate => candidate !== item).map(candidate => candidate.name)
    if (!nextName || names.includes(nextName)) {
        item.name = previousName
        ElMessage.warning(nextName ? '同一契约分区内名称不能重复' : '契约名称不能为空')
        return
    }
    const scope = section === 'parameters' ? 'param' : section === 'local_variables' ? 'local' : ''
    if (scope) for (const node of selected.graph?.nodes || []) node.params = rewriteScopedReferences(node.params || {}, scope, previousName, nextName)
    await store.saveWorkflowImmediately()
}

async function removeContractItem(section, index) {
    const selected = currentFunction.value
    const item = selected?.[section]?.[index]
    if (!selected || !item) return
    const scope = section === 'parameters' ? 'param' : section === 'local_variables' ? 'local' : ''
    if (scope && containsScopedReference(selected.graph?.nodes || [], scope, item.name)) return ElMessage.warning(`函数体仍在使用 ${formatScopedReference(scope, item.name)}，请先调整引用`)
    try {
        await ElMessageBox.confirm(`删除“${item.name}”？相关稳定 ID 绑定会同步清理。`, '删除函数契约项', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    } catch { return }

    const idField = section === 'parameters' ? 'parameter_id' : section === 'local_variables' ? 'local_id' : 'output_id'
    const stableId = item[idField]
    const graphs = [store.blueprint?.main_graph, ...(store.blueprint?.functions || []).map(fn => fn.graph)].filter(Boolean)
    for (const graph of graphs) {
        for (const node of graph.nodes || []) {
            if (node.node_type !== 'call_function' || node.params?.function_id !== selected.function_id) continue
            if (section === 'parameters') node.params.input_bindings = (node.params.input_bindings || []).filter(binding => binding.parameter_id !== stableId)
            if (section === 'outputs') node.params.output_bindings = (node.params.output_bindings || []).filter(binding => binding.output_id !== stableId)
        }
    }
    if (section === 'parameters') for (const testCase of selected.test_cases || []) if (testCase.inputs) delete testCase.inputs[stableId]
    if (section === 'outputs') for (const node of selected.graph?.nodes || []) if (node.node_type === 'function_return') node.params.output_bindings = (node.params.output_bindings || []).filter(binding => binding.output_id !== stableId)
    selected[section].splice(index, 1)
    await store.saveWorkflowImmediately()
}

function addOutcome() {
    const selected = currentFunction.value
    if (!selected) return
    const used = new Set(selected.outcomes.map(item => item.name))
    let name = '结果', index = 1
    while (used.has(name)) name = `结果${index++}`
    selected.outcomes.push({ outcome_id: createStableId('outcome'), name, color: 'success' })
    saveSelected()
}

async function removeOutcome(outcome) {
    const selected = currentFunction.value
    if (!selected) return
    const usedByReturns = (selected.graph?.nodes || []).some(node => node.node_type === 'function_return' && node.params?.outcome_id === outcome.outcome_id)
    if (usedByReturns) return ElMessage.warning('该结果仍被函数返回节点使用，请先调整返回节点')
    selected.outcomes = selected.outcomes.filter(item => item.outcome_id !== outcome.outcome_id)
    await saveSelected()
}

function openFunctionTest(item, testCase = null) {
    const inputs = {}
    for (const parameter of item.parameters || []) inputs[parameter.parameter_id] = testCase?.inputs?.[parameter.parameter_id] ?? ''
    Object.assign(testDialog, { visible: true, function: item, testId: testCase?.test_id || '', name: testCase?.name || `测试 ${(item.test_cases || []).length + 1}`, inputs, expectedOutcomeId: testCase?.expected_outcome_id || '' })
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
        const testCase = { test_id: testDialog.testId || createStableId('test'), name: testDialog.name.trim() || `测试 ${(fn.test_cases || []).length + 1}`, inputs, expected_outcome_id: testDialog.expectedOutcomeId || '' }
        fn.test_cases ||= []
        const existing = fn.test_cases.findIndex(item => item.test_id === testCase.test_id)
        existing >= 0 ? fn.test_cases.splice(existing, 1, testCase) : fn.test_cases.push(testCase)
        await saveSelected()

        const callId = createStableId('function_test_call')
        const nodes = [{ node_id: callId, node_name: `测试 ${fn.name}`, node_type: 'call_function', params: { function_id: fn.function_id, input_bindings: Object.entries(inputs).map(([parameter_id, value]) => ({ parameter_id, value })), output_bindings: (fn.outputs || []).map(output => ({ output_id: output.output_id, target: `$var.__function_test_${output.output_id}` })) }, delay_before: 0, loop_count: 1, enabled: true, position: { x: 80, y: 120 }, size: { w: 180, h: 92 } }]
        const edges = []
        ;(fn.outcomes || []).forEach((outcome, index) => {
            const logId = createStableId('function_test_result')
            const expected = !testCase.expected_outcome_id || testCase.expected_outcome_id === outcome.outcome_id
            nodes.push({ node_id: logId, node_name: expected ? '测试结果符合预期' : '测试结果不符合预期', node_type: 'log', params: { message: `${expected ? '[函数测试通过]' : '[函数测试未通过]'} 实际结果：${outcome.name}` }, delay_before: 0, loop_count: 1, enabled: true, position: { x: 360, y: 70 + index * 115 }, size: { w: 180, h: 84 } })
            edges.push({ edge_id: createStableId('edge'), source_node: callId, target_node: logId, source_port: `outcome_${index}`, source_port_id: outcome.outcome_id, canvas: 'workflow' })
        })
        const runtimeBlueprint = JSON.parse(JSON.stringify(store.blueprint))
        runtimeBlueprint.main_graph = { graph_id: 'main', nodes, edges }
        testDialog.visible = false
        await store.executionStore.runTask('main', callId, { blueprintData: runtimeBlueprint, skipSave: true, breakpoints: [] })
    } catch (error) { ElMessage.error(error.message || '函数测试启动失败') }
}

async function removeTestCase(testCase) {
    const selected = currentFunction.value
    if (!selected) return
    selected.test_cases = (selected.test_cases || []).filter(item => item.test_id !== testCase.test_id)
    await saveSelected()
}
</script>

<style scoped>
.function-inspector{width:100%;height:100%;min-height:0;display:flex;flex-direction:column;background:var(--app-panel-bg);color:var(--app-text-primary);font-size:11px}.inspector-heading{height:42px;display:flex;align-items:center;gap:5px;padding:0 9px;border-bottom:1px solid var(--app-separator)}.heading-copy{min-width:0;flex:1;display:flex;align-items:center;gap:8px}.heading-copy>svg{color:var(--el-color-primary)}.heading-copy>div{min-width:0;display:flex;flex-direction:column;gap:1px}.heading-copy strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px}.heading-copy small{color:var(--app-text-placeholder);font-size:10px}.inspector-heading>button,.contract-section button{width:28px;height:28px;display:grid;place-items:center;padding:0;border:0;border-radius:6px;background:transparent;color:var(--app-text-secondary);cursor:pointer}.inspector-heading>button:hover,.contract-section button:hover{background:var(--el-fill-color-light);color:var(--app-text-primary)}.inspector-scroll{min-height:0;flex:1;overflow:auto;padding:10px}.field-label{display:flex;flex-direction:column;gap:5px;margin-bottom:10px;color:var(--app-text-secondary);font-size:10px}.field-label input,.field-label textarea,.contract-row input,.outcome-row input,.contract-meta input{box-sizing:border-box;border:1px solid var(--app-border-subtle);border-radius:5px;outline:0;background:var(--app-input-bg);color:var(--app-text-primary);font:inherit}.field-label input{height:28px;padding:0 7px}.field-label textarea{width:100%;padding:6px;resize:vertical}.field-label input:focus,.field-label textarea:focus,.contract-row input:focus,.contract-meta input:focus{border-color:var(--el-color-primary);box-shadow:var(--focus-ring)}.contract-section{margin-top:12px}.contract-section>header{height:27px;display:flex;align-items:center;border-bottom:1px solid var(--app-separator);font-weight:650}.contract-section>header span{flex:1}.contract-section>header button{width:23px;height:23px}.contract-item{padding:6px 0;border-bottom:1px solid color-mix(in srgb,var(--app-separator) 55%,transparent)}.contract-row,.outcome-row,.test-row{min-height:29px;display:flex;align-items:center;gap:4px}.contract-row input,.outcome-row input{min-width:0;flex:1;height:26px;padding:0 6px}.contract-row select{width:72px;height:26px;border:1px solid var(--app-border-subtle);border-radius:5px;background:var(--app-input-bg);color:var(--app-text-secondary);font-size:10px}.contract-row button,.outcome-row button,.test-row>button{width:24px;height:24px}.contract-meta{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px;padding:4px 0 1px}.contract-meta>input{min-width:0;width:100%;height:24px;padding:0 6px;font-size:10px}.contract-meta>input:last-child{grid-column:1/-1}.contract-meta label{height:24px;display:flex;align-items:center;gap:3px;padding:0 6px;border:1px solid var(--app-border-subtle);border-radius:5px;color:var(--app-text-secondary);font-size:10px;white-space:nowrap}.contract-meta label input{accent-color:var(--el-color-primary)}.outcome-row>i{width:7px;height:7px;border-radius:50%;background:var(--el-color-success)}.outcome-row>i.danger{background:var(--el-color-danger)}.outcome-row>svg{margin:0 5px;color:var(--app-text-placeholder)}.test-row .test-name{min-width:0;flex:1;width:auto;display:flex;align-items:center;justify-content:flex-start;gap:5px;padding:0 5px}.test-name span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.empty-contract{height:26px;display:flex;align-items:center;color:var(--app-text-placeholder)}.function-test-form{display:grid;gap:10px}.function-test-form label{display:grid;grid-template-columns:130px 1fr;align-items:center;gap:10px;font-size:12px}.function-test-form label>span{display:flex;align-items:center;gap:6px;color:var(--app-text-secondary)}.function-test-form small{color:var(--app-text-placeholder)}.function-test-form input,.function-test-form select{height:31px;box-sizing:border-box;padding:0 8px;border:1px solid var(--app-border-subtle);border-radius:6px;background:var(--app-input-bg);color:var(--app-text-primary)}.function-test-form p{margin:3px 0 0;color:var(--app-text-placeholder);font-size:11px;line-height:1.55}
</style>
