<template>
    <div class="capability-select">
        <el-select
            :model-value="modelValue"
            :loading="loading"
            filterable
            clearable
            placeholder="选择能力函数"
            style="width: 100%"
            @visible-change="opened => opened && load()"
            @update:model-value="$emit('update:modelValue', $event)">
            <el-option
                v-for="item in capabilities"
                :key="`${item.id}@${item.version}`"
                :label="`${item.name} · ${item.id}@${item.version}`"
                :value="item.id">
                <div class="option-line">
                    <span>{{ item.name }}</span>
                    <small>{{ item.id }}@{{ item.version }}</small>
                </div>
            </el-option>
        </el-select>
        <el-tooltip v-if="errors.length" :content="errors.map(item => item.message).join('\n')">
            <TriangleAlert class="catalog-warning" :size="16" />
        </el-tooltip>
        <el-button text title="重新扫描能力" @click="load(true)"><RefreshCw :size="15" /></el-button>
    </div>
</template>

<script setup>
import { onMounted, toRef, watch } from 'vue'
import { RefreshCw, TriangleAlert } from 'lucide-vue-next'
import { useIdeStore } from '@/stores'
import { useCapabilityCatalog } from '@/composables/useCapabilityCatalog'

defineProps({ modelValue: { type: String, default: '' } })
defineEmits(['update:modelValue'])
const store = useIdeStore()
const projectPath = toRef(store, 'currentProjectPath')
const { capabilities, errors, loading, load } = useCapabilityCatalog(projectPath)
onMounted(() => load())
watch(projectPath, () => load(true))
</script>

<style scoped>
.capability-select { display: flex; align-items: center; width: 100%; gap: 4px; }
.option-line { display: flex; justify-content: space-between; gap: 16px; }
.option-line small { color: var(--el-text-color-secondary); }
.catalog-warning { color: var(--el-color-warning); flex-shrink: 0; }
</style>
