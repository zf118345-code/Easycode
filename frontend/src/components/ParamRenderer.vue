<template>
    <div v-if="isVisible" class="param-renderer" :class="{ 'is-inline': inline, 'is-file-type': config.type === 'file', 'is-coord-type': config.type === 'list_int4' || config.type === 'list_int4_picker' }">
        <!-- 标签：如果是坐标类型（list_int4），让标题和“框选区域”按钮在同一行展示 -->
        <div v-if="label && config.type !== 'file'" class="param-label" :class="{ 'coord-label-row': config.type === 'list_int4' || config.type === 'list_int4_picker' }">
            <span>{{ displayLabel }}</span>
            <!-- 框选按钮：统一深色风格与图标 -->
            <el-button v-if="(config.type === 'list_int4' || config.type === 'list_int4_picker') && config.type.includes('picker')"
                       class="inline-region-btn"
                       @click="openScreenshot('region')">
                <SquareDashedMousePointer class="custom-btn-icon" />
                <span>框选区域</span>
            </el-button>
        </div>

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

            <!-- int (针对相似度、超时时长等特殊字段进行左侧居左、右侧带后缀的定制渲染) -->
            <template v-else-if="config.type === 'int'">
                <el-input-number v-if="!isThresholdField && !isTimeoutField"
                                 v-model="localValue"
                                 :min="config.min !== undefined ? config.min : 0"
                                 :max="config.max !== undefined ? config.max : Infinity"
                                 :step="config.step || 1"
                                 :controls="false"
                                 @change="emitChange('int')" />

                <!-- 匹配相似度输入框 (数值居左，右侧 0-99%) -->
                <el-input v-else-if="isThresholdField"
                          v-model.number="localValue"
                          size="default"
                          class="threshold-input-with-percent"
                          @change="emitChange('int')">
                    <template #suffix>
                        <span class="input-percent-suffix">0-99%</span>
                    </template>
                </el-input>

                <!-- 匹配超时时长输入框 (数值居左，右侧 毫秒) -->
                <el-input v-else-if="isTimeoutField"
                          v-model.number="localValue"
                          size="default"
                          class="threshold-input-with-percent"
                          @change="emitChange('int')">
                    <template #suffix>
                        <span class="input-percent-suffix">毫秒</span>
                    </template>
                </el-input>
            </template>

            <!-- float -->
            <template v-else-if="config.type === 'float'">
                <el-input-number v-model="localValue"
                                 :min="config.min !== undefined ? config.min : 0"
                                 :max="config.max !== undefined ? config.max : Infinity"
                                 :step="config.step || 0.1"
                                 :precision="2"
                                 :controls="false"
                                 @change="emitChange('float')" />
            </template>

            <!-- bool -->
            <template v-else-if="config.type === 'bool'">
                <el-switch v-model="localValue" class="custom-fixed-switch" @change="emitChange('bool')" />
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

            <!-- file (应用 4:3 比例 + 高斯模糊氛围背景) -->
            <template v-else-if="config.type === 'file'">
                <div class="file-hover-card aspect-ratio-box" :title="localValue ? `当前图片: ${localValue}` : '未选择图片'" :style="localValue ? { '--bg-image-url': `url(${resolveTemplateUrl(localValue)})` } : {}">
                    <div class="card-preview-area">
                        <template v-if="localValue">
                            <img :src="resolveTemplateUrl(localValue)"
                                 class="preview-image-full"
                                 alt="模板预览"
                                 @error="(e) => { e.target.style.display = 'none'; }" />
                            <div class="preview-name-badge">{{ localValue }}</div>
                        </template>
                        <div v-else class="preview-empty-text">
                            <Image style="width: 14px; height: 14px; margin-bottom: -3px; margin-right: 2px; opacity: 0.6;" />
                            <span>暂无模板图片（悬停可选择或录入）</span>
                        </div>
                    </div>

                    <div class="hover-action-overlay">
                        <div class="overlay-half left-half" @click.stop="openFileBrowser('select')">
                            <span class="action-tip">📁 选择图片</span>
                        </div>
                        <div class="overlay-divider"></div>
                        <div class="overlay-half right-half" @click.stop="openScreenshot('template')">
                            <span class="action-tip">📷 录入图片</span>
                        </div>
                    </div>
                </div>
            </template>

            <!-- list_int2 / list_int2_picker -->
            <template v-else-if="config.type === 'list_int2' || config.type === 'list_int2_picker'">
                <div class="list-int2">
                    <div class="coord-item">
                        <span class="coord-label">X</span>
                        <el-input-number v-model="localValue[0]" :min="0" :controls="false" size="small" @change="emitChange('list_int2')" />
                    </div>
                    <div class="coord-item">
                        <span class="coord-label">Y</span>
                        <el-input-number v-model="localValue[1]" :min="0" :controls="false" size="small" @change="emitChange('list_int2')" />
                    </div>
                    <el-button v-if="config.type === 'list_int2_picker'"
                               class="inline-region-btn"
                               @click="openScreenshot('point')">
                        <MapPinned class="custom-btn-icon" />
                        <span>取点</span>
                    </el-button>
                </div>
            </template>

            <!-- list_int4 / list_int4_picker -->
            <template v-else-if="config.type === 'list_int4' || config.type === 'list_int4_picker'">
                <div class="list-int4-single-row">
                    <div class="coord-item">
                        <span class="coord-label">X</span>
                        <el-input-number v-model="localValue[0]" :min="0" :controls="false" size="small" @change="emitChange('list_int4')" />
                    </div>
                    <div class="coord-item">
                        <span class="coord-label">Y</span>
                        <el-input-number v-model="localValue[1]" :min="0" :controls="false" size="small" @change="emitChange('list_int4')" />
                    </div>
                    <div class="coord-item">
                        <span class="coord-label">W</span>
                        <el-input-number v-model="localValue[2]" :min="0" :controls="false" size="small" @change="emitChange('list_int4')" />
                    </div>
                    <div class="coord-item">
                        <span class="coord-label">H</span>
                        <el-input-number v-model="localValue[3]" :min="0" :controls="false" size="small" @change="emitChange('list_int4')" />
                    </div>
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

            <!-- condition_list_editor -->
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

            <!-- branch_candidate_editor -->
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

        <ScreenshotTool ref="screenshotTool"
                        @template-crop-selected="onTemplateCropSelected"
                        @point-selected="onPointSelected"
                        @region-selected="onRegionSelected" />

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
    import { SquareDashedMousePointer, Image, MapPinned } from 'lucide-vue-next'

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
        components: { ScreenshotTool, FileBrowser, ConditionDialog, SquareDashedMousePointer, Image, MapPinned },
        props: {
            config: { type: Object, required: true },
            value: { required: false },
            label: { type: String, default: '' },
            context: { type: Object, default: () => ({}) },
            inline: { type: Boolean, default: false }
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
            const imageVersion = ref(Date.now())

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

            const isThresholdField = computed(() => {
                return props.label === 'threshold' || props.label.includes('阈值') || props.label.includes('相似度')
            })

            const isTimeoutField = computed(() => {
                return props.label === 'timeout' || props.label.includes('超时')
            })

            const isGrayScaleField = computed(() => {
                return props.label === 'gray_scale' || props.label.includes('灰度') || props.label.includes('二值化')
            })

            const displayLabel = computed(() => {
                if (!props.label) return ''
                if (isThresholdField.value) return '匹配相似度'
                if (isTimeoutField.value) return '匹配超时时长'
                if (isGrayScaleField.value) return '去除背景干扰（灰度处理）'
                return props.label
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

            const resolveTemplateUrl = (imgPath) => {
                if (!imgPath) return ''
                if (imgPath.startsWith('http') || imgPath.startsWith('data:')) return imgPath
                let cleanName = imgPath.replace(/\\/g, '/')
                if (!/\.(png|jpg|jpeg)$/i.test(cleanName)) {
                    cleanName += '.png'
                }
                return `/api/image/thumb?project_path=${encodeURIComponent(projectPath.value || '')}&name=${encodeURIComponent(cleanName)}&t=${imageVersion.value}`
            }

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
                    imageVersion.value = Date.now()
                    setTimeout(() => { isInternalUpdate = false }, 0)
                },
                { immediate: true, deep: true }
            )

            const emitChange = (triggerType = 'component') => {
                if (isInternalUpdate) {
                    return
                }
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
                imageVersion.value = Date.now()
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
                    imageVersion.value = Date.now()
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
                isThresholdField,
                isTimeoutField,
                isGrayScaleField,
                displayLabel,
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
                condDialogVisible,
                isBranchMode,
                editingCondData,
                openCondDialog,
                openBranchDialog,
                removeCond,
                handleCondSave,
                formatJumpType,
                resolveTemplateUrl
            }
        }
    }
</script>

<style scoped>
    .param-renderer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 12px;
    }

    .param-label {
        font-size: 13px;
        color: var(--el-text-color-primary);
        font-weight: 500;
        white-space: nowrap;
        flex-shrink: 0;
        width: 120px;
        text-align: left;
    }

    .param-control {
        flex: 1;
        display: flex;
        justify-content: flex-end;
        align-items: center;
    }

        .param-control .el-input,
        .param-control .el-select,
        .param-control .el-input-number {
            width: 100% !important;
        }

    /* 修复开关（el-switch）在关闭状态下的底色改成与下方表单输入框一致的深色 */
    :deep(.custom-fixed-switch .el-switch__core) {
        background-color: var(--el-fill-color-blank, #181926) !important;
        border-color: var(--el-border-color-light, #313352) !important;
    }

    :deep(.custom-fixed-switch.is-checked .el-switch__core) {
        background-color: var(--el-color-primary, #4ed19c) !important;
        border-color: var(--el-color-primary, #4ed19c) !important;
    }

    /* 专门针对带有范围或单位提示的数值输入框样式（数值居左） */
    .threshold-input-with-percent :deep(.el-input__wrapper) {
        background-color: var(--el-fill-color-blank) !important;
        box-shadow: 0 0 0 1px var(--el-border-color-light) inset !important;
        padding-left: 10px !important;
        padding-right: 8px !important;
    }

    .threshold-input-with-percent :deep(.el-input__inner) {
        text-align: left !important;
        font-size: 12px;
        color: var(--el-text-color-primary);
    }

    .input-percent-suffix {
        font-size: 11px;
        font-weight: 600;
        color: var(--el-text-color-secondary);
        margin-left: 2px;
        white-space: nowrap;
    }

    .param-renderer.is-file-type {
        flex-direction: column;
        align-items: stretch;
    }

        .param-renderer.is-file-type .param-control {
            width: 100%;
            display: block;
        }

    .param-renderer.is-coord-type {
        flex-direction: column;
        align-items: stretch;
    }

        .param-renderer.is-coord-type .param-label {
            width: 100%;
            margin-bottom: 6px;
        }

    .coord-label-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .inline-region-btn {
        background-color: var(--el-fill-color-blank, #26283d) !important;
        border: 1px solid var(--el-border-color-light, #313352) !important;
        color: var(--el-text-color-regular, #c0c4cc) !important;
        padding: 4px 12px !important;
        height: 32px !important;
        font-size: 12px !important;
        font-weight: 500 !important;
        border-radius: 4px !important;
        display: flex;
        align-items: center;
        gap: 6px;
        transition: all 0.2s ease;
    }

        .inline-region-btn:hover {
            background-color: var(--el-fill-color, #2b2d3d) !important;
            border-color: var(--el-color-primary, #4ed19c) !important;
            color: var(--el-color-primary, #4ed19c) !important;
        }

    .custom-btn-icon {
        width: 14px !important;
        height: 14px !important;
        color: currentColor !important;
        display: inline-block !important;
        visibility: visible !important;
        flex-shrink: 0;
        vertical-align: middle;
    }

    .param-renderer.is-coord-type .param-control {
        width: 100%;
        display: block;
    }

    .list-int2 {
        display: flex;
        gap: 6px;
        align-items: center;
        width: 100%;
    }

        .list-int2 .coord-item {
            flex: 1;
            display: flex;
            align-items: center;
            background: var(--el-fill-color-blank);
            border: 1px solid var(--el-border-color-light);
            border-radius: 4px;
            padding: 2px 4px;
            box-sizing: border-box;
        }

    .list-int4-single-row {
        display: flex;
        gap: 6px;
        width: 100%;
    }

        .list-int4-single-row .coord-item {
            flex: 1;
            display: flex;
            align-items: center;
            background: var(--el-fill-color-blank);
            border: 1px solid var(--el-border-color-light);
            border-radius: 4px;
            padding: 2px 4px;
            box-sizing: border-box;
        }

    /* ⭐ 模板图片卡片：应用 4:3 比例 + 高斯模糊背景填充 */
    .file-hover-card {
        position: relative;
        width: 100%;
        background: var(--el-fill-color-blank);
        border: 1px solid var(--el-border-color-light);
        border-radius: 6px;
        overflow: hidden;
        user-select: none;
    }

    .aspect-ratio-box {
        aspect-ratio: 4 / 3;
        box-sizing: border-box;
    }

    .file-hover-card::before {
        content: '';
        position: absolute;
        inset: -20px;
        background-image: var(--bg-image-url);
        background-size: cover;
        background-position: center;
        filter: blur(14px) brightness(0.5);
        z-index: 1;
    }

    .card-preview-area {
        position: relative;
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: transparent;
        z-index: 2;
    }

    .preview-image-full {
        width: 100%;
        height: 100%;
        object-fit: contain !important;
    }

    .preview-name-badge {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        background: rgba(25, 26, 38, 0.8);
        color: #fff;
        font-size: 10px;
        padding: 2px 6px;
        text-align: center;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        z-index: 3;
    }

    .preview-empty-text {
        font-size: 11px;
        color: var(--el-text-color-placeholder);
        z-index: 2;
    }

    .hover-action-overlay {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(25, 26, 38, 0.8);
        backdrop-filter: blur(2px);
        display: flex;
        align-items: center;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.2s ease;
        z-index: 4;
    }

    .file-hover-card:hover .hover-action-overlay {
        opacity: 1;
        pointer-events: auto;
    }

    .overlay-half {
        flex: 1;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        box-sizing: border-box;
        border: 2px dashed transparent;
        transition: all 0.2s;
    }

    .left-half:hover {
        border-color: var(--el-color-primary);
        background: rgba(64, 158, 255, 0.15);
    }

    .right-half:hover {
        border-color: #67C23A;
        background: rgba(103, 194, 58, 0.15);
    }

    .overlay-divider {
        width: 1px;
        height: 60%;
        background: rgba(255, 255, 255, 0.2);
    }

    .action-tip {
        font-size: 12px;
        font-weight: 600;
        color: #fff;
        text-shadow: 0 1px 3px rgba(0,0,0,0.5);
    }

    .coord-item {
        display: flex;
        align-items: center;
        gap: 2px;
    }

    .coord-label {
        font-size: 11px;
        color: var(--el-text-color-secondary);
        font-weight: 500;
    }

    .coord-item .el-input-number {
        width: 100% !important;
    }

    :deep(.el-input-number) {
        background-color: var(--el-fill-color-blank) !important;
        border: 1px solid var(--el-border-color-light) !important;
        border-radius: 4px !important;
        overflow: hidden !important;
    }

    :deep(.el-input-number__decrease),
    :deep(.el-input-number__increase) {
        display: none !important;
    }

    :deep(.el-input-number .el-input__wrapper) {
        background-color: transparent !important;
        box-shadow: none !important;
        padding-left: 2px !important;
        padding-right: 2px !important;
    }

    :deep(.el-input-number .el-input__inner) {
        text-align: center !important;
    }

    .dict-container {
        padding-left: 12px;
        border-left: 2px solid var(--el-border-color-light);
        margin-top: 4px;
        width: 100%;
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
        width: 100%;
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