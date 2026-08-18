<!-- frontend/src/components/inspector/panels/NodeInspectorPanel.vue -->
<template>
    <div class="panel-layout-root">
        <!-- 1. 顶部固定标题 -->
        <div class="inspector-fixed-header">
            <div class="node-title-box">
                <div class="node-type-icon-badge" :title="nodeTypeLabel">
                    <component :is="getNodeIcon(node.node_type)" class="inspector-type-svg" />
                </div>
                <el-input v-model="node.node_name" size="default" class="node-name-input" placeholder="请输入节点名称" @change="handleSave" />
            </div>
        </div>

        <!-- 2. 中间滚动参数区 -->
        <div class="inspector-scrollable-body">
            <div class="params-container">
                <!-- ⚡ OCR 专属: 顶部图片下方的实时识字高亮结果框 -->
                <div v-if="node.node_type === 'ocr_recognition'" class="ocr-live-result-card">
                    <div class="result-header">
                        <span>🔤 当前视角识别文字结果</span>
                        <el-button size="small" type="primary" link :loading="previewLoading" @click="fetchOcrText">
                            <RefreshCcw style="width: 12px; height: 12px; margin-right: 2px;" :class="{ 'is-spinning': previewLoading }" />
                            测试识别
                        </el-button>
                    </div>
                    <div class="result-text-box" :class="{ 'is-empty': !previewText }">
                        {{ previewText || '(暂未识别到文本，拖动灰度滑条或点击测试)' }}
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
                                   @input="val => handleParamUpdate('gray_threshold', val)"
                                   @change="val => handleParamUpdate('gray_threshold', val)" />
                    </div>

                    <!-- 基础通用参数渲染网关 -->
                    <div v-else-if="!['gray_threshold', 'on_success', 'on_failure'].includes(paramName)" class="param-item">
                        <ParamRenderer
:config="config"
                                       :value="node.params[paramName]"
                                       :label="config.label || paramName"
                                       :context="node.params"
                                       @update="val => handleParamUpdate(paramName, val)"
                                       @auto-change-type="handleAutoChangeType"
                                       @capture-reset="handleCaptureReset(paramName)" />
                    </div>
                </template>
            </div>
        </div>

        <!-- 3. 底部固定延时/循环 -->
        <div class="inspector-fixed-footer">
            <div class="footer-inline-container">
                <div class="footer-setting-group">
                    <span class="footer-label">延迟</span>
                    <el-input v-model.number="node.delay_before" size="small" class="pure-compact-input" @change="handleSave" />
                    <span class="footer-unit">ms</span>
                </div>
                <div class="footer-setting-group">
                    <span class="footer-label">循环</span>
                    <el-input v-model.number="node.loop_count" size="small" class="pure-compact-input" @change="handleSave" />
                    <span class="footer-unit">次</span>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
    import { ref, computed, watch } from 'vue'
    import { useMainStore } from '@/stores'
    import { visionApi } from '@/api/visionApi'
    import ParamRenderer from '@/components/ParamRenderer.vue'
    import {
        MousePointerClick, Clock, Image, ScanText, GitBranch,
        SearchCheck, Binary, ListOrdered, FileCode, RefreshCcw, ScanSearch
    } from 'lucide-vue-next'
    import { NODE_TYPE_CONFIG } from '@/utils/canvasShared'

    const props = defineProps({
        node: { type: Object, required: true }
    })
    const emit = defineEmits(['save'])
    const store = useMainStore()

    const previewLoading = ref(false)
    const previewText = ref('')
    const originalRecordedRegion = ref(null)
    const imageVersion = ref(Date.now())
    let isSyncingRecorded = false
    let ocrTimer = null

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

    // ⚡ OCR 文本测试识别方法
    const fetchOcrText = async () => {
        if (!props.node || props.node.node_type !== 'ocr_recognition') return
        previewLoading.value = true
        try {
            const res = await visionApi.testOcr(
                store.currentProjectPath,
                props.node.params.region_value || [0, 0, 0, 0],
                props.node.params.gray_scale ?? true,
                props.node.params.gray_threshold ?? 127,
                props.node.params.image_source || ''
            )
            if (res) {
                previewText.value = res.text || ''
            }
        } catch (err) {
            console.warn('OCR 测试失败', err)
        } finally {
            previewLoading.value = false
        }
    }

    const syncRecordedRegion = async () => {
        if (!props.node || !store.currentProjectPath) return
        const rawTemplateName = props.node.params.image_source
        if (!rawTemplateName) return

        isSyncingRecorded = true
        try {
            const regions = await visionApi.getRegions(store.currentProjectPath)
            const cleanName = rawTemplateName.replace(/\.png$/i, '').replace(/\\/g, '/')
            const fileNameOnly = cleanName.split('/').pop()
            const rect = regions[rawTemplateName] || regions[cleanName] || regions[fileNameOnly] || regions[`${cleanName}.png`]
            if (rect && Array.isArray(rect) && rect.length === 4) {
                props.node.params.region_value = [...rect]
                originalRecordedRegion.value = [...rect]
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
        previewText.value = ''
        if (props.node?.node_type === 'ocr_recognition') {
            fetchOcrText()
        }
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

    const handleParamUpdate = (paramName, value) => {
        if (paramName === 'region_value' && props.node.params.region_type === 'recorded' && !isSyncingRecorded) {
            if (originalRecordedRegion.value && JSON.stringify(value) !== JSON.stringify(originalRecordedRegion.value)) {
                props.node.params.region_type = 'custom'
            }
        }
        props.node.params[paramName] = value
        props.node.params = { ...props.node.params }

        if (paramName === 'region_type' && value === 'recorded') syncRecordedRegion()
        if (paramName === 'image_source' && props.node.params.region_type === 'recorded') syncRecordedRegion()

        if (['image_source', 'gray_scale', 'gray_threshold'].includes(paramName)) {
            imageVersion.value = Date.now()
            if (props.node?.node_type === 'ocr_recognition') {
                if (ocrTimer) clearTimeout(ocrTimer)
                ocrTimer = setTimeout(fetchOcrText, 200)
            }
        }
        handleSave()
    }

    const handleSave = () => emit('save')
</script>

<style scoped>
    .panel-layout-root {
        width: 100%;
        height: 100%;
        display: flex;
        flex-direction: column;
    }

    .inspector-fixed-header {
        padding: 12px 14px;
        background: rgba(25, 26, 38, 0.95);
        border-bottom: 1px solid var(--el-border-color-light);
        flex-shrink: 0;
    }

    .inspector-scrollable-body {
        flex: 1;
        padding: 12px 14px;
        overflow-y: auto;
        overscroll-behavior: contain;
    }

    .inspector-fixed-footer {
        padding: 10px 14px;
        background: rgba(25, 26, 38, 0.95);
        border-top: 1px solid var(--el-border-color-light);
        flex-shrink: 0;
    }

    .node-title-box {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .node-type-icon-badge {
        width: 32px;
        height: 32px;
        background: rgba(78, 209, 156, 0.1);
        border: 1px solid rgba(78, 209, 156, 0.3);
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

    .params-container {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .param-item {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .ocr-live-result-card {
        background: rgba(103, 194, 58, 0.08);
        border: 1px solid rgba(103, 194, 58, 0.3);
        border-radius: 8px;
        padding: 10px 12px;
        margin-bottom: 4px;
    }

    .result-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 11px;
        font-weight: bold;
        color: var(--el-color-success);
        margin-bottom: 6px;
    }

    .result-text-box {
        font-size: 15px;
        font-weight: bold;
        color: var(--el-color-success);
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
        justify-content: space-between;
    }

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
        width: 60px !important;
    }

        .pure-compact-input :deep(.el-input__wrapper) {
            padding-left: 4px !important;
            padding-right: 4px !important;
            background-color: var(--el-fill-color-blank) !important;
        }

    .is-spinning {
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        100% {
            transform: rotate(360deg);
        }
    }
</style>