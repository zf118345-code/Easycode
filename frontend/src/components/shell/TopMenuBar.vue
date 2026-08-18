<!-- frontend/src/components/shell/TopMenuBar.vue -->
<template>
    <div class="top-menu-bar">
        <div class="menu-brand">
            <span class="brand-logo"><Zap :size="18" /></span>
            <span class="brand-title">Easycode IDE</span>
        </div>

        <div class="menu-items-group">
            <el-dropdown trigger="click" @command="handleMenuCommand">
                <span class="menu-label">文件 (F)</span>
                <template #dropdown>
                    <el-dropdown-menu>
                        <el-dropdown-item command="open">打开项目...</el-dropdown-item>
                        <el-dropdown-item command="save" divided>保存蓝图</el-dropdown-item>
                        <el-dropdown-item command="export">导出配置</el-dropdown-item>
                    </el-dropdown-menu>
                </template>
            </el-dropdown>

            <el-dropdown trigger="click" @command="handleMenuCommand">
                <span class="menu-label">编辑 (E)</span>
                <template #dropdown>
                    <el-dropdown-menu>
                        <el-dropdown-item command="undo">撤销</el-dropdown-item>
                        <el-dropdown-item command="redo">重做</el-dropdown-item>
                        <el-dropdown-item command="batch" divided>批量操作</el-dropdown-item>
                        <el-dropdown-item command="hotkey-settings" divided>快捷键设置…</el-dropdown-item>
                    </el-dropdown-menu>
                </template>
            </el-dropdown>

            <el-dropdown trigger="click" @command="handleMenuCommand">
                <span class="menu-label">视图 (V)</span>
                <template #dropdown>
                    <el-dropdown-menu>
                        <el-dropdown-item command="toggle_minimap">切换全景导航</el-dropdown-item>
                        <el-dropdown-item command="toggle_log">切换运行日志</el-dropdown-item>
                    </el-dropdown-menu>
                </template>
            </el-dropdown>

            <el-dropdown trigger="click" @command="handleMenuCommand">
                <span class="menu-label">运行 (R)</span>
                <template #dropdown>
                    <el-dropdown-menu>
                        <el-dropdown-item command="run_task">▶ 运行当前任务</el-dropdown-item>
                        <el-dropdown-item command="screenshot"><Camera :size="14" style="vertical-align: middle;" /> 截图工具</el-dropdown-item>
                        <el-dropdown-item command="control-capture"><ScanSearch :size="14" style="vertical-align: middle;" /> 控件捕获模式</el-dropdown-item>
                    </el-dropdown-menu>
                </template>
            </el-dropdown>

            <!-- ⚡ 打包 (P)：客户表单配置与脚本包导出（原在变量面板，移至此统一收口） -->
            <el-dropdown trigger="click" @command="handleMenuCommand">
                <span class="menu-label">打包 (P)</span>
                <template #dropdown>
                    <el-dropdown-menu>
                        <el-dropdown-item command="open-schema-editor">
                            <Settings :size="14" style="vertical-align: middle;" /> 配置客户表单
                        </el-dropdown-item>
                        <el-dropdown-item command="export-package">
                            <Package :size="14" style="vertical-align: middle;" /> 导出脚本包
                        </el-dropdown-item>
                    </el-dropdown-menu>
                </template>
            </el-dropdown>

            <el-dropdown trigger="click" @command="handleMenuCommand">
                <span class="menu-label">帮助 (H)</span>
                <template #dropdown>
                    <el-dropdown-menu>
                        <el-dropdown-item command="docs">官方文档</el-dropdown-item>
                        <el-dropdown-item command="about">关于 Easycode</el-dropdown-item>
                    </el-dropdown-menu>
                </template>
            </el-dropdown>
        </div>

        <!-- ⚡ 双画布模式切换 Tab：业务流程 / 页面拓扑 -->
        <div class="canvas-mode-switcher">
            <div
v-for="opt in canvasModeOptions"
                 :key="opt.value"
                 class="canvas-mode-tab"
                 :class="{ active: store.canvasMode === opt.value }"
                 @click="handleSwitchCanvasMode(opt.value)">
                <component :is="opt.icon" class="mode-icon" :size="13" />
                <span class="mode-label">{{ opt.label }}</span>
            </div>
        </div>

        <!-- 右侧操作区：工作面板胶囊 + 运行按钮 -->
        <div class="menu-right-actions">
            <div class="workspace-switcher-badge" @click="$emit('openSettings')">
                <span class="device-icon"><Monitor :size="14" /></span>
                <span class="workspace-label">工作面板:</span>
                <span class="workspace-name">{{ currentWorkspaceName }}</span>
                <ChevronDown :size="10" class="dropdown-arrow" />
            </div>

            <el-button type="success" size="small" class="run-quick-btn" :disabled="runDisabled" @click="$emit('run')">
                <Play :size="12" style="vertical-align: middle;" /> 运行
            </el-button>
        </div>
    </div>
</template>

<script setup>
    import { computed } from 'vue'
    import { useMainStore } from '@/stores'
    import { ElMessage } from 'element-plus'
    import { Workflow, Share2, Zap, Camera, Monitor, ChevronDown, Play, Settings, Package, ScanSearch } from 'lucide-vue-next'

    const store = useMainStore()
    defineProps({
        // 执行会话活跃（运行中/已暂停）时禁用「运行」，避免与继续执行冲突
        runDisabled: { type: Boolean, default: false }
    })
    const emit = defineEmits(['run', 'openSettings', 'openSchemaEditor', 'openControlCapture', 'openHotkeySettings', 'openScreenshot'])

    // ⚡ 画布模式选项配置
    const canvasModeOptions = [
        { value: 'workflow', label: '业务流程', icon: Workflow },
        { value: 'topology', label: '页面拓扑', icon: Share2 }
    ]

    const currentWorkspaceName = computed(() => {
        const ctx = store.currentContext
        if (ctx && ctx.windowTitle) {
            return ctx.windowTitle
        }
        return 'Windows 桌面'
    })

    // ⚡ 切换画布模式
    const handleSwitchCanvasMode = (mode) => {
        if (store.canvasMode === mode) return
        store.setCanvasMode(mode)
        const label = canvasModeOptions.find(o => o.value === mode)?.label || mode
        ElMessage.info(`已切换到「${label}」画布`)
    }

    const handleMenuCommand = (command) => {
        if (command === 'toggle_minimap') store.toggleMinimap()
        if (command === 'toggle_log') store.toggleLogPanel()
        if (command === 'about') ElMessage.info('Easycode Automation Studio v2.2')
        // ⚡ 运行菜单：运行当前任务 / 截图工具
        if (command === 'run_task') emit('run')
        if (command === 'screenshot') emit('openScreenshot')
        // ⚡ 打包菜单：配置客户表单 / 导出脚本包 → 打开表单配置与打包弹窗
        if (command === 'open-schema-editor' || command === 'export-package') {
            emit('openSchemaEditor')
        }
        // ⚡ 控件捕获工具
        if (command === 'control-capture') {
            emit('openControlCapture')
        }
        // ⚡ 快捷键设置（编辑菜单）
        if (command === 'hotkey-settings') {
            emit('openHotkeySettings')
        }
    }
</script>

<style scoped>
    .top-menu-bar {
        height: 40px;
        background: var(--el-bg-color);
        border-bottom: 1px solid var(--el-border-color-light);
        display: flex;
        align-items: center;
        padding: 0 12px;
        gap: 16px;
        flex-shrink: 0;
        user-select: none;
        font-size: 12px;
    }

    .menu-brand {
        display: flex;
        align-items: center;
        gap: 6px;
        font-weight: bold;
        color: var(--el-color-primary);
    }

    .brand-logo {
        font-size: 14px;
    }

    .menu-items-group {
        display: flex;
        gap: 12px;
    }

    .menu-label {
        color: var(--el-text-color-regular);
        cursor: pointer;
        padding: 4px 8px;
        border-radius: 4px;
        transition: background 0.2s;
    }

        .menu-label:hover {
            background: var(--el-fill-color-light);
            color: var(--el-text-color-primary);
        }

    /* ⚡ 画布模式切换 Tab 样式 */
    .canvas-mode-switcher {
        display: flex;
        align-items: center;
        background: var(--el-fill-color-light);
        border: 1px solid var(--el-border-color-light);
        border-radius: 8px;
        padding: 2px;
        gap: 2px;
    }

    .canvas-mode-tab {
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 3px 12px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 12px;
        color: var(--el-text-color-secondary);
        transition: all 0.2s ease;
        user-select: none;
        white-space: nowrap;
    }

        .canvas-mode-tab:hover {
            color: var(--el-text-color-primary);
            background: var(--el-fill-color);
        }

        .canvas-mode-tab.active {
            background: var(--el-color-primary);
            color: #fff;
            font-weight: 600;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
        }

    .mode-icon {
        flex-shrink: 0;
    }

    .mode-label {
        line-height: 1;
    }

    .menu-right-actions {
        margin-left: auto;
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .workspace-switcher-badge {
        display: flex;
        align-items: center;
        gap: 6px;
        background: rgba(25, 26, 38, 0.85);
        border: 1px solid var(--el-border-color-light);
        padding: 2px 10px;
        border-radius: 14px;
        font-size: 11px;
        cursor: pointer;
        transition: all 0.2s ease;
        user-select: none;
        height: 26px;
    }

        .workspace-switcher-badge:hover {
            border-color: var(--el-color-primary);
            background: rgba(38, 40, 61, 0.95);
        }

    .device-icon {
        font-size: 11px;
    }

    .workspace-label {
        color: var(--el-text-color-secondary);
    }

    .workspace-name {
        color: var(--el-color-primary);
        font-weight: 600;
    }

    .dropdown-arrow {
        font-size: 8px;
        color: var(--el-text-color-secondary);
        margin-left: 2px;
    }

    .run-quick-btn {
        height: 26px !important;
        padding: 0 12px !important;
        font-size: 12px !important;
    }
</style>
