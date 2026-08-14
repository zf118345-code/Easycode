<!-- frontend/src/components/controls/ControlWindowSelect.vue -->
<template>
    <el-select
:model-value="modelValue"
               filterable
               allow-create
               default-first-option
               placeholder="下拉选择或手动输入窗口标题"
               style="width: 100%;"
               popper-class="window-select-popper"
               :loading="loading"
               @visible-change="onVisibleChange"
               @update:model-value="val => $emit('update:modelValue', val)">
        <el-option
v-for="w in windowList"
                   :key="w.hwnd || w.title"
                   :label="w.title"
                   :value="w.title" />
    </el-select>
</template>

<script setup>
    import { ref } from 'vue'
    import { workspaceApi } from '@/api/workspaceApi'

    defineProps({
        config: { type: Object, default: () => ({}) },
        modelValue: { type: String, default: '' }
    })
    defineEmits(['update:modelValue'])

    const windowList = ref([])
    const loading = ref(false)

    const fetchWindows = async () => {
        loading.value = true
        try {
            const res = await workspaceApi.getWindows()
            windowList.value = res.windows || []
        } catch (err) {
            console.error('获取窗口列表失败:', err)
        } finally {
            loading.value = false
        }
    }

    const onVisibleChange = (visible) => {
        if (visible) {
            fetchWindows()
        }
    }
</script>

<!-- ⚡ 仅约束弹出窗口的最大宽度并实现超长文本省略（...），绝不干扰输入框本体样式 -->
<style>
    .window-select-popper {
        max-width: 280px !important;
    }

        .window-select-popper .el-select-dropdown__item {
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            white-space: nowrap !important;
        }
</style>