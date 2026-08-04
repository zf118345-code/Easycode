<template>
    <header class="app-header">
        <div class="left-group">
            <el-icon class="menu-icon" @click="toggleMenu"><Menu /></el-icon>
            <span class="logo">⚡ 节点自动化</span>
        </div>

        <div class="project-selector">
            <span class="project-name">📁 {{ store.currentProjectName || '未选择项目' }}</span>
            <el-button size="small" type="primary" @click="switchProject">
                🔄 切换
            </el-button>
        </div>

        <el-menu mode="horizontal"
                 :default-active="activeMenu"
                 background-color="#2d2d44"
                 text-color="#cfd3e6"
                 active-text-color="#409EFF"
                 @select="onMenuSelect"
                 class="menu-bar">
            <el-menu-item index="file">文件</el-menu-item>
            <el-menu-item index="edit">编辑</el-menu-item>
            <el-menu-item index="view">视图</el-menu-item>
            <el-menu-item index="screenshot" @click="openScreenshot">截图工具</el-menu-item>
            <el-menu-item index="run">运行</el-menu-item>
        </el-menu>

        <!-- ⭐⭐⭐ 核心升级：视图切换模式 (列表模式 vs 流程图画布) -->
        <div class="view-mode-switch">
            <el-radio-group v-model="store.viewMode" size="small">
                <el-radio-button label="list">📊 列表</el-radio-button>
                <el-radio-button label="flow">🔀 画布</el-radio-button>
            </el-radio-group>
        </div>

        <div class="header-actions">
            <el-button type="primary" size="small" @click="runTask">▶ 运行</el-button>
        </div>

        <ScreenshotTool ref="screenshotTool" />
    </header>
</template>

<script>
    import { Menu } from '@element-plus/icons-vue'
    import { useMainStore } from '@/stores'
    import { ElMessage, ElMessageBox } from 'element-plus'
    import ScreenshotTool from './ScreenshotTool.vue'

    export default {
        components: { Menu, ScreenshotTool },
        data() {
            return { activeMenu: 'file' }
        },
        setup() {
            const store = useMainStore()
            return { store }
        },
        methods: {
            async switchProject() {
                try {
                    const { value: path } = await ElMessageBox.prompt('请输入新的项目完整路径', '切换项目', {
                        confirmButtonText: '确定',
                        cancelButtonText: '取消',
                        inputValue: this.store.currentProjectPath || '',
                        inputPattern: /^[a-zA-Z]:[\\/].+/,
                        inputErrorMessage: '请输入有效的绝对路径（如 D:/MyProjects/demo）'
                    })
                    if (path) {
                        await this.store.loadProjectByPath(path)
                        ElMessage.success(`已切换到项目: ${this.store.currentProjectName}`)
                        this.store.selectedNodeId = null
                    }
                } catch (err) {
                    if (err !== 'cancel') {
                        ElMessage.error('切换失败: ' + err.message)
                    }
                }
            },
            onMenuSelect(index) {
                this.activeMenu = index
                if (index === 'screenshot') this.openScreenshot()
            },
            openScreenshot() {
                this.$refs.screenshotTool.open()
            },
            async runTask() {
                if (!this.store.currentTaskId) {
                    ElMessage.warning('请先选择一个任务')
                    return
                }
                try {
                    ElMessage.info('任务执行中...')
                    const result = await this.store.runTask(this.store.currentTaskId, null)
                    if (result.status === 'started') {
                        ElMessage.success('任务已启动，请查看执行状态')
                    } else {
                        ElMessage.error('执行失败: ' + (result.message || '未知错误'))
                    }
                } catch (err) {
                    ElMessage.error('执行请求失败: ' + (err.response?.data?.detail || err.message))
                    console.error(err)
                }
            },
            toggleMenu() { }
        }
    }
</script>

<style scoped>
    .app-header {
        display: flex;
        align-items: center;
        height: 40px;
        padding: 0 12px;
        background: var(--el-bg-color);
        border-bottom: 1px solid var(--el-border-color-light);
        flex-shrink: 0;
        gap: 12px;
    }

    .left-group {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .menu-icon {
        color: var(--el-text-color-regular);
        font-size: 20px;
        cursor: pointer;
    }

        .menu-icon:hover {
            color: var(--el-color-primary);
        }

    .logo {
        color: var(--el-text-color-primary);
        font-weight: bold;
        font-size: 16px;
    }

    .project-selector {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-shrink: 0;
    }

    .project-name {
        color: var(--el-text-color-regular);
        font-weight: 500;
    }

    .menu-bar {
        flex: 1;
        border-bottom: none;
        background: transparent !important;
    }

        .menu-bar .el-menu-item {
            height: 40px;
            line-height: 40px;
        }

    .view-mode-switch {
        margin-right: 8px;
    }

    .header-actions {
        display: flex;
        gap: 8px;
    }
</style>