<!-- frontend/src/components/inspector/controls/VariableInputControl.vue -->
<template>
    <div class="variable-input-control">
        <el-select :model-value="modelValue"
                   :placeholder="config.placeholder || '选择已有变量或直接输入常数'"
                   size="small"
                   filterable
                   allow-create
                   default-first-option
                   clearable
                   class="var-select-full"
                   @change="handleSelectChange"
                   @update:model-value="val => $emit('update:model-value', val)">
            <el-option v-for="item in availableVariables"
                       :key="item.value"
                       :label="item.label"
                       :value="item.value">
                <div class="var-option-item">
                    <span class="type-badge" :class="`type-${item.type}`">{{ item.typeLabel }}</span>
                    <span class="var-name">{{ item.value }}</span>
                </div>
            </el-option>
            <template #empty>
                <div class="empty-vars-hint">
                    <span>暂无预设变量，可直接打字回车输入常数，或在变量面板新建</span>
                </div>
            </template>
        </el-select>
    </div>
</template>

<script setup>
    import { computed } from 'vue'
    import { useMainStore } from '@/stores'

    const props = defineProps({
        config: { type: Object, default: () => ({}) },
        modelValue: { type: [String, Number, Boolean, Array, Object], default: '' },
        label: { type: String, default: '' },
        context: { type: Object, default: () => ({}) }
    })

    const emit = defineEmits(['update:model-value', 'auto-change-type'])
    const store = useMainStore()

    const getVarTypeInfo = (val) => {
        if (typeof val === 'boolean') return { type: 'boolean', label: 'BOOL' }
        if (typeof val === 'number') return { type: 'number', label: 'NUM' }
        if (Array.isArray(val)) return { type: 'list', label: 'LIST' }
        if (typeof val === 'object' && val !== null) return { type: 'dict', label: 'DICT' }
        return { type: 'string', label: 'STR' }
    }

    const availableVariables = computed(() => {
        const varsObj = store.blueprint?.variables || {}
        return Object.keys(varsObj).map(key => {
            const val = varsObj[key]
            const typeInfo = getVarTypeInfo(val)
            return {
                value: key,
                label: `${key} (${typeInfo.label})`,
                type: typeInfo.type,
                typeLabel: typeInfo.label
            }
        })
    })

    const handleSelectChange = (val) => {
        emit('update:model-value', val)
        const selectedOpt = availableVariables.value.find(item => item.value === val)
        if (selectedOpt) {
            emit('auto-change-type', selectedOpt.type)
        }
    }
</script>

<style scoped>
    .variable-input-control {
        width: 100%;
    }

    .var-select-full {
        width: 100%;
    }

    .var-option-item {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .type-badge {
        font-size: 9px;
        font-weight: bold;
        padding: 1px 4px;
        border-radius: 3px;
        color: #fff;
        line-height: 1.2;
    }

    .type-number {
        background: #409eff;
    }

    .type-string {
        background: #67c23a;
    }

    .type-boolean {
        background: #e6a23c;
    }

    .type-list {
        background: #909399;
    }

    .type-dict {
        background: #f56c6c;
    }

    .var-name {
        font-size: 12px;
        color: var(--el-text-color-primary);
    }

    .empty-vars-hint {
        padding: 12px;
        font-size: 11px;
        color: var(--el-text-color-placeholder);
        text-align: center;
        white-space: normal;
        line-height: 1.5;
    }
</style>