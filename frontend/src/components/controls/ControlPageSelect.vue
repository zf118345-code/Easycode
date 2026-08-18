<!-- frontend/src/components/controls/ControlPageSelect.vue
    目标页面下拉：从当前项目的拓扑地图中读取 page_state 节点（label=页面名、value=page_id），
    供 smart_jump 节点选择跳转目标。下拉展开时动态刷新，可过滤。
-->
<template>
    <el-select
        :model-value="modelValue"
        filterable
        default-first-option
        placeholder="请选择目标页面"
        style="width: 100%;"
        popper-class="page-select-popper"
        :loading="loading"
        @visible-change="onVisibleChange"
        @update:model-value="val => $emit('update:modelValue', val)">
        <el-option
            v-for="page in pageList"
            :key="page.page_id"
            :label="page.page_name"
            :value="page.page_id" />
        <template #empty>
            <span v-if="!loading" class="page-select-empty">拓扑地图中暂无页面，请先在拓扑画布添加页面状态节点</span>
        </template>
    </el-select>
</template>

<script setup>
    import { ref } from 'vue'
    import { useMainStore } from '@/stores'

    defineProps({
        config: { type: Object, default: () => ({}) },
        modelValue: { type: String, default: '' }
    })
    defineEmits(['update:modelValue'])

    const store = useMainStore()
    const pageList = ref([])
    const loading = ref(false)

    const fetchPages = () => {
        loading.value = true
        try {
            const topology = store.blueprint?.topology || {}
            const tasks = topology.tasks || []
            const pages = []
            for (const task of tasks) {
                for (const node of task.nodes || []) {
                    if (node?.node_type !== 'page_state') continue
                    const pageId = node.params?.page_id
                    if (!pageId) continue
                    pages.push({ page_id: pageId, page_name: node.node_name || pageId })
                }
            }
            pageList.value = pages
        } finally {
            loading.value = false
        }
    }

    const onVisibleChange = (visible) => {
        if (visible) {
            fetchPages()
        }
    }
</script>

<!-- ⚡ 仅约束下拉面板宽度与空态提示，绝不干扰输入框本体样式 -->
<style>
    .page-select-popper {
        max-width: 280px !important;
    }

    .page-select-popper .el-select-dropdown__item {
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        white-space: nowrap !important;
    }

    .page-select-empty {
        font-size: 12px;
        color: var(--el-text-color-secondary);
        padding: 4px 8px;
    }
</style>
