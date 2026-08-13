<!-- frontend/src/components/shell/ToolWindow.vue -->
<template>
    <div class="tool-window-pane" :style="{ width: width, height: height }">
        <div class="tool-window-header">
            <span class="window-title">{{ title }}</span>
            <div class="window-tools">
                <button class="window-tool-btn" title="最小化收起" @click="$emit('close')">
                    <Minus style="width: 12px; height: 12px;" />
                </button>
            </div>
        </div>
        <div class="tool-window-content">
            <slot />
        </div>
    </div>
</template>

<script setup>
import { Minus } from 'lucide-vue-next'

defineProps({
  title: { type: String, default: '工具面板' },
  width: { type: String, default: '280px' },
  height: { type: String, default: '100%' }
})

defineEmits(['close'])
</script>

<style scoped>
    .tool-window-pane {
        background: var(--el-bg-color);
        border-right: 1px solid var(--el-border-color-light);
        border-bottom: 1px solid var(--el-border-color-light);
        display: flex;
        flex-direction: column;
        flex-shrink: 0;
        overflow: hidden;
        box-sizing: border-box;
    }

    .tool-window-header {
        height: 30px;
        background: rgba(25, 26, 38, 0.95);
        border-bottom: 1px solid var(--el-border-color-light);
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 10px;
        font-size: 11px;
        font-weight: 600;
        color: var(--el-text-color-regular);
        user-select: none;
    }

    .window-tools {
        display: flex;
        align-items: center;
    }

    .window-tool-btn {
        background: transparent;
        border: none;
        color: var(--el-text-color-secondary);
        cursor: pointer;
        padding: 2px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 3px;
        transition: all 0.2s;
    }

        .window-tool-btn:hover {
            background: var(--el-fill-color-light);
            color: var(--el-text-color-primary);
        }

    .tool-window-content {
        flex: 1;
        overflow: hidden;
        position: relative;
        display: flex;
        flex-direction: column;
    }
</style>