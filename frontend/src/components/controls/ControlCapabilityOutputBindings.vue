<template>
    <div class="binding-editor">
        <div v-for="(binding, index) in rows" :key="index" class="binding-row">
            <el-select
                :model-value="binding.source"
                filterable
                allow-create
                placeholder="能力输出"
                @update:model-value="updateRow(index, 'source', $event)">
                <el-option v-for="item in declarations" :key="item.name" :label="item.name" :value="item.name" />
            </el-select>
            <el-input
                :model-value="binding.target"
                :placeholder="targetPlaceholder"
                @update:model-value="updateRow(index, 'target', $event)" />
            <el-button text type="danger" title="删除映射" @click="removeRow(index)"><X :size="14" /></el-button>
        </div>
        <el-button size="small" plain :disabled="!selected" @click="addRow"><Plus :size="14" /> 添加结果映射</el-button>
    </div>
</template>

<script setup>
import { computed, onMounted, toRef } from 'vue'
import { Plus, X } from 'lucide-vue-next'
import { useIdeStore } from '@/stores'
import { useCapabilityCatalog } from '@/composables/useCapabilityCatalog'

const props = defineProps({
    modelValue: { type: Array, default: () => [] },
    context: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['update:modelValue'])
const store = useIdeStore()
const { capabilities, load } = useCapabilityCatalog(toRef(store, 'currentProjectPath'))
onMounted(() => load())
const rows = computed(() => Array.isArray(props.modelValue) ? props.modelValue : [])
const selected = computed(() => capabilities.value.find(item => item.id === props.context?.capability_id) || null)
const declarations = computed(() => selected.value?.outputs || [])
const targetPlaceholder = computed(() => store.canvasMode === 'function'
    ? '写入 $local.name / $var.name / $ctx.name'
    : '写入 $var.name / $ctx.name')
const commit = next => emit('update:modelValue', next)
const addRow = () => {
    const unused = declarations.value.find(item => !rows.value.some(row => row.source === item.name))
    commit([...rows.value, { source: unused?.name || '', target: '' }])
}
const removeRow = index => commit(rows.value.filter((_, rowIndex) => rowIndex !== index))
const updateRow = (index, key, value) => commit(rows.value.map((row, rowIndex) => rowIndex === index ? { ...row, [key]: value } : row))
</script>

<style scoped>
.binding-editor { display: flex; flex-direction: column; width: 100%; gap: 6px; }
.binding-row { display: grid; grid-template-columns: minmax(110px, .8fr) minmax(150px, 1.4fr) 28px; gap: 6px; }
</style>
