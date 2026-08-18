<!-- frontend/src/components/ControlCaptureTool.vue
  控件捕获模式（控制面板版，无快照模态）：
  - 进入捕获模式：系统禁止打字/鼠标点击（后端低级钩子），鼠标移动可用
  - 模式激活时前端实时轮询识别鼠标下控件 → 上报全局高亮（框 + 鼠标旁标签）
  - Ctrl+Shift+Enter（可配置）复制选择器 + 生成控件节点；模式不退出，可连续捕获；Esc 退出
  - 面板展示实时识别信息 + 最近捕获结果 + 当前快捷键配置
-->
<template>
    <el-dialog
        v-model="dialogVisible"
        title="控件捕获模式"
        width="420px"
        append-to-body
        :close-on-click-modal="false"
        @closed="stopAll">
        <div class="ctrl-capture-body">
            <div class="capture-tip">
                <b>控件捕获模式</b>：<b>不拦截任何输入</b>，可正常操作任意应用。
                <b>鼠标悬停在目标控件上 250ms</b> 自动识别并高亮（同一位置停留再久也只识别一次）；
                识别后按 <b>{{ fmt(copyCombo) }}</b> 生成控件节点（高亮自动清除，<b>模式不退出，可连续捕获</b>），
                <b>{{ fmt(exitCombo) }}</b> 退出。
            </div>

            <!-- 模式状态 + 快捷键说明 -->
            <div class="mode-status" :class="{ 'is-active': active, 'is-down': !backendConnected }">
                <span class="status-dot" />
                <span v-if="!backendConnected">⛔ 后端连接中断，捕获模式已失效（请重启后端后重试）</span>
                <span v-else>{{ active ? '● 捕获模式运行中（悬停自动识别）' : '○ 未激活' }}</span>
                <span v-if="!hotkeyOk" class="hotkey-warn" title="全局热键可能被其他软件占用">热键冲突</span>
            </div>

            <div class="hotkey-list">
                <div class="hk-row">
                    <kbd>{{ fmt(enterCombo) }}</kbd><span>进入捕获模式（全局）</span>
                </div>
                <div class="hk-row">
                    <kbd>{{ fmt(copyCombo) }}</kbd><span>复制选择器 + 生成控件节点（仅模式期间）</span>
                </div>
                <div class="hk-row">
                    <kbd>{{ fmt(exitCombo) }}</kbd><span>退出捕获模式（仅模式期间）</span>
                </div>
                <div class="hk-row hint">如需修改，见顶部「编辑 (E) → 快捷键设置」</div>
            </div>

            <!-- 实时识别信息 -->
            <div v-if="active" class="capture-list">
                <div class="cap-row">
                    <span class="cap-label">元素名称</span>
                    <span class="cap-value" :title="control.name">{{ control.name || '—' }}</span>
                </div>
                <div class="cap-row">
                    <span class="cap-label">控件类型</span>
                    <span class="cap-value mono">{{ control.control_type || '—' }}</span>
                </div>
                <div class="cap-row">
                    <span class="cap-label">选择器</span>
                    <code class="sel-code">{{ selector || '—' }}</code>
                </div>
            </div>

            <!-- 最近捕获结果 -->
            <div v-if="lastResult" class="capture-result">
                <div class="res-header">最近捕获 {{ nodeCreatedTip ? '· 已生成控件节点' : '' }}</div>
                <div class="cap-row">
                    <span class="cap-label">选择器</span>
                    <code class="sel-code">{{ lastResult.selector || '—' }}</code>
                </div>
            </div>
        </div>

        <template #footer>
            <el-button size="small" @click="dialogVisible = false">关闭</el-button>
            <el-button v-if="!active" size="small" type="primary" @click="startMode">
                进入捕获模式
            </el-button>
            <el-button v-else size="small" type="danger" plain @click="stopMode">
                退出模式 ({{ fmt(exitCombo) }})
            </el-button>
        </template>
    </el-dialog>
</template>

<script setup>
    import { ref, computed, watch, onUnmounted } from 'vue'
    import { ElMessage } from 'element-plus'
    import { uiControlApi } from '@/api/uiControlApi'

    const props = defineProps({
        modelValue: { type: Boolean, default: false },
        // ⚡ SSE 捕获事件（由 IdeLayout 的 EventSource 转发）：前端零轮询，全部由后端事件驱动
        captureEvent: { type: Object, default: null },
        backendConnected: { type: Boolean, default: true }   // SSE 连接状态（断开明示，防假激活穿透）
    })
    const emit = defineEmits(['update:modelValue', 'node-requested'])

    const dialogVisible = computed({
        get: () => props.modelValue,
        set: (val) => emit('update:modelValue', val)
    })

    const active = ref(false)
    const hotkeyOk = ref(true)
    const control = ref({})
    const lastResult = ref(null)
    const nodeCreatedTip = ref(false)
    const enterCombo = ref('Ctrl+Shift+C')
    const copyCombo = ref('Ctrl+Shift+Enter')
    const exitCombo = ref('Esc')

    const fmt = (c) => String(c || '').toUpperCase()
    const selector = computed(() => {
        const t = control.value
        if (!t) return ''
        if (t.name) return `name="${t.name}"`
        if (t.control_type) return `type="${t.control_type}"`
        if (t.automation_id) return `id="${t.automation_id}"`
        if (t.class_name) return `class="${t.class_name}"`
        return ''
    })

    // ===== SSE 捕获事件消费（零轮询：点击/滚轮/右键/复制/模式状态全部由后端推送） =====
    watch(() => props.captureEvent, (ev) => {
        if (!ev) return
        if (ev.event === 'mode') {
            active.value = !!ev.active
            if (ev.active) {
                lastResult.value = null
                nodeCreatedTip.value = false
            }
            return
        }
        if (ev.event === 'clear') {
            control.value = {}
            lastResult.value = null
            nodeCreatedTip.value = false
            return
        }
        if (ev.event === 'select' || ev.event === 'wheel') {
            active.value = true  // 能收到选中/层级事件说明模式在运行
            control.value = ev.info || {}
            lastResult.value = null
            nodeCreatedTip.value = false
            return
        }
        if (ev.event === 'copy') {
            lastResult.value = ev
            nodeCreatedTip.value = true
            emit('node-requested', ev.info || {})
        }
    }, { immediate: true })

    let hotkeysLoaded = false
    async function loadHotkeysIfNeeded() {
        if (hotkeysLoaded) return
        hotkeysLoaded = true
        try {
            const res = await uiControlApi.getHotkeys()
            if (res?.hotkeys) {
                enterCombo.value = res.hotkeys.enter_capture || 'ctrl+shift+c'
                copyCombo.value = res.hotkeys.copy_generate || 'ctrl+shift+enter'
                exitCombo.value = res.hotkeys.exit_mode || 'esc'
            }
        } catch { /* 静默 */ }
    }

    // ===== 控制（一次性请求，非轮询） =====
    async function startMode() {
        try {
            const res = await uiControlApi.modeControl('start')
            if (res?.ok) {
                active.value = !!res.active
                lastResult.value = null
                ElMessage.info(`已进入捕获模式（左键选中控件，${fmt(copyCombo.value)} 生成节点，${fmt(exitCombo.value)} 退出）`)
            }
        } catch (e) {
            ElMessage.error('进入捕获模式失败: ' + (e.message || ''))
        }
    }

    async function stopMode() {
        try {
            const res = await uiControlApi.modeControl('stop')
            active.value = !!res?.active
        } catch { /* 静默 */ }
    }

    function stopAll() {
        // ⚡ 关闭面板一律无条件退出捕获模式（后端幂等）——
        // 即使 SSE 状态未同步（active 显示 false），也要保证所有高亮框被清除
        uiControlApi.modeControl('stop').catch(() => {})
        active.value = false
        control.value = {}
        lastResult.value = null
        nodeCreatedTip.value = false
    }

    // 模式退出：清空面板信息（高亮由后端统一清理）
    watch(active, (val) => {
        if (!val) {
            control.value = {}
            lastResult.value = null
            nodeCreatedTip.value = false
        }
    })

    watch(dialogVisible, (visible) => {
        if (visible) {
            loadHotkeysIfNeeded()
            // ⚡ 打开时一次性获取当前模式状态（SSE 已推送过的历史事件不重放）
            uiControlApi.mode().then(res => {
                if (res?.success) {
                    active.value = !!res.active
                    if (res.hotkey_ok !== undefined) hotkeyOk.value = !!res.hotkey_ok
                }
            }).catch(() => {})
        } else {
            stopAll()
        }
    }, { immediate: true })

    onUnmounted(stopAll)
</script>

<style scoped>
    .ctrl-capture-body { display: flex; flex-direction: column; gap: 10px; max-height: 60vh; overflow-y: auto; }
    .capture-tip { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.6;
                   padding: 8px 10px; border-radius: 8px; background: rgba(0,188,212,.08);
                   border: 1px solid rgba(0,188,212,.25); }
    .mode-status { display: flex; align-items: center; gap: 6px; font-size: 12px;
                   color: var(--el-text-color-secondary); padding: 6px 10px; border-radius: 6px;
                   background: var(--el-fill-color-lighter); }
    .mode-status.is-active { color: #00e5ff; background: rgba(0,229,255,.1); }
    .mode-status.is-down { color: #f56c6c; background: rgba(245,108,108,.1); }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--el-text-color-placeholder); }
    .mode-status.is-active .status-dot { background: #00e5ff; box-shadow: 0 0 6px #00e5ff; }
    .mode-status.is-down .status-dot { background: #f56c6c; }
    .hotkey-warn { margin-left: auto; font-size: 11px; color: #e6a23c; }

    .hotkey-list { border: 1px solid var(--el-border-color-lighter); border-radius: 8px;
                   padding: 6px 10px; display: flex; flex-direction: column; gap: 5px; }
    .hk-row { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--el-text-color-regular); }
    .hk-row span { margin-left: 6px; color: var(--el-text-color-secondary); }
    .hk-row.hint { font-size: 11px; color: var(--el-text-color-placeholder); }
    kbd { font-family: Consolas, monospace; font-size: 11px; background: var(--el-fill-color-lighter);
          border: 1px solid var(--el-border-color); border-radius: 4px; padding: 1px 5px;
          color: var(--el-color-primary); }

    .capture-list { border: 1px solid var(--el-border-color-lighter); border-radius: 8px; overflow: hidden; }
    .capture-result { border: 1px solid var(--el-border-color-lighter); border-radius: 8px; overflow: hidden; }
    .res-header { padding: 6px 10px; font-size: 12px; font-weight: 600; color: var(--el-text-color-regular);
                  border-bottom: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-lighter); }
    .cap-row { display: flex; align-items: center; gap: 10px; padding: 5px 10px; font-size: 12px;
               border-bottom: 1px solid rgba(255,255,255,.05); }
    .cap-row:last-child { border-bottom: none; }
    .cap-label { flex-shrink: 0; width: 68px; color: var(--el-text-color-secondary); }
    .cap-value { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
                 color: var(--el-text-color-regular); }
    .cap-value.mono { font-family: Consolas, monospace; color: #00bcd4; }
    .sel-code { flex: 1; min-width: 0; font-family: Consolas, monospace; font-size: 11px;
                background: var(--el-fill-color-lighter); border: 1px dashed var(--el-border-color);
                border-radius: 4px; padding: 2px 6px; overflow: hidden; text-overflow: ellipsis;
                white-space: nowrap; color: var(--el-color-primary); }
</style>
