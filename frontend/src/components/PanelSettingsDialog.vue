<!-- frontend/src/components/PanelSettingsDialog.vue -->
<template>
    <el-dialog
v-model="dialogVisible"
               title="工作面板设置"
               width="520px"
               append-to-body
               :close-on-click-modal="false"
               @close="onClose">
        <el-form :model="localContext" label-width="120px" size="small">
            <!-- 1. 工作模式选择 -->
            <el-form-item label="工作模式">
                <el-radio-group v-model="localContext.workMode">
                    <el-radio value="window">指定窗口/模拟器</el-radio>
                    <el-radio value="desktop">全桌面模式</el-radio>
                </el-radio-group>
            </el-form-item>

            <!-- 2. 指定窗口模式下的参数 -->
            <template v-if="localContext.workMode === 'window'">
                <el-form-item label="窗口标题">
                    <el-select
v-model="localContext.windowTitle"
                               filterable
                               allow-create
                               default-first-option
                               placeholder="下拉选择或手动输入窗口标题"
                               style="width: 100%;"
                               @focus="fetchWindows">
                        <el-option
v-for="w in windowList"
                                   :key="w.hwnd"
                                   :label="w.title"
                                   :value="w.title" />
                    </el-select>
                    <div class="setting-tip">
                        💡 提示：已被最小化的窗口不会列出，请先还原窗口。
                    </div>
                </el-form-item>

                <el-form-item label="模拟器模式">
                    <el-switch v-model="localContext.isEmulator" />
                </el-form-item>
            </template>

            <!-- 3. 通用裁剪参数 -->
            <el-form-item label="裁剪 (T,B,L,R)">
                <div style="display: flex; gap: 6px;">
                    <el-input-number v-model="localContext.offsetTop" :min="0" controls-position="right" style="width:80px;" />
                    <el-input-number v-model="localContext.offsetBottom" :min="0" controls-position="right" style="width:80px;" />
                    <el-input-number v-model="localContext.offsetLeft" :min="0" controls-position="right" style="width:80px;" />
                    <el-input-number v-model="localContext.offsetRight" :min="0" controls-position="right" style="width:80px;" />
                </div>
            </el-form-item>

            <!-- 4. 目标尺寸设置 -->
            <template v-if="localContext.workMode === 'window'">
                <el-form-item label="目标尺寸(宽×高)">
                    <div class="dimension-box">
                        <el-input-number v-model="localContext.targetContentWidth" :min="0" placeholder="0为不修改" style="width:110px;" />
                        <span class="dimension-cross">×</span>
                        <el-input-number v-model="localContext.targetContentHeight" :min="0" placeholder="0为不修改" style="width:110px;" />
                    </div>
                    <div class="setting-tip">(设为0代表不强制调整窗口大小)</div>
                </el-form-item>
            </template>
        </el-form>

        <template #footer>
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" @click="applyContext">应用</el-button>
        </template>
    </el-dialog>
</template>

<script setup>
    import { ref, watch, computed } from 'vue'
    import { useMainStore } from '@/stores'
    import { workspaceApi } from '@/api/workspaceApi'

    const props = defineProps({
        visible: { type: Boolean, default: false }
    })

    const emit = defineEmits(['update:visible', 'apply'])

    const store = useMainStore()

    const localContext = ref({
        workMode: 'window',
        windowTitle: '',
        isEmulator: false,
        offsetTop: 0,
        offsetBottom: 0,
        offsetLeft: 0,
        offsetRight: 0,
        targetContentWidth: 0,
        targetContentHeight: 0
    })

    const windowList = ref([])

    const dialogVisible = computed({
        get: () => props.visible,
        set: (val) => emit('update:visible', val)
    })

    watch(() => props.visible, (val) => {
        if (val) {
            const ctx = store.currentContext
            localContext.value = {
                workMode: ctx.workMode || (ctx.windowTitle ? 'window' : 'desktop'),
                windowTitle: ctx.windowTitle || '',
                isEmulator: ctx.isEmulator || false,
                offsetTop: ctx.offsetTop || 0,
                offsetBottom: ctx.offsetBottom || 0,
                offsetLeft: ctx.offsetLeft || 0,
                offsetRight: ctx.offsetRight || 0,
                targetContentWidth: ctx.targetContentWidth || 0,
                targetContentHeight: ctx.targetContentHeight || 0
            }
            fetchWindows()
        }
    })

    const fetchWindows = async () => {
        try {
            const res = await workspaceApi.getWindows()
            windowList.value = res.windows || []
        } catch (err) {
            console.error('获取窗口列表失败', err)
        }
    }

    const applyContext = () => {
        if (localContext.value.workMode === 'desktop') {
            localContext.value.windowTitle = ''
            localContext.value.isEmulator = false
        }
        emit('apply', localContext.value)
        dialogVisible.value = false
    }

    const onClose = () => {
        dialogVisible.value = false
    }
</script>

<style scoped>
    .setting-tip {
        font-size: 11px;
        color: var(--el-text-color-secondary);
        margin-top: 4px;
        line-height: 1.3;
    }

    .dimension-box {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .dimension-cross {
        color: var(--el-text-color-secondary);
        font-weight: bold;
    }
</style>