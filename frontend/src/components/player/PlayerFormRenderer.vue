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
                    <div v-if="isFieldVisible(field)" class="form-field-row">
                        <div class="field-label-box">
                            <span class="field-label-text">{{ field.label }}</span>
                            <span v-if="field.help" class="field-help-icon" :title="field.help">❓</span>
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
                                <el-input-number v-model="formModel[field.target]"
                                                 :min="field.min !== undefined ? field.min : 0"
                                                 :max="field.max !== undefined ? field.max : 99999"
                                                 size="small"
                                                 controls-position="right"
                                                 style="width: 100%;"
                                                 @change="emitChange" />
                            </template>

                            <!-- 4. 滑块 slider -->
                            <template v-else-if="field.ui_type === 'slider'">
                                <div class="slider-wrapper">
                                    <el-slider v-model="formModel[field.target]"
                                               :min="field.min !== undefined ? field.min : 0"
                                               :max="field.max !== undefined ? field.max : 100"
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

                            <!-- 6. 默认字符串输入 str -->
                            <template v-else>
                                <el-input v-model="formModel[field.target]" :placeholder="field.placeholder || ''" @input="emitChange" />
                            </template>
                        </div>
                    </div>
                </template>
            </div>
        </div>
    </div>
</template>

<script setup>
    import { ref, reactive, watch, onMounted } from 'vue'
    import axios from 'axios'

    const props = defineProps({
        schema: { type: Object, required: true },
        userConfig: { type: Object, default: () => ({ vars: {}, ctx: {}, env: {} }) }
    })

    const emit = defineEmits(['change'])

    // 全寻址状态池表单模型：{"$var.account": "zhangsan", "$env.target_window_title": "弹弹堂"}
    const formModel = reactive({})
    const providerOptionsMap = reactive({})

    // 格式化 Target 读取内部存储值
    const getValueByTarget = (target, defaultVal) => {
        if (!target) return defaultVal
        if (target.startswith && target.startswith('$var.')) {
            const k = target.substring(5)
            return props.userConfig.vars?.[k] ?? defaultVal
        }
        if (target.startswith && target.startswith('$ctx.')) {
            const k = target.substring(5)
            return props.userConfig.ctx?.[k] ?? defaultVal
        }
        if (target.startswith && target.startswith('$env.')) {
            const k = target.substring(5)
            return props.userConfig.env?.[k] ?? defaultVal
        }
        return defaultVal
    }

    // 初始化模型数据并拉取 Provider
    const initFormModel = () => {
        const groups = props.schema?.groups || []
        groups.forEach(group => {
            (group.fields || []).forEach(field => {
                const target = field.target
                if (target) {
                    const initialVal = getValueByTarget(target, field.default)
                    formModel[target] = initialVal
                }
                if (field.provider) {
                    fetchProviderData(field.provider)
                }
            })
        })
    }

    const fetchProviderData = async (providerKey) => {
        try {
            const res = await axios.get('/api/player/providers', { params: { provider: providerKey } })
            providerOptionsMap[providerKey] = res.data?.options || []
        } catch (err) {
            console.error(`获取 Provider [${providerKey}] 失败`, err)
            providerOptionsMap[providerKey] = []
        }
    }

    const getOptions = (field) => {
        if (field.provider && providerOptionsMap[field.provider]) {
            return providerOptionsMap[field.provider]
        }
        return field.options || []
    }

    // 判定 visible_if 条件
    const isFieldVisible = (field) => {
        const rule = field.visible_if
        if (!rule || !rule.field && !rule.target) return true

        const targetKey = rule.target || (rule.field.startsWith('$') ? rule.field : `$var.${rule.field}`)
        const currentVal = formModel[targetKey]

        const op = rule.operator || 'eq'
        const expectedVal = rule.value

        if (op === 'eq') return currentVal === expectedVal
        if (op === 'ne') return currentVal !== expectedVal
        if (op === 'contains') return Array.isArray(currentVal) && currentVal.includes(expectedVal)
        if (op === 'in') return Array.isArray(expectedVal) && expectedVal.includes(currentVal)

        return true
    }

    const emitChange = () => {
        // 解构序列化出标准的 {"vars": {}, "ctx": {}, "env": {}} 结构
        const result = { vars: {}, ctx: {}, env: {} }
        Object.keys(formModel).forEach(target => {
            const val = formModel[target]
            if (target.startsWith('$var.')) {
                result.vars[target.substring(5)] = val
            } else if (target.startsWith('$ctx.')) {
                result.ctx[target.substring(5)] = val
            } else if (target.startsWith('$env.')) {
                result.env[target.substring(5)] = val
            }
        })
        emit('change', result)
    }

    watch(() => props.schema, initFormModel, { deep: true, immediate: true })
    onMounted(initFormModel)
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
        font-size: 11px;
        opacity: 0.7;
    }

    .field-control-box {
        flex: 1;
        display: flex;
        justify-content: flex-end;
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
</style>