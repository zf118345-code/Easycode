<!-- frontend/src/views/PlayerView.vue -->
<template>
    <div class="player-container">
        <!-- 顶部状态栏 -->
        <div class="player-header">
            <div class="title-area">
                <span class="logo"><Bot :size="20" /></span>
                <span class="title">{{ formTitle || 'Easycode 自动化运行助手' }}</span>
                <el-tag size="small" type="success" effect="plain">Player 客户端</el-tag>
            </div>
            <div class="action-btns">
                <el-button type="success" size="default" :icon="Position" @click="handleRun" :loading="isRunning">
                    <Rocket :size="16" style="vertical-align: middle;" /> 开始运行自动化
                </el-button>
                <el-button type="danger" size="default" :icon="CircleClose" @click="handleStop" plain>
                    <Square :size="16" style="vertical-align: middle;" /> 停止
                </el-button>
            </div>
        </div>

        <!-- 主体区域：左侧动态配置表单，右侧实时运行日志 -->
        <div class="player-main">
            <!-- 左侧：根据 Schema 渲染的动态表单 -->
            <div class="form-panel">
                <div class="panel-title"><ClipboardList :size="16" style="vertical-align: middle;" /> 运行参数配置</div>
                <el-form label-position="right" label-width="140px" size="default" class="config-form">
                    <div v-for="(group, gIdx) in formSchema.groups" :key="gIdx" class="group-box">
                        <div class="group-name">{{ group.group_title }}</div>
                        <el-form-item v-for="(field, fIdx) in group.fields" :key="fIdx" :label="field.label">
                            <!-- 逻辑开关 -->
                            <template v-if="field.ui_type === 'switch'">
                                <el-switch v-model="userConfig.vars[field.target.replace('$var.', '')]" />
                            </template>
                            <!-- 数字调节 -->
                            <template v-else-if="field.ui_type === 'number' || field.ui_type === 'slider'">
                                <el-input-number v-model="userConfig.vars[field.target.replace('$var.', '')]" controls-position="right" style="width: 100%;" />
                            </template>
                            <!-- 下拉选择 -->
                            <template v-else-if="field.ui_type === 'select'">
                                <el-select v-model="userConfig.vars[field.target.replace('$var.', '')]" style="width: 100%;">
                                    <el-option v-for="opt in (providerOptions[field.provider] || [])" :key="opt.value" :label="opt.label" :value="opt.value" />
                                </el-select>
                            </template>
                            <!-- 默认字符串输入 -->
                            <template v-else>
                                <el-input v-model="userConfig.vars[field.target.replace('$var.', '')]" />
                            </template>
                        </el-form-item>
                    </div>
                    <!-- 兜底提示：如果 Schema 为空，显示友好提示 -->
                    <div v-if="!formSchema.groups || formSchema.groups.length === 0" class="empty-schema">
                        当前项目未配置动态表单参数 (form_schema)
                    </div>
                </el-form>
            </div>

            <!-- 右侧：控制台实时日志输出 -->
            <div class="log-panel">
                <div class="panel-title"><Monitor :size="16" style="vertical-align: middle;" /> 实时运行控制台</div>
                <div class="log-box" ref="logBoxRef">
                    <div v-for="(log, idx) in executionLogs" :key="idx" class="log-item">
                        <span class="log-time">[{{ log.time }}]</span>
                        <span class="log-msg">{{ log.message }}</span>
                    </div>
                    <div v-if="!executionLogs.length" class="empty-log">暂无运行日志输出...</div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
    import { ref, reactive, onMounted, nextTick } from 'vue'
    import { ElMessage } from 'element-plus'
    import { Position, CircleClose } from '@element-plus/icons-vue'
    import { Bot, Rocket, ClipboardList, Monitor, Square } from 'lucide-vue-next'
    import client from '@/api/client'

    const formTitle = ref('Easycode 客户端运行面板')
    const formSchema = reactive({ groups: [] })
    const userConfig = reactive({ vars: {}, ctx: {} })
    const providerOptions = reactive({})
    const executionLogs = ref([])
    const isRunning = ref(false)
    const logBoxRef = ref(null)
    let activeEventSource = null

    // 初始化加载内存密包
    const initPlayerSession = async () => {
        try {
            // ⚡ 工业级多项目动态寻址：自动获取浏览器本地存储中记录的当前项目路径并传给后端
            const currentPath = localStorage.getItem('lastProjectPath') || ''
            console.log('🔍 [PlayerView] 当前携带的项目路径:', currentPath)

            const res = await client.get('/api/player/init', {
                params: { project_path: currentPath }
            })
            console.log('🔍 [PlayerView] /api/player/init 完整响应:', res)

            const rawData = res?.data || res
            if (rawData) {
                const schema = rawData.form_schema || {}
                formTitle.value = schema.form_title || '自动化客户端'

                if (schema.groups && Array.isArray(schema.groups)) {
                    formSchema.groups = schema.groups
                }

                const config = rawData.user_config || {}
                if (config.vars) {
                    userConfig.vars = config.vars
                }

                ElMessage.success('📦 密包安全解密加载成功')
            }
        } catch (err) {
            console.error('❌ [PlayerView] 初始化失败:', err)
            ElMessage.error('初始化 Player 失败: ' + (err.message || err))
        }
    }

    // 触发运行
    const handleRun = async () => {
        try {
            // 先保存当前配置
            await client.post('/api/player/config', { user_config: userConfig })

            if (activeEventSource) {
                activeEventSource.close()
                activeEventSource = null
            }
            executionLogs.value = []
            isRunning.value = true

            const res = await client.post('/api/player/run')
            console.log('🚀 [PlayerView] /api/player/run 完整响应:', res)

            const rawData = res?.data || res
            const executionId = rawData?.execution_id || rawData?.data?.execution_id

            if (!executionId) {
                ElMessage.error('启动任务失败: 未获得 execution_id')
                executionLogs.value.push({ time: new Date().toLocaleTimeString(), message: '❌ 任务启动失败: 未获得 execution_id' })
                isRunning.value = false
                return
            }

            executionLogs.value.push({ time: new Date().toLocaleTimeString(), message: '🚀 自动化流程开始执行...' })

            const eventSource = new EventSource(`/api/execution/${executionId}/stream`)
            activeEventSource = eventSource

            eventSource.onmessage = (event) => {
                try {
                    const payload = JSON.parse(event.data)
                    const newLogs = payload.logs || []
                    const status = payload.status || {}

                    if (Array.isArray(newLogs)) {
                        newLogs.forEach(item => {
                            executionLogs.value.push(typeof item === 'string' ? { time: new Date().toLocaleTimeString(), message: item } : item)
                        })
                        nextTick(() => {
                            if (logBoxRef.value) logBoxRef.value.scrollTop = logBoxRef.value.scrollHeight
                        })
                    }

                    if (status.status === 'success' || status.status === 'error') {
                        executionLogs.value.push({ time: new Date().toLocaleTimeString(), message: status.status === 'success' ? '🎉 任务流程执行完毕 ✅' : `💥 异常终止: ${status.message}` })
                        eventSource.close()
                        activeEventSource = null
                        isRunning.value = false
                    }
                } catch (e) {
                    console.error('解析日志流错误', e)
                }
            }

            eventSource.onerror = () => {
                eventSource.close()
                activeEventSource = null
                isRunning.value = false
            }
        } catch (err) {
            console.error('❌ [PlayerView] 运行触发异常:', err)
            ElMessage.error('运行触发异常: ' + (err.message || err))
            executionLogs.value.push({ time: new Date().toLocaleTimeString(), message: `❌ 运行异常: ${err.message}` })
            isRunning.value = false
        }
    }

    const handleStop = async () => {
        try {
            await client.post('/api/player/stop')
            if (activeEventSource) {
                activeEventSource.close()
                activeEventSource = null
            }
            isRunning.value = false
            ElMessage.warning('已下发停止指令')
        } catch (err) {
            ElMessage.error('停止失败')
        }
    }

    onMounted(() => {
        initPlayerSession()
    })
</script>

<style scoped>
    .player-container {
        display: flex;
        flex-direction: column;
        height: 100vh;
        background-color: #121824;
        color: #e3e8f0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    .player-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 20px;
        background-color: #1a2234;
        border-bottom: 1px solid #2a344d;
    }

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
        padding: 16px;
        gap: 16px;
    }

    .form-panel, .log-panel {
        flex: 1;
        background-color: #1a2234;
        border: 1px solid #2a344d;
        border-radius: 8px;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .panel-title {
        padding: 12px 16px;
        font-size: 14px;
        font-weight: 600;
        border-bottom: 1px solid #2a344d;
        background-color: rgba(255,255,255,0.02);
    }

    .config-form {
        padding: 16px;
        overflow-y: auto;
        flex: 1;
    }

    .group-box {
        margin-bottom: 16px;
        padding: 12px;
        background: rgba(0,0,0,0.2);
        border-radius: 6px;
        border: 1px solid #2a344d;
    }

    .group-name {
        font-size: 13px;
        font-weight: 600;
        color: #409eff;
        margin-bottom: 12px;
    }

    .empty-schema {
        color: #606366;
        text-align: center;
        margin-top: 40px;
        font-size: 13px;
    }

    .log-box {
        flex: 1;
        background-color: #0d1117;
        padding: 12px;
        font-family: Consolas, Monaco, monospace;
        font-size: 12px;
        overflow-y: auto;
        color: #a9b7c6;
    }

    .log-item {
        margin-bottom: 4px;
        line-height: 1.5;
    }

    .log-time {
        color: #606366;
        margin-right: 8px;
    }

    .empty-log {
        color: #606366;
        text-align: center;
        margin-top: 40px;
    }
</style>