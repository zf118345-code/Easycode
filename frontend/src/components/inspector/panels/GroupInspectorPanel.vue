<!-- frontend/src/components/inspector/panels/GroupInspectorPanel.vue -->
<template>
    <div class="panel-layout-root">
        <!-- 1. 顶部 Folder 图标 + 组名称 -->
        <div class="inspector-fixed-header">
            <div class="node-title-box">
                <div class="node-type-icon-badge" title="任务组配置">
                    <Folder class="inspector-type-svg" />
                </div>
                <el-input v-model="group.groupName" size="default" class="node-name-input" placeholder="请输入任务组名称" @change="handleSave" />
            </div>
        </div>

        <!-- 2. 中间提示占位 -->
        <div class="inspector-scrollable-body">
            <div class="inspector-empty-tip">
                <span><Folder :size="14" style="vertical-align: middle;" /> 当前配置适用于任务组 [{{ group.groupName }}]</span>
            </div>
        </div>

        <!-- 3. 底部组循环间隔/循环次数（拓扑模式无任务组循环概念，隐藏） -->
        <div v-if="mode !== 'topology'" class="inspector-fixed-footer">
            <div class="footer-inline-container">
                <div class="footer-setting-group">
                    <span class="footer-label">循环间隔</span>
                    <el-input v-model.number="group.loopInterval" size="small" class="pure-compact-input" @change="handleSave" />
                    <span class="footer-unit">ms</span>
                </div>
                <div class="footer-setting-group">
                    <span class="footer-label">循环</span>
                    <el-input v-model.number="group.loopCount" size="small" class="pure-compact-input" @change="handleSave" />
                    <span class="footer-unit">次</span>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
    import { Folder } from 'lucide-vue-next'

    defineProps({
        group: { type: Object, required: true },
        mode: { type: String, default: 'workflow' }
    })
    const emit = defineEmits(['save'])
    const handleSave = () => emit('save')
</script>

<style scoped>
    .panel-layout-root {
        width: 100%;
        height: 100%;
        display: flex;
        flex-direction: column;
    }

    .inspector-fixed-header {
        padding: 12px 14px;
        background: rgba(25, 26, 38, 0.95);
        border-bottom: 1px solid var(--el-border-color-light);
        flex-shrink: 0;
    }

    .inspector-scrollable-body {
        flex: 1;
        padding: 12px 14px;
        overflow-y: auto;
        overscroll-behavior: contain;
        display: flex;
    }

    .inspector-fixed-footer {
        padding: 10px 14px;
        background: rgba(25, 26, 38, 0.95);
        border-top: 1px solid var(--el-border-color-light);
        flex-shrink: 0;
    }

    .node-title-box {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .node-type-icon-badge {
        width: 32px;
        height: 32px;
        background: rgba(78, 209, 156, 0.1);
        border: 1px solid rgba(78, 209, 156, 0.3);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }

    .inspector-type-svg {
        width: 18px;
        height: 18px;
        color: var(--el-color-primary);
    }

    .inspector-empty-tip {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 20px;
        text-align: center;
        font-size: 12px;
        color: var(--el-text-color-placeholder);
    }

    .footer-inline-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .footer-setting-group {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        color: var(--el-text-color-regular);
    }

    .footer-label {
        font-weight: 600;
        color: var(--el-text-color-primary);
    }

    .footer-unit {
        font-size: 11px;
        color: var(--el-text-color-secondary);
    }

    .pure-compact-input {
        width: 60px !important;
    }

        .pure-compact-input :deep(.el-input__wrapper) {
            padding-left: 4px !important;
            padding-right: 4px !important;
            background-color: var(--el-fill-color-blank) !important;
        }
</style>