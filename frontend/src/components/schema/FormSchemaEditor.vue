<!-- frontend/src/components/schema/FormSchemaEditor.vue -->
<template>
    <el-dialog
v-model="dialogVisible"
               width="850px"
               append-to-body
               destroy-on-close
               :close-on-click-modal="false">
        <template #header>
            <span class="el-dialog__title">
                <Wrench :size="16" style="vertical-align: middle;" />
                {{ mode === 'publish' ? '发布脚本包' : 'Player 配置' }}
            </span>
        </template>
        <div class="schema-editor-body">
            <!-- 顶栏标题与配置操作 -->
            <div class="header-toolbar">
                <el-input v-model="localSchema.form_title" placeholder="请输入客户面板标题（如：弹弹堂挂机助手配置）" style="width: 320px;" size="small" />
                <div class="right-btns">
                    <el-button type="primary" plain size="small" @click="addGroup"><Plus :size="14" style="vertical-align: middle;" /> 添加配置分组</el-button>
                    <el-button type="warning" plain size="small" @click="autoGenerateFromVars"><Zap :size="14" style="vertical-align: middle;" /> 从现有变量一键生成</el-button>
                    <el-button type="success" plain size="small" @click="addContextFields"><MonitorCog :size="14" style="vertical-align: middle;" /> 一键添加上下文配置（窗口与裁剪）</el-button>
                </div>
            </div>

            <!-- ⚡ 运行入口配置：打包时指定 Player 端点击「运行」的起始节点 -->
            <div class="entry-config-bar">
                <span class="entry-label"><Flag :size="14" style="vertical-align: middle;" /> 运行入口（Player 点击运行将从此节点开始）</span>
                <span class="entry-main-chip">主流程</span>
                <el-select v-model="entryNodeId" placeholder="选择主流程起始节点" size="small" style="width: 230px;" clearable>
                    <el-option v-for="n in entryNodes" :key="n.node_id" :label="n.node_name || n.node_id" :value="n.node_id" />
                </el-select>
                <span v-if="entryNodeId" class="entry-preview">→ 主流程 / {{ entryNodeName }}</span>
                <el-button v-if="entryNodeId" type="info" link size="small" @click="clearEntry">清除入口</el-button>
            </div>

            <!-- 分组卡片列表 -->
            <div class="groups-container">
                <div v-for="(group, gIdx) in localSchema.groups" :key="gIdx" class="group-card">
                    <div class="group-header">
                        <div class="group-title-input">
                            <span class="drag-handle"><GripVertical :size="14" /></span>
                            <el-input v-model="group.group_title" placeholder="分组名称（如：挂机功能选择）" size="small" style="width: 240px;" />
                        </div>
                        <div class="group-actions">
                            <el-button type="primary" link size="small" @click="addField(group)"><Plus :size="14" style="vertical-align: middle;" /> 添加控件项</el-button>
                            <el-button type="danger" link size="small" @click="removeGroup(gIdx)">删除分组</el-button>
                        </div>
                    </div>

                    <!-- 字段控件列表表格 -->
                    <div class="fields-table-wrapper">
                        <table v-if="group.fields && group.fields.length" class="schema-fields-table">
                            <thead>
                                <tr>
                                    <th width="160">控件 Label 标题</th>
                                    <th width="150">Target 寻址目标</th>
                                    <th width="130">控件 UI 类型</th>
                                    <th width="130">默认值/选项</th>
                                    <th width="130">动态 Provider</th>
                                    <th width="70">操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="(field, fIdx) in group.fields" :key="fIdx">
                                    <td>
                                        <el-input v-model="field.label" placeholder="如: 刷日常副本" size="small" />
                                    </td>
                                    <td>
                                        <el-select v-model="field.target" placeholder="目标路径" size="small" filterable allow-create @change="() => onTargetChange(field)">
                                            <el-option-group label="全局变量 ($var)">
                                                <el-option v-for="v in globalVarNames" :key="`$var.${v}`" :label="`$var.${v}`" :value="`$var.${v}`" />
                                            </el-option-group>
                                            <el-option-group label="上下文参数 ($ctx)">
                                                <el-option label="$ctx.image_threshold" value="$ctx.image_threshold" />
                                                <el-option label="$ctx.ocr_confidence" value="$ctx.ocr_confidence" />
                                                <el-option label="$ctx.max_retry" value="$ctx.max_retry" />
                                            </el-option-group>
                                            <el-option-group label="项目运行设置 ($settings)">
                                                <el-option v-for="item in settingBindingOptions" :key="item.target" :label="item.label" :value="item.target" />
                                            </el-option-group>
                                            <el-option-group label="节点运行属性 ($node)">
                                                <el-option v-for="item in nodeBindingOptions" :key="item.target" :label="item.label" :value="item.target" />
                                            </el-option-group>
                                        </el-select>
                                    </td>
                                    <td>
                                        <el-select v-model="field.ui_type" size="small" @change="() => onUiTypeChange(field)">
                                            <el-option label="多选框组" value="checkbox_group" />
                                            <el-option label="下拉选择" value="select" />
                                            <el-option label="字符串输入" value="str" />
                                            <el-option label="密码输入" value="secret" />
                                            <el-option label="数字微调" value="number" />
                                            <el-option label="匹配滑块" value="slider" />
                                            <el-option label="逻辑开关" value="switch" />
                                            <el-option label="图片（支持 Player 截图替换）" value="image_asset" />
                                        </el-select>
                                    </td>
                                    <td>
                                        <template v-if="field.ui_type === 'switch'">
                                            <el-switch v-model="field.default" size="small" />
                                        </template>
                                        <template v-else-if="field.ui_type === 'number' || field.ui_type === 'slider'">
                                            <el-input-number v-model="field.default" size="small" controls-position="right" style="width: 100%;" />
                                        </template>
                                        <template v-else-if="field.ui_type === 'select' || field.ui_type === 'checkbox_group'">
                                            <el-input v-model="field.default_str" placeholder="默认值" size="small" @change="val => parseDefaultValue(field, val)" />
                                            <el-input v-model="field.options_str" placeholder="选项：A,B,C" size="small" style="margin-top: 4px;" @change="val => parseStaticOptions(field, val)" />
                                        </template>
                                        <template v-else>
                                            <el-input v-model="field.default_str" placeholder="默认值/逗号分隔" size="small" @change="val => parseDefaultValue(field, val)" />
                                        </template>
                                    </td>
                                    <td>
                                        <el-select v-model="field.provider" placeholder="静态选项" size="small" clearable>
                                            <el-option label="静态 Options" value="" />
                                            <el-option label="当前打开窗口列表" value="sys.window_list" />
                                            <el-option label="显示器分辨率" value="sys.monitors" />
                                            <el-option label="硬件串口端口" value="sys.com_ports" />
                                        </el-select>
                                    </td>
                                    <td>
                                        <el-button type="primary" link size="small" @click="openAdvanced(field)">高级</el-button>
                                        <el-button type="danger" link size="small" @click="removeField(group, fIdx)">删除</el-button>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                        <div v-else class="empty-field-tip">
                            暂无控件项，点击右上角“添加控件项”以定义此分组表单
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <el-dialog v-model="advancedVisible" title="字段高级设置" width="520px" append-to-body>
            <el-form v-if="advancedField" label-width="100px" size="small">
                <el-form-item label="帮助说明"><el-input v-model="advancedField.help" type="textarea" :rows="2" /></el-form-item>
                <el-form-item label="占位提示"><el-input v-model="advancedField.placeholder" /></el-form-item>
                <el-form-item label="必填"><el-switch v-model="advancedField.required" /></el-form-item>
                <template v-if="advancedField.ui_type === 'number' || advancedField.ui_type === 'slider'">
                    <el-form-item label="最小值"><el-input-number v-model="advancedField.min" controls-position="right" /></el-form-item>
                    <el-form-item label="最大值"><el-input-number v-model="advancedField.max" controls-position="right" /></el-form-item>
                    <el-form-item label="步长"><el-input-number v-model="advancedField.step" :min="0.000001" controls-position="right" /></el-form-item>
                </template>
                <el-form-item v-if="advancedField.ui_type === 'str' || advancedField.ui_type === 'secret'" label="格式正则">
                    <el-input v-model="advancedField.pattern" placeholder="例如：[a-zA-Z0-9_]+" />
                </el-form-item>
            </el-form>
            <template #footer><el-button type="primary" @click="advancedVisible = false">完成</el-button></template>
        </el-dialog>

        <template #footer>
            <div class="dialog-footer">
                <el-button size="small" @click="dialogVisible = false">取消</el-button>
                <el-button v-if="mode === 'publish'" type="success" plain size="small" @click="handleExportPackage"><Package :size="14" style="vertical-align: middle;" /> 仅打包密包 (.ebp)</el-button>
                <el-button v-if="mode === 'publish'" type="warning" plain size="small" :loading="compileLoading" @click="handleCompileExecutable">
                    <Hammer :size="14" style="vertical-align: middle;" /> 一键编译发布完整客户端 (.exe)
                </el-button>
                <el-button type="primary" size="small" @click="handleSaveSchema">确认并保存 Schema</el-button>
            </div>
        </template>
    </el-dialog>
</template>

<script setup>
    import { ref, computed, watch, reactive } from 'vue'
    import { useIdeStore } from '@/stores'
    import { ElMessage, ElLoading, ElMessageBox } from 'element-plus'
    import { exporterApi } from '@/api/exporterApi'
    import client from '@/api/client'
    import { normalizePlayerSchema } from '@/utils/playerSchema'
    import { Wrench, GripVertical, Plus, Package, Hammer, Zap, Flag, MonitorCog } from 'lucide-vue-next'

    const props = defineProps({
        modelValue: { type: Boolean, default: false },
        mode: { type: String, default: 'configure' }
    })

    const emit = defineEmits(['update:modelValue', 'saved'])
    const store = useIdeStore()

    const dialogVisible = computed({
        get: () => props.modelValue,
        set: (val) => emit('update:modelValue', val)
    })

    const compileLoading = ref(false)
    const advancedVisible = ref(false)
    const advancedField = ref(null)
    const projectSettingGroups = ref([])

    const localSchema = reactive({
        schema_version: 3,
        form_title: '弹弹堂挂机助手 - 客户配置面板',
        groups: [],
        entry: null  // { task_id, node_id, node_name } Player 运行入口
    })

    const globalVarNames = computed(() => {
        return Object.keys(store.blueprint?.variables || {})
    })

    const settingBindingOptions = computed(() => projectSettingGroups.value.flatMap(group =>
        (group.fields || []).map(field => ({
            target: `$settings.${field.key}`,
            label: `${group.title} / ${field.label}`,
            default: store.blueprint?.settings?.[field.key],
            type: field.type
        }))
    ))

    const graphTasks = computed(() => [
        { task_id: 'main', task_name: '主流程', canvasLabel: '主流程', ...(store.blueprint?.main_graph || {}) },
        ...(store.blueprint?.functions || []).map(fn => ({
            task_id: fn.function_id,
            task_name: fn.name,
            canvasLabel: '函数',
            ...(fn.graph || {})
        })),
        { task_id: 'page_map', task_name: '页面地图', canvasLabel: '页面地图', ...(store.blueprint?.page_map || {}) }
    ])

    const flattenRuntimeLeaves = (value, path = [], result = []) => {
        if (Array.isArray(value)) {
            value.forEach((item, index) => flattenRuntimeLeaves(item, [...path, String(index)], result))
            return result
        }
        if (value && typeof value === 'object') {
            Object.entries(value).forEach(([key, child]) => flattenRuntimeLeaves(child, [...path, key], result))
            return result
        }
        if (path.length) result.push({ path: path.join('.'), value, leaf: path.at(-1) })
        return result
    }

    const runtimePathLabel = path => path.split('.').map(part => /^\d+$/.test(part) ? `#${Number(part) + 1}` : part).join(' / ')

    const nodeBindingOptions = computed(() => graphTasks.value.flatMap(task => (task.nodes || []).flatMap(node => {
        const base = `${task.canvasLabel} / ${task.task_name || task.task_id} / ${node.node_name || node.node_id}`
        const paramSchema = store.paramsDefinitions?.[node.node_type]?.params || {}
        const params = flattenRuntimeLeaves(node.params || {})
            .filter(item => item.path !== 'page_id')
            .map(item => ({
                target: `$node.${node.node_id}.params.${item.path}`,
                label: `${base} / ${paramSchema[item.path]?.label || runtimePathLabel(item.path)}`,
                default: item.value,
                key: item.path,
                isImage: item.leaf.endsWith('image_source')
            }))
        return [
            { target: `$node.${node.node_id}.delay_before`, label: `${base} / 执行前延迟`, default: node.delay_before ?? 0, key: 'delay_before' },
            { target: `$node.${node.node_id}.loop_count`, label: `${base} / 循环次数`, default: node.loop_count ?? 1, key: 'loop_count' },
            ...params
        ]
    })))

    const bindingOption = target => [...settingBindingOptions.value, ...nodeBindingOptions.value]
        .find(item => item.target === target)

    const onTargetChange = field => {
        const option = bindingOption(field.target)
        if (!option) return
        field.default = JSON.parse(JSON.stringify(option.default ?? ''))
        field.default_str = Array.isArray(field.default) ? field.default.join(',') : String(field.default ?? '')
        if (option.isImage) field.ui_type = 'image_asset'
        else if (typeof option.default === 'boolean' || option.type === 'bool') field.ui_type = 'switch'
        else if (typeof option.default === 'number' || option.type === 'number') field.ui_type = 'number'
        else field.ui_type = 'str'
    }

    // ===== ⚡ 运行入口配置（打包时指定 Player 端起始节点） =====
    const entryTaskId = ref('main')
    const entryNodeId = ref('')
    const entryNodes = computed(() => store.blueprint?.main_graph?.nodes || [])
    const entryNodeName = computed(() => entryNodes.value.find(n => n.node_id === entryNodeId.value)?.node_name || '')

    const clearEntry = () => {
        entryTaskId.value = 'main'
        entryNodeId.value = ''
        localSchema.entry = null
    }

    // ===== ⚡ 一键添加上下文配置（窗口选择 + 裁剪表单，target 指向 $ctx.*） =====
    const addContextFields = () => {
        const fields = [
            { label: '目标窗口', target: '$ctx.window_title', ui_type: 'select', default: '', default_str: '', provider: 'sys.window_list' },
            { label: '模拟器模式', target: '$ctx.is_emulator', ui_type: 'switch', default: false, default_str: '', provider: '' },
            { label: '上裁剪', target: '$ctx.offset_top', ui_type: 'number', default: 0, default_str: '0', provider: '' },
            { label: '下裁剪', target: '$ctx.offset_bottom', ui_type: 'number', default: 0, default_str: '0', provider: '' },
            { label: '左裁剪', target: '$ctx.offset_left', ui_type: 'number', default: 0, default_str: '0', provider: '' },
            { label: '右裁剪', target: '$ctx.offset_right', ui_type: 'number', default: 0, default_str: '0', provider: '' },
            { label: '目标宽度', target: '$ctx.target_content_width', ui_type: 'number', default: 1280, default_str: '1280', provider: '' },
            { label: '目标高度', target: '$ctx.target_content_height', ui_type: 'number', default: 718, default_str: '718', provider: '' },
        ]
        const existing = localSchema.groups.find(g => g.group_title === '窗口与裁剪')
        if (existing) {
            existing.fields = fields
        } else {
            localSchema.groups.push({ group_title: '窗口与裁剪', fields })
        }
        ElMessage.success('已生成「窗口与裁剪」上下文配置组（客户可选窗口并调整裁剪）')
    }

    const addGroup = () => {
        localSchema.groups.push({
            group_title: `功能分组 ${localSchema.groups.length + 1}`,
            fields: []
        })
    }

    const removeGroup = (idx) => {
        localSchema.groups.splice(idx, 1)
    }

    const addField = (group) => {
        if (!group.fields) group.fields = []
        group.fields.push({
            label: '新功能设置',
            target: '$var.new_feature',
            ui_type: 'switch',
            default: true,
            default_str: '',
            options: [],
            options_str: '',
            provider: '',
            required: false,
            help: '',
            placeholder: ''
        })
    }

    const removeField = (group, idx) => {
        group.fields.splice(idx, 1)
    }

    const onUiTypeChange = (field) => {
        if (field.ui_type === 'switch') field.default = true
        else if (field.ui_type === 'number' || field.ui_type === 'slider') field.default = 10
        else if (field.ui_type === 'checkbox_group') field.default = []
        else field.default = ''
    }

    const openAdvanced = (field) => {
        if (field.required === undefined) field.required = false
        if ((field.ui_type === 'number' || field.ui_type === 'slider') && field.step === undefined) field.step = 1
        advancedField.value = field
        advancedVisible.value = true
    }

    const parseDefaultValue = (field, valStr) => {
        if (field.ui_type === 'checkbox_group') {
            field.default = valStr.split(',').map(s => s.trim()).filter(Boolean)
        } else {
            field.default = valStr
        }
    }

    const parseStaticOptions = (field, value) => {
        field.options = String(value || '').split(',').map(item => item.trim()).filter(Boolean).map(item => {
            const separator = item.indexOf('=')
            if (separator > 0) return { label: item.slice(0, separator).trim(), value: item.slice(separator + 1).trim() }
            return { label: item, value: item }
        })
    }

    const prepareEditorSchema = (schema) => {
        const normalized = normalizePlayerSchema(schema)
        normalized.groups.forEach(group => group.fields.forEach(field => {
            field.default_str = Array.isArray(field.default) ? field.default.join(',') : String(field.default ?? '')
            field.options_str = (field.options || []).map(option => option.label === String(option.value) ? option.label : `${option.label}=${option.value}`).join(',')
        }))
        return normalized
    }

    const autoGenerateFromVars = () => {
        const varsObj = store.blueprint?.variables || {}
        const keys = Object.keys(varsObj)
        if (!keys.length) {
            return ElMessage.warning('当前项目暂无全局变量，请先在左侧变量面板新建')
        }

        const autoFields = keys.map(k => {
            const val = varsObj[k]
            let uiType = 'str'
            if (typeof val === 'boolean') uiType = 'switch'
            else if (typeof val === 'number') uiType = 'number'
            else if (Array.isArray(val)) uiType = 'checkbox_group'

            return {
                label: k,
                target: `$var.${k}`,
                ui_type: uiType,
                default: val,
                default_str: Array.isArray(val) ? val.join(',') : String(val),
                provider: ''
            }
        })

        localSchema.groups = [
            {
                group_title: '主运行参数配置',
                fields: autoFields
            }
        ]
        ElMessage.success('已自动根据全局变量生成 Schema 分组配置')
    }

    watch(() => props.modelValue, async (val) => {
        if (val && store.currentProjectPath) {
            try {
                const settingsResponse = await client.get('/api/project/settings', { params: { project_path: store.currentProjectPath } })
                projectSettingGroups.value = settingsResponse.groups || []
            } catch {
                projectSettingGroups.value = []
            }
            try {
                const res = prepareEditorSchema(await exporterApi.getFormSchema(store.currentProjectPath))
                if (res && res.groups && res.groups.length) {
                    Object.assign(localSchema, res)
                } else {
                    autoGenerateFromVars()
                }
                // ⚡ 回显运行入口配置
                localSchema.entry = res.entry || null
                entryTaskId.value = 'main'
                entryNodeId.value = res.entry?.task_id === 'main' ? (res.entry?.node_id || '') : ''
            } catch {
                autoGenerateFromVars()
            }
        }
    }, { immediate: false })

    // ⚡ 打包/保存前同步入口配置到 schema（下拉选中 → localSchema.entry）
    const syncEntry = () => {
        localSchema.schema_version = 3
        if (entryNodeId.value) {
            localSchema.entry = {
                task_id: 'main',
                node_id: entryNodeId.value,
                node_name: entryNodeName.value || entryNodeId.value
            }
        } else {
            localSchema.entry = null
        }
    }


    const validateSchemaDraft = () => {
        const targets = new Set()
        for (const group of localSchema.groups || []) {
            for (const field of group.fields || []) {
                if (!field.label?.trim()) {
                    ElMessage.error('存在未填写标题的客户参数')
                    return false
                }
                const target = field.target || ''
                const validTarget = /^\$(var|ctx)\.[A-Za-z_][\w.-]*$/.test(target)
                    || /^\$settings\.[A-Za-z_][\w-]*$/.test(target)
                    || /^\$node\.[A-Za-z0-9_-]+\.(delay_before|loop_count|params\.[A-Za-z_][\w.-]*)$/.test(target)
                if (!validTarget) {
                    ElMessage.error(`参数「${field.label}」没有绑定到合法的变量、上下文、项目设置或节点运行属性`)
                    return false
                }
                if (targets.has(field.target)) {
                    ElMessage.error(`Target 重复：${field.target}`)
                    return false
                }
                targets.add(field.target)
                if ((field.ui_type === 'select' || field.ui_type === 'checkbox_group') && !field.provider && !(field.options || []).length) {
                    ElMessage.error(`参数「${field.label}」需要填写静态选项或选择动态 Provider`)
                    return false
                }
                if ((field.ui_type === 'number' || field.ui_type === 'slider') && field.min != null && field.max != null && field.min > field.max) {
                    ElMessage.error(`参数「${field.label}」的最小值不能大于最大值`)
                    return false
                }
            }
        }
        return true
    }

    const runPreflight = async () => {
        const report = await client.post('/api/exporter/preflight', {
            project_path: store.currentProjectPath,
            form_schema: localSchema
        })
        const errors = (report.issues || []).filter(issue => issue.severity === 'error')
        const warnings = (report.issues || []).filter(issue => issue.severity === 'warning')
        const formatIssues = issues => issues.slice(0, 12).map(issue => `• ${issue.message}${issue.location ? `（${issue.location}）` : ''}`).join('\n')
        if (errors.length) {
            await ElMessageBox.alert(formatIssues(errors), `发布前检查失败（${errors.length} 项错误）`, {
                type: 'error',
                confirmButtonText: '返回修改'
            })
            return { ok: false, acknowledgeWarnings: false, report }
        }
        if (warnings.length) {
            try {
                await ElMessageBox.confirm(formatIssues(warnings), `发布前检查发现 ${warnings.length} 项警告`, {
                    type: 'warning',
                    confirmButtonText: '确认并继续',
                    cancelButtonText: '返回修改'
                })
            } catch {
                return { ok: false, acknowledgeWarnings: false, report }
            }
        }
        const suggestions = report.counts?.suggestion || 0
        if (suggestions) ElMessage.info(`发布前检查通过，另有 ${suggestions} 项优化建议`)
        return { ok: true, acknowledgeWarnings: warnings.length > 0, report }
    }

    const handleSaveSchema = async () => {
        try {
            syncEntry()
            if (!validateSchemaDraft()) return
            await exporterApi.saveFormSchema(store.currentProjectPath, localSchema)
            ElMessage.success('客户表单 Schema 配置保存成功')
            emit('saved')
            dialogVisible.value = false
        } catch (err) {
            ElMessage.error('保存失败: ' + err.message)
        }
    }

    const handleExportPackage = async () => {
        try {
            syncEntry()
            if (!validateSchemaDraft()) return
            const preflight = await runPreflight()
            if (!preflight.ok) return
            ElMessage.info('打包编译资产密包中...')
            const res = await client.post('/api/exporter/build', {
                project_path: store.currentProjectPath,
                form_schema: localSchema,
                acknowledge_warnings: preflight.acknowledgeWarnings
            })
            if (res.success) {
                ElMessage.success(`资产密包导出成功：${res.ebp_file}`)
            }
        } catch (err) {
            ElMessage.error('导出打包失败: ' + err.message)
        }
    }

    // ⚡ 工业级一键编译 .exe 客户端交付包 (带全屏 Loading 遮罩与 5 分钟超时放宽)
    const handleCompileExecutable = async () => {
        const loadingInstance = ElLoading.service({
            lock: true,
            text: '正在后台使用 PyInstaller 构建 .exe 客户端，预计耗时 30 秒至 2 分钟…',
            background: 'rgba(0, 0, 0, 0.7)'
        })

        try {
            compileLoading.value = true

            // 1. 同步入口配置并保存 Schema
            syncEntry()
            if (!validateSchemaDraft()) return
            const preflight = await runPreflight()
            if (!preflight.ok) return
            await exporterApi.saveFormSchema(store.currentProjectPath, localSchema)
            // 2. 打包资产密包
            await client.post('/api/exporter/build', {
                project_path: store.currentProjectPath,
                form_schema: localSchema,
                acknowledge_warnings: preflight.acknowledgeWarnings
            })

            // 3. 异步触发后端 PyInstaller 编译，timeout 放宽至 300,000ms (5分钟)
            const res = await client.post('/api/exporter/compile-exe', {
                project_path: store.currentProjectPath
            }, {
                timeout: 300000
            })

            const result = res?.data || res
            if (result?.success) {
                ElMessage.success(`客户端 .exe 编译打包成功：${result.output_dir}`)
            }
        } catch (err) {
            const errDetail = err.response?.data?.detail || err.message
            ElMessage.error('编译 .exe 客户端失败: ' + errDetail)
        } finally {
            compileLoading.value = false
            loadingInstance.close() // 无论成功失败，必须关闭 Loading 遮罩
        }
    }
</script>

<style scoped>
    .schema-editor-body {
        display: flex;
        flex-direction: column;
        gap: 12px;
        max-height: 70vh;
        overflow-y: auto;
    }

    .header-toolbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: var(--el-fill-color-blank);
        padding: 10px 12px;
        border-radius: 8px;
        border: 1px solid var(--el-border-color-light);
    }

    .entry-config-bar {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border-radius: 8px;
        border: 1px dashed var(--el-color-primary-light-5);
        background: var(--el-color-primary-light-9);
    }

    .entry-label {
        font-size: 12px;
        font-weight: 600;
        color: var(--el-color-primary);
        white-space: nowrap;
    }

    .entry-main-chip {
        display: inline-flex;
        align-items: center;
        height: 26px;
        padding: 0 10px;
        border: 1px solid var(--el-border-color);
        border-radius: 7px;
        background: var(--el-fill-color-light);
        color: var(--el-text-color-regular);
        font-size: 12px;
        font-weight: 600;
        white-space: nowrap;
    }

    .entry-preview {
        font-size: 12px;
        color: var(--el-color-success);
        white-space: nowrap;
    }

    .right-btns {
        display: flex;
        gap: 8px;
    }

    .groups-container {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .group-card {
        background: var(--el-bg-color);
        border: 1px solid var(--el-border-color-light);
        border-radius: 8px;
        padding: 12px;
    }

    .group-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }

    .group-title-input {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .drag-handle {
        cursor: grab;
        color: var(--el-text-color-secondary);
    }

    .fields-table-wrapper {
        width: 100%;
        overflow-x: auto;
    }

    .schema-fields-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
    }

        .schema-fields-table th, .schema-fields-table td {
            border: 1px solid var(--el-border-color-light);
            padding: 6px 8px;
            text-align: left;
        }

        .schema-fields-table th {
            background: var(--el-fill-color-blank);
            color: var(--el-text-color-regular);
        }

    .empty-field-tip {
        font-size: 11px;
        color: var(--el-text-color-placeholder);
        text-align: center;
        padding: 16px 0;
    }
</style>
