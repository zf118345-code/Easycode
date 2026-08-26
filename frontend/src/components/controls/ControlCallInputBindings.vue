<template>
    <div class="binding-editor">
        <div v-for="(binding, index) in rows" :key="index" class="binding-row">
            <el-select
                :model-value="binding.parameter_id"
                filterable
                allow-create
                placeholder="函数形参"
                @update:model-value="updateRow(index, 'parameter_id', $event)">
                <el-option v-for="item in declarations" :key="item.parameter_id" :label="declarationLabel(item)" :value="item.parameter_id" />
            </el-select>
            <el-input
                :model-value="binding.value"
                placeholder="常量 / $var.name / $ctx.name"
                @update:model-value="updateRow(index, 'value', $event)" />
            <el-button text type="danger" title="删除绑定" @click="removeRow(index)"><X :size="14" /></el-button>
        </div>
        <el-button size="small" plain @click="addRow"><Plus :size="14" /> 添加输入绑定</el-button>
        <div v-if="requiredMissing.length" class="binding-warning">
            尚未绑定必填输入：{{ requiredMissing.join('、') }}
        </div>
    </div>
</template>

<script setup>
import { computed } from 'vue'
import { useProjectStore } from '@/stores'
import { Plus, X } from 'lucide-vue-next'

const props = defineProps({
    modelValue: { type: Array, default: () => [] },
    context: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['update:modelValue'])
const projectStore = useProjectStore()
const rows = computed(() => Array.isArray(props.modelValue) ? props.modelValue : [])
const targetFunction = computed(() => projectStore.functions.find(item => item.function_id === props.context?.function_id))
const declarations = computed(() => targetFunction.value?.parameters || [])
const requiredMissing = computed(() => declarations.value
    .filter(item => item.required && item.default_value === undefined && !rows.value.some(row => row.parameter_id === item.parameter_id))
    .map(item => item.name))

const declarationLabel = (item) => `${item.name}${item.type ? ` (${item.type})` : ''}${item.required ? ' *' : ''}`
const commit = (next) => emit('update:modelValue', next)
const addRow = () => commit([...rows.value, { parameter_id: '', value: '' }])
const removeRow = (index) => commit(rows.value.filter((_, rowIndex) => rowIndex !== index))
const updateRow = (index, key, value) => {
    const next = rows.value.map((row, rowIndex) => rowIndex === index ? { ...row, [key]: value } : row)
    commit(next)
}
</script>

<style scoped>
.binding-editor { display: flex; flex-direction: column; width: 100%; gap: 6px; }
.binding-row { display: grid; grid-template-columns: minmax(100px, .8fr) minmax(150px, 1.4fr) 28px; gap: 6px; }
.binding-warning { color: var(--el-color-warning); font-size: 11px; }
</style>
