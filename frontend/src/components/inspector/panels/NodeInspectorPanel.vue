<!-- frontend/src/components/inspector/panels/NodeInspectorPanel.vue -->
<template>
    <div class="panel-layout-root">
        <!-- 1. 顶部固定标题 -->
        <div class="inspector-fixed-header">
            <div class="node-title-box">
                <div class="node-type-icon-badge" :title="nodeTypeLabel">
                    <component :is="getNodeIcon(node.node_type)" class="inspector-type-svg" />
                </div>
                <div class="node-heading-copy">
                    <el-input v-model="node.node_name" size="default" class="node-name-input" placeholder="节点名称" @change="handleSave" />
                </div>
            </div>
        </div>

        <!-- 2. 中间滚动参数区 -->
        <div class="inspector-scrollable-body">
            <div class="params-container">
                <!-- ⚡ OCR 专属: 顶部图片下方的实时识字高亮结果框 -->
                <div v-if="node.node_type === 'ocr_recognition'" class="ocr-live-result-card">
                    <div class="result-header">
                        <span><ScanText :size="14" /> 识别结果</span>
                        <el-button size="small" type="primary" link :disabled="!hasOcrTemplate" :loading="previewLoading" @click="fetchOcrText">
                            <RefreshCcw style="width: 12px; height: 12px; margin-right: 2px;" :class="{ 'is-spinning': previewLoading }" />
                            刷新识别
                        </el-button>
                    </div>
                    <div class="result-text-box" :class="{ 'is-empty': !previewText }">
                        {{ previewText || ocrPreviewHint }}
                    </div>
                </div>

                <!-- ⚡ 纯 Schema 自动分发表单：依次渲染节点参数 -->
                <template v-for="(config, paramName) in allParams" :key="paramName + (node ? node.node_id : '')">
                    <!-- 灰度阈值滑块定制优化 (支持实时二值化黑白预览与防抖测试) -->
                    <div v-if="paramName === 'gray_threshold' && node.params.gray_scale" class="param-item slider-box">
                        <div class="slider-header">
                            <span>二值化灰度阈值: <strong>{{ node.params.gray_threshold ?? 127 }}</strong></span>
                            <span class="slider-tip">(向左增强浅色，向右过滤背景)</span>
                        </div>
                        <el-slider
v-model="node.params.gray_threshold"
                                   :min="0"
                                   :max="255"
                                   :step="1"
                                   @change="val => handleParamUpdate('gray_threshold', val)" />
                    </div>

                    <!-- 基础通用参数渲染网关 -->
                    <div v-else class="param-item">
                        <ParamRenderer
:config="config"
                                       :value="node.params[paramName]"
                                       :label="config.label || paramName"
                                       :context="node.params"
                                       :node-type="node.node_type"
                                       :preview-revision="imageVersion"
                                       @update="val => handleParamUpdate(paramName, val)"
                                       @coordinate-meta="meta => handleCoordinateMeta(paramName, meta)"
                                       @capture-bundle="bundle => handleCaptureBundle(paramName, bundle)"
                                       @window-selected="handleWindowSelected"
                                       @auto-change-type="handleAutoChangeType"
                                       @capture-reset="handleCaptureReset(paramName)" />
                    </div>
                </template>
            </div>
        </div>

        <!-- 3. 底部固定延时/循环 -->
        <div class="inspector-fixed-footer">
            <span
                class="autosave-state"
                :class="`is-${projectStore.saveState}`"
                :title="autosaveTitle">
                <LoaderCircle v-if="projectStore.saveState === 'saving'" :size="12" class="is-spinning" />
                <CircleAlert v-else-if="projectStore.saveState === 'error'" :size="12" />
                <Check v-else :size="12" />
                {{ autosaveLabel }}
            </span>
            <div class="footer-inline-container">
                <div class="footer-setting-group">
                    <span class="footer-label">延迟</span>
                    <el-input v-model.number="node.delay_before" size="small" class="pure-compact-input" @change="handleSave" />
                    <span class="footer-unit">ms</span>
                </div>
            <div v-if="node.node_type !== 'call_function'" class="footer-setting-group">
                    <span class="footer-label">循环</span>
                    <el-input v-model.number="node.loop_count" size="small" class="pure-compact-input" @change="handleSave" />
                    <span class="footer-unit">次</span>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
    import { ref, computed, watch, onUnmounted } from 'vue'
    import { useIdeStore, useProjectStore } from '@/stores'
    import { visionApi } from '@/api/visionApi'
    import { workspaceApi } from '@/api/workspaceApi'
    import { ElMessage } from 'element-plus'
    import ParamRenderer from '@/components/ParamRenderer.vue'
    import {
        MousePointerClick, Clock, Image, ScanText, GitBranch,
        SearchCheck, Binary, ListOrdered, FileCode, RefreshCcw, ScanSearch, Check, LoaderCircle, CircleAlert
    } from 'lucide-vue-next'
    import { NODE_TYPE_CONFIG } from '@/utils/canvasShared'

    const props = defineProps({
        node: { type: Object, required: true }
    })
    const emit = defineEmits(['save'])
    const store = useIdeStore()
    const projectStore = useProjectStore()

    const previewLoading = ref(false)
    const previewText = ref('')
    const originalRecordedRegion = ref(null)
    const originalStopRecordedRegion = ref(null)
    const imageVersion = ref(Date.now())
    let isSyncingRecorded = false
    let ocrTimer = null
    let ocrRequestId = 0

    // 图标映射统一从 canvasShared.NODE_TYPE_CONFIG 获取
    const _iconComponentCache = {
        MousePointerClick, Clock, Image, ScanText, GitBranch,
        SearchCheck, Binary, ListOrdered, FileCode, ScanSearch
    }
    const getNodeIcon = (type) => {
        const config = NODE_TYPE_CONFIG[type]
        return (config && _iconComponentCache[config.icon]) || FileCode
    }

    const nodeTypeLabel = computed(() => store.paramsDefinitions[props.node?.node_type]?.label || props.node?.node_type)
    const allParams = computed(() => store.paramsDefinitions[props.node?.node_type]?.params || {})
    const hasOcrTemplate = computed(() => !!String(props.node?.params?.image_source || '').trim())
    const ocrPreviewHint = computed(() => (
        hasOcrTemplate.value ? '尚未识别到文字，可点击刷新' : '选择模板图片后可测试识别'
    ))
    const autosaveLabel = computed(() => ({
        saving: '正在保存…',
        error: '保存失败',
        saved: projectStore._lastSavedAt ? '已自动保存' : '等待编辑'
    }[projectStore.saveState] || '等待编辑'))
    const autosaveTitle = computed(() => projectStore._lastSaveError?.message || autosaveLabel.value)

    // ⚡ OCR 文本测试识别方法
    const fetchOcrText = async () => {
        if (!props.node || props.node.node_type !== 'ocr_recognition') return
        if (ocrTimer) {
            clearTimeout(ocrTimer)
            ocrTimer = null
        }
        if (!hasOcrTemplate.value) {
            ocrRequestId += 1
            previewLoading.value = false
            previewText.value = ''
            return
        }
        const requestId = ++ocrRequestId
        previewLoading.value = true
        try {
            const res = await visionApi.testOcr(
                store.currentProjectPath,
                props.node.params.region_value || [0, 0, 0, 0],
                props.node.params.gray_scale ?? true,
                props.node.params.gray_threshold ?? 127,
                props.node.params.image_source || '',
                props.node.params.region_reference_size || [0, 0]
            )
            if (requestId === ocrRequestId && res) {
                previewText.value = res.text || ''
            }
        } catch (err) {
            if (requestId === ocrRequestId) console.warn('OCR 测试失败', err)
        } finally {
            if (requestId === ocrRequestId) previewLoading.value = false
        }
    }

    const scheduleOcrPreview = () => {
        if (ocrTimer) clearTimeout(ocrTimer)
        ocrTimer = null
        if (!hasOcrTemplate.value) {
            ocrRequestId += 1
            previewLoading.value = false
            previewText.value = ''
            return
        }
        ocrTimer = setTimeout(() => {
            ocrTimer = null
            fetchOcrText()
        }, 200)
    }

    const syncRecordedRegion = async (prefix = '') => {
        if (!props.node || !store.currentProjectPath) return
        const sourceKey = `${prefix}image_source`
        const regionKey = `${prefix}region_value`
        const referenceKey = `${prefix}region_reference_size`
        const rawTemplateName = props.node.params[sourceKey]
        if (!rawTemplateName) return
        const nodeId = props.node.node_id

        isSyncingRecorded = true
        try {
            const resolved = await visionApi.resolveTemplate(store.currentProjectPath, rawTemplateName)
            if (props.node.node_id !== nodeId || props.node.params[sourceKey] !== rawTemplateName) return
            const capture = resolved?.capture
            const rect = capture?.region
            if (Array.isArray(rect) && rect.length === 4 && Number(rect[2]) > 0 && Number(rect[3]) > 0) {
                const referenceSize = Array.isArray(capture.reference_size) ? capture.reference_size : [0, 0]
                const previousRegion = props.node.params[regionKey]
                const previousReference = props.node.params[referenceKey]
                const changed = JSON.stringify(previousRegion) !== JSON.stringify(rect)
                    || JSON.stringify(previousReference) !== JSON.stringify(referenceSize)
                    || props.node.params.coordinate_space !== (capture.coordinate_space || 'workspace_px')
                props.node.params[regionKey] = [...rect]
                props.node.params[referenceKey] = [...referenceSize]
                props.node.params.coordinate_space = capture.coordinate_space || 'workspace_px'
                props.node.params = { ...props.node.params }
                if (prefix) originalStopRecordedRegion.value = [...rect]
                else originalRecordedRegion.value = [...rect]
                if (changed) handleSave()
            }
        } catch (err) {
            console.error('获取区域配置失败', err)
        } finally {
            setTimeout(() => { isSyncingRecorded = false }, 300)
        }
    }

    watch(() => props.node?.node_id, () => {
        if (props.node?.params?.region_type === 'recorded') {
            syncRecordedRegion()
        }
        if (props.node?.params?.stop_region_type === 'recorded') {
            syncRecordedRegion('stop_')
        }
        previewText.value = ''
        ocrRequestId += 1
        previewLoading.value = false
    }, { immediate: true })

    const handleAutoChangeType = (inferredType) => {
        if (inferredType && props.node && props.node.params) {
            props.node.params.var_type = inferredType
            handleSave()
        }
    }

    // ⚡「重置控件」：清空控件名称 + 节点上存储的控件信息
    const handleCaptureReset = (paramName) => {
        props.node.params[paramName] = ''
        delete props.node.params.control_info
        props.node.params = { ...props.node.params }
        handleSave()
    }

    const resolveNodeAdb = async () => {
        if (props.node?.node_type !== 'set_window' || !props.node.params.is_emulator) return
        try {
            const result = await workspaceApi.resolveAdbDevice({
                windowTitle: props.node.params.title,
                windowHwnd: props.node.params.window_hwnd || 0,
                processId: props.node.params.window_process_id || 0
            })
            props.node.params.adb_device_id = result.serial || ''
        } catch (error) {
            props.node.params.is_emulator = false
            props.node.params.adb_device_id = ''
            ElMessage.error(error.response?.data?.detail || error.message || '无法自动识别模拟器 ADB 设备')
        }
        props.node.params = { ...props.node.params }
        handleSave()
    }

    const handleWindowSelected = async windowInfo => {
        if (props.node?.node_type !== 'set_window' || !windowInfo) return
        props.node.params.title = windowInfo.title || props.node.params.title || ''
        props.node.params.window_hwnd = Number(windowInfo.hwnd || 0)
        props.node.params.window_process_id = Number(windowInfo.process_id || 0)
        props.node.params.window_class_name = windowInfo.class_name || ''
        if (props.node.params.is_emulator) await resolveNodeAdb()
    }

    const handleParamUpdate = async (paramName, value) => {
        if (paramName === 'region_value' && props.node.params.region_type === 'recorded' && !isSyncingRecorded) {
            if (originalRecordedRegion.value && JSON.stringify(value) !== JSON.stringify(originalRecordedRegion.value)) {
                props.node.params.region_type = 'custom'
            }
        }
        if (paramName === 'stop_region_value' && props.node.params.stop_region_type === 'recorded' && !isSyncingRecorded) {
            if (originalStopRecordedRegion.value && JSON.stringify(value) !== JSON.stringify(originalStopRecordedRegion.value)) {
                props.node.params.stop_region_type = 'custom'
            }
        }
        props.node.params[paramName] = value
        props.node.params = { ...props.node.params }

        if (paramName === 'is_emulator') {
            if (value) await resolveNodeAdb()
            else props.node.params.adb_device_id = ''
        }

        if (paramName === 'region_type' && value === 'recorded') await syncRecordedRegion()
        if (paramName === 'image_source' && props.node.params.region_type === 'recorded') await syncRecordedRegion()
        if (paramName === 'stop_region_type' && value === 'recorded') await syncRecordedRegion('stop_')
        if (paramName === 'stop_image_source' && props.node.params.stop_region_type === 'recorded') await syncRecordedRegion('stop_')

        if (['image_source', 'gray_scale', 'gray_threshold'].includes(paramName)) {
            imageVersion.value = Date.now()
            if (props.node?.node_type === 'ocr_recognition') {
                scheduleOcrPreview()
            }
        }
        handleSave()
    }

    const handleCoordinateMeta = (paramName, meta) => {
        if (!meta?.referenceSize || !props.node?.params) return
        const referenceKey = paramName === 'position'
            ? 'position_reference_size'
            : (paramName.startsWith('stop_') ? 'stop_region_reference_size' : 'region_reference_size')
        props.node.params[referenceKey] = [...meta.referenceSize]
        props.node.params.coordinate_space = meta.coordinateSpace || 'workspace_px'
        props.node.params = { ...props.node.params }
        handleSave()
    }

    const handleCaptureBundle = (paramName, bundle) => {
        if (!bundle?.assetRef || !props.node?.params) return
        props.node.params[paramName] = bundle.assetRef
        const isStopFeature = paramName.startsWith('stop_')
        const prefix = isStopFeature ? 'stop_' : ''
        props.node.params[`${prefix}region_type`] = 'recorded'
        props.node.params[`${prefix}region_value`] = [...(bundle.rect || [0, 0, 0, 0])]
        props.node.params[`${prefix}region_reference_size`] = [...(bundle.referenceSize || [0, 0])]
        props.node.params.coordinate_space = bundle.coordinateSpace || 'workspace_px'
        props.node.params = { ...props.node.params }
        if (!isStopFeature) originalRecordedRegion.value = [...props.node.params.region_value]
        imageVersion.value = Date.now()
        if (props.node.node_type === 'ocr_recognition') scheduleOcrPreview()
        handleSave()
    }

    onUnmounted(() => {
        ocrRequestId += 1
        if (ocrTimer) clearTimeout(ocrTimer)
    })

    const handleSave = () => emit('save')
</script>

<style scoped>
    .panel-layout-root {
        width: 100%;
        height: 100%;
        display: flex;
        flex-direction: column;
        container: inspector / inline-size;
    }

    .inspector-fixed-header {
        padding: 12px;
        background: var(--app-bg-sidebar);
        border-bottom: 1px solid var(--app-separator);
        flex-shrink: 0;
    }

    .inspector-scrollable-body {
        flex: 1;
        padding: 12px;
        overflow-y: auto;
        overscroll-behavior: contain;
    }

    .inspector-fixed-footer {
        min-height: 42px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding: 7px 12px;
        background: var(--app-bg-sidebar);
        border-top: 1px solid var(--app-separator);
        flex-shrink: 0;
    }

    .node-title-box {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .node-type-icon-badge {
        width: 34px;
        height: 34px;
        background: rgba(217, 84, 23, 0.1);
        border: 1px solid rgba(217, 84, 23, 0.3);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }

    .inspector-type-svg {
        width: 18px;
        height: 18px;
        color: var(--el-color-primary);
    }

    .node-heading-copy { min-width: 0; flex: 1; }
    .node-name-input :deep(.el-input__wrapper) { min-height:28px !important; padding:0 8px !important; background:transparent !important; border-color:transparent !important; box-shadow:none !important; }
    .node-name-input :deep(.el-input__wrapper:hover), .node-name-input :deep(.el-input__wrapper.is-focus) { background:var(--app-bg-input) !important; border-color:var(--app-border-default) !important; }
    .node-name-input :deep(.el-input__inner) { font-size:13px; font-weight:600; }

    .params-container {
        display: flex;
        flex-direction: column;
        gap: 0;
    }

    .param-item {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .ocr-live-result-card {
        background: var(--app-bg-raised);
        border: 1px solid var(--app-border-default);
        border-radius: 8px;
        padding: 10px 12px;
        margin-bottom: 4px;
    }

    .result-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 11px;
        font-weight: 600;
        color: var(--app-text-secondary);
        margin-bottom: 6px;
    }

    .result-header > span {
        display: inline-flex;
        align-items: center;
        gap: 5px;
    }

    .result-text-box {
        font-size: 15px;
        font-weight: 600;
        color: var(--app-text-primary);
        word-break: break-all;
        line-height: 1.4;
    }

        .result-text-box.is-empty {
            font-size: 11px;
            font-weight: normal;
            color: var(--el-text-color-placeholder);
        }

    .slider-box {
        background: var(--el-fill-color-blank);
        padding: 10px 12px;
        border-radius: 8px;
        border: 1px solid var(--el-border-color-light);
    }

    .slider-header {
        display: flex;
        justify-content: space-between;
        font-size: 12px;
        color: var(--el-text-color-primary);
        margin-bottom: 4px;
    }

    .slider-tip {
        color: var(--el-text-color-secondary);
        font-size: 11px;
    }

    .footer-inline-container {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 14px;
    }

    .autosave-state { display:inline-flex; align-items:center; gap:4px; color:var(--app-text-secondary); font-size:10px; white-space:nowrap; }
    .autosave-state.is-saved { color:var(--app-color-success); }
    .autosave-state.is-error { color:var(--app-color-danger); }

    .footer-setting-group {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        color: var(--el-text-color-regular);
    }

    .footer-label {
        font-weight: 600;
        color: var(--el-text-color-primary);
    }

    .footer-unit {
        font-size: 11px;
        color: var(--el-text-color-secondary);
    }

    .pure-compact-input {
        width: 62px !important;
    }

        .pure-compact-input :deep(.el-input__wrapper) {
            padding-left: 4px !important;
            padding-right: 4px !important;
            background-color: var(--el-fill-color-blank) !important;
        }

    .is-spinning {
        animation: spin 1s linear infinite;
    }

    @container inspector (max-width: 360px) {
        .footer-inline-container { gap:8px; }
        .footer-setting-group { gap:4px; }
        .footer-label { font-size:10px; }
        .footer-unit { display:none; }
    }

    @keyframes spin {
        100% {
            transform: rotate(360deg);
        }
    }
</style>
