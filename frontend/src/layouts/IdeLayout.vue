<!-- frontend/src/layouts/IdeLayout.vue -->
<template>
    <div class="ide-shell-layout">
        <!-- 1. 顶部主菜单栏 -->
        <TopMenuBar
            :run-disabled="store.isRunning || store.isPaused"
            @run="handleRun"
            @open-settings="settingsVisible = true"
            @open-schema-editor="schemaDialogVisible = true"
            @open-control-capture="controlCaptureVisible = true"
            @open-hotkey-settings="hotkeySettingsVisible = true"
            @open-screenshot="openGlobalScreenshot" />

        <!-- 1.1 调试工具栏（工业级：▶⏸⏹⏭⏬⏫ + 断点统计 + 激活节点） -->
        <div class="debug-toolbar-bar">
            <DebugToolbar />
        </div>

        <!-- 2. 全局主工作区 -->
        <div class="ide-workspace-root">
<!-- 左侧固定 40px 图标栏 -->
            <div class="fixed-dock-left">
                <ActivityBar
position="left"
                             :items="leftPanelsConfig"
                             :active-id="leftActive"
                             @select="toggleLeftPanel" />
                <div class="bottom-toggle-dock">
                    <el-tooltip
v-for="item in bottomPanelsConfig"
                                :key="item.id"
                                effect="dark"
                                :content="item.title"
                                placement="right"
                                :show-after="300"
                                popper-class="ide-sidebar-tooltip">
                        <div
class="activity-icon-item"
                             :class="{ 'is-active': store.uiState.bottomPanelExpanded && bottomActive === item.id }"
                             @click="toggleBottomPanel(item.id)">
                            <component :is="item.icon" class="act-svg" />
                        </div>
                    </el-tooltip>
                </div>
            </div>

            <!-- 中间大区域 -->
            <div class="ide-middle-area">
<!-- 上半行：左侧面板 + 画布 + 右侧面板 -->
                <div class="ide-upper-row">
                    <!-- 左侧展开面板 -->
                    <ToolWindow
v-if="store.uiState.leftPanelExpanded && currentLeftPanel"
                                :title="leftPanelTitle"
                                :width="store.uiState.leftPanelWidth + 'px'"
                                class="ide-card-panel"
                                @close="store.updateUiState('leftPanelExpanded', false)">
                        <component :is="currentLeftPanel.component" />
                    </ToolWindow>

                    <!-- 左侧 5px 拖拽调节分割线 -->
                    <div
v-if="store.uiState.leftPanelExpanded && currentLeftPanel"
                         class="splitter-v"
                         @mousedown="startLeftResize" />

                    <!-- 中央画布区域：唯一画布页面（workflow/topology 共用一套画布组件，仅数据源不同） -->
                    <div class="ide-center-viewport ide-card-panel">
                        <div class="pane-content-inner">
                            <CanvasPage ref="canvasPageRef" :key="store.canvasMode" />
                        </div>
                    </div>

                    <!-- 右侧 5px 拖拽调节分割线 -->
                    <div
v-if="store.uiState.rightPanelExpanded && currentRightPanel"
                         class="splitter-v"
                         @mousedown="startRightResize" />

                    <!-- 右侧展开面板：统一属性检查器（按 canvasMode 自动切换数据源） -->
                    <ToolWindow
                        v-if="store.uiState.rightPanelExpanded && currentRightPanel"
                        :title="rightPanelTitle"
                        :width="store.uiState.rightPanelWidth + 'px'"
                        class="ide-card-panel"
                        @close="store.updateUiState('rightPanelExpanded', false)">
                        <component :is="currentRightPanel.component" />
                    </ToolWindow>
                </div>

                <!-- 底部 5px 拖拽调节分割线 -->
                <div
v-if="store.uiState.bottomPanelExpanded && currentBottomPanel"
                     class="splitter-h"
                     @mousedown="startBottomResize" />

                <!-- 下半行：底部工具窗口 -->
                <ToolWindow
v-if="store.uiState.bottomPanelExpanded && currentBottomPanel"
                            :title="currentBottomPanel.title"
                            width="100%"
                            :height="store.uiState.bottomPanelHeight + 'px'"
                            class="ide-card-panel"
                            @close="store.updateUiState('bottomPanelExpanded', false)">
                    <component :is="currentBottomPanel.component" />
                </ToolWindow>
</div>

            <!-- 右侧固定 40px 图标栏 -->
            <div class="fixed-dock-right">
                <ActivityBar
position="right"
                             :items="rightPanelsConfig"
                             :active-id="rightActive"
                             @select="toggleRightPanel" />
            </div>
</div>

        <!-- 3. 底部纯净状态栏 -->
        <footer class="ide-status-footer">
            <div class="status-left">
                <span class="status-dot">●</span>
                <span>就绪</span>
                <span class="status-divider">|</span>
                <span>画布模式: {{ canvasModeLabel }}</span>
                <span class="status-divider">|</span>
                <span>项目路径: {{ store.currentProjectPath || '未打开' }}</span>
            </div>
            <div class="status-right">
                <span>执行状态: 空闲</span>
                <span class="status-divider">|</span>
                <span>UTF-8</span>
                <span class="status-divider">|</span>
                <span>Vue 3.5</span>
            </div>
        </footer>

        <!-- 面板设置弹窗 -->
        <PanelSettingsDialog v-model:visible="settingsVisible" @apply="handleApplyContext" />

        <!-- 客户表单配置与脚本包导出弹窗（顶栏「打包 (P)」菜单入口） -->
        <FormSchemaEditor v-model="schemaDialogVisible" />

        <!-- 控件捕获工具（顶栏「运行 (R)」菜单入口；捕获结果 → 一键生成控件节点） -->
        <ControlCaptureTool
            v-model="controlCaptureVisible"
            :capture-event="captureEvent"
            :backend-connected="captureConnected"
            @node-requested="handleCaptureNodeRequested" />

        <!-- 全局快捷键设置（顶部「编辑 (E) → 快捷键设置」） -->
        <HotkeySettingsDialog v-model="hotkeySettingsVisible" />

        <!-- 截图工具（顶栏「运行 (R) → 截图工具」）：框选后自动保存到项目 templates/ -->
        <ScreenshotTool
            ref="screenshotToolRef"
            @template-crop-selected="onGlobalTemplateCrop" />
    </div>
</template>

<script setup>
    import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
    import { useMainStore, useUiStore } from '@/stores'
    import { ElMessage } from 'element-plus'

    import TopMenuBar from '@/components/shell/TopMenuBar.vue'
    import ActivityBar from '@/components/shell/ActivityBar.vue'
    import ToolWindow from '@/components/shell/ToolWindow.vue'
    import CanvasPage from '@/components/CanvasPage.vue'
    import PanelSettingsDialog from '@/components/PanelSettingsDialog.vue'
    import FormSchemaEditor from '@/components/schema/FormSchemaEditor.vue'
    import ControlCaptureTool from '@/components/ControlCaptureTool.vue'
    import HotkeySettingsDialog from '@/components/HotkeySettingsDialog.vue'
    import ScreenshotTool from '@/components/ScreenshotTool.vue'
    import DebugToolbar from '@/components/DebugToolbar.vue'
    import { uiControlApi } from '@/api/uiControlApi'
    import { workspaceApi } from '@/api/workspaceApi'

    import { leftPanelsConfig, rightPanelsConfig, bottomPanelsConfig } from '@/config/panelsConfig'

    const store = useMainStore()
    const settingsVisible = ref(false)
    const schemaDialogVisible = ref(false)
    const controlCaptureVisible = ref(false)
    const hotkeySettingsVisible = ref(false)
    const canvasPageRef = ref(null)
    const screenshotToolRef = ref(null)

    // ⚡ 顶栏「运行 (R) → 截图工具」：打开全局模板截图（框选 → 自动保存到项目 templates/）
    const openGlobalScreenshot = () => {
        if (!store.currentProjectPath) {
            ElMessage.warning('请先打开一个项目，再使用截图工具')
            return
        }
        screenshotToolRef.value?.open('template')
    }
    const onGlobalTemplateCrop = async (cropRect) => {
        try {
            const ts = new Date()
            const pad = n => String(n).padStart(2, '0')
            const name = `截图_${ts.getFullYear()}${pad(ts.getMonth() + 1)}${pad(ts.getDate())}_${pad(ts.getHours())}${pad(ts.getMinutes())}${pad(ts.getSeconds())}`
            await workspaceApi.cropScreenshot(store.currentProjectPath, name, cropRect)
            ElMessage.success(`模板图片 [${name}] 已保存到 templates/`)
        } catch (err) {
            ElMessage.error('截图保存失败: ' + (err?.message || err))
        }
    }

    // ⚡ 捕获结果处理：若节点表单/条件对话框注册了填充回调（captureFillHandler）→ 回填当前编辑目标
    // 并退出捕获模式（一次性填充语义：捕获一次赋给当前节点后即退出；再次点击捕获则覆盖重填）；
    // 否则维持原行为：生成新控件节点（全局「控件捕获模式」：不退出，可连续捕获）
    const handleCaptureNodeRequested = async (info) => {
        const uiStore = useUiStore()
        const fillHandler = uiStore.captureFillHandler
        if (fillHandler) {
            try {
                fillHandler(info)
            } catch (err) {
                ElMessage.error('控件捕获填充失败: ' + (err?.message || ''))
            } finally {
                uiStore.clearCaptureFillHandler()
                uiStore.bumpInspectorSync()  // 检查器立即同步外部填充
                uiControlApi.modeControl('stop').catch(() => {})  // ⚡ 填充完成即退出捕获模式
                controlCaptureVisible.value = false  // ⚡ 一次性填充完成：面板一并收起（再次捕获需重新点按钮）
            }
            return
        }
        if (!store.currentProjectPath) {
            ElMessage.warning('请先打开一个项目，再生成控件节点')
            return
        }
        if (!canvasPageRef.value) {
            ElMessage.warning('画布尚未就绪，请稍后再试')
            return
        }
        try {
            await canvasPageRef.value.createControlNodeFromCapture(info)
        } catch (err) {
            ElMessage.error('生成控件节点失败: ' + (err?.message || ''))
        }
    }

    // ⚡ 捕获事件 SSE 长连接（零轮询）：热键进入（mode active）自动召唤面板；
    // 选中/层级/取消/复制事件转发给面板消费；后端断开时明示连接中断
    const captureEvent = ref(null)
    const captureConnected = ref(true)
    let captureEventSource = null

    function connectCaptureEvents() {
        if (captureEventSource) return
        captureEventSource = new EventSource('/api/ui-control/events')
        captureEventSource.onopen = () => { captureConnected.value = true }
        captureEventSource.onerror = () => {
            // EventSource 自动重连；断开期间面板显示「后端连接中断」（模态已失效，防假激活穿透）
            captureConnected.value = false
        }
        captureEventSource.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data)
                captureConnected.value = true
                captureEvent.value = data
                if (data.event === 'mode' && data.active) {
                    controlCaptureVisible.value = true  // ⚡ 热键进入 → 自动弹出面板（与点菜单一致）
                }
            } catch { /* 忽略非法帧 */ }
        }
    }
    onMounted(connectCaptureEvents)
    onUnmounted(() => {
        if (captureEventSource) {
            captureEventSource.close()
            captureEventSource = null
        }
    })

    // ⚡ 右侧面板：统一属性检查器（InspectorPanel 按 canvasMode 自动切换数据源，标题恒定）
    const rightActive = ref('inspector')
    const currentRightPanel = computed(() => {
        return rightPanelsConfig.find(p => p.id === rightActive.value)
    })

    const rightPanelTitle = computed(() => {
        return currentRightPanel.value?.title || '属性面板'
    })

    // ⚡ 左侧面板标题：仅「资源管理器」随画布模式切换（内容同数据源切换）；
    // 其余面板（变量监控/插件中心等）标题与模式无关，按当前激活面板返回
    const leftPanelTitle = computed(() => {
        const base = currentLeftPanel.value?.title || '项目资源管理器'
        if (store.canvasMode === 'topology' && currentLeftPanel.value?.id === 'explorer') {
            return '拓扑资源管理器'
        }
        return base
    })

    // ⚡ 状态栏画布模式文案
    const canvasModeLabel = computed(() => {
        return store.canvasMode === 'topology' ? '页面拓扑' : '业务流程'
    })

    // 左侧面板选项与切换（状态联动 store.uiState）
    const leftActive = ref('explorer')
    const currentLeftPanel = computed(() => leftPanelsConfig.find(p => p.id === leftActive.value))

    const toggleLeftPanel = (id) => {
        if (leftActive.value === id && store.uiState.leftPanelExpanded) {
            store.updateUiState('leftPanelExpanded', false)
        } else {
            leftActive.value = id
            store.updateUiState('leftPanelExpanded', true)
        }
    }

    // 右侧面板切换（状态联动 store.uiState）
    const toggleRightPanel = (id) => {
        if (rightActive.value === id && store.uiState.rightPanelExpanded) {
            store.updateUiState('rightPanelExpanded', false)
        } else {
            rightActive.value = id
            store.updateUiState('rightPanelExpanded', true)
        }
    }

    // 底部面板选项与切换（状态联动 store.uiState）
    const bottomActive = ref('console')
    const currentBottomPanel = computed(() => bottomPanelsConfig.find(p => p.id === bottomActive.value))

    const toggleBottomPanel = (id) => {
        if (bottomActive.value === id && store.uiState.bottomPanelExpanded) {
            store.updateUiState('bottomPanelExpanded', false)
        } else {
            bottomActive.value = id
            store.updateUiState('bottomPanelExpanded', true)
        }
    }

    // ⚡ 左侧面板拖拽调整宽度（实时保存到 JSON）
    const startLeftResize = (e) => {
        e.preventDefault()
        const startX = e.clientX
        const startW = store.uiState.leftPanelWidth
        const onMouseMove = (moveEvent) => {
            const dx = moveEvent.clientX - startX
            const newW = Math.max(160, Math.min(startW + dx, 600))
            store.updateUiState('leftPanelWidth', newW)
        }
        const onMouseUp = () => {
            window.removeEventListener('mousemove', onMouseMove)
            window.removeEventListener('mouseup', onMouseUp)
        }
        window.addEventListener('mousemove', onMouseMove)
        window.addEventListener('mouseup', onMouseUp)
    }

    // ⚡ 右侧面板拖拽调整宽度（实时保存到 JSON）
    const startRightResize = (e) => {
        e.preventDefault()
        const startX = e.clientX
        const startW = store.uiState.rightPanelWidth
        const onMouseMove = (moveEvent) => {
            const dx = startX - moveEvent.clientX
            const newW = Math.max(200, Math.min(startW + dx, 600))
            store.updateUiState('rightPanelWidth', newW)
        }
        const onMouseUp = () => {
            window.removeEventListener('mousemove', onMouseMove)
            window.removeEventListener('mouseup', onMouseUp)
        }
        window.addEventListener('mousemove', onMouseMove)
        window.addEventListener('mouseup', onMouseUp)
    }

    // ⚡ 底部面板拖拽调整高度（实时保存到 JSON）
    const startBottomResize = (e) => {
        e.preventDefault()
        const startY = e.clientY
        const startH = store.uiState.bottomPanelHeight
        const onMouseMove = (moveEvent) => {
            const dy = startY - moveEvent.clientY
            const newH = Math.max(80, Math.min(startH + dy, 500))
            store.updateUiState('bottomPanelHeight', newH)
        }
        const onMouseUp = () => {
            window.removeEventListener('mousemove', onMouseMove)
            window.removeEventListener('mouseup', onMouseUp)
        }
        window.addEventListener('mousemove', onMouseMove)
        window.addEventListener('mouseup', onMouseUp)
    }

    const handleRun = async () => {
        if (!store.currentTaskId) return ElMessage.warning('请先选择任务')
        if (store.isRunning || store.isPaused) {
            return ElMessage.warning('已有任务正在执行/暂停，请先停止再运行')
        }
        const res = await store.runTask(store.currentTaskId, null)
        if (res?.status === 'started') {
            ElMessage.success('任务已启动')
        } else {
            ElMessage.warning((res?.error) || '任务启动失败')
        }
    }

    const handleApplyContext = async (ctx) => {
        await store.setCurrentContext(ctx)
        ElMessage.success('工作面板切换成功')
    }
</script>

<style scoped>
    .ide-shell-layout {
        width: 100vw;
        height: 100vh;
        display: flex;
        flex-direction: column;
        background: #12131e;
        overflow: hidden;
        box-sizing: border-box;
    }

    .ide-workspace-root {
        flex: 1;
        display: flex;
        position: relative;
        overflow: hidden;
        background: #12131e;
    }

    .debug-toolbar-bar {
        display: flex; align-items: center;
        padding: 6px 12px;
        background: linear-gradient(180deg, #1a1b2e 0%, #161728 100%);
        border-bottom: 1px solid var(--el-border-color-lighter, #25273f);
        flex-shrink: 0;
        gap: 12px;
    }

    .fixed-dock-left, .fixed-dock-right {
        width: 40px;
        height: 100%;
        background: #181926;
        flex-shrink: 0;
        z-index: 60;
        user-select: none;
        display: flex;
        flex-direction: column;
    }

    .fixed-dock-left {
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }

    .fixed-dock-right {
        border-left: 1px solid rgba(255, 255, 255, 0.05);
    }

    .fixed-dock-left :deep(.activity-bar) {
        flex: 1;
        border-right: none !important;
        width: 100%;
    }

    .bottom-toggle-dock {
        flex-shrink: 0;
        padding-bottom: 8px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        border-top: 1px solid rgba(255, 255, 255, 0.05);
        padding-top: 8px;
    }

    .activity-icon-item {
        width: 32px;
        height: 32px;
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

    .ide-middle-area {
        flex: 1;
        display: flex;
        flex-direction: column;
        position: relative;
        overflow: hidden;
        padding: 4px;
        box-sizing: border-box;
    }

    .ide-upper-row {
        flex: 1;
        display: flex;
        position: relative;
        overflow: hidden;
    }

    .ide-center-viewport {
        flex: 1;
        display: flex;
        flex-direction: column;
        position: relative;
        overflow: hidden;
        background: #2b2d3d;
    }

    .pane-content-inner {
        flex: 1;
        position: relative;
        overflow: hidden;
    }

    .ide-card-panel {
        border-radius: 8px !important;
        overflow: hidden !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.06) !important;
    }

    .splitter-v {
        width: 5px;
        height: 100%;
        cursor: col-resize;
        flex-shrink: 0;
        background: transparent;
        transition: background 0.2s ease;
        z-index: 10;
    }

        .splitter-v:hover {
            background: var(--el-color-primary);
        }

    .splitter-h {
        width: 100%;
        height: 5px;
        cursor: row-resize;
        flex-shrink: 0;
        background: transparent;
        transition: background 0.2s ease;
        z-index: 10;
    }

        .splitter-h:hover {
            background: var(--el-color-primary);
        }

    .ide-status-footer {
        height: 26px;
        background: #181926;
        border-top: 1px solid var(--el-border-color-light);
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 12px;
        font-size: 11px;
        color: var(--el-text-color-secondary);
        flex-shrink: 0;
        user-select: none;
        z-index: 1000;
    }

    .status-left, .status-right {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .status-dot {
        color: var(--el-color-primary);
        font-size: 10px;
    }

    .status-divider {
        color: var(--el-border-color-light);
    }
</style>
