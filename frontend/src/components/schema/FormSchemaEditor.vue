<!-- frontend/src/components/schema/FormSchemaEditor.vue -->
<template>
    <el-dialog
v-model="dialogVisible"
               title="🛠️ 配置暴露给客户的动态表单面板 (Schema Editor)"
               width="850px"
               append-to-body
               destroy-on-close
               :close-on-click-modal="false">
        <div class="schema-editor-body">
            <!-- 顶栏标题与配置操作 -->
            <div class="header-toolbar">
                <el-input v-model="localSchema.form_title" placeholder="请输入客户面板标题（如：弹弹堂挂机助手配置）" style="width: 320px;" size="small" />
                <div class="right-btns">
                    <el-button type="primary" plain size="small" @click="addGroup">➕ 添加配置分组</el-button>
                    <el-button type="warning" plain size="small" @click="autoGenerateFromVars">⚡ 从现有变量一键生成</el-button>
                </div>
            </div>

            <!-- 分组卡片列表 -->
            <div class="groups-container">
                <div v-for="(group, gIdx) in localSchema.groups" :key="gIdx" class="group-card">
                    <div class="group-header">
                        <div class="group-title-input">
                            <span class="drag-handle">☰</span>
                            <el-input v-model="group.group_title" placeholder="分组名称（如：挂机功能选择）" size="small" style="width: 240px;" />
                        </div>
                        <div class="group-actions">
                            <el-button type="primary" link size="small" @click="addField(group)">➕ 添加控件项</el-button>
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
                                        <el-select v-model="field.target" placeholder="目标路径" size="small" filterable allow-create>
                                            <el-option-group label="全局变量 ($var)">
                                                <el-option v-for="v in globalVarNames" :key="`$var.${v}`" :label="`$var.${v}`" :value="`$var.${v}`" />
                                            </el-option-group>
                                            <el-option-group label="上下文参数 ($ctx)">
                                                <el-option label="$ctx.image_threshold" value="$ctx.image_threshold" />
                                                <el-option label="$ctx.ocr_confidence" value="$ctx.ocr_confidence" />
                                                <el-option label="$ctx.max_retry" value="$ctx.max_retry" />
                                            </el-option-group>
                                            <el-option-group label="系统环境 ($env)">
                                                <el-option label="$env.target_window_title" value="$env.target_window_title" />
                                                <el-option label="$env.auto_save_log" value="$env.auto_save_log" />
                                            </el-option-group>
                                        </el-select>
                                    </td>
                                    <td>
                                        <el-select v-model="field.ui_type" size="small" @change="() => onUiTypeChange(field)">
                                            <el-option label="☑️ 多选框组" value="checkbox_group" />
                                            <el-option label="🔘 下拉选择" value="select" />
                                            <el-option label="🔤 字符串输入" value="str" />
                                            <el-option label="🔢 数字微调" value="number" />
                                            <el-option label="🎚️ 匹配滑块" value="slider" />
                                            <el-option label="🔀 逻辑开关" value="switch" />
                                        </el-select>
                                    </td>
                                    <td>
                                        <template v-if="field.ui_type === 'switch'">
                                            <el-switch v-model="field.default" size="small" />
                                        </template>
                                        <template v-else-if="field.ui_type === 'number' || field.ui_type === 'slider'">
                                            <el-input-number v-model="field.default" size="small" controls-position="right" style="width: 100%;" />
                                        </template>
                                        <template v-else>
                                            <el-input v-model="field.default_str" placeholder="默认值/逗号分隔" size="small" @change="val => parseDefaultValue(field, val)" />
                                        </template>
                                    </td>
                                    <td>
                                        <el-select v-model="field.provider" placeholder="静态选项" size="small" clearable>
                                            <el-option label="静态 Options" value="" />
                                            <el-option label="🪟 当前打开窗口列表" value="sys.window_list" />
                                            <el-option label="🖥️ 显示器分辨率" value="sys.monitors" />
                                            <el-option label="🔌 硬件串口端口" value="sys.com_ports" />
                                        </el-select>
                                    </td>
                                    <td>
                                        <el-button type="danger" link size="small" @click="removeField(group, fIdx)">删除</el-button>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                        <div v-else class="empty-field-tip">
                            暂无控件项，点击右上角“➕ 添加控件项”以定义此分组表单
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <template #footer>
            <div class="dialog-footer">
                <el-button size="small" @click="dialogVisible = false">取消</el-button>
                <el-button type="success" plain size="small" @click="handleExportPackage">📦 仅打包密包 (.ebp)</el-button>
                <el-button type="warning" plain size="small" :loading="compileLoading" @click="handleCompileExecutable">
                    🔨 一键编译发布完整客户端 (.exe)
                </el-button>
                <el-button type="primary" size="small" @click="handleSaveSchema">确认并保存 Schema</el-button>
            </div>
        </template>
    </el-dialog>
</template>

<script setup>
    import { ref, computed, watch, reactive } from 'vue'
    import { useMainStore } from '@/stores'
    import { ElMessage, ElLoading } from 'element-plus'
    import { exporterApi } from '@/api/exporterApi'
    import client from '@/api/client'

    const props = defineProps({
        modelValue: { type: Boolean, default: false }
    })

    const emit = defineEmits(['update:modelValue', 'saved'])
    const store = useMainStore()

    const dialogVisible = computed({
        get: () => props.modelValue,
        set: (val) => emit('update:modelValue', val)
    })

    const compileLoading = ref(false)

    const localSchema = reactive({
        form_title: '弹弹堂挂机助手 - 客户配置面板',
        groups: []
    })

    const globalVarNames = computed(() => {
        return Object.keys(store.blueprint?.variables || {})
    })

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
            provider: ''
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

    const parseDefaultValue = (field, valStr) => {
        if (field.ui_type === 'checkbox_group') {
            field.default = valStr.split(',').map(s => s.trim()).filter(Boolean)
        } else {
            field.default = valStr
        }
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
                const res = await exporterApi.getFormSchema(store.currentProjectPath)
                if (res && res.groups && res.groups.length) {
                    localSchema.form_title = res.form_title || '客户运行配置面板'
                    localSchema.groups = res.groups
                } else {
                    autoGenerateFromVars()
                }
            } catch {
                autoGenerateFromVars()
            }
        }
    }, { immediate: false })

    const handleSaveSchema = async () => {
        try {
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
            ElMessage.info('打包编译资产密包中...')
            const res = await exporterApi.buildExportBundle(store.currentProjectPath, localSchema)
            if (res.success) {
                ElMessage.success(`🎉 资产密包导出成功！生成文件：${res.ebp_file}`)
            }
        } catch (err) {
            ElMessage.error('导出打包失败: ' + err.message)
        }
    }

    // ⚡ 工业级一键编译 .exe 客户端交付包 (带全屏 Loading 遮罩与 5 分钟超时放宽)
    const handleCompileExecutable = async () => {
        const loadingInstance = ElLoading.service({
            lock: true,
            text: '🔨 正在后台使用 PyInstaller 打包 Python 内核并构建 .exe 客户端，预计耗时 30 秒至 2 分钟，请耐心等待...',
            background: 'rgba(0, 0, 0, 0.7)'
        })

        try {
            compileLoading.value = true

            // 1. 保存 Schema
            await exporterApi.saveFormSchema(store.currentProjectPath, localSchema)
            // 2. 打包资产密包
            await exporterApi.buildExportBundle(store.currentProjectPath, localSchema)

            // 3. 异步触发后端 PyInstaller 编译，timeout 放宽至 300,000ms (5分钟)
            const res = await client.post('/api/exporter/compile-exe', {
                project_path: store.currentProjectPath
            }, {
                timeout: 300000
            })

            if (res.data?.success) {
                ElMessage.success(`🎉 客户端 .exe 编译打包成功！交付文件夹已生成于: ${res.data.output_dir}`)
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