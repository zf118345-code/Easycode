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
                    <el-radio value="android">Android 设备</el-radio>
                    <el-radio value="desktop">全桌面模式</el-radio>
                </el-radio-group>
            </el-form-item>

            <!-- 2. 指定窗口模式下的参数 -->
            <template v-if="localContext.workMode === 'window'">
                <el-form-item label="窗口标题">
                    <el-select
v-model="localContext.windowHwnd"
                               filterable
                               default-first-option
                               placeholder="请选择具体窗口实例"
                               style="width: 100%;"
                               @focus="fetchWindows"
                               @change="selectWindowInstance">
                        <el-option
v-for="w in windowList"
                                   :key="w.hwnd"
                                   :label="`${w.title} · PID ${w.process_id} · HWND ${w.hwnd}`"
                                   :value="w.hwnd" />
                    </el-select>
                    <div class="setting-tip">
                        <Lightbulb :size="12" style="vertical-align: middle;" /> 绑定具体句柄和进程，避免多开同名窗口串实例。
                    </div>
                </el-form-item>

                <el-form-item label="模拟器模式">
                    <el-switch v-model="localContext.isEmulator" />
                </el-form-item>

                <el-form-item v-if="localContext.isEmulator" label="ADB 设备（自动）">
                    <el-input
                        v-model="localContext.adbDeviceId"
                        readonly
                        :loading="adbResolving"
                        placeholder="选择窗口后自动识别" />
                    <div class="setting-tip">
                        根据当前窗口自动匹配唯一设备；无法唯一识别时会退出模拟器模式，防止点错实例。
                    </div>
                </el-form-item>
            </template>

            <template v-if="localContext.workMode === 'android'">
                <el-form-item label="Android 设备">
                    <div class="android-device-row">
                        <el-select
                            v-model="localContext.adbDeviceId"
                            filterable
                            placeholder="请选择已授权设备"
                            style="flex: 1;"
                            :loading="devicesLoading"
                            @focus="fetchAdbDevices"
                            @change="selectAndroidDevice">
                            <el-option
                                v-for="device in adbDevices"
                                :key="device.serial"
                                :value="device.serial"
                                :disabled="device.state !== 'device'"
                                :label="`${device.model || device.serial} · ${device.serial} · ${device.state}`" />
                        </el-select>
                        <el-button :loading="devicesLoading" title="刷新设备" @click="fetchAdbDevices">
                            <RefreshCw :size="14" />
                        </el-button>
                    </div>
                    <div class="setting-tip">
                        真机和模拟器都直接通过 ADB 绑定，不需要对应的 Windows 窗口；未授权设备不会允许运行。
                    </div>
                </el-form-item>
                <el-form-item label="运行能力">
                    <div class="android-capability">
                        <Smartphone :size="14" />
                        <span>{{ selectedAndroidCapability }}</span>
                    </div>
                </el-form-item>
            </template>

            <!-- 3. 通用裁剪参数 -->
            <el-form-item v-if="localContext.workMode !== 'android'" label="裁剪 (T,B,L,R)">
                <div style="display: flex; gap: 6px;">
                    <el-input-number v-model="localContext.offsetTop" :min="0" controls-position="right" style="width:80px;" />
                    <el-input-number v-model="localContext.offsetBottom" :min="0" controls-position="right" style="width:80px;" />
                    <el-input-number v-model="localContext.offsetLeft" :min="0" controls-position="right" style="width:80px;" />
                    <el-input-number v-model="localContext.offsetRight" :min="0" controls-position="right" style="width:80px;" />
                </div>
            </el-form-item>

            <!-- 4. 目标尺寸设置 -->
            <template v-if="localContext.workMode === 'window' || localContext.workMode === 'android'">
                <el-form-item label="目标尺寸(宽×高)">
                    <div class="dimension-box">
                        <el-input-number v-model="localContext.targetContentWidth" :min="0" placeholder="0为不修改" style="width:110px;" />
                        <span class="dimension-cross">×</span>
                        <el-input-number v-model="localContext.targetContentHeight" :min="0" placeholder="0为不修改" style="width:110px;" />
                    </div>
                    <div class="setting-tip">
                        {{ localContext.workMode === 'android' ? '设为 0 自动使用设备当前画面尺寸' : '设为0代表不强制调整窗口大小' }}
                    </div>
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
    import { ElMessage } from 'element-plus'
    import { useIdeStore } from '@/stores'
    import { workspaceApi } from '@/api/workspaceApi'
    import { Lightbulb, RefreshCw, Smartphone } from 'lucide-vue-next'

    const props = defineProps({
        visible: { type: Boolean, default: false }
    })

    const emit = defineEmits(['update:visible', 'apply'])

    const store = useIdeStore()

    const localContext = ref({
        workMode: 'window',
        windowTitle: '',
        windowHwnd: 0,
        windowProcessId: 0,
        windowClassName: '',
        isEmulator: false,
        isAndroid: false,
        adbDeviceId: '',
        offsetTop: 0,
        offsetBottom: 0,
        offsetLeft: 0,
        offsetRight: 0,
        targetContentWidth: 0,
        targetContentHeight: 0
    })

    const windowList = ref([])
    const adbDevices = ref([])
    const adbResolving = ref(false)
    const devicesLoading = ref(false)

    const selectedAndroidCapability = computed(() => {
        const device = adbDevices.value.find(item => item.serial === localContext.value.adbDeviceId)
        if (!device) return '请选择设备后查看能力'
        if (device.state !== 'device') return `设备状态：${device.state}，当前不可运行`
        return `Android ${device.android_version || '未知'} · ${device.width || '?'}×${device.height || '?'} · scrcpy持续采帧 / 后台触控（运行前自检）`
    })

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
                windowHwnd: Number(ctx.windowHwnd || 0),
                windowProcessId: Number(ctx.windowProcessId || 0),
                windowClassName: ctx.windowClassName || '',
                isEmulator: ctx.isEmulator || false,
                isAndroid: ctx.isAndroid || ctx.workMode === 'android',
                adbDeviceId: ctx.adbDeviceId || '',
                offsetTop: ctx.offsetTop || 0,
                offsetBottom: ctx.offsetBottom || 0,
                offsetLeft: ctx.offsetLeft || 0,
                offsetRight: ctx.offsetRight || 0,
                targetContentWidth: ctx.targetContentWidth || 0,
                targetContentHeight: ctx.targetContentHeight || 0
            }
            fetchWindows()
            fetchAdbDevices()
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

    const fetchAdbDevices = async () => {
        devicesLoading.value = true
        try {
            const result = await workspaceApi.getAdbDevices()
            adbDevices.value = result.devices || []
        } catch (error) {
            adbDevices.value = []
            ElMessage.error(error.response?.data?.detail || error.message || '无法枚举 Android 设备')
        } finally {
            devicesLoading.value = false
        }
    }

    const selectAndroidDevice = serial => {
        const device = adbDevices.value.find(item => item.serial === serial)
        if (!device) return
        if (!localContext.value.targetContentWidth && device.width) localContext.value.targetContentWidth = device.width
        if (!localContext.value.targetContentHeight && device.height) localContext.value.targetContentHeight = device.height
    }

    const selectWindowInstance = async (hwnd) => {
        const selected = windowList.value.find(w => Number(w.hwnd) === Number(hwnd))
        if (!selected) return
        localContext.value.windowTitle = selected.title
        localContext.value.windowHwnd = Number(selected.hwnd)
        localContext.value.windowProcessId = Number(selected.process_id || 0)
        localContext.value.windowClassName = selected.class_name || ''
        if (localContext.value.isEmulator) await resolveAdbForSelectedWindow()
    }

    const resolveAdbForSelectedWindow = async () => {
        if (!localContext.value.isEmulator) {
            localContext.value.adbDeviceId = ''
            return false
        }
        if (!localContext.value.windowTitle || !localContext.value.windowHwnd) {
            localContext.value.isEmulator = false
            localContext.value.adbDeviceId = ''
            ElMessage.warning('请先选择模拟器窗口，再开启模拟器模式')
            return false
        }
        adbResolving.value = true
        try {
            const result = await workspaceApi.resolveAdbDevice({
                windowTitle: localContext.value.windowTitle,
                windowHwnd: localContext.value.windowHwnd,
                processId: localContext.value.windowProcessId
            })
            localContext.value.adbDeviceId = result.serial || ''
            return Boolean(localContext.value.adbDeviceId)
        } catch (error) {
            localContext.value.isEmulator = false
            localContext.value.adbDeviceId = ''
            ElMessage.error(error.response?.data?.detail || error.message || '无法自动识别模拟器 ADB 设备')
            return false
        } finally {
            adbResolving.value = false
        }
    }

    watch(() => localContext.value.isEmulator, async (enabled, previous) => {
        if (enabled && !previous) await resolveAdbForSelectedWindow()
        if (!enabled) localContext.value.adbDeviceId = ''
    })

    const applyContext = async () => {
        if (localContext.value.workMode === 'android') {
            localContext.value.windowTitle = ''
            localContext.value.windowHwnd = 0
            localContext.value.windowProcessId = 0
            localContext.value.windowClassName = ''
            localContext.value.isEmulator = false
            localContext.value.isAndroid = true
            if (!localContext.value.adbDeviceId.trim()) {
                ElMessage.warning('请选择已授权的 Android 设备')
                return
            }
        } else if (localContext.value.workMode === 'desktop') {
            localContext.value.windowTitle = ''
            localContext.value.windowHwnd = 0
            localContext.value.windowProcessId = 0
            localContext.value.windowClassName = ''
            localContext.value.isEmulator = false
            localContext.value.isAndroid = false
            localContext.value.adbDeviceId = ''
        } else if (!localContext.value.windowTitle || !localContext.value.windowHwnd) {
            ElMessage.warning('请选择具体窗口实例')
            return
        } else if (localContext.value.isEmulator && !localContext.value.adbDeviceId.trim()) {
            if (!await resolveAdbForSelectedWindow()) return
        }
        if (localContext.value.workMode === 'window') localContext.value.isAndroid = false
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

    .android-device-row {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 100%;
    }

    .android-capability {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        color: var(--el-text-color-regular);
        font-size: 12px;
    }

    .dimension-cross {
        color: var(--el-text-color-secondary);
        font-weight: bold;
    }
</style>
