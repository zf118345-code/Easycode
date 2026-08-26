<!-- frontend/src/layouts/IdeLayout.vue -->
<template>
    <div class="ide-shell-layout">
        <!-- 1. 顶部主菜单栏 -->
        <TopMenuBar
            :run-disabled="!canRunFromSelection"
            :run-disabled-reason="runDisabledReason"
            :recording-active="recordingState.active"
            :recording-frames="recordingState.frame_count || 0"
            :recording-fps="recordingState.average_fps || 0"
            :recording-disabled="store.isRunning || store.isPaused || recordingBusy"
            @run="handleRun"
            @open-project="handleOpenProject"
            @new-project="createDialogVisible = true"
            @close-project="handleCloseProject"
            @save-project="handleSaveProject"
            @export-config="handleExportConfig"
            @undo="handleUndo"
            @redo="handleRedo"
            @open-global-search="globalSearchVisible = true"
            @open-history="historyVisible = true"
            @auto-layout="handleAutoLayout"
            @open-docs="handleOpenDocs"
            @open-settings="settingsVisible = true"
            @open-schema-editor="schemaDialogVisible = true"
            @publish-package="openPublishCenter"
            @open-control-capture="openControlCapture"
            @open-hotkey-settings="hotkeySettingsVisible = true"
            @open-project-settings="projectSettingsVisible = true"
            @open-schedules="schedulesVisible = true"
            @open-screenshot="openGlobalScreenshot"
            @open-frame-replay="frameReplayVisible = true"
            @open-left-panel="openLeftPanel"
            @toggle-frame-recording="toggleFrameRecording" />

        <!-- 1.1 调试工具栏（工业级：▶⏸⏹⏭⏬⏫ + 断点统计 + 激活节点） -->
        <div v-if="store.isRunning || store.isPaused" class="debug-toolbar-bar">
            <DebugToolbar :recording-active="recordingState.active" />
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
                        <button
type="button"
                             class="activity-icon-item"
                             :class="{ 'is-active': store.uiState.bottomPanelExpanded && bottomActive === item.id }"
                             :aria-label="item.title"
                             :aria-pressed="store.uiState.bottomPanelExpanded && bottomActive === item.id"
                             @click="toggleBottomPanel(item.id)">
                            <component :is="item.icon" class="act-svg" />
                        </button>
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
                            <CanvasPage ref="canvasPageRef" />
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

        <!-- 3. 底部状态栏：只保留持续有决策价值的信息 -->
        <footer class="ide-status-footer">
            <div class="status-left">
                <span class="status-dot" :class="`is-${store.executionState}`">●</span>
                <span>{{ ideStatusLabel }}</span>
                <template v-if="recordingState.active">
                    <span class="status-divider">·</span>
                    <span class="recording-footer-status">帧录制 {{ recordingState.frame_count || 0 }} 帧 · {{ Number(recordingState.average_fps || 0).toFixed(1) }} FPS</span>
                    <button v-if="recordingState.recording_mode === 'diagnostic_events'" class="recording-mark-button" title="保留下一帧并写入诊断标记" @click="markRecordingFrame">
                        <Bookmark :size="12" /> 标记
                    </button>
                </template>
            </div>
            <div class="status-right">
                <span class="project-location" :title="store.currentProjectPath">{{ currentProjectName }}</span>
                <span class="status-divider">·</span>
                <span>{{ canvasModeLabel }}</span>
            </div>
        </footer>

        <!-- 面板设置弹窗 -->
        <PanelSettingsDialog v-model:visible="settingsVisible" @apply="handleApplyContext" />

        <!-- 客户表单配置与脚本包导出弹窗（顶栏「打包 (P)」菜单入口） -->
        <FormSchemaEditor v-model="schemaDialogVisible" :mode="schemaDialogMode" />
        <ProjectCreateDialog v-model="createDialogVisible" />

        <!-- 控件捕获工具（顶栏「运行 (R)」菜单入口；捕获结果 → 一键生成控件节点） -->
        <ControlCaptureTool
            v-model="controlCaptureVisible"
            :capture-event="captureEvent"
            :backend-connected="captureConnected"
            @node-requested="handleCaptureNodeRequested" />

        <!-- 全局快捷键设置（顶部「编辑 (E) → 快捷键设置」） -->
        <HotkeySettingsDialog v-model="hotkeySettingsVisible" />

        <!-- 项目设置（顶部「编辑 (E) → 项目设置」）：加载等待/弹窗/识别/引擎/日志 全局参数 -->
        <ProjectSettingsDialog v-model="projectSettingsVisible" />
        <GlobalSearchDialog v-model="globalSearchVisible" />
        <VersionHistoryDialog v-model="historyVisible" />
        <FrameReplayDialog v-model="frameReplayVisible" />
        <FrameRecordingStartDialog v-model="recordingStartVisible" :busy="recordingBusy" @confirm="startFrameRecording" />
    <PlatformScheduleDialog v-if="schedulesVisible" v-model="schedulesVisible" scope="ide" :tasks="runtimeEntryTasks" />
    </div>
</template>

<script setup>
    import { ref, computed, defineAsyncComponent, nextTick, onMounted, onUnmounted, watch } from 'vue'
    import { useIdeStore, useProjectStore, useUiStore } from '@/stores'
    import { ElMessage, ElMessageBox } from 'element-plus'

    import TopMenuBar from '@/components/shell/TopMenuBar.vue'
    import ActivityBar from '@/components/shell/ActivityBar.vue'
    import ToolWindow from '@/components/shell/ToolWindow.vue'
    import CanvasPage from '@/components/CanvasPage.vue'
    import PanelSettingsDialog from '@/components/PanelSettingsDialog.vue'
    import FormSchemaEditor from '@/components/schema/FormSchemaEditor.vue'
    import ControlCaptureTool from '@/components/ControlCaptureTool.vue'
    import HotkeySettingsDialog from '@/components/HotkeySettingsDialog.vue'
    import ProjectSettingsDialog from '@/components/ProjectSettingsDialog.vue'
    import ProjectCreateDialog from '@/components/ProjectCreateDialog.vue'
    import DebugToolbar from '@/components/DebugToolbar.vue'
    import GlobalSearchDialog from '@/components/GlobalSearchDialog.vue'
    import VersionHistoryDialog from '@/components/VersionHistoryDialog.vue'
    import FrameReplayDialog from '@/components/FrameReplayDialog.vue'
    import FrameRecordingStartDialog from '@/components/FrameRecordingStartDialog.vue'
    import { Bookmark } from 'lucide-vue-next'
    import { uiControlApi } from '@/api/uiControlApi'
    import { frameRecordingApi } from '@/api/frameRecordingApi'
    import { captureApi } from '@/api/captureApi'
    import client from '@/api/client'
    import { subscribeResourceMutations } from '@/utils/resourceMutationEvents'
    import { clearAssetPreviewCache } from '@/utils/assetPreview'
    import { useProjectEntryActions } from '@/composables/useProjectEntryActions'
    import { useRunFromSelection } from '@/composables/useRunFromSelection'

    const PlatformScheduleDialog = defineAsyncComponent(() => import('@/components/PlatformScheduleDialog.vue'))

    import { leftPanelsConfig, rightPanelsConfig, bottomPanelsConfig } from '@/config/panelsConfig'

    const store = useIdeStore()
    const projectStore = useProjectStore()
    const settingsVisible = ref(false)
    const schemaDialogVisible = ref(false)
    const schemaDialogMode = ref('configure')
    const createDialogVisible = ref(false)
    const controlCaptureVisible = ref(false)
    const hotkeySettingsVisible = ref(false)
    const projectSettingsVisible = ref(false)
    const globalSearchVisible = ref(false)
    const historyVisible = ref(false)
    const frameReplayVisible = ref(false)
    const recordingStartVisible = ref(false)
    const schedulesVisible = ref(false)
    const canvasPageRef = ref(null)
    const recordingState = ref({ active: false, status: 'idle', frame_count: 0, output_dir: '' })
    const recordingBusy = ref(false)
    let recordingEventSource = null
    let lastFinishedRecording = ''
    let externalChangeTimer = null
    let externalChangePromptActive = false

    const ideStatusLabel = computed(() => {
        if (!store.currentProjectPath) return '未打开项目'
        if (store.isRunning) return '正在执行'
        if (store.isPaused) return '调试暂停'
        if (store.executionState === 'error') return '执行失败'
        return '就绪'
    })
    const currentProjectName = computed(() => (store.currentProjectPath || '').split(/[/\\]/).pop() || '未打开项目')
    const canvasModeLabel = computed(() => ({ workflow: '主流程', function: '函数画布', topology: '页面地图' }[store.canvasMode] || '画布'))
    const runtimeEntryTasks = computed(() => [{ task_id: 'main', task_name: '主流程', ...(store.blueprint?.main_graph || {}) }])
    const { chooseAndOpenProject } = useProjectEntryActions()
    const handleOpenProject = () => chooseAndOpenProject()

    const handleCloseProject = async () => {
        try {
            await ElMessageBox.confirm('关闭当前项目并返回欢迎页？未完成的自动保存会先写入磁盘。', '关闭项目', {
                confirmButtonText: '关闭项目', cancelButtonText: '取消', type: 'info'
            })
            await projectStore.closeProject()
        } catch (err) {
            if (err !== 'cancel' && err !== 'close') ElMessage.error(err?.message || String(err))
        }
    }

    const handleSaveProject = async () => {
        if (!store.currentProjectPath) return ElMessage.warning('请先打开项目')
        try {
            await store.saveBlueprintImmediately()
            ElMessage.success('项目蓝图已保存')
        } catch (err) {
            ElMessage.error('保存失败: ' + (err?.message || err))
        }
    }

    const handleExportConfig = async () => {
        if (!store.currentProjectPath) return ElMessage.warning('请先打开项目')
        try {
            const result = await client.post('/api/exporter/config', { project_path: store.currentProjectPath })
            ElMessage.success(`配置已导出：${result.output_file}`)
        } catch (err) {
            ElMessage.error('导出配置失败: ' + (err?.message || err))
        }
    }

    const handleUndo = () => {
        if (!canvasPageRef.value?.undoCanvas()) ElMessage.info('当前画布没有可撤销的操作')
    }
    const handleRedo = () => {
        if (!canvasPageRef.value?.redoCanvas()) ElMessage.info('当前画布没有可重做的操作')
    }
    const handleAutoLayout = () => canvasPageRef.value?.openAutoLayout?.()
    const openPublishCenter = () => {
        schemaDialogMode.value = 'publish'
        schemaDialogVisible.value = true
    }
    watch(schemaDialogVisible, visible => {
        if (!visible) schemaDialogMode.value = 'configure'
    })

    const onGlobalShortcut = (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'p') {
            event.preventDefault()
            globalSearchVisible.value = true
        }
    }
    const handleOpenDocs = () => {
        const opened = window.open('/docs', '_blank', 'noopener,noreferrer')
        if (!opened) ElMessage.info('文档地址：/docs（浏览器拦截了新窗口）')
    }

    const applyRecordingState = (state) => {
        if (!state || typeof state !== 'object') return
        recordingState.value = { ...recordingState.value, ...state }
    }

    const stopFrameRecording = async (reason = 'api') => {
        if (recordingBusy.value) return
        recordingBusy.value = true
        try {
            const result = await frameRecordingApi.stop(reason)
            applyRecordingState(result)
            if (!result.active && result.session_id && result.session_id !== lastFinishedRecording) {
                lastFinishedRecording = result.session_id
                ElMessage.success(`逐帧录制已停止，共保存 ${result.frame_count || 0} 帧：${result.output_dir}`)
            }
        } catch (err) {
            ElMessage.error('停止逐帧录制失败: ' + (err?.message || err))
        } finally {
            recordingBusy.value = false
        }
    }

    const toggleFrameRecording = async () => {
        if (recordingState.value.active) {
            await stopFrameRecording('menu')
            return
        }
        if (!store.currentProjectPath) return ElMessage.warning('请先打开项目并配置工作面板')
        if (store.isRunning || store.isPaused) return ElMessage.warning('请先停止当前任务，再进入帧录制模式')
        recordingStartVisible.value = true
    }

    const startFrameRecording = async options => {
        if (recordingBusy.value) return
        recordingBusy.value = true
        try {
            const result = await frameRecordingApi.start(store.currentProjectPath, options)
            applyRecordingState(result)
            if (result.active) {
                recordingStartVisible.value = false
                ElMessage.success(`工作面板已激活，逐帧录制已开始；按 Esc 停止。首帧已保存到：${result.output_dir}`)
            }
        } catch (err) {
            ElMessage.error('逐帧录制启动失败: ' + (err?.message || err))
        } finally {
            recordingBusy.value = false
        }
    }

    const markRecordingFrame = async () => {
        try {
            await frameRecordingApi.mark('IDE 手动标记')
            ElMessage.success('已标记，下一帧将强制保留')
        } catch (error) {
            ElMessage.error(error?.message || '标记录制帧失败')
        }
    }

    const onRecordingEscape = (event) => {
        if (!recordingState.value.active || event.key !== 'Escape') return
        event.preventDefault()
        event.stopPropagation()
        event.stopImmediatePropagation?.()
        stopFrameRecording('esc_frontend')
    }

    function connectRecordingEvents() {
        if (recordingEventSource) return
        recordingEventSource = new EventSource('/api/frame-recording/events')
        recordingEventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)
                const wasActive = recordingState.value.active
                applyRecordingState(data)
                if (wasActive && !data.active && data.session_id && data.session_id !== lastFinishedRecording) {
                    lastFinishedRecording = data.session_id
                    if (data.status === 'error') {
                        ElMessage.error(`逐帧录制异常停止：${data.last_error || '未知错误'}；已保存 ${data.frame_count || 0} 帧`)
                    } else {
                        ElMessage.success(`逐帧录制已停止，共保存 ${data.frame_count || 0} 帧：${data.output_dir}`)
                    }
                }
            } catch { /* EventSource 会继续接收后续合法状态 */ }
        }
    }

    // ⚡ 顶栏「运行 (R) → 截图工具」：打开全局模板截图（框选 → 自动保存到项目 templates/）
    const openControlCapture = () => {
        if (store.isRunning || store.isPaused) return ElMessage.warning('请先停止当前任务')
        if (recordingState.value.active) return ElMessage.warning('请先停止逐帧录制')
        controlCaptureVisible.value = true
    }

    const openGlobalScreenshot = async () => {
        if (!store.currentProjectPath) {
            ElMessage.warning('请先打开一个项目，再使用截图工具')
            return
        }
        if (store.isRunning || store.isPaused) return ElMessage.warning('请先停止当前任务')
        if (recordingState.value.active) return ElMessage.warning('请先停止逐帧录制')
        try {
            await registerCaptureSession(true)
            await captureApi.trigger()
        } catch (error) {
            ElMessage.error(error?.message || '截图捕获启动失败')
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
    const captureSessionId = sessionStorage.getItem('easycodeCaptureSessionId') || `ide_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
    sessionStorage.setItem('easycodeCaptureSessionId', captureSessionId)
    let captureHeartbeat = null
    let captureRegisterTimer = null
    let capturePrewarmStarted = false
    let lastFocusAt = Date.now() / 1000

    async function registerCaptureSession(focused = false) {
        if (!store.currentProjectPath) return
        if (focused) lastFocusAt = Date.now() / 1000
        await nextTick()
        if (!canvasPageRef.value) return
        const context = canvasPageRef.value?.getCaptureContext?.() || {}
        await captureApi.registerSession({
            session_id: captureSessionId,
            project_path: store.currentProjectPath,
            workspace_id: projectStore.workspaceId,
            workspace_generation: projectStore.workspaceGeneration,
            project_name: store.currentProjectName,
            target_name: store.currentContext?.windowTitle || (store.currentContext?.workMode === 'desktop' ? '桌面工作区' : ''),
            canvas_mode: store.canvasMode,
            capture_context: context,
            execution_state: store.isPaused ? 'paused' : store.isRunning ? 'running' : (store.executionState || 'idle'),
            recording_active: Boolean(recordingState.value.active),
            origin: window.location.origin,
            last_focus_at: lastFocusAt
        })
        if (!capturePrewarmStarted) {
            capturePrewarmStarted = true
            captureApi.prewarm().catch(() => {
                // 真正进入捕获时会返回可见错误；预热失败不打断 IDE 编辑。
            })
        }
    }

    function scheduleCaptureRegistration() {
        clearTimeout(captureRegisterTimer)
        captureRegisterTimer = setTimeout(() => registerCaptureSession(false).catch(() => {}), 100)
    }

    async function handleCaptureCommand(data) {
        if (data.session_id && data.session_id !== captureSessionId) return
        let result
        try {
            if (data.kind === 'field_confirm') {
                result = await useUiStore().completeFieldCapture(data)
                result = { ok: true, ...(result || {}) }
            } else if (data.kind === 'field_cancel') {
                useUiStore().cancelFieldCapture(data.field_request_id || null)
                result = { ok: true }
            } else {
                if (!canvasPageRef.value) throw new Error('画布尚未就绪')
                result = await canvasPageRef.value.executeCaptureCommand(data)
            }
        } catch (error) {
            result = { ok: false, message: error?.message || String(error) }
        }
        await captureApi.acknowledgeAction(data.request_id, result).catch(() => {})
    }

    let captureCommandQueue = Promise.resolve()
    function enqueueCaptureCommand(data) {
        captureCommandQueue = captureCommandQueue
            .then(() => handleCaptureCommand(data))
            .catch(() => {})
    }

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
                } else if (data.event === 'screenshot-capture' && (!data.session_id || data.session_id === captureSessionId)) {
                    if (!data.native_host) {
                        ElMessage.error(data.message || '桌面捕获宿主未启动；已阻止浏览器内嵌降级')
                    }
                } else if (data.event === 'screenshot-error' && (!data.session_id || data.session_id === captureSessionId)) {
                    useUiStore().cancelFieldCapture()
                    ElMessage.error(data.message || '截图捕获失败')
                } else if (data.event === 'screenshot-focus' && !data.native_host && (!data.session_id || data.session_id === captureSessionId)) {
                    ElMessage.error(data.message || '桌面捕获宿主已退出，请重新进入截图捕获模式')
                } else if (data.event === 'mode-error') {
                    ElMessage.warning(data.message || '控件捕获模式启动失败')
                } else if (data.event === 'capture-command') {
                    enqueueCaptureCommand(data)
                }
            } catch { /* 忽略非法帧 */ }
        }
    }
    let unsubscribeResourceMutations = null

    const onResourceMutation = async (event) => {
        if (!event?.projectPath || event.projectPath !== projectStore.currentProjectPath) return
        if (event.phase === 'before') {
            projectStore.cancelPendingSaves()
            return
        }
        if (event.phase === 'complete') {
            try {
                projectStore.invalidateAssetPreviews()
                await projectStore.reloadAfterResourceMutation()
                await nextTick()
                clearAssetPreviewCache()
            } catch (error) {
                ElMessage.error(error.message || '资源变更后刷新项目失败，请重新打开项目')
            }
        }
    }

    const checkExternalProjectChanges = async () => {
        if (
            externalChangePromptActive
            || !projectStore.currentProjectPath
            || projectStore.workspaceBusy
            || store.isRunning
            || store.isPaused
            || recordingState.value.active
            || controlCaptureVisible.value
        ) return
        try {
            const result = await projectStore.checkExternalChanges()
            if (!result?.changed) return
            externalChangePromptActive = true
            const changed = (result.paths || []).slice(0, 5).join('、')
            if (result.identity_changed) {
                await ElMessageBox.alert(
                    '磁盘中的 project_id 已发生变化，当前编辑会话不能继续写入。EasyCode 将放弃未提交的旧会话修改，并以新项目身份重新打开此目录。',
                    '项目身份已更换',
                    { type: 'warning', confirmButtonText: '重新打开项目', closeOnClickModal: false }
                )
                await projectStore.reopenAfterExternalIdentityChange()
                ElMessage.warning('项目已按新的身份重新打开')
                return
            }
            if (!projectStore.hasPendingSaves()) {
                await projectStore.reloadExternalChanges()
                ElMessage.info(`检测到项目文件在外部变化，已重新载入${changed ? `：${changed}` : ''}`)
                return
            }
            try {
                await ElMessageBox.confirm(
                    `磁盘文件已在 EasyCode 外部修改，同时编辑器仍有待保存内容。变化：${changed || '项目文件'}。请选择要保留哪一份。`,
                    '项目文件冲突',
                    {
                        confirmButtonText: '重新载入磁盘',
                        cancelButtonText: '保留本地并覆盖',
                        distinguishCancelAndClose: true,
                        closeOnClickModal: false,
                        type: 'warning'
                    }
                )
                await projectStore.reloadExternalChanges()
                ElMessage.success('已重新载入磁盘版本，本地待保存修改已放弃')
            } catch (choice) {
                if (choice === 'cancel') {
                    await projectStore.keepLocalAfterExternalChange()
                    ElMessage.success('已保留编辑器版本并写回磁盘')
                }
            }
        } catch (error) {
            // Polling failures must not interrupt editing; normal API actions
            // still surface authoritative workspace errors.
        } finally {
            externalChangePromptActive = false
        }
    }

    const flushAutosaveBestEffort = () => {
        if (!projectStore.currentProjectPath || !projectStore.hasPendingSaves()) return
        projectStore.flushPendingSaves().catch(error => {
            console.error('页面离开前自动保存失败:', error)
        })
    }

    const onDocumentVisibilityChange = () => {
        if (document.visibilityState === 'hidden') flushAutosaveBestEffort()
    }

    onMounted(() => {
        unsubscribeResourceMutations = subscribeResourceMutations(onResourceMutation)
        connectCaptureEvents()
        connectRecordingEvents()
        window.addEventListener('keydown', onGlobalShortcut)
        window.addEventListener('keydown', onRecordingEscape, true)
        window.addEventListener('focus', onIdeFocus)
        window.addEventListener('pagehide', flushAutosaveBestEffort)
        document.addEventListener('visibilitychange', onDocumentVisibilityChange)
        registerCaptureSession(true).catch(() => {})
        captureHeartbeat = setInterval(() => registerCaptureSession(false).catch(() => {}), 30000)
        // 外部编辑检测是兜底保护，不应成为 IDE 的高频常驻负载。窗口重新
        // 获得焦点时立即检查，后台仅低频巡检一次。
        externalChangeTimer = setInterval(checkExternalProjectChanges, 10000)
    })
    onUnmounted(() => {
        unsubscribeResourceMutations?.()
        unsubscribeResourceMutations = null
        window.removeEventListener('keydown', onGlobalShortcut)
        window.removeEventListener('keydown', onRecordingEscape, true)
        window.removeEventListener('focus', onIdeFocus)
        window.removeEventListener('pagehide', flushAutosaveBestEffort)
        document.removeEventListener('visibilitychange', onDocumentVisibilityChange)
        flushAutosaveBestEffort()
        clearInterval(captureHeartbeat)
        clearInterval(externalChangeTimer)
        clearTimeout(captureRegisterTimer)
        captureApi.unregisterSession(captureSessionId).catch(() => {})
        if (captureEventSource) {
            captureEventSource.close()
            captureEventSource = null
        }
        if (recordingEventSource) {
            recordingEventSource.close()
            recordingEventSource = null
        }
    })

    function onIdeFocus() {
        lastFocusAt = Date.now() / 1000
        scheduleCaptureRegistration()
        checkExternalProjectChanges()
    }

    watch(
        () => [
            store.currentProjectPath,
            store.canvasMode,
            store.selectedNodeId,
            (store.selectedNodeIds || []).join(','),
            store.selectedGroupId,
            store.executionState,
            recordingState.value.active
        ],
        scheduleCaptureRegistration
    )

    // ⚡ 右侧面板：统一属性检查器（InspectorPanel 按 canvasMode 自动切换数据源，标题恒定）
    const rightActive = ref('inspector')
    const currentRightPanel = computed(() => {
        return rightPanelsConfig.find(p => p.id === rightActive.value)
    })

    const rightPanelTitle = computed(() => {
        return currentRightPanel.value?.title || '属性面板'
    })

    const leftPanelTitle = computed(() => {
        return currentLeftPanel.value?.title || '项目大纲'
    })

    // 左侧面板选项与切换（状态联动 store.uiState）
    const leftActive = ref('explorer')
    const currentLeftPanel = computed(() => leftPanelsConfig.find(p => p.id === leftActive.value))

    const openLeftPanel = async id => {
        if (!leftPanelsConfig.some(panel => panel.id === id)) return
        leftActive.value = id
        store.updateUiState('leftPanelExpanded', true)
        try {
            if (id === 'explorer') {
                await store.loadTaskData('main')
                await store.setCanvasMode('workflow')
            } else if (id === 'page-map') {
                await store.setCanvasMode('topology')
            }
        } catch (error) {
            ElMessage.error(error.message || '切换工作区失败')
        }
    }

    const toggleLeftPanel = async id => {
        if (leftActive.value === id && store.uiState.leftPanelExpanded) {
            store.updateUiState('leftPanelExpanded', false)
            return
        }
        await openLeftPanel(id)
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
            const newW = Math.max(200, Math.min(startW + dx, 600))
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
            const newW = Math.max(280, Math.min(startW + dx, 640))
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

    const {
        canRun: canRunFromSelection,
        disabledReason: runDisabledReason,
        runSelectedNode: handleRun
    } = useRunFromSelection({
        blocked: computed(() => recordingState.value.active),
        blockedReason: '请先停止逐帧录制'
    })

    const handleApplyContext = async (ctx) => {
        await store.setCurrentContext(ctx)
        ElMessage.success('工作面板切换成功')
    }
</script>

<style scoped>
.recording-mark-button {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 7px;
    border: 1px solid var(--el-color-danger-light-5);
    border-radius: 5px;
    background: transparent;
    color: var(--el-color-danger-light-3);
    font: inherit;
    cursor: pointer;
}
.recording-mark-button:hover { background: var(--el-color-danger-light-9); }
    .ide-shell-layout {
        width: 100vw;
        height: 100vh;
        display: flex;
        flex-direction: column;
        background: var(--el-bg-color-page);
        overflow: hidden;
        box-sizing: border-box;
    }

    .ide-workspace-root {
        flex: 1;
        display: flex;
        position: relative;
        overflow: hidden;
        background: var(--el-bg-color-page);
    }

    .debug-toolbar-bar {
        min-height: 38px;
        display: flex;
        align-items: center;
        padding: 0 12px;
        background: var(--app-chrome-bg);
        border-bottom: 1px solid var(--app-separator);
        flex-shrink: 0;
    }

    .fixed-dock-left, .fixed-dock-right {
        width: 40px;
        height: 100%;
        background: var(--app-sidebar-bg);
        flex-shrink: 0;
        z-index: 60;
        user-select: none;
        display: flex;
        flex-direction: column;
    }

    .fixed-dock-left {
        border-right: 1px solid var(--app-separator);
    }

    .fixed-dock-right {
        border-left: 1px solid var(--app-separator);
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
        border-top: 1px solid var(--app-separator);
        padding-top: 8px;
    }

    .activity-icon-item {
        width: 32px;
        height: 32px;
        border-radius: 7px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        color: var(--el-text-color-secondary);
        transition: background .14s ease, color .14s ease;
        padding: 0;
        border: 0;
        background: transparent;
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

    .ide-middle-area {
        flex: 1;
        display: flex;
        flex-direction: column;
        position: relative;
        overflow: hidden;
        padding: 0;
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
        background: var(--app-canvas-bg);
    }

    .pane-content-inner {
        flex: 1;
        position: relative;
        overflow: hidden;
    }

    .ide-card-panel {
        border-radius: 0 !important;
        overflow: hidden !important;
        box-shadow: none;
        border: none !important;
    }

    .splitter-v {
        width: 4px;
        height: 100%;
        cursor: col-resize;
        flex-shrink: 0;
        background: transparent;
        transition: background .14s ease;
        z-index: 10;
    }

        .splitter-v:hover {
            background: rgba(217, 84, 23, 0.78);
        }

    .splitter-h {
        width: 100%;
        height: 4px;
        cursor: row-resize;
        flex-shrink: 0;
        background: transparent;
        transition: background .14s ease;
        z-index: 10;
    }

        .splitter-h:hover {
            background: rgba(217, 84, 23, 0.78);
        }

    .ide-status-footer {
        height: 24px;
        background: var(--app-chrome-bg);
        border-top: 1px solid var(--app-separator);
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 10px;
        font-size: 10.5px;
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

    .status-dot.is-running { color: var(--el-color-success); }
    .status-dot.is-paused { color: var(--el-color-warning); }
    .status-dot.is-error { color: var(--el-color-danger); }
    .status-dot.is-stopped { color: var(--el-text-color-secondary); }

    .status-divider {
        color: var(--el-border-color-light);
    }

    .save-status.is-saving { color: var(--el-color-warning); }
    .save-status.is-saved { color: var(--el-color-success); }
    .save-status.is-error { color: var(--el-color-danger); font-weight: 600; }

    .recording-footer-status {
        color: var(--el-color-danger);
        font-weight: 600;
    }
</style>
