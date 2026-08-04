<template>
    <div class="node-editor-panel">
        <div v-if="store.selectedNode" class="editor-form">
            <div class="node-title">
                <span class="node-type-badge">{{ nodeTypeLabel }}</span>
                <span class="node-name">{{ store.selectedNode.node_name }}</span>
            </div>

            <el-divider content-position="left">参数配置与调优区</el-divider>
            <div class="params-container">
                <!-- 1. 通用字段渲染 -->
                <template v-for="(config, paramName) in allParams" :key="paramName">
                    <!-- 区域坐标显隐 -->
                    <div v-if="paramName === 'region_value'"
                         v-show="shouldShowRegionValue"
                         class="param-item">
                        <ParamRenderer :key="paramName + store.selectedNodeId"
                                       :config="config"
                                       :value="store.selectedNode.params.region_value"
                                       :label="config.label || paramName"
                                       :context="store.selectedNode.params"
                                       @update="(val) => handleParamUpdate(paramName, val)" />
                    </div>

                    <!-- 灰度滑块（处于开启状态时） -->
                    <div v-else-if="paramName === 'gray_threshold' && store.selectedNode.params.gray_scale"
                         class="param-item slider-box">
                        <div class="slider-header">
                            <span>二值化灰度阈值: <strong>{{ store.selectedNode.params.gray_threshold ?? 127 }}</strong></span>
                            <span class="slider-tip">(向左增强浅色，向右过滤背景)</span>
                        </div>
                        <el-slider v-model="store.selectedNode.params.gray_threshold"
                                   :min="0"
                                   :max="255"
                                   :step="1"
                                   @input="debounceRefreshRealtime" />
                    </div>

                    <!-- 其他通用组件（排除跳转和候选列表，由下方独立接管） -->
                    <div v-else-if="!['region_value', 'gray_threshold', 'on_success', 'on_failure', 'candidates'].includes(paramName)"
                         class="param-item">
                        <ParamRenderer :key="paramName + store.selectedNodeId"
                                       :config="config"
                                       :value="store.selectedNode.params[paramName]"
                                       :label="config.label || paramName"
                                       :context="store.selectedNode.params"
                                       @update="(val) => handleParamUpdate(paramName, val)" />
                    </div>
                </template>

                <!-- ⭐⭐⭐ 2. 特别针对 branch 节点的 candidates 候选条件列表独立渲染 -->
                <div v-if="store.selectedNode.node_type === 'branch' && allParams.candidates" class="param-item">
                    <ParamRenderer :key="'candidates_' + store.selectedNodeId"
                                   :config="allParams.candidates"
                                   :value="store.selectedNode.params.candidates"
                                   :label="allParams.candidates.label || '多分支判定列表'"
                                   :context="store.selectedNode.params"
                                   @update="(val) => handleParamUpdate('candidates', val)" />
                </div>

                <!-- ⭐⭐⭐ 3. 文字识别 (OCR) 实时调优卡片 -->
                <div v-if="store.selectedNode.node_type === 'ocr_recognition'" class="interactive-preview-card">
                    <div class="preview-header">
                        <span>👁️ OCR 实时视场与文本预览</span>
                        <el-button size="small" type="primary" link :loading="previewLoading" @click="fetchPreview">
                            🔄 刷新视角
                        </el-button>
                    </div>
                    <div class="preview-body">
                        <div class="preview-box">
                            <div class="box-tag">二值化视角图</div>
                            <img v-if="previewImg" :src="previewImg" class="realtime-img" />
                            <div v-else class="placeholder">未框选有效区域</div>
                        </div>
                        <div class="preview-box">
                            <div class="box-tag">抓取文本结果</div>
                            <div class="realtime-text" :class="{ empty: !previewText }">
                                {{ previewText || '(未识别到文本)' }}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- ⭐⭐⭐ 4. 图像识别 实时调优卡片 -->
                <div v-if="store.selectedNode.node_type === 'image_recognition'" class="interactive-preview-card">
                    <div class="preview-header">
                        <span>🎯 图像匹配实时对比分析</span>
                        <el-button size="small" type="primary" link :loading="previewLoading" @click="fetchPreview">
                            🔄 刷新视角
                        </el-button>
                    </div>
                    <div class="preview-body">
                        <div class="preview-box">
                            <div class="box-tag">二值化搜索画幅 (红框为找到的目标)</div>
                            <img v-if="previewImg" :src="previewImg" class="realtime-img" />
                            <div v-else class="placeholder">请先选择模板图片</div>
                        </div>
                        <div class="preview-box stat-box">
                            <div class="box-tag">匹配得分与位置</div>
                            <div class="stat-score" :class="{ pass: isMatchPass }">
                                {{ imageScore }}%
                            </div>
                            <div class="stat-detail">
                                <span>判定: <strong>{{ isMatchPass ? '✅ 匹配成功' : '❌ 未达阈值' }}</strong></span>
                                <span>中心点: <strong>{{ imageCenterPos }}</strong></span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- ⭐⭐⭐ 5. 恢复所有判断/行为节点的【成功跳转】与【失败跳转】配置区 -->
                <template v-if="hasJumpConfig">
                    <div v-for="jumpKey in jumpKeysList" :key="jumpKey" class="jump-section">
                        <el-divider content-position="left">
                            {{ jumpKey === 'on_success' ? '成功跳转' : (store.selectedNode.node_type === 'branch' ? '兜底失败跳转 (全不满足时)' : '失败跳转') }}
                        </el-divider>
                        <div class="jump-config">
                            <div class="param-item">
                                <ParamRenderer :config="jumpTypeConfig"
                                               :value="store.selectedNode.params[jumpKey]?.jump_type || store.selectedNode.params[jumpKey]?.type || 'next'"
                                               label="跳转类型"
                                               :context="store.selectedNode.params"
                                               @update="(val) => updateJumpParam(jumpKey, 'jump_type', val)" />
                            </div>
                            <!-- 动态目标任务 -->
                            <div v-if="['task'].includes(store.selectedNode.params[jumpKey]?.jump_type || store.selectedNode.params[jumpKey]?.type)" class="param-item">
                                <ParamRenderer :config="getTargetConfig(jumpKey)"
                                               :value="store.selectedNode.params[jumpKey]?.target_task || store.selectedNode.params[jumpKey]?.target || ''"
                                               label="目标任务"
                                               :context="store.selectedNode.params"
                                               @update="(val) => updateJumpParam(jumpKey, 'target_task', val)" />
                            </div>
                            <!-- 动态目标节点 -->
                            <div v-if="['node', 'task'].includes(store.selectedNode.params[jumpKey]?.jump_type || store.selectedNode.params[jumpKey]?.type)" class="param-item">
                                <ParamRenderer :config="getTargetNodeConfig(jumpKey)"
                                               :value="store.selectedNode.params[jumpKey]?.target_node || ''"
                                               label="目标节点"
                                               :context="store.selectedNode.params"
                                               @update="(val) => updateJumpParam(jumpKey, 'target_node', val)" />
                            </div>
                        </div>
                    </div>
                </template>
            </div>

            <div class="save-actions">
                <el-button type="primary" size="small" @click="saveNode">保存参数</el-button>
            </div>
        </div>
        <div v-else class="empty">请从节点列表中选择一个节点</div>
    </div>
</template>

<script>
    import { useMainStore } from '@/stores'
    import { computed, ref, watch } from 'vue'
    import ParamRenderer from '@/components/ParamRenderer.vue'
    import { ElMessage } from 'element-plus'
    import { logger } from '@/utils/logger'
    import axios from 'axios'

    export default {
        name: 'NodeEditorPanel',
        components: { ParamRenderer },
        setup() {
            const store = useMainStore()

            const previewLoading = ref(false)
            const previewText = ref('')
            const previewImg = ref('')
            const imageScore = ref(0)
            const imageCenterPos = ref('(0, 0)')
            const originalRecordedRegion = ref(null)
            let isSyncingRecorded = false
            let timer = null

            const paramDefs = computed(() => {
                const node = store.selectedNode
                if (!node) return {}
                return store.params[node.node_type]?.params || {}
            })

            const nodeTypeLabel = computed(() => {
                const node = store.selectedNode
                if (!node) return ''
                return store.params[node.node_type]?.label || node.node_type
            })

            // 判断当前节点是否包含跳转配置
            const hasJumpConfig = computed(() => {
                const defs = paramDefs.value
                return defs && ('on_success' in defs || 'on_failure' in defs)
            })

            // 动态决定要渲染哪些跳转区
            const jumpKeysList = computed(() => {
                const defs = paramDefs.value
                const keys = []
                if ('on_success' in defs) keys.push('on_success')
                if ('on_failure' in defs) keys.push('on_failure')
                return keys
            })

            const shouldShowRegionValue = computed(() => {
                const node = store.selectedNode
                if (!node || !node.params) return false
                const nodeType = node.node_type
                if (nodeType === 'ocr_recognition') return true
                const regionType = node.params.region_type
                return regionType === 'recorded' || regionType === 'custom'
            })

            const isMatchPass = computed(() => {
                const targetThreshold = store.selectedNode?.params?.threshold ?? 85
                return imageScore.value >= targetThreshold
            })

            const allParams = computed(() => paramDefs.value)

            const jumpTypeConfig = {
                type: 'select',
                options: [
                    { value: 'next', label: '下一个节点' },
                    { value: 'node', label: '跳转节点' },
                    { value: 'task', label: '跳转任务' },
                    { value: 'end', label: '结束流程' }
                ],
                default: 'next',
                label: '跳转类型'
            }

            const getTargetConfig = (jumpKey) => ({
                type: 'select',
                options: (store.tasks || []).map(t => ({ value: t.task_id, label: t.task_name || t.task_id })),
                default: '',
                label: '目标任务'
            })

            const getTargetNodeConfig = (jumpKey) => ({
                type: 'select',
                options: (store.nodes || []).map(n => ({ value: n.node_id, label: n.node_name || n.node_id })),
                default: '',
                label: '目标节点'
            })

            const handleParamUpdate = (paramName, value) => {
                const node = store.selectedNode
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

                if (['image_source', 'region_value', 'region_type', 'gray_scale', 'gray_threshold', 'threshold'].includes(paramName)) {
                    debounceRefreshRealtime()
                }
            }

            const updateJumpParam = (jumpKey, subKey, value) => {
                const node = store.selectedNode
                if (!node) return
                if (!node.params[jumpKey]) {
                    node.params[jumpKey] = { jump_type: 'next', target_task: '', target_node: '' }
                }
                node.params[jumpKey][subKey] = value
                node.params = { ...node.params }
            }

            const syncRecordedRegion = async () => {
                const node = store.selectedNode
                if (!node || !store.currentProjectPath) return

                const rawTemplateName = node.params.image_source
                if (!rawTemplateName) return

                isSyncingRecorded = true
                try {
                    const res = await axios.get('/api/regions', {
                        params: { project_path: store.currentProjectPath }
                    })
                    const regions = res.data || {}
                    const cleanName = rawTemplateName.replace(/\.png$/i, '').replace(/\\/g, '/')
                    const fileNameOnly = cleanName.split('/').pop()

                    const rect = regions[rawTemplateName] || regions[cleanName] || regions[fileNameOnly] || regions[`${cleanName}.png`] || regions[`${fileNameOnly}.png`]

                    if (rect && Array.isArray(rect) && rect.length === 4) {
                        node.params.region_value = [...rect]
                        originalRecordedRegion.value = [...rect]
                        debounceRefreshRealtime()
                    }
                } catch (err) {
                    logger.error('NodeEditor', '获取区域配置失败:', err)
                } finally {
                    setTimeout(() => { isSyncingRecorded = false }, 300)
                }
            }

            const debounceRefreshRealtime = () => {
                if (timer) clearTimeout(timer)
                timer = setTimeout(() => {
                    fetchPreview()
                }, 150)
            }

            const fetchPreview = async () => {
                const node = store.selectedNode
                if (!node) return

                previewLoading.value = true
                try {
                    if (node.node_type === 'ocr_recognition') {
                        const res = await axios.post('/api/ocr/test', {
                            project_path: store.currentProjectPath,
                            region_value: node.params.region_value || [0, 0, 0, 0],
                            gray_scale: node.params.gray_scale ?? true,
                            gray_threshold: node.params.gray_threshold ?? 127
                        })
                        previewText.value = res.data.text
                        previewImg.value = res.data.image
                    } else if (node.node_type === 'image_recognition') {
                        if (!node.params.image_source) {
                            previewImg.value = ''
                            imageScore.value = 0
                            return
                        }
                        const res = await axios.post('/api/image/test', {
                            project_path: store.currentProjectPath,
                            template_name: node.params.image_source,
                            region_type: node.params.region_type || 'fullwindow',
                            region_value: node.params.region_value || [0, 0, 0, 0],
                            gray_scale: node.params.gray_scale ?? true,
                            gray_threshold: node.params.gray_threshold ?? 127
                        })
                        imageScore.value = res.data.confidence
                        imageCenterPos.value = JSON.stringify(res.data.center_pos)
                        previewImg.value = res.data.image
                    }
                } catch (err) {
                    console.error('实时预览调用异常', err)
                } finally {
                    previewLoading.value = false
                }
            }

            watch(
                () => store.selectedNodeId,
                (newId) => {
                    if (newId) {
                        const node = store.selectedNode
                        if (node?.params?.region_type === 'recorded') {
                            syncRecordedRegion()
                        }
                        if (['ocr_recognition', 'image_recognition'].includes(node?.node_type)) {
                            fetchPreview()
                        }
                    }
                },
                { immediate: true }
            )

            const saveNode = async () => {
                try {
                    await store.saveCurrentTask(true)
                    ElMessage.success('参数已保存')
                } catch (err) {
                    ElMessage.error('保存失败')
                }
            }

            return {
                store,
                allParams,
                shouldShowRegionValue,
                hasJumpConfig,
                jumpKeysList,
                jumpTypeConfig,
                getTargetConfig,
                getTargetNodeConfig,
                nodeTypeLabel,
                previewLoading,
                previewText,
                previewImg,
                imageScore,
                imageCenterPos,
                isMatchPass,
                handleParamUpdate,
                updateJumpParam,
                debounceRefreshRealtime,
                fetchPreview,
                saveNode
            }
        }
    }
</script>

<style scoped>
    .node-editor-panel {
        height: 100%;
        padding: 16px;
        overflow-y: auto;
        background-color: var(--el-bg-color);
    }

    .node-title {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 16px;
    }

    .node-type-badge {
        background: var(--el-fill-color-blank);
        color: var(--el-color-primary);
        border: 1px solid var(--el-border-color-light);
        padding: 2px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }

    .node-name {
        color: var(--el-text-color-primary);
        font-size: 18px;
        font-weight: 600;
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

    .jump-section {
        border-top: 1px solid var(--el-border-color-light);
        padding-top: 12px;
        margin-top: 8px;
    }

    .jump-config {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding-left: 12px;
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
        flex: 1;
        display: flex;
        flex-direction: column;
        background: var(--el-bg-color);
        border: 1px solid var(--el-border-color-light);
        border-radius: 6px;
        padding: 8px;
        min-height: 90px;
    }

    .box-tag {
        font-size: 11px;
        color: var(--el-text-color-secondary);
        margin-bottom: 6px;
    }

    .realtime-img {
        max-width: 100%;
        max-height: 120px;
        object-fit: contain;
        border-radius: 4px;
    }

    .placeholder {
        content: "";
        color: var(--el-text-color-placeholder);
        font-size: 11px;
        text-align: center;
        margin: auto;
    }

    .realtime-text {
        font-size: 18px;
        font-weight: bold;
        color: #67C23A;
        margin: auto;
        word-break: break-all;
        text-align: center;
    }

        .realtime-text.empty {
            color: var(--el-text-color-placeholder);
            font-size: 12px;
        }

    .stat-box {
        align-items: center;
        justify-content: center;
    }

    .stat-score {
        font-size: 28px;
        font-weight: bold;
        color: #F56C6C;
        margin-bottom: 4px;
    }

        .stat-score.pass {
            color: var(--el-color-primary);
        }

    .stat-detail {
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 11px;
        color: var(--el-text-color-regular);
        text-align: center;
    }

    .save-actions {
        margin-top: 20px;
        display: flex;
        justify-content: flex-end;
    }

    .empty {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: var(--el-text-color-secondary);
    }
</style>