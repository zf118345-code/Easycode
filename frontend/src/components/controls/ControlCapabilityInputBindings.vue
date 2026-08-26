<template>
    <div class="binding-editor">
        <div v-for="(binding, index) in rows" :key="index" class="binding-row">
            <el-select
                :model-value="binding.name"
                filterable
                placeholder="能力输入"
                @update:model-value="updateRow(index, 'name', $event)">
                <el-option v-for="item in declarations" :key="item.name" :label="label(item)" :value="item.name" />
            </el-select>
            <el-input
                :model-value="binding.value"
                :placeholder="valuePlaceholder"
                @update:model-value="updateRow(index, 'value', $event)" />
            <el-button text type="danger" title="删除绑定" @click="removeRow(index)"><X :size="14" /></el-button>
        </div>
        <el-button size="small" plain :disabled="!declarations.length" @click="addRow"><Plus :size="14" /> 添加输入绑定</el-button>
        <div v-if="requiredMissing.length" class="binding-warning">尚未绑定必填输入：{{ requiredMissing.join('、') }}</div>
        <div v-if="selected?.description" class="capability-description">{{ selected.description }}</div>
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
const declarations = computed(() => selected.value?.inputs || [])
const valuePlaceholder = computed(() => store.canvasMode === 'function'
    ? '常量 / $param.name / $local.name / =表达式'
    : '常量 / $var.name / $ctx.name / =表达式')
const requiredMissing = computed(() => declarations.value
    .filter(item => item.required && item.default === undefined && !rows.value.some(row => row.name === item.name))
    .map(item => item.name))
const label = item => `${item.name}${item.type ? ` (${item.type})` : ''}${item.required ? ' *' : ''}`
const commit = next => emit('update:modelValue', next)
const addRow = () => {
    const unused = declarations.value.find(item => !rows.value.some(row => row.name === item.name))
    commit([...rows.value, { name: unused?.name || '', value: unused?.default ?? '' }])
}
const removeRow = index => commit(rows.value.filter((_, rowIndex) => rowIndex !== index))
const updateRow = (index, key, value) => commit(rows.value.map((row, rowIndex) => rowIndex === index ? { ...row, [key]: value } : row))
</script>

<style scoped>
.binding-editor { display: flex; flex-direction: column; width: 100%; gap: 6px; }
.binding-row { display: grid; grid-template-columns: minmax(110px, .8fr) minmax(150px, 1.4fr) 28px; gap: 6px; }
.binding-warning { color: var(--el-color-warning); font-size: 11px; }
.capability-description { color: var(--el-text-color-secondary); font-size: 11px; line-height: 1.5; }
</style>
