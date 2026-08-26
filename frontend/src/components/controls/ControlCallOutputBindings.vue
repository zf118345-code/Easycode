<template>
    <div class="binding-editor">
        <div v-for="(binding, index) in rows" :key="index" class="binding-row">
            <el-select
                :model-value="binding.output_id"
                filterable
                allow-create
                placeholder="函数输出"
                @update:model-value="updateRow(index, 'output_id', $event)">
                <el-option v-for="item in declarations" :key="item.output_id" :label="`${item.name}${item.type ? ` (${item.type})` : ''}`" :value="item.output_id" />
            </el-select>
            <el-input
                :model-value="binding.target"
                placeholder="写回 $var.name / $ctx.name"
                @update:model-value="updateRow(index, 'target', $event)" />
            <el-button text type="danger" title="删除绑定" @click="removeRow(index)"><X :size="14" /></el-button>
        </div>
        <el-button size="small" plain @click="addRow"><Plus :size="14" /> 添加输出绑定</el-button>
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
const declarations = computed(() => targetFunction.value?.outputs || [])
const commit = (next) => emit('update:modelValue', next)
const addRow = () => commit([...rows.value, { output_id: '', target: '' }])
const removeRow = (index) => commit(rows.value.filter((_, rowIndex) => rowIndex !== index))
const updateRow = (index, key, value) => commit(rows.value.map((row, rowIndex) => rowIndex === index ? { ...row, [key]: value } : row))
</script>

<style scoped>
.binding-editor { display: flex; flex-direction: column; width: 100%; gap: 6px; }
.binding-row { display: grid; grid-template-columns: minmax(110px, .8fr) minmax(150px, 1.4fr) 28px; gap: 6px; }
</style>
