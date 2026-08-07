<template>
    <!-- 全屏模态背景遮罩：点击空白处自动保存并关闭 -->
    <div v-if="visible"
         class="inspector-backdrop"
         :style="{ zIndex: zIndex }"
         @click.self="saveInspector">

        <!-- 遮罩上的友好引导提示文字 -->
        <div class="backdrop-tip">💡 点击任意空白处即可自动保存并关闭</div>

        <div class="workflow-inspector-wrapper" :style="{ zIndex: zIndex + 1 }" @mousedown.stop>

            <!-- 1. 顶部固定区域：统一采用图二节点的卡片式头部（左侧图标 + 可直接修改名称的输入框） -->
            <div class="inspector-fixed-header" v-if="targetType === 'node' && currentNode">
                <div class="node-title-box">
                    <div class="node-type-icon-badge" :title="nodeTypeLabel">
                        <component :is="getNodeIcon(currentNode.node_type)" class="inspector-type-svg" />
                    </div>
                    <el-input v-model="currentNode.node_name"
                              size="default"
                              class="node-name-input"
                              placeholder="请输入节点名称" />
                </div>
            </div>
            <div class="inspector-fixed-header" v-else-if="targetType === 'group' && targetData">
                <div class="node-title-box">
                    <div class="node-type-icon-badge" title="任务组配置">
                        <Folder class="inspector-type-svg" />
                    </div>
                    <el-input v-model="targetData.groupName"
                              size="default"
                              class="node-name-input"
                              placeholder="请输入任务组名称" />
                </div>
            </div>

            <!-- 2. 中间可滚动区域：无内容时高度为 0，有内容时自动撑开 -->
            <div class="inspector-scrollable-body" v-show="hasScrollableContent">
                <!-- 节点编辑模式的内容 -->
                <template v-if="targetType === 'node' && currentNode">
                    <div class="params-container">
                        <template v-for="(config, paramName) in allParams" :key="paramName + (currentNode ? currentNode.node_id : '')">
                            <!-- 区域坐标显隐 -->
                            <div v-if="paramName === 'region_value'" v-show="shouldShowRegionValue" class="param-item">
                                <ParamRenderer :key="paramName + (currentNode ? currentNode.node_id : '')"
                                               :config="config"
                                               :value="currentNode.params.region_value"
                                               :label="config.label || paramName"
                                               :context="currentNode.params"
                                               @update="(val) => handleParamUpdate(paramName, val)" />
                            </div>

                            <!-- 灰度滑块（处于开启状态时，将预览图内嵌在下方） -->
                            <div v-else-if="paramName === 'gray_threshold' && currentNode.params.gray_scale" class="param-item slider-box">
                                <div class="slider-header">
                                    <span>二值化灰度阈值: <strong>{{ currentNode.params.gray_threshold ?? 127 }}</strong></span>
                                    <span class="slider-tip">(向左增强浅色，向右过滤背景)</span>
                                </div>
                                <el-slider v-model="currentNode.params.gray_threshold"
                                           :min="0" :max="255" :step="1"
                                           @change="fetchPreview" />

                                <!-- 嵌套在滑块下方的实时二值化效果预览 -->
                                <div class="preview-header" style="margin-top: 12px; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center;">
                                    <span class="slider-header" style="font-size: 13px; font-weight: 500; color: var(--el-text-color-primary);">二值化效果实时预览</span>
                                    <el-button size="small" class="icon-only-refresh-btn" @click="fetchPreview" title="刷新预览">
                                        <RefreshCcw style="width: 14px; height: 14px;" :class="{ 'is-spinning': previewLoading }" />
                                    </el-button>
                                </div>
                                <div class="preview-body" style="justify-content: center;">
                                    <div class="preview-box aspect-ratio-box" style="max-width: 100%;" :style="previewImg ? { '--bg-image-url': `url(${previewImg})` } : {}">
                                        <img v-if="previewImg" :src="previewImg" class="realtime-img" />
                                        <div v-else class="placeholder">点击刷新或拖动滑块加载预览</div>
                                    </div>
                                </div>
                            </div>

                            <!-- 其他通用组件 -->
                            <div v-else-if="!['region_value', 'gray_threshold', 'on_success', 'on_failure', 'candidates'].includes(paramName)" class="param-item">
                                <ParamRenderer :key="paramName + (currentNode ? currentNode.node_id : '')"
                                               :config="config"
                                               :value="currentNode.params[paramName]"
                                               :label="config.label || paramName"
                                               :context="currentNode.params"
                                               :inline="['threshold', 'timeout'].includes(paramName)"
                                               @update="(val) => handleParamUpdate(paramName, val)" />
                            </div>
                        </template>

                        <!-- branch 节点的 candidates 候选条件列表独立渲染 -->
                        <div v-if="currentNode.node_type === 'branch' && allParams.candidates" class="param-item">
                            <ParamRenderer :key="'candidates_' + (currentNode ? currentNode.node_id : '')"
                                           :config="allParams.candidates"
                                           :value="currentNode.params.candidates"
                                           :label="allParams.candidates.label || '多分支判定列表'"
                                           :context="currentNode.params"
                                           @update="(val) => handleParamUpdate('candidates', val)" />
                        </div>

                        <!-- 文字识别 (OCR) 实时调优卡片 -->
                        <div v-if="currentNode.node_type === 'ocr_recognition'" class="interactive-preview-card">
                            <div class="preview-header">
                                <span>👁️ OCR 视场与文本测试</span>
                                <el-button size="small" type="primary" link :loading="previewLoading" @click="fetchPreview">🔄 手动监测测试</el-button>
                            </div>
                            <div class="preview-body">
                                <div class="preview-box aspect-ratio-box" :style="previewImg ? { '--bg-image-url': `url(${previewImg})` } : {}">
                                    <div class="box-tag">二值化视角图</div>
                                    <img v-if="previewImg" :src="previewImg" class="realtime-img" />
                                    <div v-else class="placeholder">点击右上角进行监测</div>
                                </div>
                                <div class="preview-box aspect-ratio-box">
                                    <div class="box-tag">抓取文本结果</div>
                                    <div class="realtime-text" :class="{ empty: !previewText }">
                                        {{ previewText || '(点击测试后显示)' }}
                                    </div>
                                </div>
                            </div>
                        </div>

                    </div>
                </template>
            </div>

            <!-- 3. 底部固定区域：节点 or 任务组的底部同行精简配置展示 -->
            <div class="inspector-fixed-footer" v-if="targetType === 'node' && currentNode">
                <div class="footer-inline-container">
                    <div class="footer-setting-group">
                        <span class="footer-label">延迟</span>
                        <el-input v-model.number="currentNode.delay_before" size="small" class="pure-compact-input" />
                        <span class="footer-unit">ms</span>
                    </div>
                    <div class="footer-setting-group">
                        <span class="footer-label">循环</span>
                        <el-input v-model.number="currentNode.loop_count" size="small" class="pure-compact-input" />
                        <span class="footer-unit">次</span>
                    </div>
                </div>
            </div>

            <!-- 任务组专属底部 Footer：左侧循环间隔(ms)，右侧循环(次) -->
            <div class="inspector-fixed-footer" v-else-if="targetType === 'group' && targetData">
                <div class="footer-inline-container">
                    <div class="footer-setting-group">
                        <span class="footer-label">循环间隔</span>
                        <el-input v-model.number="targetData.loopInterval" size="small" class="pure-compact-input" />
                        <span class="footer-unit">ms</span>
                    </div>
                    <div class="footer-setting-group">
                        <span class="footer-label">循环</span>
                        <el-input v-model.number="targetData.loopCount" size="small" class="pure-compact-input" />
                        <span class="footer-unit">次</span>
                    </div>
                </div>
            </div>

        </div>
    </div>
</template>

<script>
    import { ref, computed, watch, nextTick } from 'vue'
    import { useMainStore } from '@/stores'
    import ParamRenderer from '@/components/ParamRenderer.vue'
    import { ElMessage } from 'element-plus'
    import axios from 'axios'
    import { RefreshCcw, Image, Folder } from 'lucide-vue-next'

    import {
        MousePointerClick,
        Clock,
        Target,
        FileSearch,
        GitBranch,
        SearchCheck,
        Binary,
        ListOrdered,
        FileCode,
        ScanText
    } from 'lucide-vue-next'

    export default {
        name: 'WorkflowInspector',
        components: {
            ParamRenderer,
            MousePointerClick,
            Clock,
            Target,
            FileSearch,
            GitBranch,
            SearchCheck,
            Binary,
            ListOrdered,
            FileCode,
            RefreshCcw,
            Image,
            ScanText,
            Folder
        },
        props: {
            visible: { type: Boolean, default: false },
            targetType: { type: String, default: 'node' },
            targetData: { type: Object, default: null },
            targets: { type: Array, default: () => [] },
            position: { type: Object, default: () => ({ x: 100, y: 100 }) },
            zIndex: { type: Number, default: 200 }
        },
        emits: ['update', 'close'],
        setup(props, { emit }) {
            const store = useMainStore()
            const currentNode = ref(null)

            const previewLoading = ref(false)
            const previewText = ref('')
            const previewImg = ref('')
            const imageScore = ref(0)
            const imageCenterPos = ref('(0, 0)')
            const originalRecordedRegion = ref(null)
            const imageVersion = ref(Date.now())
            let isSyncingRecorded = false

            // 任务组中间部分目前没有其他表单，因此默认返回 false 使得高度为 0
            const hasScrollableContent = computed(() => {
                if (props.targetType === 'node') {
                    return true // 节点有丰富的参数列表
                }
                return false // 任务组目前无中间表单，高度收缩为 0
            })

            const nodeIconComponentMap = {
                click: 'MousePointerClick',
                wait: 'Clock',
                image_recognition: 'Image',
                ocr_recognition: 'scan-text',
                branch: 'GitBranch',
                logic_check: 'SearchCheck',
                variable_op: 'Binary',
                log: 'ListOrdered',
                script_call: 'FileCode'
            }

            const getNodeIcon = (nodeType) => {
                return nodeIconComponentMap[nodeType] || 'FileCode'
            }

            const fetchPreview = async () => {
                const node = currentNode.value
                if (!node) return

                imageVersion.value = Date.now()
                previewLoading.value = true
                try {
                    if (node.node_type === 'ocr_recognition') {
                        const res = await axios.post('/api/ocr/test', {
                            project_path: store.currentProjectPath,
                            region_value: node.params.region_value || [0, 0, 0, 0],
                            gray_scale: node.params.gray_scale ?? true,
                            gray_threshold: node.params.gray_threshold ?? 127
                        })
                        if (!currentNode.value || !res.data) return
                        previewText.value = res.data.text || ''
                        previewImg.value = res.data.image ? `${res.data.image}&v=${imageVersion.value}` : ''
                    } else if (node.node_type === 'image_recognition') {
                        const imageSource = node.params.image_source
                        if (!imageSource || imageSource.includes('未选择') || !imageSource.trim()) {
                            previewImg.value = ''
                            return
                        }
                        const res = await axios.post('/api/image/test', {
                            project_path: store.currentProjectPath,
                            template_name: imageSource,
                            gray_scale: node.params.gray_scale ?? true,
                            gray_threshold: node.params.gray_threshold ?? 127
                        })
                        if (!currentNode.value || !res.data) return
                        previewImg.value = res.data.image ? (res.data.image.startsWith('data:') ? res.data.image : `${res.data.image}&v=${imageVersion.value}`) : ''
                    }
                } catch (err) {
                    console.warn('监测测试调用异常', err)
                } finally {
                    previewLoading.value = false
                }
            }

            const syncRecordedRegion = async () => {
                const node = currentNode.value
                if (!node || !store.currentProjectPath) return

                const rawTemplateName = node.params.image_source
                if (!rawTemplateName) return

                isSyncingRecorded = true
                try {
                    const res = await axios.get('/api/regions', {
                        params: { project_path: store.currentProjectPath }
                    })
                    if (!currentNode.value) return
                    const regions = res.data || {}
                    const cleanName = rawTemplateName.replace(/\.png$/i, '').replace(/\\/g, '/')
                    const fileNameOnly = cleanName.split('/').pop()

                    const rect = regions[rawTemplateName] || regions[cleanName] || regions[fileNameOnly] || regions[`${cleanName}.png`] || regions[`${fileNameOnly}.png`]

                    if (rect && Array.isArray(rect) && rect.length === 4) {
                        node.params.region_value = [...rect]
                        originalRecordedRegion.value = [...rect]
                    }
                } catch (err) {
                    console.error('获取区域配置失败', err)
                } finally {
                    setTimeout(() => { isSyncingRecorded = false }, 300)
                }
            }

            watch(() => props.targetData, (newVal) => {
                if (props.targetType === 'node' && newVal) {
                    const nodeCopy = JSON.parse(JSON.stringify(newVal))
                    if (!nodeCopy.params) nodeCopy.params = {}

                    const defs = store.params[nodeCopy.node_type]?.params || {}
                    for (const [pName, pConfig] of Object.entries(defs)) {
                        if (nodeCopy.params[pName] === undefined) {
                            nodeCopy.params[pName] = pConfig.default !== undefined ? JSON.parse(JSON.stringify(pConfig.default)) : ''
                        }
                    }

                    currentNode.value = nodeCopy
                    if (currentNode.value.params.region_type === 'recorded') {
                        syncRecordedRegion()
                    }

                    previewImg.value = ''
                    previewText.value = ''
                    imageScore.value = 0
                    imageCenterPos.value = '(0, 0)'

                    if (currentNode.value.node_type === 'image_recognition' && currentNode.value.params.gray_scale) {
                        nextTick(() => {
                            fetchPreview()
                        })
                    }
                }
            }, { immediate: true, deep: true })

            const paramDefs = computed(() => {
                const node = currentNode.value
                if (!node) return {}
                return store.params[node.node_type]?.params || {}
            })

            const nodeTypeLabel = computed(() => {
                const node = currentNode.value
                if (!node) return ''
                return store.params[node.node_type]?.label || node.node_type
            })

            const shouldShowRegionValue = computed(() => {
                const node = currentNode.value
                if (!node || !node.params) return false
                const nodeType = node.node_type
                if (nodeType === 'ocr_recognition') return true
                const regionType = node.params.region_type
                return regionType === 'recorded' || regionType === 'custom'
            })

            const isMatchPass = computed(() => {
                const targetThreshold = currentNode.value?.params?.threshold ?? 85
                return imageScore.value >= targetThreshold
            })

            const allParams = computed(() => paramDefs.value)

            const handleParamUpdate = (paramName, value) => {
                const node = currentNode.value
                if (!node) return

                if (paramName === 'region_value' && node.params.region_type === 'recorded' && !isSyncingRecorded) {
                    if (originalRecordedRegion.value && JSON.stringify(value) !== JSON.stringify(originalRecordedRegion.value)) {
                        node.params.region_type = 'custom'
                        ElMessage.info('检测到坐标手动微调，已自动切换为【自定义区域】模式')
                    }
                }

                node.params[paramName] = value
                node.params = { ...node.params }

                if (paramName === 'region_type' && value === 'recorded') {
                    syncRecordedRegion()
                }
                if (paramName === 'image_source' && node.params.region_type === 'recorded') {
                    syncRecordedRegion()
                }

                if (['image_source', 'gray_scale', 'gray_threshold'].includes(paramName)) {
                    imageVersion.value = Date.now()
                    fetchPreview()
                }
            }

            const saveInspector = async () => {
                try {
                    if (props.targetType === 'node' && currentNode.value) {
                        const tasks = store.currentTaskData?.tasks || []
                        for (const task of tasks) {
                            if (task.nodes) {
                                const idx = task.nodes.findIndex(n => n.node_id === currentNode.value.node_id)
                                if (idx > -1) {
                                    currentNode.value.loop_count = Number(currentNode.value.loop_count) || 1
                                    currentNode.value.delay_before = Number(currentNode.value.delay_before) || 0

                                    task.nodes[idx] = JSON.parse(JSON.stringify(currentNode.value))
                                    break
                                }
                            }
                        }
                    } else if (props.targetType === 'group' && props.targetData) {
                        props.targetData.loopCount = Number(props.targetData.loopCount) || 1
                        props.targetData.loopInterval = Number(props.targetData.loopInterval) || 0

                        const tasks = store.currentTaskData?.tasks || []
                        const groupTask = tasks.find(t => t.task_id === props.targetData.taskId || `group_${t.task_id || tasks.indexOf(t)}` === props.targetData.groupId)
                        if (groupTask) {
                            groupTask.task_name = props.targetData.groupName
                            groupTask.loop_count = props.targetData.loopCount
                            groupTask.loop_interval = props.targetData.loopInterval
                        }
                    }

                    await axios.post('/api/blueprint/save', {
                        project_path: store.currentProjectPath,
                        blueprint_data: store.currentTaskData
                    })

                    await store.loadTasks()

                    ElMessage.success('配置已自动保存')
                    emit('update')
                    emit('close')
                } catch (err) {
                    console.error('保存配置失败:', err)
                    ElMessage.error('保存失败')
                }
            }

            return {
                currentNode,
                allParams,
                shouldShowRegionValue,
                nodeTypeLabel,
                previewLoading,
                previewText,
                previewImg,
                imageScore,
                imageCenterPos,
                isMatchPass,
                handleParamUpdate,
                fetchPreview,
                saveInspector,
                getNodeIcon,
                hasScrollableContent
            }
        }
    }
</script>

<style scoped>
    /* 全屏透明模态遮罩 */
    .inspector-backdrop {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: rgba(0, 0, 0, 0.25);
        pointer-events: auto;
        display: flex;
        justify-content: center;
        align-items: center;
    }

    /* 遮罩上的提示文字 */
    .backdrop-tip {
        position: absolute;
        top: 24px;
        background: rgba(43, 45, 61, 0.85);
        border: 1px solid var(--el-color-primary, #4ed19c);
        color: var(--el-color-primary, #4ed19c);
        padding: 6px 16px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: bold;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        pointer-events: none;
        animation: fadeInDown 0.3s ease;
    }

    @keyframes fadeInDown {
        from {
            opacity: 0;
            transform: translateY(-10px);
        }

        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* 浮动式详情面板：与右侧节点配置面板质感完全一致 */
    .workflow-inspector-wrapper {
        position: relative;
        width: 380px;
        max-height: calc(380px * 1.5);
        background: rgba(38, 40, 61, 0.95);
        backdrop-filter: blur(12px);
        border: 1px solid var(--el-color-primary, #4ed19c);
        border-radius: 12px;
        box-shadow: 0 12px 36px rgba(0, 0, 0, 0.6);
        display: flex;
        flex-direction: column;
        user-select: none;
        overflow: hidden;
    }

    /* 1. 顶部固定区 (Header) */
    .inspector-fixed-header {
        padding: 14px 16px;
        background: rgba(25, 26, 38, 0.95);
        border-bottom: 1px solid var(--el-border-color-light, #313352);
        flex-shrink: 0;
        z-index: 2;
    }

    /* 2. 中间滚动区 (Body)：默认无内容时自动收缩为 0 占用 */
    .inspector-scrollable-body {
        flex: 1;
        padding: 0 16px;
        overflow-y: auto;
        overscroll-behavior: contain;
    }

        /* 当中间有实际内容时自动加上内边距 */
        .inspector-scrollable-body:not(:empty) {
            padding: 16px;
        }

    /* 3. 底部固定区 (Footer) */
    .inspector-fixed-footer {
        padding: 10px 16px;
        background: rgba(25, 26, 38, 0.95);
        border-top: 1px solid var(--el-border-color-light, #313352);
        flex-shrink: 0;
        z-index: 2;
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

    /* 底部纯净输入框样式 */
    .pure-compact-input {
        width: 60px !important;
    }

        .pure-compact-input :deep(.el-input__wrapper) {
            padding-left: 4px !important;
            padding-right: 4px !important;
            background-color: var(--el-fill-color-blank) !important;
            box-shadow: 0 0 0 1px var(--el-border-color-light) inset !important;
        }

        .pure-compact-input :deep(.el-input__inner) {
            text-align: center;
            font-size: 12px;
            color: var(--el-text-color-primary);
        }

    /* 顶部标题栏里的图标与输入框 */
    .node-title-box {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .node-type-icon-badge {
        width: 36px;
        height: 36px;
        background: rgba(78, 209, 156, 0.1);
        border: 1px solid rgba(78, 209, 156, 0.3);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }

    .inspector-type-svg {
        width: 20px;
        height: 20px;
        color: var(--el-color-primary, #4ed19c);
    }

    .node-name-input :deep(.el-input__wrapper) {
        background-color: var(--el-fill-color-blank);
        box-shadow: 0 0 0 1px var(--el-border-color-light) inset;
    }

    .node-name-input :deep(.el-input__inner) {
        color: var(--el-text-color-primary);
        font-size: 16px;
        font-weight: 600;
    }

    /* 参数容器 */
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

    .interactive-preview-card {
        background: var(--el-fill-color-blank);
        border: 1px solid var(--el-border-color-light);
        border-radius: 8px;
        padding: 12px;
        margin-top: 4px;
    }

    .preview-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 13px;
        font-weight: bold;
        color: var(--el-color-primary);
        margin-bottom: 10px;
    }

    .preview-body {
        display: flex;
        gap: 12px;
    }

    .preview-box {
        position: relative;
        flex: 1;
        background: var(--el-bg-color);
        border: 1px solid var(--el-border-color-light);
        border-radius: 6px;
        padding: 8px;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .aspect-ratio-box {
        aspect-ratio: 4 / 3;
        width: 100%;
        box-sizing: border-box;
    }

    .preview-box::before {
        content: '';
        position: absolute;
        inset: -20px;
        background-image: var(--bg-image-url);
        background-size: cover;
        background-position: center;
        filter: blur(14px) brightness(0.5);
        z-index: 1;
    }

    .box-tag {
        position: relative;
        font-size: 11px;
        color: #fff;
        text-shadow: 0 1px 2px rgba(0,0,0,0.8);
        margin-bottom: 6px;
        flex-shrink: 0;
        z-index: 2;
    }

    .realtime-img {
        position: relative;
        width: 100%;
        height: 100%;
        object-fit: contain !important;
        border-radius: 4px;
        display: block;
        margin: auto;
        z-index: 2;
        pointer-events: none;
    }

    .placeholder {
        position: relative;
        color: var(--el-text-color-placeholder);
        font-size: 11px;
        text-align: center;
        margin: auto;
        z-index: 2;
    }

    .realtime-text {
        font-size: 18px;
        font-weight: bold;
        color: #67C23A;
        margin: auto;
        word-break: break-all;
        text-align: center;
        z-index: 2;
    }

        .realtime-text.empty {
            color: var(--el-text-color-placeholder);
            font-size: 12px;
        }

    /* 纯图标按钮样式 */
    .icon-only-refresh-btn {
        background-color: transparent !important;
        border: none !important;
        color: #fff !important;
        width: 28px !important;
        height: 28px !important;
        padding: 0 !important;
        border-radius: 4px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: background-color 0.2s ease;
    }

        .icon-only-refresh-btn:hover {
            background-color: rgba(255, 255, 255, 0.1) !important;
            color: #fff !important;
        }

        .icon-only-refresh-btn:active {
            background-color: rgba(255, 255, 255, 0.2) !important;
        }
</style>