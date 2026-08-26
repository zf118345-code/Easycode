<!-- frontend/src/components/shell/ActivityBar.vue -->
<template>
    <div class="activity-bar" :class="position">
        <el-tooltip
v-for="(item, index) in items"
                    :key="item.id"
                    effect="dark"
                    :content="item.title"
                    :placement="position === 'right' ? 'left' : 'right'"
                    :show-after="300"
                    popper-class="ide-sidebar-tooltip">
            <button
type="button"
                 class="activity-icon-item"
                 :class="{ 'is-active': activeId === item.id, 'is-section-start': index > 0 && items[index - 1]?.group !== item.group }"
                 :aria-label="item.title"
                 :aria-pressed="activeId === item.id"
                 @click="$emit('select', item.id)">
                <component :is="item.icon" class="act-svg" />
            </button>
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
        background: var(--app-sidebar-bg);
        display: flex;
        align-items: center;
        flex-shrink: 0;
        z-index: 50;
        user-select: none;
    }

        .activity-bar.left, .activity-bar.right {
            width: 44px;
            height: 100%;
            flex-direction: column;
            padding-top: 7px;
            gap: 3px;
        }

        .activity-bar.bottom {
            height: 40px;
            width: 100%;
            flex-direction: row;
            padding-left: 6px;
            gap: 4px;
        }

    .activity-icon-item {
        position: relative;
        width: 32px;
        height: 32px;
        margin: 0 auto;
        border-radius: 7px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        padding: 0;
        border: 0;
        background: transparent;
        color: var(--el-text-color-secondary);
        transition: background .14s ease, color .14s ease;
    }

        .activity-icon-item.is-section-start {
            margin-top: 9px;
        }

        .activity-icon-item.is-section-start::before {
            content: '';
            position: absolute;
            top: -5px;
            left: 7px;
            right: 7px;
            height: 1px;
            background: var(--app-separator);
        }

        .activity-icon-item:hover {
            background: var(--el-fill-color-light);
            color: var(--el-text-color-primary);
        }

        .activity-icon-item.is-active {
    background: var(--app-color-primary-dim);
            color: var(--el-color-primary);
            box-shadow: inset 2px 0 var(--el-color-primary);
        }

    .act-svg {
        width: 18px;
        height: 18px;
    }
</style>

<!-- ⚡ 全局 Popper 气泡美化样式（必须为非 scoped，才能精确修饰 Element Plus 的浮动提示框） -->
<style>
    .el-popper.ide-sidebar-tooltip {
    background: var(--app-overlay-bg) !important;
    border: 1px solid var(--app-overlay-border) !important;
    color: var(--app-text-primary) !important;
        font-size: 12px !important;
        padding: 6px 10px !important;
        border-radius: 7px !important;
    box-shadow: var(--app-shadow-md) !important;
    }

        .el-popper.ide-sidebar-tooltip .el-popper__arrow::before {
    background: var(--app-overlay-bg) !important;
    border: 1px solid var(--app-overlay-border) !important;
        }
</style>
