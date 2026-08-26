<template>
    <el-dialog
        v-model="visible"
        :title="title || '更换识别图片'"
        width="560px"
        append-to-body
        :close-on-click-modal="false"
        @opened="focusPasteArea">
        <div
            ref="pasteAreaRef"
            class="capture-paste-area"
            tabindex="0"
            @paste="handlePaste">
            <img v-if="preview" :src="preview" class="capture-preview" alt="截图预览" />
            <div v-else class="capture-empty">
                <ImageIcon :size="34" />
                <strong>使用 Windows 截图后粘贴到这里</strong>
                <span>点击“系统截图”，框选目标区域，返回后按 Ctrl+V</span>
            </div>
        </div>
        <input ref="fileInputRef" class="hidden-file" type="file" accept="image/png,image/jpeg,image/webp" @change="handleFileInput" />
        <div class="capture-actions">
            <el-button type="primary" :loading="launching" @click="launchSnipping"><Camera :size="15" /> 系统截图</el-button>
            <el-button @click="readClipboard"><ClipboardPaste :size="15" /> 读取剪贴板</el-button>
            <el-button @click="fileInputRef?.click()"><Upload :size="15" /> 选择图片</el-button>
            <el-button v-if="preview" text type="danger" @click="preview = ''">清空</el-button>
        </div>
        <template #footer>
            <el-button @click="visible = false">取消</el-button>
            <el-button type="primary" :disabled="!preview" @click="confirm"><Check :size="15" /> 使用此图片</el-button>
        </template>
    </el-dialog>
</template>

<script setup>
    import { computed, nextTick, ref } from 'vue'
    import { ElMessage } from 'element-plus'
    import { Camera, Check, ClipboardPaste, Image as ImageIcon, Upload } from 'lucide-vue-next'
    import client from '@/api/client'

    const props = defineProps({
        modelValue: { type: Boolean, default: false },
        title: { type: String, default: '' }
    })
    const emit = defineEmits(['update:modelValue', 'confirm'])
    const visible = computed({
        get: () => props.modelValue,
        set: value => emit('update:modelValue', value)
    })
    const preview = ref('')
    const launching = ref(false)
    const pasteAreaRef = ref(null)
    const fileInputRef = ref(null)

    const focusPasteArea = () => nextTick(() => pasteAreaRef.value?.focus())

    const loadBlob = blob => {
        if (!blob?.type?.startsWith('image/')) return ElMessage.warning('剪贴板中没有图片')
        if (blob.size > 16 * 1024 * 1024) return ElMessage.error('图片不能超过 16MB')
        const reader = new FileReader()
        reader.onload = () => { preview.value = String(reader.result || '') }
        reader.onerror = () => ElMessage.error('读取图片失败')
        reader.readAsDataURL(blob)
    }

    const handlePaste = event => {
        const item = [...(event.clipboardData?.items || [])].find(entry => entry.type.startsWith('image/'))
        if (!item) return ElMessage.warning('剪贴板中没有图片，请先完成系统截图')
        event.preventDefault()
        loadBlob(item.getAsFile())
    }

    const handleFileInput = event => {
        loadBlob(event.target?.files?.[0])
        event.target.value = ''
    }

    const launchSnipping = async () => {
        launching.value = true
        try {
            await client.post('/api/player/screen-snipping')
            ElMessage.info('框选完成后返回 Player，按 Ctrl+V 粘贴截图')
        } catch (error) {
            ElMessage.error(error?.message || '无法启动系统截图工具')
        } finally {
            launching.value = false
            focusPasteArea()
        }
    }

    const readClipboard = async () => {
        try {
            const items = await navigator.clipboard.read()
            for (const item of items) {
                const type = item.types.find(value => value.startsWith('image/'))
                if (type) {
                    loadBlob(await item.getType(type))
                    return
                }
            }
            ElMessage.warning('剪贴板中没有图片')
        } catch {
            ElMessage.warning('浏览器未授权直接读取，请在预览区域按 Ctrl+V')
            focusPasteArea()
        }
    }

    const confirm = () => {
        if (!preview.value) return
        emit('confirm', preview.value)
        visible.value = false
    }
</script>

<style scoped>
    .capture-paste-area {
        min-height: 270px;
        border: 1px dashed var(--el-border-color);
        border-radius: var(--app-radius-md, 10px);
        background: var(--el-fill-color-light);
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        outline: none;
    }
    .capture-paste-area:focus { border-color: var(--el-color-primary); }
    .capture-preview { max-width: 100%; max-height: 360px; object-fit: contain; }
    .capture-empty { display: flex; flex-direction: column; align-items: center; gap: 8px; color: var(--el-text-color-secondary); }
    .capture-empty strong { color: var(--el-text-color-primary); }
    .capture-empty span { font-size: 12px; }
    .capture-actions { display: flex; align-items: center; gap: 6px; margin-top: 12px; }
    .hidden-file { display: none; }
</style>
