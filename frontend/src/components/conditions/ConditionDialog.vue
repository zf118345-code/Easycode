<!-- frontend/src/components/conditions/ConditionDialog.vue -->
<template>
    <el-dialog
v-model="dialogVisible"
               width="560px"
               append-to-body
               destroy-on-close
               :close-on-click-modal="false"
               custom-class="condition-dialog-custom">
        <template #title>
            <Settings v-if="isBranch" :size="16" style="vertical-align: middle;" />
            <Plus v-else :size="16" style="vertical-align: middle;" />
            {{ isBranch ? '设置分流条件分支' : '设置判定条件' }}
        </template>
        <div class="condition-form-body">
            <!-- 1. 条件类别切换 (5大判定场景) -->
            <div class="type-selector-item">
                <span class="selector-label">条件判定类型</span>
                <el-select
v-model="activeConditionType"
                           placeholder="请选择条件类型"
                           style="width: 100%"
                           @change="handleTypeChange">
                    <el-option label="屏幕/区域存在指定图片" value="image_exists" />
                    <el-option label="屏幕/区域包含指定文本 (OCR)" value="text_contains" />
                    <el-option label="变量数值/逻辑比较" value="variable_check" />
                    <el-option label="指定窗口状态 (存在/激活/关闭)" value="window_state" />
                    <el-option label="本地文件/文件夹是否存在" value="file_exists" />
                </el-select>
            </div>

            <!-- 2. Schema 驱动的通用原子控件分发表单 -->
            <div class="schema-rendered-container">
                <template v-for="(config, paramName) in currentParamsSchema" :key="paramName">
                    <!-- 灰度阈值滑块定制优化 -->
                    <div
v-if="paramName === 'gray_threshold' && conditionPayload.gray_scale"
                         class="param-item-wrapper slider-box">
                        <div class="slider-header">
                            <span>二值化灰度阈值: <strong>{{ conditionPayload.gray_threshold ?? 127 }}</strong></span>
                            <span class="slider-tip">(向左增强浅色，向右过滤背景)</span>
                        </div>
                        <el-slider
v-model="conditionPayload.gray_threshold"
                                   :min="0"
                                   :max="255"
                                   :step="1"
                                   @input="val => handleParamChange('gray_threshold', val)" />
                    </div>

                    <!-- 统一原子控件渲染 -->
                    <div v-else-if="paramName !== 'gray_threshold'" class="param-item-wrapper">
                        <ParamRenderer
:config="config"
                                       :value="conditionPayload[paramName]"
                                       :label="config.label || paramName"
                                       :context="conditionPayload"
                                       @update="val => handleParamChange(paramName, val)"
                                       @open-browser="mode => $emit('open-browser', mode)"
                                       @open-screenshot="mode => $emit('open-screenshot', mode)" />
                    </div>
                </template>
            </div>
        </div>

        <template #footer>
            <div class="dialog-footer">
                <el-button @click="dialogVisible = false">取消</el-button>
                <el-button type="primary" @click="handleSave">确认保存</el-button>
            </div>
        </template>
    </el-dialog>
</template>

<script setup>
    import { ref, computed, watch } from 'vue'
    import ParamRenderer from '@/components/ParamRenderer.vue'
    import { CONDITION_SCHEMAS } from './conditionSchemas.js'
    import { useMainStore } from '@/stores'
    import { visionApi } from '@/api/visionApi'
    import { ElMessage } from 'element-plus'
    import { Settings, Plus } from 'lucide-vue-next'

    const props = defineProps({
        visible: { type: Boolean, default: false },
        showJumpConfig: { type: Boolean, default: false },
        initialData: { type: Object, default: null }
    })

    const emit = defineEmits(['update:visible', 'save', 'open-browser', 'open-screenshot'])
    const store = useMainStore()

    const dialogVisible = computed({
        get: () => props.visible,
        set: (val) => emit('update:visible', val)
    })

    const isBranch = computed(() => props.showJumpConfig)
    const activeConditionType = ref('image_exists')
    const conditionPayload = ref({})

    const currentParamsSchema = computed(() => {
        return CONDITION_SCHEMAS[activeConditionType.value]?.params || {}
    })

    const initDefaultPayload = (type) => {
        const schema = CONDITION_SCHEMAS[type]?.params || {}
        const payload = { condition_type: type }
        Object.keys(schema).forEach(key => {
            payload[key] = schema[key].default
        })
        return payload
    }

    const handleTypeChange = (newType) => {
        conditionPayload.value = initDefaultPayload(newType)
    }

    const autoFillRecordedRegion = async (imageSource) => {
        const projectPath = store.currentProjectPath || ''
        if (!imageSource || !projectPath) return

        try {
            const res = await visionApi.getRegions(projectPath)
            const regions = res?.data || res || {}

            const cleanKey = imageSource.replace(/\\/g, '/').split('/').pop().replace(/\.(png|jpg|jpeg)$/i, '')
            const recordedBox = regions[cleanKey] || regions[imageSource] || regions[`${cleanKey}.png`]

            if (Array.isArray(recordedBox) && recordedBox.length >= 4) {
                const targetBox = [...recordedBox]
                conditionPayload.value.region_value = targetBox
                conditionPayload.value.crop_rect = targetBox
                conditionPayload.value.region = targetBox

                ElMessage.success(`已自动带入图片 [${cleanKey}] 录制坐标: [${targetBox.join(', ')}]`)
            } else {
                conditionPayload.value.region_value = [0, 0, 0, 0]
                conditionPayload.value.crop_rect = [0, 0, 0, 0]
                conditionPayload.value.region = [0, 0, 0, 0]
                ElMessage.warning(`未找到图片 [${cleanKey}] 的录制坐标，已重置为 [0,0,0,0]`)
            }

            conditionPayload.value = { ...conditionPayload.value }
        } catch (err) {
            console.error('获取录制坐标失败:', err)
        }
    }

    const handleParamChange = async (paramName, val) => {
        conditionPayload.value[paramName] = val

        const isRecordedMode = (paramName === 'region_type' || paramName === 'match_mode') && val === 'recorded'
        const isImageChangeInRecordedMode = paramName === 'image_source' && (conditionPayload.value.region_type === 'recorded' || conditionPayload.value.match_mode === 'recorded')

        if (isRecordedMode || isImageChangeInRecordedMode) {
            await autoFillRecordedRegion(conditionPayload.value.image_source)
        }

        conditionPayload.value = { ...conditionPayload.value }
    }

    watch(() => props.visible, (val) => {
        if (val) {
            if (props.initialData) {
                const initCond = props.initialData.condition || props.initialData
                activeConditionType.value = initCond.condition_type || 'image_exists'
                conditionPayload.value = JSON.parse(JSON.stringify(initCond))
            } else {
                activeConditionType.value = 'image_exists'
                conditionPayload.value = initDefaultPayload('image_exists')
            }
        }
    })

    const handleSave = () => {
        emit('save', {
            condition: conditionPayload.value,
            on_success: props.initialData?.on_success || {}
        })
        dialogVisible.value = false
    }
</script>

<style scoped>
    .condition-form-body {
        display: flex;
        flex-direction: column;
        gap: 14px;
        max-height: 65vh;
        overflow-y: auto;
        padding-right: 4px;
    }

    .type-selector-item {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .selector-label {
        font-size: 13px;
        font-weight: 600;
        color: var(--el-text-color-primary);
    }

    .schema-rendered-container {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .param-item-wrapper {
        width: 100%;
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

    .dialog-footer {
        display: flex;
        justify-content: flex-end;
        gap: 10px;
    }
</style>