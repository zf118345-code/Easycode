<!-- frontend/src/components/ParamRenderer.vue -->
<template>
    <div v-if="isVisible" class="param-renderer" :class="{ 'is-stacked': isStackedType }">
        <!-- 统一标签渲染 -->
        <div v-if="label && !isCoordType" class="param-label">
            <span>{{ displayLabel }}</span>
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
                       @open-browser="mode => openBrowser(mode)"
                       @open-screenshot="mode => openScreenshot(mode)"
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
                         @save="onFileSave"
                         @close="browserVisible = false" />
        </el-dialog>

        <ScreenshotTool
ref="screenshotToolRef"
                        @template-crop-selected="onTemplateCropSelected"
                        @point-selected="onPointSelected"
                        @region-selected="onRegionSelected" />

        <ConditionDialog
v-model:visible="condDialogVisible"
                         :show-jump-config="isBranchMode"
                         :initial-data="editingCondData"
                         @open-browser="mode => openBrowser(mode || 'select')"
                         @open-screenshot="mode => openScreenshot(mode || 'template')"
                         @save="handleCondSave" />
    </div>
</template>

<script setup>
    import { ref, computed } from 'vue'
    import { ElMessage } from 'element-plus'
    import { useMainStore } from '@/stores'
    import { workspaceApi } from '@/api/workspaceApi'
    import { controlMap } from './controls'

    import VariableInputControl from './controls/VariableInputControl.vue'
    import ScreenshotTool from '@/components/ScreenshotTool.vue'
    import FileBrowser from '@/components/FileBrowser.vue'
    import ConditionDialog from '@/components/conditions/ConditionDialog.vue'

    const props = defineProps({
        config: { type: Object, required: true },
        value: { required: false },
        label: { type: String, default: '' },
        context: { type: Object, default: () => ({}) }
    })

    const emit = defineEmits(['update', 'autoChangeType'])
    const store = useMainStore()
    const projectPath = computed(() => store.currentProjectPath)

    const activeControl = computed(() => {
        const type = props.config.type
        if (type === 'variable' || type === 'autocomplete') {
            return VariableInputControl
        }
        return controlMap[type] || controlMap.str
    })

    const modelValue = computed(() => props.value)
    const isCoordType = computed(() => props.config.type && props.config.type.startsWith('list_int'))

    const isStackedType = computed(() => {
        return [
            'margin4', 'size2', 'file',
            'condition_list_editor', 'branch_candidate_editor',
            'condition_list', 'candidates', 'list_dict', 'textarea'
        ].includes(props.config.type)
    })

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

    const displayLabel = computed(() => props.config.label || props.label || '')

    const handleUpdate = (val) => emit('update', val)
    const handleAutoChangeType = (varType) => emit('autoChangeType', varType)

    const fileBrowserRef = ref(null)
    const screenshotToolRef = ref(null)
    const browserVisible = ref(false)
    const fileBrowserMode = ref('select')
    const browserInitialPath = ref('')
    const pendingCropRect = ref(null)
    const imageVersion = ref(Date.now())

    const condDialogVisible = ref(false)
    const isBranchMode = ref(false)
    const editingIdx = ref(-1)
    const editingCondData = ref(null)

    // ⚡ 参数纯化：保障 mode 为纯字符串
    const openBrowser = (mode = 'select') => {
        if (!projectPath.value) return ElMessage.warning('请先打开项目')
        const targetMode = typeof mode === 'string' ? mode : 'select'
        fileBrowserMode.value = targetMode
        if (targetMode === 'select') pendingCropRect.value = null

        const isOcr = props.config?.label?.includes('OCR') || props.label?.includes('OCR')
        browserInitialPath.value = isOcr ? 'ocr' : ''

        browserVisible.value = true
        if (screenshotToolRef.value) screenshotToolRef.value.setPauseState(true)
    }

    const handleBrowserClose = () => {
        browserVisible.value = false
        if (screenshotToolRef.value) screenshotToolRef.value.setPauseState(false)
    }

    // ⚡ 参数纯化：确保 ScreenshotTool open 拿到干净的模式，并触发 useZIndex 动态压盖
    const openScreenshot = (mode = 'template') => {
        const targetMode = typeof mode === 'string' ? mode : 'template'
        if (screenshotToolRef.value) {
            screenshotToolRef.value.open(targetMode)
        }
    }

    const onFileSelected = (relPath) => {
        if (fileBrowserMode.value === 'save') return
        const cleanPath = relPath.replace(/\.png$/i, '')
        emit('update', cleanPath)
        imageVersion.value = Date.now()
        browserVisible.value = false
    }

    const onTemplateCropSelected = (cropRect) => {
        pendingCropRect.value = cropRect
        openBrowser('save')
    }

    const onFileSave = async ({ relativePath, fileName }) => {
        if (!pendingCropRect.value) return ElMessage.error('缺少截图框选数据')
        try {
            const cleanFileName = fileName.trim().replace(/\.png$/i, '')
            const cleanRelPath = relativePath ? relativePath.replace(/\.png$/i, '') : ''
            const fullTemplateName = cleanRelPath ? `${cleanRelPath}/${cleanFileName}` : cleanFileName

            await workspaceApi.cropScreenshot(projectPath.value, fullTemplateName, pendingCropRect.value)

            emit('update', fullTemplateName)
            imageVersion.value = Date.now()
            ElMessage.success(`模板图片 [${fullTemplateName}] 保存成功`)

            browserVisible.value = false
            pendingCropRect.value = null
            if (screenshotToolRef.value) screenshotToolRef.value.close()
        } catch (err) {
            ElMessage.error('保存失败: ' + err.message)
        }
    }

    const onPointSelected = (pointArr) => emit('update', pointArr)
    const onRegionSelected = (regionArr) => emit('update', regionArr)

    const handleOpenCondDialog = ({ idx, data, isBranch }) => {
        isBranchMode.value = isBranch
        editingIdx.value = idx
        editingCondData.value = data
        condDialogVisible.value = true
    }

    const handleCondSave = ({ condition, on_success }) => {
        const currentList = Array.isArray(props.value) ? [...props.value] : []
        const payload = isBranchMode.value ? { condition, on_success } : condition

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
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 12px;
    }

        .param-renderer.is-stacked {
            flex-direction: column;
            align-items: flex-start;
            gap: 6px;
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
        width: 100%;
    }
</style>