<!-- frontend/src/components/PanelHeader.vue -->
<template>
    <div class="panel-header">
        <div class="header-title">
            <span class="title-text">{{ title }}</span>
        </div>
        <div class="header-actions">
            <slot />
            <template v-if="actions && actions.length">
                <el-button v-for="act in actions"
                           :key="act.key"
                           size="small"
                           :type="act.type || 'default'"
                           @click="act.onClick">
                    {{ act.label }}
                </el-button>
            </template>
        </div>
    </div>
</template>

<script setup>
    defineProps({
        title: { type: String, default: '¹¤×÷Ãæ°å' },
        actions: { type: Array, default: () => [] }
    })
</script>

<style scoped>
    .panel-header {
        height: 36px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 12px;
        background: var(--el-bg-color-page);
        border-bottom: 1px solid var(--el-border-color-light);
        flex-shrink: 0;
        user-select: none;
    }

    .header-title {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .title-text {
        font-size: 13px;
        font-weight: 600;
        color: var(--el-text-color-primary);
    }

    .header-actions {
        display: flex;
        align-items: center;
        gap: 8px;
    }
</style>