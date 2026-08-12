<!-- frontend/src/components/PanelContainer.vue -->
<template>
    <div class="main-layout-container">
        <div class="pane-content">
            <PanelHeader title="可视化全景流程图 (多组同屏、右键管理、跨组连线)">
                <div class="workspace-switcher-badge" @click="openPanelSettings">
                    <span class="device-icon">💻</span>
                    <span class="workspace-label">工作面板:</span>
                    <span class="workspace-name">{{ currentWorkspaceName }}</span>
                    <span class="dropdown-arrow">▼</span>
                </div>
            </PanelHeader>

            <div class="canvas-viewport-wrapper">
                <WorkflowCanvas />
            </div>
        </div>

        <PanelSettingsDialog v-model:visible="dialogVisible"
                             @apply="handleApplyContext" />
    </div>
</template>

<script setup>
    import { ref, computed } from 'vue'
    import { useMainStore } from '@/stores'
    import { ElMessage } from 'element-plus'
    import PanelHeader from './PanelHeader.vue'
    import WorkflowCanvas from './WorkflowCanvas.vue'
    import PanelSettingsDialog from './PanelSettingsDialog.vue'

    const store = useMainStore()
    const dialogVisible = ref(false)

    const currentWorkspaceName = computed(() => {
        const ctx = store.currentContext
        if (ctx && ctx.windowTitle) {
            return ctx.windowTitle
        }
        return 'Windows 桌面'
    })

    const openPanelSettings = () => {
        dialogVisible.value = true
    }

    const handleApplyContext = async (context) => {
        try {
            await store.setCurrentContext(context)
            ElMessage.success('工作面板切换成功')
        } catch (err) {
            ElMessage.error('切换失败: ' + err.message)
        }
    }
</script>

<style scoped>
    .main-layout-container {
        width: 100%;
        height: 100%;
        background: var(--el-bg-color-page);
        display: flex;
        flex-direction: column;
        box-sizing: border-box;
    }

    .pane-content {
        display: flex;
        flex-direction: column;
        height: 100%;
        width: 100%;
        background: var(--el-bg-color);
        overflow: hidden;
        box-sizing: border-box;
    }

    .canvas-viewport-wrapper {
        flex: 1;
        position: relative;
        overflow: hidden;
    }

    .workspace-switcher-badge {
        display: flex;
        align-items: center;
        gap: 6px;
        background: rgba(25, 26, 38, 0.85);
        border: 1px solid var(--el-border-color-light);
        padding: 2px 10px;
        border-radius: 14px;
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s ease;
        user-select: none;
        height: 24px;
    }

        .workspace-switcher-badge:hover {
            border-color: var(--el-color-primary);
            background: rgba(38, 40, 61, 0.95);
        }

    .device-icon {
        font-size: 12px;
    }

    .workspace-label {
        color: var(--el-text-color-secondary);
    }

    .workspace-name {
        color: var(--el-color-primary);
        font-weight: 600;
    }

    .dropdown-arrow {
        font-size: 9px;
        color: var(--el-text-color-secondary);
        margin-left: 2px;
    }
</style>