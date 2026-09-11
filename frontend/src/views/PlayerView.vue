<!-- frontend/src/views/PlayerView.vue -->
<template>
    <div class="player-container">
        <!-- 顶部状态栏 -->
        <div class="player-header">
            <div class="title-area pywebview-drag-region" @pointerdown.left="beginWindowDrag">
                <span class="logo"><Bot :size="20" /></span>
                <span class="title">{{ formTitle || 'EasyCode 自动化运行助手' }}</span>
            </div>
            <div class="action-btns">
                <el-select :model-value="currentInstanceId" size="small" class="instance-select" @change="switchInstance">
                    <el-option v-for="instance in instances" :key="instance.id" :label="instance.name" :value="instance.id">
                        <span>{{ instance.name }}</span><span class="instance-state">{{ statusLabels[instance.state] || instance.state }}</span>
                    </el-option>
                </el-select>
                <el-button size="small" circle title="新增并行实例" @click="addInstance"><Plus :size="14" /></el-button>
                <el-button v-if="instances.length > 1" size="small" circle title="删除当前实例" @click="removeInstance"><Minus :size="14" /></el-button>
                <el-button type="success" size="default" @click="handleRun(false)" :loading="isRunning">
                    <Rocket :size="16" style="vertical-align: middle;" /> 开始运行自动化
                </el-button>
                <el-button v-if="canResume" type="warning" size="default" @click="handleRun(true)">从恢复点继续</el-button>
                <el-button type="danger" size="default" :disabled="!isRunning" @click="handleStop" plain>
                    <Square :size="16" style="vertical-align: middle;" /> 停止
                </el-button>
                <div v-if="nativeWindowAvailable" class="window-controls">
                    <button type="button" title="最小化" @click="minimizeWindow"><Minus :size="15" /></button>
                    <button type="button" title="最大化/还原" @click="toggleMaximizeWindow"><Maximize2 :size="14" /></button>
                    <button type="button" class="close-window" title="关闭" @click="closeWindow"><X :size="15" /></button>
                </div>
            </div>
        </div>

        <!-- ⚡ 运行入口展示：打包时指定的起始节点（Player 只有一个运行按钮，入口由打包页配置） -->
        <div class="entry-bar">
            <Flag :size="14" style="vertical-align: middle;" />
            <span>运行入口：{{ entryInfo || '默认入口' }}</span>
            <span class="entry-spacer" />
            <el-select v-model="selectedProfile" size="small" clearable :disabled="profileBusy" placeholder="配置方案" style="width:150px" @change="applyProfile">
                <el-option v-for="profile in profiles" :key="profile.name" :label="profile.name" :value="profile.name" />
            </el-select>
            <el-button size="small" text :loading="profileBusy" @click="saveProfile">保存方案</el-button>
            <el-button size="small" text :disabled="!selectedProfile || profileBusy" @click="deleteProfile">删除方案</el-button>
            <el-button size="small" text @click="openEnvironment">环境自检</el-button>
            <el-dropdown trigger="click" @command="handlePlayerTool">
                <el-button size="small"><MoreHorizontal :size="15" />更多</el-button>
                <template #dropdown>
                    <el-dropdown-menu>
                        <el-dropdown-item command="schedules">计划任务</el-dropdown-item>
                        <el-dropdown-item command="runtime">运行服务</el-dropdown-item>
                        <el-dropdown-item command="diagnostics" divided>导出诊断包</el-dropdown-item>
                    </el-dropdown-menu>
                </template>
            </el-dropdown>
        </div>

        <div class="state-strip" :class="`state-${currentState}`">
            <span class="state-dot" />
            <strong>{{ stateLabel }}</strong>
            <span>{{ currentInstance.message || '等待操作' }}</span>
            <span v-if="currentInstance.executionId" class="execution-id">{{ currentInstance.executionId }}</span>
        </div>
        <div v-if="runtimeMetricItems.length" class="performance-strip">
            <span v-for="item in runtimeMetricItems" :key="item.label"><strong>{{ item.label }}</strong> {{ item.value }}</span>
        </div>

        <!-- 主体区域：左侧动态配置表单，右侧实时运行日志 -->
        <div class="player-main">
            <!-- 左侧：根据 Schema 渲染的动态表单 -->
            <div class="form-panel">
                <div class="panel-title"><ClipboardList :size="16" style="vertical-align: middle;" /> 运行参数配置</div>
                <div class="config-form">
                    <PlayerFormRenderer
                        v-if="formSchema.groups?.length"
                        ref="formRendererRef"
                        :schema="formSchema"
                        :user-config="userConfig"
                        @change="handleConfigChange" />
                    <!-- 兜底提示：如果 Schema 为空，显示友好提示 -->
                    <div v-if="!formSchema.groups || formSchema.groups.length === 0" class="empty-schema">
                        当前脚本无需额外运行参数
                    </div>
                </div>
            </div>

            <!-- 右侧：控制台实时日志输出 -->
            <div class="log-panel">
                <div class="panel-title"><Monitor :size="16" style="vertical-align: middle;" /> 实时运行控制台</div>
                <div class="log-box" ref="logBoxRef">
                    <div v-for="(log, idx) in executionLogs" :key="idx" class="log-item">
                        <span class="log-time">[{{ log.time }}]</span>
                        <span class="log-msg">{{ displayLogMessage(log.message) }}</span>
                    </div>
                    <div v-if="!executionLogs.length" class="empty-log">运行后将在这里显示日志</div>
                </div>
            </div>
        </div>

        <el-dialog v-model="environmentVisible" title="运行环境自检" width="680px" append-to-body>
            <el-alert
                :type="environmentReport.status === 'error' ? 'error' : environmentReport.status === 'warning' ? 'warning' : 'success'"
                :title="environmentSummary"
                :closable="false" />
            <div class="check-list">
                <div v-for="check in environmentReport.checks || []" :key="check.code + check.label" class="check-row">
                    <el-tag size="small" :type="check.status === 'pass' ? 'success' : check.status === 'warning' ? 'warning' : 'danger'">
                        {{ check.status === 'pass' ? '通过' : check.status === 'warning' ? '提醒' : '失败' }}
                    </el-tag>
                    <strong>{{ check.label }}</strong><span>{{ check.message }}</span>
                </div>
            </div>
            <template #footer><el-button @click="openEnvironment">重新检测</el-button><el-button type="primary" @click="environmentVisible = false">关闭</el-button></template>
        </el-dialog>
        <PlatformScheduleDialog
            v-if="schedulesVisible"
            v-model="schedulesVisible"
            scope="player"
            :instance-id="currentInstanceId"
            :profiles="profiles" />
        <el-dialog v-model="runtimeServicesVisible" title="运行服务" width="760px" append-to-body destroy-on-close>
            <div class="player-runtime-services"><RuntimeServicesPanel scope="player" :instance-id="currentInstanceId" :profiles="profiles" /></div>
        </el-dialog>
    </div>
</template>

<script setup>
    import { ref, reactive, computed, defineAsyncComponent, onMounted, onUnmounted, nextTick } from 'vue'
    import { ElMessage, ElMessageBox } from 'element-plus'
    import { Bot, Rocket, ClipboardList, Monitor, Square, Flag, Plus, Minus, Maximize2, X, MoreHorizontal } from 'lucide-vue-next'
    import client from '@/api/client'
    import PlayerFormRenderer from '@/components/player/PlayerFormRenderer.vue'
    import { buildPlayerConfig, normalizePlayerSchema } from '@/utils/playerSchema'

    const PlatformScheduleDialog = defineAsyncComponent(() => import('@/components/PlatformScheduleDialog.vue'))
    const RuntimeServicesPanel = defineAsyncComponent(() => import('@/components/panels/RuntimeServicesPanel.vue'))

    const formTitle = ref('EasyCode 客户端运行面板')
    const formSchema = reactive({ groups: [] })
    const userConfig = reactive({ vars: {}, ctx: {}, overrides: {} })
    const logBoxRef = ref(null)
    const entryInfo = ref('')
    const formRendererRef = ref(null)
    const hasWebViewBridge = () => Boolean(window.chrome?.webview?.postMessage)
    const nativeWindowAvailable = ref(Boolean(window.pywebview?.api) || hasWebViewBridge())
    const instances = reactive([{ id: 'instance-1', name: '实例 1', state: 'initializing', message: '正在初始化', executionId: null, canResume: false }])
    const currentInstanceId = ref('instance-1')
    const instanceLogs = reactive({ 'instance-1': [] })
    const instanceConfigs = reactive({})
    const eventSources = new Map()
    const profiles = ref([])
    const selectedProfile = ref('')
    const profileBusy = ref(false)
    const environmentVisible = ref(false)
    const schedulesVisible = ref(false)
    const runtimeServicesVisible = ref(false)
    const environmentReport = reactive({ status: 'warning', counts: {}, checks: [] })
    let statusPollTimer = null

    const statusLabels = {
        initializing: '初始化中', ready: '就绪', validating: '校验中', starting: '启动中',
        running: '运行中', stopping: '停止中', success: '已完成', error: '失败',
        stopped: '已停止', recovering: '恢复中'
    }
    const currentInstance = computed(() => instances.find(item => item.id === currentInstanceId.value) || instances[0])
    const currentState = computed(() => currentInstance.value?.state || 'initializing')
    const stateLabel = computed(() => statusLabels[currentState.value] || currentState.value)
    const isRunning = computed(() => ['validating', 'starting', 'running', 'stopping', 'recovering'].includes(currentState.value))
    const canResume = computed(() => Boolean(currentInstance.value?.canResume) && !isRunning.value)
    const executionLogs = computed(() => instanceLogs[currentInstanceId.value] || [])
    const formatMetricBytes = value => {
        const bytes = Number(value || 0)
        return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`
    }
    const runtimeMetricItems = computed(() => {
        const metrics = currentInstance.value?.runtimeMetrics || {}
        const worker = metrics.worker || {}
        const frames = metrics.frame_stream || {}
        const capture = metrics.capture || {}
        return [
            worker.pid ? { label: 'Worker', value: `#${worker.pid}` } : null,
            worker.cpu_percent != null ? { label: 'CPU', value: `${Number(worker.cpu_percent).toFixed(1)}%` } : null,
            worker.rss_bytes ? { label: '内存', value: formatMetricBytes(worker.rss_bytes) } : null,
            (frames.provider || capture.provider) ? { label: '采帧', value: frames.provider || capture.provider } : null,
            frames.average_capture_ms != null ? { label: '截图', value: `${Number(frames.average_capture_ms).toFixed(1)} ms` } : null,
            frames.latest_frame_age_ms != null ? { label: '帧龄', value: `${Number(frames.latest_frame_age_ms).toFixed(1)} ms` } : null,
            frames.overwritten_frames ? { label: '覆盖帧', value: String(frames.overwritten_frames) } : null,
        ].filter(Boolean)
    })
    const displayLogMessage = message => {
        const decorations = ['✅', '❌', '⚠️', '⚠', '🎯', '🚀', '📋', '🔍', '📏', '💥', '🎉', '🔨', '♻️', '♻', '⚡']
        return decorations.reduce((text, icon) => text.split(icon).join(''), String(message || '')).trimStart()
    }
    const environmentSummary = computed(() => {
        const counts = environmentReport.counts || {}
        return counts.error ? `${counts.error} 项失败，暂不能运行` : counts.warning ? `检查通过，另有 ${counts.warning} 项提醒` : '所有检查均已通过'
    })
    const handlePlayerTool = command => {
        if (command === 'schedules') schedulesVisible.value = true
        if (command === 'runtime') runtimeServicesVisible.value = true
        if (command === 'diagnostics') downloadDiagnostics()
    }

    // ⚡ Player 日志条数上限（与 IDE 执行日志一致）：防止长任务 DOM 无限增长卡死
    const MAX_EXECUTION_LOGS = 500

    const replaceConfig = (nextConfig) => {
        for (const slot of ['vars', 'ctx', 'overrides']) {
            Object.keys(userConfig[slot]).forEach(key => delete userConfig[slot][key])
            Object.assign(userConfig[slot], nextConfig[slot] || {})
        }
    }

    const handleConfigChange = (nextConfig) => replaceConfig(nextConfig)

    const cloneConfig = () => JSON.parse(JSON.stringify(userConfig))
    const rememberCurrentConfig = () => { instanceConfigs[currentInstanceId.value] = cloneConfig() }
    const switchInstance = (instanceId) => {
        rememberCurrentConfig()
        currentInstanceId.value = instanceId
        if (!instanceLogs[instanceId]) instanceLogs[instanceId] = []
        replaceConfig(instanceConfigs[instanceId] || instanceConfigs['instance-1'] || { vars: {}, ctx: {}, overrides: {} })
    }
    const addInstance = () => {
        rememberCurrentConfig()
        const id = `instance-${Date.now()}`
        instances.push({ id, name: `实例 ${instances.length + 1}`, state: 'ready', message: '就绪', executionId: null, canResume: false })
        instanceLogs[id] = []
        instanceConfigs[id] = cloneConfig()
        currentInstanceId.value = id
        ElMessage.success('已创建独立运行实例')
    }
    const removeInstance = async () => {
        const instance = currentInstance.value
        if (!instance || instance.id === 'instance-1') return
        try {
            await client.delete(`/api/player/instances/${encodeURIComponent(instance.id)}`)
            eventSources.get(instance.id)?.close()
            eventSources.delete(instance.id)
            const index = instances.findIndex(item => item.id === instance.id)
            instances.splice(index, 1)
            delete instanceLogs[instance.id]
            delete instanceConfigs[instance.id]
            switchInstance(instances[0].id)
        } catch {
            ElMessage.error(err.message || '删除实例失败')
        }
    }

    const updateInstanceStatus = (instanceId, status) => {
        let instance = instances.find(item => item.id === instanceId)
        if (!instance) {
            instance = { id: instanceId, name: `实例 ${instances.length + 1}` }
            instances.push(instance)
        }
        instance.state = status.state || instance.state || 'ready'
        instance.message = status.message || instance.message || ''
        instance.executionId = status.execution_id || status.executionId || instance.executionId || null
        instance.canResume = Boolean(status.can_resume)
        instance.runtimeMetrics = status.runtime_metrics || instance.runtimeMetrics || {}
    }

    let statusPollInFlight = false
    const pollStatuses = async () => {
        if (statusPollInFlight) return
        statusPollInFlight = true
        try {
            await Promise.all([...instances].map(async instance => {
                try {
                    const status = await client.get('/api/player/status', { params: { instance_id: instance.id } })
                    updateInstanceStatus(instance.id, status?.data || status)
                } catch { /* 初始化前或后端退出时保持最后状态 */ }
            }))
        } finally {
            statusPollInFlight = false
        }
    }

    const loadProfiles = async () => {
        const response = await client.get('/api/player/profiles')
        profiles.value = (response?.data || response)?.profiles || []
    }

    // 初始化加载内存密包
    const initPlayerSession = async () => {
        try {
            // Player only opens the bundle fixed by its executable/development
            // environment. It never reads IDE recent-project state.
            const res = await client.get('/api/player/init')

            const rawData = res?.data || res
            if (rawData) {
                const schema = normalizePlayerSchema(rawData.form_schema || {})
                formTitle.value = schema.form_title || '自动化客户端'
                replaceConfig(buildPlayerConfig(schema, rawData.user_config || {}))
                instanceConfigs['instance-1'] = cloneConfig()
                Object.keys(formSchema).forEach(key => delete formSchema[key])
                Object.assign(formSchema, schema)

                // ⚡ 运行入口展示：打包时在打包页指定的起始节点
                const entry = schema.entry
                if (entry && entry.node_name) {
                    entryInfo.value = `${entry.node_name || entry.node_id}`
                }

                if (rawData.runtime_status) updateInstanceStatus('instance-1', rawData.runtime_status)
                else updateInstanceStatus('instance-1', { state: 'ready', message: '脚本资源已就绪' })
                if (rawData.environment) Object.assign(environmentReport, rawData.environment)
                await loadProfiles()

                ElMessage.success('密包已安全解密并加载')
            }
        } catch (err) {
            updateInstanceStatus('instance-1', { state: 'error', message: err.message || String(err) })
            ElMessage.error('初始化 Player 失败: ' + (err.message || err))
        }
    }

    // 触发运行
    const handleRun = async (resume = false) => {
        const instanceId = currentInstanceId.value
        const instance = currentInstance.value
        const logs = instanceLogs[instanceId] || (instanceLogs[instanceId] = [])
        try {
            const validation = formRendererRef.value?.validate()
            if (validation && !validation.valid) {
                ElMessage.error(validation.errors[0]?.message || '请检查运行参数')
                return
            }
            if (validation?.config) replaceConfig(validation.config)
            instanceConfigs[instanceId] = cloneConfig()
            // 先保存当前配置
            await client.post('/api/player/config', { user_config: userConfig, instance_id: instanceId })

            eventSources.get(instanceId)?.close()
            eventSources.delete(instanceId)
            logs.splice(0)
            updateInstanceStatus(instanceId, { state: resume ? 'recovering' : 'starting', message: resume ? '正在恢复' : '正在启动' })

            const res = await client.post('/api/player/run', { instance_id: instanceId, resume })
            console.debug('[PlayerView] /api/player/run 响应:', res)

            const rawData = res?.data || res
            const executionId = rawData?.execution_id || rawData?.data?.execution_id

            if (!executionId) {
                ElMessage.error('启动任务失败: 未获得 execution_id')
                logs.push({ time: new Date().toLocaleTimeString(), level: 'error', message: '任务启动失败: 未获得 execution_id' })
                updateInstanceStatus(instanceId, { state: 'error', message: '未获得 execution_id' })
                return
            }

            updateInstanceStatus(instanceId, { state: 'running', message: '自动化正在运行', execution_id: executionId })
            logs.push({ time: new Date().toLocaleTimeString(), level: 'info', message: resume ? '已从恢复点继续执行…' : '自动化流程开始执行…' })

            const eventSource = new EventSource(`/api/execution/${executionId}/stream`)
            eventSources.set(instanceId, eventSource)

            eventSource.onmessage = (event) => {
                try {
                    const payload = JSON.parse(event.data)
                    const newLogs = payload.logs || []
                    const status = payload.status || {}

                    if (Array.isArray(newLogs)) {
                        newLogs.forEach(item => {
                            logs.push(typeof item === 'string' ? { time: new Date().toLocaleTimeString(), message: item } : item)
                        })
                        // ⚡ 截断到上限，防止长任务 DOM/内存无限增长（与 IDE 一致）
                        if (logs.length > MAX_EXECUTION_LOGS) {
                            logs.splice(0, logs.length - MAX_EXECUTION_LOGS)
                        }
                        nextTick(() => {
                            if (logBoxRef.value) logBoxRef.value.scrollTop = logBoxRef.value.scrollHeight
                        })
                    }

                    if (['success', 'error', 'stopped'].includes(status.status)) {
                        const message = status.status === 'success' ? '任务流程执行完毕'
                            : status.status === 'stopped' ? '任务已停止'
                                : `异常终止: ${status.message}`
                        logs.push({ time: new Date().toLocaleTimeString(), message })
                        eventSource.close()
                        eventSources.delete(instanceId)
                        updateInstanceStatus(instanceId, { state: status.status, message: status.message, execution_id: executionId })
                        pollStatuses()
                    }
                } catch (e) {
                    console.error('解析日志流错误', e)
                }
            }

            eventSource.onerror = () => {
                eventSource.close()
                eventSources.delete(instanceId)
                if (instance.state === 'running') updateInstanceStatus(instanceId, { state: 'error', message: '日志连接中断' })
            }
        } catch (err) {
            console.error('[PlayerView] 运行触发异常:', err)
            ElMessage.error('运行触发异常: ' + (err.message || err))
            logs.push({ time: new Date().toLocaleTimeString(), level: 'error', message: `运行异常: ${err.message}` })
            updateInstanceStatus(instanceId, { state: 'error', message: err.message || String(err) })
            await pollStatuses()
        }
    }

    const handleStop = async () => {
        const instanceId = currentInstanceId.value
        try {
            updateInstanceStatus(instanceId, { state: 'stopping', message: '正在停止' })
            await client.post('/api/player/stop', { instance_id: instanceId })
            eventSources.get(instanceId)?.close()
            eventSources.delete(instanceId)
            updateInstanceStatus(instanceId, { state: 'stopped', message: '用户主动停止' })
            ElMessage.warning('已下发停止指令')
        } catch (err) {
            ElMessage.error('停止失败')
        }
    }

    const openEnvironment = async () => {
        try {
            const response = await client.get('/api/player/environment', { params: { instance_id: currentInstanceId.value } })
            Object.assign(environmentReport, response?.data || response)
            environmentVisible.value = true
        } catch (err) {
            ElMessage.error(err.message || '环境自检失败')
        }
    }
    const saveProfile = async () => {
        if (profileBusy.value) return
        try {
            const { value } = await ElMessageBox.prompt('保存当前运行参数，之后可一键切换。', '保存配置方案', {
                inputValue: selectedProfile.value || '',
                inputPlaceholder: '例如：测试服-账号A',
                inputValidator: value => value?.trim() && value.trim().length <= 64 ? true : '请输入 1-64 字符名称'
            })
            profileBusy.value = true
            await client.post('/api/player/profiles', { name: value.trim(), user_config: cloneConfig() })
            selectedProfile.value = value.trim()
            await loadProfiles()
            ElMessage.success('配置方案已保存')
        } catch (err) {
            if (err === 'cancel' || err === 'close') return
            ElMessage.error(err.message || '保存方案失败')
        } finally {
            profileBusy.value = false
        }
    }
    const applyProfile = async (name) => {
        if (!name || profileBusy.value) return
        profileBusy.value = true
        try {
            const response = await client.post(`/api/player/profiles/${encodeURIComponent(name)}/apply`, { instance_id: currentInstanceId.value })
            const data = response?.data || response
            replaceConfig(data.user_config || {})
            instanceConfigs[currentInstanceId.value] = cloneConfig()
            ElMessage.success(`已应用配置方案「${name}」`)
        } catch (err) {
            ElMessage.error(err.message || '应用方案失败')
        } finally {
            profileBusy.value = false
        }
    }
    const deleteProfile = async () => {
        if (!selectedProfile.value || profileBusy.value) return
        try {
            await ElMessageBox.confirm(`确定删除配置方案「${selectedProfile.value}」吗？`, '删除方案', { type: 'warning' })
            profileBusy.value = true
            await client.delete(`/api/player/profiles/${encodeURIComponent(selectedProfile.value)}`)
            selectedProfile.value = ''
            await loadProfiles()
            ElMessage.success('配置方案已删除')
        } catch (err) {
            const action = String(err?.action || err || '').toLowerCase()
            if (!['cancel', 'close'].includes(action)) ElMessage.error(err?.message || '删除方案失败')
        } finally {
            profileBusy.value = false
        }
    }
    const downloadDiagnostics = () => {
        window.open(`/api/player/diagnostics?instance_id=${encodeURIComponent(currentInstanceId.value)}`, '_blank')
    }

    const nativeWindowCall = async (method) => {
        if (hasWebViewBridge()) {
            const command = method === 'toggle_maximize' ? 'maximize' : method
            window.chrome.webview.postMessage({ event: 'window-command', version: 1, command })
            return
        }
        const api = window.pywebview?.api
        if (!api?.[method]) return
        try {
            await api[method]()
        } catch (err) {
            ElMessage.error(`窗口操作失败: ${err?.message || err}`)
        }
    }
    const minimizeWindow = () => nativeWindowCall('minimize')
    const toggleMaximizeWindow = () => nativeWindowCall('toggle_maximize')
    const closeWindow = () => nativeWindowCall('close')
    const beginWindowDrag = (event) => {
        if (!hasWebViewBridge() || event.button !== 0) return
        nativeWindowCall('drag')
    }
    const markNativeWindowReady = () => {
        nativeWindowAvailable.value = Boolean(window.pywebview?.api) || hasWebViewBridge()
    }
    const handleNativeMessage = (event) => {
        if (event?.data?.event === 'desktop-shell-ready' || event?.data?.event === 'desktop-window-state') {
            nativeWindowAvailable.value = true
        }
    }

    onMounted(() => {
        window.addEventListener('pywebviewready', markNativeWindowReady)
        window.chrome?.webview?.addEventListener?.('message', handleNativeMessage)
        markNativeWindowReady()
        initPlayerSession()
        statusPollTimer = window.setInterval(pollStatuses, 1200)
    })
    onUnmounted(() => {
        window.removeEventListener('pywebviewready', markNativeWindowReady)
        window.chrome?.webview?.removeEventListener?.('message', handleNativeMessage)
        if (statusPollTimer) window.clearInterval(statusPollTimer)
        eventSources.forEach(source => source.close())
        eventSources.clear()
    })
</script>

<style scoped>
    .player-container {
        display: flex;
        flex-direction: column;
        height: 100vh;
        background-color: var(--el-bg-color-page);
        color: var(--el-text-color-primary);
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'PingFang SC', 'Segoe UI', sans-serif;
    }

    .player-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        min-height: 48px;
        padding: 8px 14px;
        background: var(--app-bg-chrome);
        border-bottom: 1px solid var(--app-separator);
    }

    .action-btns, .window-controls {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .instance-select { width: 132px; }
    .instance-state { float: right; margin-left: 18px; color: var(--el-text-color-secondary); font-size: 11px; }

    .window-controls {
        margin-left: 6px;
        padding-left: 10px;
        border-left: 1px solid var(--app-separator);
    }

    .window-controls button {
        width: 30px;
        height: 28px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border: 0;
        border-radius: 6px;
        color: var(--el-text-color-regular);
        background: transparent;
        cursor: pointer;
    }

.window-controls button:hover { background: color-mix(in srgb, var(--app-text-primary) 10%, transparent); }
.window-controls .close-window:hover { background: var(--app-color-danger); color: var(--app-color-on-primary); }

    .entry-bar {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 6px 20px;
        font-size: 12px;
        color: var(--el-text-color-regular);
        background-color: var(--app-bg-sidebar);
        border-bottom: 1px solid var(--app-separator);
    }
    .entry-spacer { flex: 1; }

    .state-strip {
        display: flex; align-items: center; gap: 8px; padding: 7px 20px;
        background: var(--app-bg-sidebar); border-bottom: 1px solid var(--app-separator);
        color: var(--el-text-color-secondary); font-size: 12px;
    }
    .state-strip strong { color: var(--el-text-color-primary); }
    .performance-strip { display:flex; flex-wrap:wrap; gap:14px; padding:5px 20px; background:var(--app-bg-base); border-bottom:1px solid var(--app-separator); color:var(--el-text-color-secondary); font-size:11px; }
    .performance-strip strong { color:var(--el-text-color-regular); font-weight:600; }
.state-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--app-text-placeholder); }
.state-running .state-dot, .state-starting .state-dot, .state-validating .state-dot, .state-recovering .state-dot { background:var(--app-color-warning); box-shadow:0 0 0 3px var(--app-color-warning-soft); }
.state-success .state-dot, .state-ready .state-dot { background:var(--app-color-success); }
.state-error .state-dot { background:var(--app-color-danger); }
.execution-id { margin-left:auto; color:var(--app-text-placeholder); font-family:var(--app-font-mono); }
    .check-list { display:flex; flex-direction:column; gap:8px; margin-top:14px; }
    .check-row { display:grid; grid-template-columns:56px 100px 1fr; align-items:center; gap:8px; padding:9px; border:1px solid var(--el-border-color); border-radius:6px; }
    .check-row span:last-child { color:var(--el-text-color-secondary); overflow-wrap:anywhere; }

    .title-area {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 16px;
        font-weight: 600;
    }

    .player-main {
        display: flex;
        flex: 1;
        overflow: hidden;
        padding: 10px;
        gap: 10px;
    }

    .form-panel, .log-panel {
        flex: 1;
        background-color: var(--app-bg-panel);
        border: 1px solid var(--app-border-default);
        border-radius: 8px;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .panel-title {
        padding: 12px 16px;
        font-size: 14px;
        font-weight: 600;
        border-bottom: 1px solid var(--app-separator);
        background-color: var(--app-bg-sidebar);
    }

    .config-form {
        padding: 16px;
        overflow-y: auto;
        flex: 1;
    }

    .group-box {
        margin-bottom: 16px;
        padding: 12px;
    background: color-mix(in srgb, var(--app-bg-base) 72%, transparent);
        border-radius: 6px;
    border: 1px solid var(--app-border-default);
    }

    .group-name {
        font-size: 13px;
        font-weight: 600;
    color: var(--app-color-success);
        margin-bottom: 12px;
    }

    .empty-schema {
    color: var(--app-text-placeholder);
        text-align: center;
        margin-top: 40px;
        font-size: 13px;
    }

    .log-box {
        flex: 1;
        background-color: var(--app-bg-input);
        padding: 12px;
        font-family: 'SFMono-Regular', Consolas, Monaco, monospace;
        font-size: 12px;
        overflow-y: auto;
    color: var(--app-text-regular);
    }

    .log-item {
        margin-bottom: 4px;
        line-height: 1.5;
    }

    .log-time {
    color: var(--app-text-placeholder);
        margin-right: 8px;
    }

    .empty-log {
    color: var(--app-text-placeholder);
        text-align: center;
        margin-top: 40px;
    }

    .player-runtime-services {
        height: min(68vh, 680px);
        min-height: 460px;
        overflow: hidden;
        border: 1px solid var(--app-separator);
        border-radius: 8px;
    }

    @media (max-width: 920px) {
        .player-header { align-items:flex-start; }
        .title-area .title { max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .action-btns { flex-wrap:wrap; justify-content:flex-end; }
        .entry-bar { flex-wrap:wrap; }
        .entry-spacer { display:none; }
        .player-main { flex-direction:column; overflow:auto; }
        .form-panel,.log-panel { min-height:320px; flex:0 0 auto; }
    }
    @media (max-width: 620px) {
        .player-header { padding:7px 9px; }
        .title-area .title { display:none; }
        .instance-select { width:110px; }
        .window-controls { display:none; }
        .entry-bar,.state-strip,.performance-strip { padding-left:10px; padding-right:10px; }
        .entry-bar > span:first-of-type { max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .performance-strip { gap:8px; }
    }
</style>
