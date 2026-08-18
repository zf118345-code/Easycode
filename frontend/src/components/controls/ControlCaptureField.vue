<!-- ControlCaptureField.vue：控件信息字段（只读 textarea 展示捕获的全部信息） + 「捕获控件/重置控件」按钮
  - 捕获控件：进入捕获模式（悬停自动识别），Ctrl+Shift+Enter 捕获后自动退出并回填
  - textarea 只读可赋值不可修改：展示 control_info（控件名称/类型/自动化ID/类名/窗口标题/坐标等）
  - 重置控件：清空控件信息（由上层监听 capture-reset 处理 control_info 清理）
  - 同时用于条件对话框（条件 payload 的 target 字段），填充目标由注册的 captureFillHandler 决定
-->
<template>
    <div class="capture-field">
        <el-input
            :model-value="displayText"
            type="textarea"
            :rows="5"
            readonly
            resize="none"
            placeholder="点击「捕获控件」自动填入控件信息"
            class="capture-info-textarea" />
        <div class="capture-btns">
            <button type="button" class="app-btn-secondary" :disabled="capturing" @click="startCapture">
                <component :is="ScanSearch" class="app-btn-icon" />
                <span>{{ capturing ? '捕获中…' : '捕获控件' }}</span>
            </button>
            <button type="button" class="app-btn-secondary" :disabled="!modelValue" @click="handleReset">
                <component :is="RotateCcw" class="app-btn-icon" />
                <span>重置控件</span>
            </button>
        </div>
    </div>
</template>

<script setup>
    import { ref, computed, onUnmounted } from 'vue'
    import { ScanSearch, RotateCcw } from 'lucide-vue-next'
    import { useUiStore } from '@/stores'
    import { uiControlApi } from '@/api/uiControlApi'
    import { buildControlParamsFromInfo, formatControlInfo } from '@/utils/captureNode'

    const props = defineProps({
        config: { type: Object, default: () => ({}) },
        modelValue: { required: false },
        context: { type: Object, default: () => ({}) }
    })
    const emit = defineEmits(['update:modelValue', 'capture-reset'])

    const uiStore = useUiStore()
    const capturing = ref(false)

    // ⚡ 只读展示捕获到的全部控件信息（数据源：context.control_info；旧节点无 control_info 时兜底显示名称）
    const displayText = computed(() => formatControlInfo(props.context?.control_info, props.modelValue))

    // ⚡ 捕获成功后回填本字段：注册填充回调（由全局捕获链路在 Ctrl+Shift+Enter 后调用）
    // 回写内容：target（展示名称）+ by/window_title/index/control_info（存储到 context=节点/条件参数对象）
    function startCapture() {
        uiStore.setCaptureFillHandler((info) => {
            const params = buildControlParamsFromInfo(info || {})
            const ctx = props.context || {}
            if (ctx && typeof ctx === 'object') {
                ctx.by = params.by
                ctx.window_title = String(info?.window_title || '')
                ctx.index = info?.index ?? 0
                ctx.control_info = info || null
            }
            emit('update:modelValue', params.target)
            capturing.value = false
        })
        capturing.value = true
        uiControlApi.modeControl('start').catch(() => {
            capturing.value = false
            uiStore.clearCaptureFillHandler()
        })
    }

    function handleReset() {
        emit('update:modelValue', '')
        emit('capture-reset')
    }

    onUnmounted(() => {
        // 组件销毁（如条件对话框关闭）：若仍持有本组件的填充回调则清空，防悬挂
        if (uiStore.captureFillHandler) uiStore.clearCaptureFillHandler()
    })
</script>

<style scoped>
    .capture-field {
        display: flex;
        flex-direction: column;
        gap: 6px;
        width: 100%;
    }

    .capture-btns {
        display: flex;
        gap: 6px;
    }

    .capture-info-textarea {
        width: 100%;
    }

        .capture-info-textarea :deep(.el-textarea__inner) {
            color: var(--el-text-color-secondary);
            background: var(--el-fill-color-lighter);
            cursor: default;
            font-family: Consolas, monospace;
            font-size: 12px;
            line-height: 1.6;
            resize: none;
        }
</style>
