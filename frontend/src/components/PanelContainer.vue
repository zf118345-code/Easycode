<template>
    <div class="main-layout-container">
        <!-- 上方：全屏可视化流程图画布 -->
        <div class="pane-content">
            <PanelHeader title="可视化全景流程图 (多组同屏、右键管理、跨组连线)" :actions="[]">
                <!-- 直接在这里塞入工作面板切换器 -->
                <div class="workspace-switcher-badge" @click="openWorkspaceSelector">
                    <span class="device-icon">💻</span>
                    <span class="workspace-label">工作面板:</span>
                    <span class="workspace-name">{{ store.currentWorkspace || 'Windows 桌面' }}</span>
                    <span class="dropdown-arrow">▼</span>
                </div>
            </PanelHeader>
            <WorkflowCanvas />
        </div>
    </div>
</template>

<script>
    import PanelHeader from './PanelHeader.vue'
    import WorkflowCanvas from './WorkflowCanvas.vue'
    import { useMainStore } from '@/stores'
    import { ElMessage } from 'element-plus'

    export default {
        components: {
            PanelHeader,
            WorkflowCanvas
        },
        setup() {
            const store = useMainStore()

            const openWorkspaceSelector = () => {
                ElMessage.info('正在打开工作面板切换设置...')
            }

            return {
                store,
                openWorkspaceSelector
            }
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
        padding: 4px;
        background: var(--el-bg-color);
        border-radius: 6px;
        overflow: hidden;
        box-sizing: border-box;
    }

    /* 顶栏精致的胶囊工作区切换按钮样式 */
    .workspace-switcher-badge {
        display: flex;
        align-items: center;
        gap: 6px;
        background: rgba(25, 26, 38, 0.85);
        border: 1px solid var(--el-border-color-light, #313352);
        padding: 2px 10px;
        border-radius: 14px;
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s ease;
        user-select: none;
        height: 26px;
        box-sizing: border-box;
    }

        .workspace-switcher-badge:hover {
            border-color: var(--el-color-primary, #4ed19c);
            background: rgba(38, 40, 61, 0.95);
        }

    .device-icon {
        font-size: 12px;
    }

    .workspace-label {
        color: var(--el-text-color-secondary, #909399);
    }

    .workspace-name {
        color: var(--el-color-primary, #4ed19c);
        font-weight: 600;
    }

    .dropdown-arrow {
        font-size: 9px;
        color: var(--el-text-color-secondary);
        margin-left: 2px;
    }
</style>