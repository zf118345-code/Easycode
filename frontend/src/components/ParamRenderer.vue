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
        </div>

        <!-- ⭐ 层级 1050 比截图蒙层(1000)高一级，保证遮罩与显示顺畅 -->
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
        components: { ScreenshotTool, FileBrowser },
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
                // 选择现有图片时清洗后缀
                const cleanPath = relPath.replace(/\.png$/i, '')
                localValue.value = cleanPath
                emitChange('file-select')
                browserVisible.value = false
            }

            const onTemplateCropSelected = (cropRect) => {
                pendingCropRect.value = cropRect
                openFileBrowser('save')
            }

            // ⭐ 彻底解决 test.png.png 的核心存盘逻辑
            const onFileSave = async ({ relativePath, fileName }) => {
                if (!pendingCropRect.value) {
                    return ElMessage.error('缺少截图框选数据')
                }
                try {
                    // 双重正则彻底剥离文件名和相对路径中的 .png 后缀
                    const cleanFileName = fileName.trim().replace(/\.png$/i, '')
                    const cleanRelPath = relativePath ? relativePath.replace(/\.png$/i, '') : ''

                    // 拼接最纯净的 key 路径（例如 "EnterPage/test"）
                    const fullTemplateName = cleanRelPath ? `${cleanRelPath}/${cleanFileName}` : cleanFileName

                    // 1. 请求后端剪裁图片
                    await axios.post('/api/screenshot/crop', {
                        project_path: projectPath.value,
                        template_name: fullTemplateName,
                        crop_rect: pendingCropRect.value
                    })

                    // 2. 将纯净的路径赋给输入框
                    localValue.value = fullTemplateName
                    emitChange('screenshot-saved')
                    ElMessage.success(`模板图片 [${fullTemplateName}] 保存成功`)

                    // 3. 一并关闭对话框和底部的截图蒙层
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
                handleSubUpdate
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
        color: #cfd3e6;
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
        color: #8a8fa8;
        font-weight: 500;
        min-width: 14px;
    }

    .coord-item .el-input-number {
        width: 70px;
    }

    .dict-container {
        padding-left: 12px;
        border-left: 2px solid #3d3d5a;
        margin-top: 4px;
    }
    .field-tip {
        font-size: 11px;
        color: #8a8fa8;
        margin-top: 4px;
        line-height: 1.2;
    }
</style>