<!-- frontend/src/components/player/PlayerFormRenderer.vue -->
<template>
    <div class="player-form-renderer">
        <div v-for="(group, gIdx) in schema.groups" :key="gIdx" class="form-group-card">
            <div v-if="group.group_title" class="group-header-title">
                <span>{{ group.group_title }}</span>
            </div>

            <div class="fields-container">
                <template v-for="field in group.fields" :key="field.target">
                    <!-- 动态计算显隐 visible_if -->
                    <div v-if="isFieldVisible(field)" class="form-field-row" :class="{ 'is-error': errorFor(field.target) }">
                        <div class="field-label-box">
                            <span class="field-label-text">{{ field.label }}<i v-if="field.required" class="required-mark">*</i></span>
                            <CircleHelp v-if="field.help" class="field-help-icon" :size="14" :title="field.help" />
                        </div>

                        <div class="field-control-box">
                            <!-- 1. 多选框组 checkbox_group -->
                            <template v-if="field.ui_type === 'checkbox_group'">
                                <el-checkbox-group v-model="formModel[field.target]" @change="emitChange">
                                    <el-checkbox v-for="opt in getOptions(field)" :key="opt.value" :value="opt.value">
                                        {{ opt.label }}
                                    </el-checkbox>
                                </el-checkbox-group>
                            </template>

                            <!-- 2. 下拉选择 select -->
                            <template v-else-if="field.ui_type === 'select'">
                                <el-select v-model="formModel[field.target]" placeholder="请选择" style="width: 100%;" @change="emitChange">
                                    <el-option v-for="opt in getOptions(field)" :key="opt.value" :label="opt.label" :value="opt.value" />
                                </el-select>
                            </template>

                            <!-- 3. 数字微调 number -->
                            <template v-else-if="field.ui_type === 'number'">
                                <el-input-number
v-model="formModel[field.target]"
                                                 :min="field.min !== undefined ? field.min : 0"
                                                 :max="field.max !== undefined ? field.max : 99999"
                                                 :step="field.step || 1"
                                                 size="small"
                                                 controls-position="right"
                                                 style="width: 100%;"
                                                 @change="emitChange" />
                            </template>

                            <!-- 4. 滑块 slider -->
                            <template v-else-if="field.ui_type === 'slider'">
                                <div class="slider-wrapper">
                                    <el-slider
v-model="formModel[field.target]"
                                               :min="field.min !== undefined ? field.min : 0"
                                               :max="field.max !== undefined ? field.max : 100"
                                               :step="field.step || 1"
                                               size="small"
                                               style="flex: 1;"
                                               @change="emitChange" />
                                    <span class="slider-val-badge">{{ formModel[field.target] }}{{ field.suffix || '' }}</span>
                                </div>
                            </template>

                            <!-- 5. 逻辑开关 switch -->
                            <template v-else-if="field.ui_type === 'switch'">
                                <el-switch v-model="formModel[field.target]" @change="emitChange" />
                            </template>

                            <template v-else-if="field.ui_type === 'image_asset'">
                                <div class="image-asset-control">
                                    <img v-if="String(formModel[field.target] || '').startsWith('data:image/')" :src="formModel[field.target]" alt="Player 截图" />
                                    <div v-else class="image-asset-name"><ImageIcon :size="15" /> {{ formModel[field.target] || '未设置图片' }}</div>
                                    <el-button size="small" @click="openImageCapture(field)"><Camera :size="14" /> 截图/更换</el-button>
                                </div>
                            </template>

                            <!-- 6. 字符串/密码输入 -->
                            <template v-else>
                                <el-input
                                    v-model="formModel[field.target]"
                                    :type="field.ui_type === 'secret' ? 'password' : 'text'"
                                    :show-password="field.ui_type === 'secret'"
                                    :placeholder="field.placeholder || ''"
                                    @input="emitChange" />
                            </template>
                            <div v-if="errorFor(field.target)" class="field-error">{{ errorFor(field.target) }}</div>
                        </div>
                    </div>
                </template>
            </div>
        </div>
        <PlayerImageCaptureDialog
            v-model="imageCaptureVisible"
            :title="activeImageField ? `更换：${activeImageField.label}` : '更换识别图片'"
            @confirm="applyCapturedImage" />
    </div>
</template>

<script setup>
    import { ref, reactive, watch } from 'vue'
    import { Camera, CircleHelp, Image as ImageIcon } from 'lucide-vue-next'
    import client from '@/api/client'
    import PlayerImageCaptureDialog from './PlayerImageCaptureDialog.vue'
    import {
        buildPlayerConfig,
        isPlayerFieldVisible,
        normalizeOption,
        normalizePlayerSchema,
        targetSlot,
        validatePlayerConfig
    } from '@/utils/playerSchema'

    const props = defineProps({
        schema: { type: Object, required: true },
        userConfig: { type: Object, default: () => ({ vars: {}, ctx: {}, overrides: {} }) }
    })

    const emit = defineEmits(['change'])

    // 全寻址状态池表单模型：{"$var.account": "zhangsan", "$ctx.window_title": "弹弹堂"}
    const formModel = reactive({})
    const providerOptionsMap = reactive({})
    const validationErrors = ref([])
    const imageCaptureVisible = ref(false)
    const activeImageField = ref(null)

    // 初始化模型数据并拉取 Provider
    const initFormModel = () => {
        Object.keys(formModel).forEach(key => delete formModel[key])
        const schema = normalizePlayerSchema(props.schema)
        const config = buildPlayerConfig(schema, props.userConfig)
        const groups = schema.groups || []
        groups.forEach(group => {
            (group.fields || []).forEach(field => {
                const target = field.target
                if (target) {
                    const [slot, key] = targetSlot(target)
                    if (slot) formModel[target] = config[slot][key]
                }
                if (field.provider) {
                    fetchProviderData(field.provider)
                }
            })
        })
    }

    const fetchProviderData = async (providerKey) => {
        try {
            const res = await client.get('/api/player/providers', { params: { provider: providerKey } })
            const raw = res?.data || res
            providerOptionsMap[providerKey] = raw?.options || []
        } catch (err) {
            console.error(`获取 Provider [${providerKey}] 失败`, err)
            providerOptionsMap[providerKey] = []
        }
    }

    const getOptions = (field) => {
        if (field.provider && providerOptionsMap[field.provider]) {
            return providerOptionsMap[field.provider].map(normalizeOption)
        }
        return (field.options || []).map(normalizeOption)
    }

    // 判定 visible_if 条件
    const isFieldVisible = (field) => {
        return isPlayerFieldVisible(field, formModel)
    }

    const getConfig = () => {
        const result = { vars: {}, ctx: {}, overrides: {} }
        Object.keys(formModel).forEach(target => {
            const val = formModel[target]
            const [slot, key] = targetSlot(target)
            if (slot) result[slot][key] = val
        })
        return result
    }

    const openImageCapture = field => {
        activeImageField.value = field
        imageCaptureVisible.value = true
    }

    const applyCapturedImage = dataUrl => {
        if (!activeImageField.value) return
        formModel[activeImageField.value.target] = dataUrl
        emitChange()
    }

    const emitChange = () => {
        validationErrors.value = []
        const result = getConfig()
        emit('change', result)
    }

    const validate = () => {
        validationErrors.value = validatePlayerConfig(props.schema, getConfig())
        return { valid: validationErrors.value.length === 0, errors: validationErrors.value, config: getConfig() }
    }

    const errorFor = (target) => validationErrors.value.find(item => item.target === target)?.message || ''

    watch(() => props.schema, initFormModel, { deep: true, immediate: true })
    defineExpose({ validate, getConfig })
</script>

<style scoped>
    .player-form-renderer {
        display: flex;
        flex-direction: column;
        gap: 12px;
        width: 100%;
    }

    .form-group-card {
        background: var(--el-bg-color);
        border: 1px solid var(--el-border-color-light);
        border-radius: var(--app-radius-md, 8px);
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    .group-header-title {
        font-size: 13px;
        font-weight: bold;
        color: var(--el-color-primary);
        padding-bottom: 6px;
        border-bottom: 1px solid var(--el-border-color-light);
    }

    .fields-container {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    .form-field-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
    }

    .field-label-box {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 12px;
        color: var(--el-text-color-primary);
        font-weight: 500;
        width: 140px;
        flex-shrink: 0;
    }

    .field-help-icon {
        cursor: help;
        opacity: 0.7;
    }

    .field-control-box {
        flex: 1;
        display: flex;
        justify-content: flex-end;
        flex-direction: column;
    }

    .slider-wrapper {
        display: flex;
        align-items: center;
        gap: 10px;
        width: 100%;
    }

    .slider-val-badge {
        font-size: 11px;
        font-weight: bold;
        color: var(--el-color-primary);
        min-width: 36px;
        text-align: right;
    }

    .image-asset-control { display: flex; align-items: center; gap: 8px; min-width: 0; }
    .image-asset-control img { width: 54px; height: 38px; object-fit: cover; border-radius: 5px; border: 1px solid var(--el-border-color); }
    .image-asset-name { flex: 1; min-width: 0; display: flex; align-items: center; gap: 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; color: var(--el-text-color-secondary); }

    .required-mark {
        color: var(--el-color-danger);
        font-style: normal;
        margin-left: 2px;
    }

    .field-error {
        color: var(--el-color-danger);
        font-size: 11px;
        margin-top: 4px;
    }

    .form-field-row.is-error :deep(.el-input__wrapper),
    .form-field-row.is-error :deep(.el-select__wrapper) {
        box-shadow: 0 0 0 1px var(--el-color-danger) inset;
    }
</style>
