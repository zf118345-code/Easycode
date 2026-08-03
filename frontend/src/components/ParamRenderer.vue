<template>
    <div v-if="isVisible" class="param-renderer">
        <!-- 标签 -->
        <div v-if="label" class="param-label">{{ label }}</div>

        <!-- 控件 -->
        <div class="param-control">
            <!-- str -->
            <template v-if="config.type === 'str'">
                <el-input v-model="localValue" :placeholder="config.label || ''" @change="emitChange('str')" />
            </template>

            <!-- window_select -->
            <template v-else-if="config.type === 'window_select'">
                <el-select v-model="localValue"
                           filterable
                           allow-create
                           default-first-option
                           placeholder="下拉选择或手动输入窗口标题"
                           style="width: 100%;"
                           @focus="fetchWindows"
                           @change="emitChange('window_select')">
                    <el-option v-for="w in windowList"
                               :key="w.hwnd"
                               :label="w.title"
                               :value="w.title" />
                </el-select>
                <div class="field-tip">💡 提示：已被最小化的窗口不会列出，请先还原窗口。</div>
            </template>

            <!-- int -->
            <template v-else-if="config.type === 'int'">
                <el-input-number v-model="localValue"
                                 :min="config.min !== undefined ? config.min : 0"
                                 :max="config.max !== undefined ? config.max : Infinity"
                                 :step="config.step || 1"
                                 controls-position="right"
                                 @change="emitChange('int')" />
            </template>

            <!-- float -->
            <template v-else-if="config.type === 'float'">
                <el-input-number v-model="localValue"
                                 :min="config.min !== undefined ? config.min : 0"
                                 :max="config.max !== undefined ? config.max : Infinity"
                                 :step="config.step || 0.1"
                                 :precision="2"
                                 controls-position="right"
                                 @change="emitChange('float')" />
            </template>

            <!-- bool -->
            <template v-else-if="config.type === 'bool'">
                <el-switch v-model="localValue" @change="emitChange('bool')" />
            </template>

            <!-- select -->
            <template v-else-if="config.type === 'select'">
                <el-select v-model="localValue" :placeholder="config.label || '请选择'" @change="emitChange('select')">
                    <el-option v-for="opt in resolvedOptions"
                               :key="opt.value"
                               :label="opt.label"
                               :value="opt.value" />
                </el-select>
            </template>

            <!-- file (模板图片浏览/录入) -->
            <template v-else-if="config.type === 'file'">
                <div class="file-selector">
                    <el-input :model-value="localValue" placeholder="请选择模板图片" readonly @click="openFileBrowser('select')">
                        <template #append>
                            <el-button @click="openFileBrowser('select')">📂 浏览</el-button>
                        </template>
                    </el-input>
                    <el-button type="success" size="small" @click="openScreenshot('template')">📷 录入</el-button>
                </div>
            </template>

            <!-- list_int2 / list_int2_picker -->
            <template v-else-if="config.type === 'list_int2' || config.type === 'list_int2_picker'">
                <div class="list-int2">
                    <div class="coord-item">
                        <span class="coord-label">X</span>
                        <el-input-number v-model="localValue[0]" :min="0" controls-position="right" size="small" @change="emitChange('list_int2')" />
                    </div>
                    <div class="coord-item">
                        <span class="coord-label">Y</span>
                        <el-input-number v-model="localValue[1]" :min="0" controls-position="right" size="small" @change="emitChange('list_int2')" />
                    </div>
                    <el-button v-if="config.type === 'list_int2_picker'" type="primary" size="small" @click="openScreenshot('point')">📍 取点</el-button>
                </div>
            </template>

            <!-- list_int4 / list_int4_picker -->
            <template v-else-if="config.type === 'list_int4' || config.type === 'list_int4_picker'">
                <div class="list-int4">
                    <div class="coord-item">
                        <span class="coord-label">X</span>
                        <el-input-number v-model="localValue[0]" :min="0" controls-position="right" size="small" @change="emitChange('list_int4')" />
                    </div>
                    <div class="coord-item">
                        <span class="coord-label">Y</span>
                        <el-input-number v-model="localValue[1]" :min="0" controls-position="right" size="small" @change="emitChange('list_int4')" />
                    </div>
                    <div class="coord-item">
                        <span class="coord-label">W</span>
                        <el-input-number v-model="localValue[2]" :min="0" controls-position="right" size="small" @change="emitChange('list_int4')" />
                    </div>
                    <div class="coord-item">
                        <span class="coord-label">H</span>
                        <el-input-number v-model="localValue[3]" :min="0" controls-position="right" size="small" @change="emitChange('list_int4')" />
                    </div>
                    <el-button v-if="config.type === 'list_int4_picker'" type="warning" size="small" @click="openScreenshot('region')">📐 框选</el-button>
                </div>
            </template>

            <!-- dict -->
            <template v-else-if="config.type === 'dict'">
                <div class="dict-container">
                    <ParamRenderer v-for="(subConfig, subKey) in config.sub"
                                   :key="subKey"
                                   :config="subConfig"
                                   :value="localValue ? localValue[subKey] : undefined"
                                   :label="subConfig.label || subKey"
                                   :context="localValue"
                                   @update="(val) => handleSubUpdate(subKey, val)" />
                </div>
            </template>

            <!-- 1. 逻辑判断节点的条件列表编辑器 -->
            <template v-else-if="config.type === 'condition_list_editor'">
                <div class="condition-list-wrapper">
                    <div v-for="(cond, idx) in (localValue || [])" :key="idx" class="cond-card">
                        <span class="cond-desc">
                            {{ cond.condition_type === 'image_exists' ? `🖼️ 图片: ${cond.params.image_source}` : `🔢 变量: ${cond.params.var_name} ${cond.params.operator} ${cond.params.target_value}` }}
                        </span>
                        <div class="card-btns">
                            <el-button link size="small" type="primary" @click="openCondDialog(idx, cond)">✏️ 编辑</el-button>
                            <el-button link size="small" type="danger" @click="removeCond(idx)">🗑️ 删除</el-button>
                        </div>
                    </div>
                    <el-button type="primary" size="small" style="margin-top: 6px;" @click="openCondDialog(-1, null)">➕ 添加判断条件</el-button>
                </div>
            </template>

            <!-- 2. 分支选择节点的带跳转分支列表编辑器 -->
            <template v-else-if="config.type === 'branch_candidate_editor'">
                <div class="condition-list-wrapper">
                    <div v-for="(cand, idx) in (localValue || [])" :key="idx" class="cond-card">
                        <div class="card-info">
                            <div>{{ cand.condition.condition_type === 'image_exists' ? `🖼️ 条件: 图片 [${cand.condition.params.image_source}]` : `🔢 条件: 变量 ${cand.condition.params.var_name} ${cand.condition.params.operator} ${cand.condition.params.target_value}` }}</div>
                            <div class="jump-tip">➔ 成功跳转: {{ formatJumpType(cand.on_success ? cand.on_success.jump_type : 'next') }}</div>
                        </div>
                        <div class="card-btns">
                            <el-button link size="small" type="primary" @click="openBranchDialog(idx, cand)">✏️ 编辑分支</el-button>
                            <el-button link size="small" type="danger" @click="removeCond(idx)">🗑️ 删除</el-button>
                        </div>
                    </div>
                    <el-button type="success" size="small" style="margin-top: 6px;" @click="openBranchDialog(-1, null)">➕ 添加分流条件分支</el-button>
                </div>
            </template>
        </div>

        <!-- ⭐ 层级 1050 比截图蒙层(1000)高一级 -->
        <el-dialog v-model="browserVisible"
                   :title="fileBrowserMode === 'save' ? '选择保存目录并输入图片名称' : '选择模板图片'"
                   width="80%"
                   top="5vh"
                   append-to-body
                   :z-index="1050"
                   :close-on-click-modal="false"
                   @close="handleBrowserClose">
            <FileBrowser ref="fileBrowserRef"
                         :project-path="projectPath"
                         :mode="fileBrowserMode"
                         @select="onFileSelected"
                         @save="onFileSave"
                         @close="browserVisible = false" />
        </el-dialog>

        <!-- 截图蒙层工具 -->
        <ScreenshotTool ref="screenshotTool"
                        @template-crop-selected="onTemplateCropSelected"
                        @point-selected="onPointSelected"
                        @region-selected="onRegionSelected" />

        <!-- 通用条件配置弹窗 -->
        <ConditionDialog v-model:visible="condDialogVisible"
                         :show-jump-config="isBranchMode"
                         :initial-data="editingCondData"
                         @save="handleCondSave" />
    </div>
</template>

<script>
    import { ref, watch, computed, toRaw } from 'vue'
    import { ElMessage } from 'element-plus'
    import axios from 'axios'
    import { useMainStore } from '@/stores'
    import { logger } from '@/utils/logger'
    import ScreenshotTool from '@/components/ScreenshotTool.vue'
    import FileBrowser from '@/components/FileBrowser.vue'
    import ConditionDialog from '@/components/ConditionDialog.vue'

    function safeDeepClone(obj) {
        if (obj === null || typeof obj !== 'object') return obj
        try {
            return JSON.parse(JSON.stringify(toRaw(obj)))
        } catch (e) {
            return { ...obj }
        }
    }

    export default {
        name: 'ParamRenderer',
        components: { ScreenshotTool, FileBrowser, ConditionDialog },
        props: {
            config: { type: Object, required: true },
            value: { required: false },
            label: { type: String, default: '' },
            context: { type: Object, default: () => ({}) }
        },
        emits: ['update'],
        setup(props, { emit }) {
            const store = useMainStore()
            const projectPath = computed(() => store.currentProjectPath)

            const screenshotTool = ref(null)
            const fileBrowserRef = ref(null)
            const browserVisible = ref(false)
            const fileBrowserMode = ref('select')
            const windowList = ref([])

            const pendingCropRect = ref(null)

            // 条件弹窗相关状态
            const condDialogVisible = ref(false)
            const isBranchMode = ref(false)
            const editingIdx = ref(-1)
            const editingCondData = ref(null)

            const isVisible = computed(() => {
                const rule = props.config.visible_if
                if (!rule) return true
                const { field, operator, value } = rule
                const targetValue = props.context?.[field]
                switch (operator) {
                    case 'eq': return targetValue === value
                    case 'ne': return targetValue !== value
                    case 'in': return Array.isArray(value) && value.includes(targetValue)
                    default: return true
                }
            })

            const localValue = ref(safeDeepClone(props.value))
            let isInternalUpdate = false

            const resolvedOptions = computed(() => {
                const options = props.config.options
                if (typeof options === 'function') {
                    try {
                        const result = options(props.context, localValue.value)
                        return Array.isArray(result) ? result.map(opt => typeof opt === 'string' ? { value: opt, label: opt } : opt) : []
                    } catch (e) {
                        return []
                    }
                }
                if (Array.isArray(options)) {
                    return options.map(opt => typeof opt === 'string' ? { value: opt, label: opt } : opt)
                }
                return []
            })

            const fetchWindows = async () => {
                try {
                    const res = await axios.get('/api/windows')
                    windowList.value = res.data.windows || []
                } catch (err) {
                    logger.error('ParamRenderer', '获取窗口列表失败:', err)
                }
            }

            watch(
                () => props.value,
                (newVal) => {
                    isInternalUpdate = true
                    localValue.value = safeDeepClone(newVal)
                    setTimeout(() => { isInternalUpdate = false }, 0)
                },
                { immediate: true, deep: true }
            )

            const emitChange = (triggerType = 'component') => {
                if (isInternalUpdate) return
                logger.debug('ParamRenderer', `控件 [${triggerType}:${props.label}] 发射 update:`, localValue.value)
                emit('update', localValue.value)
            }

            const handleSubUpdate = (subKey, val) => {
                if (!localValue.value || typeof localValue.value !== 'object') {
                    localValue.value = {}
                }
                localValue.value[subKey] = val
                emitChange('sub-dict')
            }

            const openFileBrowser = (mode = 'select') => {
                if (!projectPath.value) return ElMessage.warning('请先打开项目')
                fileBrowserMode.value = mode
                browserVisible.value = true

                if (screenshotTool.value) {
                    screenshotTool.value.setPauseState(true)
                }
            }

            const handleBrowserClose = () => {
                browserVisible.value = false
                if (screenshotTool.value) {
                    screenshotTool.value.setPauseState(false)
                }
            }

            const onFileSelected = (relPath) => {
                if (fileBrowserMode.value === 'save') return
                const cleanPath = relPath.replace(/\.png$/i, '')
                localValue.value = cleanPath
                emitChange('file-select')
                browserVisible.value = false
            }

            const onTemplateCropSelected = (cropRect) => {
                pendingCropRect.value = cropRect
                openFileBrowser('save')
            }

            const onFileSave = async ({ relativePath, fileName }) => {
                if (!pendingCropRect.value) {
                    return ElMessage.error('缺少截图框选数据')
                }
                try {
                    const cleanFileName = fileName.trim().replace(/\.png$/i, '')
                    const cleanRelPath = relativePath ? relativePath.replace(/\.png$/i, '') : ''
                    const fullTemplateName = cleanRelPath ? `${cleanRelPath}/${cleanFileName}` : cleanFileName

                    await axios.post('/api/screenshot/crop', {
                        project_path: projectPath.value,
                        template_name: fullTemplateName,
                        crop_rect: pendingCropRect.value
                    })

                    localValue.value = fullTemplateName
                    emitChange('screenshot-saved')
                    ElMessage.success(`模板图片 [${fullTemplateName}] 保存成功`)

                    browserVisible.value = false
                    if (screenshotTool.value) {
                        screenshotTool.value.close()
                    }
                } catch (err) {
                    logger.error('ParamRenderer', '保存模板图片失败:', err)
                    ElMessage.error('保存失败: ' + (err.response?.data?.detail || err.message))
                }
            }

            const openScreenshot = (mode = 'template') => {
                if (screenshotTool.value) {
                    screenshotTool.value.open(mode)
                } else {
                    logger.error('ParamRenderer', 'screenshotTool 实例未绑定成功')
                }
            }

            const onPointSelected = (pointArr) => {
                localValue.value = pointArr
                emitChange('point-picker')
            }

            const onRegionSelected = (regionArr) => {
                localValue.value = regionArr
                emitChange('region-picker')
            }

            // ====== ⭐ 修复方法绑定：条件编辑弹窗事件函数 ======
            const openCondDialog = (idx, cond) => {
                isBranchMode.value = false
                editingIdx.value = idx
                editingCondData.value = cond
                condDialogVisible.value = true
            }

            const openBranchDialog = (idx, cand) => {
                isBranchMode.value = true
                editingIdx.value = idx
                editingCondData.value = cand
                condDialogVisible.value = true
            }

            const removeCond = (idx) => {
                if (!Array.isArray(localValue.value)) return
                localValue.value.splice(idx, 1)
                emitChange('remove-cond')
            }

            const handleCondSave = ({ condition, on_success }) => {
                if (!Array.isArray(localValue.value)) localValue.value = []

                const payload = isBranchMode.value ? { condition, on_success } : condition

                if (editingIdx.value > -1) {
                    localValue.value[editingIdx.value] = payload
                } else {
                    localValue.value.push(payload)
                }
                emitChange('save-cond')
            }

            // ⭐ 格式化英文跳转类型为中文提示
            const formatJumpType = (type) => {
                const map = {
                    'next': '下一个节点',
                    'node': '跳转节点',
                    'task': '跳转任务',
                    'end': '结束流程'
                }
                return map[type] || type
            }

            return {
                localValue,
                screenshotTool,
                fileBrowserRef,
                browserVisible,
                fileBrowserMode,
                windowList,
                projectPath,
                isVisible,
                resolvedOptions,
                fetchWindows,
                openFileBrowser,
                handleBrowserClose,
                onFileSelected,
                onFileSave,
                openScreenshot,
                onTemplateCropSelected,
                onPointSelected,
                onRegionSelected,
                emitChange,
                handleSubUpdate,
                // 弹窗绑定与格式化
                condDialogVisible,
                isBranchMode,
                editingCondData,
                openCondDialog,
                openBranchDialog,
                removeCond,
                handleCondSave,
                formatJumpType
            }
        }
    }
</script>

<style scoped>
    .param-renderer {
        margin-bottom: 8px;
    }

    .param-label {
        font-size: 13px;
        color: var(--el-text-color-primary);
        font-weight: 500;
        margin-bottom: 4px;
    }

    .param-control {
        width: 100%;
    }

    .file-selector {
        display: flex;
        gap: 6px;
        align-items: center;
    }

        .file-selector .el-input {
            flex: 1;
        }

    .list-int2, .list-int4 {
        display: flex;
        gap: 8px;
        align-items: center;
        flex-wrap: wrap;
    }

    .coord-item {
        display: flex;
        align-items: center;
        gap: 4px;
    }

    .coord-label {
        font-size: 12px;
        color: var(--el-text-color-secondary);
        font-weight: 500;
        min-width: 14px;
    }

    .coord-item .el-input-number {
        width: 70px;
    }

    .dict-container {
        padding-left: 12px;
        border-left: 2px solid var(--el-border-color-light);
        margin-top: 4px;
    }

    .field-tip {
        font-size: 11px;
        color: var(--el-text-color-secondary);
        margin-top: 4px;
        line-height: 1.2;
    }

    .condition-list-wrapper {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .cond-card {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        background: var(--el-fill-color-blank);
        border: 1px solid var(--el-border-color-light);
        border-radius: 6px;
        font-size: 12px;
        color: var(--el-text-color-regular);
    }

    .card-info {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .jump-tip {
        color: var(--el-color-primary);
        font-size: 11px;
    }

    .card-btns {
        display: flex;
        gap: 4px;
    }
</style>