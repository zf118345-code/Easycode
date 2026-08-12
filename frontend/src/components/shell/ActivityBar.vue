<!-- frontend/src/components/shell/ActivityBar.vue -->
<template>
    <div class="activity-bar" :class="position">
        <el-tooltip v-for="item in items"
                    :key="item.id"
                    effect="dark"
                    :content="item.title"
                    placement="right"
                    :show-after="300"
                    popper-class="ide-sidebar-tooltip">
            <div class="activity-icon-item"
                 :class="{ 'is-active': activeId === item.id }"
                 @click="$emit('select', item.id)">
                <component :is="item.icon" class="act-svg" />
            </div>
        </el-tooltip>
    </div>
</template>

<script setup>
    defineProps({
        items: { type: Array, default: () => [] },
        activeId: { type: String, default: null },
        position: { type: String, default: 'left' } // left | right | bottom
    })

    defineEmits(['select'])
</script>

<style scoped>
    .activity-bar {
        background: #181926;
        display: flex;
        align-items: center;
        flex-shrink: 0;
        z-index: 50;
        user-select: none;
    }

        .activity-bar.left, .activity-bar.right {
            width: 40px;
            height: 100%;
            flex-direction: column;
            padding-top: 6px;
            gap: 4px;
        }

        .activity-bar.bottom {
            height: 40px;
            width: 100%;
            flex-direction: row;
            padding-left: 6px;
            gap: 4px;
        }

    .activity-icon-item {
        width: 32px;
        height: 32px;
        margin: 0 auto;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        color: var(--el-text-color-secondary);
        transition: all 0.2s ease;
    }

        .activity-icon-item:hover {
            background: var(--el-fill-color-light);
            color: var(--el-text-color-primary);
        }

        .activity-icon-item.is-active {
            background: rgba(78, 209, 156, 0.15);
            color: var(--el-color-primary);
        }

    .act-svg {
        width: 18px;
        height: 18px;
    }
</style>

<!-- ⚡ 全局 Popper 气泡美化样式（必须为非 scoped，才能精确修饰 Element Plus 的浮动提示框） -->
<style>
    .el-popper.ide-sidebar-tooltip {
        background: #252536 !important;
        border: 1px solid #353757 !important;
        color: #ffffff !important;
        font-size: 12px !important;
        padding: 6px 10px !important;
        border-radius: 6px !important;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.5) !important;
    }

        .el-popper.ide-sidebar-tooltip .el-popper__arrow::before {
            background: #252536 !important;
            border: 1px solid #353757 !important;
        }
</style>