<template>
    <footer class="app-footer">
        <div class="footer-left">
            <span>● 就绪 | 项目: {{ currentProject }}</span>
        </div>

        <div class="footer-center">
            <span class="panel-status" @click="showPanelDialog">
                <el-icon><Monitor /></el-icon>
                {{ panelStatus }}
            </span>
        </div>

        <!-- 右侧：像图2一样整齐排列的切换按钮 -->
        <div class="footer-right">
            <div class="footer-tab-btn" :class="{ 'is-active': store.minimapExpanded }" @click="store.toggleMinimap">
                <span>🗺️ 全景导航</span>
            </div>
            <div class="footer-tab-btn" :class="{ 'is-active': store.logExpanded }" @click="store.toggleLogPanel">
                <span>📝 运行日志</span>
            </div>
            <span class="exec-status">⚡ 执行状态: 空闲</span>
        </div>

        <PanelSettingsDialog v-model:visible="dialogVisible"
                             @apply="handleApplyContext" />
    </footer>
</template>

<script>
    import { useMainStore } from '@/stores'
    import { ElMessage } from 'element-plus'
    import { Monitor } from '@element-plus/icons-vue'
    import PanelSettingsDialog from './PanelSettingsDialog.vue'

    export default {
        components: { Monitor, PanelSettingsDialog },
        data() {
            return { dialogVisible: false }
        },
        setup() {
            const store = useMainStore()
            return { store }
        },
        computed: {
            currentProject() {
                return this.store.currentProjectName || '未选择'
            },
            panelStatus() {
                const ctx = this.store.currentContext
                if (ctx && ctx.windowTitle) {
                    const label = ctx.isEmulator ? '📱' : '🪟'
                    return `${label} 工作面板：${ctx.windowTitle}`
                }
                return '🖥️ 工作面板：Windows 桌面'
            }
        },
        methods: {
            showPanelDialog() {
                this.dialogVisible = true
            },
            async handleApplyContext(context) {
                try {
                    await this.store.setCurrentContext(context)
                    ElMessage.success('工作面板已更新并保存')
                } catch (err) {
                    ElMessage.error('保存失败: ' + err.message)
                }
            }
        }
    }
</script>

<style scoped>
    .app-footer {
        height: 30px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 20px;
        background: var(--el-bg-color);
        border-top: 1px solid var(--el-border-color-light);
        color: var(--el-text-color-secondary);
        font-size: 12px;
        flex-shrink: 0;
        z-index: 1000;
        user-select: none;
    }

    .footer-left, .footer-center, .footer-right {
        display: flex;
        align-items: center;
        gap: 12px;
        height: 100%;
    }

    .panel-status {
        cursor: pointer;
        padding: 2px 10px;
        border-radius: 12px;
        background: var(--el-fill-color-blank);
        transition: background 0.2s;
    }

        .panel-status:hover {
            background: var(--el-fill-color-light);
        }

        .panel-status .el-icon {
            margin-right: 4px;
        }

    /* 仿图2的高亮切换按钮效果 */
    .footer-tab-btn {
        padding: 0 10px;
        height: 100%;
        display: flex;
        align-items: center;
        cursor: pointer;
        transition: all 0.2s ease;
        color: var(--el-text-color-secondary);
        border-radius: 3px;
    }

        .footer-tab-btn:hover {
            background: rgba(255, 255, 255, 0.05);
            color: var(--el-text-color-primary);
        }

        /* 点亮激活状态（带底部强调线） */
        .footer-tab-btn.is-active {
            background: rgba(78, 209, 156, 0.15);
            color: var(--el-color-primary, #4ed19c);
            font-weight: 600;
            border-bottom: 2px solid var(--el-color-primary, #4ed19c);
        }
</style>