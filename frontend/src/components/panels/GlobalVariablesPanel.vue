<!-- frontend/src/components/panels/GlobalVariablesPanel.vue -->
<template>
    <div class="global-vars-panel">
        <div class="accordion-container">
<!-- 1. 第一行：用户自定义全局变量 -->
            <div class="accordion-item" :class="{ 'is-expanded': expandedSection === 'user' }">
                <div class="accordion-header" @click="toggleSection('user')">
                    <div class="header-left">
                        <span class="header-title">用户自定义全局变量</span>
                        <span class="tab-badge">{{ userVarList.length }}</span>
                    </div>
                    <ChevronDown class="arrow-icon" :class="{ 'is-rotated': expandedSection === 'user' }" />
                </div>

                <div v-show="expandedSection === 'user'" class="accordion-content">
                    <!-- 工具栏：新建变量 + 清理未引用（配置客户表单/导出脚本包已移至顶栏「打包」菜单） -->
                    <div class="vars-toolbar">
                        <el-button size="small" type="primary" class="pure-btn btn-create" @click="openCreateDialog">
                            <Plus class="btn-icon" />
                            <span>新建变量</span>
                        </el-button>

                        <el-button
size="small"
                                   type="danger"
                                   plain
                                   class="pure-btn btn-clear-unused"
                                   :disabled="unusedVarCount === 0"
                                   @click="handleClearUnused">
                            <Trash2 class="btn-icon" />
                            <span>清理未引用 ({{ unusedVarCount }})</span>
                        </el-button>
                    </div>

                    <!-- 用户变量列表 -->
                    <div class="vars-list-scroll">
                        <template v-if="userVarList.length">
                            <div
v-for="item in userVarList"
                                 :key="item.key"
                                 class="var-card-row">
                                <!-- 左列：类型标识 Badge + 变量名 -->
                                <div class="var-name-col">
                                    <span class="type-badge" :class="`type-${item.type}`">{{ item.typeLabel }}</span>
                                    <span class="var-name-text" :title="item.key">{{ item.key }}</span>
                                </div>

                                <!-- 中列：静态当前值预览 -->
                                <div class="var-val-col">
                                    <span class="static-val-text" :title="item.displayValue">{{ item.displayValue }}</span>
                                </div>

                                <!-- 右列：默认显示引用次数，悬停淡入操作按钮组 -->
                                <div class="var-action-col">
                                    <span class="ref-tag" :class="{ 'is-unused': item.refCount === 0 }">
                                        {{ item.refCount > 0 ? `${item.refCount} 次引用` : '—' }}
                                    </span>

                                    <div class="hover-action-group">
                                        <button type="button" class="icon-action-btn" title="复制表达式 $var{xxx}" @click.stop="copyVarExpr(item.key)">
                                            <Copy class="lucide-svg" />
                                        </button>
                                        <button type="button" class="icon-action-btn" title="编辑变量" @click.stop="openEditDialog(item)">
                                            <Pencil class="lucide-svg" />
                                        </button>
                                        <button type="button" class="icon-action-btn danger" title="删除变量" @click.stop="handleDeleteVar(item.key)">
                                            <Trash2 class="lucide-svg" />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </template>

                        <div v-else class="empty-vars-tip">
                            暂无自定义变量，请点击上方【新建变量】按钮创建
                        </div>
                    </div>
                </div>
            </div>

            <!-- 2. 第二行：运行上下文变量 ($ctx) -->
            <div class="accordion-item" :class="{ 'is-expanded': expandedSection === 'ctx' }">
                <div class="accordion-header" @click="toggleSection('ctx')">
                    <div class="header-left">
                        <span class="header-title">运行上下文变量 ($ctx)</span>
                    </div>
                    <ChevronDown class="arrow-icon" :class="{ 'is-rotated': expandedSection === 'ctx' }" />
                </div>

                <div v-show="expandedSection === 'ctx'" class="accordion-content">
                    <div class="vars-list-scroll">
                        <!-- 运行上下文只读展示（左键右值 + 复制），工作面板设置统一走顶部「工作面板」入口 -->
                        <div class="ctx-readonly-hint">由顶部「工作面板」设置，此处只读展示，可复制表达式</div>
                        <div
v-for="item in ctxVarList"
                             :key="item.field"
                             class="var-card-row readonly-row">
                            <div class="var-name-col" :title="item.label">
                                <span class="var-name-text env-key">{{ item.token }}</span>
                            </div>
                            <div class="var-val-col">
                                <span class="static-val-text" :title="item.value">{{ item.value }}</span>
                            </div>
                            <div class="var-action-col">
                                <button type="button" class="icon-action-btn static-copy" title="复制表达式 $ctx{xxx}" @click.stop="copyCtxExpr(item.field)">
                                    <Copy class="lucide-svg" />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 3. 第三行：系统环境变量 ($env) -->
            <div class="accordion-item" :class="{ 'is-expanded': expandedSection === 'env' }">
                <div class="accordion-header" @click="toggleSection('env')">
                    <div class="header-left">
                        <span class="header-title">系统环境变量 ($env)</span>
                    </div>
                    <ChevronDown class="arrow-icon" :class="{ 'is-rotated': expandedSection === 'env' }" />
                </div>

                <div v-show="expandedSection === 'env'" class="accordion-content">
                    <div class="vars-list-scroll">
                        <div
v-for="env in systemEnvList"
                             :key="env.key"
                             class="var-card-row readonly-row">
                            <div class="var-name-col">
                                <span class="var-name-text env-key">{{ env.key }}</span>
                            </div>
                            <div class="var-desc-col">
                                <span>{{ env.desc }}</span>
                            </div>
                            <div class="var-action-col">
                                <button type="button" class="icon-action-btn static-copy" title="复制表达式 $env{xxx}" @click.stop="copyVarName(env.key)">
                                    <Copy class="lucide-svg" />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
</div>

        <!-- ⚡ 新建/编辑变量弹窗 -->
        <el-dialog
v-model="varDialogVisible"
                   :title="isEditing ? `✏️ 编辑变量 [${editingKey}]` : '➕ 新建全局变量'"
                   width="460px"
                   append-to-body
                   destroy-on-close
                   :close-on-click-modal="false">
            <div class="dialog-form-body">
                <template v-for="(schema, field) in activeFormSchema" :key="field">
                    <div class="form-item-wrapper">
                        <ParamRenderer
:config="schema"
                                       :value="dialogFormPayload[field]"
                                       :label="schema.label"
                                       :context="dialogFormPayload"
                                       @update="val => handleDialogParamUpdate(field, val)" />
                    </div>
                </template>
            </div>

            <template #footer>
                <div class="dialog-footer">
                    <el-button class="pure-btn" @click="varDialogVisible = false">
                        <X class="btn-icon" />
                        <span>取消</span>
                    </el-button>
                    <el-button type="primary" class="pure-btn" @click="confirmSaveVar">
                        <Check class="btn-icon" />
                        <span>确认保存</span>
                    </el-button>
                </div>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
    import { ref, computed, reactive } from 'vue'
    import { useMainStore } from '@/stores'
    import { ElMessage, ElMessageBox } from 'element-plus'
    import { Plus, Trash2, Copy, ChevronDown, Pencil, Check, X } from 'lucide-vue-next'
    import ParamRenderer from '@/components/ParamRenderer.vue'

    const store = useMainStore()
    const expandedSection = ref('user')

    const toggleSection = (key) => {
        expandedSection.value = expandedSection.value === key ? null : key
    }

    const varDialogVisible = ref(false)
    const isEditing = ref(false)
    const editingKey = ref('')

    const dialogFormPayload = reactive({
        name: '',
        type: 'string',
        value_number: 0,
        value_string: '',
        value_bool: false,
        value_json: ''
    })

    const openCreateDialog = () => {
        isEditing.value = false
        editingKey.value = ''
        dialogFormPayload.name = ''
        dialogFormPayload.type = 'number'
        dialogFormPayload.value_number = 0
        dialogFormPayload.value_string = ''
        dialogFormPayload.value_bool = false
        dialogFormPayload.value_json = '[]'
        varDialogVisible.value = true
    }

    const openEditDialog = (item) => {
        isEditing.value = true
        editingKey.value = item.key
        dialogFormPayload.name = item.key
        dialogFormPayload.type = item.type

        if (item.type === 'number') dialogFormPayload.value_number = Number(item.value) || 0
        else if (item.type === 'string') dialogFormPayload.value_string = String(item.value ?? '')
        else if (item.type === 'boolean') dialogFormPayload.value_bool = Boolean(item.value)
        else dialogFormPayload.value_json = JSON.stringify(item.value ?? (item.type === 'list' ? [] : {}), null, 2)

        varDialogVisible.value = true
    }

    const activeFormSchema = computed(() => {
        return {
            name: {
                type: 'str',
                label: '变量名称',
                placeholder: '仅支持字母、数字、下划线，如 run_count'
            },
            type: {
                type: 'select',
                label: '数据类型',
                options: [
                    { label: '数字 (Number)', value: 'number' },
                    { label: '文本 (String)', value: 'string' },
                    { label: '布尔 (Boolean)', value: 'boolean' },
                    { label: '数组 (List)', value: 'list' },
                    { label: '字典 (Dict)', value: 'dict' }
                ]
            },
            value_number: {
                type: 'int',
                label: '初始数值',
                default: 0,
                visible_if: { field: 'type', operator: 'eq', value: 'number' }
            },
            value_string: {
                type: 'str',
                label: '初始文本',
                default: '',
                placeholder: '请输入初始字符串',
                visible_if: { field: 'type', operator: 'eq', value: 'string' }
            },
            value_bool: {
                type: 'bool',
                label: '初始开关状态',
                default: false,
                visible_if: { field: 'type', operator: 'eq', value: 'boolean' }
            },
            value_json: {
                type: 'textarea',
                label: '初始 JSON 结构',
                default: '',
                placeholder: '列表如 ["a", "b"]；字典如 {"key": "val"}',
                rows: 3,
                visible_if: { field: 'type', operator: 'in', value: ['list', 'dict'] }
            }
        }
    })

    const handleDialogParamUpdate = (field, val) => {
        dialogFormPayload[field] = val
    }

    const confirmSaveVar = async () => {
        const name = dialogFormPayload.name ? dialogFormPayload.name.trim() : ''
        if (!name) return ElMessage.warning('请输入变量名称')

        if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name)) {
            return ElMessage.warning('变量名称只能包含字母、数字和下划线，且不能以数字开头')
        }

        if (!store.blueprint) store.blueprint = { variables: {} }
        if (!store.blueprint.variables) store.blueprint.variables = {}

        if (isEditing.value && editingKey.value && editingKey.value !== name) {
            delete store.blueprint.variables[editingKey.value]
        } else if (!isEditing.value && store.blueprint.variables[name] !== undefined) {
            return ElMessage.warning('该变量名称已存在，请勿重复创建')
        }

        let parsedVal = ''
        const type = dialogFormPayload.type

        if (type === 'number') parsedVal = Number(dialogFormPayload.value_number) || 0
        else if (type === 'string') parsedVal = String(dialogFormPayload.value_string ?? '')
        else if (type === 'boolean') parsedVal = Boolean(dialogFormPayload.value_bool)
        else if (type === 'list' || type === 'dict') {
            try {
                parsedVal = dialogFormPayload.value_json ? JSON.parse(dialogFormPayload.value_json) : (type === 'list' ? [] : {})
            } catch {
                return ElMessage.error('JSON 格式解析失败，请检查语法')
            }
        }

        store.blueprint.variables[name] = parsedVal
        await store.saveBlueprintImmediately()
        ElMessage.success(`变量 [${name}] 保存成功`)
        varDialogVisible.value = false
    }

    // ===== 运行上下文变量（$ctx）只读展示 =====
    const ctxFieldList = [
        { field: 'work_mode', label: '工作模式', token: '$ctx{work_mode}' },
        { field: 'title', label: '窗口标题', token: '$ctx{title}' },
        { field: 'is_emulator', label: '是否为模拟器', token: '$ctx{is_emulator}' },
        { field: 'content_offset', label: '内容偏移', token: '$ctx{content_offset}' },
        { field: 'target_content_size', label: '目标内容尺寸', token: '$ctx{target_content_size}' },
    ]

    const formatCtxValue = (val) => {
        if (val === undefined || val === null || val === '') return '—'
        if (Array.isArray(val) || typeof val === 'object') return JSON.stringify(val)
        if (typeof val === 'boolean') return val ? 'True' : 'False'
        return String(val)
    }

    // 工作面板设置统一走顶部「工作面板」入口，此处仅展示当前上下文值并支持复制
    const ctxVarList = computed(() => ctxFieldList.map(m => ({
        ...m,
        value: formatCtxValue(getCtxFieldValue(m.field))
    })))

    const getCtxFieldValue = (field) => {
        const ctx = store.currentContext || {}
        switch (field) {
            case 'work_mode': return ctx.workMode || 'window'
            case 'title': return ctx.windowTitle || ''
            case 'is_emulator': return !!ctx.isEmulator
            case 'content_offset':
                if (Array.isArray(ctx.contentOffset)) return ctx.contentOffset
                return [ctx.offsetTop || 0, ctx.offsetBottom || 0, ctx.offsetLeft || 0, ctx.offsetRight || 0]
            case 'target_content_size':
                if (Array.isArray(ctx.targetSize)) return ctx.targetSize
                return [ctx.targetWidth || 0, ctx.targetHeight || 0]
            default: return ''
        }
    }

    const systemEnvList = [
        { key: '$env.current_time', desc: '系统当前时间戳 (ms)' },
        { key: '$env.project_path', desc: '当前自动化项目根目录路径' },
        { key: '$env.last_error', desc: '最近一次节点的运行报错信息' },
        { key: '$env.loop_index', desc: '当前循环体内的索引序号' }
    ]

    const varReferenceCounts = computed(() => {
        const counts = {}
        const tasks = store.blueprint?.tasks || []

        const scanObj = (obj) => {
            if (!obj) return
            if (typeof obj === 'string') {
                // 新格式 $var{name} 与旧格式 {$var.name} / 裸 {name} 都计数
                for (const varName of Object.keys(store.blueprint?.variables || {})) {
                    if (obj === varName || obj.includes(`$var{${varName}}`) || obj.includes(`{${varName}}`) || obj.includes(`{$var.${varName}}`)) {
                        counts[varName] = (counts[varName] || 0) + 1
                    }
                }
            } else if (typeof obj === 'object') {
                for (const val of Object.values(obj)) {
                    scanObj(val)
                }
            }
        }

        tasks.forEach(t => {
            (t.nodes || []).forEach(n => {
                scanObj(n.params)
            })
        })

        return counts
    })

    const getVarType = (val) => {
        if (typeof val === 'boolean') return { type: 'boolean', label: 'BOOL' }
        if (typeof val === 'number') return { type: 'number', label: 'NUM' }
        if (Array.isArray(val)) return { type: 'list', label: 'LIST' }
        if (typeof val === 'object' && val !== null) return { type: 'dict', label: 'DICT' }
        return { type: 'string', label: 'STR' }
    }

    const formatDisplayValue = (val) => {
        if (Array.isArray(val)) return `${val.length} 项 (List)`
        if (typeof val === 'object' && val !== null) return `${Object.keys(val).length} 项 (Dict)`
        if (typeof val === 'boolean') return val ? 'True' : 'False'
        if (val === '' || val === undefined) return '—'
        return String(val)
    }

    const userVarList = computed(() => {
        const varsObj = store.blueprint?.variables || {}
        const refs = varReferenceCounts.value

        return Object.keys(varsObj).map(key => {
            const val = varsObj[key]
            const typeInfo = getVarType(val)
            return {
                key,
                value: val,
                type: typeInfo.type,
                typeLabel: typeInfo.label,
                displayValue: formatDisplayValue(val),
                refCount: refs[key] || 0
            }
        })
    })

    const unusedVarCount = computed(() => {
        return userVarList.value.filter(v => v.refCount === 0).length
    })

    const copyVarName = async (raw) => {
        // 输入形如 $env.current_time / $sys.xxx → 复制为新格式 $env{current_time}
        const m = String(raw || '').match(/^\$(env|sys)\.(.+)$/)
        const text = m ? `$${m[1]}{${m[2]}}` : String(raw || '')
        try {
            await navigator.clipboard.writeText(text)
            ElMessage.success(`已复制变量表达式: ${text}`)
        } catch {
            ElMessage.error('复制失败')
        }
    }

    const copyVarExpr = async (varName) => {
        const expr = `$var{${varName}}`
        try {
            await navigator.clipboard.writeText(expr)
            ElMessage.success(`已复制变量表达式: ${expr}`)
        } catch {
            ElMessage.error('复制失败')
        }
    }

    const copyCtxExpr = async (field) => {
        const expr = `$ctx{${field}}`
        try {
            await navigator.clipboard.writeText(expr)
            ElMessage.success(`已复制变量表达式: ${expr}`)
        } catch {
            ElMessage.error('复制失败')
        }
    }

    const handleDeleteVar = async (varName) => {
        try {
            await ElMessageBox.confirm(
                `确定要删除变量 [${varName}] 吗？删除后画布中对其引用的求值将失效。`,
                '删除变量确认',
                { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
            )
            delete store.blueprint.variables[varName]
            await store.saveBlueprintImmediately()
            ElMessage.success(`已删除变量 [${varName}]`)
        } catch {
            /* 取消删除 */
        }
    }

    const handleClearUnused = async () => {
        const unusedList = userVarList.value.filter(v => v.refCount === 0).map(v => v.key)
        if (unusedList.length === 0) return

        try {
            await ElMessageBox.confirm(
                `确定要清理以下 ${unusedList.length} 个未引用的变量吗？\n${unusedList.join(', ')}`,
                '清理确认',
                { confirmButtonText: '确定清理', cancelButtonText: '取消', type: 'warning' }
            )

            unusedList.forEach(key => {
                delete store.blueprint.variables[key]
            })
            await store.saveBlueprintImmediately()
            ElMessage.success(`成功清理 ${unusedList.length} 个未引用变量`)
        } catch (err) {
            if (err !== 'cancel') ElMessage.error('清理失败')
        }
    }
</script>

<style scoped>
    .global-vars-panel {
        width: 100%;
        height: 100%;
        display: flex;
        flex-direction: column;
        background: var(--el-bg-color);
        box-sizing: border-box;
        overflow-y: auto;
    }

    .accordion-container {
        display: flex;
        flex-direction: column;
        gap: 1px;
        background: var(--el-border-color-light);
    }

    .accordion-item {
        background: var(--el-bg-color);
        display: flex;
        flex-direction: column;
    }

    .accordion-header {
        padding: 10px 12px;
        background: rgba(25, 26, 38, 0.95);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: space-between;
        user-select: none;
        transition: background 0.2s;
    }

        .accordion-header:hover {
            background: rgba(38, 40, 61, 0.8);
        }

    .header-left {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .header-title {
        font-size: 12px;
        font-weight: 600;
        color: var(--el-text-color-primary);
    }

    .tab-badge {
        font-size: 10px;
        background: rgba(78, 209, 156, 0.15);
        color: var(--el-color-primary);
        padding: 1px 5px;
        border-radius: 10px;
    }

    .arrow-icon {
        width: 14px;
        height: 14px;
        color: var(--el-text-color-secondary);
        transition: transform 0.2s ease;
    }

        .arrow-icon.is-rotated {
            transform: rotate(180deg);
            color: var(--el-color-primary);
        }

    .accordion-content {
        display: flex;
        flex-direction: column;
        border-top: 1px solid var(--el-border-color-light);
        background: var(--el-bg-color);
    }

    .vars-toolbar {
        padding: 8px 12px;
        display: flex;
        gap: 8px;
        border-bottom: 1px solid var(--el-border-color-light);
        flex-shrink: 0;
        flex-wrap: wrap;
    }

    /* 通用按钮（对话框 footer 等）基础样式 */
    .pure-btn {
        display: flex;
        align-items: center;
        gap: 4px;
    }

    .btn-icon {
        width: 13px;
        height: 13px;
    }

    /* ⚡ 变量工具栏按钮统一风格：等高中距、图标对齐，主按钮实底突出、清理次按钮 */
    .vars-toolbar .pure-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 5px;
        min-height: 28px;
        padding: 4px 12px;
        border-radius: 6px;
        font-weight: 500;
        transition: all .15s;
        margin: 0;
    }

    .vars-toolbar .btn-create {
        background: var(--el-color-primary);
        border-color: var(--el-color-primary);
        color: #fff;
        box-shadow: 0 2px 6px rgba(78, 209, 156, 0.25);
    }

        .vars-toolbar .btn-create:hover:not(:disabled) {
            background: var(--el-color-primary-light-3);
            border-color: var(--el-color-primary-light-3);
            box-shadow: 0 3px 10px rgba(78, 209, 156, 0.35);
        }

    .vars-toolbar .btn-clear-unused {
        background: rgba(245, 108, 108, 0.08);
        border-color: rgba(245, 108, 108, 0.35);
        color: #f56c6c;
    }

        .vars-toolbar .btn-clear-unused:hover:not(:disabled) {
            background: #f56c6c;
            border-color: #f56c6c;
            color: #fff;
        }

    .vars-toolbar .pure-btn:disabled {
        opacity: .4;
        cursor: not-allowed;
        box-shadow: none;
    }

    .vars-toolbar .btn-icon {
        width: 13px;
        height: 13px;
    }

    .vars-list-scroll {
        padding: 10px 12px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        max-height: 480px;
        overflow-y: auto;
    }

    .var-card-row {
        position: relative;
        background: var(--el-fill-color-blank);
        border: 1px solid var(--el-border-color-light);
        border-radius: 6px;
        padding: 8px 10px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        transition: border-color 0.2s, background-color 0.2s;
    }

        .var-card-row:hover {
            border-color: var(--el-color-primary);
            background-color: rgba(78, 209, 156, 0.03);
        }

    .var-name-col {
        display: flex;
        align-items: center;
        gap: 6px;
        width: 130px;
        flex-shrink: 0;
    }

    .type-badge {
        font-size: 9px;
        font-weight: bold;
        padding: 1px 4px;
        border-radius: 3px;
        color: #fff;
        line-height: 1.2;
        flex-shrink: 0;
    }

    .type-number {
        background: #409eff;
    }

    .type-string {
        background: #67c23a;
    }

    .type-boolean {
        background: #e6a23c;
    }

    .type-list {
        background: #909399;
    }

    .type-dict {
        background: #f56c6c;
    }

    .var-name-text {
        font-size: 12px;
        font-weight: 600;
        color: var(--el-text-color-primary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .env-key {
        color: var(--el-color-primary);
    }

    .var-val-col {
        flex: 1;
        text-align: center;
        padding: 0 8px;
        overflow: hidden;
    }

    .static-val-text {
        font-size: 12px;
        color: var(--el-text-color-regular);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        display: block;
    }

    .var-action-col {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        width: 90px;
        flex-shrink: 0;
    }

    .ref-tag {
        font-size: 10px;
        color: var(--el-color-primary);
        background: rgba(78, 209, 156, 0.1);
        padding: 2px 6px;
        border-radius: 4px;
        white-space: nowrap;
    }

        .ref-tag.is-unused {
            color: var(--el-text-color-placeholder);
            background: transparent;
        }

    .hover-action-group {
        display: none;
        align-items: center;
        gap: 4px;
    }

    .var-card-row:hover .ref-tag {
        display: none;
    }

    .var-card-row:hover .hover-action-group {
        display: flex;
    }

    .icon-action-btn {
        background: transparent;
        border: none;
        color: var(--el-text-color-secondary);
        cursor: pointer;
        padding: 3px;
        border-radius: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
    }

        .icon-action-btn:hover {
            color: var(--el-color-primary);
            background: rgba(255, 255, 255, 0.08);
        }

        .icon-action-btn.danger:hover {
            color: var(--el-color-danger);
            background: rgba(245, 108, 108, 0.15);
        }

        .icon-action-btn.static-copy {
            opacity: 0;
        }

    .var-card-row:hover .icon-action-btn.static-copy {
        opacity: 1;
    }

    .lucide-svg {
        width: 13px;
        height: 13px;
    }

    .readonly-row {
        opacity: 0.9;
    }

    .var-desc-col {
        flex: 1;
        font-size: 11px;
        color: var(--el-text-color-secondary);
        text-align: right;
        padding-right: 6px;
    }

    .empty-vars-tip {
        font-size: 11px;
        color: var(--el-text-color-placeholder);
        text-align: center;
        padding: 20px 0;
        line-height: 1.6;
    }

    .ctx-readonly-hint {
        font-size: 11px;
        color: var(--el-text-color-placeholder);
        padding: 2px 4px 4px;
        line-height: 1.5;
    }

    .dialog-form-body {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .form-item-wrapper {
        width: 100%;
    }

    .dialog-footer {
        display: flex;
        justify-content: flex-end;
        gap: 10px;
    }
</style>