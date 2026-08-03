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

                    <!-- 其他通用组件 -->
                    <div v-else-if="!['region_value', 'gray_threshold', 'on_success', 'on_failure'].includes(paramName)"
                         class="param-item">
                        <ParamRenderer :key="paramName + store.selectedNodeId"
                                       :config="config"
                                       :value="store.selectedNode.params[paramName]"
                                       :label="config.label || paramName"
                                       :context="store.selectedNode.params"
                                       @update="(val) => handleParamUpdate(paramName, val)" />
                    </div>
                </template>

                <!-- ⭐⭐⭐ 2. 文字识别 (OCR) 实时调优卡片 -->
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

                <!-- ⭐⭐⭐ 3. 图像识别 实时调优卡片 -->
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

            const shouldShowRegionValue = computed(() => {
                const node = store.selectedNode
                if (!node || !node.params) return false
                const regionType = node.params.region_type
                return regionType === 'recorded' || regionType === 'custom'
            })

            const isMatchPass = computed(() => {
                const targetThreshold = store.selectedNode?.params?.threshold ?? 85
                return imageScore.value >= targetThreshold
            })

            const allParams = computed(() => paramDefs.value)

            const handleParamUpdate = (paramName, value) => {
                const node = store.selectedNode
                if (!node) return

                // 手动修改坐标时自动转为自定义模式
                if (paramName === 'region_value' && node.params.region_type === 'recorded' && !isSyncingRecorded) {
                    if (originalRecordedRegion.value && JSON.stringify(value) !== JSON.stringify(originalRecordedRegion.value)) {
                        node.params.region_type = 'custom'
                        ElMessage.info('检测到坐标手动微调，已自动切换为【自定义区域】模式')
                    }
                }

                node.params[paramName] = value
                node.params = { ...node.params }

                // ⭐⭐ 关键修复：当切换为 recorded 或改变模板图片时，强行触发录入坐标拉取
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

            // ⭐⭐ 关键修复：全方位多重 Key 比对拉取算法
            const syncRecordedRegion = async () => {
                const node = store.selectedNode
                if (!node || !store.currentProjectPath) return

                const rawTemplateName = node.params.image_source
                if (!rawTemplateName) {
                    ElMessage.warning('请先选择模板图片')
                    return
                }

                isSyncingRecorded = true

                try {
                    const res = await axios.get('/api/regions', {
                        params: { project_path: store.currentProjectPath }
                    })
                    const regions = res.data || {}

                    // 清洗各种可能的 key 格式（含/不含 .png，相对路径/纯文件名）
                    const cleanName = rawTemplateName.replace(/\.png$/i, '').replace(/\\/g, '/')
                    const fileNameOnly = cleanName.split('/').pop()

                    const rect = regions[rawTemplateName] ||
                        regions[cleanName] ||
                        regions[fileNameOnly] ||
                        regions[`${cleanName}.png`] ||
                        regions[`${fileNameOnly}.png`]

                    if (rect && Array.isArray(rect) && rect.length === 4) {
                        node.params.region_value = [...rect]
                        originalRecordedRegion.value = [...rect]
                        logger.info('NodeEditor', `✅ 成功回填录入坐标: [${rect}]`)
                        debounceRefreshRealtime()
                    } else {
                        node.params.region_value = [0, 0, 0, 0]
                        originalRecordedRegion.value = [0, 0, 0, 0]
                        ElMessage.warning(`未在 regions.json 中查找到图片 [${fileNameOnly}] 的保存坐标`)
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
                nodeTypeLabel,
                previewLoading,
                previewText,
                previewImg,
                imageScore,
                imageCenterPos,
                isMatchPass,
                handleParamUpdate,
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
    }

    .node-title {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 16px;
    }

    .node-type-badge {
        background: #409EFF;
        color: white;
        padding: 2px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
    }

    .node-name {
        color: #cfd3e6;
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

    .slider-box {
        background: #202030;
        padding: 10px 12px;
        border-radius: 6px;
        border: 1px solid #3d3d5a;
    }

    .slider-header {
        display: flex;
        justify-content: space-between;
        font-size: 12px;
        color: #cfd3e6;
        margin-bottom: 4px;
    }

    .slider-tip {
        color: #8a8fa8;
        font-size: 11px;
    }

    .interactive-preview-card {
        background: #181824;
        border: 1px solid #409EFF;
        border-radius: 6px;
        padding: 12px;
        margin-top: 4px;
    }

    .preview-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 13px;
        font-weight: bold;
        color: #409EFF;
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
        background: #09090d;
        border: 1px solid #2d2d3f;
        border-radius: 4px;
        padding: 8px;
        min-height: 90px;
    }

    .box-tag {
        font-size: 11px;
        color: #8a8fa8;
        margin-bottom: 6px;
    }

    .realtime-img {
        max-width: 100%;
        max-height: 120px;
        object-fit: contain;
        border-radius: 2px;
    }

    .placeholder {
        color: #5a5e72;
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
            color: #5a5e72;
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
            color: #67C23A;
        }

    .stat-detail {
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 11px;
        color: #a2a7c7;
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
        color: #8a8fa8;
    }
</style>