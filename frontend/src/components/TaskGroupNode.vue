<template>
    <div class="task-group-node" :class="{ selected: isSelected }">
        <!-- 顶部断开嵌入的标题：作为拖拽整个组的 Handle -->
        <div class="group-title-badge custom-drag-handle" @click="onTitleClick">
            📁 {{ label }}
        </div>
    </div>
</template>

<script>
    import { computed } from 'vue'

    export default {
        name: 'TaskGroupNode',
        props: {
            id: String,
            data: Object,
            selected: Boolean
        },
        setup(props, { emit }) {
            const label = computed(() => props.data?.label || '任务组')
            const isSelected = computed(() => props.selected)

            const onTitleClick = () => {
                // 点击标题时触发组选中
            }

            return {
                label,
                isSelected,
                onTitleClick
            }
        }
    }
</script>

<style scoped>
    .task-group-node {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        box-sizing: border-box;
        border: 2px dashed #4ed19c;
        border-radius: 12px;
        background: rgba(78, 209, 156, 0.02);
        /* ⭐ 核心：虚线框本身绝不响应任何鼠标事件，让点击直接穿透到背后的画布或子节点 */
        pointer-events: none;
        transition: border-color 0.2s, background-color 0.2s;
        z-index: -1;
    }

    /* 顶部标题栏恢复鼠标响应，并指定为拖拽把手 */
    .group-title-badge {
        position: absolute;
        top: -14px;
        left: 20px;
        background: var(--el-bg-color-page);
        padding: 3px 12px;
        color: #4ed19c;
        font-weight: bold;
        font-size: 12px;
        border: 1px dashed #4ed19c;
        border-radius: 6px;
        /* ⭐ 核心：只有标题允许交互，且可以通过自定义类名让 Vue Flow 识别为拖拽柄 */
        pointer-events: auto;
        cursor: grab;
        user-select: none;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2);
    }

        .group-title-badge:active {
            cursor: grabbing;
        }

        .group-title-badge:hover {
            background: var(--el-fill-color-light);
            border-color: #5ce3aa;
        }

    .task-group-node.selected {
        border-color: #409EFF;
        background: rgba(64, 158, 255, 0.04);
    }

        .task-group-node.selected .group-title-badge {
            border-color: #409EFF;
            color: #409EFF;
        }
</style>