<!-- frontend/src/components/HotkeySettingsDialog.vue
  全局快捷键设置（顶部「编辑 (E) → 快捷键设置」）：
  - 列出系统全局快捷键（进入捕获 / 复制生成 / 退出模式）
  - 点击「修改」进入按键录制（捕获按下的组合键）；保存 → 后端重注册 + 冲突检测
-->
<template>
    <el-dialog
        v-model="dialogVisible"
        title="快捷键设置"
        width="520px"
        append-to-body
        :close-on-click-modal="false">
        <div class="hk-settings-body">
            <div class="hk-tip">
                以下为<b>系统全局快捷键</b>（注册到 Windows，其他软件在前台也生效）。
                冲突检测：保存时会尝试注册，若组合键已被其他软件占用会明确提示。
            </div>

            <div class="hk-table">
                <div class="hk-row hk-head">
                    <span class="c-feature">功能</span>
                    <span class="c-combo">快捷键</span>
                    <span class="c-action">操作</span>
                </div>
                <div v-for="item in hotkeyItems" :key="item.key" class="hk-row">
                    <span class="c-feature">{{ item.label }}</span>
                    <span class="c-combo">
                        <template v-if="recordingKey === item.key">
                            <kbd class="recording">{{ pendingCombo || '请按下组合键…' }}</kbd>
                        </template>
                        <template v-else>
                            <kbd v-for="(part, i) in item.combo.split('+')" :key="i">{{ part }}</kbd>
                        </template>
                    </span>
                    <span class="c-action">
                        <el-button
                            v-if="recordingKey !== item.key"
                            size="small" @click="startRecord(item.key)">修改</el-button>
                        <template v-else>
                            <el-button size="small" type="primary" @click="applyCurrent">应用</el-button>
                            <el-button size="small" @click="cancelRecord">取消</el-button>
                        </template>
                    </span>
                </div>
            </div>

            <div v-if="conflictMsg" class="hk-conflict">
                ⚠️ {{ conflictMsg }}
            </div>
            <div v-if="savedMsg" class="hk-saved">✔ {{ savedMsg }}</div>
            <div class="hk-fixed-hint">{{ FIXED_HINT }}</div>
        </div>

        <template #footer>
            <el-button size="small" @click="dialogVisible = false">关闭</el-button>
        </template>
    </el-dialog>
</template>

<script setup>
    import { ref, computed, onMounted, onUnmounted } from 'vue'
    import { ElMessage } from 'element-plus'
    import { uiControlApi } from '@/api/uiControlApi'

    const props = defineProps({
        modelValue: { type: Boolean, default: false }
    })
    const emit = defineEmits(['update:modelValue'])

    const dialogVisible = computed({
        get: () => props.modelValue,
        set: (val) => emit('update:modelValue', val)
    })

    const FEATURES = [
        { key: 'enter_capture', label: '进入控件捕获模式' },
        { key: 'copy_generate', label: '复制选择器 + 生成控件节点' },
        { key: 'exit_mode', label: '退出捕获模式' }
    ]
    // ⚡ 识别 = 鼠标悬停 250ms 自动识别（无需快捷键）
    const FIXED_HINT = '识别控件：鼠标悬停目标 250ms 自动识别（无需快捷键）'

    const hotkeys = ref({ enter_capture: 'ctrl+shift+c', copy_generate: 'ctrl+shift+enter', exit_mode: 'esc' })
    const recordingKey = ref(null)
    const pendingCombo = ref('')
    const conflictMsg = ref('')
    const savedMsg = ref('')

    const hotkeyItems = computed(() => FEATURES.map(f => ({
        key: f.key,
        label: f.label,
        combo: recordingKey.value === f.key ? pendingCombo.value : (hotkeys.value[f.key] || '')
    })))

    async function load() {
        try {
            const res = await uiControlApi.getHotkeys()
            if (res?.hotkeys) hotkeys.value = { ...hotkeys.value, ...res.hotkeys }
        } catch { /* 静默 */ }
    }

    function startRecord(key) {
        recordingKey.value = key
        pendingCombo.value = ''
        conflictMsg.value = ''
        savedMsg.value = ''
    }

    function cancelRecord() {
        recordingKey.value = null
        pendingCombo.value = ''
    }

    // 按键录制：监听全局 keydown（弹窗打开时），忽略纯修饰键
    function onKeydown(e) {
        if (!recordingKey.value) return
        e.preventDefault()
        e.stopPropagation()
        const parts = []
        if (e.ctrlKey) parts.push('ctrl')
        if (e.shiftKey) parts.push('shift')
        if (e.altKey) parts.push('alt')
        if (e.metaKey) parts.push('win')
        const key = e.key.toLowerCase()
        // 忽略单独的修饰键
        if (['control', 'shift', 'alt', 'meta'].includes(key)) return
        if (key === 'escape') {
            parts.push('esc')
        } else if (key.length === 1 && /[a-z0-9]/.test(key)) {
            parts.push(key)
        } else {
            const map = { ' ': 'space', 'enter': 'enter', 'tab': 'tab', 'backspace': 'backspace',
                          'delete': 'delete', 'arrowup': 'up', 'arrowdown': 'down',
                          'arrowleft': 'left', 'arrowright': 'right', 'home': 'home', 'end': 'end',
                          'pageup': 'pgup', 'pagedown': 'pgdn',
                          'f1': 'f1', 'f2': 'f2', 'f3': 'f3', 'f4': 'f4', 'f5': 'f5', 'f6': 'f6',
                          'f7': 'f7', 'f8': 'f8', 'f9': 'f9', 'f10': 'f10', 'f11': 'f11', 'f12': 'f12' }
            const mapped = map[key] || `vk${e.keyCode}`
            parts.push(mapped)
        }
        pendingCombo.value = parts.length ? parts.join('+') : (parts.join('+') || '')
    }

    async function applyCurrent() {
        if (!recordingKey.value || !pendingCombo.value) return
        const key = recordingKey.value
        const combo = pendingCombo.value
        try {
            const res = await uiControlApi.putHotkeys({ [key]: combo })
            if (res?.ok) {
                hotkeys.value[key] = combo
                conflictMsg.value = ''
                savedMsg.value = `快捷键「${combo}」已保存并注册成功`
                ElMessage.success(`已更新 [${FEATURES.find(f => f.key === key).label}] = ${combo}`)
            } else {
                conflictMsg.value = res?.message || `应用「${combo}」失败（可能被其他软件占用）`
            }
        } catch (err) {
            conflictMsg.value = '保存失败: ' + (err?.message || err)
        }
        cancelRecord()
    }

    onMounted(() => window.addEventListener('keydown', onKeydown, true))
    onUnmounted(() => window.removeEventListener('keydown', onKeydown, true))
</script>

<style scoped>
    .hk-settings-body { display: flex; flex-direction: column; gap: 10px; }
    .hk-tip { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.6;
              padding: 8px 10px; border-radius: 8px; background: rgba(0,188,212,.08);
              border: 1px solid rgba(0,188,212,.25); }
    .hk-table { border: 1px solid var(--el-border-color-lighter); border-radius: 8px; overflow: hidden; }
    .hk-row { display: flex; align-items: center; gap: 10px; padding: 8px 12px;
              border-bottom: 1px solid rgba(255,255,255,.05); font-size: 12px; }
    .hk-row:last-child { border-bottom: none; }
    .hk-head { background: var(--el-fill-color-lighter); color: var(--el-text-color-secondary);
               font-weight: 600; }
    .c-feature { flex: 1; color: var(--el-text-color-regular); }
    .c-combo { flex: 1; display: flex; gap: 4px; flex-wrap: wrap; }
    .c-action { flex-shrink: 0; display: flex; gap: 6px; }
    kbd { font-family: Consolas, monospace; font-size: 11px; background: var(--el-fill-color-lighter);
          border: 1px solid var(--el-border-color); border-radius: 4px; padding: 1px 5px;
          color: var(--el-color-primary); }
    kbd.recording { color: #e6a23c; border-color: #e6a23c; animation: pulse 1s infinite; }
    @keyframes pulse { 50% { opacity: .4; } }
    .hk-conflict { font-size: 12px; color: #f56c6c; padding: 6px 10px; border-radius: 6px;
                   background: rgba(245,108,108,.1); }
    .hk-saved { font-size: 12px; color: #4ed19c; padding: 6px 10px; }
    .hk-fixed-hint { font-size: 12px; color: var(--el-text-color-secondary); padding: 6px 10px;
                     border-radius: 6px; background: rgba(78,209,156,.08); border: 1px solid rgba(78,209,156,.25); }
</style>
