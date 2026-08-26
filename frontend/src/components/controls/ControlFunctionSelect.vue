<template>
    <div class="function-select-control">
        <el-select :model-value="modelValue" filterable clearable placeholder="选择函数" @update:model-value="$emit('update:modelValue', $event)">
            <el-option v-for="item in callableFunctions" :key="item.function_id" :label="item.name" :value="item.function_id">
                <div class="function-option"><span>{{ item.name }}</span><small>{{ (item.parameters || []).length }} 入 · {{ (item.outputs || []).length }} 出</small></div>
            </el-option>
        </el-select>
        <button type="button" class="view-function-button" :disabled="!selectedFunction" :title="selectedFunction ? `打开函数：${selectedFunction.name}` : '请先选择函数'" @click="viewFunction"><ExternalLink /><span>查看</span></button>
    </div>
</template>
<script setup>
import { computed } from 'vue'
import { useIdeStore } from '@/stores'
import { ExternalLink } from 'lucide-vue-next'
import { notifyActionError } from '@/utils/userActionErrors'
const props = defineProps({ modelValue: { type: String, default: '' } })
defineEmits(['update:modelValue'])
const store = useIdeStore()
const callableFunctions = computed(() => (store.blueprint?.functions || []).filter(item => item.function_id !== store.currentTaskId))
const selectedFunction = computed(() => callableFunctions.value.find(item => item.function_id === props.modelValue) || null)
const viewFunction = async () => {
    if (!selectedFunction.value) return
    try {
        await store.navigateToGraph('function', selectedFunction.value.function_id)
        store.setFocusTarget({ type: 'graph', id: selectedFunction.value.function_id, timestamp: Date.now() })
    } catch (error) {
        notifyActionError(error, '无法打开函数')
    }
}
</script>
<style scoped>
.function-select-control{width:100%;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px}.view-function-button{height:32px;padding:0 9px;border:1px solid var(--el-border-color);border-radius:7px;display:flex;align-items:center;gap:5px;color:var(--el-text-color-regular);background:var(--el-fill-color-blank);font-size:11px;cursor:pointer}.view-function-button:hover:not(:disabled){border-color:var(--el-color-primary);color:var(--el-color-primary);background:var(--el-color-primary-light-9)}.view-function-button:disabled{opacity:.45;cursor:not-allowed}.view-function-button svg{width:13px;height:13px}.function-option{display:flex;align-items:center;gap:10px}.function-option span{flex:1}.function-option small{color:var(--app-text-placeholder);font-size:10px}
</style>
