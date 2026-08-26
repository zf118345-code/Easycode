<!-- frontend/src/components/ParamRenderer.vue -->
<template>
    <div v-if="isVisible" class="param-renderer" :class="{ 'is-stacked': isStackedType }">
        <!-- 统一标签渲染 -->
        <div v-if="label && !isCoordType" class="param-label">
            <span class="param-label-text">{{ displayLabel }}</span>
            <el-tooltip
                v-if="hasHelp"
                placement="top"
                effect="dark"
                :show-after="120"
                popper-class="param-help-popper">
                <template #content>
                    <div class="param-help-content"><pre>{{ helpText }}</pre></div>
                </template>
                <CircleHelp class="param-help-icon" />
            </el-tooltip>
        </div>

        <!-- 动态控件分发映射 -->
        <div class="param-control">
            <component
:is="activeControl"
                       :config="config"
                       :model-value="modelValue"
                       :label="displayLabel"
                       :context="context"
                       :image-version="imageVersion"
                       @update:model-value="handleUpdate"
                       @auto-change-type="handleAutoChangeType"
                       @capture-reset="handleCaptureReset"
                       @open-browser="mode => openBrowser(mode)"
                       @open-screenshot="mode => openScreenshot(mode)"
                       @window-selected="payload => emit('windowSelected', payload)"
                       @open-cond-dialog="handleOpenCondDialog" />
        </div>

        <!-- 挂载对话框与交互挂件 -->
        <el-dialog
v-model="browserVisible"
                   :title="fileBrowserMode === 'save' ? '选择保存目录并输入图片名称' : '选择模板图片'"
                   width="80%"
                   top="5vh"
                   append-to-body
                   :close-on-click-modal="false"
                   @close="handleBrowserClose">
            <FileBrowser
ref="fileBrowserRef"
                         :project-path="projectPath"
                         :mode="fileBrowserMode"
                         :initial-path="browserInitialPath"
                         @select="onFileSelected"
                         @close="browserVisible = false" />
        </el-dialog>

        <ConditionDialog
v-model:visible="condDialogVisible"
                         :show-jump-config="isBranchMode"
                         :schema-set="condSchemaSet"
                         :initial-data="editingCondData"
                         @open-browser="mode => openBrowser(mode || 'select')"
                         @open-screenshot="mode => openScreenshot(mode || 'template')"
                         @save="handleCondSave" />
    </div>
</template>

<script setup>
    import { ref, computed } from 'vue'
    import { ElMessage } from 'element-plus'
    import { CircleHelp } from 'lucide-vue-next'
    import { useIdeStore, useUiStore } from '@/stores'
    import { captureApi } from '@/api/captureApi'
    import { controlMap as baseControlMap } from './controls'
    import ControlFunctionSelect from './controls/ControlFunctionSelect.vue'
    import ControlCallInputBindings from './controls/ControlCallInputBindings.vue'
    import ControlCallOutputBindings from './controls/ControlCallOutputBindings.vue'
    import ControlCapabilitySelect from './controls/ControlCapabilitySelect.vue'
    import ControlCapabilityInputBindings from './controls/ControlCapabilityInputBindings.vue'
    import ControlCapabilityOutputBindings from './controls/ControlCapabilityOutputBindings.vue'
    import ControlGesturePathEditor from './controls/ControlGesturePathEditor.vue'
    import ControlFunctionOutcomeSelect from './controls/ControlFunctionOutcomeSelect.vue'
    import ControlFunctionReturnBindings from './controls/ControlFunctionReturnBindings.vue'

    import FileBrowser from '@/components/FileBrowser.vue'
    import ConditionDialog from '@/components/conditions/ConditionDialog.vue'

    const props = defineProps({
        config: { type: Object, required: true },
        value: { type: [String, Number, Boolean, Array, Object], default: null },
        label: { type: String, default: '' },
        context: { type: Object, default: () => ({}) },
        nodeType: { type: String, default: '' },
        assetCategory: { type: String, default: '' }
    })

    const emit = defineEmits(['update', 'autoChangeType', 'captureReset', 'coordinateMeta', 'captureBundle', 'windowSelected'])
    const store = useIdeStore()
    const uiStore = useUiStore()
    const projectPath = computed(() => store.currentProjectPath)
    const controlMap = {
        ...baseControlMap,
        function_select: ControlFunctionSelect,
        function_input_bindings: ControlCallInputBindings,
        function_output_bindings: ControlCallOutputBindings,
        function_outcome_select: ControlFunctionOutcomeSelect,
        function_return_bindings: ControlFunctionReturnBindings,
        capability_select: ControlCapabilitySelect,
        capability_input_bindings: ControlCapabilityInputBindings,
        capability_output_bindings: ControlCapabilityOutputBindings,
        gesture_path: ControlGesturePathEditor
    }

    const activeControl = computed(() => {
        return controlMap[props.config.type] || controlMap.str
    })

    const modelValue = computed(() => props.value)
    const isCoordType = computed(() => props.config.type && props.config.type.startsWith('list_int'))

    const isStackedType = computed(() => {
        return [
            'margin4', 'size2', 'file',
            'condition_list_editor', 'branch_candidate_editor',
            'condition_list', 'candidates', 'list_dict', 'textarea',
            'function_input_bindings', 'function_output_bindings', 'function_return_bindings',
            'capability_input_bindings', 'capability_output_bindings',
            'gesture_path'
        ].includes(props.config.type)
    })

    const isVisible = computed(() => {
        // 隐藏参数（如 page_state 的 page_id 内部标识）：不渲染，数据仍保留在 params 中
        if (props.config.hidden) return false
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

    const displayLabel = computed(() => props.config.label || props.label || '')

    // ⚡ 统一帮助提示：schema 配置 help（string 或 string[]）时，标签旁渲染「?」图标悬浮显示语法说明
    const hasHelp = computed(() => {
        const h = props.config?.help
        return Array.isArray(h) ? h.length > 0 : !!h
    })
    const helpLines = computed(() => {
        const h = props.config?.help
        return Array.isArray(h) ? h : (h ? [h] : [])
    })
    const helpText = computed(() => helpLines.value.join('\n'))

    const handleUpdate = (val) => emit('update', val)
    const handleCaptureReset = () => emit('captureReset')
    const handleAutoChangeType = (varType) => emit('autoChangeType', varType)

    const fileBrowserRef = ref(null)
    const browserVisible = ref(false)
    const fileBrowserMode = ref('select')
    const browserInitialPath = ref('')
    const imageVersion = ref(Date.now())

    const condDialogVisible = ref(false)
    const isBranchMode = ref(false)
    const editingIdx = ref(-1)
    const editingCondData = ref(null)
    // 条件对话框 schema 集合：页面特征（image_exists/text_contains + 组合/取反）或通用判定条件
    const condSchemaSet = computed(() => (props.config?.pageFeatures ? 'page-feature' : 'condition'))

    // ⚡ 参数纯化：保障 mode 为纯字符串
    const openBrowser = (mode = 'select') => {
        if (!projectPath.value) return ElMessage.warning('请先打开项目')
        const targetMode = typeof mode === 'string' ? mode : 'select'
        fileBrowserMode.value = targetMode
        const isPageAsset = props.assetCategory === 'page' || !!props.config?.pageFeatures
        const isOcr = props.config?.label?.includes('OCR') || props.label?.includes('OCR')
        browserInitialPath.value = props.assetCategory || (isPageAsset ? 'page' : (isOcr ? 'ocr' : 'image'))

        browserVisible.value = true
    }

    const handleBrowserClose = () => {
        browserVisible.value = false
    }

    const openScreenshot = async (mode = 'template') => {
        if (!projectPath.value) return ElMessage.warning('请先打开项目')
        if (store.isRunning || store.isPaused) return ElMessage.warning('请先停止当前任务')
        const targetMode = typeof mode === 'string' ? mode : 'template'
        const requestId = `field_${globalThis.crypto.randomUUID().replaceAll('-', '')}`
        const isPageFeatures = targetMode === 'page-features'
        const selectionMode = targetMode === 'point'
            ? 'point'
            : (targetMode === 'region' ? 'region' : 'asset')
        const category = props.assetCategory || (isPageFeatures
            ? 'page'
            : (props.nodeType === 'ocr_recognition' || displayLabel.value.toUpperCase().includes('OCR') ? 'ocr' : 'image'))
        const maxRects = isPageFeatures ? 32 : 1

        uiStore.cancelFieldCapture()
        uiStore.setFieldCaptureHandler(requestId, async payload => {
            const referenceSize = payload.reference_size || [0, 0]
            const coordinateMeta = { referenceSize, coordinateSpace: 'workspace_px' }
            if (selectionMode === 'point') {
                emit('update', payload.point || [0, 0])
                emit('coordinateMeta', coordinateMeta)
                return { message: '坐标已回填' }
            }
            if (selectionMode === 'region') {
                emit('update', payload.rects?.[0] || [0, 0, 0, 0])
                emit('coordinateMeta', coordinateMeta)
                return { message: '范围已回填' }
            }

            const assetRefs = Array.isArray(payload.asset_refs) ? payload.asset_refs : []
            const rects = Array.isArray(payload.rects) ? payload.rects : []
            if (!assetRefs.length) throw new Error('资源已经保存，但没有返回可用的资源引用')
            if (isPageFeatures) {
                const current = Array.isArray(props.value) ? [...props.value] : []
                assetRefs.forEach((assetRef, index) => current.push({
                    condition_type: 'image_exists',
                    exist_mode: 'exists',
                    image_source: assetRef,
                    threshold: 85,
                    gray_scale: true,
                    gray_threshold: 127,
                    region_type: 'recorded',
                    region_value: rects[index] || [0, 0, 0, 0],
                    region_reference_size: referenceSize,
                    coordinate_space: 'workspace_px',
                    negate: false
                }))
                emit('update', current)
                return { message: `已录入 ${assetRefs.length} 个页面图像特征` }
            }
            emit('captureBundle', {
                assetRef: assetRefs[0],
                rect: rects[0] || [0, 0, 0, 0],
                referenceSize,
                coordinateSpace: 'workspace_px'
            })
            imageVersion.value = Date.now()
            return { message: '图片与录制范围已回填' }
        })

        try {
            await captureApi.trigger({
                field_capture: {
                    request_id: requestId,
                    selection_mode: selectionMode,
                    category,
                    max_rects: maxRects,
                    title: targetMode === 'point' ? '取点' : targetMode === 'region' ? '框选范围' : '录入图片'
                }
            })
        } catch (error) {
            uiStore.cancelFieldCapture(requestId)
            ElMessage.error(error?.message || '截图捕获启动失败')
        }
    }

    const onFileSelected = (relPath) => {
        if (fileBrowserMode.value === 'save') return
        const cleanPath = relPath.replace(/\.png$/i, '')
        emit('update', cleanPath)
        imageVersion.value = Date.now()
        browserVisible.value = false
    }

    const handleOpenCondDialog = ({ idx, data, isBranch }) => {
        isBranchMode.value = isBranch
        editingIdx.value = idx
        editingCondData.value = data
        condDialogVisible.value = true
    }

    const handleCondSave = ({ condition }) => {
        const currentList = Array.isArray(props.value) ? [...props.value] : []
        const previous = editingIdx.value > -1 ? currentList[editingIdx.value] : null
        const candidateId = previous?.candidate_id || `cand_${globalThis.crypto.randomUUID().replaceAll('-', '')}`
        const payload = isBranchMode.value ? { candidate_id: candidateId, condition } : condition

        if (editingIdx.value > -1) {
            currentList[editingIdx.value] = payload
        } else {
            currentList.push(payload)
        }
        emit('update', currentList)
    }
</script>

<style scoped>
    .param-renderer {
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        align-items: start;
        gap: 6px;
        margin-bottom: 13px;
    }

        .param-renderer.is-stacked {
            grid-template-columns: minmax(0, 1fr);
        }

            .param-renderer.is-stacked .param-label {
                width: 100%;
                margin-bottom: 2px;
            }

            .param-renderer.is-stacked .param-control {
                justify-content: flex-start;
                width: 100%;
            }

    .param-label {
        font-size: 11px;
        line-height: 16px;
        color: var(--el-text-color-secondary);
        font-weight: 500;
        white-space: nowrap;
        flex-shrink: 0;
        min-width: 0;
        text-align: left;
        display: flex;
        align-items: center;
        gap: 5px;
    }

    .param-control {
        display: flex;
        justify-content: stretch;
        align-items: center;
        width: 100%;
    }

    .param-control :deep(> *) { width: 100%; }

    @container inspector (min-width: 520px) {
        .param-renderer:not(.is-stacked) {
            grid-template-columns: minmax(112px, .42fr) minmax(0, 1fr);
            align-items: center;
            column-gap: 12px;
        }
        .param-renderer:not(.is-stacked) .param-label { color: var(--el-text-color-regular); }
    }

    .param-help-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid var(--el-border-color);
        color: var(--el-text-color-secondary);
        font-size: 10px;
        line-height: 1;
        cursor: help;
        flex-shrink: 0;
        user-select: none;
        transition: color 0.15s, border-color 0.15s;
    }

    .param-help-icon:hover {
        color: var(--el-color-primary);
        border-color: var(--el-color-primary);
    }
</style>

<!-- ⚡ 帮助悬浮层内容渲染在 body 下的 popper 中，scoped 不生效，需全局样式 -->
<style>
    .param-help-popper .param-help-content pre {
        margin: 0;
        font-family: inherit;
        font-size: 12px;
        line-height: 1.6;
        white-space: pre-wrap;
        word-break: break-word;
        max-width: 320px;
        text-align: left;
    }
</style>
