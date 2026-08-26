<template>
    <el-dialog v-model="visible" title="开始逐帧录制" width="520px" :close-on-click-modal="false">
        <el-form label-position="top" class="recording-form">
            <el-form-item label="录制策略">
                <el-radio-group v-model="form.recording_mode" class="mode-group">
                    <el-radio-button value="lossless_all_frames">全部原始帧</el-radio-button>
                    <el-radio-button value="changed_frames">仅变化帧</el-radio-button>
                    <el-radio-button value="diagnostic_events">变化与标记</el-radio-button>
                </el-radio-group>
                <div class="field-help">全部原始帧最适合抢票、限时活动等无法重现的完整操作录制；系统不会自动删除旧帧。</div>
            </el-form-item>
            <div class="form-grid">
                <el-form-item label="目标帧率">
                    <el-select v-model="form.target_fps">
                        <el-option label="不限速" :value="0" />
                        <el-option v-for="fps in [10, 20, 30, 60]" :key="fps" :label="`${fps} FPS`" :value="fps" />
                    </el-select>
                </el-form-item>
                <el-form-item label="会话空间上限">
                    <el-select v-model="quotaMb">
                        <el-option label="不限制" :value="0" />
                        <el-option label="512 MB" :value="512" />
                        <el-option label="1 GB" :value="1024" />
                        <el-option label="2 GB" :value="2048" />
                        <el-option label="5 GB" :value="5120" />
                    </el-select>
                </el-form-item>
            </div>
            <el-form-item v-if="form.recording_mode !== 'lossless_all_frames'" label="变化敏感度">
                <el-slider v-model="sensitivity" :min="1" :max="20" show-input />
                <div class="field-help">数值越高，越细微的画面变化也会保存。标记模式下可在录制状态栏手动保留关键帧。</div>
            </el-form-item>
            <div class="safety-note">
                捕获与 PNG 写盘使用独立线程和有界队列；磁盘不足、达到配额或连续截图失败时会安全停止，已写入的帧保持可用。
            </div>
        </el-form>
        <template #footer>
            <el-button @click="visible = false">取消</el-button>
            <el-button type="primary" :loading="busy" @click="submit">开始录制</el-button>
        </template>
    </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'

const props = defineProps({ modelValue: Boolean, busy: Boolean })
const emit = defineEmits(['update:modelValue', 'confirm'])
const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const quotaMb = ref(0)
const sensitivity = ref(10)
const form = reactive({ recording_mode: 'lossless_all_frames', target_fps: 0, queue_capacity: 96 })

const submit = () => emit('confirm', {
    ...form,
    max_session_bytes: quotaMb.value * 1024 * 1024,
    // Higher sensitivity means a lower difference threshold.
    change_threshold: Number((0.021 - sensitivity.value * 0.001).toFixed(4))
})
</script>

<style scoped>
.recording-form { padding: 0 4px; }
.mode-group { display: flex; width: 100%; }
.mode-group :deep(.el-radio-button) { flex: 1; }
.mode-group :deep(.el-radio-button__inner) { width: 100%; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.field-help { margin-top: 7px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.55; }
.safety-note { padding: 10px 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 7px; background: var(--el-fill-color-light); color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.6; }
</style>
