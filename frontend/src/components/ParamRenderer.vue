<template>
    <div v-if="isVisible" class="param-renderer">
        <!-- 标签 -->
        <div v-if="label" class="param-label">{{ label }}</div>

        <!-- 控件 -->
        <div class="param-control">
            <!-- str -->
            <template v-if="config.type === 'str'">
                <el-input v-model="localValue" :placeholder="config.label || ''" @change="emitChange" />
            </template>

            <!-- int -->
            <template v-else-if="config.type === 'int'">
                <el-input-number v-model="localValue"
                                 :min="config.min !== undefined ? config.min : 0"
                                 :max="config.max !== undefined ? config.max : Infinity"
                                 :step="config.step || 1"
                                 controls-position="right"
                                 @change="emitChange" />
            </template>

            <!-- float -->
            <template v-else-if="config.type === 'float'">
                <el-input-number v-model="localValue"
                                 :min="config.min !== undefined ? config.min : 0"
                                 :max="config.max !== undefined ? config.max : Infinity"
                                 :step="config.step || 0.1"
                                 :precision="2"
                                 controls-position="right"
                                 @change="emitChange" />
            </template>

            <!-- bool -->
            <template v-else-if="config.type === 'bool'">
                <el-switch v-model="localValue" @change="emitChange" />
            </template>

            <!-- select -->
            <template v-else-if="config.type === 'select'">
                <el-select v-model="localValue" :placeholder="config.label || '请选择'" @change="emitChange">
                    <el-option v-for="opt in resolvedOptions"
                               :key="opt.value"
                               :label="opt.label"
                               :value="opt.value" />
                </el-select>
            </template>

            <!-- file -->
            <template v-else-if="config.type === 'file'">
                <div class="file-selector">
                    <el-input :model-value="localValue" placeholder="请选择模板图片" readonly @click="openFileDialog">
                        <template #append>
                            <el-button @click="openFileDialog">📂 浏览</el-button>
                        </template>
                    </el-input>
                    <el-button type="success" size="small" @click="openScreenshot">📷 录入</el-button>
                </div>
            </template>

            <!-- list_int2 -->
            <template v-else-if="config.type === 'list_int2'">
                <div class="list-int2">
                    <div class="coord-item">
                        <span class="coord-label">X</span>
                        <el-input-number v-model="localValue[0]" :min="0" controls-position="right" size="small" @change="emitChange" />
                    </div>
                    <div class="coord-item">
                        <span class="coord-label">Y</span>
                        <el-input-number v-model="localValue[1]" :min="0" controls-position="right" size="small" @change="emitChange" />
                    </div>
                </div>
            </template>

            <!-- list_int4 -->
            <template v-else-if="config.type === 'list_int4'">
                <div class="list-int4">
                    <div class="coord-item">
                        <span class="coord-label">X</span>
                        <el-input-number v-model="localValue[0]" :min="0" controls-position="right" size="small" @change="emitChange" />
                    </div>
                    <div class="coord-item">
                        <span class="coord-label">Y</span>
                        <el-input-number v-model="localValue[1]" :min="0" controls-position="right" size="small" @change="emitChange" />
                    </div>
                    <div class="coord-item">
                        <span class="coord-label">W</span>
                        <el-input-number v-model="localValue[2]" :min="0" controls-position="right" size="small" @change="emitChange" />
                    </div>
                    <div class="coord-item">
                        <span class="coord-label">H</span>
                        <el-input-number v-model="localValue[3]" :min="0" controls-position="right" size="small" @change="emitChange" />
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
                                   @update="(val) => { if(!localValue) localValue = {}; localValue[subKey] = val; emitChange(); }" />
                </div>
            </template>
        </div>

        <!-- 对话框 -->
        <el-dialog v-model="browserVisible" title="选择模板图片" width="80%" top="5vh" append-to-body :close-on-click-modal="false">
            <FileBrowser ref="fileBrowserRef" :project-path="projectPath" @select="onFileSelected" @close="browserVisible = false" />
        </el-dialog>

        <ScreenshotTool ref="screenshotTool" @saved="onScreenshotSaved" />
    </div>
</template>

<script>
    import { ref, watch, onBeforeUnmount, computed, toRaw } from 'vue'
    import { ElMessage } from 'element-plus'
    import { useMainStore } from '@/stores'
    import ScreenshotTool from '@/components/ScreenshotTool.vue'
    import FileBrowser from '@/components/FileBrowser.vue'

    // 辅助函数：安全克隆对象，避免 Proxy 对象导致 structuredClone 报错
    function safeDeepClone(obj) {
        if (obj === null || typeof obj !== 'object') return obj
        try {
            // 先转为纯 JS 对象再序列化克隆，最安全稳定
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

            const getInitialValue = () => {
                const val = props.value
                if (props.config.type === 'list_int4') {
                    return Array.isArray(val) && val.length === 4 ? [...val] : [0, 0, 0, 0]
                } else if (props.config.type === 'list_int2') {
                    return Array.isArray(val) && val.length === 2 ? [...val] : [0, 0]
                } else if (props.config.type === 'dict') {
                    return val ? safeDeepClone(val) : {}
                }
                return val
            }

            const localValue = ref(getInitialValue())
            const screenshotTool = ref(null)
            const browserVisible = ref(false)

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

            const unwatch = watch(
                () => props.value,
                (newVal) => {
                    if (props.config.type === 'list_int4') {
                        localValue.value = Array.isArray(newVal) && newVal.length === 4 ? [...newVal] : [0, 0, 0, 0]
                    } else if (props.config.type === 'list_int2') {
                        localValue.value = Array.isArray(newVal) && newVal.length === 2 ? [...newVal] : [0, 0]
                    } else if (props.config.type === 'dict') {
                        // 安全克隆，切断响应式循环引用
                        localValue.value = newVal ? safeDeepClone(newVal) : {}
                    } else {
                        localValue.value = newVal
                    }
                },
                { immediate: true, deep: true }
            )

            const emitChange = () => emit('update', localValue.value)
            const openFileDialog = () => {
                if (!projectPath.value) return ElMessage.warning('请先打开项目')
                browserVisible.value = true
            }
            const onFileSelected = (relPath) => {
                localValue.value = relPath
                emitChange()
                browserVisible.value = false
            }
            const openScreenshot = () => { if (screenshotTool.value) screenshotTool.value.open() }
            const onScreenshotSaved = (templateName) => {
                if (templateName) {
                    localValue.value = templateName
                    emitChange()
                }
            }

            onBeforeUnmount(() => unwatch())

            return {
                localValue,
                screenshotTool,
                browserVisible,
                projectPath,
                isVisible,
                resolvedOptions,
                openFileDialog,
                onFileSelected,
                openScreenshot,
                onScreenshotSaved,
                emitChange
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
</style>